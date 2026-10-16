"""M5 review fixes.

* commitments.promise_hash: a promise's key is an HMAC of its item and its normalised sentence, not
  its position in the extractor's answer (a different extractor, or a model's different order, must
  never duplicate a promise or reopen one the user decided on).
* notifications.teams_attempts: a failed Teams delivery is retried (at most 3 times).
* notification_candidates(): users notified longest ago first (no starvation above the limit), and
  only rules still in use count (unconfirmed rules stop after 90 days without an observation).

Revision ID: 0012
Revises: 0011
"""

from alembic import op

from vanimo.db.rls import APP_ROLE

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

STATEMENTS = [
    "delete from vanimo.commitments",  # derived data: the next learning run or scan finds them again
    "alter table vanimo.commitments add column promise_hash text not null check (promise_hash ~ '^[0-9a-f]{64}$'), "
    "drop constraint commitments_owner_user_id_item_hash_ordinal_key",
    "create unique index commitments_one_per_promise on vanimo.commitments (owner_user_id, promise_hash)",
    "create index commitments_item on vanimo.commitments (owner_user_id, item_hash)",
    "alter table vanimo.notifications add column teams_attempts smallint not null default 0",
    "drop function vanimo_private.notification_candidates(integer)",
    """
    create function vanimo_private.notification_candidates(p_limit integer)
    returns table (tenant_id uuid, user_id uuid) language sql security definer
    set search_path = vanimo, pg_temp as $$
        select u.tenant_id, u.id from vanimo.users u
         where exists (select 1 from vanimo.commitments c
                        where c.owner_user_id = u.id and c.status = 'open' and c.due_at is not null
                          and c.due_at < now() + interval '1 day'
                          and (c.snoozed_until is null or c.snoozed_until < now()))
            or exists (select 1 from vanimo.style_rules r
                        where r.owner_user_id = u.id and r.status = 'active'
                          and r.last_seen > now() - interval '90 days')
            or exists (select 1 from vanimo.notifications n
                        where n.owner_user_id = u.id and n.read_at is null
                          and (n.teams_state = 'pending' or (n.teams_state = 'failed' and n.teams_attempts < 3)))
            or (u.onboarding_state = 'review_pending' and u.created_at < now() - interval '1 day'
                and u.created_at > now() - interval '14 days')
         order by (select max(n.created_at) from vanimo.notifications n where n.owner_user_id = u.id) nulls first, u.id
         limit greatest(1, least(p_limit, 5000))
    $$
    """,
    "revoke all on function vanimo_private.notification_candidates(integer) from public",
    f"grant execute on function vanimo_private.notification_candidates(integer) to {APP_ROLE}",
]


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    raise NotImplementedError("forward-only")
