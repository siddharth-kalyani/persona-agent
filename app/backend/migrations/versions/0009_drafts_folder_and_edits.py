"""M4 drafts folder + edit loop: drafts placed in Outlook, the drafts queue, draft↔sent matching,
learned style rules with their evidence.

* drafts (new columns): the message a reply answers and the draft placed in the user's Outlook
  Drafts folder (Graph IDs, vault-encrypted — they identify mailbox items), its state, and where
  the draft↔sent matching stands. Nothing of the sent message is stored here.
* edit_events: one per matched draft — the outcome (sent as is / light / heavy edit / rewritten),
  the edit share and the content-free edit kinds. Deleted with its draft (lineage purges reach it).
* style_rules: rules learned from edits (greeting, sign-off, length, phrases to avoid, word
  preferences, exclamation marks), scoped by relationship, with candidate → active → confirmed /
  rejected. The value (a form or phrase, L1) is vault-encrypted; the key is an HMAC.
* rule_evidence: which edit events support or contradict a rule. When a purge deletes drafts,
  their evidence goes with them and the rule is re-counted (§6.5 X7: no rule evidence survives).
* drafting_settings: the user's opt-in to drafts in their Outlook Drafts folder.
* queue_dismissals: conversations the user marked "no reply needed" (thread HMAC only).
* tenant_policies.server_drafts: the organisation allows drafts in mailboxes (D8: one app holds
  Mail.ReadWrite until the Read/Compose split; this is the admin's switch meanwhile).

Revision ID: 0009
Revises: 0008
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

OWNER = (
    "tenant_id uuid not null references vanimo.tenants(id) on delete cascade, "
    "owner_user_id uuid not null references vanimo.users(id) on delete cascade"
)
HASH = r"text not null check ({} ~ '^[0-9a-f]{{64}}$')"

TABLES = {
    "edit_events": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        draft_id uuid not null unique references vanimo.drafts(id) on delete cascade,
        source_kind text not null check (source_kind in ('graph', 'sample')),
        created_at timestamptz not null default now(),
        outcome text not null check (outcome in ('sent_as_is', 'light_edit', 'heavy_edit', 'rewritten')),
        edit_share real not null check (edit_share between 0 and 1),
        draft_words integer not null, sent_words integer not null,
        relationship text not null check (relationship in ('manager', 'report', 'peer', 'external', 'personal')),
        edits jsonb not null default '[]'
    """,
    "style_rules": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        source_kind text not null check (source_kind in ('graph', 'sample')),
        scope text not null check (scope in ('manager', 'report', 'peer', 'external', 'personal', '*')),
        kind text not null check (kind in ('greeting', 'sign_off', 'length', 'avoid', 'prefer', 'exclamations')),
        key_hash {HASH.format("key_hash")},
        value_enc text not null,
        status text not null default 'candidate' check (status in ('candidate', 'active', 'confirmed', 'rejected')),
        evidence integer not null default 0, contradictions integer not null default 0,
        support real check (support between 0 and 1),
        first_seen timestamptz not null default now(), last_seen timestamptz not null default now(),
        decided_at timestamptz,
        unique (owner_user_id, source_kind, key_hash)
    """,
    "rule_evidence": f"""
        {OWNER},
        rule_id uuid not null references vanimo.style_rules(id) on delete cascade,
        edit_event_id uuid not null references vanimo.edit_events(id) on delete cascade,
        supports boolean not null,
        primary key (rule_id, edit_event_id)
    """,
    "drafting_settings": """
        owner_user_id uuid primary key references vanimo.users(id) on delete cascade,
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        outlook_drafts boolean not null default false,
        stale_days integer not null default 3 check (stale_days between 1 and 14),
        updated_at timestamptz not null default now()
    """,
    "queue_dismissals": f"""
        {OWNER},
        thread_hash {HASH.format("thread_hash")},
        dismissed_at timestamptz not null default now(),
        primary key (owner_user_id, thread_hash)
    """,
}

ALTERS = [
    # The message a reply answers (to place it in Outlook later), and the placed draft.
    "alter table vanimo.drafts add column reply_to_enc text, "
    "add column placed_ref_enc text, add column placed_link_enc text, add column placed_at timestamptz, "
    "add column placed_state text check (placed_state in ('placed', 'sent', 'removed_stale', 'replaced', 'kept_edited', "
    "'gone')), "
    "add column match_state text not null default 'pending' "
    "check (match_state in ('pending', 'matched', 'unmatched', 'excluded', 'not_tracked'))",
    "alter table vanimo.drafts drop constraint drafts_surface_check, "
    "add constraint drafts_surface_check check (surface in ('outlook', 'web', 'queue'))",
    "create index drafts_pending_match on vanimo.drafts (owner_user_id, created_at) where match_state = 'pending'",
    "create index style_rules_owner on vanimo.style_rules (owner_user_id, source_kind, status)",
    "alter table vanimo.tenant_policies add column server_drafts boolean not null default true",
]


def upgrade() -> None:
    for name, cols in TABLES.items():
        op.execute(f"create table vanimo.{name} ({cols})")
        for stmt in owner_scoped(f"vanimo.{name}"):
            op.execute(stmt)
        op.execute(f"grant select, insert, update, delete on vanimo.{name} to {APP_ROLE}")
    for stmt in ALTERS:
        op.execute(stmt)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
