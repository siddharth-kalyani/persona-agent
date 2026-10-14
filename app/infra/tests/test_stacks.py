"""Synth the cell and assert the security properties the architecture requires."""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from app import build


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Template, Template, Path]:
    root = tmp_path_factory.mktemp("assets")
    web = root / "dist"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>", encoding="utf-8")
    backend = root / "backend"
    backend.mkdir()
    (backend / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    app = cdk.App(
        context={
            "cell": "in",
            "env_name": "dev",
            "entra_tenant_id": "11111111-1111-1111-1111-111111111111",
            "entra_client_id": "22222222-2222-2222-2222-222222222222",
            "web_dist": str(web),
            "backend_dir": str(backend),
            "cloudfront_prefix_list_id": "pl-3b927c52",
        }
    )
    data, api = build(app)
    assert data.region == "ap-south-1" and api.region == "ap-south-1"
    assembly = Path(app.synth().directory)
    return Template.from_stack(data), Template.from_stack(api), assembly


@pytest.fixture(scope="module")
def templates(built: tuple[Template, Template, Path]) -> tuple[Template, Template]:
    return built[0], built[1]


def test_database_is_private_encrypted_and_content_free(templates: tuple[Template, Template]) -> None:
    data, _ = templates
    data.has_resource_properties(
        "AWS::RDS::DBCluster",
        {
            "StorageEncrypted": True,
            "KmsKeyId": Match.any_value(),
            "Engine": "aurora-postgresql",
            "ServerlessV2ScalingConfiguration": {"MinCapacity": 0, "MaxCapacity": 4},
        },
    )
    data.has_resource_properties("AWS::RDS::DBInstance", {"PubliclyAccessible": False})
    data.has_resource_properties(
        "AWS::RDS::DBClusterParameterGroup",
        {
            "Parameters": Match.object_like(
                {"log_min_error_statement": "panic", "log_statement": "none", "rds.force_ssl": "1"}
            )
        },
    )


def test_key_rotation_and_secrets_encrypted(templates: tuple[Template, Template]) -> None:
    data, _ = templates
    data.has_resource_properties("AWS::KMS::Key", {"EnableKeyRotation": True})
    for secret in data.find_resources("AWS::SecretsManager::Secret").values():
        assert "KmsKeyId" in secret["Properties"], secret


def test_alb_is_internal_and_only_reachable_from_cloudfront(templates: tuple[Template, Template]) -> None:
    _, api = templates
    api.has_resource_properties("AWS::ElasticLoadBalancingV2::LoadBalancer", {"Scheme": "internal"})
    groups = api.find_resources("AWS::EC2::SecurityGroup")
    alb_sg = next(k for k, g in groups.items() if "Internal ALB" in g["Properties"]["GroupDescription"])
    inline = groups[alb_sg]["Properties"].get("SecurityGroupIngress", [])
    separate = [
        r["Properties"]
        for r in api.find_resources("AWS::EC2::SecurityGroupIngress").values()
        if r["Properties"].get("GroupId", {}).get("Fn::GetAtt", [None])[0] == alb_sg
    ]
    alb_ingress = inline + separate
    assert alb_ingress and all(r.get("SourcePrefixListId") == "pl-3b927c52" for r in alb_ingress), alb_ingress
    assert "0.0.0.0/0" not in json.dumps(alb_ingress)


def test_api_tasks_private_with_secrets_injected(templates: tuple[Template, Template]) -> None:
    _, api = templates
    api.has_resource_properties(
        "AWS::ECS::Service",
        {"NetworkConfiguration": {"AwsvpcConfiguration": Match.object_like({"AssignPublicIp": "DISABLED"})}},
    )
    task = next(
        t
        for t in api.find_resources("AWS::ECS::TaskDefinition").values()
        if t["Properties"]["ContainerDefinitions"][0]["Name"] == "api"
    )
    container = task["Properties"]["ContainerDefinitions"][0]
    secret_names = {s["Name"] for s in container["Secrets"]}
    assert secret_names == {
        "VANIMO_DB_APP_PASSWORD",
        "VANIMO_ENTRA_CLIENT_SECRET",
        "VANIMO_REF_HMAC_KEY",
        "VANIMO_VAULT_MASTER_KEY",
    }
    env = {e["Name"]: e["Value"] for e in container["Environment"]}
    env_names = set(env)
    # Proxy headers are trusted only from inside the VPC (the ALB), never "*".
    assert "FORWARDED_ALLOW_IPS" in env and env["FORWARDED_ALLOW_IPS"] != "*"
    assert "VANIMO_ENABLE_PASSWORD_AUTH" not in env
    assert env["VANIMO_DRAFTER"] == "bedrock"
    assert not any("PASSWORD" in n or "SECRET" in n for n in env_names)
    assert container["ReadonlyRootFilesystem"] is True


def test_bedrock_permission_is_narrow(templates: tuple[Template, Template]) -> None:
    _, api = templates
    policies = json.dumps(api.find_resources("AWS::IAM::Policy"))
    assert "bedrock-mantle:CreateInference" in policies
    assert '"bedrock:*"' not in policies and '"bedrock-mantle:*"' not in policies
    assert "aws:RequestedRegion" in policies


def test_cloudfront_routes_api_and_sets_security_headers(templates: tuple[Template, Template]) -> None:
    _, api = templates
    dist = next(iter(api.find_resources("AWS::CloudFront::Distribution").values()))["Properties"]["DistributionConfig"]
    paths = {b["PathPattern"]: b for b in dist["CacheBehaviors"]}
    assert set(paths) == {"/api/*", "/addin.html", "/config.json", "/redirect.html"}
    assert paths["/api/*"]["ViewerProtocolPolicy"] == "https-only"
    assert dist["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "redirect-to-https"
    api.has_resource_properties(
        "AWS::CloudFront::ResponseHeadersPolicy",
        {
            "ResponseHeadersPolicyConfig": Match.object_like(
                {
                    "SecurityHeadersConfig": Match.object_like(
                        {
                            "ContentSecurityPolicy": {
                                "ContentSecurityPolicy": Match.string_like_regexp("frame-ancestors 'none'"),
                                "Override": True,
                            }
                        }
                    )
                }
            )
        },
    )


def test_web_bucket_is_private(templates: tuple[Template, Template]) -> None:
    _, api = templates
    api.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )


def test_config_json_has_only_public_settings(built: tuple[Template, Template, Path]) -> None:
    configs = list(built[2].glob("asset.*/config.json"))
    assert len(configs) == 1
    assert json.loads(configs[0].read_text(encoding="utf-8")) == {
        "tenantId": "11111111-1111-1111-1111-111111111111",
        "clientId": "22222222-2222-2222-2222-222222222222",  # public by design (OAuth client ID)
        "apiBase": "",
    }


def test_unknown_cell_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown cell"):
        build(cdk.App(context={"cell": "eu", "web_dist": str(tmp_path), "backend_dir": str(tmp_path)}))


def test_task_execution_roles_can_decrypt_their_secrets(templates: tuple[Template, Template]) -> None:
    """The secrets use the cell CMK; without kms:Decrypt ECS can't inject them and tasks never start."""
    _, api = templates
    tasks = api.find_resources("AWS::ECS::TaskDefinition")
    exec_roles = {t["Properties"]["ExecutionRoleArn"]["Fn::GetAtt"][0] for t in tasks.values()}
    assert len(exec_roles) == 2  # api + migrate
    for role in exec_roles:
        statements = [
            st
            for pol in api.find_resources("AWS::IAM::Policy").values()
            if any(r.get("Ref") == role for r in pol["Properties"]["Roles"])
            for st in pol["Properties"]["PolicyDocument"]["Statement"]
        ]
        actions = json.dumps([st["Action"] for st in statements])
        assert "kms:Decrypt" in actions and "secretsmanager:GetSecretValue" in actions, role


def test_secrets_use_supported_deletion_policies(templates: tuple[Template, Template]) -> None:
    data, _ = templates
    for name, secret in data.find_resources("AWS::SecretsManager::Secret").items():
        assert secret.get("DeletionPolicy", "Delete") in ("Delete", "Retain"), name
    cluster = next(iter(data.find_resources("AWS::RDS::DBCluster").values()))
    assert cluster["DeletionPolicy"] == "Snapshot"


def test_redirect_bridge_is_frameable_by_self_only(templates: tuple[Template, Template]) -> None:
    _, api = templates
    api.has_resource_properties(
        "AWS::CloudFront::ResponseHeadersPolicy",
        {
            "ResponseHeadersPolicyConfig": Match.object_like(
                {
                    "SecurityHeadersConfig": Match.object_like(
                        {
                            "ContentSecurityPolicy": {
                                "ContentSecurityPolicy": Match.string_like_regexp("frame-ancestors 'self'"),
                                "Override": True,
                            },
                            "FrameOptions": {"FrameOption": "SAMEORIGIN", "Override": True},
                        }
                    )
                }
            )
        },
    )
