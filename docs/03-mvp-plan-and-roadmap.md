# PersonaAgent — MVP Plan and Roadmap (v0.2)

> **Date:** 2026-10-06 · **Assumptions:** 3–6 engineers, ~12-week MVP, M365 mid-market & enterprise buyers (beachhead: client-facing teams at IT-services/consulting firms in the US and India), work-only company-governed recorder. Architecture: `02-solution-architecture.md`; strategy: `01-product-strategy.md`. Research cited as [R01]…[R10].
> Effort figures are estimates in **engineer-weeks (ew)**. v0.2 aligns scope and targets with the market track [R09] and the hardware track [R08].

---

## 1. The scoping problem, stated honestly

Adding up the research tracks' own estimates for "everything in the MVP" gives roughly **80–100 ew**:

| Workstream | ew (est.) | Source |
|---|---|---|
| Platform & infra (CDK, two cells, accounts, CI/CD, observability) | 6–8 | [R04] |
| Identity, consent, onboarding wizard, tenant admin console | 5–6 | [R01, R02] |
| Graph ingestion (mail + Teams backfill/incremental, throttle-aware scheduler) | 6–8 | [R01] |
| Redaction pipeline, vault, US + India detectors, test sets | 8–12 | [R10] |
| Persona engine (labelling, style cards, retrieval, drafting service, edit loop, eval harness) | 10–12 | [R05] |
| Commitments ledger v0 (email + chat) | 2–3 | [R09] |
| Memory engine (episodes, atoms, Q&A agent on AgentCore) | 6–8 | [R05, R03] |
| Surfaces: Outlook add-in, server-side drafts, Teams agent + action, web control center | 22–26 | [R02] |
| Teams meeting transcripts via Graph | 2–3 | [R02] |
| Mobile work-mode recorder (iOS + Android) + STT pipeline | 10–14 | [R06] |
| Security hardening, pentest prep, compliance docs | 3–4 | [R10, R07] |

A team of 3–6 for 12 weeks has **36–72 ew**. Even the wedge alone (platform, consent, ingestion, redaction, persona, commitments v0, a trimmed set of surfaces, security) is **≈ 54–60 ew**. So: **with 4 engineers, plan ~14–16 weeks or defer server-side drafts and the Teams agent to v1.5; with 5–6 engineers the wedge fits 12 weeks (and with 6, meeting memory too). We recommend staffing 5–6 engineers** (red-team finding RT-C4). The MVP is cut along the line the research already points to:

