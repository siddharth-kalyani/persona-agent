"""M1 data controls: Sources index, exclusion rules, never-send terms, client/account scoping,
purge jobs (architecture §6.5, docs/research/12 §9).

* Sources index (header pass): people, threads, messages, chats, meetings and their links.
  Display fields are vault-encrypted per user (`*_enc`); identifiers are per-tenant HMACs
  (`key_hash`); subjects/topics are never-send-masked *before* encryption.
* exclusion_rules: user rules only. The organisation's rules live in client_accounts
  (+ domains, + sensitive terms) and tenant_policies; one engine evaluates both.
* Tenant tables are readable by every user of the tenant (the engine needs them) and writable
  only in a transaction flagged admin (`app.is_admin`, set by the API after its role check).

Revision ID: 0004
Revises: 0003
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped, tenant_admin_writable

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

OWNER = (
    "tenant_id uuid not null references vanimo.tenants(id) on delete cascade, "
    "owner_user_id uuid not null references vanimo.users(id) on delete cascade"
)
HASH = "text not null check (key_hash ~ '^[0-9a-f]{64}$')"

USER_TABLES = {
    "source_scans": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        source_kind text not null check (source_kind in ('graph', 'sample')),
        status text not null check (status in ('running', 'done', 'failed')),
        started_at timestamptz not null default now(), finished_at timestamptz,
        counts jsonb not null default '{{}}', error_code text check (length(error_code) <= 80)
    """,
    "source_people": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        key_hash {HASH}, domain_hash text not null check (domain_hash ~ '^[0-9a-f]{{64}}$'),
        email_enc text not null, name_enc text, domain_enc text not null,
        is_internal boolean not null, is_consumer boolean not null,
        sent_count integer not null default 0, chat_count integer not null default 0,
        meeting_count integer not null default 0, last_contact_at timestamptz,
        unique (owner_user_id, key_hash)
    """,
    "source_threads": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        key_hash {HASH}, subject_enc text, message_count integer not null, last_sent_at timestamptz,
        is_forward boolean not null default false,
        unique (owner_user_id, key_hash)
    """,
    "source_messages": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        key_hash {HASH}, thread_id uuid not null references vanimo.source_threads(id) on delete cascade,
        sent_at timestamptz not null,
        unique (owner_user_id, key_hash)
    """,
    "source_message_people": f"""
        {OWNER},
        message_id uuid not null references vanimo.source_messages(id) on delete cascade,
        person_id uuid not null references vanimo.source_people(id) on delete cascade,
        primary key (message_id, person_id)
    """,
    "source_chats": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        key_hash {HASH}, chat_type text not null check (chat_type in ('oneOnOne', 'group', 'meeting')),
        topic_enc text, label_enc text not null, member_count integer not null,
        hidden boolean not null default false, last_activity_at timestamptz,
        unique (owner_user_id, key_hash)
    """,
    "source_chat_people": f"""
        {OWNER},
        chat_id uuid not null references vanimo.source_chats(id) on delete cascade,
        person_id uuid not null references vanimo.source_people(id) on delete cascade,
        primary key (chat_id, person_id)
    """,
    "source_meetings": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        key_hash {HASH}, series_hash text check (series_hash ~ '^[0-9a-f]{{64}}$'),
        subject_enc text, start_at timestamptz not null, is_private boolean not null,
        is_online boolean not null, is_organizer boolean not null, attendee_count integer not null,
        unique (owner_user_id, key_hash)
    """,
    "source_meeting_people": f"""
        {OWNER},
        meeting_id uuid not null references vanimo.source_meetings(id) on delete cascade,
        person_id uuid not null references vanimo.source_people(id) on delete cascade,
        primary key (meeting_id, person_id)
    """,
    "exclusion_rules": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        kind text not null check (kind in ('person', 'domain', 'chat', 'thread', 'meeting', 'series')),
        key_hash {HASH},
        status text not null default 'active' check (status in ('active', 'revoked')),
        created_at timestamptz not null default now(), revoked_at timestamptz
    """,
    "exclusion_exceptions": f"""
        {OWNER},
        rule_id uuid not null references vanimo.exclusion_rules(id) on delete cascade,
        chat_hash text not null check (chat_hash ~ '^[0-9a-f]{{64}}$'),
        primary key (rule_id, chat_hash)
    """,
    "never_send_terms": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        term_id text not null check (term_id ~ '^[0-9a-f]{{8}}$'),
        term_enc text not null, variants_enc text,
        kind text not null check (kind in ('word', 'name', 'codename')),
        allow_in_drafts boolean not null default false,
        created_at timestamptz not null default now(),
        unique (owner_user_id, term_id)
    """,
    "controls_state": """
        owner_user_id uuid primary key references vanimo.users(id) on delete cascade,
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        version bigint not null default 0, updated_at timestamptz not null default now()
    """,
    "purge_jobs": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        reason text not null check (reason in ('exclusion_added', 'exclusion_removed', 'term_added',
                                               'term_removed', 'tenant_policy_changed')),
        status text not null default 'pending' check (status in ('pending', 'running', 'done', 'held', 'failed')),
        requested_at timestamptz not null default now(), completed_at timestamptz,
        counts jsonb not null default '{{}}'
    """,
}

