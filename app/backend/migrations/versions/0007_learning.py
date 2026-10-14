"""M2 learn safely: L1 store, token vault, learning runs, style cards, persona settings, evals.

* l1_items: the user's own sent words (and the message they replied to) after redaction —
  Tier R masked, people tokenised, never-send words as placeholders — vault-encrypted per user.
  Lineage holds only HMACs (item, thread/chat, each participant + their domain hashes), so a
  later exclusion or never-send word can find and purge everything derived (§6.5 X4, X7).
* l1_tokens: token → original value (names, addresses, phones), encrypted, for the owner's
  display only (the re-hydrator, §7.3). Regulated values are never stored anywhere.
* style_cards / persona_settings: the Persona Snapshot and the user's studio choices.
* eval_runs: content-free metrics of the offline style evaluation.

Revision ID: 0007
Revises: 0006
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

OWNER = (
    "tenant_id uuid not null references vanimo.tenants(id) on delete cascade, "
    "owner_user_id uuid not null references vanimo.users(id) on delete cascade"
)
SOURCE = "source_kind text not null check (source_kind in ('graph', 'sample'))"


def _hash(col: str, null: bool = False) -> str:
    return f"{col} text {'' if null else 'not null '}check ({col} ~ '^[0-9a-f]{{64}}$')"


TABLES = {
    "learning_runs": f"""
        id uuid primary key default gen_random_uuid(), {OWNER}, {SOURCE},
        status text not null check (status in ('running', 'done', 'failed')),
        started_at timestamptz not null default now(), finished_at timestamptz,
        heartbeat_at timestamptz not null default now(),
        controls_version bigint, counts jsonb not null default '{{}}',
        error_code text check (length(error_code) <= 80)
    """,
    "l1_items": f"""
        id uuid primary key default gen_random_uuid(), {OWNER}, {SOURCE},
        run_id uuid references vanimo.learning_runs(id) on delete set null,
        channel text not null check (channel in ('email', 'chat')),
        {_hash("item_hash")}, {_hash("thread_hash")},
        {_hash("meeting_hash", null=True)}, {_hash("series_hash", null=True)},
        people jsonb not null default '[]',
        sent_at timestamptz not null,
        subject_enc text, text_enc text not null, context_enc text,
        relationship text not null check (relationship in ('manager', 'report', 'peer', 'external', 'personal')),
        intent text not null check (length(intent) <= 40),
        language text not null check (language in ('english', 'hinglish', 'hindi')),
        word_count integer not null, vec real[],
        suspicious boolean not null default false, held_out boolean not null default false,
        created_at timestamptz not null default now(),
        unique (owner_user_id, source_kind, item_hash)
    """,
    "l1_tokens": f"""
        {OWNER},
        token text not null check (token ~ '^⟦[A-Za-z_0-9.]{{2,40}}⟧$'),
        kind text not null check (kind in ('person', 'email', 'phone')),
        value_enc text not null, created_at timestamptz not null default now(),
        primary key (owner_user_id, token)
    """,
    "style_cards": f"""
        id uuid primary key default gen_random_uuid(), {OWNER}, {SOURCE},
        slice text not null check (length(slice) <= 120),
        level smallint not null check (level between 0 and 4),
        example_count integer not null, card_enc text not null,
        updated_at timestamptz not null default now(),
        unique (owner_user_id, source_kind, slice)
    """,
    "persona_settings": """
        owner_user_id uuid primary key references vanimo.users(id) on delete cascade,
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        settings_enc text not null, updated_at timestamptz not null default now()
    """,
    "eval_runs": f"""
        id uuid primary key default gen_random_uuid(), {OWNER}, {SOURCE},
        kind text not null check (kind in ('offline_baseline')),
        created_at timestamptz not null default now(), metrics jsonb not null
    """,
}

INDEXES = [
    "create unique index learning_runs_one_running on vanimo.learning_runs (owner_user_id) where status = 'running'",
    "create index learning_runs_owner on vanimo.learning_runs (owner_user_id, started_at desc)",
    "create index l1_items_owner on vanimo.l1_items (owner_user_id, source_kind, sent_at)",
    "create index l1_items_thread on vanimo.l1_items (owner_user_id, thread_hash)",
    "create index eval_runs_owner on vanimo.eval_runs (owner_user_id, created_at desc)",
    # A domain belongs to one client account per tenant (two admins adding it at once: one gets 409).
    "create unique index client_account_domains_one on vanimo.client_account_domains (tenant_id, domain_hash)",
]

# Meeting chats are tied to their meeting (a meeting or series rule covers the chat), and chats
# whose roster couldn't be read in full are marked, so their content is never read.
ALTERS = [
    "alter table vanimo.source_chats add column meeting_hash text check (meeting_hash ~ '^[0-9a-f]{64}$'), "
    "add column series_hash text check (series_hash ~ '^[0-9a-f]{64}$'), "
    "add column members_complete boolean not null default true",
]


def upgrade() -> None:
    for name, cols in TABLES.items():
        op.execute(f"create table vanimo.{name} ({cols})")
    for stmt in [*INDEXES, *ALTERS]:
        op.execute(stmt)
    for name in TABLES:
        for stmt in owner_scoped(f"vanimo.{name}"):
            op.execute(stmt)
        op.execute(f"grant select, insert, update, delete on vanimo.{name} to {APP_ROLE}")
    op.execute("alter table vanimo.purge_jobs drop constraint purge_jobs_reason_check")
    op.execute(
        "alter table vanimo.purge_jobs add constraint purge_jobs_reason_check check (reason in ("
        "'exclusion_added', 'exclusion_removed', 'term_added', 'term_removed', 'tenant_policy_changed', "
        "'learning_deleted'))"
    )
    for name, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"revoke all on function vanimo_private.{name} from public")
        op.execute(f"grant execute on function vanimo_private.{name} to {APP_ROLE}")


FUNCTIONS = {
    # Organisation scoping changed (admin): every user of the tenant gets a purge job (their learned
    # data from a newly excluded client is deleted) and a controls bump (a running backfill restarts
    # with the new rules). Callable only inside the caller's own tenant, from an admin transaction.
    # Returns the new jobs (IDs only), which the API starts right after commit.
    "enqueue_tenant_purge()": """
        create function vanimo_private.enqueue_tenant_purge()
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
                 select distinct i.tenant_id, i.owner_user_id, 'tenant_policy_changed' from vanimo.l1_items i
                  where i.tenant_id = v_tenant
            returning id, owner_user_id;
        end
        $$
    """,
    "fail_stale_learning_runs(integer)": """
        create function vanimo_private.fail_stale_learning_runs(p_minutes integer)
        returns integer language sql security definer set search_path = vanimo, pg_temp as $$
            with failed as (
                update vanimo.learning_runs set status = 'failed', finished_at = now(), error_code = 'interrupted'
                 where status = 'running' and heartbeat_at < now() - make_interval(mins => p_minutes)
                returning 1)
            select count(*)::integer from failed
        $$
    """,
}


def downgrade() -> None:
    raise NotImplementedError("forward-only")
