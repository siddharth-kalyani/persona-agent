"""M5 commitments + Teams.

* commitments: the user's own promises, found in their sent email and Teams chat messages (only
  allowed sources, L1). The promise as written and its short form are vault-encrypted L1; the due
  date is worked out in code. Lineage (item, thread or chat, meeting, participants and their
  domains) as for learned items, so exclusions, never-send words and "delete what Vanimo learned"
  reach them (§6.5 X7). `ref_enc` is the conversation or chat a follow-up goes to (encrypted).
* commitment_scans: how far the incremental "new promises" scan has read, per source.
* notifications: the notification channel (in-app, and Teams activity feed when configured).
  Content-free: a kind, a count and a period key; never a name, subject or promise.
* drafts: Teams chat drafts (channel 'chat', the chat's meeting lineage, the chat ID encrypted for
  the Teams edit loop), and the Teams and Commitments surfaces.
* tenant_policies: open Teams chats with the draft typed in (after the prefill spike passes),
  and Teams activity notifications.
* notification_candidates(): the sweeper's cross-tenant list of users who may need a notification
  (IDs only, like the other housekeeping functions).
* enqueue_tenant_purge() also queues users who have commitments but nothing learned or drafted.

Revision ID: 0011
Revises: 0010
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

OWNER = (
    "tenant_id uuid not null references vanimo.tenants(id) on delete cascade, "
    "owner_user_id uuid not null references vanimo.users(id) on delete cascade"
)
HASH = r"check ({} ~ '^[0-9a-f]{{64}}$')"

TABLES = {
    "commitments": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        source_kind text not null check (source_kind in ('graph', 'sample')),
        channel text not null check (channel in ('email', 'chat')),
        item_hash text not null {HASH.format("item_hash")},
        ordinal smallint not null check (ordinal between 0 and 20),
        thread_hash text not null {HASH.format("thread_hash")},
        meeting_hash text {HASH.format("meeting_hash")},
        series_hash text {HASH.format("series_hash")},
        people jsonb not null default '[]',
        relationship text not null check (relationship in ('manager', 'report', 'peer', 'external', 'personal')),
        made_at timestamptz not null,
        text_enc text not null,
        what_enc text not null,
        due_at timestamptz,
        due_phrase_enc text,
        ref_enc text,
        extractor text not null check (extractor in ('offline', 'bedrock')),
        status text not null default 'open' check (status in ('open', 'done', 'dismissed')),
        status_at timestamptz,
        snoozed_until timestamptz,
        done_hint_at timestamptz,
        created_at timestamptz not null default now(),
        unique (owner_user_id, item_hash, ordinal)
    """,
    "commitment_scans": """
        owner_user_id uuid not null references vanimo.users(id) on delete cascade,
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        source_kind text not null check (source_kind in ('graph', 'sample')),
        scanned_until timestamptz not null,
        updated_at timestamptz not null default now(),
        primary key (owner_user_id, source_kind)
    """,
    "notifications": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        kind text not null check (kind in ('commitments_due', 'rules_to_confirm', 'review_reminder')),
        period text not null check (period ~ '^[0-9A-Za-z:_-]{{1,32}}$'),
        count integer not null check (count >= 0),
        created_at timestamptz not null default now(),
        read_at timestamptz,
        teams_state text not null default 'pending' check (teams_state in ('pending', 'sent', 'failed', 'off')),
        unique (owner_user_id, kind, period)
    """,
}

ALTERS = [
    "alter table vanimo.drafts add column channel text not null default 'email' check (channel in ('email', 'chat')), "
    f"add column meeting_hash text {HASH.format('meeting_hash')}, "
    f"add column series_hash text {HASH.format('series_hash')}, "
    "add column chat_ref_enc text",
    "alter table vanimo.drafts drop constraint drafts_surface_check, add constraint drafts_surface_check "
    "check (surface in ('outlook', 'web', 'queue', 'teams', 'commitments'))",
    "alter table vanimo.drafts drop constraint drafts_outcome_check, add constraint drafts_outcome_check "
    "check (outcome in ('inserted', 'copied', 'opened_reply', 'opened_chat', 'discarded'))",
    "create index commitments_open on vanimo.commitments (owner_user_id, due_at) where status = 'open'",
    "create index commitments_thread on vanimo.commitments (owner_user_id, thread_hash)",
    "alter table vanimo.tenant_policies add column teams_prefill boolean not null default false, "
    "add column teams_notifications boolean not null default true",
]

FUNCTIONS = {
    # Users who may need a notification now: open promises due within a day (or overdue, not
    # snoozed), rules waiting for a decision, or a review still pending a day after sign-up.
    # Cross-tenant, so SECURITY DEFINER; it returns IDs only and the sweeper does the rest
    # inside each user's own RLS transaction.
    "notification_candidates(integer)": """
        create function vanimo_private.notification_candidates(p_limit integer)
        returns table (tenant_id uuid, user_id uuid) language sql security definer
        set search_path = vanimo, pg_temp as $$
            select u.tenant_id, u.id from vanimo.users u
             where exists (select 1 from vanimo.commitments c
                            where c.owner_user_id = u.id and c.status = 'open' and c.due_at is not null
                              and c.due_at < now() + interval '1 day'
                              and (c.snoozed_until is null or c.snoozed_until < now()))
                or exists (select 1 from vanimo.style_rules r
                            where r.owner_user_id = u.id and r.status = 'active')
                or (u.onboarding_state = 'review_pending' and u.created_at < now() - interval '1 day'
                    and u.created_at > now() - interval '14 days')
             order by u.id
             limit greatest(1, least(p_limit, 5000))
        $$
    """,
    "enqueue_tenant_purge()": """
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
                     union
                     select c.tenant_id, c.owner_user_id from vanimo.commitments c where c.tenant_id = v_tenant
                 ) o
            returning id, owner_user_id;
        end
        $$
    """,
}


def upgrade() -> None:
    for name, cols in TABLES.items():
        op.execute(f"create table vanimo.{name} ({cols})")
        for stmt in owner_scoped(f"vanimo.{name}"):
            op.execute(stmt)
        op.execute(f"grant select, insert, update, delete on vanimo.{name} to {APP_ROLE}")
    for stmt in ALTERS:
        op.execute(stmt)
    for name, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"revoke all on function vanimo_private.{name} from public")
        op.execute(f"grant execute on function vanimo_private.{name} to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only")
