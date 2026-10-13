"""Network, encryption key, database and secrets for one cell (long-lived; app stacks come and go)."""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as sm
from constructs import Construct

from vanimo_infra.config import DeployConfig


class DataStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, cfg: DeployConfig, **kw) -> None:
        super().__init__(scope, cid, **kw)
        # Snapshot applies to the database only; secrets support just Retain/Delete.
        retain = RemovalPolicy.RETAIN if cfg.is_prod else RemovalPolicy.SNAPSHOT
        secret_policy = RemovalPolicy.RETAIN if cfg.is_prod else RemovalPolicy.DESTROY

        # One customer-managed key for the cell's data. Per-tenant keys arrive with external tenants.
        self.key = kms.Key(
            self,
            "DataKey",
            alias=f"alias/vanimo-{cfg.cell}-{cfg.env_name}-data",
            enable_key_rotation=True,
            description="Vanimo cell data key (database, secrets, logs)",
            removal_policy=RemovalPolicy.RETAIN,
        )
        self.key.grant_encrypt_decrypt(
            # CloudWatch Logs must use the key to encrypt log groups.
            _logs_principal(self.region)
        )

        # Public subnets only hold the NAT gateway (fixed egress IP for Graph + Bedrock);
        # the API runs in private subnets; the database in isolated subnets with no route out.
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="app", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=22),
                ec2.SubnetConfiguration(name="data", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24),
            ],
            flow_logs={
                "rejects": ec2.FlowLogOptions(
                    destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                        logs.LogGroup(
                            self,
                            "FlowLogs",
                            retention=logs.RetentionDays.ONE_MONTH,
                            encryption_key=self.key,
                            removal_policy=RemovalPolicy.DESTROY,
                        )
                    ),
                    traffic_type=ec2.FlowLogTrafficType.REJECT,
                )
            },
        )
        self.vpc.add_gateway_endpoint("S3", service=ec2.GatewayVpcEndpointAwsService.S3)
        for name, svc in (
            ("SecretsManager", ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER),
            ("EcrApi", ec2.InterfaceVpcEndpointAwsService.ECR),
            ("EcrDocker", ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER),
            ("Logs", ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS),
            ("Kms", ec2.InterfaceVpcEndpointAwsService.KMS),
        ):
            self.vpc.add_interface_endpoint(
                name, service=svc, subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
            )

        self.db_sg = ec2.SecurityGroup(self, "DbSg", vpc=self.vpc, description="Aurora", allow_all_outbound=False)

        # Content-free database logs: no statement text on errors, no connection details.
        params = rds.ParameterGroup(
            self,
            "DbParams",
            engine=_engine(),
            parameters={
                "log_min_error_statement": "panic",
                "log_error_verbosity": "terse",
                "log_statement": "none",
                "rds.force_ssl": "1",
            },
        )
        self.db = rds.DatabaseCluster(
            self,
            "Db",
            engine=_engine(),
            parameter_group=params,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[self.db_sg],
            writer=rds.ClusterInstance.serverless_v2("writer", publicly_accessible=False),
            serverless_v2_min_capacity=0,  # scales to zero when idle (dev); resumes in ~15 s
            serverless_v2_max_capacity=4,
            credentials=rds.Credentials.from_generated_secret("vanimo_admin", encryption_key=self.key),
            storage_encrypted=True,
            storage_encryption_key=self.key,
            default_database_name="postgres",
            backup=rds.BackupProps(retention=Duration.days(7 if not cfg.is_prod else 30)),
            deletion_protection=cfg.is_prod,
            removal_policy=retain,
            iam_authentication=False,
        )

        def generated(name: str, length: int) -> sm.Secret:
            return sm.Secret(
                self,
                name,
                encryption_key=self.key,
                generate_secret_string=sm.SecretStringGenerator(
                    password_length=length, exclude_punctuation=True, include_space=False
                ),
                removal_policy=secret_policy,
            )

        self.owner_password = generated("DbOwnerPassword", 40)
        self.app_password = generated("DbAppPassword", 40)
        self.ref_hmac_key = generated("RefHmacKey", 64)
        # Placeholder: set the real value from the Entra app registration after the first deploy
        # (aws secretsmanager put-secret-value ...; see app/README.md).
        self.entra_client_secret = sm.Secret(
            self,
            "EntraClientSecret",
            encryption_key=self.key,
            description="Vanimo Entra app client secret (set manually; never in code)",
            removal_policy=secret_policy,
        )


def _engine() -> rds.IClusterEngine:
    return rds.DatabaseClusterEngine.aurora_postgres(version=rds.AuroraPostgresEngineVersion.VER_18_4)


def _logs_principal(region: str):
    from aws_cdk import aws_iam as iam

    return iam.ServicePrincipal(f"logs.{region}.amazonaws.com")
