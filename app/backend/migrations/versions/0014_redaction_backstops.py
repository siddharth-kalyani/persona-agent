"""F11 redaction backstops: Comprehend (S5), Bedrock Guardrails (model input/output), Macie (S13).

* tenants.pipeline_paused_*: a Macie finding pauses the organisation's pipeline (§7.2 S13 "Findings ⇒
  pause tenant pipeline"): no new content is read, redacted or sent to a model until an admin has
  looked and resumed it. The reason is a code; the reference is the finding's ID.
* backstop_events: what the backstops caught, content-free — which service, at which stage, the
  entity types and counts, a finding ID, and for snapshot findings the flagged rows (table + row ID,
  never content) so an admin can remove exactly those items. Users write their own guardrail events
  (the model call that was blocked); admins read their tenant's. Macie findings are recorded once.
* l1_snapshots: each user's last L1 snapshot for Macie — when, how many items, a hash of its content
  (an unchanged snapshot isn't uploaded again, so Macie doesn't re-scan it), the S3 ETag, and the
  manifest (table + row ID per line) that turns a finding's line numbers into rows. Owner-scoped.
* Triggers: deleting or changing L1 text in any snapshot table counts a change on the owner's snapshot
  row; a snapshot exported before the latest change is due, so the next sweep rewrites it within minutes
  — whatever deleted it (purge, "forget a meeting", retention, a learning re-run, a future path). The
  export records the count it read *before* reading the data, so a change committed while it runs
  keeps the snapshot due.
* snapshot_due(): users whose snapshot is missing or stale and who have L1 data (or still have a
  snapshot to delete). IDs only, like claim_purge_jobs(). With a tenant, an admin transaction in that
  tenant forces its users regardless of age ("export now").
* record_backstop_finding(): the sweeper's cross-tenant write — the event once, its rows from the
  manifest of the snapshot it was found in (matched by ETag), and the pause.
* purge_flagged(): an admin deletes the rows a snapshot finding names (in their own tenant; they never
  see the content). resume_pipeline(): an admin clears their own tenant's pause.

Revision ID: 0014
Revises: 0013
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, force_rls, owner_scoped

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

CODE = r"check ({} ~ '^[a-z0-9_]{{1,40}}$')"
REF = r"check ({} ~ '^[A-Za-z0-9_.:/\-]{{0,160}}$')"

# Tables holding L1 text, with their text columns (vanimo.backstops.snapshots.SNAPSHOT_FIELDS).
L1_TABLES = {
    "l1_items": ("subject_enc", "text_enc", "context_enc"),
    "commitments": ("text_enc", "what_enc", "due_phrase_enc"),
    "episodes": ("title_enc",),
    "episode_segments": ("text_enc",),
    "memory_atoms": ("text_enc", "quote_enc", "due_phrase_enc"),
    "drafts": ("text_enc",),
    "style_cards": ("card_enc",),
    "style_rules": ("value_enc",),
}
# Rows an admin may remove after a finding. Drafts aren't: one may be placed in the user's Outlook
# Drafts folder, which only the user's own "delete what Vanimo learned" tidies.
PURGEABLE = tuple(t for t in L1_TABLES if t != "drafts")

STATEMENTS = [
    "alter table vanimo.tenants add column pipeline_paused_at timestamptz, "
    f"add column pipeline_pause_reason text {CODE.format('pipeline_pause_reason')}, "
    f"add column pipeline_paused_ref text {REF.format('pipeline_paused_ref')}",
    f"""
    create table vanimo.backstop_events (
        id bigint generated always as identity primary key,
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        user_id uuid references vanimo.users(id) on delete set null,
        source text not null check (source in ('comprehend', 'guardrail', 'macie')),
        stage text not null check (stage in ('redaction', 'model_input', 'model_output', 'snapshot')),
        outcome text not null check (outcome in ('blocked', 'finding', 'unavailable')),
        kinds jsonb not null default '{{}}' check (jsonb_typeof(kinds) = 'object' and length(kinds::text) <= 2000),
        severity text check (severity in ('low', 'medium', 'high')),
        detail text not null default '' {REF.format("detail")},
        locations jsonb not null default '[]' check (jsonb_typeof(locations) = 'array'
                                                     and jsonb_array_length(locations) <= 200),
        purged_at timestamptz,
        occurred_at timestamptz not null default now()
    )
    """,
    "create index backstop_events_tenant_time on vanimo.backstop_events (tenant_id, occurred_at desc)",
    "create unique index backstop_events_finding on vanimo.backstop_events (source, detail) "
    "where source = 'macie' and detail <> ''",
    *force_rls("vanimo.backstop_events"),
    # A user records only their own events; an admin transaction reads the tenant's.
    f"""create policy app_insert on vanimo.backstop_events for insert to {APP_ROLE}
        with check (tenant_id = vanimo.current_tenant_id() and user_id = vanimo.current_app_user_id())""",
    f"""create policy app_admin_read on vanimo.backstop_events for select to {APP_ROLE}
        using (tenant_id = vanimo.current_tenant_id() and current_setting('app.is_admin', true) = 'true')""",
    f"grant select, insert on vanimo.backstop_events to {APP_ROLE}",
    """
    create table vanimo.l1_snapshots (
        owner_user_id uuid primary key references vanimo.users(id) on delete cascade,
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        exported_at timestamptz not null default now(),
        items integer not null default 0,
        bytes integer not null default 0,
        stored boolean not null default false,
        content_hash text check (content_hash ~ '^[0-9a-f]{64}$'),
        etag text check (etag ~ '^[A-Za-z0-9\\-]{1,80}$'),
        manifest jsonb not null default '[]' check (jsonb_typeof(manifest) = 'array'),
        offline_findings integer,
        changes bigint not null default 0,
        exported_changes bigint not null default 0
    )
    """,
    *owner_scoped("vanimo.l1_snapshots"),
    f"grant select, insert, update, delete on vanimo.l1_snapshots to {APP_ROLE}",
    # Runs as whoever changed the data (the owner's own transaction, or a SECURITY DEFINER job), so
    # row-level security still limits it to that owner's snapshot row.
    """
    create function vanimo.mark_snapshot_stale() returns trigger language plpgsql
    set search_path = vanimo, pg_temp as $$
    begin
        update vanimo.l1_snapshots set changes = changes + 1 where owner_user_id = old.owner_user_id;
        return null;
    end
    $$
    """,
    f"grant execute on function vanimo.mark_snapshot_stale() to {APP_ROLE}",
]
for _table, _cols in L1_TABLES.items():
    STATEMENTS += [
        f"create trigger snapshot_stale_on_delete after delete on vanimo.{_table} "
        "for each row execute function vanimo.mark_snapshot_stale()",
        f"create trigger snapshot_stale_on_update after update of {', '.join(_cols)} on vanimo.{_table} "
        "for each row execute function vanimo.mark_snapshot_stale()",
    ]

FUNCTIONS = {
    "snapshot_due(integer, integer, uuid)": """
        create function vanimo_private.snapshot_due(p_hours integer, p_limit integer, p_tenant uuid)
        returns table (tenant_id uuid, user_id uuid) language plpgsql security definer
        set search_path = vanimo, pg_temp as $$
        begin
            if p_tenant is not null and (p_tenant is distinct from vanimo.current_tenant_id()
                    or coalesce(current_setting('app.is_admin', true), '') <> 'true') then
                raise exception 'admin transaction required' using errcode = '42501';
            end if;
            return query
            with data as (
                select x.tenant_id, x.owner_user_id from vanimo.l1_items x
                union select x.tenant_id, x.owner_user_id from vanimo.drafts x
                union select x.tenant_id, x.owner_user_id from vanimo.commitments x
                union select x.tenant_id, x.owner_user_id from vanimo.episodes x
                union select x.tenant_id, x.owner_user_id from vanimo.style_cards x
                union select x.tenant_id, x.owner_user_id from vanimo.style_rules x
                union select s.tenant_id, s.owner_user_id from vanimo.l1_snapshots s where s.stored
            )
            select d.tenant_id, d.owner_user_id from data d
              left join vanimo.l1_snapshots s on s.owner_user_id = d.owner_user_id
             where (p_tenant is null or d.tenant_id = p_tenant)
               and (p_tenant is not null or s.exported_at is null or s.changes > s.exported_changes
                    or s.exported_at < now() - make_interval(hours => greatest(1, p_hours)))
             order by (s.changes > s.exported_changes) desc nulls first, s.exported_at nulls first
             limit greatest(1, least(p_limit, 500));
        end
        $$
    """,
    "record_backstop_finding(uuid, uuid, text, text, jsonb, text, text, jsonb)": """
        create function vanimo_private.record_backstop_finding(
            p_tenant uuid, p_user uuid, p_source text, p_finding text, p_kinds jsonb, p_severity text,
            p_etag text, p_records jsonb)
        returns boolean language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare
            v_n integer;
            v_user uuid;
            v_locations jsonb := '[]';
        begin
            if p_source <> 'macie' or coalesce(p_finding, '') = '' or jsonb_typeof(p_kinds) <> 'object'
               or exists (select 1 from jsonb_each(p_kinds) k
                           where k.key !~ '^[A-Za-z0-9_:. \\-]{1,60}$' or jsonb_typeof(k.value) <> 'number') then
                raise exception 'invalid finding' using errcode = '22023';
            end if;
            if not exists (select 1 from vanimo.tenants t where t.id = p_tenant) then
                return false;  -- the tenant has gone since the snapshot was written
            end if;
            select u.id into v_user from vanimo.users u where u.id = p_user and u.tenant_id = p_tenant;
            -- The finding's line numbers → rows, from the manifest of the snapshot it was found in.
            if v_user is not null and p_etag is not null and jsonb_typeof(p_records) = 'array' then
                select coalesce(jsonb_agg(distinct m.loc), '[]') into v_locations
                  from vanimo.l1_snapshots s,
                       lateral (select jsonb_build_object('t', s.manifest -> (r.value::int) ->> 0,
                                                          'id', s.manifest -> (r.value::int) ->> 1) as loc
                                  from jsonb_array_elements_text(p_records) r
                                 where r.value ~ '^[0-9]{1,7}$'
                                   and (r.value::int) < jsonb_array_length(s.manifest)
                                 limit 200) m
                 where s.owner_user_id = v_user and s.etag = p_etag;
            end if;
            insert into vanimo.backstop_events (tenant_id, user_id, source, stage, outcome, kinds, severity, detail,
                                                locations)
            values (p_tenant, v_user, 'macie', 'snapshot', 'finding', p_kinds, p_severity, p_finding, v_locations)
            on conflict (source, detail) where source = 'macie' and detail <> '' do nothing;
            get diagnostics v_n = row_count;
            if v_n > 0 then
                update vanimo.tenants set pipeline_paused_at = now(), pipeline_pause_reason = 'macie_finding',
                       pipeline_paused_ref = left(p_finding, 160)
                 where id = p_tenant and pipeline_paused_at is null;
            end if;
            return v_n > 0;
        end
        $$
    """,
    "purge_flagged(bigint)": f"""
        create function vanimo_private.purge_flagged(p_event bigint)
        returns integer language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare
            v_tenant uuid := vanimo.current_tenant_id();
            v_event vanimo.backstop_events;
            v_loc jsonb;
            v_n integer := 0;
            v_d integer;
        begin
            if v_tenant is null or coalesce(current_setting('app.is_admin', true), '') <> 'true' then
                raise exception 'admin transaction required' using errcode = '42501';
            end if;
            select * into v_event from vanimo.backstop_events e
             where e.id = p_event and e.tenant_id = v_tenant and e.source = 'macie' for update;
            if not found then
                return -1;
            end if;
            for v_loc in select * from jsonb_array_elements(v_event.locations) loop
                if (v_loc ->> 't') = any (array{list(PURGEABLE)}::text[])
                   and (v_loc ->> 'id') ~ '^[0-9a-f\\-]{{36}}$' then
                    execute format('delete from vanimo.%I where id = $1 and tenant_id = $2', v_loc ->> 't')
                      using (v_loc ->> 'id')::uuid, v_tenant;
                    get diagnostics v_d = row_count;
                    v_n := v_n + v_d;
                end if;
            end loop;
            update vanimo.backstop_events set purged_at = now() where id = p_event;
            return v_n;
        end
        $$
    """,
    "resume_pipeline()": """
        create function vanimo_private.resume_pipeline()
        returns boolean language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare
            v_tenant uuid := vanimo.current_tenant_id();
            v_n integer;
        begin
            if v_tenant is null or coalesce(current_setting('app.is_admin', true), '') <> 'true' then
                raise exception 'admin transaction required' using errcode = '42501';
            end if;
            update vanimo.tenants set pipeline_paused_at = null, pipeline_pause_reason = null, pipeline_paused_ref = null
             where id = v_tenant and pipeline_paused_at is not null;
            get diagnostics v_n = row_count;
            return v_n > 0;
        end
        $$
    """,
}


def upgrade() -> None:
    for stmt in STATEMENTS:
        op.execute(stmt)
    for name, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"revoke all on function vanimo_private.{name} from public")
        op.execute(f"grant execute on function vanimo_private.{name} to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only")
