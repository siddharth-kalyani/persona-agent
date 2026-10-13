"""Local email + password sign-in (local/dev only) and sessions.

The API role gets no direct access to these tables. It goes through narrow SECURITY
DEFINER functions: look up a login, record its result, create/resolve/revoke a session,
change the password of the session's own user. Session tokens are stored only as SHA-256
hashes; passwords only as scrypt hashes.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, force_rls

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FUNCTIONS = {
    "password_login_lookup(text)": """
        create function vanimo_private.password_login_lookup(p_email text)
        returns table (user_id uuid, tenant_id uuid, password_hash text, must_change boolean,
                       locked_until timestamptz, roles text[])
        language sql stable security definer set search_path = vanimo, pg_temp as $$
            select c.user_id, u.tenant_id, c.password_hash, c.must_change_password, c.locked_until, c.roles
            from vanimo.local_credentials c join vanimo.users u on u.id = c.user_id
            where c.email = lower(p_email)
        $$
    """,
    "password_login_result(uuid,boolean)": """
        create function vanimo_private.password_login_result(p_user uuid, p_success boolean)
        returns void language plpgsql security definer set search_path = vanimo, pg_temp as $$
        begin
            if p_success then
                update vanimo.local_credentials
                   set failed_attempts = 0, locked_until = null, last_login_at = now()
                 where user_id = p_user;
            else
                -- 5 failures in a row lock the account for 15 minutes.
                update vanimo.local_credentials
                   set failed_attempts = failed_attempts + 1,
                       locked_until = case when failed_attempts + 1 >= 5
                                           then now() + interval '15 minutes' else locked_until end
                 where user_id = p_user;
            end if;
        end $$
    """,
    "session_create(uuid,text,integer)": """
        create function vanimo_private.session_create(p_user uuid, p_token_hash text, p_ttl_seconds integer)
        returns timestamptz language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare v_expires timestamptz := now() + make_interval(secs => least(p_ttl_seconds, 43200));
        begin
            if p_token_hash !~ '^[0-9a-f]{64}$' then
                raise exception 'invalid token hash' using errcode = '22023';
            end if;
            insert into vanimo.sessions (token_hash, user_id, tenant_id, expires_at)
            select p_token_hash, u.id, u.tenant_id, v_expires
              from vanimo.users u join vanimo.local_credentials c on c.user_id = u.id
             where u.id = p_user and (c.locked_until is null or c.locked_until < now());
            if not found then
                raise exception 'cannot create session' using errcode = '42501';
            end if;
            return v_expires;
        end $$
    """,
    "session_resolve(text)": """
        create function vanimo_private.session_resolve(p_token_hash text)
        returns table (user_id uuid, tenant_id uuid, roles text[], must_change boolean, email text,
                       expires_at timestamptz)
        language plpgsql security definer set search_path = vanimo, pg_temp as $$
        begin
            update vanimo.sessions s set last_seen_at = now()
             where s.token_hash = p_token_hash and s.revoked_at is null and s.expires_at > now();
            return query
                select s.user_id, s.tenant_id, c.roles, c.must_change_password, c.email, s.expires_at
                  from vanimo.sessions s join vanimo.local_credentials c on c.user_id = s.user_id
                 where s.token_hash = p_token_hash and s.revoked_at is null and s.expires_at > now();
        end $$
    """,
    "session_revoke(text)": """
        create function vanimo_private.session_revoke(p_token_hash text)
        returns void language sql security definer set search_path = vanimo, pg_temp as $$
            update vanimo.sessions set revoked_at = now() where token_hash = p_token_hash and revoked_at is null
        $$
    """,
    "password_change(text,text)": """
        create function vanimo_private.password_change(p_token_hash text, p_new_hash text)
        returns uuid language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare v_user uuid;
        begin
            -- Only the user of a live session can change their own password.
            select s.user_id into v_user from vanimo.sessions s
             where s.token_hash = p_token_hash and s.revoked_at is null and s.expires_at > now();
            if v_user is null then
                raise exception 'no live session' using errcode = '42501';
            end if;
            update vanimo.local_credentials
               set password_hash = p_new_hash, must_change_password = false, password_changed_at = now(),
                   failed_attempts = 0, locked_until = null
             where user_id = v_user;
            -- Every existing session (including this one) ends; the caller signs in again.
            update vanimo.sessions set revoked_at = now() where user_id = v_user and revoked_at is null;
            return v_user;
        end $$
    """,
}


def upgrade() -> None:
    for stmt in [
        """
        create table vanimo.local_credentials (
            user_id               uuid primary key references vanimo.users(id) on delete cascade,
            email                 text not null unique check (email = lower(email) and email like '%_@_%'),
            password_hash         text not null check (password_hash like 'scrypt$%'),
            must_change_password  boolean not null default true,
            roles                 text[] not null default '{Vanimo.User}',
            failed_attempts       integer not null default 0,
            locked_until          timestamptz,
            password_changed_at   timestamptz,
            last_login_at         timestamptz,
            created_at            timestamptz not null default now()
        )
        """,
        """
        create table vanimo.sessions (
            token_hash    text primary key check (token_hash ~ '^[0-9a-f]{64}$'),
            user_id       uuid not null references vanimo.users(id) on delete cascade,
            tenant_id     uuid not null references vanimo.tenants(id) on delete cascade,
            created_at    timestamptz not null default now(),
            last_seen_at  timestamptz not null default now(),
            expires_at    timestamptz not null,
            revoked_at    timestamptz
        )
        """,
        "create index sessions_user on vanimo.sessions (user_id) where revoked_at is null",
        # FORCE RLS with only the owner policy: the API role can't read or write these tables at all.
        *force_rls("vanimo.local_credentials"),
        *force_rls("vanimo.sessions"),
    ]:
        op.execute(stmt)
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"revoke all on function vanimo_private.{signature} from public")
        op.execute(f"grant execute on function vanimo_private.{signature} to {APP_ROLE}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"drop function if exists vanimo_private.{signature}")
    op.execute("drop table if exists vanimo.sessions")
    op.execute("drop table if exists vanimo.local_credentials")
