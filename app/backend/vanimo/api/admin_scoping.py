"""/api/admin/scoping — client/account scoping for the whole organisation (D9, architecture §6.1).

IT-services customers are bound by their own clients' contracts. Admins can:
  * exclude a client account (its domains and subdomains) from learning, memory and drafting,
    for everyone — users see it as locked;
  * switch to "approved clients only": conversations with external people outside approved
    accounts are excluded;
  * attach company-sensitive words to a client (Tier C), masked by the redaction pipeline (M2).

Admins never see users' content, exclusions or never-send words through this API.
Changes apply immediately (the engine reads them live).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from vanimo import audit
from vanimo.api.deps import AdminPrincipal, CurrentUser, State
from vanimo.controls.jobs import run_job
from vanimo.db.session import UserRef, user_tx
from vanimo.state import AppState
from vanimo.vault import normalise_identifier

router = APIRouter(prefix="/api/admin/scoping", tags=["admin"])
DOMAIN = re.compile(r"^(?=.{3,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")
ExternalMode = Literal["allow_all", "approved_only"]


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    mode: Literal["excluded", "approved"]
    domains: list[str] = Field(min_length=1, max_length=50)
    sensitiveWords: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("domains")
    @classmethod
    def _domains(cls, values: list[str]) -> list[str]:
        out = []
        for v in values:
            d = normalise_identifier("domain", v.strip().removeprefix("@"))
            if not DOMAIN.match(d):
                raise ValueError("invalid domain")
            out.append(d)
        return list(dict.fromkeys(out))

    @field_validator("sensitiveWords")
    @classmethod
    def _words(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(w.strip() for w in values if w.strip() and len(w.strip()) <= 100))


class AccountOut(BaseModel):
    id: str
    name: str
    mode: str
    domains: list[str]
    sensitiveWords: int
    createdAt: datetime


class ScopingOut(BaseModel):
    externalMode: ExternalMode
    accounts: list[AccountOut]
    # Drafts may be put in people's Outlook Drafts folder (each person still opts in). D8: one app
    # holds Mail.ReadWrite until the Read/Compose split; this is the organisation's switch meanwhile.
    serverDrafts: bool = True


async def _read(state: State, user: CurrentUser) -> ScopingOut:
    v, t = state.vault, user.tenant_id
    async with user_tx(state.engine, user) as conn:
        policy = (await conn.execute(text("select external_mode, server_drafts from vanimo.tenant_policies"))).first()
        mode = policy.external_mode if policy else None
        accounts = (await conn.execute(text("select * from vanimo.client_accounts order by created_at"))).all()
        domains = (await conn.execute(text("select account_id, domain_enc from vanimo.client_account_domains"))).all()
        words = (
            await conn.execute(text("select account_id, count(*) as n from vanimo.client_account_terms group by 1"))
        ).all()
    by_account: dict[uuid.UUID, list[str]] = {}
    for d in domains:
        by_account.setdefault(d.account_id, []).append(v.decrypt_tenant(t, d.domain_enc, "account_domain") or "")
    counts = {w.account_id: w.n for w in words}
    return ScopingOut(
        externalMode=mode or "allow_all",
        serverDrafts=policy.server_drafts if policy else True,
        accounts=[
            AccountOut(
                id=str(a.id),
                name=v.decrypt_tenant(t, a.name_enc, "account_name") or "",
                mode=a.mode,
                domains=sorted(by_account.get(a.id, [])),
                sensitiveWords=counts.get(a.id, 0),
                createdAt=a.created_at,
            )
            for a in accounts
        ],
    )


async def _enqueue_tenant_purge(conn: Any) -> list[Any]:
    """Queue a purge (and bump the controls version) for every user of the tenant; see 0007."""
    return list((await conn.execute(text("select * from vanimo_private.enqueue_tenant_purge()"))).all())


def _start_tenant_jobs(state: AppState, admin: UserRef, jobs: list[Any]) -> None:
    """After commit: run each user's purge now (the sweeper is only the safety net)."""
    for job in jobs:
        ref = UserRef(admin.tenant_id, job.user_id)
        state.spawn(run_job(state.engine, state.vault, ref, str(job.job_id), "tenant_policy_changed"))


@router.get("", response_model=ScopingOut)
async def get_scoping(_: AdminPrincipal, user: CurrentUser, state: State) -> ScopingOut:
    return await _read(state, user)


class PolicyIn(BaseModel):
    externalMode: ExternalMode


