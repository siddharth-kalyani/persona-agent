# Vanimo: application code

The build plan is `docs/03-mvp-plan-and-roadmap.md` §0 (solo track M0–M6). This folder holds the code (D11):

| Folder | What | Stack |
|---|---|---|
| `backend/` | API, Graph access, model router, migrations, eval harness, canaries | Python 3.14, FastAPI, SQLAlchemy + psycopg, Alembic, MSAL, Anthropic SDK (Bedrock) |
| `frontend/` | Web control center + Outlook add-in task pane | React 19, Vite, TypeScript, Fluent UI 9, MSAL |
| `infra/` | One regional cell on AWS | AWS CDK (Python): VPC, Aurora PostgreSQL 18 (Serverless v2), ECS Fargate, internal ALB, CloudFront, S3, KMS, Secrets Manager |
| `infra/entra/` | How to register the Entra app | — |
| `surfaces/outlook-addin/` | Outlook add-in manifest (XML); the task pane itself is in `frontend/src/addin/` | — |
| `docker-compose.yml` | Local Postgres 18 (port 5433) | Docker |

## Sample data: works without Microsoft 365

Entra and Graph access may come late, so every feature also runs on a **sample workspace**: Kestrel Analytics, a fictional IT-services firm (`backend/vanimo/sources/sample.py`). It includes:
- clients Acme Retail, Bluefin Bank and Orion Health;
- a 62-person group chat, a hidden chat and an unnamed chat;
- forwards, Hinglish subjects, personal email, a private event and recurring meetings.

**Who sees it:**
- Password sign-ins always use the sample workspace.
- Microsoft sign-ins use their real data (Graph), unless `VANIMO_SAMPLE_DATA=always`.
- Both go through the same interface (`vanimo/sources/base.py`), so screens don't change when real data arrives.

**Local sign-in (local/dev only):**
- `VANIMO_ENABLE_PASSWORD_AUTH=true`.
- Accounts are made with `uv run python -m vanimo.ops.local_user --email … --role user|admin|superadmin`, which prints a one-time password the person must replace at first sign-in. `--reset` issues a new one.
- Production refuses this setting.

## M1: Choose what Vanimo learns from

**What it does** (architecture §6.5):
- **Header pass.** Lists people, domains, threads, chats and meetings from headers only.
- **Review screen.** Shows the impact before you confirm: "7 emails in 5 threads, 4 chats, 1 meeting".
- **Person exclusions.** Cover every chat the person is in; you can untick big group chats (D5).
- **Never-send words.** Matched by a deterministic matcher, never by an AI model:
  - it catches case, full-width and zero-width tricks, Cyrillic look-alikes, separators, plurals, Hinglish spellings, honorifics, and spellings you type yourself (e.g. Devanagari);
  - words are replaced before storage and shown as `[removed]`.
- **Finish/Skip gate.** No message content is read before you choose.
- **My data controls.** Change anything later; every change gets a receipt.
- **Admin client scoping (D9).** Exclude client accounts by domain, or allow approved clients only. Users see these rules as locked.

**How it's built:**

| Piece | Where |
|---|---|
| One exclusion engine for user and organisation rules | `vanimo/controls/engine.py` |
| Matcher | `vanimo/controls/neversend.py` |
| Header pass | `vanimo/controls/scan.py` |
| Field encryption + rule-key HMACs | `vanimo/vault.py` |
| Purge and scrub jobs | `vanimo/controls/jobs.py` |
| APIs | `vanimo/api/controls.py`, `vanimo/api/admin_scoping.py` |

**At rest:**
- Names, addresses, subjects and chat names are encrypted per user.
- Rules store only keyed hashes of identifiers.
- Never-send words are encrypted per user and never logged.
- Organisation rules can only be written in a transaction the API marked as admin, after its role check. The database refuses them in any other transaction.
  - This is a backstop against bugs, not a second security boundary: code that can run arbitrary SQL as the API role could set the flag itself.
  - All queries are parameterised.

### Carried into M2 (from the M1 reviews), done in M2

- Every content read calls `require_review_done(engine, ref, source.kind)` (the learning backfill does).
- The fetch path builds the engine with `load_engine(..., self_email=...)` (`vanimo/learning/backfill.py`).
- Every derived store (L1 text, vectors, tokens, style cards) has its purge in `vanimo/controls/jobs.py`.

## M2: Learn safely

Works the same on the sample workspace and on Microsoft 365. Tabs: **Sample workspace**, **Learning**, **Persona**.

