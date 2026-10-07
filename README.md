# PersonaAgent — Research & Strategy Pack (October 2026)

> **Status:** research phase complete (10 parallel research tracks, ~170k words with sources) and synthesised into a strategy, architecture, MVP plan, risk register and decisions log. **Next step:** founders confirm the recommended decisions (`docs/05-decisions-and-open-questions.md`), then MVP build starts.
> **Date:** 2026-10-06. **Founder decisions applied:** Microsoft 365 mid-market & enterprise buyers · US + India · 3–6 engineers, ~3-month MVP · work-only, company-governed recorder · Phase-1 redaction precise to US + Indian government regulation.
> *Working name only — "PersonaAgent" collides with an ACL 2026 research framework; rename before launch.*

---

## The product in two sentences
An assistant for client-facing teams in Microsoft 365 that **writes every email and Teams message exactly the way you would write it to that specific person** (your manager, your junior, a client, a vendor), and **remembers what you and your clients said** in email, chat, meetings and work conversations — so it can answer "what were the client's requirements in the 4 pm meeting?" and make sure promises are kept. It is governed tightly enough (US/India residency, precise redaction, consent-first capture, no training on customer data) that IT, security and legal teams say yes.

---

## Your questions, answered

| You asked | Answer (details in the linked doc) |
|---|---|
| **Should we build a frontend that shows all emails and Teams messages with an identical UI?** | **No.** A credible mail + chat client is 6–12+ engineer-months, M365 users won't switch, it multiplies breach exposure, and it fights Microsoft's UI churn. Live **inside** Outlook (add-in + optional drafts written straight into the user's Drafts folder, which covers mobile) and Teams (agent + "Draft reply" action). Our web app is the **control center and memory surface** — onboarding, persona studio, drafts queue, memory timeline, recordings, privacy center, tenant-admin and super-admin consoles — also embedded as a Teams tab. → `docs/02-solution-architecture.md` §3 |
| **Do we deploy an agent (AgentCore-style)?** | **Yes.** One backend, many thin surfaces. **Amazon Bedrock AgentCore** runs the conversational assistant and memory Q&A (Runtime, Identity with Microsoft on-behalf-of tokens, Gateway, Cedar Policy); drafting runs as a fast deterministic service on ECS Fargate. The same agent can appear inside **Microsoft 365 Copilot Chat** (no Copilot licence needed). → §9 |
| **Integrate in Teams and Outlook, or directly in Windows?** | **Outlook + Teams in the MVP; a Windows companion in Phase 2** (write-anywhere, and the only way to fill Teams' compose box, which accepts only cards from apps; plus consent-first recording of other companies' meetings). → §3 |
| **A phone/IoT device always listening; "the idea at 2 pm"; "client requirements in the 4 pm meeting"; all Teams calls** | **Teams meetings:** pull Microsoft's own post-meeting transcripts via Graph (free since Aug 2025; the tenant admin must switch on transcript API access). **Phone:** iOS and Android **cannot start the mic from the background**, so ship a **"work-mode recorder"** (one-tap work sessions, calendar prompts, quick capture; policy can pause, not start). Reframe the pillar as **"always-ready, policy-governed work capture,"** not "always listening." **Device:** later, gated — a BLE badge is the one thing that could start capture when the phone can't. → `docs/01-product-strategy.md` §3.3, §9 |
| **AWS deployment with multi-level redaction of PII and company-sensitive data** | Two regional **cells** from day 1 — US (`us-east-1`) and India (`ap-south-1`) — with content, inference, logs and backups pinned in-country. **Four data levels (L0 raw in memory only → L1 pseudonymised → L2 company-sensitive masked → L3 anonymised)**; regulated identifiers (SSN, Aadhaar, PAN, cards, bank, passport…) **irreversibly masked at first touch**; names become reversible, persona-preserving tokens. We build our **own US + India detector library** because no AWS or Microsoft service detects Indian passport, GSTIN, UPI, IFSC or US EIN. → §7, `docs/research/07` §11, `docs/research/10` §6 |
| **Full-stack app with super-admin and different user types** | Roles: platform super-admin (no standing content access), support (customer-approved break-glass), tenant admin, compliance auditor, team manager (aggregates only), end user, delegate/EA, service roles — enforced with Entra ID, Amazon Verified Permissions (Cedar) and Postgres row-level security. → §5 |
| **Huge knowledge base: vector, raw, SQL, graph** | **Aurora PostgreSQL** (system of record, row-level security, time index, relationship graph as tables) + **S3 Vectors** (one bucket and key per tenant, one index per user — ~170× cheaper per query than a shared index) + DynamoDB + S3. **Raw store:** derivatives-only by default, optional encrypted raw vault for enterprises. **Graph DB (Neptune) only when evals prove it helps.** → §8 |
| **A great, scalable, revenue-maximising product** | **Beachhead:** client-facing delivery, account and leadership teams (+ EAs) at M365 **IT-services & consulting firms** — US mid-market and Indian mid-tier/GCCs. **Wedge:** "Persona + Follow-through." **Pricing:** US $35 / $49 / from $65; India ₹1,499 / ₹2,199 / ₹3,299 / from ₹3,999. **3-year base case ≈ $13.4M ARR.** → `docs/01-product-strategy.md` |
| **Risks, in depth** | 50+ scored risks; the top ones are recording-consent class actions (*In re Otter.AI*, *Chamberlain v. Granola*), prompt-injection exfiltration, admin-consent friction, Microsoft/Google bundling "write like me," cross-audience leakage, persona misuse for fraud, and AI unit economics. → `docs/04-risk-register.md` |
| **Why Humane and Rabbit failed, and how we avoid it** | Humane: tried to replace the phone, ~6 s answers, overheating, $699 + $24/month carrier lock, ~10k units vs a 100k target, then **bricked with 10 days' notice**. Rabbit: overpromised "Large Action Model" (an Android app driving cloud browsers), ~5% daily use, **hard-coded API keys leaked**, India launch stalled on regulation. **Our answer:** software habit first, companion device only, measured claims, Hardware Trust Spec, no-brick contract terms, hardware-as-a-service inside the seat, explicit go/no-go gates. → `docs/01-product-strategy.md` §9 |
| **What else can we add that businesses will pay for?** | Ranked: EA/delegate mode · requirements → BRD/user stories/SOW/status (+ Jira/Azure DevOps) · post-meeting follow-ups in your voice · pre-meeting briefs · commitments tracker · brand-voice governance · pre-send safety checks · a personal MCP memory API · multilingual persona (Hindi/Hinglish) · knowledge-handover packs · timesheets · team/account memory. → `docs/01-product-strategy.md` §3.4 |

---

## Key numbers

| Topic | Number | Source |
|---|---|---|
| Copilot penetration | 30M+ paid seats ≈ 6.5% of ~450M M365 commercial seats (Jul 2026) | `research/09` |
| Proof of willingness to pay | Fyxer $37–64/user; $1M → $17M ARR in ~8 months (2025) | `research/09` |
| Persona tech | Retrieval of your own sent messages beats per-user fine-tuning (+14.9% vs +1.1%); no fine-tuning in v1 | `research/05` |
| AI cost per active user-month | US Sonnet stack $13.65 / $23.46 / $40.63 (low/typical/heavy); India Haiku in-country $7.73 / $13.03 / $21.20 | `research/03` |
| Speech-to-text | Amazon Transcribe $0.36/h → $11.88 per typical user-month; self-hosted ≈ $0.13–0.64 | `research/06` |
| Infrastructure | ≈ $3.10 per user-month at 1k users → ≈ $0.92 at 100k | `research/04` |
| Gross margin | 49–58% today → **~64–70% (US) / ~55–60% (India) after optimisation** | `research/09` |
| Backfill speed | 50k emails ≈ 10–90 min per user; Teams for a 1,000-user tenant ≈ 2–4 days (wave onboarding) | `research/01` |
| India constraint | Only Claude Haiku 4.5 (and Opus 5) can run with in-India inference; Sonnet/Opus 5.5 only via global routing | `research/03` |
| Redaction launch gates | ≥ 99.9% checksum IDs · ≥ 95% Indian names · ≥ 93% Hinglish · ≤ 0.1% documents leaking a regulated ID | `research/10` |
| Revenue scenarios (Y3 exit ARR) | $2.7M conservative · **$13.4M base** · $49.5M aggressive | `research/09` |

---

## The plan in one paragraph
Build **"Persona + Follow-through"** first: learn each user's voice per relationship from Sent Items and Teams chats; draft in Outlook and Teams with approvals and pre-send safety; keep a commitments ledger — all on AWS cells in the US and India with US/India-precise redaction, no training on customer data and nothing sent without a human click. Add **Teams meeting memory** (Microsoft's own transcripts) in the MVP if the team has ≥ 5 engineers, otherwise right after. Then **Persona Pro** (briefs, follow-ups, delegate mode), the **IT-Services Delivery Pack**, and the consent-first **work-mode recorder** on self-hosted speech-to-text. Hardware only after measured gates. Sell through **6–8 design partners → 30-day pilots → AWS Marketplace private offers**, targeting 15+ customers and ~$0.3M ARR by month 12 (base case).

