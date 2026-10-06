# 03 — AWS AI & Agent Stack for PersonaAgent

**Track:** Amazon Bedrock AgentCore, Bedrock models, Claude Platform on AWS, guardrails/PII services, model customization, LLM cost model
**Prepared:** 2026-10-06 (research run 2026-10-05/06) · **Audience:** founders + engineers making build decisions
**Founder constraints applied:** M365 mid-market/enterprise per-seat B2B · v1 regions US + India (EU/UK later) · 3–6 engineers, ~3-month MVP · recorder is work-only and tenant-admin governed · Phase-1 redaction precise to US + Indian requirements.

**How to read confidence tags:** **High** = read directly from an AWS/Anthropic primary source (docs page, AWS Price List API file, official blog/What's New) during this run. **Med** = primary source but ambiguous/conflicting, or derived by arithmetic from primary numbers with stated assumptions. **Low** = estimate or recollection not re-verified in this run (always labelled).

> Method note: the session's web-search budget ran out mid-run, so the second half of the research relied on fetching known primary URLs (docs.aws.amazon.com pages and their table-of-contents JSON, the **AWS Price List API** bulk files for `us-east-1`/`ap-south-1`, AgentCore/Bedrock pricing pages, Anthropic docs). All Bedrock/AgentCore prices below come from the AWS Price List API files published 2026-09-15 → 2026-10-03 unless stated otherwise.

---

## Executive summary

- **AgentCore is mature enough to build on** (High). GA was 13 Oct 2025; SOC 1/2/3, ISO, CSA STAR, HIPAA-eligible and FedRAMP per AWS docs. 2026 shipped Policy GA (3 Mar), Evaluations GA, Microsoft OBO token exchange (Apr), harness and Managed KB GA (17 Jun), per-tenant Gateway rate limits (Aug) and **Runtime v2** (18 Sep: ~2 s P75 cold starts, elastic memory). Runtime v2 lists at **$0.1276 per vCPU-hour + $0.0169 per GB-hour**. Short-term Memory moved to **per-GB pricing on 6 Oct 2026**. Runtime compute is ~$0.0003 per drafting turn, which is noise next to tokens.
- **Use AgentCore selectively.**
  - Runtime: conversational assistant and memory Q&A.
  - Identity: Entra inbound + **Graph OBO** (`MicrosoftOAuth2`).
  - Gateway: MCP tools with per-tenant limits.
  - Policy: Cedar authorization on tool calls.
  - Keep the **drafting path a warm Fargate workflow** (one streaming Bedrock call), and keep the persona corpus in our own stores. AgentCore Memory's quotas (`IngestData` 10 TPS fixed, 30 TPS retrieval) and built-in CRIS make it unsuitable for 150k-message backfills.
  - Watch the hard limits: 25 new sessions/s per account, 2 vCPU/8 GB per session, 8-h sessions.
- **Claude on Bedrock = Anthropic list price at Global routing** (High, AWS Price List):

  | Model | Input / output per M | Cache read |
  |---|---|---|
  | Opus 5.5 | $4 / $20 | $0.20 |
  | Sonnet 5.5 | $2 / $10 | $0.20 |
  | Haiku 4.5 | $1 / $5 | $0.10 |
  | Fable 5.1 | $10 / $50 | $0.25 |

  - **Geo/regional routing costs +10%.** Caching TTLs are 5 min and 1 h. The cache minimum is **512 tokens on Sonnet/Opus 5.5 but 4,096 on Haiku 4.5**.
  - **Bedrock batch (50% off) currently covers Haiku 4.5, Sonnet 4.6 and Opus 5 but *not* Sonnet 5.5, Opus 5.5 or Fable 5.1.**
  - Sonnet/Opus 5.5 are **Standard tier only**: no Priority, Flex or Reserved.
- **India residency is the pivotal constraint** (High, Bedrock model cards).
  - From Mumbai/Hyderabad, **Sonnet 5.5, Opus 5.5 and Fable 5.1 are Global-only**. **Only Haiku 4.5 (and Opus 5) have an India geo profile (`in.` → Mumbai + Hyderabad only).**
  - Titan V2 embeddings and open-weight models (gpt-oss, Qwen3, Ministral) run **in-Region in Mumbai**. Rerank models are not in India.
  - AgentCore built-in Memory extraction, Policy NL authoring and Evaluations use **APAC or global CRIS**; override them.
  - **Claude Platform on AWS offers only `us` or `global` inference** and is Anthropic-operated. It is not an India-residency option.
- **Claude Platform on AWS** (GA 11 May 2026) is Anthropic-operated with same-day API parity: Message Batches, Files, MCP connector, Skills, Managed Agents at $0.08 per session-hour. Billing goes through AWS Marketplace at list price. ZDR is on request, there is **no HIPAA-ready program**, and `inference_geo: us` costs 1.1×. **Recommendation:** Bedrock for all customer content. CPAWS only as an opt-in accelerator (50%-off Sonnet 5.5 batch, Anthropic-only features) and as a failover capacity pool.
- **Redaction, US + India precise** (High for coverage; Med for costs):
  - **Bedrock Guardrails** PII covers US SSN/ITIN/passport/bank and supports **Hindi**, but has **no Indian ID types**.
  - **Comprehend** detects **Aadhaar, PAN, Voter ID, NREGA** (English/Spanish only; not in Hyderabad).
  - **Macie** detects **Aadhaar, PAN, Indian DL** (S3 at rest only).
  - **No AWS service natively detects Indian passport, GSTIN, UPI ID, IFSC or US EIN.**
  - Recommended pipeline: deterministic validators + Guardrails `ApplyGuardrail` ($0.10 per 1k text units; regex free) + an LLM classifier pass + Macie sampling. That costs **≈ $20–27 one-off per user for a 150k-message backfill and ≈ $1/user/month ongoing**. Comprehend on every message would cost $46–180 per user.
- **Per-user fine-tuning is not worth it in v1** (Med). Claude 4.x/5.x can't be fine-tuned on Bedrock. Per-user Nova SFT costs ≈ $3–10/user-month with weaker writing and erasure headaches. Custom Model Import (merged weights only) is ≈ $2.5k/month per always-on model copy. Use retrieval + prompting (≈ $0.015 per Sonnet 5.5 draft) and log feedback for a later shared RFT/SFT model.
- **Cost per active user-month** (Med; LLM + AI-platform only, excluding STT/storage):

  | Configuration | Low | Typical | Heavy |
  |---|---|---|---|
  | US recommended (Sonnet 5.5, US geo) | **$13.65** | **$23.46** | **$40.63** |
  | US economy (Haiku 4.5) | $7.65 | $12.66 | $20.73 |
  | India-resident (Haiku 4.5 `in.`) | $7.73 | $13.03 | $21.20 |

  Output tokens and Q&A depth dominate, not caching.

---

## 1. Amazon Bedrock AgentCore (state in Oct 2026)

### 1.1 Status and timeline (High)

| Date | Milestone (from AgentCore release notes / What's New) |
|---|---|
| Jul 2025 | Preview (AWS Summit New York). |
| **13 Oct 2025** | **GA** — VPC, PrivateLink, CloudFormation, tagging for all services; Runtime adds A2A; Gateway adds MCP-server targets + IAM auth. |
| Dec 2025 | Policy (preview), **episodic memory strategy**, WebSocket **bidirectional streaming** in Runtime, Evaluations (preview). |
| Feb 2026 | ISO and CSA STAR certified. |
| **3 Mar 2026** | **Policy GA** (Cedar). Mar 2026: **Evaluations GA**, stateful MCP in Runtime, Memory resource-based policies, control-plane PrivateLink. |
| Apr 2026 | Identity **On-Behalf-Of (OBO) token exchange**; Memory structured **metadata filtering**; harness preview; São Paulo + Canada Central. |
| May 2026 | GovCloud (US-West) GA; bring-your-own file system (S3 Files/EFS) for Runtime/harness; Payments preview. |
| **17 Jun 2026** | **Harness GA**, **Managed Knowledge Base GA**, **Web Search GA**, Policy ↔ **Bedrock Guardrails** integration, Recommendations / Batch Evaluations / A/B testing GA, **SOC 1/2/3 in scope**, Runtime quota increases. |
| Aug 2026 | Agent Registry GA; Memory `IngestData` (direct long-term ingestion), flexible namespaces, JSON (non-conversational) payloads; **Runtime "Instances" compute type** (EC2 in your account, sessions up to 14 days, GPU); **Gateway customer-configurable rate limits** (per JWT claim / tool / model — explicitly for multi-tenant isolation); Runtime data-plane quota raised to 1,000 TPS. |
| **18 Sep 2026** | **Runtime v2** (new microVM runtime): P75 cold start ≈2 s for 200 MB–2 GB images (v1: ~5.4 s → ~30 s), elastic memory with idle reclaim after 120 s, new consumption pricing. Sep 2026: Identity **Consent Portal**; harness interactive shells, custom OpenAI-compatible endpoints, lifecycle hooks. |
| Oct 2026 | Gateway private-CA support for targets. |

**Bottom line:** AgentCore is no longer an early-preview bet. It has been GA for ~12 months, has SOC/ISO/CSA STAR coverage, and has shipped most of the gaps early adopters complained about in 2025: cold starts, memory high-water billing, per-tenant rate limits, OBO with Entra, and memory metadata filters. It is still moving fast. Pricing changed twice in Sep–Oct 2026, so lock assumptions per quarter.

### 1.2 Components and how PersonaAgent would use them

| Component | What it is (verified) | PersonaAgent use |
|---|---|---|
| **Runtime** | Serverless agent hosting. Each session gets a dedicated microVM with its own CPU, memory and filesystem; the microVM is terminated and memory sanitized when the session ends. Protocols: HTTP, MCP (stateless/stateful), A2A, AG-UI, WebSocket bidirectional streaming. Any framework (Strands, LangGraph, CrewAI, LlamaIndex, OpenAI Agents SDK, custom) and any model. Python and Node.js direct-code deploy or a container ≤2 GB. **v2** (Sep 2026) adds fast starts and elastic memory. **Instances** (Aug 2026) runs on EC2 in your account for long or GPU sessions. | Hosts the interactive **drafting agent** and the **memory Q&A agent**. One session per user conversation. |
| **Memory** | Short-term events (`CreateEvent`) plus asynchronous long-term extraction strategies: **semantic, summary, user-preference, episodic** (built-in), **built-in overrides** (your prompts, Bedrock model in your account) and **self-managed** (your pipeline). Namespaces keyed on actor/session, metadata filters, `RetrieveMemoryRecords` semantic search, `IngestData` for direct long-term ingestion, JSON payloads. | Optional. Good for conversational memory with the agent itself. **Not** a replacement for the persona knowledge base built from 150k messages per user (see §1.4 and §6). |
| **Gateway** | Turns APIs, Lambdas, OpenAPI/Smithy, MCP servers and other AgentCore runtimes into MCP tools. Inbound JWT/IAM auth, outbound OAuth/API key. **Semantic tool search**. New: HTTP passthrough, inference targets, response streaming, configurable rate limits (requests, tokens, connections) keyed by JWT claim, IAM principal, tool or model. | Single MCP front door for tools such as `search_persona_kb`, `get_thread`, `get_recipient_profile`, `search_transcripts` and `create_draft`. Per-tenant rate limits. |
| **Identity** | Workload identities. Inbound JWT validation (Cognito, Entra ID, Okta and others). Outbound credential providers with a KMS-encrypted **token vault**. Built-in `MicrosoftOAuth2` vendor. **OBO token exchange** (Microsoft OBO via `JWT_AUTHORIZATION_GRANT`, `requested_token_use=on_behalf_of` added automatically). Consent Portal. Can reference existing Secrets Manager secrets. | Validate the user's Entra token on the way in, then exchange it **on-behalf-of** for a Graph token (`Mail.Read`, `Chat.Read`) without a second consent screen (§1.6). |
| **Policy** | Cedar policies evaluated at the Gateway, outside agent code. Can be authored in natural language and converted to Cedar. Since Jun 2026 it can invoke Bedrock Guardrails on tool inputs and outputs. | Deterministic guardrails such as "agent may only call `send_mail` if `user.role == 'owner'` and `draft.approved == true`" and "never read another tenant's KB". |
| **Evaluations** | Built-in LLM-judge evaluators (helpfulness, faithfulness, tool-selection and similar), custom evaluators, online sampling of production traces, batch evaluations, A/B tests, recommendations. | Score "sounds like me" drafts and catch regressions when switching models (Sonnet ↔ Haiku). |
| **Observability** | OTEL traces, spans and metrics to CloudWatch/X-Ray. `ActiveSessionCount` metric. Billed at CloudWatch rates. | Per-tenant latency and cost dashboards. |
| **Code Interpreter / Browser** | Sandboxed code (Python, JS/TS, Node) and headless Chrome in microVMs. | Not needed for v1. |
| **Harness** (GA Jun 2026) | Managed agent loop (`CreateHarness` / `InvokeHarness`) with filesystem, shell, memory, skills, any model including Bedrock Mantle (which also exposes OpenAI GPT-5.x on Bedrock) and LiteLLM. No separate charge. | Fast prototyping. For the production drafting path we want our own loop, for latency and prompt control. |
| **Managed Knowledge Base** (GA Jun 2026) | Fully managed RAG behind the Gateway: connectors for S3, SharePoint, Confluence, Google Drive, OneDrive and Web Crawler; hybrid search, ranking, "agentic retrieval". | Interesting for org documents later. Not for per-user mailbox-derived persona data in v1, because there are no per-user ACL guarantees we could verify. |
| **Web Search** (GA Jun 2026) | Amazon-operated web index exposed as a Gateway connector, "zero data egress". | Not needed. |
| **Agent Registry / Payments / Optimization** | Catalogue, agent payments (x402/MPP), failure/intent insights. | Not needed for v1. |

### 1.3 Runtime limits that matter (High — AgentCore quotas page)

| Limit | Value | Adjustable? |
|---|---|---|
| Active session workloads per account | **5,000** in us-east-1 / us-west-2; **2,500** in other Regions (incl. ap-south-1) | Yes |
| Hardware per session (microVM) | **2 vCPU / 8 GB max** | No |
| Container image / direct-code package | 2 GB image; 250 MB zipped / 750 MB unzipped code | No |
| Sync request timeout | **15 min** | No |
| Max payload | **100 MB** request/response; streaming chunk 10 MB | No |
| Streaming / WebSocket connection max | **60 min**; WebSocket frame 64 KB; 250 frames/s | No |
| Async job max | **8 h** | No |
| Idle session timeout | 15 min default (`idleRuntimeSessionTimeout`) | Yes (API) |
| Max session lifetime | **8 h** per lifecycle on microVMs (`maxLifetime`), resumable; **14 days** on Instances | Yes (API) |
| Session storage | 1 GB per session (persistent across stop/resume if configured) | No |
| Data-plane API rate | **1,000 TPS per account** (shared by `InvokeAgentRuntime` and related APIs) | Yes |
| New session creation | **25 TPS per account** (all endpoints) | Yes |

**Implications.**

- **25 new sessions/s per account** is the real ceiling for an interactive product. Example: 50k DAU, each opening about 10 drafting sessions in a 9-hour workday, is about 15 sessions/s average and well above that in morning peaks. Plan to **reuse a session per user per working block**, not per draft (sticky `runtimeSessionId`, 15-min idle timeout). Request a quota increase before GA.
- The 2,500 active-session default outside us-east-1/us-west-2 also applies to **Mumbai**. Request increases early for India.
- AgentCore **does not enforce session-to-user mapping**. That is your backend's job (docs note). Never derive `runtimeSessionId` from guessable values. It must be at least 33 characters.

### 1.4 Memory: what it does, and its limits for this product (High for facts, Med for fit)

- **Short-term memory:** raw events (conversation turns or, since Aug 2026, JSON payloads up to 100 KB), keyed by `actorId` and `sessionId`. Event expiry is configurable from 7 to 365 days.
- **Long-term memory:** asynchronous extraction into memory records, organised in namespaces (flexible namespace variables since Aug 2026). Retrieval uses `RetrieveMemoryRecords` (semantic) and `ListMemoryRecords`, with structured metadata filters (Apr 2026). Built-in strategies: semantic facts, session summaries, user preferences, and **episodic** (Dec 2025: captures episodes and reflections across sessions). "Built-in overrides" let you replace the extraction/consolidation prompts and run them on a Bedrock model in your account. "Self-managed" means you run the pipeline and only use the store.
- **Quotas to design around:**

  | Quota | Value | Adjustable? |
  |---|---|---|
  | Memory resources per Region | **150** | Yes |
  | Strategies per memory | 6 | No |
  | `CreateEvent` | 200 TPS per account; **5 TPS per actor per session** | Partly |
  | **`RetrieveMemoryRecords`** | **30 TPS per account** | Yes |
  | Long-term extraction | **150k tokens/min per account** | Yes |
  | Episodic extraction | 50k tokens/min per session | No |
  | `IngestData` | **10 TPS** | No |
  | Message / event size | 100 KB per message, 10 MB per event | No |

- **Fit for PersonaAgent:** AgentCore Memory is designed for "remember what the user told the agent". Our persona corpus is different: about 150k historical messages per user, multi-store, with graph and SQL facets and strict per-tenant isolation.
  - A 150k-message backfill per user would blow through `IngestData` (10 TPS, not adjustable) and the 150k-TPM extraction quota within days of onboarding a few hundred users.
  - At 30 TPS default retrieval, memory Q&A for thousands of concurrent users needs a quota increase.

  **Recommendation (Med):** use AgentCore Memory only for agent-conversation memory, such as "user said 'never sign off with Cheers'". It can be a self-managed strategy whose records we write ourselves, if useful. Keep the persona and transcript corpora in our own stores (S3 + OpenSearch/S3 Vectors + Aurora + optional Neptune). See §6 and track 04.

### 1.5 Gateway (High)

- Defaults: 1,000 gateways/account, 100 targets per gateway, 1,000 tools per target. Tool-call/list rate is 200 TPS per gateway and per account, with 5,000 concurrent connections (adjustable). **Search-based tool calls are 25 per minute**, so don't rely on semantic tool search in the hot path. Payload limit is 6 MB.
- **Configurable rate limits (Aug 2026)** use dimension keys such as JWT `sub`, custom claims (e.g. `tenant_id`), IAM principal, tool and model. Metrics are requests/s, **tokens per minute** for inference targets, and connections. Setting `rate=0` blocks one caller instantly. Use this to give each tenant (and each seat) a fair share and contain noisy neighbours. The effective limit is `min(service ceiling, your limit)`.
- **Inference targets** (Jun 2026) mean the Gateway can sit in front of `/v1/messages` and `/v1/chat/completions`. This gives one place to meter tokens per tenant.

### 1.6 Identity — the Entra / Microsoft Graph pattern (High for API facts; Med for end-to-end fit)

**Inbound.** Configure the Runtime/Gateway authorizer with the tenant's Entra discovery URL (`https://login.microsoftonline.com/{tenantId}/v2.0/.well-known/openid-configuration`) and allowed `aud` = our app ID.

- v1.0 and v2.0 tokens are supported, **but only tokens "that do not have any custom claims"**.
- For multi-tenant SaaS you will validate tokens from many Entra tenants. **Verify in a spike** how to express "any tenant that has consented to our app" (multi-tenant `organizations` discovery vs one authorizer per tenant). The docs only show a single tenant-ID discovery URL.

**Outbound to Graph.** Create a `MicrosoftOAuth2` credential provider (`clientId`, `clientSecret`, `tenantId`). Each provider gets a **unique callback URL** that you register in Entra (session-binding protects against CSRF and replay). Tokens live in the **token vault**, encrypted with an AWS-managed or customer-managed KMS key.

**OBO (Apr 2026).** Built in for `MicrosoftOAuth2` using the JWT-bearer grant. The agent calls:

1. `GetWorkloadAccessTokenForJWT` with the user's inbound Entra token, then
2. `GetResourceOauth2Token` with `oauth2Flow=ON_BEHALF_OF_TOKEN_EXCHANGE` and scopes `Mail.Read Chat.Read`.

The result is a delegated Graph token without a second consent prompt. This fits the confirmed MVP permission model (delegated, read-only).

**Background ingestion caveat.** OBO needs a live inbound user token, so it suits interactive drafting and Q&A. The **backfill and delta-sync workers** run when the user is offline, so they need a persisted delegated refresh token (`offline_access`). You can get one either from the 3-legged `USER_FEDERATION` flow stored in the vault or from our own KMS-encrypted token store.

- We could **not verify** from AgentCore docs how the vault handles refresh-token rotation and expiry for Microsoft (Entra refresh tokens are long-lived but can be revoked by Conditional Access).
- **Spike this in week 1.** If vault semantics are opaque, keep ingestion tokens in our own per-tenant KMS-encrypted store (DynamoDB + KMS CMK per tenant). Use AgentCore Identity only for interactive OBO.

**Quotas.** 11,000 workload identities; 50 OAuth2 credential providers per account per Region (adjustable). Because the limit is 50, use **one multi-tenant Entra app and one provider**, not one provider per customer tenant. `GetResourceOauth2Token` runs at 200 TPS.

**Pricing.** $0.010 per 1,000 token/API-key requests, **free when called through Runtime or Gateway**.

### 1.7 Policy, Evaluations, Observability (High)

- **Policy** (GA 3 Mar 2026). Limits: 1,000 policy engines per account per Region, 1,000 policies per engine, 10 KB per policy, 400 KB Cedar schema per engine. Price: **$0.000025 per authorization request** ($0.025 per 1k), plus $0.13 per 1k tokens for natural-language authoring.
- **Evaluations.** Built-in evaluators cost **$2.40 per M input tokens and $12.00 per M output tokens**. Batch is 25% off ($1.80 / $9.00). Custom evaluators cost **$1.50 per 1,000 evaluations** plus your own model usage. Quotas: 1M input TPM and 1,200 evaluations/min (200/min in **Mumbai** and Singapore).
- **Observability** is billed at CloudWatch rates (spans, logs, metrics). Budget a few dollars per thousand sessions. Sample traces in production.

### 1.8 AgentCore pricing (High — AgentCore pricing page fetched 2026-10-05 + AWS Price List API, us-east-1)

| Component | Price | Notes |
|---|---|---|
| Runtime microVM **v1** | $0.0895 per vCPU-hour; $0.00945 per GB-hour | Per-second billing, 1 s minimum, 128 MB memory minimum. CPU is **not** billed during I/O wait (e.g. waiting on the LLM); memory is billed for the whole session. |
| Runtime microVM **v2** | **$0.1276 per vCPU-hour; $0.0169 per GB-hour** (consumption) | Higher unit rate but memory follows actual use (idle reclaim after 120 s). AWS says most agents pay less. **Committed baseline $0.0997 / $0.0132** is "launching October 2026". |
| Runtime **Instances** | EC2 On-Demand price + **12% management fee** (7.8% for GPU G-series) | Savings Plans/RIs apply to the EC2 portion. |
| Browser, Code Interpreter | $0.0895 per vCPU-hour; $0.00945 per GB-hour | — |
| Gateway | **$0.005 per 1k** invocations (ListTools/InvokeTool/Ping); $0.025 per 1k search calls; $0.02 per 100 tools indexed per month; $0.006/GB VPC egress | — |
| Identity | $0.010 per 1k token/API-key requests | Free via Runtime/Gateway. |
| Memory — short-term | **Through 2026-10-05:** $0.25 per 1k new events. **From 2026-10-06:** $1.00 per GB ingested, $0.20 per GB retrieved, $0.10 per GB-month stored | Each event is billed at **min 12 KB, max 64 KB**. New model ≈ **$0.012 per 1k small events**, about 20× cheaper for small events (Med — arithmetic). |
| Memory — long-term | $0.75 per 1k records/month (built-in strategies); **$0.25 per 1k records/month** (override/self-managed); **$0.50 per 1k retrievals** | Built-in extraction model cost is included; overrides bill model use to your account. |
| Policy | $0.000025 per authorization request | — |
| Evaluations | $2.40/M input, $12/M output (built-in); $1.50 per 1k custom evaluations | — |
| Managed Knowledge Base | **$0.001 per query** (retrieval), **$0.004 per query** (agentic retrieval), **$5.00 per GB-month** storage | From the AgentCore price list file. |
| Web Search | $7.00 per 1k queries | — |
| Observability | CloudWatch pricing | — |
| Harness | No separate charge | — |

**Worked example (Med — arithmetic on list prices).** One drafting turn on Runtime v2 uses about 0.25 vCPU-seconds of real CPU (prompt assembly, retrieval calls, JSON). It holds about 512 MB for a 6-second LLM-bound turn, plus about 120 s until memory is reclaimed.

- CPU: 0.25 s ≈ $0.0000089.
- Memory: 0.5 GB × 126 s ≈ 0.0175 GB-h ≈ $0.0003.

So **≈ $0.0003 per turn**, or about **$0.15–0.30 per user per month** at 25 turns/day. Runtime compute is a rounding error next to LLM tokens unless sessions are kept warm for hours. With v1 high-water billing, a session held open for 8 hours at 1 GB would cost $0.076 per day just in memory. Use short idle timeouts.

### 1.9 Regional availability — AgentCore (High — AgentCore Regions page, fetched 2026-10-05)

| Capability | us-east-1 | us-west-2 | **ap-south-1 (Mumbai)** | **ap-south-2 (Hyderabad)** | eu-central-1 | eu-west-1 |
|---|---|---|---|---|---|---|
| Runtime microVMs | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Runtime Instances | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ |
| **Memory** | ✓ | ✓ | ✓ | **✗** | ✓ | ✓ |
| Gateway | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Identity | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Built-in tools (Code Interpreter, Browser) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Observability | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Policy | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Evaluations / optimization | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Harness | ✓ | ✓ | ✓ | **✗** | ✓ | ✓ |
| Web Search tool | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Agent Registry | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| Payments | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ |

**India reading:** every AgentCore component PersonaAgent needs is in **Mumbai (ap-south-1)**. Hyderabad lacks Memory and harness, so it can serve as a DR Region for Runtime/Gateway/Identity, but not as a full mirror. The AWS Price List also publishes AgentCore SKUs for `ap-south-1` and `ap-south-2`.

**Residency trap (High — AgentCore cross-Region inference doc).** Several AgentCore features make their own LLM calls through cross-Region inference:

- **Memory built-in strategies:** from Mumbai the "Asia Pacific" geography routes to **Tokyo, Seoul, Mumbai, Singapore, Sydney**.
- **Policy** natural-language authoring: APAC geography. Hyderabad uses **global** CRIS.
- **Evaluations** built-in evaluators: APAC geography. Hyderabad uses **global** CRIS.

The docs give the opt-outs: for Memory, use **built-in-with-overrides** strategies, which pick the model (e.g. Haiku 4.5 via `in.`); for Evaluations, use **custom evaluators** with an in-Region model. CloudWatch/CloudTrail "won't specify the AWS Region in which data inference occurs." For India-resident tenants, treat built-in Memory extraction and built-in evaluators as **out-of-India processing** unless overridden.

### 1.10 Multi-tenant SaaS patterns on AgentCore (Med — synthesis of documented primitives; no AWS reference architecture was re-verified in this run)

1. **Tenant context propagation.** The user's Entra JWT carries `tid` (Entra tenant) and `oid`. Our web/Teams front end maps it to our `tenant_id` and `user_id`, then calls `InvokeAgentRuntime` with the user's JWT (inbound auth) and a server-generated `runtimeSessionId`.
   - Inside the agent, every tool call goes through **Gateway**. Gateway forwards identity claims. **Policy** (Cedar) checks `principal.tenant == resource.tenant`. Tool Lambdas enforce row-level filters again (defence in depth).
   - Entra tokens with custom claims are not accepted inbound (see §1.6). Keep tenant mapping server-side, not as a custom claim.
2. **Isolation tiers.**
   - *Pooled (default):* one runtime/gateway, per-session microVM isolation, per-tenant KMS keys and data partitions in our stores. Gateway rate limits per `tenant_id`.
   - *Silo (enterprise upsell):* a dedicated runtime and gateway per tenant, optionally in a dedicated AWS account under AWS Organizations, using the same IaC. Quotas are per account and per Region, so siloing also gives an independent quota envelope.
3. **Noisy neighbour.** Gateway token/requests limits per tenant and seat. Bedrock application inference profiles per tenant for cost attribution (tags). Separate Bedrock quotas for batch vs interactive. Per-tenant budgets enforced in our orchestrator.
4. **Memory isolation.** If AgentCore Memory is used, put the tenant in the namespace (`/tenant/{tenantId}/user/{actorId}/…`). Add metadata filters and resource-based policies. The 150-memory-resource default rules out "one memory resource per tenant" beyond the first ~150 tenants per Region without an increase.

### 1.11 Known limitations and early-adopter pain points (Med)

- **Documented constraints:**
  - 2 vCPU / 8 GB per session.
  - 15-min synchronous request cap (use async/streaming for long jobs).
  - 1 GB session storage.
  - Search-based tool calls capped at 25/min.
  - Memory `IngestData` 10 TPS; retrieval 30 TPS default.
  - Entra inbound tokens must not have custom claims.
  - No enforcement of session↔user mapping.
  - The bedrock-mantle (Messages API) endpoint for Claude does **not** support Guardrails, Knowledge Bases, Agents, Flows or structured outputs (§3).
- **Pain points AWS itself acknowledged by shipping fixes in 2026:**
  - v1 cold starts grew with image size (5.4 s → ~30 s), fixed by v2.
  - v1 billed peak memory for the whole session, fixed by v2 elastic memory.
  - Coarse per-endpoint session-creation limits, unified in Aug 2026.
  - No per-caller rate limiting, added in Aug 2026.
- **Not verified:** practitioner complaints from forums (Reddit/HN/Discord). The web-search budget was exhausted before this sweep. Treat community sentiment as unknown and run a 1-week spike measuring p50/p95 cold and warm latency in `us-east-1` and `ap-south-1`.

### 1.12 Microsoft-side fronting (cross-track facts applied)

- **Teams / Outlook front end → AgentCore.** The Teams agent is built with the **Microsoft 365 Agents SDK**, hosted on AWS (ECS Fargate or Lambda behind API Gateway). Its activity handler should:
  1. validate the Bot Connector / Entra token;
  2. resolve `tenant_id` and `user_id`;
  3. get the user's SSO token (Teams SSO) for OBO;
  4. call `InvokeAgentRuntime` (HTTP streaming) and stream partial text back to Teams as typing/streaming messages.

  Keep the Agents SDK service thin: no business logic, so the same Runtime agent also serves the Outlook add-in, the web app and the Windows client.
- **Real-time Teams media** stays out of AWS scope (Windows/.NET media bots in Azure). Meeting content arrives as Graph post-meeting transcripts, so AgentCore only sees text.
- **Agent 365 / Entra Agent ID.** We could not verify any AWS-side integration between AgentCore and Microsoft Agent 365 or Entra Agent ID in this run. The cross-track note says Agent 365 can list agents built on Amazon Bedrock. Treat AWS support as **unverified**. For v1, register PersonaAgent as a normal multi-tenant Entra app plus Teams app.

## 2. Alternatives & complements — what to run where

### 2.1 Options compared (Med — synthesis; facts referenced elsewhere in this report)

| Option | Strengths | Weaknesses for PersonaAgent |
|---|---|---|
| **AgentCore Runtime (+ Gateway/Identity/Policy)** | Per-session microVM isolation; Entra inbound auth + Graph OBO built in; MCP tool gateway with per-tenant rate limits; Cedar policy outside agent code; OTEL observability; serverless. v2 has fast starts (~2 s P75 cold) and elastic memory. | New-session ceiling 25 TPS/account (adjustable). 2 vCPU/8 GB per session. Adds a hop (client → Runtime → Bedrock). Vendor-specific APIs. Memory/Evaluations built-ins use CRIS. |
| **Bedrock Agents (classic)** | Managed orchestration, action groups, KB integration, Guardrails inline. | Older, less flexible orchestration (AWS's 2026 investment is clearly AgentCore + harness). Limited control over prompts/latency. **Not recommended** for new builds. |
| **AgentCore harness** (GA Jun 2026) | Two API calls to a working agent; memory, skills, browsing; any model; export to Strands code. | Opinionated loop. Less control over prompt structure and caching for latency-critical drafting. Not in Hyderabad. |
| **Self-hosted loop (Strands / LangGraph / Anthropic SDK tool runner) on ECS Fargate or EKS** | Full control; warm processes (no per-session cold start); easy streaming via ALB/WebSocket; cheapest at steady load; runs anywhere incl. Mumbai. | You build isolation (per-request tenant scoping, no shared mutable state), auth/OBO, and the tool gateway yourself. |
| **Lambda (+ response streaming)** | Cheapest at low volume; good for short single-call drafts. | Cold starts; 15-min cap; awkward for long agent loops and WebSockets. |
| **Step Functions (+ Bedrock / batch integrations; harness integration since Jun 2026)** | Deterministic, auditable pipelines with retries, fan-out, human approval; ideal for backfill and transcript pipelines. | Not for interactive latency. |
| **Anthropic Managed Agents via CPAWS** | Anthropic hosts loop + sandbox; scheduled deployments; outcomes; memory stores. $0.08 per session-hour plus tokens. | Anthropic is processor (outside AWS processor boundary). 6-h autonomous-session re-auth. No India residency. Not for customer content by default. |

### 2.2 Recommended placement (Med)

1. **Interactive drafting (p95 target ≤ 2.5 s to first token, ≤ 8 s full draft).**
   - **Default: a thin, warm drafting service on ECS Fargate in us-east-1 and ap-south-1.** It assembles the prompt deterministically (style card + top-k exemplars + thread), calls Bedrock with streaming and prompt caching, and runs guardrails pre/post. This is a *workflow*, not an agent: one LLM call, with an optional second "self-check" call.
   - **Use AgentCore Runtime** for the conversational "assistant" mode, where the model needs tools such as "find the last thing I told Priya about pricing" or "check my calendar". Reuse sessions per user to avoid the 25-TPS new-session ceiling and cold starts.
   - The Teams/Outlook front end (M365 Agents SDK service, §1.12) calls either path through one internal API.
   - Rationale: an extra Runtime hop plus possible session creation adds latency for zero benefit when no tool loop is needed.
2. **Background ingestion and persona-building.**
   - **Step Functions + SQS + Lambda/Fargate workers + Bedrock batch inference.** Graph delta sync → redaction (L0/L1) → labeling batch → embedding batch → S3 Vectors/Aurora/Neptune writes → style-card synthesis (one Sonnet call per user per week).
   - Bedrock batch requires ≥100 records per job and returns in hours. Use on-demand plus the Flex tier (open-weight models) for small daily deltas.
3. **Memory Q&A ("what did the client require in the 4 pm meeting?").**
   - **AgentCore Runtime agent** with Gateway tools (`search_transcripts`, `get_meeting`, `search_mail`) and Policy enforcing tenant/user scope. Sonnet 5.5 (US) or Haiku 4.5 `in.` (India) as the reasoner.
   - Optional rerank (Cohere Rerank 3.5, US only).
4. **Evaluations / regression:** AgentCore Evaluations (custom evaluators for India), or offline batch evals via Step Functions.

## 3. Bedrock models in Oct 2026 — Claude, prices, caching, batch, routing & residency

### 3.1 Two ways to call Claude on Bedrock (High)

| Endpoint | API shape | What it supports for current Claude models |
|---|---|---|
| **`bedrock-runtime`** (`InvokeModel` / `Converse`) | Bedrock-native | **Geo (US/EU/AU/JP, plus India for some models) and Global cross-Region profiles.** Supports Guardrails, Knowledge Bases, Agents, Flows, prompt caching, computer use. **Structured outputs not supported** for Sonnet 5.5 / Opus 5.5. |
| **`bedrock-mantle`** (`/anthropic/v1/messages`, "Claude in Amazon Bedrock", Opus 4.7+) | Anthropic Messages API (SDK `AnthropicBedrockMantle`) | Same request body as Anthropic's API. **"Zero operator access"** (Anthropic personnel have no access to the inference infrastructure). Regional endpoint only where listed: per the AWS model cards, Opus 5.5 is in-Region in us-east-1, ap-southeast-4 and GovCloud. Per Anthropic's doc, "In-region only" routing exists in us-east-1/2, us-west-2, eu-north-1, eu-west-1, ap-northeast-1 and ap-southeast-4 (sources differ — **Med**). **Not supported on Mantle:** Guardrails, Knowledge Bases, Agents, structured outputs, Files API, Message Batches, server tools (web search/fetch, code execution), Skills, MCP connector, Managed Agents, server-side `fallbacks`. |

**Practical consequence:** if you want **Bedrock Guardrails inline** with Claude Sonnet/Opus 5.5, use `bedrock-runtime` (Converse/Invoke), or call `ApplyGuardrail` separately (recommended anyway, see §5). If you want the **Anthropic SDK shape**, use Mantle and run guardrails out-of-band.

### 3.2 Claude models and Bedrock on-demand prices (High — AWS Price List API `AmazonBedrockFoundationModels`, us-east-1 file dated 2026-09-30, cross-checked with Anthropic pricing page)

Prices are per 1M tokens. "Global" = global cross-Region profile. "Regional" = geo profile or in-Region, a **+10% premium** that Anthropic's and AWS's docs state for Sonnet 4.5 / Haiku 4.5 / Opus 4.5 and all later models.

| Model (Bedrock ID) | Input (Global / Regional) | Output (Global / Regional) | Cache write 5 min | Cache write 1 h | Cache read | Bedrock Batch |
|---|---|---|---|---|---|---|
| Claude Fable 5.1 (`anthropic.claude-fable-5-1`) | $10.00 / $11.00 | $50.00 / $55.00 | $12.50 / $13.75 | $20.00 / $22.00 | $0.25 / $0.275 | **Not available** |
| **Claude Opus 5.5** (`anthropic.claude-opus-5-5`, GA on Bedrock 22 Sep 2026) | **$4.00** / $4.40 | **$20.00** / $22.00 | $5.00 / $5.50 | $8.00 / $8.80 | **$0.20** / $0.22 | **Not available** |
| Claude Opus 5 | $5.00 / $5.50 | $25.00 / $27.50 | $6.25 / $6.875 | $10.00 / $11.00 | $0.50 / $0.55 | $2.50/$12.50 (global); $2.75/$13.75 (regional) |
| **Claude Sonnet 5.5** (`anthropic.claude-sonnet-5-5`) | **$2.00** / $2.20 | **$10.00** / $11.00 | $2.50 / $2.75 | $4.00 / $4.40 | **$0.20** / $0.22 | **Not available** |
| Claude Sonnet 4.6 | $3.00 / $3.30 | $15.00 / $16.50 | $3.75 / $4.125 | $6.00 / $6.60 | $0.30 / $0.33 | $1.50/$7.50 (global) |
| **Claude Haiku 4.5** (`anthropic.claude-haiku-4-5`) | **$1.00** / $1.10 | **$5.00** / $5.50 | $1.25 / $1.375 | $2.00 / $2.20 | $0.10 / $0.11 | **$0.50/$2.50 (global); $0.55/$2.75 (regional)** |

**Reading the table:**

- **Global Bedrock prices equal Anthropic first-party list prices.** Anthropic API: Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 4.5 $1/$5, Fable 5.1 $10/$50; cache reads $0.20 on Opus/Sonnet 5.5. So there is **no Bedrock price penalty unless you need regional/geo routing (+10%)**.
- **Batch.** Anthropic's Message Batches give 50% off on every model (Opus 5.5 $2/$10, Sonnet 5.5 $1/$5, Haiku 4.5 $0.50/$2.50). Bedrock has its own batch inference (`CreateModelInvocationJob`, JSONL in S3, minimum 100 records per job per AWS's Comprehend-migration guide). **As of this run, Bedrock batch does not list Sonnet 5.5, Opus 5.5, Fable 5.1, Sonnet 5 or Opus 4.8.** The batch-supported-models page and price list stop at Opus 5, Sonnet 4.6 and Haiku 4.5 (**High**).
  - For a 50%-off **Sonnet 5.5** batch, today you need the Anthropic Batch API on **Claude Platform on AWS** or 1P.
  - On Bedrock, use Haiku 4.5 batch, Sonnet 4.6 batch, or open-weight models with batch/Flex.
- **Service tiers** (Reserved / Priority / Standard / Flex) exist on Bedrock (`service_tier` parameter). Per the model cards, **Sonnet 5.5 and Opus 5.5 support Standard only** (no Priority, Flex, Reserved or Batch). **Haiku 4.5 supports Standard and Reserved.**
  - Reserved for Haiku 4.5 is priced per 1K tokens-per-minute per hour: global $0.06 (input) / $0.30 (output) on a 1-month term, $0.054 / $0.27 on 3 months.
  - Reserved minimum is 100k input TPM and 10k output TPM. It targets 99.5% uptime and overflows to Standard.
- **Quotas.** Anthropic's Bedrock doc gives a default of **2M input TPM**, with up to **5M input TPM / 500k output TPM** available without Anthropic approval. RPM is set by AWS (support case).
- **Provisioned Throughput** (hourly model units, no-commit / 1-month / 6-month) still appears in the price list for Amazon (Titan) and custom models. For current Claude models, the TPM-based **Reserved tier** is the commitment vehicle (Haiku 4.5 today, not Sonnet/Opus 5.5) (**Med**).

### 3.3 Prompt caching on Bedrock (High — model cards + price list)

| Model on Bedrock | Min tokens per cache checkpoint | Max checkpoints | TTLs | Write multiplier | Read |
|---|---|---|---|---|---|
| Sonnet 5.5, Opus 5.5 | **512** | 4 | **5 min and 1 h** | 1.25× (5 min), 2× (1 h) | 0.1× Sonnet 5.5 ($0.20); **0.05× Opus 5.5** ($0.20) |
| Haiku 4.5 | **4,096** | 4 | 5 min and 1 h | 1.25× / 2× | 0.1× ($0.10) |
| Nova 2 Lite | 1K | 4 | 5 min only | **free writes** | $0.075/M (global) |

**Design implication.** For **Haiku 4.5** drafting, the cached prefix (system prompt + persona style card + exemplars) must be at least **4,096 tokens**, or nothing caches. On Sonnet/Opus 5.5 the threshold is 512.

Caches are **per organization on Bedrock** (per workspace on 1P/CPAWS) and per model. If most drafts for a user land within 5 minutes of each other (bursty email triage), the 5-min TTL is enough. For a "one draft every 20 minutes" user, the 1-h TTL pays off from the third request.

### 3.4 Cross-Region inference, data residency, and **India** (High — Bedrock model cards, price list, geographic-CRIS doc)

**Bedrock routing options:**

- **In-Region:** stays in one Region.
- **Geo CRIS:** a fixed list of destination Regions inside a geography (`us.`, `eu.`, `apac.`, `jp.`, `au.`, `ca.`, `in.`). AWS: "Cross-Region inference requests to an inference profile tied to a geography … stay within that geography". The destination list of a geo profile "will never change". Data at rest stays in the source Region, but prompts/outputs are processed in the destination Region. If AWS stores data for abuse detection, it is stored in the destination Region.
- **Global CRIS:** "all commercial Regions", list can grow.

| Model | Calling from **us-east-1 / us-west-2** | Calling from **ap-south-1 (Mumbai) / ap-south-2 (Hyderabad)** |
|---|---|---|
| Claude **Sonnet 5.5** | US geo (`us.anthropic.claude-sonnet-5-5` → us-east-1/us-east-2/us-west-2) or Global | **Global only** — no India/APAC geo, no in-Region |
| Claude **Opus 5.5** | US geo or Global | **Global only** |
| Claude Fable 5.1, Sonnet 4.6, Sonnet 4.5 | US geo or Global | **Global only** |
| Claude **Haiku 4.5** | US geo or Global | **India geo `in.anthropic.claude-haiku-4-5-20251001-v1:0` → destinations Mumbai + Hyderabad only**, or Global. Caveat: **structured outputs are not supported via the India profile**. |
| Claude **Opus 5** | US geo or Global | **India geo `in.anthropic.claude-opus-5` → Mumbai + Hyderabad only**, or Global |
| Titan Text Embeddings V2 | In-Region | **In-Region in Mumbai ($0.024/M) and Hyderabad ($0.027/M)** |
| Cohere Embed v4 | In-Region / US geo | Global only |
| Cohere Rerank 3.5 / Amazon Rerank 1.0 | In-Region us-east-1 / us-west-2 (Amazon Rerank: us-west-2) | **Not available in India** |
| gpt-oss-20b/120b, Qwen3 32B, Ministral, Gemma 3 | In-Region | **In-Region in Mumbai** (gpt-oss-20b $0.08/$0.35 per M in Mumbai vs $0.07/$0.30 in us-east-1) |
| Nova Micro / Lite | US geo / in-Region | Geo profile from Mumbai (APAC; destination list not extracted in this run, so assume multi-country) |
| Nova 2 Lite | US geo / Global | Global only |

**What this means for India tenants (pinning to ap-south-1 per the cross-track decision):**

1. **Claude inference that never leaves India is possible today only with Claude Haiku 4.5 (and Opus 5) via the `in.` geo profiles**, at the +10% regional price (Haiku 4.5: $1.10/$5.50 per M, batch $0.55/$2.75).
   - **Sonnet 5.5 / Opus 5.5 / Fable 5.1 from Mumbai are Global-only**, so inference may run in any commercial Region worldwide.
   - On Bedrock, data at rest stays in Mumbai, and these models are ZDR by default (only Fable 5/5.1 retain for abuse detection, §7).
2. **Claude Platform on AWS offers no India option.** `inference_geo` supports only `us` (1.1×) and `global`. The workspace's AWS Region does not pin inference.
3. **Recommended India pattern (Med):**
   - **Default "India-resident" mode:** Haiku 4.5 via `in.` for drafting and extraction; Titan V2 in-Region embeddings; open-weight models in-Region (gpt-oss-20b / Qwen3-32B in Mumbai) for labeling; no rerank model (use hybrid BM25 + vector scoring or a self-hosted reranker on SageMaker/EKS in Mumbai). Everything stored in ap-south-1.
   - **"Premium quality" mode (tenant-admin opt-in):** Sonnet 5.5 via Global CRIS, disclosed as "processed outside India, zero retention, AWS as processor". Watch the Bedrock model cards monthly for an `in.anthropic.claude-sonnet-5-5` profile. AWS added `in.` profiles for Haiku 4.5 and Opus 5, so precedent exists, but nothing announces one for Sonnet 5.5 (**not verified**).
4. **DPDP framing (Low — legal track owns this):** India's DPDP Act regime does not, by itself, mandate in-country processing for ordinary business email. Cross-border transfer is allowed except to government-notified restricted countries, while sectoral regulators such as RBI and SEBI impose their own localisation. **Enterprise buyers, however, frequently *expect* in-India processing**, and Microsoft already keeps their M365 data in-country. The in-India Haiku path and an explicit opt-in for Global Sonnet is the pragmatic answer. Confirm the legal position with track 07/legal.

**US tenants:** pin to us-east-1. Use `us.` geo profiles (us-east-1/us-east-2/us-west-2, +10%) or Global (list price). Global is cheaper by 10% but may route outside the US. For enterprise US customers, default to **US geo**. The 10% premium is the price of a clean residency story.

### 3.5 Latency-oriented features (Med)

- **Priority tier** (faster responses at a premium) is **not available** for Sonnet/Opus 5.5 on Bedrock. Fast mode for Opus 5.5 ($8/$40) exists on Anthropic 1P only (not Bedrock, not CPAWS).
- **Latency-optimized inference** on Bedrock historically covered older models (Claude 3.5 Haiku, Nova Pro, Llama 3.1). The current price list shows only "Nova Pro Latency Optimized" and "Llama 3.1 70B Latency Optimized" SKUs. **Not relevant for Claude 5.x.**
- **Realistic latency levers for drafting:** stream tokens to the client; keep the cached prefix warm (5-min TTL or re-send with `max_tokens: 0` keep-alive where applicable); keep output to 300–600 tokens; use `effort: low` on Sonnet 5.5 for routine replies (thinking can't be disabled on Sonnet/Opus 5.5 — `between_tools` or low effort instead); route short or simple replies to Haiku 4.5.
- **We did not find published p95 TTFT figures for Sonnet 5.5 on Bedrock.** Measure in week 1 from us-east-1 and ap-south-1 (Global CRIS adds a variable cross-Region hop).

### 3.6 Cheap models for high-volume classification/labeling (High — us-east-1 price list; per 1M tokens, input/output)

| Model | On-demand | Batch / Flex | Mumbai availability | Notes |
|---|---|---|---|---|
| **Amazon Nova Micro** | $0.035 / $0.14 | $0.0175 / $0.07 (batch) | APAC geo ($0.041/$0.164) | Text-only, cheapest Amazon model; fine-tunable on Bedrock. |
| Amazon Nova Lite (v1) | $0.06 / $0.24 | $0.03 / $0.12 | APAC geo | Fine-tunable. |
| **Amazon Nova 2 Lite** | $0.30 / $2.50 (global) | $0.15 / $1.25 (batch/flex) | Global only | Reasoning model; SFT and **RFT** fine-tuning on Bedrock. |
| **gpt-oss-20b** | $0.07 / $0.30 | $0.035 / $0.15 | **In-Region** ($0.08/$0.35) | Good JSON/labeling quality per $; open weights. |
| gpt-oss-120b | $0.15 / $0.60 | $0.075 / $0.30 | In-Region | — |
| GPT-OSS-Safeguard-20B | $0.07 / $0.20 | $0.03 / $0.10 | In-Region | Policy-classifier variant; candidate for "is this company-confidential?" classification. |
| Qwen3 32B | $0.15 / $0.60 | $0.075 / $0.30 | In-Region ($0.18/$0.71) | — |
| Qwen3 Next 80B A3B | $0.14 / $1.20 | $0.07 / $0.60 | In-Region | — |
| Ministral 3 8B / 3B | $0.15 / $0.15 ; $0.10 / $0.10 | $0.07 ; $0.05 | In-Region | Very cheap output. |
| Gemma 3 12B | $0.09 / $0.29 | $0.05 / $0.15 | In-Region | — |
| Nemotron Nano 3 30B | $0.06 / $0.24 | $0.03 / $0.12 | In-Region | — |
| Llama 3.1 8B | $0.22 / $0.22 | $0.11 / $0.11 | — | Older; poorer value. |
| Mistral Large 3 (675B) | $0.50 / $1.50 | $0.25 / $0.75 | In-Region | — |
| DeepSeek V3.2 | $0.62 / $1.85 | $0.31 / $0.925 | In-Region | — |
| Claude Haiku 4.5 (batch) | $1.00 / $5.00 | $0.50 / $2.50 | **India geo** | Highest quality of the "small" options; ~7–15× the cost of gpt-oss-20b. |

Bedrock in Oct 2026 also lists proprietary frontier models from other vendors (e.g. OpenAI "GPT-6 Astra" at $10/$50 global, xAI Grok 4.x, Moonshot Kimi K3, Z.AI GLM 5, MiniMax M2.5). They are useful as fallbacks, but they are outside this track's recommendation set.

### 3.7 One-page availability matrix — US vs India Regions (High — model cards, AgentCore Regions page, AWS Price List region indexes)

| Service / capability | us-east-1 | us-west-2 | **ap-south-1 Mumbai** | **ap-south-2 Hyderabad** |
|---|---|---|---|---|
| Claude Sonnet 5.5 / Opus 5.5 / Fable 5.1 | US geo + Global | US geo + Global | **Global only** | **Global only** |
| Claude Haiku 4.5 | US geo + Global; batch | US geo + Global; batch | **India geo (`in.` → Mumbai + Hyderabad) + Global; batch via profile** | **India geo + Global** |
| Claude Opus 5 | US geo + Global; batch | same | **India geo** + Global | **India geo** + Global |
| Titan Text Embeddings V2 | In-Region | In-Region | **In-Region** | **In-Region** |
| Cohere Rerank 3.5 / Amazon Rerank | ✓ / ✗ | ✓ / ✓ | ✗ | ✗ |
| gpt-oss-20b/120b, Qwen3-32B (open weight) | In-Region | In-Region | **In-Region** | ✗ (not in price list) |
| Bedrock Guardrails (PII filter, Classic) | ✓ | ✓ | ✓ | ✓ |
| Guardrails Standard tier | US profile | US profile | APAC profile (6 APAC Regions) | ✗ (not in tier Region list) |
| `InvokeGuardrailChecks` | ✓ | ✓ | ✗ | ✗ |
| AgentCore Runtime / Gateway / Identity / Policy / Observability | ✓ | ✓ | ✓ | ✓ |
| AgentCore Memory / harness | ✓ | ✓ | ✓ (built-ins use APAC CRIS) | ✗ |
| Comprehend (incl. PII) | ✓ | ✓ | ✓ | ✗ |
| Comprehend Medical | ✓ | ✓ | ✗ | ✗ |
| Macie | ✓ | ✓ | ✓ | ✗ |
| Transcribe (+ batch PII redaction, en-IN supported) | ✓ | ✓ | ✓ | ✗ |
| Bedrock Data Automation | ✓ | ✓ (assumed) | ✓ (price list) | ✗ |
| S3 Vectors | ✓ | ✓ | ✓ ($0.066/GB-month) | not checked |
| Custom Model Import / Nova fine-tuning | ✓ / ✓ | ✓ / ✗ | ✗ / ✗ | ✗ / ✗ |

## 4. Customization for persona — fine-tuning, Custom Model Import, per-user LoRA economics

### 4.1 What can be fine-tuned on Bedrock in Oct 2026 (High — Bedrock docs + price list)

| Route | Models | Region | Pricing | Serving |
|---|---|---|---|---|
| **Supervised fine-tuning (SFT)** | Nova Micro, Nova Lite, Nova Pro, **Nova 2 Lite**, Nova Canvas; Titan image/multimodal embeddings; **Claude 3 Haiku** (legacy, us-west-2); Llama 3.1 8B/70B, 3.2 1B/3B/11B/90B, 3.3 70B (us-west-2) | **us-east-1** for Nova; us-west-2 for Llama/Claude 3 Haiku | Training: Nova Micro **$1.00/M tokens**, Nova Lite **$2.00/M**, Nova 2 Lite **$3.78/M**. **Storage $1.95 per custom model per month.** | **Custom Nova models run on-demand at base-model token prices** (price-list "custom-model" SKUs equal base prices, e.g. Nova Micro $0.035/$0.14, Nova 2 Lite $0.30/$2.50). Provisioned Throughput is optional. |
| **Reinforcement fine-tuning (RFT)** | **Nova 2 Lite** (us-east-1), ≤20k prompts, Lambda or LLM-judge graders; open-weight **gpt-oss-20b** and **Qwen3 32B** via OpenAI-compatible fine-tuning APIs (us-west-2, Mantle) | us-east-1 / us-west-2 | Nova 2 Lite RFT **$80 per training hour** (price list) | One-click on-demand inference; open-weight RFT models callable immediately through Mantle Responses/Chat Completions. |
| **No Claude 4.x/5.x fine-tuning** | Bedrock lists no fine-tuning for Claude Haiku 4.5, Sonnet 5.5 or Opus 5.5 | — | — | — |
| **Custom Model Import (CMI)** | Bring **merged** HF weights: Llama 2/3.x, Mllama, Mistral, Mixtral, Flan-T5, GPTBigCode, Qwen2/2.5/2-VL/2.5-VL/**Qwen3** (CausalLM/MoE), **GPT-OSS 20B/120B** (us-east-1 only). ≤200 GB text, context <128K, transformers 4.51.3. **No LoRA-adapter hosting; no batch inference.** | us-east-1, us-east-2, us-west-2, eu-central-1 (**not India**) | **$0.05718 per CMU-minute** (v1); **$0.1433 per CMU-minute** (OSS v2, e.g. GPT-OSS); storage $1.95/model-month. Billed in **5-minute windows** from the first successful call, × running model copies. | On-demand `InvokeModel` with automatic copy scaling. Cold start when scaling from zero (duration not documented — **Low**). |
| **SageMaker AI adapter inference components** | Any LMI/vLLM-served base model; one **base inference component** plus many **adapter inference components** (LoRA `tar.gz` in S3) that share its compute | Any SageMaker Region incl. Mumbai (assumed — **Med**) | Instance-hours. Reference EC2 on-demand prices implied by the AgentCore Instances fee table: g5.xlarge ≈ $1.01/h, g6e.xlarge ≈ $1.86/h, g6e.12xlarge ≈ $10.49/h. SageMaker `ml.*` instances carry a premium over EC2 (**not re-verified**). | Invoke by adapter component name; adapters load on first call. |
| **Self-hosted vLLM / LoRAX multi-LoRA on EKS** | Any open model | Any Region incl. Mumbai | EC2 GPU hours + ops | Highest density (hundreds to thousands of adapters per GPU with paging); highest ops burden. |

### 4.2 Is per-user fine-tuning economically viable? (Med — arithmetic + judgement; quality claims belong to track 04)

**Option A — per-user Nova Micro/Lite SFT on Bedrock (no GPUs to run).**

- Training: say 3k–5k exemplar pairs × ~800 tokens × 2 epochs ≈ 5–8M tokens → **$5–8 (Micro) / $10–16 (Lite) / $19–30 (Nova 2 Lite)** per training run.
- Monthly refresh: the same again per month, or ~$1–3 with incremental data.
- Storage: **$1.95 per user-month**.

**Total ≈ $3–10 per user-month.** That is affordable. But:

1. Nova Micro/Lite are **much weaker writers than Sonnet 5.5**. Style fidelity improves, but judgment, thread understanding and instruction-following regress.
2. You must manage **thousands of custom models**. Per-account custom-model quotas were **not verified**, and there is training queue latency.
3. Fine-tuned weights **memorise PII and confidential content** and are hard to delete for DPDP/GDPR erasure. You would retrain on every erasure request.
4. Training is **us-east-1 only**, so it is not an India-resident option.

**Option B — shared base model + per-user LoRA on SageMaker or EKS.**

- One g6e.xlarge-class GPU (~$1.9/h EC2-equivalent, ≈ $1,360/month always-on) serving an 8B–32B model.
- With vLLM multi-LoRA it can serve a few hundred active users with a sub-second TTFT target, depending on concurrency (**Low** — must be load-tested).
- Two GPUs per Region for HA ≈ $2.7k/month. At 1,000 users ≈ **$3–5 per user-month for serving**, plus training (~$0.50–2 per user-month on spot GPUs), plus MLOps headcount.
- Breaks even against prompting only if the small model replaces Sonnet for most drafts. Quality risk as in Option A.

**Option C — Bedrock CMI per user.** Merged weights only, so every user is a separate model.

- One CMU for an always-on copy ≈ $0.05718 × 60 × 24 × 30 ≈ **$2,470 per month per user model**. Scale-to-zero adds cold starts per user.
- **Not viable** for per-user personas. It is viable only for one shared fine-tuned model per product tier.

**Option D — retrieval + prompting (style card + recipient-specific exemplars + thread), cached.**

- **≈ $0.01–0.04 per draft on Sonnet 5.5** (see §8).
- Instant updates, trivially erasable (delete vectors + style card), works in-Region, uses the best writer.

**Verdict (Med):**

- **Do not fine-tune per user in v1.** Build Option D, and capture the training data (accepted, edited and rejected drafts) so that a later step is cheap:
  1. a **global "email-style imitation" RFT/SFT model** (e.g. Nova 2 Lite RFT with a style-match grader, or a LoRA on Qwen3-32B) used for high-volume, low-stakes drafts; and/or
  2. **per-tenant** (not per-user) adapters for very large enterprises as a premium SKU.
- Revisit per-user adapters only if offline evals show a measurable style-fidelity gain that prompting cannot close.

## 5. Guardrails & PII services for the redaction pipeline (US + India precise)

### 5.1 The services at a glance (High unless marked)

| | **Bedrock Guardrails — sensitive-info filter** (`ApplyGuardrail`) | **Bedrock `InvokeGuardrailChecks`** (new, 2026) | **Amazon Comprehend PII** | **Amazon Macie** | **Transcribe PII redaction** |
|---|---|---|---|---|---|
| What it does | ML, context-dependent PII detection plus **custom regex**. Actions: **BLOCK / ANONYMIZE (`{NAME}`-style masks) / NONE** (detect), set separately for input and output. Works on arbitrary text without calling a model. | **Detect-only** scores (0–1) for content, prompt-attack and PII checks. No guardrail resource needed. | `DetectPiiEntities` (offsets + scores), `ContainsPiiEntities` (labels only), async `StartPiiEntitiesDetectionJob` with redaction (mask char or entity type). | S3 object discovery and classification jobs (managed + custom data identifiers, allow lists). Not an inline API. | PII redaction (`[PII]`) or identification in batch and streaming STT. |
| Languages | PII filter: **English, Hindi**, Arabic, Chinese, Dutch, Finnish, French, German, Italian, Japanese, Korean, Norwegian, Polish, Portuguese, Spanish, Swedish, Vietnamese ("optimized and supported") | Same safeguards | **English and Spanish only** | Mostly keyword-proximity, Latin script | Batch PII: en-US, **en-IN**, en-GB, en-AU, … (no hi-IN listed) |
| US-specific native types | `US_SOCIAL_SECURITY_NUMBER`, `US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER`, `US_PASSPORT_NUMBER`, `US_BANK_ACCOUNT_NUMBER`, `US_BANK_ROUTING_NUMBER`, plus generic `DRIVER_ID` | as Guardrails | `SSN`, `US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER`, `PASSPORT_NUMBER` (US), `BANK_ACCOUNT_NUMBER` (US), `BANK_ROUTING` (US), `DRIVER_ID` | `USA_SOCIAL_SECURITY_NUMBER`, `USA_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER`, `USA_PASSPORT_NUMBER`, `DRIVERS_LICENSE` (US), `BANK_ACCOUNT_NUMBER` (US/CA), `PHONE_NUMBER` (US/CA), `ADDRESS`, PHI: `USA_MEDICARE_BENEFICIARY_IDENTIFIER`, `USA_HEALTH_INSURANCE_CLAIM_NUMBER`, `USA_NATIONAL_PROVIDER_IDENTIFIER`, `US_DRUG_ENFORCEMENT_AGENCY_NUMBER`, `USA_NATIONAL_DRUG_CODE`, `USA_HEALTHCARE_PROCEDURE_CODE`, `MEDICAL_DEVICE_UDI` | `SSN`, `US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER`, `PASSPORT_NUMBER`, `BANK_ACCOUNT_NUMBER`, `BANK_ROUTING`, `DRIVER_ID` |
| **India-specific native types** | **None** | **None** | **`IN_AADHAAR`, `IN_PERMANENT_ACCOUNT_NUMBER` (PAN), `IN_VOTER_NUMBER` (EPIC), `IN_NREGA`** | **`INDIA_AADHAAR_NUMBER`, `INDIA_PERMANENT_ACCOUNT_NUMBER`, `INDIA_DRIVERS_LICENSE`** | **None** |
| Generic types | NAME, ADDRESS, AGE, EMAIL, PHONE, USERNAME, PASSWORD, DRIVER_ID, LICENSE_PLATE, VIN, card number/CVV/expiry, PIN, IBAN, SWIFT, IP, MAC, URL, AWS keys (+ CA/UK types) | — | Similar universal list + DATE_TIME (+ CA/UK) | Credentials (AWS/GCP/Stripe keys, private keys, JWT, cookies), card data, names (Latin), addresses, GPS, … | Similar universal list |
| Price (us-east-1) | **$0.10 per 1k text units** (PII ML); **regex and word filters free**; content/denied-topic filters $0.15 per 1k TU; contextual grounding $0.10; Automated Reasoning $0.17. A text unit is ≤1,000 characters (**Med** — AWS pricing-page definition, not re-fetched) | Content check $0.07, prompt-attack check $0.08, sensitive-info check $0.10 per 1k TU | `DetectPiiEntities` **$0.0001 per unit** (unit = 100 chars, 3-unit minimum per request — **Med**, standard Comprehend unit) for the first 10M units/month, $0.00005 for 10–50M, $0.000025 for 50–100M, $0.000005 above 100M. `ContainsPiiEntities` **$0.000002/unit** (tiers to $0.0000001). Custom entity recognizer: training $0.000833/s (= $3/h), $0.50/model-month, async inference $0.0005/unit. | **$1.00/GB** scanned (first 1 GB/month free; $0.50/GB above 50 TB; $0.25 above 500 TB), $0.10/bucket-month inventory, $0.01 per 100k objects monitored | Transcribe add-on (STT track) |
| us-east-1 / us-west-2 | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ | ✓ / ✓ |
| **ap-south-1 Mumbai** | ✓ (same prices) | **✗** (not in the 7 launch Regions) | ✓ (same prices) | ✓ | ✓ (batch PII listed for Mumbai) |
| **ap-south-2 Hyderabad** | ✓ (same prices) | ✗ | **✗** (no price list for ap-south-2) | **✗** | ✗ (no Transcribe price list) |

**Notes on Guardrails behaviour that matter for a redaction engine:**

- **ApplyGuardrail returns masked text and the matches.** The trace `match` field contains the original PII value by design. Never log the raw response.
- Masking applies only to prompts and responses. **Model invocation logs keep the original input**, so use CloudWatch Logs data protection if invocation logging is on.
- The PII filter **does not inspect tool-call arguments or tool results**. Redaction must happen *before* content enters the agent loop.
- Regex limits: pattern 1–500 characters, **no lookaround**, actions per regex. Detection is probabilistic and context-dependent; AWS advises against sending isolated short strings.
- **Safeguard tiers.** The **Standard tier** (content filters, prompt attack, denied topics with 80+ languages) **requires cross-Region guardrail profiles**. From Mumbai the `apac.guardrail.v1:0` profile routes to **Mumbai, Osaka, Seoul, Singapore, Sydney, Tokyo**. There is **no India-only guardrail profile**.
  - For India-resident tenants, use the **Classic tier** (English/French/Spanish only) for content/topic filters, or skip them.
  - The **sensitive-information filter is not a tiered policy**, so PII redaction runs on the Classic path. We did not find a statement that it leaves the Region (**Med**).
- `InvokeGuardrailChecks` is only in us-east-1/2, us-west-2, eu-west-2, eu-north-1, ap-northeast-1 and ap-southeast-2. **Not India.**
- Comprehend: topic modeling, event detection and prompt-safety classification are closed to new customers. **PII detection is unaffected** (AWS availability-change notice).
- **Comprehend Medical (`DetectPHI`)** is priced at **$0.0014 per unit** for the first 1M units/month, then $0.0005 (1–2M) and $0.00025 (>2M). That is **14× Comprehend PII** at tier 1.
  - Regions (price list): us-east-1/2, us-west-2, ca-central-1, eu-west-1/2, ap-southeast-2, GovCloud. **Not available in India.**
  - Use it only for US healthcare tenants, on content already flagged by L2 as health-related. Not in the default pipeline.

### 5.2 What needs custom detection for a US + India "precise" Phase-1 engine (Med — formats from public specifications; validate with compliance)

| Identifier | Native coverage | Recommended Phase-1 detector |
|---|---|---|
| **US SSN** | Guardrails, Comprehend, Macie, Transcribe | Native ML **plus** a regex with area/group/serial validity rules (no 000/666/9xx area, no 00 group, no 0000 serial) to boost recall on bare numbers. |
| **US ITIN** | Guardrails, Comprehend, Macie, Transcribe | Native + regex `9\d{2}-?[78]\d-?\d{4}` style. |
| **US passport** | Guardrails, Comprehend (`PASSPORT_NUMBER`), Macie | Native; add keyword-proximity regex. |
| **US driver's licence** | Generic `DRIVER_ID` (Guardrails, Comprehend); Macie `DRIVERS_LICENSE` (US) | Native generic + keyword proximity (state formats vary widely). |
| **US bank account / ABA routing** | Guardrails (`US_BANK_*`), Comprehend (`BANK_*`), Macie (account only) | Native + **ABA checksum** validation on 9-digit routing candidates. |
| **US EIN** | **None** in any service | Regex `\b\d{2}-\d{7}\b` + keyword ("EIN", "Tax ID"). |
| US Medicare MBI / NPI / DEA (PHI, if healthcare tenants) | **Macie only** | Regex/validators (NPI uses Luhn with the 80840 prefix). |
| **Aadhaar** (12 digits, often `XXXX XXXX XXXX`) | Comprehend `IN_AADHAAR`, Macie `INDIA_AADHAAR_NUMBER` | Comprehend or regex **+ Verhoeff checksum**; first digit 2–9. Also mask VIDs (16-digit virtual IDs) via regex. |
| **PAN** (`AAAAA9999A`) | Comprehend `IN_PERMANENT_ACCOUNT_NUMBER`, Macie | Regex `[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]` (4th char = holder type). |
| **Voter ID / EPIC** (3 letters + 7 digits) | Comprehend `IN_VOTER_NUMBER` only | Regex `[A-Z]{3}\d{7}` + keyword. |
| **NREGA job card** | Comprehend `IN_NREGA` only | Rarely relevant in enterprise mail; keep Comprehend/regex. |
| **Indian passport** (letter + 7 digits) | **None India-specific** (Transcribe generic `PASSPORT_NUMBER`; Comprehend's is US-only) | Regex `[A-Z][1-9]\d\s?\d{4}[1-9]` + keyword "passport". |
| **Indian driving licence** (state code + RTO + year + serial) | Macie `INDIA_DRIVERS_LICENSE`; generic `DRIVER_ID` elsewhere | Regex `[A-Z]{2}[-\s]?\d{2}[-\s]?(19|20)\d{2}\d{7}` + keyword. |
| **GSTIN** (15 chars: state code + PAN + entity + `Z` + checksum) | **None** | Regex `\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]` + mod-36 checksum. A GSTIN embeds a PAN, so mask the whole string. |
| **UPI ID / VPA** (`name@okhdfcbank`) | **None** (email detectors may miss them because there is no TLD) | Regex `[\w.\-]{2,256}@[a-zA-Z]{2,64}` restricted to a maintained allow-list of PSP handles. |
| **IFSC** (`AAAA0XXXXXX`) | **None** | Regex `[A-Z]{4}0[A-Z0-9]{6}`. A bank-branch code is not personal on its own, but it is personal when paired with an account number. |
| **Indian bank account** (9–18 digits) | **None** India-specific | Keyword proximity ("A/c", "account no") + digit-length rule. |
| Indian mobile (`+91 [6-9]XXXXXXXXX`) | Generic `PHONE` (Guardrails/Comprehend) | Native + regex for robustness. |
| ABHA health ID (14 digits), CIN, TAN, ration card | **None** | Regex + keyword. Lower priority. |
| **Company-confidential** (deal codenames, customer lists, financials, unreleased product names) | **None** | Tenant-admin dictionaries + regex (free in Guardrails), plus an **LLM classifier pass** (§5.3). Optionally a Comprehend custom entity recognizer per tenant (training $3/h, $0.50 per model-month, $0.0005/unit async). |

### 5.3 Recommended multi-level redaction pipeline and cost per user (Med — arithmetic on list prices; assumptions stated)

**Assumptions:** 150k messages per user backfill. Average 250 tokens ≈ **1,000–1,200 characters per message** after stripping quoted history and signatures (≈ 180M characters per user). Ongoing volume ≈ 60 new sent or chat messages per workday (~1,300/month). Transcripts: ~50k tokens/day ≈ 200k characters/day (see §8).

| Level | Engine | Purpose | Backfill $/user (150k msgs) | Ongoing $/user/month |
|---|---|---|---|---|
| L0 | **Deterministic validators** in our Lambda/Fargate: regex + checksums for every US/India ID in §5.2, tenant dictionaries | Highest-precision structured IDs; free; runs in-Region | ≈ $0 (compute only) | ≈ $0 |
| L1 | **Bedrock Guardrails sensitive-info filter** via `ApplyGuardrail` (ML PII: names, addresses, phones, emails, US IDs; Hindi support) + regex (free) | Contextual PII recall | ~1.2 TU/msg avg (1,000–1,200 chars; bills ≥1 TU per call) × 150k ≈ 180k–225k TU × $0.10/1k ≈ **$18–23**. Concatenating several messages per call at ≤1,000 chars per text unit sits near the low end. | ≈ $0.20 (mail) + ≈ $0.60 (transcripts at ~6M chars/month) |
| L1-alt | **Comprehend `DetectPiiEntities`** | Adds **Aadhaar/PAN/EPIC/NREGA** ML detection | 1.8M units × $0.0001 = **$180** at tier-1 prices. At account-level volume (e.g. 100 users backfilling per month = 180M units) the blended rate is ≈ $0.000026/unit ≈ **$46/user**. | ≈ $1.30 + transcripts ≈ $6 at tier-1 |
| L1-screen | **Comprehend `ContainsPiiEntities`** pre-screen, then `DetectPii` only on flagged messages | Cost control if Comprehend is required | 1.8M × $0.000002 = **$3.60**, plus DetectPii on the flagged share (e.g. 25% → $45 at tier 1) | small |
| L2 | **LLM contextual classifier** (company-confidential, third-party personal data, legal/HR/health topics). Runs in the **same pass as backfill labeling** (§8, item 2). | Things no NER detects | Incremental ≈ **$1–3** on gpt-oss-20b / Nova Micro batch; ≈ **$20–35** on Haiku 4.5 batch | ≈ $0.05–0.50 |
| L3 | **Macie** scheduled discovery on the raw S3 store (sampled) | Audit and assurance ("prove nothing leaked into the clear tier") | Raw mail ≈ 0.5–1 GB/user → **$0.50–1** for a full scan; sampling 10% ≈ $0.05–0.10 | ≈ $0.01–0.05 |

**Recommendation (Med):**

- **Standard path:** L0 (deterministic US + India validators) + L1 (Guardrails `ApplyGuardrail`, sensitive-info + regex only, Classic path, in-Region in us-east-1/ap-south-1) + L2 (LLM pass folded into labeling) + L3 (Macie sampling). That is **≈ $20–27 per user one-off** and **≈ $1/user/month** ongoing.
- **India tenants:** add Comprehend only as a **second opinion on messages that L0 flags as India-ID-bearing or that the L2 classifier marks high-risk**, not on every message.
- **Why not Comprehend everywhere:**
  - It is the most expensive per character at small scale ($0.0001 per 100 chars vs $0.0001 per 1,000 chars for Guardrails).
  - It is **English/Spanish-only**, while Guardrails' PII filter covers Hindi.
  - It is **absent from Hyderabad**.
  - Its India types are narrow (no passport, GSTIN, UPI or IFSC), so L0 regex is needed anyway.
- **Recall:** no service publishes per-entity precision/recall. **Build a labelled US/India test set** (synthetic plus consented real samples) in month 1 and measure recall per entity per engine before choosing. Treat the table above as cost guidance, not a quality verdict.
- **Order of operations:** redact **before** embedding, before AgentCore Memory, and before any LLM call that leaves the Region (Global CRIS). Store the reversible token map (e.g. `{NAME_3}` ↔ value) encrypted per tenant so the drafting agent can **re-hydrate** names locally after generation. Persona style must not be lost: the model should see `{PERSON_1}`, not a blank. Coordinate with track 09 (threat model and redaction design).

## 6. Knowledge bases, vector stores, embeddings, rerank, Data Automation

### 6.1 Vector store options (High for options/limits; Low where marked)

Bedrock Knowledge Bases supports these vector stores (KB setup doc, Oct 2026): **Amazon S3 Vectors, OpenSearch Serverless, OpenSearch Managed Clusters, Aurora PostgreSQL (pgvector), Neptune Analytics (GraphRAG), Pinecone, Redis Enterprise Cloud, MongoDB Atlas**.

- Only the OpenSearch options support binary embeddings.
- OpenSearch *managed* domains must be **public-access** to work with KBs ("domains that are behind a VPC are not supported").
- Aurora metadata filtering needs pgvector ≥ 0.8 iterative scans to avoid under-filled results.
- The new **AgentCore Managed Knowledge Base** (fully managed, $5/GB-month storage + $0.001 per query) is a separate option (§1.8).

| Store | Fit for PersonaAgent | Isolation model | Cost signal |
|---|---|---|---|
| **S3 Vectors** | **Primary store for per-user persona exemplars and transcript chunks.** Massive scale at low cost; sub-second (not single-digit-ms) queries. AWS: "best suited for infrequent query workloads". | Limits: **10,000 vector buckets per Region**, **10,000 indexes per bucket**, **2B vectors per index**, 1–4,096 dims, 2 KB filterable metadata (40 KB total, 50 keys), 1,000 write requests/s and 2,500 vectors/s per index, top-K ≤ 10,000. This allows a **bucket per tenant (own KMS key) and an index per user** for hard isolation without relying on filters. | us-east-1: **$0.06/GB-month** storage, **$0.20/GB** PUT, **$0.0025 per 1k queries** (+ $0.004/TB processed tier 1, $0.01/GB returned). Mumbai: $0.066/GB-month, $0.219/GB PUT, $0.0027 per 1k queries. |
| **OpenSearch Serverless / managed** | Hot hybrid search (BM25 + vector) for the drafting path if S3 Vectors latency is too high; text search over the raw store. | Per-tenant collections/indexes + document-level security. | OCU-based (**Low** — not re-verified this run; historically $0.24 per OCU-hour with a non-zero minimum footprint). A fixed monthly floor even at zero traffic. |
| **Aurora PostgreSQL + pgvector** | Co-locate vectors with relational persona/recipient tables (SQL DB required anyway). Row-level security per tenant. Good up to tens of millions of vectors per cluster. | RLS + schema/tenant column. | Aurora Serverless v2 ACU pricing (DB track). |
| **Neptune Analytics (GraphRAG)** | Optional relationship graph (person ↔ org ↔ thread ↔ topic). Bedrock KB GraphRAG builds entity graphs automatically. | Graph per tenant (m-NCU sizing). | Capacity-based; justify later (track 04). |

**Per-tenant isolation recommendation (Med):**

- **S3 Vectors:** one vector bucket per tenant with an SSE-KMS customer-managed key per tenant (supported at bucket creation; immutable), and one index per user × corpus (`mail`, `chat`, `transcript`).
- Retrieval code passes `{tenant, user}` derived **server-side** from the validated JWT, never from the model.
- Use Bedrock KB only where its managed chunking and sync add value (org documents). For mailbox-derived exemplars we control chunking (message, thread, recipient, situation), so call `PutVectors` / `QueryVectors` directly.

### 6.2 Embeddings (High — price list)

| Model | Price per 1M tokens | Dims | India |
|---|---|---|---|
| **Titan Text Embeddings V2** | **$0.02** on-demand, **$0.01** batch (us-east-1) | 256 / 512 / 1,024 | **In-Region in Mumbai ($0.024) and Hyderabad ($0.027)**; batch not listed for ap-south-1 |
| Cohere Embed v4 | $0.12 | multimodal | Mumbai/Hyderabad: **Global only** |
| Amazon Nova Multimodal Embeddings | $0.135 (text), batch $0.0675; audio $0.00014/s; image $0.00006 | multimodal | us-east-1 only |

**Per-user backfill embedding cost:** 150k messages × ~250 tokens = 37.5M tokens → **$0.75** (Titan V2 on-demand) / **$0.38** (batch) / $0.90 (Mumbai). Cohere v4 would cost $4.50.

**Storage at 1,024-d float32:** ~4 KB/vector, plus ~1 KB metadata. That is ≈ 0.75 GB per 150k vectors → **≈ $0.045/user-month** on S3 Vectors (≈ half at 512-d), plus a **≈ $0.15** one-off PUT.

### 6.3 Rerank (High)

| Model | Price | Regions |
|---|---|---|
| **Cohere Rerank 3.5** | **$2.00 per 1,000 queries** ($0.002 per "search unit") | In-Region us-east-1, us-west-2, eu-central-1 (+ others); **not India** |
| **Amazon Rerank 1.0** | **$1.00 per 1,000 search units** | us-west-2 in the price list (plus a few other Regions; **not us-east-1, not India**) |

Rerank becomes a **visible per-user line item**: 1,000–2,000 reranked queries per user per month ≈ $1–4. Use it selectively, for memory Q&A rather than every draft. For India-resident tenants, fall back to hybrid scoring or an LLM-judged rerank inside the same Haiku `in.` call.

### 6.4 Bedrock Data Automation (BDA) (High for price; Med for fit)

Prices (us-east-1 and Mumbai identical):

- Audio: **$0.006/min** standard, $0.009/min custom.
- Documents: $0.010/page standard, $0.040/page custom.
- Images: $0.003 each; video $0.050/min.

BDA has built-in sensitive-data detection/redaction options. Its audio pricing (≈ $0.36 per hour) is in the same range as STT, so it is a candidate for **attachments and recorded audio summarisation**. Live STT vendor choice is track 05.

**Not recommended** as the primary transcript pipeline. We need diarization quality, streaming and per-utterance timestamps controlled by our own stack.

## 7. Data privacy posture — Bedrock vs AgentCore vs Claude Platform on AWS

### 7.1 Amazon Bedrock (High — Bedrock data-protection and abuse-detection docs)

- **Zero operator access and zero data retention by default.** "Amazon Bedrock uses a zero operator access (ZOA) data security model … no operators of the service can access model input or output … by default, Amazon Bedrock does not store model inputs or outputs."
- **Model providers have no access.** Models run in AWS-owned **Model Deployment Accounts**. "Model providers don't have any access to those accounts … they don't have access to Amazon Bedrock logs or to customer prompts and completions." Anthropic's Bedrock doc says the same: zero operator access, Anthropic personnel cannot access the inference infrastructure.
- **Exceptions (abuse detection):**
  - **Claude Fable 5 / Fable 5.1:** *all traffic retained up to 30 days* for automated offline abuse detection; classifier-flagged traffic may get *human review by AWS*. ZDR through 31 Dec 2026 for eligible "Enterprise Frontier Safeguards" customers.
  - Several OpenAI GPT-5.x/6 models: flagged traffic retained up to 30 days.
  - **Opus 5.5, Sonnet 5.5 and Haiku 4.5 are not on the retention list**, so ZDR applies by default.
  - With CRIS, any retained data is stored in the *destination* Region.
- **Training.** Bedrock does not use prompts to train models. Customer prompts and completions are not shared with providers (above). Fine-tuning data stays in your account.
- **Logging.** Model invocation logging is **opt-in** (CloudWatch/S3). It logs **unmasked** inputs even when Guardrails masks them, so use CloudWatch Logs data-protection policies or keep logging off for content.
- **Network.** VPC endpoints / **PrivateLink** for Bedrock runtime. AgentCore supports VPC + PrivateLink for all services since GA.
- **Compliance.** Bedrock's compliance page now defers to "AWS services in scope". Bedrock has long been in scope for SOC, ISO, PCI, HIPAA-eligible and FedRAMP (Moderate/High in specific Regions); **we did not re-verify the per-program list in this run (Med)**. Anthropic's CPAWS page itself says regulated buyers needing *FedRAMP High, IL4/IL5 or HIPAA-ready* should use Bedrock.

### 7.2 AgentCore (High — AgentCore compliance + data-protection docs)

- **Compliance:** "HIPAA eligible and FedRAMP (Class C and Class D), SOC 2 and ISO (27001, 27017, 27018, 27701, 22301, 20000-1, 9001) and CSA STAR compliant". SOC 1/2/3 since Jun 2026. Internal assessment done for C5, HITRUST, IRAP, PCI, etc., with third-party audit pending.
- **What it stores:**
  - Memory: events and records (KMS: AWS-owned or customer-managed).
  - Gateway: tool definitions and metadata in DynamoDB/S3; customer content "is not used to provide and maintain the AgentCore Gateway service".
  - Identity: token vault, KMS-encrypted, CMK supported.
  - Observability: traces in **your** CloudWatch. **Prompts can end up in spans/logs if your agent framework logs them**, so redact or sample.
- **Residency:** see the cross-Region trap in §1.9 (Memory built-ins, Policy NL authoring and Evaluations use geo/global CRIS).

### 7.3 Claude Platform on AWS (CPAWS) (High — Anthropic CPAWS doc and pricing doc, Oct 2026)

- **Operator and processor:** **Anthropic.** AWS handles only billing and identity metadata. "Customers … are subject to Anthropic's data use terms."
  - Since workspaces created **after 18 Sep 2026**, Anthropic runs inference and stores workspace content *on AWS infrastructure*. Earlier workspaces "might process requests, store data, and run inference outside AWS".
  - Per the AWS launch blog (GA 11 May 2026), requests are processed "outside the AWS security boundary".
- **Retention:** same as the first-party API. **ZDR available on request** (opt-in, per organization).
- **Not available on CPAWS:** **HIPAA-ready program**, OAuth auth, fast mode, OpenAI-compatible endpoints.
- **Available on CPAWS:** CMEK with AWS KMS, PrivateLink, CloudTrail.
- **Residency:** `inference_geo` = **`us` (1.1× price) or `global`** only. The workspace's AWS Region "does not pin where model inference runs". **No India or EU-pinned option** was listed on the CPAWS page.
- **Features:** same-day API parity — **Message Batches (50% off), Files, MCP connector, Skills, code execution, web search/fetch, Managed Agents** ($0.08 per session-hour runtime plus tokens; autonomous sessions re-authenticate after 6 h). Separate capacity pool from Bedrock, so it **can serve as a failover path**.
- **Pricing:** billed in Claude Consumption Units ($0.01 per CCU) at **standard Anthropic list prices** via AWS Marketplace.

### 7.4 Which surface for which PersonaAgent workload (Med — recommendation)

| Workload | Recommended surface | Why |
|---|---|---|
| **Interactive drafting** (US tenants) | **Bedrock**, Sonnet 5.5 via **`us.` geo profile** (or Global for non-regulated SMB) on `bedrock-runtime` | AWS as sole processor, ZOA/ZDR default, US-only routing, inline Guardrails possible, same list price (+10% for geo). |
| **Interactive drafting** (India tenants) | **Bedrock Haiku 4.5 via `in.` profile** (India-resident). Optional tenant-admin opt-in to Sonnet 5.5 Global. | Only in-India Claude path today. |
| **Memory Q&A** | Same as drafting, per tenant Region | Same reasoning; retrieval stays in-Region. |
| **Backfill labeling and extraction** (150k msgs/user), **US** | **Bedrock batch** with Haiku 4.5 ($0.50/$2.50) or gpt-oss-20b / Nova Micro batch. Optionally **CPAWS Message Batches** with Sonnet 5.5 ($1/$5, `inference_geo: us` +10%) *only if* quality needs Sonnet and the tenant accepts Anthropic as processor with ZDR enabled. | Bedrock batch does not cover Sonnet/Opus 5.5 today. CPAWS fills that gap at 50% off but changes the processor. |
| **Backfill**, **India** | Bedrock Haiku 4.5 batch via `in.` (+10%: $0.55/$2.75) or in-Region gpt-oss-20b / Qwen3-32B batch in Mumbai | Keeps processing in India. |
| **Daily transcript summarisation** | Bedrock (Haiku 4.5 for chunk summaries; Sonnet 5.5 for the daily digest, US). India: Haiku `in.` | Same as drafting. |
| **Agentic long-running jobs** (e.g. "rebuild persona model", eval runs) | AgentCore Runtime async (8 h) or Step Functions + Bedrock; **CPAWS Managed Agents only for non-customer-content internal tooling** | Keep customer content inside the AWS processor boundary. |

**Bottom line:** default every customer-content path to **Bedrock**. Treat **CPAWS as an opt-in accelerator** for (a) 50%-off Sonnet/Opus 5.5 batch, (b) features Bedrock lacks (Files, Skills, MCP connector, server tools), and (c) a failover capacity pool. Use it only for tenants who accept Anthropic as sub-processor, and with ZDR enabled.

## 8. LLM & platform cost model (per active user per month)

All numbers in this section are **Med** confidence: arithmetic on verified list prices, under the assumptions below. Prices are global Bedrock list prices, which equal Anthropic 1P. **US/EU geo or India `in.` routing adds 10%**, applied where the configuration says "geo". A Python version of the model is kept in the research scratchpad. Re-run it when prices change.

### 8.1 Assumptions

| Parameter | Low | Typical | Heavy | Source |
|---|---|---|---|---|
| Workdays per month | 22 | 22 | 22 | assumption |
| Drafts per workday | 15 | 22 | 30 | brief |
| Input tokens per draft (style card + exemplars + thread) | 3,000 | 5,500 | 8,000 | brief |
| Visible output tokens per draft | 300 | 450 | 600 | brief |
| Thinking/progress overhead on output | ×1.3 | ×1.3 | ×1.3 | **assumption** (Sonnet/Opus 5.5 can't fully disable thinking; use low effort) |
| Prompt caching | 60% of input cacheable; 5-min TTL; 50% hit rate | same | same | assumption (bursty drafting) |
| Memory Q&A queries per day | 5 | 10 | 20 | brief |
| Q&A tokens per query (2-turn tool loop) | 12k in, 600 out | same | same | assumption |
| Transcript tokens per day (work-only recorder) | 40k | 50k | 60k | brief |
| Transcript chunking overhead | input ×1.5 (instructions), output 15% of input | same | same | assumption |
| Daily digest | 8k in, 1.5k out | same | same | assumption |
| Backfill | 150k msgs × (250 + 50 amortized instruction) tokens in, 60 tokens out; packed 10 per request | — | — | brief + assumption |

**Formulas:**

- **Drafting:** `n = drafts/day × 22`.
  - Uncached: `cost = n × (in × P_in + out × 1.3 × P_out) / 1e6`.
  - Cached: input becomes `0.4·in·P_in + 0.6·in·(h·P_read + (1−h)·P_write5m)`.
  - **Haiku 4.5's 4,096-token cache minimum means "low"/"typical" Haiku prompts don't cache.**
- **Batch:** `cost = 45M × P_in_batch + 9M × P_out_batch` per user backfill.
- **Q&A:** `q = queries/day × 22`, `cost = q × (12k × P_in + 780 × P_out) / 1e6`.

### 8.2 Component costs

**(1) Persona drafting, $ per user-month (global list; ×1.1 for geo).**

| Model | Low (no cache / cached) | Typical (no cache / cached) | Heavy (no cache / cached) | Per draft (typical, cached) |
|---|---|---|---|---|
| Haiku 4.5 | $1.63 / n/a* | $4.08 / n/a* | $7.85 / $6.82 | ≈ $0.008 |
| **Sonnet 5.5** | $3.27 / $2.88 | **$8.16 / $7.12** | $15.71 / $13.65 | **≈ $0.015** |
| Opus 5.5 | $6.53 / $5.70 | $16.31 / $14.07 | $31.42 / $26.98 | ≈ $0.029 |

\*Below Haiku's 4,096-token cache minimum. A 1-h TTL with an 80% hit rate trims Sonnet typical to $6.49.

Caching saves only about 10–20% here, because **output tokens dominate** (450 × 1.3 × $10/M ≈ $0.006 of the ~$0.015 per Sonnet draft) and per-thread content is uncacheable. **Output discipline and model routing matter more than caching.**

**(2) One-time backfill labeling and classification (150k messages).**

| Model | Cost per user |
|---|---|
| Nova Micro batch | **$1.42** |
| **gpt-oss-20b batch** | **$2.92** |
| gpt-oss-120b / Qwen3-32B batch | $6.07 |
| Nova 2 Lite batch | $18.00 |
| Haiku 4.5 batch | $45.00 (India `in.` $49.50) |
| Sonnet 5.5 via CPAWS Message Batches | $90.00 ($99 with `inference_geo: us`) |

Sonnet 5.5 is not available in Bedrock batch. Plan for **≈ $3–6/user** with an open-weight model, plus a **Haiku/Sonnet re-check on the ~5–10% of messages the cheap model is unsure about** (≈ +$2–9).

**(3) Daily transcript extraction and summarisation, per month.**

| Model | Low | Typical | Heavy |
|---|---|---|---|
| Haiku 4.5 chunking | $1.98 | $2.48 | $2.97 |
| gpt-oss-120b chunking | $0.28 | $0.35 | $0.42 |
| Sonnet 5.5 daily digest (all tiers) | $0.78 | $0.78 | $0.78 |

**(4) Memory Q&A, per month.**

| Model | Low | Typical | Heavy |
|---|---|---|---|
| Sonnet 5.5 | $3.50 | **$7.00** | $13.99 |
| Haiku 4.5 | $1.75 | $3.50 | $7.00 |

**(5) Embeddings, rerank and vectors.**

- Ongoing embeddings ≈ $0.03–0.05/month (Titan V2).
- S3 Vectors storage ≈ $0.05/month.
- Rerank (Cohere 3.5, $2 per 1k) on Q&A only ≈ $0.22–0.88.
- **Total ≈ $0.40 / $0.55 / $1.10.**
- Backfill one-off: embeddings $0.75 + PUT $0.15.

**(6) Guardrails / PII.**

- Ongoing: mail, transcripts and draft outputs at $0.10 per 1k text units ≈ **$0.70 / $0.80 / $1.00**.
- Backfill one-off ≈ **$18–23** (Guardrails). Comprehend everywhere would be $46–180.

**(7) AgentCore** (Runtime v2 + Gateway + Policy + optional Memory + CloudWatch), **≈ $0.50 / $1.00 / $2.00** (Low–Med):

- Runtime ≈ $0.0003 per turn.
- Gateway $0.005 per 1k calls.
- Policy $0.025 per 1k authorizations.
- Memory LTM $0.75 per 1k records-month plus $0.50 per 1k retrievals, if used.
- CloudWatch traces/logs are the largest and least predictable item.

### 8.3 Totals per active user per month

Backfill one-off (≈ $24 standard, ≈ $66 with Haiku labeling) is amortised over 12 months.

| Configuration | Low | Typical | Heavy |
|---|---|---|---|
| **US recommended** — Sonnet 5.5 drafting + Q&A via `us.` geo (+10%); Haiku chunking + Sonnet digest; gpt-oss-20b labeling; Guardrails PII | **$13.65** | **$23.46** | **$40.63** |
| **US economy** — Haiku 4.5 drafting + Q&A (global); gpt-oss-120b chunking; Haiku digest | $7.65 | $12.66 | $20.73 |
| **US premium** — Opus 5.5 drafting; Sonnet Q&A (`us.` geo); Haiku labeling | $20.26 | $34.61 | $58.80 |
| **India-resident** — Haiku 4.5 `in.` for drafting/Q&A/digest; gpt-oss-120b in-Region chunking; no rerank | $7.73 | $13.03 | $21.20 |

**Breakdown, US recommended (typical):**

| Component | $/month |
|---|---|
| Drafting | 7.83 |
| Q&A | 7.70 |
| Transcripts | 3.58 |
| Retrieval | 0.55 |
| PII | 0.80 |
| AgentCore | 1.00 |
| Backfill/12 | 2.00 |

**Pricing implication (for the market/pricing track).** At a $30–40/seat/month list price, the US-recommended stack leaves roughly **25–55% gross margin** on LLM + AI-platform costs before storage, STT (track 05), Graph ingestion compute and support.

The levers, in order of impact:

1. **Route easy drafts to Haiku.** A 60/40 Haiku/Sonnet split cuts drafting cost about 30%.
2. **Cap Q&A depth.** Use one turn when retrieval suffices.
3. **Move chunk extraction to open-weight models.**
4. **Negotiate a Bedrock or Anthropic private offer.** Discounts do not transfer between Bedrock and CPAWS.
5. **Keep heavy users on fair-use limits.**

STT for the always-on recorder (≈ 3–4 h/day) is **not** in these totals. At typical managed-STT rates it can rival the LLM bill. See track 05.

## 9. Recommendations for PersonaAgent

**Architecture (MVP, 3–6 engineers, ~3 months):**

1. **Two regional cells from day 1:** `us-east-1` (US tenants) and `ap-south-1` (India tenants), from the same IaC (CDK; AgentCore constructs are stable since May 2026). Tenant → cell is pinned at onboarding. Backups stay in-cell. Hyderabad is DR-only for Runtime/Gateway/Identity, since it has no AgentCore Memory, harness, Comprehend, Macie or Transcribe.
2. **Model plan:**
   - **US cell:** Sonnet 5.5 via `us.` geo for drafting and Q&A; Haiku 4.5 for simple drafts and chunk extraction; Opus 5.5 only for an opt-in "best quality" mode.
   - **India cell:** **Haiku 4.5 via `in.anthropic.claude-haiku-4-5-20251001-v1:0`** (Mumbai + Hyderabad only) as the default. Sonnet 5.5 Global as a **tenant-admin opt-in** with explicit disclosure.
   - Watch the model cards monthly for an `in.` Sonnet 5.5 profile.
   - Build the **router** (model choice per request) from day 1. It is the main cost lever.
3. **Drafting path = workflow, not agent:** a warm ECS Fargate service does deterministic retrieval, then one streaming Bedrock call with cached prefix, then post-checks. Target p95 first-token ≤ 2.5 s. **Measure in week 1** (no published p95 for Sonnet 5.5 on Bedrock).
4. **AgentCore where it earns its keep:**
   - **Runtime** for the conversational assistant and memory Q&A.
   - **Identity** for Entra inbound JWT + **Microsoft OBO** to Graph, with one multi-tenant Entra app.
   - **Gateway** as the MCP tool front door with **per-tenant rate limits**.
   - **Policy** (Cedar) for tenant/user scoping and "never send mail without approval".
   - **Observability**.
   - **Skip built-in Memory strategies and built-in evaluators in the India cell** (they use APAC CRIS), or use overrides/custom evaluators with in-Region models.
5. **Data layer for AI:**
   - **S3 Vectors** with a bucket per tenant (own KMS CMK) and an index per user per corpus; Titan Text Embeddings V2 (in-Region in both cells).
   - Aurora for persona/recipient tables; optional OpenSearch for hot hybrid search.
   - Cohere Rerank 3.5 for US Q&A only.
6. **Pipelines:** Step Functions + Bedrock batch.
   - Backfill labeling on **gpt-oss-20b** (or Nova Micro) **batch**, with a Haiku re-check of uncertain items.
   - Daily transcript chunking on gpt-oss-120b / Haiku, plus a Sonnet (US) or Haiku (India) daily digest.
7. **Redaction (US + India precise):**
   - **L0** deterministic validators (SSN/ITIN/EIN/ABA + Aadhaar-Verhoeff/PAN/EPIC/passport/DL/GSTIN/UPI/IFSC).
   - **L1** Bedrock Guardrails `ApplyGuardrail` (sensitive-info + free regex, Classic path, in-Region).
   - **L2** LLM contextual classifier folded into labeling.
   - **L3** Macie sampling.
   - Comprehend only as a second opinion on India-ID-bearing or high-risk items (Mumbai only).
   - **Build a labelled US/India PII eval set before choosing thresholds.**
8. **Personalisation = retrieval + prompting.** No per-user fine-tuning in v1. Log accepted, edited and rejected drafts now for a later global/per-tenant RFT/SFT model.
9. **Claude Platform on AWS:** keep as an **opt-in accelerator and failover**, not the default.
   - Use it for 50%-off Sonnet/Opus 5.5 batch where Bedrock batch lacks those models, Files/Skills/MCP connector experiments, and internal tooling.
   - Requires Anthropic as sub-processor and **ZDR enabled**. Never for India-resident tenants.
10. **Commercials:**
    - Raise service quotas early: AgentCore new-session TPS, active sessions in Mumbai, Bedrock TPM/RPM per model per Region, Memory retrieval TPS if used.
    - Get a Bedrock private offer once you have usage history.
    - Tag everything with `tenant_id` (application inference profiles) for per-tenant cost attribution.

## 10. Risks & watch-outs

| Risk | Impact | Mitigation |
|---|---|---|
| **No in-India Sonnet/Opus 5.5 on Bedrock** (Global only from Mumbai/Hyderabad) | India quality ceiling = Haiku 4.5 if strict residency | Tenant opt-in to Global Sonnet; monitor for `in.` profiles; evaluate Opus 5 `in.` (exists, $5.50/$27.50) for premium India tenants |
| **AgentCore built-ins silently use CRIS** (Memory extraction, Policy NL authoring, Evaluations; Hyderabad → global) | Residency breach claims | Use overrides/custom evaluators; document per-feature routing in the DPA |
| **Guardrails Standard tier routes across APAC** (no India guardrail profile) | Same | Use Classic tier for content filters in India, or skip them; PII filter isn't tiered |
| **Bedrock batch lacks Sonnet/Opus 5.5** | Higher backfill cost or processor change (CPAWS) | Open-weight/Haiku batch; re-check pass; revisit monthly |
| **Pricing churn** (AgentCore Runtime v2 rates; Memory STM repriced 2026-10-06; committed baseline launching Oct 2026) | Budget drift | Re-run cost model quarterly; per-tenant metering via Gateway token limits + tags |
| **Quotas** (25 new sessions/s/account; 2,500 active sessions outside us-east-1/us-west-2; Memory `IngestData` 10 TPS fixed; retrieval 30 TPS) | Throttling at launch | Session reuse; request increases; don't push backfill through AgentCore Memory |
| **Entra token edge cases** (AgentCore inbound rejects tokens with custom claims; multi-tenant discovery URL unclear; refresh-token custody for offline sync) | Auth failures, offline-sync gaps | Week-1 spike; own KMS-encrypted refresh-token store for workers if needed |
| **Mantle endpoint gaps** (no Guardrails, KBs, structured outputs; Sonnet 5.5 Mantle Regions limited) | Integration rework | Use `bedrock-runtime` Converse/Invoke for production; Mantle only where Anthropic-native features are needed |
| **Haiku 4.5 4,096-token cache minimum** | Lost caching savings | Pad/standardise the persona prefix to ≥4,096 tokens, or accept no caching |
| **Observability leaks** (prompts in spans/logs; invocation logs unmasked) | Sensitive data at rest in CloudWatch | Log redaction, sampling, CloudWatch data-protection policies, short retention |
| **Fable 5/5.1 retention** (30-day retention + possible human review on Bedrock) | Contract conflicts | Don't use Fable for customer content |
| **Vendor velocity** (AgentCore shipped ~15 notable features in 2026) | Docs and behaviour change under you | Pin SDK versions; contract tests; a monthly "what changed" review |

## 11. Open questions / could not verify

1. **Practitioner sentiment on AgentCore in production** (Reddit/HN/Discord complaints): not swept, because the web-search budget was exhausted. Limitations listed are from AWS docs and release notes only.
2. **p50/p95 latency (TTFT, tokens/s)** for Sonnet 5.5 / Haiku 4.5 on Bedrock from us-east-1 and from ap-south-1 via Global CRIS: no published figures found. Measure.
3. **AgentCore Identity token-vault semantics** for Microsoft refresh tokens (rotation, expiry, revocation under Conditional Access), and multi-tenant Entra discovery for inbound auth.
4. **Guardrails text-unit definition** (≤1,000 characters per unit) is from prior AWS pricing pages; not re-fetched this run.
5. **Whether the Guardrails sensitive-information filter in Mumbai ever leaves the Region** (it is not a tiered policy; docs don't say it uses CRIS).
6. **Exact Mantle in-Region Regions** for Sonnet/Opus 5.5 (AWS model cards vs Anthropic doc differ), and the **planned date for Bedrock batch support** of Sonnet/Opus 5.5.
7. **Bedrock compliance program list** (FedRAMP level per Region, HIPAA eligibility of each new model). The Bedrock page now defers to "services in scope". AgentCore's list (HIPAA-eligible, FedRAMP, SOC, ISO, CSA STAR) *was* verified.
8. **Agent 365 / Entra Agent ID integration with AgentCore**: no AWS-side source found.
9. **OpenSearch Serverless current OCU price and minimums; SageMaker `ml.*` GPU prices**: not re-verified (EC2 equivalents from the AgentCore Instances fee table were used instead).
10. **Per-entity PII recall/precision** for Guardrails vs Comprehend vs Macie on US/Indian identifiers: no vendor benchmarks. Build our own test set.
11. **DPDP Rules interpretation** for cross-border LLM processing of enterprise email: legal track.
12. **Custom-model quotas** (number of fine-tuned Nova models per account) and CMI cold-start times: not documented in the pages read.

## 12. Sources

**AWS — AgentCore**

- AgentCore GA (What's New, 13 Oct 2025): https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available
- AgentCore pricing (fetched 2026-10-05): https://aws.amazon.com/bedrock/agentcore/pricing/
- AgentCore release notes: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/release-notes.html
- AgentCore quotas: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html
- AgentCore Regions: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html
- Runtime sessions: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html
- Runtime v2 blog (18 Sep 2026): https://aws.amazon.com/blogs/machine-learning/the-new-agentcore-runtime-elastic-optimized-and-consistently-fast-starts/
- June 2026 launches blog: https://aws.amazon.com/blogs/machine-learning/new-in-amazon-bedrock-agentcore-build-agents-with-broader-knowledge-and-continuous-learning/
- Harness GA: https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-bedrock-agentcore-harness-generally-available/
- Policy GA (Mar 2026): https://aws.amazon.com/about-aws/whats-new/2026/03/policy-amazon-bedrock-agentcore-generally-available/
- Evaluations GA: https://aws.amazon.com/about-aws/whats-new/2026/03/agentcore-evaluations-generally-available
- Identity — Microsoft: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-microsoft.html
- Identity — OBO: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/on-behalf-of-token-exchange.html
- Memory strategies: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html
- AgentCore cross-Region inference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/cross-region-inference.html
- AgentCore compliance: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/compliance-validation.html
- AgentCore data protection: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/data-protection.html

**AWS — Bedrock**

- AWS Price List API (bulk files used for all Bedrock/AgentCore/Comprehend/Macie/S3 Vectors prices, us-east-1, us-west-2, ap-south-1, ap-south-2; published 2026-09-11 → 2026-10-03): https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json (offers `AmazonBedrock`, `AmazonBedrockFoundationModels`, `AmazonBedrockService`, `AmazonBedrockAgentCore`, `comprehend`, `AmazonMacie`, `AmazonS3`, `transcribe`)
- Bedrock pricing page: https://aws.amazon.com/bedrock/pricing/
- Model cards (regional availability, inference profiles, caching, tiers):
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-5-5.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-5-5.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-5.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-titan-text-embeddings-v2.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-cohere-embed-v4.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-cohere-rerank-3-5.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-oss-20b.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-micro.html
  - https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-lite.html
- Geographic CRIS: https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html
- Inference profiles support: https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html
- Batch supported models: https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-supported.html
- Service tiers: https://docs.aws.amazon.com/bedrock/latest/userguide/service-tiers-inference.html
- Data protection: https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html
- Abuse detection (ZOA/ZDR, Fable retention): https://docs.aws.amazon.com/bedrock/latest/userguide/abuse-detection.html
- Fine-tuning supported models: https://docs.aws.amazon.com/bedrock/latest/userguide/custom-model-fine-tuning.html
- Nova RFT: https://docs.aws.amazon.com/bedrock/latest/userguide/rft-nova-models.html
- Open-weight fine-tuning via OpenAI APIs: https://docs.aws.amazon.com/bedrock/latest/userguide/fine-tuning-openai-apis.html
- Custom Model Import: https://docs.aws.amazon.com/bedrock/latest/userguide/model-customization-import-model.html
- CMI cost: https://docs.aws.amazon.com/bedrock/latest/userguide/import-model-calculate-cost.html
- KB vector stores: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html
- Opus 5.5 on AWS (22 Sep 2026): https://aws.amazon.com/blogs/machine-learning/claude-opus-5-5-is-now-available-on-aws/

**AWS — Guardrails & PII**

- Sensitive-info filters: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html
- Languages: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-supported-languages.html
- Tiers: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tiers.html
- Guardrail CRIS profiles: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-cross-region-support.html
- ApplyGuardrail: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html
- InvokeGuardrailChecks: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-invoke-guardrail-checks.html
- Charging model: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html
- Comprehend PII entity types: https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html
- Comprehend availability change: https://docs.aws.amazon.com/comprehend/latest/dg/comprehend-availability-change.html
- Macie managed data identifiers: https://docs.aws.amazon.com/macie/latest/user/mdis-reference-quick.html
- Transcribe PII redaction (batch): https://docs.aws.amazon.com/transcribe/latest/dg/pii-redaction-batch.html

**AWS — other**

- S3 Vectors limits: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html
- SageMaker adapter inference components: https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints-adapt.html

**Anthropic**

- Claude in Amazon Bedrock (Mantle, zero operator access, regions, 10% regional premium, quotas): https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock
- Claude Platform on AWS (operator, retention/ZDR, `inference_geo`, feature limits, CMEK, PrivateLink): https://platform.claude.com/docs/en/build-with-claude/claude-platform-on-aws
- Pricing (model prices, cache multipliers, batch, data-residency 1.1×, CPAWS CCU billing, Managed Agents $0.08 per session-hour): https://platform.claude.com/docs/en/about-claude/pricing.md
- AWS launch blog for CPAWS (GA 11 May 2026): https://aws.amazon.com/blogs/machine-learning/introducing-claude-platform-on-aws-anthropics-native-platform-through-your-aws-account/