1. **Sample workspace** (sample only): Inbox, Sent, Chats and Meetings as Outlook and Teams would show them.
   Each item shows what Vanimo did with it (learned, excluded and why, not learned yet, received). For a
   learned item, **See what Vanimo stored** shows the stored text next to your view of it.
2. **Learning:** *Start learning* runs the backfill (`vanimo/learning/backfill.py`):
   - Gate first: nothing is read until the review is done for this source.
   - Only your own sent emails and chat messages from allowed sources are read; the engine decides from metadata
     before any text is fetched. The message you replied to is kept as context only if its sender is allowed too.
   - Redaction L0 → L1 in memory (`vanimo/redaction/`): hidden HTML and Unicode tag characters dropped,
     never-send words → `⟦NS_…⟧`, Tier R (Aadhaar/VID, PAN, GSTIN, IFSC + account, UPI, voter ID, passport,
     cards, SSN/ITIN, EIN, ABA, secrets and passwords) → `[slot]` (checksum-validated, irreversible), people
     from the header/directory gazetteer → `⟦PERSON_…⟧`, emails and phones → tokens, your own name → `⟦ME⟧`.
     A verify pass blocks any item with residue (fail-closed).
   - Labels: relationship (manager/report/peer/external/personal), intent, channel, language (English,
     Hinglish, Hindi). Stored vault-encrypted with HMAC lineage. A rule or word added mid-run restarts it.
   - *Delete what Vanimo learned* deletes everything learned and leaves a receipt.
3. **Persona:** the Persona Snapshot (style cards: greetings, sign-offs, length, formality, phrases,
   Indian-English keep-list, per audience, with back-off) and the basic studio (formality, length, warmth,
   emoji, polish, phrases to use or avoid). Also shows the offline evaluation baseline.

Two-phase fetch: thread headers are read first; text is fetched only for allowed messages and the one each replied to (and only if everyone on that message is allowed). Meeting chats are tied to their meeting by the join link, so a meeting or series rule covers them; a chat whose roster can't be read in full is never read.

Purges: adding an exclusion deletes learned items whose lineage it now excludes. Adding a never-send word
re-masks stored text, tokens and studio phrases. An admin client-scoping change queues a purge for every user
in the tenant, which the sweeper runs. Style cards are rebuilt after each purge.

## M3: Draft in Outlook

Works the same on the sample workspace and on Microsoft 365. New: the **Draft** tab in the web app and the drafting
task pane in Outlook (`frontend/src/addin/`). Both use one drafting service (`backend/vanimo/drafting/`). **Vanimo
never sends:** you insert, copy or open a reply, read it, and send it yourself.

**What it does:**
- **Reply or new email in your voice.** In Outlook the task pane reads the open email's conversation and recipients;
  on the web you pick a conversation from your inbox or start a new email. An instruction is optional for a reply
  ("tell her I'll send the plan by Wednesday") and required for a new email.
