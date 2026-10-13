"""Deployment configuration. One CDK app deploys one regional cell; the cell is a parameter (D2)."""

from __future__ import annotations

import os
from dataclasses import dataclass

CELL_REGIONS = {"in": "ap-south-1", "us": "us-east-1"}


@dataclass(frozen=True)
class DeployConfig:
    cell: str
    region: str
    account: str | None
    env_name: str  # "dev" for the first internal cell; "prod" later
    entra_tenant_id: str
    entra_client_id: str
    # Path to the built frontend (npm run build). Tests point this at a stub directory.
    web_dist: str
    backend_dir: str
    # Normally looked up at synth time; set explicitly in tests or if the lookup is blocked.
    cloudfront_prefix_list_id: str | None = None

    @property
    def prefix(self) -> str:
        return f"Vanimo-{self.cell}-{self.env_name}"

    @property
    def is_prod(self) -> bool:
        return self.env_name == "prod"


def from_context(node, root: str) -> DeployConfig:  # node: constructs.Node
    def get(key: str, default: str | None = None) -> str | None:
        value = node.try_get_context(key)
        return str(value) if value is not None else os.environ.get(f"VANIMO_{key.upper()}", default)

    cell = get("cell", "in") or "in"
    if cell not in CELL_REGIONS:
        raise ValueError(f"unknown cell {cell!r}")
    return DeployConfig(
        cell=cell,
        region=CELL_REGIONS[cell],
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        env_name=get("env_name", "dev") or "dev",
        entra_tenant_id=get("entra_tenant_id", "") or "",
        entra_client_id=get("entra_client_id", "") or "",
        web_dist=get("web_dist", os.path.join(root, "..", "frontend", "dist")) or "",
        backend_dir=get("backend_dir", os.path.join(root, "..", "backend")) or "",
        cloudfront_prefix_list_id=get("cloudfront_prefix_list_id"),
    )