---

## Document index

| Document | What's in it |
|---|---|
| [`docs/01-product-strategy.md`](docs/01-product-strategy.md) | Market & timing, beachhead, wedge, product pillars, ranked opportunities, positioning vs Copilot/Fyxer/Superhuman/Otter/Plaud/Viven, pricing & margin math, GTM plan, revenue scenarios, metrics, Humane/Rabbit lessons, hardware gates, naming |
| [`docs/02-solution-architecture.md`](docs/02-solution-architecture.md) | Architecture on one page, invariants, surfaces, AWS cells, identity & roles, ingestion (Graph mail/Teams, transcripts, phone), multi-level redaction pipeline, data stores & retention, AI layer (persona engine, memory engine, AgentCore agent, model routing, evals), security, compliance mapping, unit economics, technology choices, week-1 spikes |
| [`docs/03-mvp-plan-and-roadmap.md`](docs/03-mvp-plan-and-roadmap.md) | Honest scoping math, MVP scope, team shapes (4 vs 6), week-by-week 12-week plan, exit criteria, decisions before week 1, Phases 2–3 and Year 2, KPIs |
| [`docs/04-risk-register.md`](docs/04-risk-register.md) | Top-12 risks + full register: legal, platform, security, AI quality, commercial, technical, hardware, execution |
| [`docs/05-decisions-and-open-questions.md`](docs/05-decisions-and-open-questions.md) | Decisions taken, 20 recommended decisions to confirm, questions for founders and counsel, week-1 spikes, unverified facts |
| [`docs/06-red-team-review.md`](docs/06-red-team-review.md) | Adversarial review of this pack: critical/major findings and how each was resolved |
| [`docs/research/`](docs/research/) | The 10 detailed research reports (sources, confidence levels) + `_raw/` fact sheets |

