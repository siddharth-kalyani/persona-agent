"""Row-level security building blocks shared by migrations.

Every table that holds a user's data uses `owner_scoped(table)`: the API role sees and
writes only rows whose `tenant_id` and `owner_user_id` match the transaction's
`app.tenant_id` / `app.user_id` settings. With no settings, it sees nothing (fail-closed).
FORCE ROW LEVEL SECURITY applies the policies to the table owner too; the owner gets
an explicit policy because only migrations and SECURITY DEFINER functions run as it.
"""

from __future__ import annotations

APP_ROLE = "vanimo_app"


def force_rls(table: str) -> list[str]:
    return [
        f"alter table {table} enable row level security",
        f"alter table {table} force row level security",
        f"create policy owner_all on {table} to current_user using (true) with check (true)",
    ]


def owner_scoped(table: str, *, user_column: str = "owner_user_id") -> list[str]:
    cond = f"tenant_id = vanimo.current_tenant_id() and {user_column} = vanimo.current_app_user_id()"
    return [
        *force_rls(table),
        f"create policy app_owner on {table} to {APP_ROLE} using ({cond}) with check ({cond})",
    ]


def tenant_scoped(table: str) -> list[str]:
    """Tenant-wide rows (for example admin client scoping rules): any user of the tenant may read;
    writes are further limited by GRANTs and by the API's admin role check."""
    cond = "tenant_id = vanimo.current_tenant_id()"
    return [
        *force_rls(table),
        f"create policy app_tenant on {table} to {APP_ROLE} using ({cond}) with check ({cond})",
    ]