- **Audience chip.** "Writing to: your manager / a colleague / someone outside your organisation", from the same
  rules the learner uses (directory manager and reports, your organisation's domains).
- **Insert at the cursor** in a compose window (never replacing the quoted thread). From a message you're reading:
  **Reply with this** opens Outlook's reply form with the draft in it.
- **Pre-send checks** on every draft, and on your own text with **Check before sending** / **Check my edits**:

  | Check | Severity |
  |---|---|
  | Dates, times, amounts and promises not in the email or your instruction (generated drafts only) | warn |
  | Look-alike domain in a recipient or the sender (`c1oudnest.example` vs `cloudnest.example`) | **block** |
  | Payment-detail change or urgent payment request (BEC) | **block** |
  | First email to a domain, a personal address, an outsider added to an internal thread | warn |
  | Greeting names someone not on To; a client account named in an email to a different client | warn |
  | Regulated IDs or secrets in your text; never-send words in your text | warn |
  | Fill-ins left for you (`[date]`, `[PAN]`), links or made-up contacts removed, hidden text in the email | info |

  A **block** turns insert (and copy) off until you tick "I've checked this another way".
- **Model router.** Claude Haiku 5.5 by default; Sonnet 5.5 for a new email to a client or your manager, a long reply,
  or when you ask for higher quality, within a daily quota (`VANIMO_PREMIUM_DRAFTS_PER_DAY`, default 20). Rate limit
  per user: `VANIMO_DRAFTS_PER_MINUTE` / `VANIMO_DRAFTS_PER_DAY`.
- **Offline stand-in** (`VANIMO_DRAFTER=offline`, the local default) until the AWS account exists. No model: it turns
  your instruction into first-person sentences in your register (for example "Kindly …" if you write that way to
  clients), adds your greeting and sign-off, or writes a short acknowledgement with a fill-in when there is no
  instruction. It is labelled everywhere it appears. A deployed cell always uses Bedrock, and prod refuses `offline`.

**How a draft is made** (`vanimo/drafting/service.py`, architecture §7.2 S12):
1. Rate limit, then the onboarding gate (no review, no draft).
2. Thread **headers** only → the exclusion engine decides on the whole conversation: its thread rule, everyone in it,
   everyone you're writing to. Excluded by you: refused, or a **one-off draft** made in memory and never stored.
   Excluded by your organisation: always refused.
3. Only then the last 4 messages' own words are fetched and redacted to L1 in memory, with your instruction and the
   subject (never-send words → placeholders, Tier R → slots, people → tokens, verify, fail-closed).
4. Persona pack: the style card for this audience (greeting, sign-off and length from your *emails*, since chats have
   none), your studio settings, and up to 3 of your past messages. Every one is re-checked against the live rules
   (a rule added a moment ago wins before the purge job runs). Same thread or same people: verbatim; anything else:
   only its shape, so facts never move between audiences.
5. The prompt (`vanimo/drafting/prompt.py`): rules → persona (marked for prompt caching) → audience → examples →
   the thread as untrusted, spotlighted data → your instruction. The model writes only the body.
6. Output gate (`vanimo/drafting/gate.py`): plain text; the model's own greeting and sign-off dropped; tokens not in
   this prompt never revealed; links not in the email or instruction removed; a Tier R value blocks the draft; made-up
   addresses and phones become fill-ins; never-send words masked.
7. Your greeting + body + sign-off, re-hydrated for your screen: names back, never-send words as `[removed]` (or the
   word itself if you allowed it in drafts).
8. Pre-send checks (`vanimo/drafting/checks.py`), then the draft is stored as L1 (encrypted, with lineage) for the M4
   edit loop. Logs carry codes, counts, model and timings only.

**Purges reach drafts too:** a new exclusion deletes drafts whose lineage it covers, a new never-send word re-masks
them, "Delete what Vanimo learned" deletes them, and an organisation scoping change queues users with drafts.

### Try the Outlook add-in locally

Outlook loads add-in pages over HTTPS only, and needs a manifest. With the Docker stack (or Option B) running:

1. Create and trust a localhost certificate. One way (needs Node): `npx office-addin-dev-certs install`. It writes
   `localhost.crt` and `localhost.key` to `%USERPROFILE%\.office-addin-dev-certs`.
2. Start Vite with it (Option B frontend): set `VANIMO_DEV_HTTPS_CERT` and `VANIMO_DEV_HTTPS_KEY` to those two files,
   then `npm run dev`. The app is now on `https://localhost:5173`.
3. Render a manifest for that host: `py app/surfaces/outlook-addin/render_manifest.py https://localhost:5173 > manifest.xml`.
4. In Outlook on the web: **Get Add-ins → My add-ins → Add a custom add-in → Add from file** → `manifest.xml`.
   Your organisation may need to allow custom add-ins.
5. Open an email (or a reply) and press **Vanimo**. Until the Entra app exists the pane offers local password sign-in;
   a password account uses the **sample workspace**, so pick a sample conversation to reply to. The draft is inserted
   into the real compose window.

## Guarantees built in from M0

- **Tenant and user isolation in the database.**
  - The API connects as `vanimo_app`, which is not the owner and can't bypass row-level security.
  - Every request runs in a transaction pinned to one tenant and one user, so rows of other users are invisible.
  - A request with no identity sees nothing.
  - Tests: `tests/test_rls.py`.
- **Content-free logs.**
  - Allow-listed keys and identifier-like values only.
  - Library log messages are dropped.
  - The access log records the route template, not the path.
  - Tests: `tests/test_logging.py` and the canary check in `tests/test_api.py`.
- **Metadata-only Graph reads before the review step.**
  - `vanimo/graph/metadata.py` refuses body fields.
  - Tests pin the `$select` lists.
- **Single-tenant Entra.**
  - The API only accepts v2 tokens for this tenant that carry the `access_as_user` scope and a Vanimo app role.
  - Graph calls are made as the user (On-Behalf-Of).
- **Models only from the cell's allow-list** (Claude on Bedrock: Haiku 5.5 by default, Sonnet 5.5 for premium drafts).
- **Canaries and evals from day one** (`vanimo/canary.py`, `vanimo/evals/`).

## Local development (Windows, PowerShell or Git Bash)

### Option A: everything in Docker (one command)

Prerequisite: Docker Desktop. Run from the repo root:

```bash
docker compose -f app/docker-compose.yml --profile app up -d --build
# http://127.0.0.1:5173 (web)  ·  http://127.0.0.1:8000/api/docs (API)
```

- **What starts:** `postgres` → `migrate` (creates roles and schema, runs `alembic upgrade head`, then exits) → `api` → `web`.
- **Live reload:** both API and web reload on save. The source folders are mounted into the containers, and the containers poll for changes because Windows mounts send no file events.
- **Settings:** compose sets the local database, `VANIMO_ENV=local` and password sign-in. Anything else (e.g. Entra IDs) still comes from `backend/.env` if you have one.
- **First account:** `docker compose -f app/docker-compose.yml run --rm migrate python -m vanimo.ops.local_user --email you@example.com --role superadmin`
- **Logs / stop:** `docker compose -f app/docker-compose.yml logs -f api` · `docker compose -f app/docker-compose.yml --profile app down` (the database volume is kept).
- **After a dependency change** (`pyproject.toml`, `uv.lock`, `package*.json`): `docker compose -f app/docker-compose.yml --profile app up -d --build -V`.
- **Don't mix with Option B on the same ports:** stop one before starting the other (8000 and 5173).
- These dev images (`Dockerfile.dev`) are never deployed; AWS builds `backend/Dockerfile` (see below).

### Option B: run the API and web app directly

Faster for debugging and running single tests. Prerequisites: Docker Desktop, Python 3.14, uv, Node 24.

```bash
# 1. Database (Postgres 18 in Docker, port 5433)
docker compose -f app/docker-compose.yml up -d

# 2. Backend: install, create roles + schema
cd app/backend
uv sync
#    If uv can't create .venv on this machine, run `py -m venv .venv` first.
export VANIMO_DB_ADMIN_URL=postgresql://postgres:postgres_local@127.0.0.1:5433/postgres
export VANIMO_DB_OWNER_PASSWORD=vanimo_owner_local VANIMO_DB_APP_PASSWORD=vanimo_app_local
uv run python -m vanimo.ops.bootstrap_db
VANIMO_DB_OWNER_URL=postgresql+psycopg://vanimo_owner:vanimo_owner_local@127.0.0.1:5433/vanimo uv run alembic upgrade head

# 3. Backend settings: copy .env.example to .env and fill in the Entra IDs + secret (infra/entra/README.md)
uv run python -m vanimo.dev          # http://127.0.0.1:8000 (API docs at /api/docs)

# 4. Frontend: copy .env.example to .env.local and fill in tenant + client IDs
cd ../frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api to the backend)
```

Bedrock calls from your laptop need AWS credentials and `AWS_REGION=ap-south-1`. Everything else works without AWS.

## Tests

```bash
cd app/backend  && uv run pytest -q && uv run ruff check .   # needs the Postgres container
cd app/frontend && npm run typecheck && npm test && npm run build
cd app/infra    && uv run pytest -q                           # synthesises the stacks; no AWS needed
cd app/backend  && uv run python -m vanimo.evals --dataset evals/datasets/synthetic_v0.jsonl --drafter reference
```

CI runs the same steps (`.github/workflows/ci.yml`) against Postgres 18 and 17.

## Deploy the India cell (once AWS access is in place)

1. **AWS credentials.**
   - `aws configure sso` (or keys) for the target account.
   - In the Bedrock console (ap-south-1), check that **Claude Haiku 5.5** and **Claude Sonnet 5.5** are enabled.
2. **Bootstrap CDK once:** `cdk bootstrap aws://<account>/ap-south-1`.
3. **Build the frontend:** `cd app/frontend && npm run build`.
4. **Deploy:**

   ```
   cd app/infra
   cdk deploy --all -c cell=in -c entra_tenant_id=<tid> -c entra_client_id=<client-id>
   ```

5. **Set the Entra client secret** in Secrets Manager (`infra/entra/README.md` step 7). Then run `aws ecs update-service --force-new-deployment` on the API service.
6. **Create roles and run migrations.** Use the outputs `ClusterName`, `MigrateTaskDef`, `TaskSubnets` and `TaskSecurityGroup`:

   ```
   aws ecs run-task --region ap-south-1 --launch-type FARGATE --cluster <ClusterName> --task-definition <MigrateTaskDef> \
     --network-configuration "awsvpcConfiguration={subnets=[<subnet1>,<subnet2>],securityGroups=[<sg>],assignPublicIp=DISABLED}"
   ```

   Re-run it after every deploy that adds a migration.
7. **Register the URLs with Entra:**
   - add the `RedirectUri` output (`https://<cloudfront-domain>/redirect.html`) as a SPA redirect URI;
   - add `brk-multihub://<cloudfront-domain>` for the add-in.

## Known deviations from the target architecture (M0)

These are deliberate for 2–3 internal users and are listed again in the pre-external-customer checklist (`docs/03` §0, "Deferred"):

| Area | Target (`docs/02`) | M0 | Before external customers |
|---|---|---|---|
| API runtime | API Gateway + Lambda BFF, separate drafting service (§4.2) | One FastAPI service on ECS Fargate behind an internal ALB, reached only through CloudFront (VPC origin). ~~Revisit in M3~~ (M3): drafting runs inside this service; it is already warm | Split drafting into its own service when load or latency needs it (measure p95 in the pilot) |
| Egress | No internet egress from the data plane; Graph/Bedrock allow-list (Network Firewall / DNS Firewall) (§4.2) | API tasks reach the internet through one NAT gateway | Add the egress allow-list and WAF |
| Bedrock IAM | Scoped to allowed models | `bedrock-mantle:CreateInference` on `*`, limited to the cell region. The model allow-list is enforced in code | Scope to model ARNs once the ARN format is published |
| Keys | Per-tenant CMKs, per-user data keys (§8.2) | One cell CMK | Per-tenant keys arrive with external tenants |
| Entra | Read app + Compose app; certificate in KMS, no client secret (§5.1–5.2) | One app with a client secret in Secrets Manager (D8) | Split the apps; switch to a certificate |
| Add-in CSP | Enforced | Report-only until the add-in spike confirms Outlook's hosts. Still report-only after M3: the spike needs the Entra app and a deployed cell, which don't exist yet | Enforce right after the add-in spike |
| Stores | S3 Vectors, DynamoDB, Valkey | Aurora only | Added when M2/M4 need them |
| Vault | Separate vault account; KMS per-tenant CMK with per-user data keys, so deleting a user's key crypto-shreds their data (§7.2 S8, §8.2) | AES-256-GCM keys derived (HKDF) from one master key in Secrets Manager | Move to KMS data keys before external customers |
| Purge | Step Functions job across all stores (§6.5 X7) | In-process job. ~~M1 has no derived content yet~~ (superseded in M2): purges the L1 items, tokens, vectors and style cards by lineage, re-masks the Sources index, L1 text and studio phrases, and writes receipts | Move to Step Functions with the queue |
| Redaction (M2 vs §7.2) | NER ensemble (Presidio/spaCy, GLiNER, IndicNER), contextual Tier C/S classifier, Guardrails, Macie backstops, vault service in a separate account | Deterministic detectors + checksum validators + the M365 header/directory gazetteer. Names that never appear in a header or the directory stay in L1. No Tier C/S classification (client sensitive words are stored but not yet applied). Token map in Aurora, vault-encrypted | Add NER + the contextual classifier (needs AWS, D7) before external customers |
| Embeddings and drafting (M2) | Bedrock embeddings + S3 Vectors; Claude Haiku 5.5 drafter | Local hashing-trick vectors (`vanimo/learning/embed.py`) in Aurora; an offline drafter (`vanimo/llm/offline.py`), clearly labelled, used only for the evaluation baseline. (M3: live drafting uses Claude through `vanimo/drafting/generate.py` when `VANIMO_DRAFTER=bedrock`, always in a deployed cell; locally a separate offline stand-in) | Swap in Bedrock embeddings behind the same functions once the AWS account exists |
| Drafting (M3 vs §9.1–9.2, §9.4) | One streaming call, p95 first token ≤ 2.5 s; persona prefix padded to ≥ 4,096 tokens for caching; post-generation leakage judge; LLM revise on failed style checks | The output gate needs the whole text before anyone sees it, so the draft is returned whole: measure p95 *total* time instead. The persona block is marked for caching but not padded. No leakage judge yet (needs a model): cross-audience leakage is limited by sending other audiences' messages only as shapes. Revise runs once, only on failed checks. Pre-send checks are rules, not a model | Measure latency and caching on Bedrock in ap-south-1; add the leakage judge to the release gate before external customers |
| Language (D6 vs M2) | English-only drafting in the MVP; Hindi/Hinglish wait for their own quality gate | M2 *labels* each message English, Hinglish or Hindi and keeps their style slices apart, so Hinglish chats don't skew the English cards. Nothing is drafted in Hinglish | Unchanged: Hinglish drafting needs its own quality gate (v1.5) |
| Never-send matching (M1 review) | Research 12: invisible characters removed | Zero-width spaces are still removed, not treated as spaces, so splitting a word with them ("Fal​con") can't dodge the filter. The cost: two words glued by a zero-width space ("the​falcon") don't match a *word* (they do match a codename) | Revisit with ICU word segmentation |
| Data controls (M1 vs §6.5 / research 12) | One table of rules for admins and users; rule states active → purging → purged / held; admins can also exclude specific chats; Aho–Corasick + ICU word segmentation; internal people merged by Entra object ID; review reminders at 24 h and 48 h | Organisation rules live in their own tables (client accounts with domains and approved/excluded mode) and go through the same engine. Rules are active or revoked; purging happens in receipts. No admin chat exclusion (admins can't see users' chats). The matcher uses plain string search with Unicode-category word boundaries (letters, marks and digits are word characters, so Devanagari matras stay attached). People are keyed by email address. No reminders yet (no notification channel until M5). Words inside email addresses are masked on screen, but the address itself is kept encrypted, because it identifies the person | Before external customers: Aho–Corasick for large lists, OID merge, admin chat rules. Reminders come with Teams in M5 |
| Background work | Step Functions / durable queues | In-process tasks, plus a sweeper every 5 minutes that resumes interrupted purge jobs and fails scans cut off by a restart (`vanimo/controls/sweeper.py`) | Move to a queue when there is more than one API task |
| Housekeeping functions | Separate sweeper role | `vanimo_private.fail_stale_scans` / `claim_purge_jobs` are SECURITY DEFINER functions the API role can call. They act across tenants and return only IDs. `record_org_domains` accepts domains from Microsoft 365 scans, plus the sample domain in the local tenant only | Give the sweeper its own database role; add an admin view of recorded organisation domains |
| Sources index | One index per data source | One index per user. After switching between the sample workspace and Microsoft 365, the old index is hidden until the new scan finishes. Reviews are remembered per source | Split the index by source if both are used side by side |
| Sign-in | Entra only | Also email + password, local/dev only, for testing while the Entra app is pending | Removed or kept off in prod (the settings refuse it) |

## M0 demo and week-1 spikes

**Demo:** open the `WebUrl`, sign in. You should see your name, your manager and the subjects of your last 5 sent emails. Only headers are read; nothing is stored.

**Spikes:** use the Diagnostics and Teams prefill tabs, which need the `Vanimo.Admin` role. Record the results in `docs/05` §5.

| # | Spike | How |
|---|---|---|
| 1 | Teams prefill in existing chats | *Teams prefill test* tab: tests A and B on desktop, web and mobile |
| 2 | Add-in insert/read | Render the manifest and add it in Outlook (*Get add-ins → My add-ins → Add a custom add-in*). Test sign-in and insert in new Outlook, classic, web and Mac:<br>`py surfaces/outlook-addin/render_manifest.py https://<cloudfront-domain> > manifest.xml` |
| 3 | Graph delta details, `MSIP_Labels` | Diagnostics → *Run checks*: `sent_headers` and `sent_delta_headers` rows. **`uniqueBody` in delta moves to M2:** it needs a message body, and no body is read before the user's review step. The quote-stripper fallback is planned anyway |
| 4 | Transcript access as organiser/attendee | Diagnostics → `meeting_transcripts` row |
| 5 | Drafts on Outlook mobile | Diagnostics → *Create test draft*, check the phone, then *Delete* |
| 7 | Latency from Mumbai | Diagnostics → *Measure latency* (Haiku 5.5, Sonnet 5.5) |
| 11 | Data-control Graph checks | Diagnostics:<ul><li>*Run checks*: chat roster, `chatType` and `topic` filters, `conversationId` on forwards, calendar</li><li>*Time the header pass*: how long the M1 metadata review takes to build</li></ul>Header-only subscriptions wait for M1, because they need a public webhook |