**Research reports:** [01 Microsoft Graph data access](docs/research/01-m365-graph-data-access.md) · [02 Integration surfaces & meeting capture](docs/research/02-integration-surfaces-and-meeting-capture.md) · [03 AWS AI/agent stack](docs/research/03-aws-ai-agent-stack.md) · [04 AWS data, multi-tenancy & security](docs/research/04-aws-data-multitenancy-security.md) · [05 Persona modelling & memory](docs/research/05-persona-modeling-and-memory.md) · [06 Always-on capture & speech-to-text](docs/research/06-always-on-capture-and-stt.md) · [07 Legal, regulatory & privacy](docs/research/07-legal-regulatory-privacy.md) · [08 AI hardware lessons](docs/research/08-ai-hardware-lessons.md) · [09 Market, competition & pricing](docs/research/09-market-competition-pricing.md) · [10 Security threats & redaction](docs/research/10-security-threats-and-redaction.md)

---

## How this research was done — and its limits
- Ten research tracks ran as parallel agents (later two at a time), each reading primary sources (Microsoft Learn, AWS docs and price files, vendor pricing pages, court and regulator pages, papers) and tagging claims **High/Med/Low** confidence, with **[ESTIMATE]/[UNVERIFIED]** labels.
- The session's web-search budget ran out partway through; later checks used direct page fetches, and some sites (The Verge, Wired, NYT, several court/statute sites) could not be fetched — affected facts are marked. Each report ends with an "open questions / could not verify" list; `docs/05` consolidates the important ones.
- Cost and market figures are models built on list prices and stated assumptions; re-run them quarterly.
- **Nothing here is legal advice.** `docs/05` lists the questions to put to US and Indian counsel before launch.

## This week
1. Confirm or override the recommended decisions in `docs/05-decisions-and-open-questions.md` §2.
2. Start the naming/trademark search and engage US + Indian counsel.
3. Line up 6–8 design-partner conversations (≈ 4 India, ≈ 3–4 US) — and in each, ask whether their **client contracts** allow a third-party AI processor for client communications, and which accounts are in scope.
4. Kick off the week-1 technical spikes (`docs/02-solution-architecture.md` §15).
