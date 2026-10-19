"""Shared helpers for data-controls tests."""

from __future__ import annotations

import asyncio
import uuid

import httpx

from vanimo.config import Settings
from vanimo.ops.local_user import upsert_local_user
from vanimo.state import AppState

PASSWORD = "a long enough test phrase"


async def _user(client: httpx.AsyncClient, database: dict[str, str], settings: Settings, role: str = "user") -> dict:
    email = f"user.{uuid.uuid4().hex[:8]}@example.com"
    otp = upsert_local_user(database["owner"], email, role, reset=False, settings=settings)
    token = (await client.post("/api/auth/login", json={"email": email, "password": otp})).json()["token"]
    changed = await client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"currentPassword": otp, "newPassword": PASSWORD},
    )
    return {"Authorization": f"Bearer {changed.json()['token']}"}


async def _settle(state: AppState) -> None:
    """Wait for background jobs (purges, scrubs) started by the last request."""
    while state.tasks:
        await asyncio.gather(*list(state.tasks), return_exceptions=True)


async def _sources(client: httpx.AsyncClient, h: dict, kind: str) -> list[dict]:
    resp = await client.get("/api/controls/sources", params={"kind": kind}, headers=h)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _find(items: list[dict], label: str) -> dict:
    return next(i for i in items if i["label"] == label)
