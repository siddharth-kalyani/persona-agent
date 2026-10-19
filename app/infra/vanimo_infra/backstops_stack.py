"""Redaction backstops for one cell (F11, architecture §7.2 S5/S13 and §7.4).

* Bedrock Guardrail: sensitive-information filter on every model input and output. Built-in PII types
  for names, addresses, contact details and US/UK/CA identifiers; regexes for the Indian identifiers
  Guardrails has no types for. Every finding BLOCKs (the app records it), except names, which it only
  reports: names are each user's choice (F12) and the app decides; `-c guardrail_noisy=detect`
  switches the context-dependent types to detect-only while false positives are measured. The
  published version lives in the app stack (`guardrail_version`), so a policy change never has to
  replace a value another stack imports.
* L1 snapshot bucket: one object per user, rewritten when L1 changes, expired after 3 days if not
  rewritten. SSE-S3 (Macie reads it without key grants), TLS only, no public access, no versions kept,
  and objects readable only by Macie's service-linked role (the app writes and deletes, never reads).
* Macie: the account session (unless Macie is already enabled, `-c macie_session=existing`; kept if
  this stack is deleted, so other teams' Macie in a shared account is never switched off) and custom
  data identifiers for Indian identifiers (Macie's own India identifiers fire only next to keywords).
  The scheduled classification job has no CloudFormation resource: `python -m vanimo.ops.macie_job`.
* One managed policy with exactly what the app needs: Comprehend DetectPiiEntities, ApplyGuardrail on
  this guardrail, put/delete of snapshot objects, and reading Macie findings. The API task role attaches
  it; the low-cost EC2 deployment (F11) attaches it to its instance role.

Comprehend needs no resource. **Before real data:** opt the account out of AWS AI-service content use
(Organizations "AI services opt-out" policy): Comprehend may otherwise keep content to improve itself.
"""

from __future__ import annotations

import hashlib
import json

from aws_cdk import CfnDeletionPolicy, CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_iam as iam
from aws_cdk import aws_macie as macie
from aws_cdk import aws_s3 as s3
from constructs import Construct

from vanimo_infra.config import DeployConfig

# L1 should never hold any of these: our redaction and Comprehend replaced them with tokens or slots.
# Left out: AGE and URL (ordinary content), USERNAME and PIN (they fire on everyday words and numbers;
# Comprehend handles them at S5 with stricter thresholds).
GUARDRAIL_PII_TYPES = (
    "ADDRESS", "AWS_ACCESS_KEY", "AWS_SECRET_KEY", "CA_HEALTH_NUMBER", "CA_SOCIAL_INSURANCE_NUMBER",
    "CREDIT_DEBIT_CARD_CVV", "CREDIT_DEBIT_CARD_EXPIRY", "CREDIT_DEBIT_CARD_NUMBER", "DRIVER_ID", "EMAIL",
    "INTERNATIONAL_BANK_ACCOUNT_NUMBER", "IP_ADDRESS", "LICENSE_PLATE", "MAC_ADDRESS", "NAME", "PASSWORD",
    "PHONE", "SWIFT_CODE", "UK_NATIONAL_HEALTH_SERVICE_NUMBER", "UK_NATIONAL_INSURANCE_NUMBER",
    "UK_UNIQUE_TAXPAYER_REFERENCE_NUMBER", "US_BANK_ACCOUNT_NUMBER", "US_BANK_ROUTING_NUMBER",
    "US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER", "US_PASSPORT_NUMBER", "US_SOCIAL_SECURITY_NUMBER",
    "VEHICLE_IDENTIFICATION_NUMBER",
)  # fmt: skip
# Types judged from context by a model (most prone to false positives in ordinary business text).
NOISY_TYPES = ("ADDRESS", "PASSWORD", "DRIVER_ID", "LICENSE_PLATE", "US_PASSPORT_NUMBER")
# Names are each user's choice (F12): the guardrail only reports them, and the app blocks on a reported
# name for users who chose to replace names (`vanimo.backstops.guardrail.BLOCK_NAMES`).
APP_DECIDES = ("NAME",)

