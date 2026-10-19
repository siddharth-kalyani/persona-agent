"""Operator script: create the daily Macie classification job over the L1 snapshot bucket (F11, S13).

CloudFormation has no resource for Macie jobs, so this runs once after `cdk deploy` (the backstops
stack prints the exact command):

    python -m vanimo.ops.macie_job --bucket <SnapshotBucket> --prefix vanimo-in-dev [--region ap-south-1]

It finds the stack's custom data identifiers by name prefix, tests each with Macie's own engine
(TestCustomDataIdentifier): it must match its synthetic sample (a pattern Macie reads differently would
silently find nothing) and must NOT match a clean snapshot line (a false positive would pause the
organisation every day). Then it creates a SCHEDULED daily job with an initial run: Macie's
recommended managed identifiers plus ours, objects under `l1/`, 100% sampling. Each later run reads
only objects written since the one before (a snapshot is rewritten only when its L1 changed).

Macie jobs can't be changed: if one with this name exists it is left alone (`--replace` cancels it and
creates a new one). Custom identifiers can't be changed either: a changed pattern in `app/infra`
creates new identifiers, so run this with `--replace` after such a deploy, or the job keeps the old ones.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from typing import Any

# Synthetic values only (checksums valid where the format has one); never user data.
SAMPLES = {
    "aadhaar": "Aadhaar 2341 2341 2346 on file",
    "pan": "PAN ABCPE1234F attached",
    "gstin": "GSTIN 27AAPFU0939F1ZV",
    "ifsc": "IFSC HDFC0001234",
    "upi": "pay resort.booking@okaxis",
    "voter-id": "voter ID ABC1234567",
}


# A clean L1 snapshot line as `vanimo.backstops.snapshots` writes it: tokens, slots, an invoice number,
# and a row ID of 32 hex digits that happen to be all digits. No identifier may match it.
CLEAN_LINE = (
    '{"t": "l1_items", "f": "text", "id": "23412341234612349812345678901234", "text": "Hi ⟦PERSON_3fa2c1d0⟧, '
    'the [PAN] and [Aadhaar number] are with ⟦EMAIL_9b1c2d3e⟧. Invoice INV-2026-0042, PO 4500012345, Q4."}'
)


def job_name(prefix: str) -> str:
    return f"{prefix}-l1-snapshots-daily"


def find_identifiers(client: Any, prefix: str) -> dict[str, str]:
    """{short name: id} of the custom data identifiers named `<prefix>-<short>`."""
    out: dict[str, str] = {}
    token: str | None = None
    while True:
        resp = client.list_custom_data_identifiers(**({"nextToken": token} if token else {}))
        for item in resp.get("items") or []:
            if item.get("name", "").startswith(prefix + "-"):
                out[item["name"].removeprefix(prefix + "-")] = item["id"]
        token = resp.get("nextToken")
        if not token:
            return out


def test_identifiers(client: Any, ids: dict[str, str]) -> list[str]:
    """Names whose pattern misses its synthetic sample, or matches a clean snapshot line, in Macie's engine."""
    failed: list[str] = []
    for short, ident in ids.items():
        sample = SAMPLES.get(short)
        if sample is None:
            continue
        spec = client.get_custom_data_identifier(id=ident)
        kw: dict[str, Any] = {"regex": spec["regex"], "sampleText": sample}
        if spec.get("keywords"):
            kw |= {"keywords": spec["keywords"], "maximumMatchDistance": spec.get("maximumMatchDistance", 50)}
        if not client.test_custom_data_identifier(**kw).get("matchCount"):
            failed.append(short)
        elif client.test_custom_data_identifier(**(kw | {"sampleText": CLEAN_LINE})).get("matchCount"):
            failed.append(f"{short}(false positive)")
    return failed


def existing_job(client: Any, name: str) -> dict[str, Any] | None:
    resp = client.list_classification_jobs(
        filterCriteria={"includes": [{"comparator": "EQ", "key": "name", "values": [name]}]}
    )
    live = [j for j in resp.get("items") or [] if j.get("jobStatus") not in ("CANCELLED", "COMPLETE")]
    return live[0] if live else None


def create_job(client: Any, *, account: str, bucket: str, name: str, identifier_ids: list[str]) -> str:
    resp = client.create_classification_job(
        clientToken=str(uuid.uuid4()),
        name=name,
        description="Vanimo L1 snapshots (F11 redaction backstop): daily, new or rewritten objects only",
        jobType="SCHEDULED",
        scheduleFrequency={"dailySchedule": {}},
        initialRun=True,
        samplingPercentage=100,
        managedDataIdentifierSelector="RECOMMENDED",
        customDataIdentifierIds=identifier_ids,
        s3JobDefinition={
            "bucketDefinitions": [{"accountId": account, "buckets": [bucket]}],
            "scoping": {
                "includes": {
                    "and": [
                        {
                            "simpleScopeTerm": {
                                "comparator": "STARTS_WITH",
                                "key": "OBJECT_KEY",
                                "values": ["l1/"],
                            }
                        }
                    ]
                }
            },
        },
        tags={"app": "vanimo"},
    )
    return resp["jobId"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bucket", required=True, help="the backstops stack's SnapshotBucket output")
    ap.add_argument("--prefix", required=True, help="vanimo-<cell>-<env>, as in the stack's identifier names")
    ap.add_argument("--region", default="ap-south-1")
    ap.add_argument("--replace", action="store_true", help="cancel an existing job of this name and recreate it")
    args = ap.parse_args(argv)

    import boto3

    macie = boto3.client("macie2", region_name=args.region)
    account = boto3.client("sts", region_name=args.region).get_caller_identity()["Account"]

    ids = find_identifiers(macie, args.prefix)
    missing = sorted(set(SAMPLES) - set(ids))
    if missing:
        print(f"custom data identifiers not found: {', '.join(missing)} (deploy the backstops stack first)")
        return 2
    failed = test_identifiers(macie, ids)
    if failed:
        print(f"Macie identifiers failed their check: {', '.join(failed)} (fix the pattern in app/infra)")
        return 3

    name = job_name(args.prefix)
    job = existing_job(macie, name)
    if job and not args.replace:
        print(f"job exists: {job['jobId']} ({job.get('jobStatus')}); nothing to do")
        return 0
    if job:
        macie.update_classification_job(jobId=job["jobId"], jobStatus="CANCELLED")
        print(f"cancelled {job['jobId']}")
    job_id = create_job(macie, account=account, bucket=args.bucket, name=name, identifier_ids=sorted(ids.values()))
    print(f"created daily Macie job {job_id} over s3://{args.bucket}/l1/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
