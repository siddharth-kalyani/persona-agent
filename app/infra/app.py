#!/usr/bin/env python3
"""CDK entry point. One deployment = one regional cell (D2).

cdk deploy --all -c cell=in -c entra_tenant_id=<tid> -c entra_client_id=<appId>
"""

import os

import aws_cdk as cdk

from vanimo_infra.app_stack import AppStack
from vanimo_infra.config import from_context
from vanimo_infra.data_stack import DataStack


def build(app: cdk.App) -> tuple[DataStack, AppStack]:
    cfg = from_context(app.node, os.path.dirname(os.path.abspath(__file__)))
    env = cdk.Environment(account=cfg.account, region=cfg.region)
    data = DataStack(app, f"{cfg.prefix}-data", cfg=cfg, env=env, termination_protection=cfg.is_prod)
    api = AppStack(app, f"{cfg.prefix}-app", cfg=cfg, data=data, env=env)
    for stack in (data, api):
        cdk.Tags.of(stack).add("app", "vanimo")
        cdk.Tags.of(stack).add("cell", cfg.cell)
        cdk.Tags.of(stack).add("env", cfg.env_name)
    return data, api


if __name__ == "__main__":
    app = cdk.App()
    build(app)
    app.synth()
