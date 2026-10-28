"""AWS permissions for automatic deploys from GitHub to the EC2 instance (F14, 2026-10-28).

The founder creates these by hand in the console (app/deploy/ec2/README.md, section I). They are written
here once, with the reason for every permission, and rendered to JSON for pasting into the console:

    uv run python -m vanimo_infra.cicd        # rewrites app/deploy/ec2/aws/cicd/

Placeholders the setup steps replace: <ACCOUNT_ID>, <INSTANCE_ID>, <DEPLOY_BUCKET>.

How it fits together:
* GitHub signs each workflow run with an OIDC token. IAM trusts GitHub's token issuer (an "identity
  provider") and lets a token become the deploy role only if it says: this repository, the main branch.
  No access keys exist anywhere.
* The deploy role may push the two images to ECR, put the release's deploy files in the deploy bucket,
  and run one command document (AWS-RunShellScript) on one instance through SSM.
* The instance's own role gets read access to the two ECR repositories, so it can pull the images.
"""

from __future__ import annotations

from pathlib import Path

from vanimo_infra.manual import REGION, render

GITHUB_REPO = "siddharth-kalyani/persona-agent"
GITHUB_ISSUER = "token.actions.githubusercontent.com"
REPOSITORIES = ("vanimo-api", "vanimo-web")
OUT = Path(__file__).resolve().parents[2] / "deploy" / "ec2" / "aws" / "cicd"
KEEP_IMAGES = 15


def _repo_arns() -> list[str]:
    return [f"arn:aws:ecr:{REGION}:<ACCOUNT_ID>:repository/{name}" for name in REPOSITORIES]


def github_trust_policy() -> dict:
    """Who may become the deploy role: a GitHub Actions job of this repository, on main, and nobody else.
    `aud` is the audience the configure-aws-credentials action asks for; `sub` names the repository and
    branch (a fork, another branch or a pull request gets a different `sub` and is refused)."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "GitHubActionsOnMainOnly",
                "Effect": "Allow",
                "Principal": {"Federated": f"arn:aws:iam::<ACCOUNT_ID>:oidc-provider/{GITHUB_ISSUER}"},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        f"{GITHUB_ISSUER}:aud": "sts.amazonaws.com",
                        f"{GITHUB_ISSUER}:sub": f"repo:{GITHUB_REPO}:ref:refs/heads/main",
                    }
                },
            }
        ],
    }


def github_deploy_policy() -> dict:
    """What a deploy may do, and nothing more."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                # A short-lived password for `docker login` to the account's registry. ECR has no
                # per-repository version of this action, so the resource is "*"; the push rights below
                # still name the two repositories.
                "Sid": "EcrSignIn",
                "Effect": "Allow",
                "Action": "ecr:GetAuthorizationToken",
                "Resource": "*",
            },
            {
                # Push an image (layers, then the manifest), and read a manifest: whether a commit's image is
                # already there (`docker manifest inspect`, so a re-run reuses it).
                "Sid": "PushReleaseImages",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                    "ecr:PutImage",
                    "ecr:BatchGetImage",
                ],
                "Resource": _repo_arns(),
            },
            {
                # The release's compose.yml, Caddyfile and deploy.sh, and the presigned link the server
                # downloads them with (a presigned link carries the signer's GetObject right).
                "Sid": "ReleaseFiles",
                "Effect": "Allow",
                "Action": ["s3:PutObject", "s3:GetObject"],
                "Resource": "arn:aws:s3:::<DEPLOY_BUCKET>/releases/*",
            },
            {
                # Run a shell command on this one instance, with AWS's own shell-script document only.
                "Sid": "RunDeployOnTheServer",
                "Effect": "Allow",
                "Action": "ssm:SendCommand",
                "Resource": [
                    f"arn:aws:ec2:{REGION}:<ACCOUNT_ID>:instance/<INSTANCE_ID>",
                    f"arn:aws:ssm:{REGION}::document/AWS-RunShellScript",
                ],
            },
            {
                # Read the command's status and output (these actions can't be limited to a resource).
                "Sid": "ReadDeployResult",
                "Effect": "Allow",
                "Action": ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"],
                "Resource": "*",
                "Condition": {"StringEquals": {"aws:RequestedRegion": REGION}},
            },
        ],
    }


def instance_ecr_pull_policy() -> dict:
    """Added to the instance's role: pull (never push) the two repositories' images."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {"Sid": "EcrSignIn", "Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*"},
            {
                "Sid": "PullReleaseImages",
                "Effect": "Allow",
                "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"],
                "Resource": _repo_arns(),
            },
        ],
    }


def ecr_lifecycle_policy() -> dict:
    """Each repository keeps the most recent releases (for rollbacks); older images are deleted."""
    return {
        "rules": [
            {
                "rulePriority": 1,
                "description": f"Keep the {KEEP_IMAGES} most recent releases",
                "selection": {"tagStatus": "any", "countType": "imageCountMoreThan", "countNumber": KEEP_IMAGES},
                "action": {"type": "expire"},
            }
        ]
    }


def files() -> dict[str, dict]:
    return {
        "github-trust-policy.json": github_trust_policy(),
        "github-deploy-policy.json": github_deploy_policy(),
        "instance-ecr-pull-policy.json": instance_ecr_pull_policy(),
        "ecr-lifecycle-policy.json": ecr_lifecycle_policy(),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in files().items():
        (OUT / name).write_bytes(render(doc).encode("utf-8"))
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
