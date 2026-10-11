# PersonaAgent — Red-Team Review of the Strategy Pack (v1)

> **Date:** 2026-10-06. **Scope:** `README.md` and `docs/01`–`05`, checked against the ten research reports in `docs/research/`.
> **Who did it:** an independent review subagent was started but was stopped before it saved anything, and stopped agents can't be resumed. The lead agent then ran the same adversarial checklist itself: fidelity to evidence, internal consistency, feasibility, unit economics, security/privacy/legal gaps, strategic blind spots, completeness against the founders' brief, and missing risks. Treat it as a self-review. A fresh independent reviewer can still be commissioned.
> **Status:** every Critical and Major finding below has been **fixed in the documents** (39 edits on 2026-10-06). Minor findings are listed with their status.
> **Later decisions (2026-10-09):** founder question 3 below is answered by **F6 — no India model residency in the MVP** (global routing; in-country Haiku 4.5 / Sonnet 5 / Opus 5 became available on 29 Sep 2026 and is now the Phase-2 residency option). User data controls (F7) and the company-context graph plan (F8) were added afterwards; see `05-decisions-and-open-questions.md`. This review describes the pack as of 2026-10-06.

---

## Verdict
The pack answers every item in the founders' brief with evidence and makes clear recommendations. Before this review, though, it had **four Critical problems**: three internal contradictions that could have misled staffing, pricing and privacy decisions, and **one strategic blind spot** in the chosen beachhead (client contracts at IT-services firms). With the fixes, the pack is decision-ready. The largest remaining uncertainty is **external**: whether design partners' client contracts allow a third-party AI processor. Only customer discovery can answer that.

---

## Critical findings (all fixed)

| ID | Where | Problem | Evidence | Fix applied |
|---|---|---|---|---|
| **RT-C1** | `01` §2 (beachhead); `04`; `05`; `03` | **Beachhead blind spot: client contracts.** The wedge ingests IT-services firms' *client* communications. Those firms' client MSAs, SOWs, NDAs and offshore-delivery security schedules often restrict sharing client confidential information with new third-party processors or AI tools, and some need client approval. No research track covered this. The only related item was secure-floor bans on recording devices [R08 §4.3]. | Grep of all research: client-contract restrictions not covered. The ABA's guidance for lawyers (client consent before entering client data into AI tools) [R07 §7.3] shows the general pattern for professional-services confidentiality. | Added **client/account scoping controls** to the MVP (exclude or allow-list client domains/accounts for learning, memory and drafting, with per-client Tier C dictionaries). Added a **client-assurance pack**, a discovery question in every deal, new risks A11 and top-risk #13, decision R-20, and founder question #11 (`01` §2.3, `02` §6.1, `03` §2.1, `04`, `05`, `README`). |
| **RT-C2** | `02` §8.4; `05` R-11 | **Audio retention default contradicted the legal and security guardrails.** The architecture kept raw audio for a 7-day verification window by default. The legal track's guardrail G8 says "no raw audio" and the security track's SR-39 says "audio deleted after transcription by default". | [R07 §13.1 G8], [R10 §9 SR-39] | Default is now **deleted immediately after transcription and QA**. Tenants can opt in to 1–30 days of playback retention, with PII spans muted using word timestamps [R06 §12]. A legal hold overrides deletion (`02` §7.1, §8.4; `05` R-11). |
| **RT-C3** | `02` §0 #5, §9.1, §13 vs `01` §5 | **The default model contradicted pricing and margins.** The architecture made Sonnet 5.5 the US default "with a Haiku router". The pricing and margin math assume Haiku by default with a quota of Sonnet "premium drafts". The "US MVP stack" COGS (~$38/user-month) was **above the $35 Persona price**. | [R09 §6.4]: blended LLM cost $12.81 assumes Haiku default with a 20% premium share; [R03 §8.3] | Routing is now **Haiku 4.5 by default, Sonnet 5.5 (US-geo) for premium drafts within tier quotas, router shipped in the MVP**. Added an explicit note that the MVP-stack row is a worst case and that Persona excludes recording (`02` §0, §9.1, §13; `01` §5 note). |
| **RT-C4** | `03` §1, §3; `05` R-2 | **MVP feasibility overstated.** The plan said a 4-engineer team (~48 engineer-weeks) "can just fit the wedge". Its own estimates for the wedge add up to ≈ 54–60 engineer-weeks even with trimmed surfaces. That could mislead the staffing decision. | `03` §1 workstream table | Now states: **4 engineers ⇒ ~14–16 weeks, or defer server-side drafts and the Teams agent to v1.5; 5–6 engineers ⇒ 12 weeks; recommend 5–6** (`03` §1, §3; `05` R-2). |

## Major findings (all fixed)

