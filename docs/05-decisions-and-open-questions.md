# PersonaAgent — Decisions Log and Open Questions (v0.1)

> **Date:** 2026-10-06. Living document — update as decisions are taken. Research cited as [R01]…[R10] (`docs/research/`).

---

## 1. Decisions already taken by the founders (2026-10-05/06)

| # | Decision | Implication |
|---|---|---|
| F1 | **First buyer:** Microsoft 365 mid-market & enterprise teams (per-seat B2B) | IT-led sales; admin consent; Microsoft-only integrations in v1 |
| F2 | **v1 regions:** United States + India | Two regional cells (`us-east-1`, `ap-south-1`) from day 1; US + India legal packs; Indian-English/Hindi/Hinglish support |
| F3 | **Team:** 3–6 engineers, ~3-month MVP | Persona-first MVP; recorder beta only with ≥ 5 engineers (`03-mvp-plan-and-roadmap.md`) |
| F4 | **Recorder scope:** work-only, company-governed | Tenant-admin policies; recordings private to the user; no personal lifelogging |
| F5 | **Phase-1 redaction:** precise to US + Indian government regulatory requirements | US + India detector catalogue and treatment map [R07 §11, R10 §6.4]; EU identifiers later |

---

## 2. Recommended decisions — please confirm or override

| # | Recommendation | Alternatives | Evidence |
|---|---|---|---|
| R-1 | **No Outlook/Teams clone.** In-place Outlook add-in + opt-in server-side drafts + Teams agent/action; web app = control center & memory surface | Build our own mail/chat client (6–12+ engineer-months) | [R02 §E.1] |
| R-2 | **Persona + Follow-through is the MVP wedge**; Teams meeting memory (Graph transcripts) in the MVP if team ≥ 5, else v1.5; phone recorder = alpha only with a dedicated mobile engineer (team of 6), else Phase 2; **staff 5–6 engineers** (4 engineers ⇒ ~14–16 weeks) | Both pillars at full scope in 3 months (not feasible: ~80–100 ew of work) | [R07, R09, MVP plan §1, red-team RT-C4] |
| R-3 | **Two cells from day 1** (US, India); content, inference, logs and backups pinned in-country | Single US region first, India later (expensive retrofit; India buyers expect residency) | [R03, R04, R01 §E] |
| R-4 | **India model default = Claude Haiku 4.5 via the in-India profile**; global Sonnet 5.5 only by tenant-admin opt-in (with disclosure, recorded as a cross-border transfer in the DPA, enforced by per-tenant model allow-lists); **India-only processing mandatory for BFSI** | Global Sonnet for everyone (residency complaints; illegal for RBI/SEBI/IRDAI-regulated data) | [R03 §3, R07 §6.5, red-team RT-M5] |
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
| R-16 | **Pricing (annual):** US Persona $35 · Pro $49 · Enterprise from $65; India (excl. 18% GST, India-resident) Lite ₹1,499 · Persona ₹2,199 · Pro ₹3,299 · Enterprise from ₹3,999; add-ons Capture+ / Delivery Pack / Power user / dedicated-BYOC; **no freemium**; 30-day pilots credited to annual; monthly +20% | Freemium (≈ $25 onboarding cost per user, no viral loop); deep India discounts (COGS ≈ US) | Margin math [R09 §6.4] |
| R-17 | **Positioning: complement Copilot** — "the voice and follow-through layer for Microsoft 365, with or without Copilot"; Copilot Chat agent, Agent 365 registration, MCP memory API | Compete head-on with Copilot | [R09 §9] |
| R-18 | **Hardware:** none in the MVP; "integrate before building" (Plaud SDK US-first, Omi experimental, headsets) after gate G1; pilot badges only after G2; production badge (Capture+ hardware-as-a-service) only after G3; **publish a Hardware Trust Spec and put no-brick terms in the MSA now**; describe Pillar 2 as **"always-ready, policy-governed work capture"**, not "always listening" | Build a device now (Humane/Rabbit pattern) | [R08 §6, 01-product-strategy §9] |
| R-19 | **GTM:** admin-approval-led growth; 6–8 design-partner LOIs before the MVP ships (~4 India, ~3–4 US); AWS Marketplace private offers + co-sell first, then Microsoft Marketplace/Teams Store; Indian entity with GSTIN; targets: 3–5 paid by month 5, 10 by month 9, 15+ (~$0.3M ARR) by month 12 | Classic PLG (blocked by Microsoft's consent defaults) | [R09 §7, R01] |
| R-20 | **Client/account scoping in the MVP:** admins can exclude or allow-list client domains/accounts for learning, memory and drafting; ship a client-assurance pack (DPA flow-down, sub-processor list, no-training statement) customers can share with their own clients | Ingest everything and hope customers' client contracts allow it | [Red-team RT-C1] |

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

---

## 5. Week-1 technical spikes (from `02-solution-architecture.md` §15)
1. Teams deep-link prefill in **existing** chats.
2. Add-in insert/read across new Outlook, classic, OWA, Mac (quoted-thread handling).
3. Graph: `uniqueBody` in delta; `MSIP_Labels` on Sent Items; Sent Items subscriptions; pagination depth; encrypted mail.
4. Transcripts with Transcript-API-access / speaker-attribution ON vs OFF.
5. `createReply` draft visibility on Outlook iOS/Android.
6. AgentCore Identity with multi-tenant Entra tokens; refresh-token custody for offline sync.
7. Latency: Sonnet 5.5 (US geo) and Haiku 4.5 `in.` p95.
8. iOS background resume after calls/AirPods; Android per-OEM survival; battery %/h.
9. STT bake-off set collection (US English, Indian English, Hinglish, Hindi, noisy).
10. Redaction recall on US + India labelled sets; L0-vs-L1 persona A/B harness.

---

## 6. Facts the research could not verify (re-check before relying on them)
- Whether Microsoft has shipped a native "write in my style/sound like me" feature in Copilot for Outlook/Teams [R01, R02].
- Teams deep-link prefill behaviour in existing chats; transcript availability latency after meetings; coverage of Teams "Meet Now" [R02].
- `uniqueBody` in delta responses; headers/labels on Sent Items copies; Graph Data Connect current pricing [R01].
- Whether AgentCore Identity's token vault handles Microsoft refresh tokens for offline sync; whether Guardrails PII filtering stays inside Mumbai; when Bedrock batch will add Sonnet/Opus 5.5; Sonnet 5.5 p95 on Bedrock [R03].
- HIPAA eligibility of S3 Vectors and AgentCore; whether AWS Marketplace purchases count toward customers' AWS commitments (EDP drawdown) [R04].
- Independent Hinglish/Indian-English STT benchmarks; Sarvam India-only processing for its API; real battery drain per hour; iOS background resume after calls on iOS 26/27 [R06].
- Primary texts: the *Otter* order and *Granola* complaint; full DPDP Rules text; SEBI/IRDAI localisation wording; MeitY AI governance guidelines; EU-US DPF appeal status [R07].
- OWASP LLM Top 10 2026 contents; UIDAI Aadhaar Data Vault circular; several identifier format specs (ITIN ranges, NPI/DEA, GSTIN checksum details) [R10].
