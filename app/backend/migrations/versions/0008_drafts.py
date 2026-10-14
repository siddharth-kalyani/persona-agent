"""M3 drafting: drafts Vanimo wrote, kept as L1 for the M4 edit loop (draft ↔ sent).

* drafts: the draft exactly as generated (L1 — tokens, slots, never-send placeholders),
  vault-encrypted per user, with HMAC lineage (thread, participants and their domains) so an
  exclusion or a never-send word reaches it like any learned item (§6.5 X7). Check results
  are stored as codes only. One-off drafts in excluded conversations are never stored.
* enqueue_tenant_purge() also queues users who have drafts but nothing learned yet.

Revision ID: 0008
Revises: 0007
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

DRAFTS = """
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
    owner_user_id uuid not null references vanimo.users(id) on delete cascade,
    source_kind text not null check (source_kind in ('graph', 'sample')),
    created_at timestamptz not null default now(),
    surface text not null check (surface in ('outlook', 'web')),
    mode text not null check (mode in ('reply', 'new')),
    generator text not null check (generator in ('offline', 'bedrock')),
    tier text not null check (tier in ('default', 'premium')),
    model_id text check (length(model_id) <= 80),
    relationship text not null check (relationship in ('manager', 'report', 'peer', 'external', 'personal')),
    thread_hash text check (thread_hash ~ '^[0-9a-f]{64}$'),
    people jsonb not null default '[]',
    text_enc text not null,
    checks jsonb not null default '[]',
    word_count integer not null,
    latency_ms integer,
    outcome text check (outcome in ('inserted', 'copied', 'opened_reply', 'discarded')),
    rating text check (rating in ('good', 'bad')),
    outcome_at timestamptz
"""


def upgrade() -> None:
    op.execute(f"create table vanimo.drafts ({DRAFTS})")
    op.execute("create index drafts_owner on vanimo.drafts (owner_user_id, created_at desc)")
    op.execute("create index drafts_thread on vanimo.drafts (owner_user_id, thread_hash)")
    for stmt in owner_scoped("vanimo.drafts"):
        op.execute(stmt)
    op.execute(f"grant select, insert, update, delete on vanimo.drafts to {APP_ROLE}")
    op.execute(
        """
        create or replace function vanimo_private.enqueue_tenant_purge()
        returns table (job_id uuid, user_id uuid) language plpgsql security definer
        set search_path = vanimo, pg_temp as $$
        declare
            v_tenant uuid := vanimo.current_tenant_id();
        begin
            if v_tenant is null or coalesce(current_setting('app.is_admin', true), '') <> 'true' then
                raise exception 'admin transaction required' using errcode = '42501';
            end if;
            insert into vanimo.controls_state (owner_user_id, tenant_id, version)
                 select id, tenant_id, 1 from vanimo.users where tenant_id = v_tenant
            on conflict (owner_user_id) do update
                 set version = vanimo.controls_state.version + 1, updated_at = now();
            return query
            insert into vanimo.purge_jobs (tenant_id, owner_user_id, reason)
                 select distinct o.tenant_id, o.owner_user_id, 'tenant_policy_changed' from (
                     select i.tenant_id, i.owner_user_id from vanimo.l1_items i where i.tenant_id = v_tenant
                     union
                     select d.tenant_id, d.owner_user_id from vanimo.drafts d where d.tenant_id = v_tenant
                 ) o
            returning id, owner_user_id;
        end
        $$
        """
    )
    op.execute("revoke all on function vanimo_private.enqueue_tenant_purge() from public")
    op.execute(f"grant execute on function vanimo_private.enqueue_tenant_purge() to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only")
