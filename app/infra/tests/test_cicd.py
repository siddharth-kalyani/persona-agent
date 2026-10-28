"""The CI/CD permissions (F14) are current on disk and stay least-privilege."""

from __future__ import annotations

import json

from vanimo_infra import cicd
from vanimo_infra.manual import render


def _actions(policy: dict) -> list[str]:
    out: list[str] = []
    for s in policy["Statement"]:
        out += [s["Action"]] if isinstance(s["Action"], str) else s["Action"]
    return sorted(out)


def test_committed_files_are_current() -> None:
    expected = cicd.files()
    assert {p.name for p in cicd.OUT.glob("*.json")} == set(expected), "run: uv run python -m vanimo_infra.cicd"
    for name, doc in expected.items():
        assert (cicd.OUT / name).read_bytes().decode("utf-8") == render(doc), (
            f"{name} is stale; run: uv run python -m vanimo_infra.cicd"
        )


def test_only_main_of_this_repository_can_deploy() -> None:
    (statement,) = cicd.github_trust_policy()["Statement"]
    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    condition = statement["Condition"]
    assert set(condition) == {"StringEquals"}  # exact match: no StringLike wildcards on the subject
    assert condition["StringEquals"]["token.actions.githubusercontent.com:sub"] == (
        "repo:siddharth-kalyani/persona-agent:ref:refs/heads/main"
    )
    assert condition["StringEquals"]["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"


def test_deploy_role_is_least_privilege() -> None:
    policy = cicd.github_deploy_policy()
    assert _actions(policy) == sorted([
        "ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:DescribeImages",
        "s3:PutObject", "s3:GetObject", "ssm:SendCommand", "ssm:GetCommandInvocation", "ssm:ListCommandInvocations",
    ])  # fmt: skip
    text = json.dumps(policy)
    assert '"*:' not in text and ':*"' not in text  # no wildcard actions
    by_sid = {s["Sid"]: s for s in policy["Statement"]}
    assert by_sid["RunDeployOnTheServer"]["Resource"] == [
        "arn:aws:ec2:ap-south-1:<ACCOUNT_ID>:instance/<INSTANCE_ID>",
        "arn:aws:ssm:ap-south-1::document/AWS-RunShellScript",
    ]
    assert by_sid["ReleaseFiles"]["Resource"] == "arn:aws:s3:::<DEPLOY_BUCKET>/releases/*"
    assert all(r.endswith(("/vanimo-api", "/vanimo-web")) for r in by_sid["PushReleaseImages"]["Resource"])


def test_instance_can_only_pull() -> None:
    actions = _actions(cicd.instance_ecr_pull_policy())
    assert actions == sorted([
        "ecr:GetAuthorizationToken", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability",
    ])  # fmt: skip
    assert not any(a in actions for a in ("ecr:PutImage", "ecr:InitiateLayerUpload"))
