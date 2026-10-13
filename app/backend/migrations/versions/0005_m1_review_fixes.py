"""M1 review fixes.

* users.reviewed_source_kind: the onboarding gate is per data source — reviewing the sample
  workspace must never unlock reading a real mailbox.
* never_send_terms.folds: Hinglish-folded matching (aa→a, w→v …) is opt-in per word, shown to
  the user for confirmation (docs/research/12 §9.6), not applied silently.
* tenant_org_domains: the organisation's own domains, known tenant-wide (not from one user's
  latest scan), so "approved clients only" never excludes colleagues. Written only through
  record_org_domains (any user may add domains their own Microsoft 365 reports as verified).
* Sweeper functions so background work survives restarts: fail stale scans, list stale jobs.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, force_rls

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

FUNCTIONS = {
    "record_org_domains(text[])": """
        create function vanimo_private.record_org_domains(p_hashes text[])
        returns void language sql security definer set search_path = vanimo, pg_temp as $$
            insert into vanimo.tenant_org_domains (tenant_id, domain_hash)
            select vanimo.current_tenant_id(), h from unnest(p_hashes) as h
            where vanimo.current_tenant_id() is not null and h ~ '^[0-9a-f]{64}$'
            on conflict do nothing
        $$
    """,
    "fail_stale_scans(integer)": """
        create function vanimo_private.fail_stale_scans(p_minutes integer)
        returns integer language sql security definer set search_path = vanimo, pg_temp as $$
            with failed as (
                update vanimo.source_scans set status = 'failed', finished_at = now(), error_code = 'interrupted'
                 where status = 'running' and started_at < now() - make_interval(mins => p_minutes)
                returning 1)
            select count(*)::integer from failed
        $$
    """,
    "stale_purge_jobs(integer)": """
        create function vanimo_private.stale_purge_jobs(p_minutes integer)
        returns table (job_id uuid, tenant_id uuid, user_id uuid, reason text)
        language sql security definer set search_path = vanimo, pg_temp as $$
            select id, tenant_id, owner_user_id, reason from vanimo.purge_jobs
             where status in ('pending', 'running') and requested_at < now() - make_interval(mins => p_minutes)
             order by requested_at limit 100
        $$
    """,
}


def upgrade() -> None:
    for stmt in [
        "alter table vanimo.users add column reviewed_source_kind text "
        "check (reviewed_source_kind in ('graph', 'sample'))",
        "update vanimo.users set reviewed_source_kind = 'sample' where onboarding_state = 'review_done'",
        f"grant update (reviewed_source_kind) on vanimo.users to {APP_ROLE}",
        "alter table vanimo.never_send_terms add column folds boolean not null default false",
        """
        create table vanimo.tenant_org_domains (
            tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
            domain_hash text not null check (domain_hash ~ '^[0-9a-f]{64}$'),
            primary key (tenant_id, domain_hash)
        )
        """,
        *force_rls("vanimo.tenant_org_domains"),
        f"create policy app_read on vanimo.tenant_org_domains for select to {APP_ROLE} "
        "using (tenant_id = vanimo.current_tenant_id())",
        f"grant select on vanimo.tenant_org_domains to {APP_ROLE}",
    ]:
        op.execute(stmt)
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"revoke all on function vanimo_private.{signature} from public")
        op.execute(f"grant execute on function vanimo_private.{signature} to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only")
