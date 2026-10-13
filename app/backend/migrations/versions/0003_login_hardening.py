"""Harden local sign-in (security review of 0002).

* Lockout is atomic: `password_login_begin` locks the row, clears an expired lock, and charges
  the attempt *before* the password is checked, so parallel guesses can't exceed the limit.
  A successful check refunds it.
* The API role can no longer mint a session for an arbitrary user: a successful check issues a
  short-lived single-use nonce that `session_create` must consume.
* `password_login_lookup` (returned any user's hash on request) is dropped.
* `session_resolve` refreshes `last_seen_at` at most once a minute.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

from vanimo.db.rls import APP_ROLE

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

MAX_ATTEMPTS = 5

NEW_FUNCTIONS = {
    "password_login_begin(text)": f"""
        create function vanimo_private.password_login_begin(p_email text)
        returns table (user_id uuid, tenant_id uuid, password_hash text, must_change boolean, roles text[],
                       locked boolean, now_locked boolean)
        language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare c vanimo.local_credentials%rowtype;
        begin
            select * into c from vanimo.local_credentials where email = lower(p_email) for update;
            if not found then
                return;
            end if;
            if c.locked_until is not null and c.locked_until > now() then
                return query select c.user_id, u.tenant_id, null::text, c.must_change_password, c.roles, true, false
                             from vanimo.users u where u.id = c.user_id;
                return;
            end if;
            if c.locked_until is not null then  -- an expired lock starts a fresh window
                c.failed_attempts := 0;
            end if;
            -- Charge the attempt now; a correct password refunds it in password_login_succeeded.
            update vanimo.local_credentials
               set failed_attempts = c.failed_attempts + 1,
                   locked_until = case when c.failed_attempts + 1 >= {MAX_ATTEMPTS}
                                       then now() + interval '15 minutes' else null end
             where vanimo.local_credentials.user_id = c.user_id;
            return query select c.user_id, u.tenant_id, c.password_hash, c.must_change_password, c.roles, false,
                                c.failed_attempts + 1 >= {MAX_ATTEMPTS}
                         from vanimo.users u where u.id = c.user_id;
        end $$
    """,
    "password_login_succeeded(uuid,text)": """
        create function vanimo_private.password_login_succeeded(p_user uuid, p_nonce_hash text)
        returns void language plpgsql security definer set search_path = vanimo, pg_temp as $$
        begin
            if p_nonce_hash !~ '^[0-9a-f]{64}$' then
                raise exception 'invalid nonce' using errcode = '22023';
            end if;
            update vanimo.local_credentials
               set failed_attempts = 0, locked_until = null, last_login_at = now(),
                   login_nonce_hash = p_nonce_hash, login_nonce_expires = now() + interval '1 minute'
             where user_id = p_user;
        end $$
    """,
    "session_create(uuid,text,text,integer)": """
        create function vanimo_private.session_create(p_user uuid, p_nonce_hash text, p_token_hash text,
                                                      p_ttl_seconds integer)
        returns timestamptz language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare v_expires timestamptz := now() + make_interval(secs => least(p_ttl_seconds, 43200));
        begin
            if p_token_hash !~ '^[0-9a-f]{64}$' then
                raise exception 'invalid token hash' using errcode = '22023';
            end if;
            -- Consume the single-use nonce from a successful password check (proof of login).
            update vanimo.local_credentials
               set login_nonce_hash = null, login_nonce_expires = null
             where user_id = p_user and login_nonce_hash = p_nonce_hash and login_nonce_expires > now()
               and (locked_until is null or locked_until < now());
            if not found then
                raise exception 'cannot create session' using errcode = '42501';
            end if;
            insert into vanimo.sessions (token_hash, user_id, tenant_id, expires_at)
            select p_token_hash, u.id, u.tenant_id, v_expires from vanimo.users u where u.id = p_user;
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
             where s.token_hash = p_token_hash and s.revoked_at is null and s.expires_at > now()
               and s.last_seen_at < now() - interval '1 minute';
            return query
                select s.user_id, s.tenant_id, c.roles, c.must_change_password, c.email, s.expires_at
                  from vanimo.sessions s join vanimo.local_credentials c on c.user_id = s.user_id
                 where s.token_hash = p_token_hash and s.revoked_at is null and s.expires_at > now();
        end $$
    """,
}
DROPPED = [
    "password_login_lookup(text)",
    "password_login_result(uuid,boolean)",
    "session_create(uuid,text,integer)",
    "session_resolve(text)",
]


def upgrade() -> None:
    op.execute(
        "alter table vanimo.local_credentials add column login_nonce_hash text, "
        "add column login_nonce_expires timestamptz"
    )
    for signature in DROPPED:
        op.execute(f"drop function vanimo_private.{signature}")
    for signature, body in NEW_FUNCTIONS.items():
        op.execute(body)
        op.execute(f"revoke all on function vanimo_private.{signature} from public")
        op.execute(f"grant execute on function vanimo_private.{signature} to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only: restore from backup or rebuild the local database")
