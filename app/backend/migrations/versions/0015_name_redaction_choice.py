"""Founder decision F12 (2026-10-19): replacing people's names is each user's choice, made on the Learning
page, and off until they turn it on.

* users.redact_names: off by default. Off: names stay in L1 (and reach the model). On: names known from
  headers and the directory, and names Comprehend finds, become person tokens, as before F12. Regulated
  identifiers, contact details, addresses and never-send words are masked either way.

Revision ID: 0015
Revises: 0014
"""

from alembic import op

from vanimo.db.rls import APP_ROLE

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table vanimo.users add column redact_names boolean not null default false")
    op.execute(f"grant update (redact_names) on vanimo.users to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only")
