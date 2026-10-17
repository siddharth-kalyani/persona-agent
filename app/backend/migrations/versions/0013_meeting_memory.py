"""M6 meeting memory.

* episodes: one per meeting occurrence Vanimo read a Teams transcript of (calendar-first
  segmentation, R05 §5.2). The title is L1 (vault-encrypted); lineage as for learned items (the
  occurrence, its series, every invitee but the user with their domains), so exclusions, never-send
  words and "delete what Vanimo learned" reach it (§6.5 X7). `roster` holds the invitees' person
  tokens and sides (for speaker corrections and "the client"); the names stay in l1_tokens.
  Governance fields of R05 §5.1: capture source, consent state, retention class, audio retained
  (always false: Vanimo never receives audio from Teams).
* episode_segments: the transcript as L1 speaker turns, kept 30 days (§8.4 "Transcripts (L1)"),
  for citations. Raw transcripts are never stored (Mode A).
* memory_atoms: typed, bi-temporal memory (R05 §5.3): what kind, said by whom (a person token or
  the user), when it was said (valid time) and stored (record time), the evidence span (segment
  ordinals and offsets), due date for action items and promises, confidence and trust. Keyed by an
  HMAC of the occurrence, kind and sentence, so finding it again never duplicates it. Kept 12 months.
* meeting_ingests: what became of each occurrence (stored, no transcript yet, unavailable, deleted
  by the user...), so a meeting is read once and a deleted one is never read again. Content-free.
* commitments.channel gains 'meeting': the user's own promises made in meetings.
* tenant_policies.meeting_memory: the organisation's switch (on by default; nothing is read until
  the Teams admin allows Graph access to transcripts).
* expire_meeting_memory(): the sweeper's cross-tenant retention job (segments after 30 days, atoms
  after 12 months, empty episodes). meeting_ingest_health(): content-free counts for the admin's
  health check. enqueue_tenant_purge() also queues users who have meeting memory.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

from vanimo.db.rls import APP_ROLE, owner_scoped

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

OWNER = (
    "tenant_id uuid not null references vanimo.tenants(id) on delete cascade, "
    "owner_user_id uuid not null references vanimo.users(id) on delete cascade"
)
HASH = r"check ({} ~ '^[0-9a-f]{{64}}$')"
TOKEN = r"check ({} ~ '^⟦(ME|PERSON_[0-9a-f]{{8}})(\.full|\.last)?⟧$')"  # noqa: S105 - a regex, not a secret
SIDE = "check ({} in ('me', 'internal', 'external', 'unknown'))"
KINDS = "('decision', 'action_item', 'commitment', 'requirement', 'open_question', 'risk', 'idea')"

TABLES = {
    "episodes": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        source_kind text not null check (source_kind in ('graph', 'sample')),
        meeting_hash text not null {HASH.format("meeting_hash")},
        series_hash text {HASH.format("series_hash")},
        title_enc text not null,
        starts_at timestamptz not null,
        ends_at timestamptz not null,
        transcript_at timestamptz not null,
        people jsonb not null default '[]',
        roster jsonb not null default '[]',
        external boolean not null default false,
        organizer_is_me boolean not null default false,
        attribution text not null check (attribution in ('named', 'unattributed')),
        capture_source text not null default 'teams_transcript' check (capture_source in ('teams_transcript')),
        consent_state text not null default 'teams_banner' check (consent_state in ('teams_banner')),
        retention_class text not null default 'standard' check (retention_class in ('standard')),
        audio_retained boolean not null default false check (not audio_retained),
        extractor text not null check (extractor in ('offline', 'bedrock')),
        segments_until timestamptz not null,
        counts jsonb not null default '{{}}',
        created_at timestamptz not null default now(),
        unique (owner_user_id, meeting_hash)
    """,
    "episode_segments": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        episode_id uuid not null references vanimo.episodes(id) on delete cascade,
        ordinal integer not null check (ordinal between 0 and 10000),
        starts_ms integer not null,
        ends_ms integer not null,
        speaker text {TOKEN.format("speaker")},
        speaker_side text not null {SIDE.format("speaker_side")},
        text_enc text not null,
        expires_at timestamptz not null,
        unique (episode_id, ordinal)
    """,
    "memory_atoms": f"""
        id uuid primary key default gen_random_uuid(), {OWNER},
        episode_id uuid not null references vanimo.episodes(id) on delete cascade,
        kind text not null check (kind in {KINDS}),
        atom_hash text not null {HASH.format("atom_hash")},
        text_enc text not null,
        quote_enc text not null,
        speaker text {TOKEN.format("speaker")},
        speaker_side text not null {SIDE.format("speaker_side")},
        owner text {TOKEN.format("owner")},
        said_at timestamptz not null,
        recorded_at timestamptz not null default now(),
        seg_from integer not null,
        seg_to integer not null,
        starts_ms integer not null,
        ends_ms integer not null,
        due_at timestamptz,
        due_phrase_enc text,
        confidence real not null check (confidence between 0 and 1),
        trust text not null check (trust in ('high', 'medium', 'low')),
        extractor text not null check (extractor in ('offline', 'bedrock')),
        status text not null default 'active' check (status in ('active', 'dismissed')),
        status_at timestamptz,
        expires_at timestamptz not null,
        unique (owner_user_id, atom_hash)
    """,
    "meeting_ingests": f"""
        owner_user_id uuid not null references vanimo.users(id) on delete cascade,
        tenant_id uuid not null references vanimo.tenants(id) on delete cascade,
        source_kind text not null check (source_kind in ('graph', 'sample')),
        meeting_hash text not null {HASH.format("meeting_hash")},
        state text not null check (state in ('stored', 'no_transcript', 'unavailable', 'failed', 'deleted', 'empty')),
        detail text not null default '' check (detail ~ '^[a-z0-9_]{{0,40}}$'),
        attempts integer not null default 1,
        ends_at timestamptz not null,
        checked_at timestamptz not null default now(),
        primary key (owner_user_id, source_kind, meeting_hash)
    """,
}

ALTERS = [
    "alter table vanimo.commitments drop constraint commitments_channel_check, add constraint commitments_channel_check "
    "check (channel in ('email', 'chat', 'meeting'))",
    "alter table vanimo.tenant_policies add column meeting_memory boolean not null default true",
    "create index episodes_when on vanimo.episodes (owner_user_id, starts_at desc)",
    "create index atoms_episode on vanimo.memory_atoms (episode_id)",
    "create index atoms_expiry on vanimo.memory_atoms (expires_at)",
    "create index segments_expiry on vanimo.episode_segments (expires_at)",
]

FUNCTIONS = {
    # Retention (§8.4), across tenants: SECURITY DEFINER, returns counts only. A segment past its 30
    # days and an atom past its 12 months go; an episode with neither left goes too (its ingest
    # record stays, so the meeting isn't read again).
    "expire_meeting_memory()": """
        create function vanimo_private.expire_meeting_memory()
        returns table (segments bigint, atoms bigint, episodes bigint) language plpgsql security definer
        set search_path = vanimo, pg_temp as $$
        declare s bigint; a bigint; e bigint;
        begin
            delete from vanimo.episode_segments where expires_at < now();
            get diagnostics s = row_count;
            delete from vanimo.memory_atoms where expires_at < now();
            get diagnostics a = row_count;
            delete from vanimo.episodes ep
             where ep.segments_until < now()
               and not exists (select 1 from vanimo.memory_atoms m where m.episode_id = ep.id)
               and not exists (select 1 from vanimo.episode_segments g where g.episode_id = ep.id);
            get diagnostics e = row_count;
            delete from vanimo.meeting_ingests where checked_at < now() - interval '120 days'
               and state <> 'deleted';
            return query select s, a, e;
        end
        $$
    """,
    # The admin's transcript health check: what reading transcripts ran into across the tenant's
    # users in the last p_days (state and content-free detail codes, counted). Admin transactions only.
    "meeting_ingest_health(integer)": """
        create function vanimo_private.meeting_ingest_health(p_days integer)
        returns table (state text, detail text, n bigint, users bigint, last_at timestamptz)
        language plpgsql security definer set search_path = vanimo, pg_temp as $$
        declare
            v_tenant uuid := vanimo.current_tenant_id();
        begin
            if v_tenant is null or coalesce(current_setting('app.is_admin', true), '') <> 'true' then
                raise exception 'admin transaction required' using errcode = '42501';
            end if;
            return query
            select i.state, i.detail, count(*), count(distinct i.owner_user_id), max(i.checked_at)
              from vanimo.meeting_ingests i
             where i.tenant_id = v_tenant and i.checked_at > now() - make_interval(days => greatest(1, least(p_days, 90)))
             group by i.state, i.detail;
        end
        $$
    """,
    "enqueue_tenant_purge()": """
        create or replace function vanimo_private.enqueue_tenant_purge()
        returns table (job_id uuid, user_id uuid) language plpgsql security definer
        set search_path = vanimo, pg_temp as $$
        declare
            v_tenant uuid := vanimo.current_tenant_id();
        begin
            if v_tenant is null or coalesce(current_setting('app.is_admin', true), '') <> 'true' then
                raise exception 'admin transaction required' using errcode = '42501';
            end if;
            insert into vanimo.controls_state (owner_user_id, tenant_id, version)
                 select id, tenant_id, 1 from vanimo.users where tenant_id = v_tenant
            on conflict (owner_user_id) do update
                 set version = vanimo.controls_state.version + 1, updated_at = now();
            return query
            insert into vanimo.purge_jobs (tenant_id, owner_user_id, reason)
                 select distinct o.tenant_id, o.owner_user_id, 'tenant_policy_changed' from (
                     select i.tenant_id, i.owner_user_id from vanimo.l1_items i where i.tenant_id = v_tenant
                     union
                     select d.tenant_id, d.owner_user_id from vanimo.drafts d where d.tenant_id = v_tenant
                     union
                     select c.tenant_id, c.owner_user_id from vanimo.commitments c where c.tenant_id = v_tenant
                     union
                     select e.tenant_id, e.owner_user_id from vanimo.episodes e where e.tenant_id = v_tenant
                 ) o
            returning id, owner_user_id;
        end
        $$
    """,
}


def upgrade() -> None:
    for name, cols in TABLES.items():
        op.execute(f"create table vanimo.{name} ({cols})")
        for stmt in owner_scoped(f"vanimo.{name}"):
            op.execute(stmt)
        op.execute(f"grant select, insert, update, delete on vanimo.{name} to {APP_ROLE}")
    for stmt in ALTERS:
        op.execute(stmt)
    for name, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"revoke all on function vanimo_private.{name} from public")
        op.execute(f"grant execute on function vanimo_private.{name} to {APP_ROLE}")


def downgrade() -> None:
    raise NotImplementedError("forward-only")
