"""M4 review fixes.

* drafts.audience_enc: the recipients Vanimo checked (vault-encrypted), so a draft put in Outlook
  is addressed to exactly them, never to whatever Reply-To the sender set.
* drafts.checked_sent: HMACs of sent messages already compared with this draft and rejected (a
  "new email" draft isn't starved by other mail to the same person, nor are they re-read).
* drafts.match_state 'superseded' (an older draft in a conversation the user answered once) and
  placed_state 'placing' (a claim, so two clicks can't create two Outlook drafts).
* edit_events.sent_hash: the sent message a draft was matched to (HMAC); one draft per sent message.
* orphan_placements: Outlook drafts Vanimo placed whose record a purge deleted. The mailbox item
  can only be tidied while the user is signed in, so its ID (encrypted) waits here until then.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

STATEMENTS = [
    "alter table vanimo.drafts add column audience_enc text, add column checked_sent jsonb not null default '[]'",
    "alter table vanimo.drafts drop constraint drafts_match_state_check, add constraint drafts_match_state_check "
    "check (match_state in ('pending', 'matched', 'unmatched', 'excluded', 'not_tracked', 'superseded'))",
    "alter table vanimo.drafts drop constraint drafts_placed_state_check, add constraint drafts_placed_state_check "
    "check (placed_state in ('placing', 'placed', 'sent', 'removed_stale', 'replaced', 'kept_edited', 'gone'))",
    "alter table vanimo.edit_events add column sent_hash text check (sent_hash ~ '^[0-9a-f]{64}$')",
    "create unique index edit_events_one_per_sent on vanimo.edit_events (owner_user_id, sent_hash)",
]

ORPHANS = """
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
    owner_user_id uuid not null references vanimo.users(id) on delete cascade,
    source_kind text not null check (source_kind in ('graph', 'sample')),
    placed_ref_enc text not null,
    placed_at timestamptz not null,
    created_at timestamptz not null default now()
"""


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)
    op.execute(f"create table vanimo.orphan_placements ({ORPHANS})")
    for stmt in owner_scoped("vanimo.orphan_placements"):
        op.execute(stmt)
    op.execute(f"grant select, insert, update, delete on vanimo.orphan_placements to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only")