# Indian identifiers. No lookaround (Guardrails doesn't support it), no capturing groups (Macie doesn't),
# ≤ 500 characters each.
UPI_HANDLES = "okaxis|okhdfcbank|okicici|oksbi|ybl|ibl|axl|apl|paytm|upi|ptyes|ptsbi|ptaxis|pthdfc"
INDIA_PATTERNS = {
    "india_aadhaar": (r"\b[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}\b", "Aadhaar number (12 digits)"),
    "india_pan": (r"\b[A-Za-z]{3}[ABCFGHJLPTabcfghjlpt][A-Za-z][0-9]{4}[A-Za-z]\b", "PAN (income-tax ID)"),
    "india_gstin": (r"\b[0-3][0-9][A-Za-z]{5}[0-9]{4}[A-Za-z][1-9A-Za-z][Zz][0-9A-Za-z]\b", "GSTIN"),
    "india_ifsc": (r"\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b", "IFSC bank branch code"),
    "india_upi": (rf"\b[A-Za-z0-9._-]{{2,64}}@(?:{UPI_HANDLES})\b", "UPI payment address"),
}
# Aadhaar is detected everywhere, bare 12-digit numbers included (founder, 2026-10-19). A regex can't
# check the Verhoeff checksum, so an order number that looks like one is blocked too; Vanimo writes no
# numbers of its own into what is checked (snapshot lines carry no row IDs; tokens are 8 hex characters).
GUARDRAIL_REGEXES = tuple(INDIA_PATTERNS)
MACIE_KEYWORDS: dict[str, list[str]] = {}
# Voter IDs (3 letters + 7 digits) look like invoice numbers: Macie checks them next to a keyword only,
# and the guardrail leaves them to Comprehend's IN_VOTER_NUMBER at S5.
VOTER_ID = (r"\b[A-Za-z]{3}[0-9]{7}\b", ["voter", "epic", "electoral"])
BLOCKED_MESSAGE = "Blocked by Vanimo's sensitive-data check."
MACIE_ROLE = "aws-service-role/macie.amazonaws.com/AWSServiceRoleForAmazonMacie"


def guardrail_policy(noisy: str = "block") -> dict:
    """The whole guardrail policy, as data: the stack builds it from this and its digest names the
    published version, so any change to it (types, actions, regexes, messages) publishes a new one."""

    def action(t: str) -> str:
        return "NONE" if t in APP_DECIDES or (noisy == "detect" and t in NOISY_TYPES) else "BLOCK"

    return {
        "pii": [{"type": t, "action": action(t)} for t in GUARDRAIL_PII_TYPES],
        "regexes": [
            {"name": n, "pattern": INDIA_PATTERNS[n][0], "description": INDIA_PATTERNS[n][1], "action": "BLOCK"}
            for n in GUARDRAIL_REGEXES
        ],
        "blocked_input": BLOCKED_MESSAGE,
        "blocked_output": BLOCKED_MESSAGE,
    }


def guardrail_config_digest(policy: dict) -> str:
    return hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()[:12]


class BackstopsStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, cfg: DeployConfig, **kw) -> None:
        super().__init__(scope, cid, **kw)
        name = f"vanimo-{cfg.cell}-{cfg.env_name}"
        self.name_prefix = name

        # --- Bedrock Guardrail ---------------------------------------------------------------
        policy = guardrail_policy(cfg.guardrail_noisy)
        self.guardrail_digest = guardrail_config_digest(policy)
        self.guardrail = bedrock.CfnGuardrail(
            self,
            "Guardrail",
            name=f"{name}-l1-backstop",
            description="Vanimo: blocks model input/output holding PII that redaction should have removed",
            blocked_input_messaging=policy["blocked_input"],
            blocked_outputs_messaging=policy["blocked_output"],
            sensitive_information_policy_config=bedrock.CfnGuardrail.SensitiveInformationPolicyConfigProperty(
                pii_entities_config=[
                    bedrock.CfnGuardrail.PiiEntityConfigProperty(type=e["type"], action=e["action"])
                    for e in policy["pii"]
                ],
                regexes_config=[
                    bedrock.CfnGuardrail.RegexConfigProperty(
                        name=r["name"], pattern=r["pattern"], description=r["description"], action=r["action"]
                    )
                    for r in policy["regexes"]
                ],
            ),
        )

        # --- L1 snapshot bucket (Macie scans it) ---------------------------------------------
        self.bucket = s3.Bucket(
            self,
            "L1Snapshots",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=False,  # an overwritten or purged snapshot is gone, not kept as a version
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-unrefreshed-snapshots",
                    expiration=Duration.days(3),
                    abort_incomplete_multipart_upload_after=Duration.days(1),
                )
            ],
            removal_policy=RemovalPolicy.RETAIN if cfg.is_prod else RemovalPolicy.DESTROY,
            auto_delete_objects=not cfg.is_prod,
        )
        # L1 outside the per-user vault encryption: only Macie reads it. Admin, CI and deploy roles with
        # s3:* can't (changing this policy is itself a logged, deliberate act).
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="OnlyMacieReadsSnapshots",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectAttributes"],
                resources=[self.bucket.arn_for_objects("*")],
                conditions={"ArnNotLike": {"aws:PrincipalArn": f"arn:aws:iam::{self.account}:role/{MACIE_ROLE}"}},
            )
        )
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="EncryptedWritesOnly",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:PutObject"],
                resources=[self.bucket.arn_for_objects("*")],
                conditions={"StringNotEquals": {"s3:x-amz-server-side-encryption": "AES256"}},
            )
        )

        # --- Macie ----------------------------------------------------------------------------
        session = None
        if cfg.macie_session != "existing":
            session = macie.CfnSession(self, "Macie", status="ENABLED", finding_publishing_frequency="FIFTEEN_MINUTES")
            # Deleting this stack must never switch Macie off for the whole account and region.
            session.cfn_options.deletion_policy = CfnDeletionPolicy.RETAIN
            session.cfn_options.update_replace_policy = CfnDeletionPolicy.RETAIN
        self.identifiers: list[macie.CfnCustomDataIdentifier] = []
        specs = [(n.removeprefix("india_"), p, d, MACIE_KEYWORDS.get(n)) for n, (p, d) in INDIA_PATTERNS.items()]
        specs.append(("voter-id", VOTER_ID[0], "Voter ID (EPIC), next to a keyword", VOTER_ID[1]))
        for short, pattern, description, keywords in specs:
            ident = macie.CfnCustomDataIdentifier(
                self,
                f"Ident{short.title().replace('-', '')}",
                name=f"{name}-{short}",
                regex=pattern,
                description=f"Vanimo L1 backstop: {description}",
                keywords=keywords,
                maximum_match_distance=50 if keywords else None,
            )
            if session is not None:
                ident.add_dependency(session)
            self.identifiers.append(ident)

        # --- what the app may do ------------------------------------------------------------
        self.policy = iam.ManagedPolicy(
            self,
            "BackstopsAccess",
            description="Vanimo app: Comprehend PII detection, Bedrock guardrail, L1 snapshots, Macie findings",
            statements=[
                iam.PolicyStatement(
                    actions=["comprehend:DetectPiiEntities"],
                    resources=["*"],  # Comprehend's real-time APIs have no resource-level permissions
                    conditions={"StringEquals": {"aws:RequestedRegion": cfg.region}},
                ),
                iam.PolicyStatement(actions=["bedrock:ApplyGuardrail"], resources=[self.guardrail.attr_guardrail_arn]),
                iam.PolicyStatement(
                    actions=["s3:PutObject", "s3:DeleteObject"], resources=[self.bucket.arn_for_objects("l1/*")]
                ),
                iam.PolicyStatement(
                    # No resource-level permissions for findings: the app can list the metadata of every
                    # Macie finding in the account and region (it uses only its own bucket's).
                    actions=["macie2:ListFindings", "macie2:GetFindings"],
                    resources=["*"],
                    conditions={"StringEquals": {"aws:RequestedRegion": cfg.region}},
                ),
            ],
        )

        CfnOutput(self, "GuardrailId", value=self.guardrail.attr_guardrail_id)
        CfnOutput(self, "SnapshotBucket", value=self.bucket.bucket_name)
        CfnOutput(self, "BackstopsPolicyArn", value=self.policy.managed_policy_arn)
        CfnOutput(
            self,
            "MacieJobCommand",
            value=(
                f"python -m vanimo.ops.macie_job --bucket {self.bucket.bucket_name} --prefix {name} "
                f"--region {cfg.region}"
            ),
            description="Run once after deploy (from app/backend) to create the daily Macie job",
        )


def guardrail_version(scope: Construct, backstops: BackstopsStack) -> bedrock.CfnGuardrailVersion:
    """The published guardrail version the app uses, created in the app's own stack: a policy change
    (new digest) replaces it there, and the app's setting follows in the same deploy."""
    return bedrock.CfnGuardrailVersion(
        scope,
        "GuardrailVersion",
        guardrail_identifier=backstops.guardrail.attr_guardrail_id,
        description=f"policy {backstops.guardrail_digest}",
    )
