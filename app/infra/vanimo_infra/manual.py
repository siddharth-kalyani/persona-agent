"""The F11 backstops and the app's permissions as JSON for a hand-built deployment (F13, 2026-10-22).

The founder sets up the low-cost EC2 deployment by hand (console, CloudShell and the AWS CLI) to learn
AWS, instead of `cdk deploy`. These files are what the backstops stack and the app stack would create,
built from the same definitions, so the two can't drift (a test compares them):

    uv run python -m vanimo_infra.manual        # rewrites app/deploy/ec2/aws/

Placeholders the setup steps replace: <ACCOUNT_ID>, <BUCKET_NAME>, <GUARDRAIL_ID>.
"""

from __future__ import annotations

import json
from pathlib import Path

from vanimo_infra.backstops_stack import (
    INDIA_PATTERNS,
    MACIE_KEYWORDS,
    MACIE_ROLE,
    VOTER_ID,
    guardrail_policy,
)

REGION = "ap-south-1"
NAME = "vanimo-in-dev"  # vanimo-<cell>-<env>, the prefix `vanimo.ops.macie_job` looks for
OUT = Path(__file__).resolve().parents[2] / "deploy" / "ec2" / "aws"
BUCKET_ARN = "arn:aws:s3:::<BUCKET_NAME>"


def guardrail() -> dict:
    """Input for `aws bedrock create-guardrail --cli-input-json`."""
    policy = guardrail_policy()
    return {
        "name": f"{NAME}-l1-backstop",
        "description": "Vanimo: blocks model input/output holding PII that redaction should have removed",
        "blockedInputMessaging": policy["blocked_input"],
        "blockedOutputsMessaging": policy["blocked_output"],
        "sensitiveInformationPolicyConfig": {
            "piiEntitiesConfig": [{"type": e["type"], "action": e["action"]} for e in policy["pii"]],
            "regexesConfig": [
                {"name": r["name"], "description": r["description"], "pattern": r["pattern"], "action": r["action"]}
                for r in policy["regexes"]
            ],
        },
    }


def bucket_policy() -> dict:
    """The snapshot bucket's policy: TLS only, SSE-S3 writes only, readable by Macie alone."""
    objects = f"{BUCKET_ARN}/*"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "TlsOnly",
                "Effect": "Deny",
                "Principal": {"AWS": "*"},
                "Action": "s3:*",
                "Resource": [BUCKET_ARN, objects],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            },
            {
                "Sid": "OnlyMacieReadsSnapshots",
                "Effect": "Deny",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectAttributes"],
                "Resource": objects,
                "Condition": {"ArnNotLike": {"aws:PrincipalArn": f"arn:aws:iam::<ACCOUNT_ID>:role/{MACIE_ROLE}"}},
            },
            {
                "Sid": "EncryptedWritesOnly",
                "Effect": "Deny",
                "Principal": {"AWS": "*"},
                "Action": "s3:PutObject",
                "Resource": objects,
                "Condition": {"StringNotEquals": {"s3:x-amz-server-side-encryption": "AES256"}},
            },
        ],
    }


def bucket_lifecycle() -> dict:
    """Input for `aws s3api put-bucket-lifecycle-configuration --lifecycle-configuration`."""
    return {
        "Rules": [
            {
                "ID": "expire-unrefreshed-snapshots",
                "Status": "Enabled",
                "Filter": {},
                "Expiration": {"Days": 3},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
            }
        ]
    }


def app_policy() -> dict:
    """What the instance role may do: the app stack's Bedrock statement plus the backstops policy."""
    in_region = {"StringEquals": {"aws:RequestedRegion": REGION}}
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ClaudeOnBedrock",
                "Effect": "Allow",
                "Action": "bedrock-mantle:CreateInference",
                "Resource": "*",
                "Condition": in_region,
            },
            {
                "Sid": "ComprehendPii",
                "Effect": "Allow",
                "Action": "comprehend:DetectPiiEntities",
                "Resource": "*",
                "Condition": in_region,
            },
            {
                "Sid": "Guardrail",
                "Effect": "Allow",
                "Action": "bedrock:ApplyGuardrail",
                "Resource": f"arn:aws:bedrock:{REGION}:<ACCOUNT_ID>:guardrail/<GUARDRAIL_ID>",
            },
            {
                "Sid": "SnapshotWrites",
                "Effect": "Allow",
                "Action": ["s3:PutObject", "s3:DeleteObject"],
                "Resource": f"{BUCKET_ARN}/l1/*",
            },
            {
                "Sid": "MacieFindings",
                "Effect": "Allow",
                "Action": ["macie2:ListFindings", "macie2:GetFindings"],
                "Resource": "*",
                "Condition": in_region,
            },
        ],
    }


def macie_identifiers() -> dict[str, dict]:
    """{file name: input for `aws macie2 create-custom-data-identifier --cli-input-json`}."""
    specs = [(n.removeprefix("india_"), p, d, MACIE_KEYWORDS.get(n)) for n, (p, d) in INDIA_PATTERNS.items()]
    specs.append(("voter-id", VOTER_ID[0], "Voter ID (EPIC), next to a keyword", VOTER_ID[1]))
    out: dict[str, dict] = {}
    for short, pattern, description, keywords in specs:
        spec: dict = {"name": f"{NAME}-{short}", "regex": pattern, "description": f"Vanimo L1 backstop: {description}"}
        if keywords:
            spec |= {"keywords": keywords, "maximumMatchDistance": 50}
        out[f"macie-{short}.json"] = spec
    return out


def files() -> dict[str, dict]:
    return {
        "guardrail.json": guardrail(),
        "bucket-policy.json": bucket_policy(),
        "bucket-lifecycle.json": bucket_lifecycle(),
        "app-policy.json": app_policy(),
        **macie_identifiers(),
    }


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in files().items():
        (OUT / name).write_bytes(render(doc).encode("utf-8"))
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
