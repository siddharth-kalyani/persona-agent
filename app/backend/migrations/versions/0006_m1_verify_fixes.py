"""M1 verification fixes.

* users.reviewed_sources: the set of data sources the user reviewed (reviewing the sample
  workspace no longer re-locks an earlier Microsoft 365 review).
* purge_jobs.lease_until / attempts: the sweeper claims jobs with a lease (no double runs, safe
  with several API tasks) and retries failed jobs up to 3 times.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

from vanimo.db.rls import APP_ROLE

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in [
        "alter table vanimo.users add column reviewed_sources text[] not null default '{}'",
        "update vanimo.users set reviewed_sources = array[reviewed_source_kind] where reviewed_source_kind is not null",
        f"grant update (reviewed_sources) on vanimo.users to {APP_ROLE}",
        "alter table vanimo.purge_jobs add column lease_until timestamptz, "
        "add column attempts integer not null default 0",
        "drop function vanimo_private.stale_purge_jobs(integer)",
        """
        create function vanimo_private.claim_purge_jobs(p_minutes integer)
        returns table (job_id uuid, tenant_id uuid, user_id uuid, reason text)
        language sql security definer set search_path = vanimo, pg_temp as $$
            with due as (
                select id from vanimo.purge_jobs
                 where (status = 'pending' and requested_at < now() - make_interval(mins => p_minutes))
                    or (status = 'running' and (lease_until is null or lease_until < now())
                        and requested_at < now() - make_interval(mins => p_minutes))
                    or (status = 'failed' and attempts < 3)
                 order by requested_at
                 limit 100
                 for update skip locked)
            update vanimo.purge_jobs j
               set status = 'running', lease_until = now() + interval '10 minutes', attempts = j.attempts + 1
              from due where j.id = due.id
            returning j.id, j.tenant_id, j.owner_user_id, j.reason
        $$
        """,
        "revoke all on function vanimo_private.claim_purge_jobs(integer) from public",
        f"grant execute on function vanimo_private.claim_purge_jobs(integer) to {APP_ROLE}",
    ]:
        op.execute(stmt)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
