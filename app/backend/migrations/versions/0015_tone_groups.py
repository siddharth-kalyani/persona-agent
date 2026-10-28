"""F15 tone groups: every conversation gets a tone (formal, friendly, casual), learning is per channel
bucket (email, Teams 1:1, Teams group), and a vocabulary per tone is shared across the three.

* l1_items.bucket / tone: where a learned message was written (email, dm, group) and the tone of its
  conversation when it was learned. counterpart: who it was written to, as a hash (the first To recipient
  of an email, the other person in a 1:1 chat, the group chat itself), so the user's greeting for each
  person can be learned. situations: what the message does (request, update, thanks…),
  content-free. phrases_enc: the user's own short phrases for each situation (L1, vault-encrypted per user),
  from which the per-tone vocabulary is counted; they go wherever the message goes (purges, scrubs, Macie).
* conversation_tones: one row per conversation partner — a person (email or Teams 1:1) or a group chat —
  with its tone, why (your messages, theirs, the directory, the default), who judged it (Claude or the
  rules), how many messages it was judged from, and the user's own choice (`override`, which wins).
  Content-free: hashes and labels only; names come from the Sources index when shown. `people` is the
  lineage (person and domain hashes) and `chat_hash` the chat it was learned in (1:1 and group chats): a
  purge judges it by both, as it judges l1_items.
* drafts.tone: the tone a draft was written in (content-free), shown in the drafts list.
* The vocabulary and how the user greets each person live in style_cards (already L1, snapshotted, purged
  and rebuilt), so no new text table is needed.

Revision ID: 0015
Revises: 0014
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

TONES = "('formal', 'friendly', 'casual')"
HASH = "text not null check ({} ~ '^[0-9a-f]{{64}}$')"

STATEMENTS = [
    "alter table vanimo.l1_items "
    "add column bucket text not null default 'email' check (bucket in ('email', 'dm', 'group')), "
    f"add column tone text not null default 'formal' check (tone in {TONES}), "
    "add column counterpart text check (counterpart ~ '^[0-9a-f]{64}$'), "
    "add column situations text[] not null default '{}' "
    "check (cardinality(situations) <= 9 and array_to_string(situations, ',') ~ '^[a-z,]*$'), "
    "add column phrases_enc text",
    # Learned before buckets existed: chats count as group chats until the user learns again (drafting
    # asks them to: learning_runs.counts.version).
    "update vanimo.l1_items set bucket = 'group' where channel = 'chat'",
    # The Macie snapshot goes stale when learned text changes: the phrases are learned text too.
    "drop trigger snapshot_stale_on_update on vanimo.l1_items",
    "create trigger snapshot_stale_on_update after update of subject_enc, text_enc, context_enc, phrases_enc "
    "on vanimo.l1_items for each row execute function vanimo.mark_snapshot_stale()",
    f"""
    create table vanimo.conversation_tones (
        id uuid primary key default gen_random_uuid(),
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        owner_user_id uuid not null references vanimo.users(id) on delete cascade,
        source_kind text not null check (source_kind in ('graph', 'sample')),
        bucket text not null check (bucket in ('email', 'dm', 'group')),
        key_hash {HASH.format("key_hash")},
        people jsonb not null default '[]',
        chat_hash text check (chat_hash ~ '^[0-9a-f]{{64}}$'),
        tone text not null check (tone in {TONES}),
        basis text not null check (basis in ('your_messages', 'their_messages', 'directory', 'default')),
        judged_by text not null check (judged_by in ('ai', 'rules')),
        mine integer not null default 0,
        theirs integer not null default 0,
        override text check (override in {TONES}),
        updated_at timestamptz not null default now(),
        unique (owner_user_id, source_kind, bucket, key_hash)
    )
    """,
    *owner_scoped("vanimo.conversation_tones"),
    f"grant select, insert, update, delete on vanimo.conversation_tones to {APP_ROLE}",
    f"alter table vanimo.drafts add column tone text check (tone in {TONES})",
]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("alter table vanimo.drafts drop column tone")
    op.execute("drop table vanimo.conversation_tones")
    op.execute("drop trigger snapshot_stale_on_update on vanimo.l1_items")
    op.execute(
        "create trigger snapshot_stale_on_update after update of subject_enc, text_enc, context_enc "
        "on vanimo.l1_items for each row execute function vanimo.mark_snapshot_stale()"
    )
    op.execute(
        "alter table vanimo.l1_items drop column phrases_enc, drop column situations, drop column counterpart, "
        "drop column tone, drop column bucket"
    )
