# PersonaAgent — Risk Register (v0.1)

> **Date:** 2026-10-06. Consolidates the risk sections of research tracks [R01]–[R10] (`docs/research/`).
> **Scoring:** Likelihood (L) and Impact (I) on 1–5; **inherent score = L × I** before mitigation; **residual** = expected level after the listed mitigations (H/M/L). Analyst judgement, medium confidence. *Not legal advice.*
> Review cadence: monthly in the MVP, then quarterly; re-score after every major Microsoft/AWS/legal change.

---

## 1. Top risks at a glance

| # | Risk | L×I | Residual | One-line mitigation |
|---|---|---|---|---|
| 1 | **Recording-consent class action** (wiretap/CIPA, all-party states) | 4×5 = **20** | M | Never record silently; consent ledger; external meetings & in-person OFF by default; self-only mode; no use of content for training [R07] |
| 2 | **Indirect prompt injection → data exfiltration** via inbound mail/chat/transcripts | 4×5 = **20** | M | Quarantined tool-less reader; no egress; output gate; plain-text drafts; human sends [R10] |
| 3 | **Admin-consent friction → long sales cycles, no self-serve virality** | 5×4 = **20** | M | IT-led motion; minimal read-only scopes; trust pack; verified publisher + attestation + certification [R01] |
| 4 | **Microsoft commoditises "write like me" / memory inside Copilot** | 4×4 = **16** | M | Differentiate on per-audience persona fidelity, cross-surface memory (email + Teams + meetings + in-person), governance, US/India residency, working without Copilot licences; integrate *with* Copilot as an agent [R01, R02] |
| 5 | **Cross-audience leakage in drafts** (client A's facts in a mail to client B) | 4×4 = **16** | L-M | Code-enforced audience ACLs, skeleton exemplars, leakage judge, release-blocking tests [R05, R10] |
| 6 | **Persona misuse for impersonation / BEC fraud** | 3×5 = **15** | L-M | Owner-only persona + MFA; no autonomous send; payment-change guard; anomaly detection; offboarding freeze [R07, R10] |
| 7 | **Breach of the communications corpus or OAuth token vault** | 3×5 = **15** | M | Derivatives-only storage; Tier R masked at ingestion; per-tenant keys; secretless federation; ingestion-only decrypt [R10, R04] |
| 8 | **Persona quality not good enough** (heavy edits; "sounds like AI"), esp. Teams chat & Hinglish | 3×5 = **15** | M | Eval harness from week 1; style cards + exemplars + edit-learned rules; code-controlled greetings/sign-offs; MESR north star [R05] |
| 9 | **Redaction misses Indian names / Hinglish; overclaiming accuracy** | 4×4 = **16** | M | Own detector library + gazetteer; recall gates; published quality statement; never claim 100% [R10] |
| 10 | **Unit economics: AI COGS $14–38 per active user-month** squeezes margins | 4×4 = **16** | M | Model router, Q&A depth caps, open-weight batch models, self-hosted STT, recording-hour fair use, tiered pricing [R03, R06] |
| 11 | **Small team overextended** across two pillars and two regions | 4×4 = **16** | M | Persona-first MVP; recorder beta only with ≥ 5 engineers; strict "deferred until trigger" list [MVP plan] |
| 12 | **Biometric-privacy claims** if speaker ID/voice enrolment ships | 3×5 = **15** | L | No voiceprints in the MVP; enrolment only with written release + state gating + counsel opinion [R07] |
| 13 | **Client-contract restrictions at IT-services customers** — their client MSAs/NDAs may forbid a new third-party AI processor handling client communications (added by red-team RT-C1) | 4×4 = **16** | M | Discovery in every deal; client/account scoping controls; client-assurance pack; dedicated tenancy for strict accounts |

---

## 2. Full register

### A. Legal and regulatory

| ID | Risk | L | I | Score | Mitigations | Residual | Early-warning signal | Owner |
|---|---|---|---|---|---|---|---|---|
| A1 | Wiretap / CIPA / all-party-consent class action over meeting or in-person capture. *In re Otter.AI* survived dismissal (13 Aug 2026); *Chamberlain v. Granola* (Jul 2026) targets bot-free device-audio capture; CIPA $5,000 per violation | 4 | 5 | 20 | G3–G7: never silent; disclosures + indicator; consent ledger; external meetings & in-person capture OFF by default; self-only mode; auto-pause on privileged/HR tags; G1 no independent use; AUP + customer warranties; cyber/privacy insurance | M | Demand letters; partner legal objections; plaintiff-firm activity against peers | CEO + counsel |
| A2 | Biometric claims (BIPA $1k/$5k per person, Texas CUBI, Washington, Colorado; India SPDI written consent for voice biometrics) | 3 | 5 | 15 | No voiceprints in MVP; speaker labels from Teams metadata/manual tags; counsel opinion on ephemeral filtering ("filtering paradox") before any wearer-only biometric mode | L | Feature requests for "who said what" auto-ID | CTO + counsel |
| A3 | Losing processor / service-provider status through secondary use (training, cross-tenant analytics, human review, post-termination retention) — the *Otter* "third-party eavesdropper" theory | 3 | 5 | 15 | G1 enforced in code, IAM and contracts; content-free telemetry; deletion on termination; annual third-party attestation | L-M | Any internal request to "use customer data to improve models" | CEO |
| A4 | Microsoft API Terms: email APIs only for sync/backup unless the customer **expressly and specifically** grants other use; minimisation; mirror deletions; delete on abandonment; Microsoft can terminate access | 3 | 4 | 12 | G2 express grant captured in the admin-consent flow and MSA/DPA; lineage + 24 h delete cascade; abandonment deletion job | M | Microsoft partner/compliance inquiries; ToU revisions | CEO |
| A5 | India readiness: CERT-In 6-hour reporting + 180-day India logs **now**; SPDI written consent now; DPDP full obligations from 13 May 2027 (72-hour breach notice; penalties up to ₹250 crore) | 2 | 4 | 8 | India cell; India log copies ≥ 180 days; CERT-In runbook; English + Hindi notices; DPDP gap assessment Q1 2027 | L | Customer audits; regulator FAQs | Security lead + Indian counsel |
| A6 | Sector rules: FINRA/SEC recordkeeping; HIPAA; RBI/SEBI/IRDAI localisation and outsourcing | 2 | 4 | 8 | G21 tenant gating (no healthcare without BAA, no public sector/defence/schools in v1); India-only processing flag mandatory for BFSI; regulated-recordkeeping mode later | L | RFP clauses from BFSI/healthcare | Sales + counsel |
| A7 | Workplace-monitoring & AI-governance rules (NY/CT/DE notices, California CPPA risk assessments/ADMT, Colorado; EU works councils and AI Act later) | 3 | 3 | 9 | G11 (no voice emotion, no per-employee analytics); G17 notice pack; DPIA template; EU deferred | L-M | Customer HR/works-council pushback | Counsel |
| A8 | eDiscovery / spoliation / privilege (auto-delete during a hold; privileged meetings captured; AI summaries as evidence) | 3 | 3 | 9 | G15 legal hold overrides all deletion; privileged-tag auto-pause; AI-generated labels + source links | L-M | Legal-hold requests from customers | Product + counsel |
| A9 | Trademark conflict: "PersonaAgent" is also an ACL 2026 research framework name | 3 | 2 | 6 | Clearance search now; rename before public launch if needed | L | Search results/SEO collisions | Founders |
| A10 | AI-disclosure rules tighten (EU Art. 50 machine-readable marking; autonomous-send disclosure rules) | 2 | 3 | 6 | Invisible `X-AI-Assisted` marker; optional visible footer; no autonomous send | L | New state/EU guidance | Product |
| A11 | **Client-contract restrictions (beachhead-specific):** IT-services firms' client MSAs/SOWs/NDAs and offshore-delivery security schedules often restrict sharing client confidential information with new third-party processors or AI tools — and our wedge ingests exactly those client communications | 4 | 4 | 16 | Discovery question in every design-partner deal; client/account scoping (exclude or allow-list client domains/accounts); per-client Tier C dictionaries; a client-assurance pack (DPA flow-down, sub-processor list, no-training statement) customers can share with their clients; dedicated tenancy/BYOC for strict accounts; start with internal + approved accounts | M | Pilots stalled at customer legal; client objections | CEO + counsel |

### B. Platform dependency

| ID | Risk | L | I | Score | Mitigations | Residual | Early-warning signal | Owner |
|---|---|---|---|---|---|---|---|---|
| B1 | Microsoft tightens defaults or APIs again (precedents: managed consent policy late 2025; Teams Transcript API access default OFF since ~29 Jul 2026; external bots labelled "Unverified") | 3 | 4 | 12 | Minimal scopes; onboarding health checks; Message Center watch; Microsoft partner relationship; Agent 365-ready design | M | Message Center posts; Graph deprecations | Tech lead |
| B2 | Copilot ships native "sound like me" / memory (status unverified) | 4 | 4 | 16 | Differentiation (see top-12 #4); integrate as a Copilot Chat agent; target tenants without Copilot licences; US/India residency and governance | M | Microsoft Ignite/Build announcements | CEO + product |
| B3 | Teams has no plain-text compose-box API → clunkier Teams drafting | 5 | 2 | 10 | Deep-link prefill (validate week 1); polished Copy flow; Windows companion in Phase 2 | L-M | Low Teams draft usage | Product |
| B4 | Apple/Google policy friction: App Review 2.5.14/2.5.4, Play "monitoring tool"/stalkerware classes, FGS declarations | 3 | 4 | 12 | Recordings private to the user; visible state everywhere; explicit consent; reviewer demo tenant; no silent-audio keep-alive; no Accessibility API | M | Review rejections | Mobile lead |
| B5 | AWS service churn (CloudTrail Lake and Audit Manager closed to new customers; AgentCore repriced twice in Sep–Oct 2026) | 4 | 2 | 8 | Abstract behind our interfaces; quarterly cost-model re-run; pin SDKs; monthly "what changed" review | L | AWS What's New | Tech lead |
| B6 | **No in-India Sonnet/Opus 5.5** (only Haiku 4.5 / Opus 5 `in.`) caps India quality under strict residency; AgentCore built-ins route cross-region by default | 4 | 3 | 12 | Haiku `in.` default; measure gap by week 8; governed global opt-in for non-BFSI; overrides for AgentCore built-ins; watch model cards | M | MESR gap ≥ 10 points | AI lead |
| B7 | Third-party meeting bots blocked in Teams (auto-block from Aug 2026) | 4 | 2 | 8 | Don't depend on bots; Graph transcripts + desktop/phone capture | L | — | Product |
| B8 | **Model-vendor concentration** (Anthropic Claude via Amazon Bedrock): price changes, regional availability (no in-India Sonnet), capacity/quotas, model retirements | 3 | 4 | 12 | Model abstraction in the router; evaluated fallbacks (in-region open-weight models such as gpt-oss/Qwen, Amazon Nova); per-slice evals so a switch is measurable; private offer for capacity | M | Quota errors; price or deprecation notices | AI lead |

### C. Security and privacy

| ID | Risk | L | I | Score | Mitigations | Residual | Early-warning signal | Owner |
|---|---|---|---|---|---|---|---|---|
| C1 | Indirect prompt injection → exfiltration (EchoLeak CVSS 9.3; ForcedLeak 9.4; adaptive attacks beat most published defences > 90%) | 4 | 5 | 20 | Quarantined reader; no data-plane egress; output gate; CSP/no remote content; no tools that send; injection corpus in CI; external red team | M | Output-gate blocks; anomaly alerts | Security lead |
| C2 | Memory poisoning / persona hijack (ZombieAgent; 31 companies planting memory instructions, Feb 2026) | 3 | 5 | 15 | Validated memory writes; reject imperatives; provenance + trust; style only from sent items; quarantine payment/contact changes; user memory review | L-M | Quarantine-queue spikes | Security lead |
| C3 | Cross-audience leakage (26–39% baseline even when instructed) | 4 | 4 | 16 | Audience ACLs; skeleton exemplars; leakage judge; T6 release gate | L-M | Leakage-test regressions | AI lead |
| C4 | Cross-tenant leakage (shared indexes, caches, prompt caches) | 2 | 5 | 10 | One key + bucket per tenant, per-user index, RLS, tenant-scoped caches, canary tenants in CI | L | Canary hits | Security lead |
| C5 | OAuth token-vault theft (Salesloft-Drift pattern) | 3 | 5 | 15 | Secretless workload federation; CMK-encrypted vault; ingestion-only decrypt; per-tenant revoke-all; decrypt anomaly alerts | M | Unusual decrypt volume | Security lead |
| C6 | Insider access by our staff | 2 | 5 | 10 | No standing access; customer-approved, recorded break-glass; vault keys deny humans; Enterprise Nitro Enclave vault | L | Break-glass requests | CTO |
| C7 | Redaction misses (Indian names, Hinglish, novel ID formats) and overclaiming | 4 | 4 | 16 | Detector library + gazetteer + NER ensemble; verify pass; fail-closed; recall gates; quality statement; tenant review queue | M | Rolling recall below gate | Security lead |
| C8 | Lost/stolen phones with buffered audio | 3 | 3 | 9 | ≤ 24 h encrypted buffer; app lock; remote wipe; no backups | L | Device-loss reports | Mobile lead |
| C9 | Supply-chain compromise (packages, MCP servers, CI) | 3 | 4 | 12 | Hash pinning; registry cool-down; SHA-pinned CI; no third-party MCP servers in the data plane; SBOM | L-M | Dependency alerts | Tech lead |
| C10 | Denial of wallet (inbox floods, giant threads) | 3 | 3 | 9 | Size caps; per-tenant budgets; circuit breakers; cost alarms | L | Cost anomalies | Tech lead |

### D. AI quality and product

| ID | Risk | L | I | Score | Mitigations | Residual | Early-warning signal | Owner |
|---|---|---|---|---|---|---|---|---|
| D1 | Persona quality insufficient (chat/Hinglish hardest; imitations of email are strong, informal writing weak) | 3 | 5 | 15 | Eval harness; slices; edit loop; anti-pattern suppression; Hinglish behind its own gate | M | MESR flat after 4 weeks | AI lead |
| D2 | Invented commitments / hallucinated facts in drafts | 3 | 4 | 12 | Commitment/date detector; highlight unsupported claims; "no invented commitments" metric | L-M | User reports | AI lead |
| D3 | Wrong register (incomplete org charts; Hinglish to a client) | 3 | 3 | 9 | Deterministic labels; user confirms top contacts; unknown → formal; Hinglish only where the user already used it | L | Edit patterns on greetings | AI lead |
| D4 | Speaker misattribution corrupts meeting memory | 4 | 3 | 12 | Calendar-bounded speaker counts; confidence labels; cite audio; easy relabel | M | Corrections rate | AI lead |
| D5 | STT accuracy on Indian English / Hindi / Hinglish unknown | 4 | 3 | 12 | 12 h bake-off weeks 2–6; language routing; show citations with audio | M | WER/CER on eval set | AI lead |
| D6 | Recording gaps on Android OEMs (most of the Indian market) | 4 | 3 | 12 | Per-OEM wizard; heartbeat; gap UI; supported-device list | M | Gap minutes per user-day | Mobile lead |
| D7 | Automation complacency (users rubber-stamp drafts) | 3 | 3 | 9 | Highlight changed facts/recipients; BEC warnings; friction on risky drafts | L-M | Very low edit rates on risky drafts | Product |
| D8 | **Executives label or encrypt most of their mail** → excluded content makes personas weakest for the most valuable users [R01] | 3 | 3 | 9 | Explain coverage; let users approve sample messages for learning; lean on Teams chats and the draft↔sent edit loop | L-M | Low learning coverage for exec users | AI lead |

### E. Commercial and market

| ID | Risk | L | I | Score | Mitigations | Residual | Early-warning signal | Owner |
|---|---|---|---|---|---|---|---|---|
| E1 | Admin-consent friction → long sales cycles; no bottom-up virality | 5 | 4 | 20 | "Admin-approval-led growth": minimal read-only scopes; pilot groups; trust pack; certification; **6–8 design-partner LOIs before the MVP ships** [R09 §7] | M | Admin approval rate < 30% of consent requests | CEO |
| E2 | Security teams reject whole-mailbox access for a startup | 3 | 4 | 12 | Read-only, audit to customer SIEM, data minimisation, app-only RBAC option, SOC 2 roadmap, Exchange RBAC-for-Applications guidance | M | Security-review losses | CEO + security lead |
| E3 | **Platform bundling / commoditisation:** Gmail made style-matched replies free (8 Jan 2026); Copilot has 30M+ paid seats and "sound like you" (typed instructions today — automatic sent-mail style learning expected within 12–24 months, analyst judgement); E7 suite at $99 | 4 | 5 | 20 | Measured relationship-level fidelity; follow-through ledger; delegation; US + India governance; IT-services Delivery Pack; ship *inside* Copilot Chat / Agent 365; MCP memory API [R09 §8.7] | M | Microsoft announces sent-mail style learning or per-recipient tone | CEO |
| E4 | **Fast, well-funded specialists:** Superhuman (Grammarly; > $700M revenue; bought Fathom 14 Sep 2026), Fyxer ($1M → $17M ARR in ~8 months; enterprise tier), Granola ($1.5B), Viven ($35M seed; employee twins) | 4 | 4 | 16 | One beachhead (IT services, US + India), compliance moat, workflow lock-in (approvals, commitments, Delivery Pack), IT-services firms as resellers | M | Competitor push into M365 mid-market / India | CEO |
| E5 | **Pricing vs COGS:** gross margin 49–58% at today's AI costs (US) and 36–45% (India); Capture+ on Amazon Transcribe is −62% | 4 | 4 | 16 | Fair-use caps, premium-draft quotas, Power/Capture+ add-ons, router, caching, batch, drafting on demand, self-hosted STT (breakeven ~25–65 recorder users/region); **never price US Persona below $30** [R09 §6.4] | M | COGS > 30% of ARPU (US) / > 40% (India) | CEO |
| E6 | **India margin constraint:** COGS is in USD and about equal to the US while list prices are ~25–30% lower | 4 | 3 | 12 | Lite tier + caps + annual prepay instead of deep discounts; Haiku-only India SKUs; volume discount floor −20%; lower India sales/CS costs | M | Optimised India GM < 55% | CEO |
| E7 | Buyers' legal departments block the recording pillar; employee-surveillance perception | 3 | 4 | 12 | Persona + Teams-transcript memory first; Capture+ as a consent-first add-on; "always-ready, policy-governed work capture" language [R08] | M | Pilot scope reductions | CEO |
| E8 | Price compression (~10–15%/year in horizontal tiers as model costs fall — estimate) | 3 | 3 | 9 | Shift the mix to Pro, packs and Enterprise; bank model deflation as margin first | L-M | Competitor price cuts | CEO |
| E9 | Slow enterprise cycles and India payment terms (net 45–90, TDS) strain cash | 3 | 3 | 9 | Annual prepay with quarterly billing; AWS Marketplace private offers; Indian entity with GSTIN | L-M | DSO > 75 days | CEO |
| E10 | Big-tech consolidation in AI recorders (Bee → Amazon, Limitless → Meta) raises buyer expectations ("no-brick", exit terms) | 3 | 3 | 9 | No-brick/exit terms in the MSA from day one; open-format export | L | RFP clauses | CEO |

### F. Technical and operational

| ID | Risk | L | I | Score | Mitigations | Residual | Early-warning signal | Owner |
|---|---|---|---|---|---|---|---|---|
| F1 | Teams throttling/quotas at scale (20 rps/tenant; 1 rps/chat; 10k subscriptions per org shared across vendors) | 4 | 3 | 12 | Wave onboarding; chat-level dedupe; rich notifications; app-only export option | M | Backfill SLA misses | Tech lead |
| F2 | AgentCore quotas at launch (25 new sessions/s/account; Memory ingest 10 TPS) | 3 | 3 | 9 | Session reuse; early quota increases; no backfill through AgentCore Memory | L | Throttling errors | Tech lead |
| F3 | India DR degraded (Hyderabad lacks several services) | 2 | 4 | 8 | State "data recovery + degraded service" in contracts; Mumbai multi-AZ; backups in-country | L-M | — | Tech lead |
| F4 | S3 Vectors is new (no documented CRR/AWS Backup) | 2 | 3 | 6 | Nightly vector export; re-embedding runbook (RTO driven by re-embedding) | L | — | Tech lead |
| F5 | Cost overrun (managed STT at scale, long Q&A loops, pre-generation) | 3 | 4 | 12 | Per-tenant budgets; batch by default; self-host STT; pre-generate only reply-likely mail | M | $/user/day trending up | Tech lead |
| F6 | Refresh-token expiry/revocation causes silent sync gaps | 4 | 3 | 12 | Per-user health monitor; re-auth nudges; coverage indicator | L-M | Sync health < 99% | Tech lead |

### G. Hardware (Phase 4, gated)

| ID | Risk | L | I | Score | Mitigations | Residual |
|---|---|---|---|---|---|---|
| G1 | Repeating Humane/Rabbit failure modes: no killer use case, phone-replacement ambition, cloud latency, heat/battery, overpromised demos, hard-coded keys, bricking customers | gated | 5 | — | Phone-first; companion, not replacement; gates G1–G3 (`01-product-strategy.md` §9.4) with **kill after a gate is missed twice**; no staged demos; Hardware Trust Spec; no-brick terms [R08] | Gated |
| G2 | The background-BLE assumption fails (iOS gives ~10 s wake windows and doesn't relaunch force-quit apps) — the main reason to build a device | 3 | 4 | 12 | 2-week spike before any hardware commitment; on-device buffer + store-and-forward; stop if it fails on iOS or top-5 Android OEMs | — |
| G3 | Certification delays / classification ambiguity in India (WPC ETA, BIS) — Rabbit's India launch stalled on regulation | 3 | 4 | 12 | Start ≥ 6 months before India shipments; Authorised Indian Representative; US-only pilots until approvals are in hand | L-M |
| G4 | Partner-device dependency (maker acquired or cuts regions — the Limitless precedent) | 3 | 3 | 9 | Device-abstraction layer; multiple partners; Omi open design as fallback | L-M |
| G5 | Battery/supply-chain recall (Humane's charging-case recall outlived the company) | 2 | 4 | 8 | Certified cells, UN38.3, recall playbook, serialised fleet tracking | L |
| G6 | Hardware distracts a 3–6 engineer team; AI cost ($15–27/user-month) squeezes hardware margin | 3 | 4 | 12 | ≤ 0.5 FTE until G2; 18 months of runway excluding hardware revenue; ≥ 50% HaaS margin gate | L-M |
| G7 | Client sites ban recording devices (secure delivery floors at Indian IT-services firms) | 4 | 3 | 12 | Policy geofences/auto-off; "secure-floor mode"; target roles that work outside secure floors | M |

### H. Execution

| ID | Risk | L | I | Score | Mitigations | Residual |
|---|---|---|---|---|---|---|
| H1 | Small team overextended across two pillars, two regions | 4 | 4 | 16 | Persona-first MVP; deferred-until-trigger list; recorder beta only with ≥ 5 engineers | M |
| H2 | Founder bandwidth consumed by security reviews, counsel, partner programs | 3 | 3 | 9 | Fractional CISO; trust-centre self-serve; standard questionnaire pack | L-M |
| H3 | Key-person dependency on the security/redaction engineer | 3 | 3 | 9 | Documentation, pairing, detector library as code with tests | L-M |
| H4 | **Funding/runway:** the base case implies ~35–50 FTE and ~$10–15M of venture funding by Y3; hardware gates require 18 months of runway excluding hardware revenue [R09, R08] | 3 | 4 | 12 | Stage-gated hiring; pilots credited to annual contracts; AWS/Microsoft programme credits; raise against design-partner LOIs and pilot metrics | M |