| ID | Where | Problem | Fix applied |
|---|---|---|---|
| **RT-M1** | `02` §3.2 vs `03` §2.2 vs `05` R-2 | The recorder's MVP status was inconsistent across documents: "MVP beta (month 3)", "beta if team ≥ 5" and "alpha only with team of 6". | Harmonised everywhere: **alpha only with a dedicated mobile engineer (team of 6); otherwise Phase 2.** |
| **RT-M2** | `01` §5 vs `02` §8.4 | Memory horizon was inconsistent: pricing tiers say Lite 6-month and Persona 12-month memory, while the architecture kept memory atoms "until the user deletes". | Retention by tier: **Lite 6 months · Persona 12 months · Pro/Enterprise configurable**. Transcripts 30 days. Notes added in `01` §5 and `02` §8.4. |
| **RT-M3** | `02` §9.2; `03` Year 2; `05` R-10 | Fine-tuning governance was ambiguous. The AI-stack research suggested logging drafts for a later "global/per-tenant" fine-tuned model [R03 §9 item 8]. Any global or pooled training would break guardrail G1 and risk processor status (the *Otter* "third-party eavesdropper" theory) [R07]. | Explicit rule: **adapters are per-tenant, trained only on that tenant's L1 data on documented customer instruction, never pooled or global, and deleted with the tenant.** |
| **RT-M4** | `02` §7–8 | "Derivatives-only" and pseudonymised L1 text risked being presented as anonymous. Pseudonymised text is still personal data, and context can re-identify people. | Added a **"Pseudonymised is not anonymous"** rule in `02` §7.1. L1 stays subject to DSARs, breach rules and contracts; only L3 aggregates are anonymous. |
| **RT-M5** | `02` §4.1, §9.1; `05` R-4 | The India global-routing opt-in is a **cross-border transfer to unspecified regions**. Region-deny SCPs restrict where API calls are made, not where cross-region inference processes data. | Enforced through **per-tenant model allow-lists in the router**, recorded in the DPA/transfer register, and never enabled for BFSI. Notes added to `02` §4.1 and §9.1, and to `05` R-4. |
| **RT-M6** | `04` | Missing risks: (a) **model-vendor concentration** (Claude via Bedrock: price, regional availability, quotas, retirements); (b) **executives' labelled or encrypted mail** weakens personas for the most valuable users [R01]; (c) **funding and runway** (the base case implies ~$10–15M of venture funding by Y3 [R09]; hardware gates need 18 months of runway [R08]); (d) client contracts (RT-C1). | Added **B8, D8, H4, A11** and top-risk #13. Added funding as founder question #12. |
| **RT-M7** | `03` | Hidden MVP work and costs were not listed: publisher verification, Azure Bot registration, gold-set labelling and Indian raters, pentest lead time and remediation, store review, India/US entities, SOC 2 and counsel budgets, on-call (the CERT-In 6-hour clock). The pentest also sat in weeks 11–12 with no time to remediate. | Added **§4.1 Hidden work and budget**. The pentest is now booked by week 4, run in weeks 9–10, and remediated in weeks 11–12. |

## Minor findings

| ID | Where | Note | Status |
|---|---|---|---|
| RT-m1 | `01` §5.1 | The Persona tier promised "server-side drafts for mobile". That needs the tenant to approve the separate Compose permission. | Fixed ("where the tenant approves") |
| RT-m2 | `01` §5.1 | The Pro tier's "10 h/month capture" depends on the recorder shipping. | Fixed ("once the recorder ships") |
| RT-m3 | `02` §3.2 | "Bot Framework SDK is archived" was imprecise. The research says support ended in Dec 2025. | Fixed |
| RT-m4 | `02` §9.2 | Padding the persona prompt prefix to the 4,096 tokens Haiku needs before caching kicks in raises cache-write cost. That is fine at our volumes but should be measured. | Open (measure in week 1–2 cost tests) |
| RT-m5 | All | Several prices and limits come from Sep–Oct 2026 pages and change often (AgentCore was repriced twice in two months). | Open — re-run cost models quarterly (`02` §13) |
| RT-m6 | `01` §7 | The revenue scenarios come from one analyst model with judgement-based conversion rates. | Open — replace with pilot data by month 6 |
| RT-m7 | `README` | Decision count changed (19 → 20) and the review document was added to the index. | Fixed |

---

## What the pack gets right
- It answers the founders' central product question with a clear, evidence-based "no clone UI" and a concrete in-place surface plan.
- It is honest about platform reality: users can't consent to mail/chat access themselves, Teams transcript access is off by default, phones can't start the mic from the background, and Teams' compose box only accepts cards from apps.
- It treats India residency precisely. Only Haiku 4.5 and Opus 5 can run in-country; the rules for banks, brokers and insurers (BFSI) differ from general DPDP requirements; Hyderabad has service gaps for disaster recovery.
- It makes redaction a product capability, with US + India detector specifics, launch thresholds and fail-closed behaviour, not a compliance afterthought.
- It translates legal exposure (*Otter*, *Granola*, BIPA, CERT-In, DPDP) into product guardrails with owners.
- It links unit economics to pricing, tier limits and a model router rather than hand-waving margins.
- Its hardware plan learns from Humane and Rabbit with measurable go/no-go gates and kill criteria.

## Top 5 questions the founders must answer
1. **Client contracts:** will your target IT-services design partners' client agreements allow a third-party AI processor for client communications? Which accounts are in scope on day one?
2. **Staffing:** can you staff **5–6 engineers**, including a full-time security/redaction owner, for the 12-week MVP? If not, accept ~14–16 weeks.
3. **India residency stance:** will Indian design partners accept Haiku-only in-country drafting, with an opt-in to global Sonnet routing for non-BFSI tenants?
4. **Funding path:** bootstrap through pilots, or raise against LOIs and pilot metrics? The base case implies ~$10–15M by Y3.
5. **Name and entities:** which name survives trademark clearance in the US and India, and when will the Indian (GSTIN) and US entities and marketplace seller accounts be ready?