TENANT_TABLES = {
    "tenant_policies": """
        tenant_id uuid primary key references vanimo.tenants(id) on delete cascade,
        external_mode text not null default 'allow_all' check (external_mode in ('allow_all', 'approved_only')),
        updated_at timestamptz not null default now(), updated_by uuid references vanimo.users(id)
    """,
    "client_accounts": """
        id uuid primary key default gen_random_uuid(),
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        name_enc text not null,
        mode text not null check (mode in ('excluded', 'approved')),
        created_at timestamptz not null default now(), created_by uuid references vanimo.users(id)
    """,
    "client_account_domains": """
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        account_id uuid not null references vanimo.client_accounts(id) on delete cascade,
        domain_hash text not null check (domain_hash ~ '^[0-9a-f]{64}$'),
        domain_enc text not null,
        primary key (account_id, domain_hash)
    """,
    # Company-sensitive (Tier C) words per client, masked at L2 by the redaction pipeline (M2).
    "client_account_terms": """
        id uuid primary key default gen_random_uuid(),
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        account_id uuid not null references vanimo.client_accounts(id) on delete cascade,
        term_enc text not null
    """,
}

INDEXES = [
    "create unique index exclusion_rules_active on vanimo.exclusion_rules (owner_user_id, kind, key_hash) "
    "where status = 'active'",
    "create index source_people_domain on vanimo.source_people (owner_user_id, domain_hash)",
    "create index source_message_people_person on vanimo.source_message_people (person_id)",
    "create index source_chat_people_person on vanimo.source_chat_people (person_id)",
    "create index source_meeting_people_person on vanimo.source_meeting_people (person_id)",
    "create index source_messages_thread on vanimo.source_messages (thread_id)",
    "create index source_meetings_series on vanimo.source_meetings (owner_user_id, series_hash)",
    "create index client_account_domains_hash on vanimo.client_account_domains (tenant_id, domain_hash)",
    "create index purge_jobs_owner on vanimo.purge_jobs (owner_user_id, requested_at desc)",
]


def upgrade() -> None:
    for name, cols in {**USER_TABLES, **TENANT_TABLES}.items():
        op.execute(f"create table vanimo.{name} ({cols})")
    for stmt in INDEXES:
        op.execute(stmt)
    for name in USER_TABLES:
        user_col = "owner_user_id"
        for stmt in owner_scoped(f"vanimo.{name}", user_column=user_col):
            op.execute(stmt)
        op.execute(f"grant select, insert, update, delete on vanimo.{name} to {APP_ROLE}")
    for name in TENANT_TABLES:
        for stmt in tenant_admin_writable(f"vanimo.{name}"):
            op.execute(stmt)
        op.execute(f"grant select, insert, update, delete on vanimo.{name} to {APP_ROLE}")


def downgrade() -> None:
    for name in [*reversed(list(TENANT_TABLES)), *reversed(list(USER_TABLES))]:
        op.execute(f"drop table if exists vanimo.{name} cascade")
