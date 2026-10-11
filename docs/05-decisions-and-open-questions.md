# PersonaAgent — Decisions Log and Open Questions (v0.2)

> **Date:** 2026-10-06, updated 2026-10-09 (F6, F7, R-21) and 2026-10-11 (F8, R-22, research backlog §7). Living document — update as decisions are taken. Research cited as [R01]…[R12] (`docs/research/`).

---

## 1. Decisions already taken by the founders (2026-10-05/06, 2026-10-09, 2026-10-11)

| # | Decision | Implication |
|---|---|---|
| F1 | **First buyer:** Microsoft 365 mid-market & enterprise teams (per-seat B2B) | IT-led sales; admin consent; Microsoft-only integrations in v1 |
| F2 | **v1 regions:** United States + India | Two regional cells (`us-east-1`, `ap-south-1`) from day 1; US + India legal packs; Indian-English/Hindi/Hinglish support |
| F3 | **Team:** 3–6 engineers, ~3-month MVP | Persona-first MVP; recorder beta only with ≥ 5 engineers (`03-mvp-plan-and-roadmap.md`) |
| F4 | **Recorder scope:** work-only, company-governed | Tenant-admin policies; recordings private to the user; no personal lifelogging |
| F5 | **Phase-1 redaction:** precise to US + Indian government regulatory requirements | US + India detector catalogue and treatment map [R07 §11, R10 §6.4]; EU identifiers later |
| F6 | **No India model residency in the MVP** (2026-10-09) — "we will figure that part out later" | India tenants use the same model router as the US on Bedrock **global** profiles; data at rest still stays in the Mumbai cell; the DPA/trust centre disclose AI processing outside India; Indian BFSI/regulated tenants wait for the Phase-2 India residency option (in-country Haiku 4.5 / Sonnet 5 / Opus 5 since 29 Sep 2026). Supersedes R-4 for the MVP (`02-solution-architecture.md` §0 #5, §9.1) |
| F7 | **User data controls in the MVP** (2026-10-09): a customer-facing screen where users search their DMs (by person), group chats (by name) and email (by address/ID) and exclude them from training entirely, plus a list of words that must never be sent | `02-solution-architecture.md` §6.5 and security invariant #8; metadata-first onboarding (content backfill waits for the user's review); canary release gates; MVP scope and effort in `03-mvp-plan-and-roadmap.md` §1–2. Design choices are in R-21 |
| F8 | **Graph: keep the MVP simple; build company-level shared context later** (2026-10-11). The MVP keeps plain relationship tables and SQL joins (option A — no graph database, no GraphRAG). Later phases add company-level context, putting the graph/GraphRAG investment (option D) at company level so its cost is shared across the company | `02-solution-architecture.md` §8.6 (levels 1–4, six boundaries, Neptune triggers) and security invariant #9; `03` §7 (Phase 2 → Year 2); risks A7, C12, D10; open questions parked in §7 research backlog — **not researched yet, by founder choice** |

---

## 2. Recommended decisions — please confirm or override

| # | Recommendation | Alternatives | Evidence |
|---|---|---|---|
| R-1 | **No Outlook/Teams clone.** In-place Outlook add-in + opt-in server-side drafts + Teams agent/action; web app = control center & memory surface | Build our own mail/chat client (6–12+ engineer-months) | [R02 §E.1] |
| R-2 | **Persona + Follow-through is the MVP wedge**; Teams meeting memory (Graph transcripts) in the MVP if team ≥ 5, else v1.5; phone recorder = alpha only with a dedicated mobile engineer (team of 6), else Phase 2; **staff 5–6 engineers** (4 engineers ⇒ ~15–17 weeks; after the 2026-10-09 additions, 5 engineers fit the wedge in ~13 weeks and meeting memory in ~14–16) | Both pillars at full scope in 3 months (not feasible: ~80–100 ew of work) | [R07, R09, MVP plan §1, red-team RT-C4] |
| R-3 | **Two cells from day 1** (US, India); content, logs and backups pinned in-country; US inference pinned to US-geo profiles (India inference global in the MVP — F6) | Single US region first, India later (expensive retrofit; India buyers expect residency) | [R03, R04, R01 §E] |
| R-4 | ~~India model default = Claude Haiku 4.5 via the in-India profile; global Sonnet 5.5 only by tenant-admin opt-in~~ **Superseded for the MVP by founder decision F6** (global routing for India). Still the plan for the **Phase-2 India residency option**: in-country Haiku 4.5 / **Sonnet 5** (new, 29 Sep 2026) / Opus 5 via the India geographic profile, enforced by per-tenant model allow-lists; **India-only processing mandatory for BFSI** | Global Sonnet for everyone forever (residency complaints; not acceptable for RBI/SEBI/IRDAI-regulated data) | [R03 §3, R07 §6.5, red-team RT-M5; AWS What's New 29 Sep 2026] |
| R-5 | **Mode A (derivatives only) default; Mode B encrypted raw vault for enterprises that ask** | Always store raw content (bigger breach/legal exposure) | [R04 §8, R10 §11, R07 G8] |
| R-6 | **Server-side drafts via a separate opt-in "Compose" app registration** (`Mail.ReadWrite`) | Add-in only (no Outlook mobile coverage) or one broad app (slower approvals) | [R01 §H1, R02 §A] |
| R-7 | **No voiceprints / speaker enrolment in the MVP**; consent prompt → full capture, else self-only mode | Speaker ID from day 1 (BIPA/SPDI exposure) | [R07 §4, R06 §7] |
| R-8 | **External-company meeting capture OFF by default; Windows recorder in Phase 2** (MVP stretch only if a design partner insists, with mandatory disclosure) | Meeting bots (Teams now flags/blocks them) or silent desktop capture (*Granola* suit) | [R02, R07 §3] |
| R-9 | **STT: Amazon Transcribe batch in-region for the MVP behind an `AsrEngine` interface; self-host Parakeet + Nemotron diarization from month 4 (US first)** | Managed STT forever ($11.88/typical user-month on Transcribe) | [R06 §9, §11] |
| R-10 | **No per-user fine-tuning in v1**; v2 only if the seven gates pass — and then **per-tenant, customer-instructed adapters only, never pooled or global** (guardrail G1) | Per-user LoRA now (worse quality, $3–10/user-month, hard deletion); a shared model trained on customers' drafts (breaks processor status) | [R03 §4, R05 §7.11, R07 G1] |
| R-11 | **Retention defaults:** raw audio deleted immediately after transcription (tenant opt-in 1–30 days for playback, PII spans muted); transcripts 30 days; memory atoms by tier (Lite 6 months, Persona 12 months, Pro/Enterprise configurable); India logs ≥ 180 days in India; legal hold overrides deletion | Keep everything (exposure) / keep nothing (no recall value) | [R07 G8, G15; R10 SR-39; 02-solution-architecture §8.4] |
| R-12 | **Trademark clearance now; be ready to rename** before public launch | Keep "PersonaAgent" (collides with an ACL 2026 research framework) | [R05, R07] |
| R-13 | **One named engineer owns security & redaction full-time from day 1**; external pentest before the first paying tenant; SOC 2 Type I readiness in the MVP window | Defer security to later (blocks every enterprise deal) | [R10 §11] |
| R-14 | **One beachhead:** client-facing delivery, account and leadership teams (+ their EAs) at M365-standardised IT-services & tech-consulting firms — US mid-market; India mid-tier IT services and GCC delivery centres. Non-goals for 12 months: healthcare, legal, financial advisors, real estate, consumer, SMB self-serve | Sales teams (crowded: Gong/Fathom/Fireflies), legal/healthcare (slow, risky), execs only | Beachhead scorecard 4.3 / 4.1 of 5 [R09 §8] |
| R-15 | **Wedge = "Persona + Follow-through"** (relationship-aware drafts, approvals, pre-send safety, commitments ledger, light EA mode) → Persona Pro (Teams meeting memory, briefs, follow-ups) → IT-Services Delivery Pack → governed work-mode capture last | Lead with the recorder / a notetaker (commoditised; litigation) | [R09 §8.3, R07] |
| R-16 | **Pricing (annual):** US Persona $35 · Pro $49 · Enterprise from $65; India (excl. 18% GST; data stored in India — in-country AI processing once the Phase-2 residency option ships, F6) Lite ₹1,499 · Persona ₹2,199 · Pro ₹3,299 · Enterprise from ₹3,999; add-ons Capture+ / Delivery Pack / Power user / dedicated-BYOC; **no freemium**; 30-day pilots credited to annual; monthly +20% | Freemium (≈ $25 onboarding cost per user, no viral loop); deep India discounts (COGS ≈ US) | Margin math [R09 §6.4] |
| R-17 | **Positioning: complement Copilot** — "the voice and follow-through layer for Microsoft 365, with or without Copilot"; Copilot Chat agent, Agent 365 registration, MCP memory API | Compete head-on with Copilot | [R09 §9] |
| R-18 | **Hardware:** none in the MVP; "integrate before building" (Plaud SDK US-first, Omi experimental, headsets) after gate G1; pilot badges only after G2; production badge (Capture+ hardware-as-a-service) only after G3; **publish a Hardware Trust Spec and put no-brick terms in the MSA now**; describe Pillar 2 as **"always-ready, policy-governed work capture"**, not "always listening" | Build a device now (Humane/Rabbit pattern) | [R08 §6, 01-product-strategy §9] |
| R-19 | **GTM:** admin-approval-led growth; 6–8 design-partner LOIs before the MVP ships (~4 India, ~3–4 US); AWS Marketplace private offers + co-sell first, then Microsoft Marketplace/Teams Store; Indian entity with GSTIN; targets: 3–5 paid by month 5, 10 by month 9, 15+ (~$0.3M ARR) by month 12 | Classic PLG (blocked by Microsoft's consent defaults) | [R09 §7, R01] |
| R-20 | **Client/account scoping in the MVP:** admins can exclude or allow-list client domains/accounts for learning, memory and drafting; ship a client-assurance pack (DPA flow-down, sub-processor list, no-training statement) customers can share with their own clients | Ingest everything and hope customers' client contracts allow it | [Red-team RT-C1] |
| R-21 | **How F7 works:** an exclusion means *not at all* (no style learning, memory, retrieval, drafting context, evals or caches); **a person exclusion covers everywhere they take part**, with a preview where the user can untick big team chats; tenant and user rules combine and any exclusion wins; **never-send words default to Never send** — `[removed]` in drafts, never filled in — with a per-word **Allow in my drafts** opt-in; matching is our own in-memory matcher before any model (Bedrock Guardrails and Transcribe filters can't hold per-user lists), with rule-based variants and no ML transliteration in the MVP; the word list lives in the vault and only the user can read it (admins see counts); **no message bodies are fetched before the user selects Finish or Skip**; logical exclusion ≤ 1 min, physical purge ≤ 24 h (a legal hold defers only the purge); a one-off in-memory draft in a user-excluded thread on explicit request (never for tenant exclusions) | Exclude from style learning only (excluded chats would still feed memory); a person rule limited to 1:1 chats and direct mail (their group-chat messages would still be learned); Guardrails word filters (block-only, 100 guardrails per account-Region); exclusions applied only after backfill (content already processed); admin-visible word lists (chills use) | Founder request; [R12]; `02` §6.5 |
| R-22 | **How F8 works:** four levels — personal (MVP) → shared by access (process shared chats and meetings once, copy results into each member's private index; Phase 2) → opt-in team spaces with per-team, per-manager and per-client sub-contexts (Phase 3 → Year 2) → company graph with GraphRAG-style account summaries and consented "who knows whom" (Year 2 Enterprise add-on). Six boundaries: mirror Microsoft 365 access; manager status grants nothing; team spaces opt-in; personal stays personal (style, never-send words, exclusions); client walls; company-wide views metadata-only (k ≥ 10) | A company-wide shared index from day one (one permission bug leaks private chats); manager-based visibility (employee monitoring); per-user GraphRAG (≈ $170–750+ per user one-off, nothing shared) | Founder idea (2026-10-11); [R11 §0, §7, §9]; `02` §8.6 |

---

## 3. Open questions for the founders

1. **Design partners:** which 3–5 organisations (1–2 US, 1–2 India)? Can your own company be partner #0 (dogfooding on its M365 tenant)?
2. **Partner programs:** do you already have AWS Partner (Software Path / Marketplace seller) and Microsoft AI Cloud Partner Program accounts? (Speeds up Marketplace listings, co-sell, publisher verification.)
3. **Budget envelope** for the MVP window: counsel (US + India), external pentest, SOC 2 tooling + auditor, Microsoft 365 Certification (≈ $15–40k/yr est. [R01]), AWS/Bedrock usage.
4. **Sub-processors you accept:** Anthropic models via Amazon Bedrock (default); any STT vendor beyond AWS (e.g., Azure Speech Central India for Hindi/Hinglish; Recall.ai — no India region)?
5. **Hindi/Hinglish at launch:** launch English-first with Hinglish behind a quality gate (recommended), or require Hinglish parity in v1?
6. **Server-side drafts:** comfortable asking design partners for `Mail.ReadWrite` on the opt-in Compose app?
7. **Desktop external-meeting capture in MVP:** only if a design partner requires it — do any of your target partners?
8. **Founder access:** the beachhead score assumes the team has an AWS/IT-services network for design partners in both countries — is that right? Which firms could sign LOIs in the next 6–8 weeks?
9. **Entities and billing:** do you have (or will you set up) an Indian entity with a GSTIN and a US entity for AWS/Microsoft marketplace listings?
10. **Product name:** shortlist 3–5 distinctive names for trademark search (US + India) before the public launch.
11. **Client contracts (critical for the beachhead):** do your target design partners' client MSAs/SOWs/NDAs allow a third-party AI processor to handle client communications? Which client accounts would be in or out of scope on day one?
12. **Funding:** bootstrap/pre-seed through pilots, or raise against design-partner LOIs? (The base case implies ~$10–15M by Y3; hardware gates require 18 months of runway excluding hardware revenue.)
13. **India residency check (follows F6):** do any target Indian design partners — BFSI, public sector, or firms whose *client* contracts demand in-India processing — need in-country AI processing during pilots? If yes, they wait for Phase 2 or we pull the India residency option forward (~1–2 ew).
14. **User data controls — confirm or override three defaults in R-21:** (a) a person exclusion covers everywhere they take part (vs only 1:1 chats and direct mail); (b) a one-off in-memory draft is allowed in a thread the user excluded themselves; (c) never-send variants are rule-based only — is an offline transliteration model (e.g. AI4Bharat IndicXlit, run inside our own boundary) acceptable later under the "never sent to any AI model" promise?

---

## 4. Questions for counsel (start in weeks 0–6) [R07 §13.4, §16]

**US privacy / litigation counsel**
1. Under CIPA §632, is a **summary** of an unconsented recording itself a violation (vs the recording)?
2. Do **temporary voice embeddings used only to filter out non-consenting speakers** count as voiceprints/biometric identifiers under BIPA (the "filtering paradox")?
3. Review of the meeting and in-person capture flows and announcement wording for all-party-consent states (*In re Otter.AI*, *Chamberlain v. Granola*).
4. MSA / AUP / DPA drafting (customer warranties on notices and consents; CCPA service-provider terms).

**Indian counsel**
5. Do DPDP "legitimate uses" cover **third parties** whose data appears in ingested emails/recordings, or is consent/notice required?
6. SPDI Rules written-consent language for the current period (before 13 May 2027).
7. SEBI/RBI/IRDAI localisation scope — does it cover **inference**, or storage only?
8. Telecommunications Act interception question for recording calls/meetings.
9. Aadhaar handling: confirm masking approach and whether Aadhaar Data Vault requirements apply to incidental Aadhaar numbers in emails.

**Other specialists**
10. **QSA:** PCI DSS scope for in-memory processing of card numbers that we irreversibly mask at ingestion.
11. **Trademark counsel:** clearance for the product name in the US and India.
12. **Microsoft API Terms §3(c):** is our admin-consent "express and specific grant" mechanism adequate?
13. **Legal hold vs user exclusions** (US + Indian counsel): when a tenant places a legal hold, must we preserve our *derived* copies (L1 text, vectors, memory) of sources a user excluded, given that Microsoft 365 remains the system of record? (Design today: the hold defers only the physical purge [R12 §9.5].)

---

## 5. Week-1 technical spikes (from `02-solution-architecture.md` §15)
1. Teams deep-link prefill in **existing** chats.
2. Add-in insert/read across new Outlook, classic, OWA, Mac (quoted-thread handling).
3. Graph: `uniqueBody` in delta; `MSIP_Labels` on Sent Items; Sent Items subscriptions; pagination depth; encrypted mail.
4. Transcripts with Transcript-API-access / speaker-attribution ON vs OFF.
5. `createReply` draft visibility on Outlook iOS/Android.
6. AgentCore Identity with multi-tenant Entra tokens; refresh-token custody for offline sync.
7. Latency: Sonnet 5.5 (US geo) p95, and global-profile p95 from Mumbai (India tenants, F6).
8. iOS background resume after calls/AirPods; Android per-OEM survival; battery %/h.
9. STT bake-off set collection (US English, Indian English, Hinglish, Hindi, noisy).
10. Redaction recall on US + India labelled sets; L0-vs-L1 persona A/B harness.
11. User data controls: header-pass time; header-only Sent Items subscription; `chatType`/`topic` filters; `conversationId` on forwards; ICU segmentation on Hinglish/Devanagari [R12 §11].

---

## 6. Facts the research could not verify (re-check before relying on them)
- Whether Microsoft has shipped a native "write in my style/sound like me" feature in Copilot for Outlook/Teams [R01, R02].
- Teams deep-link prefill behaviour in existing chats; transcript availability latency after meetings; coverage of Teams "Meet Now" [R02].
- `uniqueBody` in delta responses; headers/labels on Sent Items copies; Graph Data Connect current pricing [R01].
- Whether AgentCore Identity's token vault handles Microsoft refresh tokens for offline sync; whether Guardrails PII filtering stays inside Mumbai; when Bedrock batch will add Sonnet/Opus 5.5; Sonnet 5.5 p95 on Bedrock [R03].
- **India in-country Claude (AWS, 29 Sep 2026):** the exact inference-profile IDs for Sonnet 5 / Opus 5 / Haiku 4.5 in India, and the precise guarantee — AWS's post says data is processed "in India Regions" (Mumbai + Hyderabad) but does not repeat the "never leaves the Region" wording it uses for Seoul and Singapore. Confirm in the Bedrock docs or with AWS before contracting residency (Phase 2).
- HIPAA eligibility of S3 Vectors and AgentCore; whether AWS Marketplace purchases count toward customers' AWS commitments (EDP drawdown) [R04].
- Independent Hinglish/Indian-English STT benchmarks; Sarvam India-only processing for its API; real battery drain per hour; iOS background resume after calls on iOS 26/27 [R06].
- Primary texts: the *Otter* order and *Granola* complaint; full DPDP Rules text; SEBI/IRDAI localisation wording; MeitY AI governance guidelines; EU-US DPF appeal status [R07].
- OWASP LLM Top 10 2026 contents; UIDAI Aadhaar Data Vault circular; several identifier format specs (ITIN ranges, NPI/DEA, GSTIN checksum details) [R10].
- User data controls [R12 §11]: a header-only rich subscription on `SentItems` (documented only for `Drafts`); `chatType`/`topic` filters on `/me/chats`; `$filter` on `conversationId`; whether forwards start a new `conversationId`; non-organiser access to transcripts with delegated permissions; Transcribe vocabulary filters for hi-IN; S3 Vectors `$nin` on list metadata; whether IndicXlit runs offline on CPU.

---

## 7. Research backlog — parked for a later research agent (founder decision, 2026-10-11)
Not researched yet, by founder choice. Each item names what it blocks; run it before the phase that needs it — RB-1, RB-4 and RB-8 first, before company-context level 2 (`02-solution-architecture.md` §8.6). Open items from the finished research live in `docs/research/11` §12 and `docs/research/12` §11.

| ID | Question to research | Blocks | Starting points |
|---|---|---|---|
| RB-1 | **Mirroring Microsoft 365 access for shared items:** chat history for people added later (Teams "include history"), removed members, guests and external users; meeting invitees vs attendees vs forwarded invites; who can read transcripts and recordings; email threads (Bcc, forwards, shared mailboxes, delegates); keeping membership in sync (change notifications, `lastUpdatedDateTime`) | Level 2 | Graph chat, member, meeting and transcript APIs; `research/12` §1–4 |
| RB-2 | **Client walls in Microsoft 365:** can we read and mirror Microsoft Purview information barriers or sensitivity labels through Graph, or must admins define walls in PersonaAgent? | Level 3 | Purview information-barriers docs; client/account scoping (`02` §6.1) |
| RB-3 | **Employee notice and workplace-monitoring rules for shared and manager context:** US (New York electronic-monitoring notice law, Connecticut, Delaware; California CPPA ADMT and risk assessments), India (DPDP notice; employment "legitimate uses"), EU works councils (later) | Levels 3–4 | `research/07` §3, §7; risk A7 |
| RB-4 | **Sharing factor and economics:** how many enrolled users share each chat and meeting in design-partner tenants; level-2 savings and level-4 cost per user (shared GraphRAG extraction, Neptune per tenant) against pricing | Level 2 go/no-go; level 4 business case | `03` §8 KPI; `research/11` §7 |
| RB-5 | **Company-graph technology:** Postgres two-table graph vs Neptune Analytics vs Bedrock Knowledge Bases GraphRAG vs the awslabs graphrag-toolkit; incremental re-indexing and deletion inside GraphRAG summaries; per-tenant isolation; India gaps (no Neptune Analytics in Hyderabad, no managed GraphRAG in India). Carries over `research/11` §12: Neptune memory per edge, replica billing, stopped-graph start time, Knowledge Bases GraphRAG metadata filters during traversal, LazyGraphRAG availability | Level 4 | `research/11` §6–7, §9, §12 |
| RB-6 | **Team-space product design and precedents:** how Granola Spaces, Plaud Teams, Glean, Viven and Microsoft Copilot Pages/Notebooks handle membership, sharing, revocation and audit; UX for per-team, per-manager and per-client sub-contexts | Level 3 | `research/09` (opportunity #13 competitors) |
| RB-7 | **Pricing for company context / relationship intelligence:** verify Introhive, 4Degrees and Dynamics 365 Sales Premium prices (unverified in `research/11` §11); willingness to pay among IT-services buyers | Level 4 pricing | `research/11` §11; `research/09` |
| RB-8 | **Purge and consent across users:** what happens to shared summaries and graph edges when one member excludes a shared chat, leaves the company or files a deletion request; legal-hold interplay; regeneration within 24 h | Levels 2–4 | `research/12` §9.5; counsel question 13 |
| RB-9 | **Evaluation for shared context:** does company context measurably improve answers and drafts (for example, consistent facts for colleagues writing to the same client)? Gate metrics in the style of `research/11` §8, plus cross-user leakage canaries | Levels 3–4 | `research/11` §8 |