@router.put("/policy", response_model=ScopingOut)
async def set_policy(
    body: PolicyIn, _: AdminPrincipal, user: CurrentUser, state: State, request: Request
) -> ScopingOut:
    async with user_tx(state.engine, user, admin=True) as conn:
        await conn.execute(
            text(
                "insert into vanimo.tenant_policies (tenant_id, external_mode, updated_by) values (:t, :m, :u) "
                "on conflict (tenant_id) do update set external_mode = :m, updated_at = now(), updated_by = :u"
            ),
            {"t": user.tenant_id, "m": body.externalMode, "u": user.user_id},
        )
        jobs = await _enqueue_tenant_purge(conn)  # learned data follows the new rules
        await audit.record(conn, user, f"admin.scoping.mode_{body.externalMode}", request_id=request.state.request_id)
    _start_tenant_jobs(state, user, jobs)
    return await _read(state, user)


class DraftsPolicyIn(BaseModel):
    serverDrafts: bool


@router.put("/drafts", response_model=ScopingOut)
async def set_drafts_policy(
    body: DraftsPolicyIn, _: AdminPrincipal, user: CurrentUser, state: State, request: Request
) -> ScopingOut:
    async with user_tx(state.engine, user, admin=True) as conn:
        await conn.execute(
            text(
                "insert into vanimo.tenant_policies (tenant_id, server_drafts, updated_by) values (:t, :d, :u) "
                "on conflict (tenant_id) do update set server_drafts = :d, updated_at = now(), updated_by = :u"
            ),
            {"t": user.tenant_id, "d": body.serverDrafts, "u": user.user_id},
        )
        action = "admin.server_drafts_on" if body.serverDrafts else "admin.server_drafts_off"
        await audit.record(conn, user, action, request_id=request.state.request_id)
    return await _read(state, user)


@router.post("/accounts", response_model=ScopingOut, status_code=201)
async def add_account(
    body: AccountIn, _: AdminPrincipal, user: CurrentUser, state: State, request: Request
) -> ScopingOut:
    try:
        return await _add_account(body, user, state, request)
    except IntegrityError:
        raise HTTPException(409, detail={"error": "domain_already_assigned"}) from None


async def _add_account(body: AccountIn, user: UserRef, state: AppState, request: Request) -> ScopingOut:
    v, t = state.vault, user.tenant_id
    async with user_tx(state.engine, user, admin=True) as conn:
        hashes = {d: v.key_hash(t, "domain", d) for d in body.domains}
        clash = (
            await conn.execute(
                text("select 1 from vanimo.client_account_domains where domain_hash = any(:h) limit 1"),
                {"h": list(hashes.values())},
            )
        ).first()
        if clash:
            raise HTTPException(409, detail={"error": "domain_already_assigned"})
        account_id = (
            await conn.execute(
                text(
                    "insert into vanimo.client_accounts (tenant_id, name_enc, mode, created_by) "
                    "values (:t, :n, :m, :u) returning id"
                ),
                {
                    "t": t,
                    "n": v.encrypt_tenant(t, body.name.strip(), "account_name"),
                    "m": body.mode,
                    "u": user.user_id,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "insert into vanimo.client_account_domains (tenant_id, account_id, domain_hash, domain_enc) "
                "values (:t, :a, :h, :d)"
            ),
            [
                {"t": t, "a": account_id, "h": h, "d": v.encrypt_tenant(t, d, "account_domain")}
                for d, h in hashes.items()
            ],
        )
        if body.sensitiveWords:
            await conn.execute(
                text("insert into vanimo.client_account_terms (tenant_id, account_id, term_enc) values (:t, :a, :w)"),
                [{"t": t, "a": account_id, "w": v.encrypt_tenant(t, w, "account_term")} for w in body.sensitiveWords],
            )
        jobs = await _enqueue_tenant_purge(conn)  # learned data follows the new rules
        await audit.record(conn, user, "admin.scoping.account_added", target_kind="client_account",
                           target_ref=str(account_id), request_id=request.state.request_id)  # fmt: skip
    _start_tenant_jobs(state, user, jobs)
    return await _read(state, user)


@router.delete("/accounts/{account_id}", response_model=ScopingOut)
async def remove_account(
    account_id: uuid.UUID, _: AdminPrincipal, user: CurrentUser, state: State, request: Request
) -> ScopingOut:
    async with user_tx(state.engine, user, admin=True) as conn:
        done = (
            await conn.execute(
                text("delete from vanimo.client_accounts where id = :id returning id"), {"id": account_id}
            )
        ).first()
        if not done:
            raise HTTPException(404, detail={"error": "account_not_found"})
        jobs = await _enqueue_tenant_purge(conn)  # learned data follows the new rules
        await audit.record(conn, user, "admin.scoping.account_removed", target_kind="client_account",
                           target_ref=str(account_id), request_id=request.state.request_id)  # fmt: skip
    _start_tenant_jobs(state, user, jobs)
    return await _read(state, user)
