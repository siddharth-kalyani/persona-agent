"""The API (ECS Fargate behind an internal ALB), the web app (S3 + CloudFront) and the migration task.

Traffic: browser → CloudFront (HTTPS, *.cloudfront.net) → /api/* over a CloudFront VPC origin to an
internal ALB → Fargate. Nothing in the VPC is reachable from the internet except through CloudFront.
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudfront as cf
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_secretsmanager as sm
from constructs import Construct

from vanimo_infra.config import DeployConfig
from vanimo_infra.data_stack import DataStack

API_PORT = 8000

# Main web app: same-origin API, Entra sign-in redirects only, no framing (the Teams dialog and tab use /teams.html, M5).
WEB_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self' https://login.microsoftonline.com; frame-src 'self' https://login.microsoftonline.com; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
# MSAL v5 redirect bridge (/redirect.html): loaded in a hidden same-origin iframe for silent token
# renewal and in popups, so it may be framed by our own origin only.
BRIDGE_CSP = (
    "default-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "frame-ancestors 'self'"
)
# Outlook add-in task pane: Office.js from Microsoft's CDN and framing by Outlook hosts. Report-only
# until the add-in spike confirms the exact hosts on every Outlook client. The spike needs the Entra app
# and a deployed cell; enforce right after it.
ADDIN_CSP = (
    "default-src 'self'; script-src 'self' https://appsforoffice.microsoft.com; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self' https://login.microsoftonline.com; "
    "frame-src 'self' https://login.microsoftonline.com; object-src 'none'; base-uri 'self'"
)

# Teams dialog and personal tab (/teams.html, M5): TeamsJS is bundled, so only framing by Teams and
# Microsoft 365 hosts is added. Report-only, like the add-in, until the Teams spike confirms the hosts
# on every client; enforce right after it.
TEAMS_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "connect-src 'self' https://login.microsoftonline.com; frame-src 'self' https://login.microsoftonline.com; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'self' https://teams.microsoft.com "
    "https://*.teams.microsoft.com https://teams.cloud.microsoft https://*.cloud.microsoft https://*.office.com "
    "https://*.microsoft365.com"
)

SPA_REWRITE = """
function handler(event) {
  var req = event.request;
  // Client-side routes (no file extension) serve the SPA; real files and the API pass through.
  if (!req.uri.startsWith('/api/') && req.uri.indexOf('.') === -1) { req.uri = '/index.html'; }
  return req;
}
"""


class AppStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, cfg: DeployConfig, data: DataStack, **kw) -> None:
        super().__init__(scope, cid, **kw)

        # Reference the data stack's key and secrets by ARN: grants then land on this stack's IAM roles
        # (the key policy delegates to IAM) instead of editing the data stack, which would create a cycle.
        key = kms.Key.from_key_arn(self, "DataKeyRef", data.key.key_arn)

        def secret(name: str, s: sm.ISecret) -> sm.ISecret:
            return sm.Secret.from_secret_complete_arn(self, name, s.secret_arn)

        # The secrets are encrypted with the cell CMK. ECS fetches them at task start with the
        # execution role, which therefore needs kms:Decrypt — only via Secrets Manager. (CDK can't
        # add this through an imported key, so it is granted explicitly below.)
        decrypt_secrets = iam.PolicyStatement(
            actions=["kms:Decrypt"],
            resources=[data.key.key_arn],
            conditions={"StringEquals": {"kms:ViaService": f"secretsmanager.{cfg.region}.amazonaws.com"}},
        )

        app_password = secret("DbAppPasswordRef", data.app_password)
        owner_password = secret("DbOwnerPasswordRef", data.owner_password)
        ref_hmac_key = secret("RefHmacKeyRef", data.ref_hmac_key)
        vault_master_key = secret("VaultMasterKeyRef", data.vault_master_key)
        entra_client_secret = secret("EntraClientSecretRef", data.entra_client_secret)
        db_admin = secret("DbAdminRef", data.db.secret)

        image = ecs.ContainerImage.from_asset(cfg.backend_dir, platform=ecr_assets.Platform.LINUX_AMD64)
        cluster = ecs.Cluster(self, "Cluster", vpc=data.vpc, container_insights_v2=ecs.ContainerInsights.ENABLED)
        log_group = logs.LogGroup(
            self,
            "ApiLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            encryption_key=key,
            removal_policy=RemovalPolicy.DESTROY if not cfg.is_prod else RemovalPolicy.RETAIN,
        )

        alb_sg = ec2.SecurityGroup(
            self, "AlbSg", vpc=data.vpc, description="Internal ALB (CloudFront only)", allow_all_outbound=False
        )
        api_sg = ec2.SecurityGroup(self, "ApiSg", vpc=data.vpc, description="API tasks")
        api_sg.add_ingress_rule(alb_sg, ec2.Port.tcp(API_PORT), "ALB to API")
        alb_sg.add_egress_rule(api_sg, ec2.Port.tcp(API_PORT), "ALB to API")
        # Only CloudFront (VPC origin) can reach the ALB.
        pl_id = (
            cfg.cloudfront_prefix_list_id
            or ec2.PrefixList.from_lookup(
                self, "CloudFrontOriginFacing", prefix_list_name="com.amazonaws.global.cloudfront.origin-facing"
            ).prefix_list_id
        )
        alb_sg.add_ingress_rule(ec2.Peer.prefix_list(pl_id), ec2.Port.tcp(80), "CloudFront")
        # API (and the migration task, which shares this group) to the database. Defined here so the
        # data stack never depends on the app stack.
        ec2.CfnSecurityGroupIngress(
            self,
            "DbFromApi",
            group_id=data.db_sg.security_group_id,
            source_security_group_id=api_sg.security_group_id,
            ip_protocol="tcp",
            from_port=5432,
            to_port=5432,
            description="API to Aurora",
        )

        common_env = {
            "VANIMO_ENV": cfg.env_name,
            "VANIMO_CELL": cfg.cell,
            "VANIMO_DB_HOST": data.db.cluster_endpoint.hostname,
            "VANIMO_DB_PORT": "5432",
            "VANIMO_DB_NAME": "vanimo",
        }

        # --- API service -------------------------------------------------------------------
        task = ecs.FargateTaskDefinition(
            self,
            "ApiTask",
            cpu=512,
            memory_limit_mib=1024,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64, operating_system_family=ecs.OperatingSystemFamily.LINUX
            ),
        )
        task.add_to_execution_role_policy(decrypt_secrets)
        api_container = task.add_container(
            "api",
            image=image,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="api", log_group=log_group),
            port_mappings=[ecs.PortMapping(container_port=API_PORT)],
            readonly_root_filesystem=True,
            environment={
                **common_env,
                "VANIMO_ENTRA_TENANT_ID": cfg.entra_tenant_id,
                "VANIMO_ENTRA_CLIENT_ID": cfg.entra_client_id,
                "VANIMO_CORS_ORIGINS": "[]",  # same origin through CloudFront
                "VANIMO_ENABLE_DIAGNOSTICS": "true",
                # A deployed cell has Bedrock: drafts come from Claude, never the offline stand-in.
                "VANIMO_DRAFTER": "bedrock",
                # uvicorn trusts X-Forwarded-For only from the ALB (inside the VPC).
                "FORWARDED_ALLOW_IPS": data.vpc.vpc_cidr_block,
                # Teams (M5): empty until the Teams app and its bot are registered.
                "VANIMO_TEAMS_APP_ID": cfg.teams_app_id,
                "VANIMO_TEAMS_BOT_ID": cfg.teams_bot_id,
            },
            secrets={
                "VANIMO_DB_APP_PASSWORD": ecs.Secret.from_secrets_manager(app_password),
                "VANIMO_ENTRA_CLIENT_SECRET": ecs.Secret.from_secrets_manager(entra_client_secret),
                "VANIMO_REF_HMAC_KEY": ecs.Secret.from_secrets_manager(ref_hmac_key),
                "VANIMO_VAULT_MASTER_KEY": ecs.Secret.from_secrets_manager(vault_master_key),
            },
        )
        # Claude on Bedrock (D7) via the Messages-API endpoint. No ARN format is published for
        # bedrock-mantle model resources yet, so the action is region-scoped; the code-side model
        # allow-list (vanimo.config.CELLS) limits which models are called. Tighten after first deploy.
        task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-mantle:CreateInference"],
                resources=["*"],
                conditions={"StringEquals": {"aws:RequestedRegion": cfg.region}},
            )
        )

        service = ecs.FargateService(
            self,
            "Api",
            cluster=cluster,
            task_definition=task,
            desired_count=1,
            assign_public_ip=False,
            security_groups=[api_sg],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            min_healthy_percent=100,
            enable_execute_command=False,
        )

        alb = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            vpc=data.vpc,
            internet_facing=False,
            security_group=alb_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            drop_invalid_header_fields=True,
        )
        listener = alb.add_listener("Http", port=80, open=False)
        listener.add_targets(
            "Api",
            port=API_PORT,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[service],
            health_check=elbv2.HealthCheck(path="/healthz", healthy_http_codes="200"),
            deregistration_delay=Duration.seconds(15),
        )

        # --- Migration task (run once per deploy; see app/README.md) -----------------------
        migrate = ecs.FargateTaskDefinition(self, "MigrateTask", cpu=256, memory_limit_mib=512)
        migrate.add_to_execution_role_policy(decrypt_secrets)
        migrate.add_container(
            "migrate",
            image=image,
            command=["python", "-m", "vanimo.ops.migrate"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="migrate", log_group=log_group),
            readonly_root_filesystem=True,
            environment=common_env,
            secrets={
                "VANIMO_DB_ADMIN_USER": ecs.Secret.from_secrets_manager(db_admin, "username"),
                "VANIMO_DB_ADMIN_PASSWORD": ecs.Secret.from_secrets_manager(db_admin, "password"),
                "VANIMO_DB_OWNER_PASSWORD": ecs.Secret.from_secrets_manager(owner_password),
                "VANIMO_DB_APP_PASSWORD": ecs.Secret.from_secrets_manager(app_password),
            },
        )

        # --- Web app -------------------------------------------------------------------------
        bucket = s3.Bucket(
            self,
            "Web",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            encryption=s3.BucketEncryption.S3_MANAGED,  # static assets only; no customer data
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        web_origin = origins.S3BucketOrigin.with_origin_access_control(bucket)
        hsts = cf.ResponseHeadersStrictTransportSecurity(
            access_control_max_age=Duration.days(365), include_subdomains=True, override=True
        )
        web_headers = cf.ResponseHeadersPolicy(
            self,
            "WebHeaders",
            security_headers_behavior=cf.ResponseSecurityHeadersBehavior(
                content_security_policy=cf.ResponseHeadersContentSecurityPolicy(
                    content_security_policy=WEB_CSP, override=True
                ),
                frame_options=cf.ResponseHeadersFrameOptions(frame_option=cf.HeadersFrameOption.DENY, override=True),
                content_type_options=cf.ResponseHeadersContentTypeOptions(override=True),
                referrer_policy=cf.ResponseHeadersReferrerPolicy(
                    referrer_policy=cf.HeadersReferrerPolicy.NO_REFERRER, override=True
                ),
                strict_transport_security=hsts,
            ),
        )
        addin_headers = cf.ResponseHeadersPolicy(
            self,
            "AddinHeaders",
            security_headers_behavior=cf.ResponseSecurityHeadersBehavior(
                content_type_options=cf.ResponseHeadersContentTypeOptions(override=True),
                referrer_policy=cf.ResponseHeadersReferrerPolicy(
                    referrer_policy=cf.HeadersReferrerPolicy.NO_REFERRER, override=True
                ),
                strict_transport_security=hsts,
            ),
            custom_headers_behavior=cf.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cf.ResponseCustomHeader(
                        header="Content-Security-Policy-Report-Only", value=ADDIN_CSP, override=True
                    )
                ]
            ),
        )
        bridge_headers = cf.ResponseHeadersPolicy(
            self,
            "BridgeHeaders",
            security_headers_behavior=cf.ResponseSecurityHeadersBehavior(
                content_security_policy=cf.ResponseHeadersContentSecurityPolicy(
                    content_security_policy=BRIDGE_CSP, override=True
                ),
                frame_options=cf.ResponseHeadersFrameOptions(
                    frame_option=cf.HeadersFrameOption.SAMEORIGIN, override=True
                ),
                content_type_options=cf.ResponseHeadersContentTypeOptions(override=True),
                referrer_policy=cf.ResponseHeadersReferrerPolicy(
                    referrer_policy=cf.HeadersReferrerPolicy.NO_REFERRER, override=True
                ),
                strict_transport_security=hsts,
            ),
        )
        teams_headers = cf.ResponseHeadersPolicy(
            self,
            "TeamsHeaders",
            security_headers_behavior=cf.ResponseSecurityHeadersBehavior(
                content_type_options=cf.ResponseHeadersContentTypeOptions(override=True),
                referrer_policy=cf.ResponseHeadersReferrerPolicy(
                    referrer_policy=cf.HeadersReferrerPolicy.NO_REFERRER, override=True
                ),
                strict_transport_security=hsts,
            ),
            custom_headers_behavior=cf.ResponseCustomHeadersBehavior(
                custom_headers=[
                    cf.ResponseCustomHeader(
                        header="Content-Security-Policy-Report-Only", value=TEAMS_CSP, override=True
                    )
                ]
            ),
        )
        spa = cf.Function(
            self, "SpaRewrite", code=cf.FunctionCode.from_inline(SPA_REWRITE), runtime=cf.FunctionRuntime.JS_2_0
        )
        api_origin = origins.VpcOrigin.with_application_load_balancer(
            alb,
            http_port=80,
            protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
            read_timeout=Duration.seconds(60),
            keepalive_timeout=Duration.seconds(60),
        )
        distribution = cf.Distribution(
            self,
            "Cdn",
            comment=f"{cfg.prefix} web + API",
            default_root_object="index.html",
            price_class=cf.PriceClass.PRICE_CLASS_200,  # includes India edge locations
            http_version=cf.HttpVersion.HTTP2_AND_3,
            default_behavior=cf.BehaviorOptions(
                origin=web_origin,
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=web_headers,
                function_associations=[
                    cf.FunctionAssociation(function=spa, event_type=cf.FunctionEventType.VIEWER_REQUEST)
                ],
            ),
            additional_behaviors={
                "/api/*": cf.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.HTTPS_ONLY,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    response_headers_policy=cf.ResponseHeadersPolicy.SECURITY_HEADERS,
                ),
                "/addin.html": cf.BehaviorOptions(
                    origin=web_origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=addin_headers,
                ),
                "/teams.html": cf.BehaviorOptions(
                    origin=web_origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=teams_headers,
                ),
                "/redirect.html": cf.BehaviorOptions(
                    origin=web_origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=bridge_headers,
                ),
                "/config.json": cf.BehaviorOptions(
                    origin=web_origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    response_headers_policy=web_headers,
                ),
            },
        )
        s3deploy.BucketDeployment(
            self,
            "WebDeploy",
            sources=[
                s3deploy.Source.asset(cfg.web_dist),
                s3deploy.Source.json_data(
                    "config.json",
                    {"tenantId": cfg.entra_tenant_id, "clientId": cfg.entra_client_id, "apiBase": ""},
                ),
            ],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
            prune=True,
        )

        url = f"https://{distribution.distribution_domain_name}"
        # Teams dialogs load from the web app's own origin.
        api_container.add_environment("VANIMO_WEB_URL", url)
        CfnOutput(self, "WebUrl", value=url, description="Vanimo web app (also the add-in host)")
        CfnOutput(self, "RedirectUri", value=f"{url}/redirect.html", description="Add as a SPA redirect URI in Entra")
        CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        CfnOutput(self, "MigrateTaskDef", value=migrate.task_definition_arn)
        CfnOutput(
            self,
            "TaskSubnets",
            value=",".join(
                s.subnet_id for s in data.vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnets
            ),
        )
        CfnOutput(self, "TaskSecurityGroup", value=api_sg.security_group_id)
        CfnOutput(self, "ApiLogGroup", value=log_group.log_group_name)
