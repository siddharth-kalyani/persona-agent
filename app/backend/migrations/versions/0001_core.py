"""Core tenancy: tenants, users, audit events, RLS helpers, user provisioning.

Revision ID: 0001
Revises:
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, force_rls, owner_scoped

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for stmt in [
        # Functions are executable by PUBLIC by default; every grant must be explicit instead. This must be
        # the global form: per-schema default privileges can only add to the global ones, never revoke.
        "alter default privileges revoke execute on functions from public",
        # Transaction-local identity set by the API on every request (is_local => true).
        """
        create function vanimo.current_tenant_id() returns uuid
        language sql stable as
        $$ select nullif(current_setting('app.tenant_id', true), '')::uuid $$
        """,
        """
        create function vanimo.current_app_user_id() returns uuid
        language sql stable as
        $$ select nullif(current_setting('app.user_id', true), '')::uuid $$
        """,
        """
        create table vanimo.tenants (
            id               uuid primary key default gen_random_uuid(),
            entra_tenant_id  text not null unique,
            cell             text not null,
            data_region      text not null check (data_region in ('IN', 'US')),
            created_at       timestamptz not null default now()
        )
        """,
        """
        create table vanimo.users (
            id                   uuid primary key default gen_random_uuid(),
            tenant_id            uuid not null references vanimo.tenants(id) on delete cascade,
            entra_oid            text not null,
            -- Onboarding gate (architecture §6.5): no message bodies are fetched until the
            -- user finishes or skips the "Choose what Vanimo learns from" review.
            onboarding_state     text not null default 'review_pending'
                                 check (onboarding_state in ('review_pending', 'review_done')),
            review_outcome       text check (review_outcome in ('finished', 'skipped')),
            review_completed_at  timestamptz,
            created_at           timestamptz not null default now(),
            last_seen_at         timestamptz not null default now(),
            unique (tenant_id, entra_oid)
        )
        """,
        """
        create table vanimo.audit_events (
            id           bigint generated always as identity primary key,
            tenant_id    uuid not null references vanimo.tenants(id) on delete cascade,
            user_id      uuid not null references vanimo.users(id) on delete cascade,
            action       text not null check (action ~ '^[a-z0-9_.]+$'),
            -- Never raw content or identifiers: a kind plus an opaque or keyed-hash reference.
            target_kind  text check (target_kind ~ '^[a-z0-9_]+$'),
            target_ref   text check (length(target_ref) <= 128),
            request_id   text check (length(request_id) <= 64),
            occurred_at  timestamptz not null default now()
        )
        """,
        "create index audit_events_tenant_user_time on vanimo.audit_events (tenant_id, user_id, occurred_at desc)",
    ]:
        op.execute(stmt)

    # tenants: the API sees only its own tenant row.
    for stmt in [
        *force_rls("vanimo.tenants"),
        f"create policy app_self on vanimo.tenants to {APP_ROLE} using (id = vanimo.current_tenant_id())",
        *force_rls("vanimo.users"),
        f"""create policy app_self on vanimo.users to {APP_ROLE}
            using (tenant_id = vanimo.current_tenant_id() and id = vanimo.current_app_user_id())
            with check (tenant_id = vanimo.current_tenant_id() and id = vanimo.current_app_user_id())""",
        *owner_scoped("vanimo.audit_events", user_column="user_id"),
    ]:
        op.execute(stmt)

    # Provisioning on first sign-in runs before the user's ID is known, so it is a
    # SECURITY DEFINER function with a fixed search_path; it can only create or touch
    # the caller's own tenant/user pair and returns just their IDs.
    op.execute(
        """
        create function vanimo_private.provision_user(
            p_entra_tenant_id text, p_entra_oid text, p_cell text, p_data_region text)
        returns table (tenant_id uuid, user_id uuid)
        language plpgsql security definer
        set search_path = vanimo, pg_temp
        as $$
        declare
            v_tenant uuid;
            v_user uuid;
        begin
            if p_entra_tenant_id !~ '^[0-9a-f-]{36}$' or p_entra_oid !~ '^[0-9a-f-]{36}$' then
                raise exception 'invalid identifiers' using errcode = '22023';
            end if;
            insert into vanimo.tenants (entra_tenant_id, cell, data_region)
            values (p_entra_tenant_id, p_cell, p_data_region)
            on conflict (entra_tenant_id) do nothing;
            select t.id into v_tenant from vanimo.tenants t where t.entra_tenant_id = p_entra_tenant_id;

            insert into vanimo.users as u (tenant_id, entra_oid)
            values (v_tenant, p_entra_oid)
            on conflict on constraint users_tenant_id_entra_oid_key
            do update set last_seen_at = now()
            returning u.id into v_user;
            return query select v_tenant, v_user;
        end
        $$
        """
    )
    for stmt in [
        "revoke all on function vanimo_private.provision_user(text, text, text, text) from public",
        f"grant execute on function vanimo_private.provision_user(text, text, text, text) to {APP_ROLE}",
        f"grant execute on function vanimo.current_tenant_id() to {APP_ROLE}",
        f"grant execute on function vanimo.current_app_user_id() to {APP_ROLE}",
        f"grant select on vanimo.tenants to {APP_ROLE}",
        f"grant select on vanimo.users to {APP_ROLE}",
        f"grant update (onboarding_state, review_outcome, review_completed_at, last_seen_at) "
        f"on vanimo.users to {APP_ROLE}",
        f"grant select, insert on vanimo.audit_events to {APP_ROLE}",
    ]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("drop function if exists vanimo_private.provision_user(text, text, text, text)")
    op.execute("drop table if exists vanimo.audit_events")
    op.execute("drop table if exists vanimo.users")
    op.execute("drop table if exists vanimo.tenants")
    op.execute("drop function if exists vanimo.current_app_user_id()")
    op.execute("drop function if exists vanimo.current_tenant_id()")
