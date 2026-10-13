# Vanimo: application code

The build plan is `docs/03-mvp-plan-and-roadmap.md` §0 (solo track M0–M6). This folder holds the code (D11):

| Folder | What | Stack |
|---|---|---|
| `backend/` | API, Graph access, model router, migrations, eval harness, canaries | Python 3.14, FastAPI, SQLAlchemy + psycopg, Alembic, MSAL, Anthropic SDK (Bedrock) |
| `frontend/` | Web control center + Outlook add-in task pane | React 19, Vite, TypeScript, Fluent UI 9, MSAL |
| `infra/` | One regional cell on AWS | AWS CDK (Python): VPC, Aurora PostgreSQL 18 (Serverless v2), ECS Fargate, internal ALB, CloudFront, S3, KMS, Secrets Manager |
| `infra/entra/` | How to register the Entra app | — |
| `surfaces/outlook-addin/` | Outlook add-in manifest (XML) | — |
| `docker-compose.yml` | Local Postgres 18 (port 5433) | Docker |

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
- **Models only from the cell's allow-list** (Claude on Bedrock: Haiku 4.5 by default, Sonnet 5.5 for premium drafts).
- **Canaries and evals from day one** (`vanimo/canary.py`, `vanimo/evals/`).

## Local development (Windows, PowerShell or Git Bash)

Prerequisites: Docker Desktop, Python 3.14, uv, Node 24.

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
   - In the Bedrock console (ap-south-1), check that **Claude Haiku 4.5** and **Claude Sonnet 5.5** are enabled.
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
| API runtime | API Gateway + Lambda BFF, separate drafting service (§4.2) | One FastAPI service on ECS Fargate behind an internal ALB, reached only through CloudFront (VPC origin) | Revisit when drafting gets its own warm service (M3) |
| Egress | No internet egress from the data plane; Graph/Bedrock allow-list (Network Firewall / DNS Firewall) (§4.2) | API tasks reach the internet through one NAT gateway | Add the egress allow-list and WAF |
| Bedrock IAM | Scoped to allowed models | `bedrock-mantle:CreateInference` on `*`, limited to the cell region. The model allow-list is enforced in code | Scope to model ARNs once the ARN format is published |
| Keys | Per-tenant CMKs, per-user data keys (§8.2) | One cell CMK | Per-tenant keys arrive with external tenants |
| Entra | Read app + Compose app; certificate in KMS, no client secret (§5.1–5.2) | One app with a client secret in Secrets Manager (D8) | Split the apps; switch to a certificate |
| Add-in CSP | Enforced | Report-only until the add-in spike confirms Outlook's hosts | Enforce in M3 |
| Stores | S3 Vectors, DynamoDB, Valkey | Aurora only | Added when M2/M4 need them |

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
| 7 | Latency from Mumbai | Diagnostics → *Measure latency* (Haiku 4.5, Sonnet 5.5) |
| 11 | Data-control Graph checks | Diagnostics:<ul><li>*Run checks*: chat roster, `chatType` and `topic` filters, `conversationId` on forwards, calendar</li><li>*Time the header pass*: how long the M1 metadata review takes to build</li></ul>Header-only subscriptions wait for M1, because they need a public webhook |