- **Pillar 1 — "Persona + Follow-through" — is the wedge.** It is the lower-legal-risk pillar ("a manageable contract and data-protection problem" [R07]), the clearest daily habit, the segment's top pain [R09], and it builds the data foundation everything else uses.
- **Teams meeting memory (Microsoft's own transcripts, free, banner consent) is in the MVP only with ≥ 5 engineers**; otherwise it is the first v1.5 deliverable (months 4–5).
- **The phone recorder is an internal/design-partner alpha only with a dedicated mobile engineer (team of 6)**; otherwise it starts in Phase 2. In-person capture stays OFF by default either way [R07 G5], and the MVP is instrumented for the hardware gates [R08].

---

## 2. MVP scope

### 2.1 In scope (all team sizes)
1. **Two production cells** (US `us-east-1`, India `ap-south-1`) from one CDK app; tenant pinning; region-deny SCPs.
2. **Entra multi-tenant "Read" app** (delegated `Mail.Read`, `Chat.Read`, `User.ReadBasic.All`, optional `User.Read.All`) with an admin-consent wizard that records the **express persona-learning grant**; publisher verification + Publisher Attestation.
3. **Ingestion:** sent mail + Teams chats (backfill newest-first + incremental), thread and relationship labelling, pre-ingestion privacy gate, and **client/account scoping controls** (exclude or allow-list client domains/accounts — needed by IT-services customers bound by client contracts; RT-C1).
4. **Redaction L0→L1:** US + India Tier R validators, secrets rules, NER ensemble with the M365-directory gazetteer, tokenisation vault + re-hydrator, verify pass, fail-closed; 2–3 tenant presets (`US-Default`, `India-DPDP`, optionally `India-BFSI`).
5. **Persona engine v1:** slices (relationship × intent × channel × language mode), style cards, exemplar retrieval, code-controlled greeting/sign-off/length, deterministic checks + revise, model router (US Sonnet 5.5/Haiku; India Haiku `in.`), draft↔sent edit loop, learned-rules confirmation, **Persona Snapshot** (the onboarding "aha").
6. **Approval-first drafting + pre-send safety:** redaction, invented-commitment and recipient-mismatch checks, BEC warnings.
7. **Commitments ledger v0:** promises extracted from sent email and Teams chats → list + nudges drafted in the user's voice.
8. **Light delegate (EA) mode:** EA drafts in the principal's voice where delegate access already exists and the principal enabled it; activity visible to the principal.
9. **Evaluation harness** (weeks 1–2): held-out reconstruction, send-without-edit, leakage tests (release-blocking), US + India gold set.
10. **Surfaces:** Outlook add-in (XML manifest) · Teams "Draft reply" message action + minimal personal agent · **web control center** (onboarding/admin, Persona Snapshot/studio, drafts queue, commitments, privacy center, tenant admin, super-admin) also embedded as a Teams tab.
11. **Server-side drafts** behind the opt-in "Compose" app registration (`Mail.ReadWrite`) for design partners who approve it (covers Outlook mobile).
12. **Security baseline:** no-egress data plane, content-free logs, Bedrock invocation logging off, Guardrails on every call, output gate, quarantined reader, canary-tenant isolation tests, external pentest before the first paying tenant.
13. **Legal/trust pack:** MSA/ToS (with no-brick/exit terms), AUP, DPA (US + India annexes), sub-processor list, privacy policy, AI transparency notice, recording-notice templates, customer DPIA template, trust-centre page [R07 §13.2, R08 §9].

### 2.2 Conditional
14. **Team ≥ 5 — Teams meeting memory v1:** Graph post-meeting transcripts (internal Teams meetings) → episodes → typed memory atoms (decisions, action items, commitments, requirements, ideas) → **recall Q&A** with citations on AgentCore; onboarding health checks for Transcript API access + speaker attribution [R02].
15. **Team of 6 (dedicated mobile engineer) — recorder alpha:** iOS + Android work-session / meeting-prompt / quick-capture modes, Silero VAD → Opus → encrypted in-region upload, Transcribe batch behind `AsrEngine`, calendar-bounded sessions, consent prompt → full or self-only capture, consent ledger, per-OEM Android wizard, heartbeat; **dogfood and 1–2 design partners only**; start the 12-hour STT bake-off [R06].

### 2.3 Explicitly out of the MVP
Windows/Mac companions · bot-free desktop capture of external meetings (stretch only if a design partner insists — see §6) · meeting bots · voiceprints/speaker enrolment · autonomous or server-side sending · Slack (closed by its API terms) and Gmail · Neptune/OpenSearch · per-user fine-tuning · Mode B raw vault (data model designed, not built) · BYOK/XKS · Delivery Pack · hardware.

---

## 3. Team shapes

| Seat | Team of 4 | Team of 6 | Focus |
|---|---|---|---|
| **Tech lead / platform** | ✅ | ✅ | CDK cells, accounts, CI/CD, identity (Entra, AgentCore Identity), observability, cost metering |
| **Security & redaction engineer** (full-time from day 1 [R10]) | ✅ | ✅ | Detector library, vault, privacy gate, output gate, isolation tests, pentest, SOC 2 readiness |
| **AI/backend engineer** | ✅ | ✅ | Ingestion, labelling, persona engine, drafting service, commitments, eval harness |
| **Full-stack engineer** | ✅ | ✅ | Outlook add-in, Teams app/agent front-end, web control center |
| **AI/memory engineer** | — (meeting memory moves to v1.5) | ✅ | Memory engine, AgentCore agent, transcripts, recall Q&A |
| **Mobile engineer** | — (recorder in Phase 2) | ✅ | Recorder apps + STT pipeline (alpha) |
| Founders (non-engineering) | | | 6–8 design-partner LOIs, Microsoft & AWS partner programs, counsel (US + India), pricing, security questionnaires |

A fractional CISO/advisor for customer security reviews is strongly recommended [R10 §11.3]. With **5 engineers**, take the AI/memory seat (meeting memory in the MVP) and keep the recorder in Phase 2. **With 4 engineers**, expect ~14–16 weeks for the wedge, or move server-side drafts and the Teams agent to v1.5.

---

## 4. Week-by-week plan (12 weeks)

| Weeks | Engineering | Founders / GTM / legal |
|---|---|---|
| **0–1 (spikes + foundations)** | AWS Org/Control Tower, two cell skeletons, CI/CD · Entra app registrations · **Spikes:** Teams deep-link prefill in existing chats; add-in insert/read across new Outlook/classic/OWA/Mac; `uniqueBody` in delta + `MSIP_Labels` on Sent Items; transcript API with Transcript-API-access/speaker-attribution ON/OFF; `createReply` visibility on Outlook mobile; AgentCore Identity with multi-tenant Entra tokens; Sonnet 5.5 (US geo) and Haiku `in.` latency [R02, R01, R03] | Partner Center + **publisher verification**; start **Publisher Attestation**; engage **US privacy/litigation counsel and Indian counsel** [R07 §13.4]; **trademark search / naming decision**; start **6–8 design-partner LOIs** (~4 India mid-tier IT services/GCC delivery orgs, ~3–4 US mid-market IT services/consulting) [R09 §7.5] |
| **1–2** | **Eval harness** (held-out reconstruction, stylometrics, leakage suite) · mail backfill (delta) + privacy gate v0 (Tier R validators + secrets) · data model + RLS · add-in skeleton | Design-partner agreements (pilot terms, data-use grant, success criteria); US + India gold-set labelling (800 messages) |
| **3–4** | Teams ingestion + relationship labelling + intents (Haiku) · style cards v1 + drafting service v1 + router · NER ensemble + gazetteer + vault v1 · add-in drafting E2E (internal dogfood) · **India cell parity** | Draft MSA (incl. no-brick/exit terms)/AUP/DPA + sub-processor list; security questionnaire pack; **book the external pentest** (lead times are weeks) |
| **5–6** | **Edit loop** (draft↔sent diff → candidate rules) · **commitments ledger v0** · opt-in **server-side drafts** · **Teams "Draft reply" action** + minimal agent · onboarding wizard with live health checks · output gate + injection corpus v1 · *(team ≥ 5: Graph transcripts → episodes → atoms)* | Trust-centre page; consent/notice templates (English + Hindi); SOC 2 Type I readiness tooling |
| **7–8** | **Persona Snapshot** + persona studio + drafts queue + privacy center + tenant admin console · light delegate mode · **L0-vs-L1 persona A/B** · **India Haiku-vs-Sonnet gap measurement** · canary-tenant isolation tests in CI · *(team ≥ 5: recall Q&A agent on AgentCore)* · *(team of 6: recorder alpha + Transcribe pipeline)* | Pricing conversations (US $35/$49/$65; India ₹1,499/₹2,199/₹3,299/₹3,999) [R09]; Marketplace listing prep |
| **9–10** | **Pilots start** (dogfood → partners) · recall gates on US + India sets · fail-closed chaos tests · BEC guardrails · super-admin console + JIT break-glass · **external pentest** (web, add-in, Teams app, cloud; mobile if in scope) · *(team of 6: recorder alpha with 1–2 partners; STT bake-off)* | CERT-In and DPDP incident runbooks |
| **11–12** | Pilot hardening · **pentest remediation + retest** · cost tuning (router thresholds, Q&A depth caps) · go/no-go review | Convert partners to **30-day paid pilots** (10–50 seats; credited to annual) [R09] |

---

### 4.1 Hidden work and budget to plan for (red-team finding RT-M7)
| Item | Why it bites | Plan |
|---|---|---|
| Microsoft publisher verification + Publisher Attestation | Needs a verified Partner Center business account; days to weeks | Start week 0 (founders) |
| Azure Bot registration for the Teams agent | Required even though hosting is on AWS | Week 0–1 spike |
| Gold-set labelling (800 US + India messages) and Indian raters for Hinglish | Someone must label consented data; needs budget and privacy controls | Contract labellers or founders + partners' volunteers; weeks 2–4 |
| External pentest | Booking lead time + remediation window before paid pilots | Book by week 4; test weeks 9–10; fix weeks 11–12 |
| App Store / Play review (recorder) | Recording apps get extra scrutiny; FGS video declaration on Play | Only if the recorder alpha is in scope; reviewer demo tenant |
| India entity with GSTIN, US entity, marketplace seller accounts | Needed to invoice Indian customers and to list on AWS/Microsoft marketplaces | Founders, in parallel; tax advice |
| SOC 2 tooling + auditor, counsel (US + India), Microsoft 365 Certification later | Real cash costs before revenue | Budget explicitly (see `05-decisions-and-open-questions.md` §3) |
| On-call and incident response | CERT-In's 6-hour clock applies from the first India tenant | Rota + runbooks before the first India pilot |

## 5. MVP exit criteria (go / no-go for paid pilots)

| Area | Criterion |
|---|---|
| **Persona quality** | **Send-without-edit (≤ 5% character edits) ≥ 25% by pilot week 4**, light-edit (< 20%) ≥ 55%, "sounds like me" ≥ 4.0/5 — trending to ≥ 40% send-without-edit at scale [R09 §8.5]; Hinglish slices launched only behind their own quality gate [R05] |
| **Follow-through** | Commitments captured ≥ 5 per weekly active user per week at ≥ 80% precision [R09] |
| **Privacy & safety** | Zero Tier R leaks in the CI suite; recall gates met (≥ 99.9% checksum IDs, ≥ 95% Indian names, ≥ 93% Hinglish, ≤ 0.1% doc-level leakage) [R10]; contextual-integrity tests pass (release-blocking); 0 successful exfiltration on the injection corpus; pentest has no open high/critical findings |
| **Isolation** | 0 cross-tenant canary hits; all IDOR/authz matrix tests pass |
| **Performance** | p95 first token ≤ 2.5 s for US drafts *(target from [R03])*; India measured and shared with partners; backfill makes the persona usable within the first hour |
| **Reliability** | Webhooks acknowledged < 3 s; delete propagation ≤ 24 h verified; subscription renewal health ≥ 99% |
| **Adoption** | Activation ≥ 70% (persona built + first draft used within 7 days); weekly active ≥ 60% of enrolled pilot users; admin approval rate ≥ 30% of consent requests [R09] |
| **Commercial** | ≥ 6 signed LOIs; ≥ 4 pilots meeting written success criteria by month 5; first 3–5 paid annual contracts by month 5 [R09 §7.5] |
| **Unit economics** | Measured COGS per active user within the modelled range (`02-solution-architecture.md` §13); onboarding cost per pilot user tracked (≈ $25 each — qualify pilots tightly) |

---

## 6. Decisions to take before week 1

| Decision | Recommendation | Why |
|---|---|---|
| Recorder in MVP? | **Alpha only with a dedicated mobile engineer (team of 6), dogfood + 1–2 partners; otherwise Phase 2.** Instrument hardware-gate metrics from day one (missed-capture rate, in-person capture hours, memory queries/user/week) | Highest legal risk and 10–14 ew; Graph transcripts already cover internal Teams meetings; market says capture comes after the wedge [R07, R09, R08] |
| External-company meeting capture in MVP? | **No by default.** If a design partner insists: a minimal Windows recorder (+3–4 ew via Recall Desktop SDK, or 6–8 ew in-house) with mandatory disclosure, indicator and consent ledger | *Chamberlain v. Granola* targets bot-free capture; Recall has no India region [R02, R07] |
| Server-side drafts (`Mail.ReadWrite`)? | **Yes, opt-in** via a separate "Compose" app registration | Only way to reach Outlook mobile; keeps the default consent minimal [R01, R02] |
| India model default | **Haiku 4.5 `in.`** (in-country); global Sonnet 5.5 only by tenant-admin opt-in; never for BFSI | Residency vs quality; measure the gap by week 8 [R03, R05, R07] |
| Pricing & packaging | **US $35 / $49 / from $65; India ₹1,499 / ₹2,199 / ₹3,299 / from ₹3,999 (excl. GST); no freemium; 30-day credited pilots** | Margin math in [R09 §6.4] |
| Product name | **Rename before public launch; file US + India trademarks** | "PersonaAgent" is an ACL 2026 research framework name [R05, R07, R09] |

---

## 7. Roadmap after the MVP

### Phase 2 — Months 4–9: "Persona Pro + work memory"
- **Persona Pro:** Teams meeting memory (if not in the MVP), **pre-meeting briefs**, **post-meeting follow-ups drafted in your voice**, cross-channel commitments, full **delegate (EA) mode** (exec approves on mobile), **MCP memory API v0** [R09].
- **IT-Services Delivery Pack beta:** requirements → BRD / user stories / SOW / change requests / status reports, synced to Jira / Azure DevOps (+$12 / +₹799 add-on) [R09].
- **Work-mode recorder beta → GA** (consent-first, Capture+ add-on) and **self-hosted STT** once ~25–65 recorder users exist per region (US first; India language routing: English → self-hosted, Hindi/Hinglish → Transcribe/Azure Central India) [R06, R09].
- **Windows companion:** write-anywhere (fixes the Teams compose-box limitation) + bot-free recorder with disclosure UX; MSIX via Intune; signed builds [R02].
- **Copilot Chat exposure** of the same agent; Agent 365 registration; Microsoft marketplace listings; **Microsoft 365 Certification** started [R01, R02, R09].
- **Hardware Phase 1 ("integrate before building")** if gate G1 is met: device-abstraction layer, Plaud SDK (US first), Omi experimental, headsets; 2-week background-BLE spike [R08].
- Enterprise readiness: BYOK, Mode B raw vault, SIEM export, Purview `processContent` DLP on drafts, enterprise app-only ingestion, per-custodian legal hold [R04, R10].
- **GTM:** AWS Marketplace listing + FTR; founding AE/SE (India) + CS lead; 2 channel partners; SOC 2 Type II window; target **10 paying customers (~600–900 seats)** by month 9 [R09].
- "Send as me" (explicit click) for Teams and Outlook under the Compose app, with AgentCore Policy approval-before-send [R10].

### Phase 3 — Months 9–12: "Enterprise and India hardening"
- Enterprise policy engine v1 (capture policies, retention, legal hold, eDiscovery export); India in-region stack hardened; **India-BFSI tier** with in-region inference only.
- ISV Accelerate application; US AE; first 1,000+-seat proposal; first GCC → US-parent expansion; target **15+ customers, ≈ $0.3M ARR (base case)** [R09].
- Mac companion; Gmail/Google Workspace (CASA) — Slack stays out under current terms [R01].

### Year 2 — "Expand and verticalise"
- Knowledge handover packs, Time Capture Pack (timesheets), team/account memory, Sales pack (CRM/ServiceNow), RFP drafting [R09 §5].
- EU cell (Frankfurt) and EU legal pack (works councils, AI Act Art. 50 marking) [R07].
- Neptune Analytics org graph / OpenSearch hybrid search for enterprise tenants **when evals show lift** [R04, R05].
- Gated v2 persona fine-tuning experiments (in-region open-weight LoRA) **only if** the seven gates in [R05 §7.11] pass — **per-tenant and customer-instructed only, never pooled across tenants** (guardrail G1).
- ISO 27001; AWS co-sell at scale; ISO 42001 later.
- **Hardware Phase 2 (pilot badges)** only after gate G2; **Phase 3 (production badge as Capture+ hardware-as-a-service)** only after gate G3 — months 15–30 [R08 §6; `01-product-strategy.md` §9].

---

## 8. KPIs to instrument from the first commit
- **Send-without-edit rate** (north star), light-edit rate, normalised edit distance, time-to-send, "sounds like me" rating — by slice (relationship × intent × channel × language).
- Admin approval rate; activation; weekly active / paid seats; drafts per active user per day; commitments captured and closed; memory questions per day; answer citation and acceptance rate; abstention rate.
- **Hardware-gate metrics:** missed-capture rate (policy-eligible meetings not captured), in-person capture hours per user, weekly capture use [R08].
- Redaction: per-class recall on rolling labelled samples; Tier R residual alerts; review-queue backlog.
- Security: injection attempts blocked; output-gate blocks; anomaly alerts; break-glass events.
- Cost: $/active user/day by component (drafting, Q&A, extraction, STT, infra); router mix; cache hit rate; onboarding cost per pilot user.
- Reliability: backfill completion time; subscription health; webhook latency; delete-propagation lag; recorder gap minutes per user-day.
