# PersonaAgent — Product Strategy (v0.1)

> **Date:** 2026-10-06 · **Founder decisions:** M365 mid-market & enterprise buyers · US + India · 3–6 engineers, ~3-month MVP · work-only, company-governed recorder · Phase-1 redaction precise to US + Indian regulation.
> **Sources:** research tracks in `docs/research/` cited as [R01]…[R10]; Humane/Rabbit/wearables fact sheets in `docs/research/_raw/`. Market numbers and prices were checked in Oct 2026 where marked in [R09]; estimates are labelled.

---

## 0. Strategy on one page

| Question | Answer |
|---|---|
| **The bet** | Knowledge workers in Microsoft 365 will pay for an assistant that **writes exactly like them, per relationship**, and **remembers and follows through** on what they said across email, Teams and meetings — governed tightly enough that their IT, security and legal teams say yes. |
| **Why now** | Copilot is in only ~6.5% of M365 commercial seats (30M+ of ~450M, Jul 2026) and its "sound like you" works from typed instructions — it does not learn from sent mail or adapt per recipient [R09]. Buyers already pay above Copilot's $30 for inbox AI (Fyxer $37–64/user, $1M→$17M ARR in ~8 months of 2025). India's DPDP obligations start **13 May 2027** — a buying trigger for "India-resident, DPDP-ready AI" [R07, R09]. |
| **Beachhead (one segment, two countries)** | **Client-facing delivery, account and leadership teams (and their EAs) at M365-standardised IT-services and technology-consulting firms** — US mid-market (500–10,000 employees); India mid-tier IT services (1,000–20,000) and GCC delivery centres. Scored 4.3 / 4.1 of 5, highest of ten segments [R09 §8]. |
| **Wedge** | **"Persona + Follow-through" for client communication in Outlook and Teams:** relationship-aware drafts, approval-first, pre-send safety, a commitments ledger, light EA/delegate mode. Then Teams meeting memory, then an IT-services Delivery Pack, then governed work-mode capture [R09 §8.3]. |
| **Positioning** | **"The voice and follow-through layer for Microsoft 365 — works with or without Copilot."** Ship as a Copilot Chat agent, register in Agent 365, expose an MCP memory API [R09 §9]. |
| **Pricing (annual, per user/month)** | US: **Persona $35 · Pro $49 · Enterprise from $65**. India (excl. 18% GST, India-resident processing): **Lite ₹1,499 · Persona ₹2,199 · Pro ₹3,299 · Enterprise from ₹3,999**. Add-ons: Capture+, Delivery Pack, Power user, dedicated/BYOC. No freemium — 30-day pilots credited to annual contracts [R09 §6]. |
| **Unit economics** | ~49–58% gross margin at today's AI costs → **~64–70% (US) and ~55–60% (India) after optimisation** (model routing, caching, batch, drafting on demand, self-hosted STT) [R09 §6.4, R03, R06]. |
| **GTM** | Admin-approval-led growth (users can no longer self-consent to mail/chat scopes [R01]); 6–8 design-partner LOIs before the MVP ships; first 3–5 paid by month 5, 10 by month 9, 15+ (~$0.3M ARR) by month 12; AWS Marketplace private offers + co-sell first [R09 §7]. |
| **3-year outlook (exit ARR)** | Conservative ~$2.7M · **Base ~$13.4M (~35k seats, ~50/50 US/India)** · Aggressive ~$49M [R09 §8.6]. |
| **Biggest strategic risk** | Microsoft/Google bundling automatic style learning (Gmail made style-matched replies free on 8 Jan 2026). The moat must be relationship-level fidelity, follow-through, delegation, governance (US + India), and vertical workflow [R09]. |
| **Hardware** | Not before the software habit is proven. Phone first; partner devices before our own; strict go/no-go gates — the lesson of Humane and Rabbit (§9). |

---

## 1. Market and timing

**What changed in 2025–2026** [R09 §1–2]
- **Free "write like me" arrived on Gmail** (style-matched Suggested Replies and Help Me Write free for all users, 8 Jan 2026). Expect the same pressure on Microsoft within 12–24 months (analyst judgement — no public roadmap found).
- **Copilot is big but thin:** 30M+ paid seats (Jul 2026) ≈ 6.5% of ~450M+ M365 commercial seats; $30/user, Copilot Business (≤ 300 seats) $21 list / $18 promo; the new **E7 suite at $99** bundles Copilot and Agent 365 ($15 standalone).
- **Inbox AI commands premium prices:** Fyxer $37–64 annual / $49–99 monthly; Superhuman (Grammarly renamed itself Superhuman in Oct 2025; >$700M revenue) suite $33 and bought Fathom on 14 Sep 2026; Shortwave $30/$45/$120 by model tier.
- **Meeting notes commoditised; the value moved to memory, follow-through and verticals:** Otter ~$100M ARR; Plaud >$100M software ARR and 2M+ devices; Granola $1.5B valuation; Fireflies $1B; vertical players Jump ($80M Series B, financial advisors) and Zocks ($45M). Meta bought Limitless (Dec 2025); Amazon bought Bee (Jul 2025).
- **Recording is under legal attack:** *In re Otter.AI* survived dismissal on 13 Aug 2026; *Chamberlain v. Granola* (Jul 2026) targets bot-free device capture; BIPA suits against Fireflies [R07 §3].
- **"Digital twins of employees" got funded:** Viven ($35M seed; Genpact an early user) — the main threat to org-memory and out-of-office-twin ideas.

**Market size (estimates; country-level M365 seat counts are not public)** [R09 §3]
- Persona drafting (+ follow-through): **US SAM ≈ $4.9–5.7B; India ≈ $0.5–0.8B**; the beachhead is ~2M seats.
- Standalone meeting-notes spend today ≈ $0.6–0.9B — a crowded, commoditising market we enter only as a memory input, not as another notetaker.

---

## 2. Customer

### 2.1 Beachhead and why it is one segment
**Client-facing delivery, account and leadership teams (and their EAs) at M365-standardised IT services & tech-consulting firms** — US mid-market and Indian mid-tier IT services/GCCs [R09 §8.2]:
- **Same workflow:** client email, Teams chat, status reports, requirements, SOWs, change requests, escalations — high volume, high stakes, relationship-sensitive tone.
- **Same buying centre:** delivery/practice head (economic buyer) + CIO/CISO (approvers).
- **Same stack:** Microsoft 365 + Teams; many already on AWS.
- **Natural US ↔ India bridge:** US firms run India delivery centres; Indian firms and GCCs write to US clients all day. India supplies fast design partners and volume; the US supplies ARPU; **GCCs are the bridge to US enterprise parents.**
- **Founder access:** the team's AWS/IT-services network (adjust if wrong).

**Explicit non-goals for 12 months:** healthcare, legal, financial advisors (Jump/Zocks own it), real estate, consumer lifelogging, general SMB self-serve, hardware [R09 §8.2].

### 2.2 Personas and jobs to be done
| Persona | Top jobs | What they buy |
|---|---|---|
| **Delivery / account lead** (US or India) | Answer clients fast in the right tone; keep promises; turn calls into status reports, requirements and change requests | Persona Pro + Delivery Pack |
| **Executive + EA** | Exec's voice at scale, approvals from mobile, nothing falls through the cracks | Pro (delegate mode) — the entry persona (scored 3.9) |
| **Consultant / engineer writing to clients** (often non-native English writers in India) | Polished, on-voice client communication; Hinglish only where appropriate | Persona / Lite |
| **Practice head / COO** (economic buyer) | Client satisfaction, utilisation, faster documentation, attrition-proof knowledge | Enterprise + handover |
| **CIO / CISO** (approvers) | Least privilege, residency, redaction, audit, certifications | Enterprise governance |

### 2.3 Buying reality
- **Every account starts with IT approval:** Microsoft's managed consent policy (late 2025) blocks users from self-consenting to `Mail.Read`/`Chat.Read` → "admin-approval-led growth", then expansion inside the tenant without new consent [R01, R09 §7.1].
- **Security review is the gate:** SOC 2 (Type I → II), pentest letter, DPA + AI addendum (no training on customer data), sub-processor list, permission justifications, US/India residency, DPDP/CERT-In pack, Exchange RBAC-for-Applications guidance [R09 §9].
- **Client contracts gate the beachhead:** IT-services firms often need contractual cover — sometimes their *clients'* approval — before a new third-party AI processor handles client communications. Every design-partner deal starts with this discovery; the product ships **client/account scoping controls** (exclude or allow-list client domains/accounts) and a **client-assurance pack** customers can share with their clients (red-team RT-C1, `06-red-team-review.md`).

---

## 3. Product

### 3.1 Product principles
1. **In place, not instead** — Outlook and Teams stay the tools; we add voice and memory (`02-solution-architecture.md` §3).
2. **Approval-first** — the human sends; delegate actions are visible to the principal.
3. **Measured fidelity** — every user sees their own send-without-edit and edit-distance trend; we publish a Voice Fidelity Benchmark.
4. **Governance is a feature** — residency, redaction profiles, capture policies, audit, legal hold are sold, not hidden.
5. **Consent-first memory** — Microsoft's own transcripts before our own capture; capture is user-started and visible.

### 3.2 Pillar 1 — Persona + Follow-through (the wedge)
| Capability | MVP | v1.5 | Later |
|---|---|---|---|
| Persona learned from Sent Items + Teams chats, **per relationship × intent × channel × language** | ✅ | Per-language personas (en-IN / Hinglish / Hindi) behind quality gates | Brand-voice layer under personal personas (Enterprise) |
| Drafts: Outlook add-in, server-side drafts (mobile), Teams "Draft reply" (Copy / prefill), Teams agent | ✅ | Copilot Chat agent; Windows write-anywhere | "Send as me" (explicit click) |
| **Approval-first + pre-send safety** (PII/secret redaction, invented commitments, recipient mismatch, BEC warnings) | ✅ | Advanced policies | Purview DLP on drafts |
| **Commitments ledger v0** (what you promised in email/chat → nudges drafted in your voice) | ✅ (email + chat) | + meetings | + in-person capture |
| **Delegate / EA mode** | Lite | Full (exec approves on mobile, audit trail) | — |
| Persona Snapshot ("how you write to your manager vs clients") — the onboarding "aha" | ✅ | — | — |
| Learned-rules digest (confirm/reject what the agent learned) | ✅ | — | — |

### 3.3 Pillar 2 — Work memory
**Language matters:** describe Pillar 2 as **"always-ready, policy-governed work capture — on during your work sessions, visibly indicated, instantly mutable,"** not "always listening." "Always listening" invites the backlash that hit Friend, Google Glass and Meta's glasses, and phones can't start the mic in the background anyway [R08 §4, R06].

| Stage | What | When | Why this order |
|---|---|---|---|
| 1 | **Teams meeting memory** from Microsoft's own transcripts (free; banner consent) → episodes, decisions, requirements, commitments → recall Q&A with citations ("what were the client's requirements in the 4 pm meeting?") | MVP if team ≥ 5, else v1.5 | Cheapest and legally safest capture path [R02, R07] |
| 2 | **Pre-meeting briefs** and **post-meeting follow-ups drafted in your voice** | v1.5 | Ties memory back to the persona — our unique combination |
| 3 | **Governed work-mode capture** on the phone (user-started work sessions, calendar-prompted meeting capture, quick capture; consent prompt → full or self-only) | Beta after MVP; Capture+ add-on | Highest legal risk; needs self-hosted STT to be margin-positive [R06, R07, R09] |
| 4 | **Windows companion** recorder for other companies' meetings (disclosure + indicator + ledger) | Phase 2 | *Granola*-type risk managed by design |
| 5 | **Team / account memory** (shared spaces per client account) | Year 2 | Org-level network effects; Viven competition |
| 6 | **Work wearable** (partner device first) | Year 2–3, gated (§9) | Humane/Rabbit lessons |

The founders' example questions map directly: *"What was that good idea I was talking about at 2 pm?"* → work-session capture → episode at ~2 pm → `idea` atoms; *"In the 4 pm meeting, what were the client's requirements?"* → calendar lookup → Teams transcript (internal) or captured session (external) → `requirement` atoms with citations and an audio snippet while audio is retained.

### 3.4 What else the market needs — and will pay for (ranked) [R09 §5]
Scores 1–5 for willingness to pay (WTP), defensibility (Def), fit with both pillars (Fit), ease for a small team (Ease), legal/trust safety (Safe).

| Rank | Opportunity | WTP | Def | Fit | Ease | Safe | Total | Timing | Where it's monetised |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **EA / delegate mode** (EA drafts in exec's voice; exec approves on mobile) | 5 | 4 | 5 | 3 | 4 | 21 | v1 lite → v1.5 | Pro |
| 2 | **Requirements → BRD / user stories / SOW / change requests / status reports** from meetings, email and chat, synced to Jira / Azure DevOps | 5 | 4 | 5 | 3 | 4 | 21 | v1.5 | **IT-Services Delivery Pack** (+$12 / +₹799) |
| 3 | **Post-meeting follow-ups in your voice** | 4 | 3 | 5 | 5 | 4 | 21 | v1.5 | Pro |
| 4 | **Pre-meeting briefs** (relationship history, open commitments, last tone) | 3 | 3 | 5 | 5 | 5 | 21 | v1.5 | Pro |
| 5 | **Commitment / follow-up tracker** across email → Teams → meetings → in-person | 4 | 4 | 5 | 3 | 4 | 20 | **v1** | Persona (basic), Pro (cross-channel) |
| 6 | **Brand-voice governance** (org style guide under personal personas) | 4 | 3 | 4 | 4 | 5 | 20 | v1 basic → Enterprise | Enterprise |
| 7 | **Pre-send safety check** (redaction, unintended commitments, recipient mismatch) | 4 | 3 | 4 | 4 | 5 | 20 | **v1** | Included; advanced in Enterprise |
| 8 | **Personal MCP "memory layer" API** for Copilot/Claude/ChatGPT under policy | 3 | 4 | 5 | 5 | 3 | 20 | v1.5 | Pro/Enterprise, metered |
| 9 | **Multilingual persona** (Hindi/Hinglish/regional; English polish for non-native writers) | 3 | 3 | 4 | 4 | 5 | 19 | v1.5 (India) | Included (India differentiator) |
| 10 | **Knowledge handover / offboarding pack** | 4 | 4 | 5 | 3 | 3 | 19 | Year 2 | ~$250 per handover |
| 11 | RFP / proposal drafting from memory | 4 | 3 | 4 | 3 | 5 | 19 | Year 2 | Delivery Pack add-on |
| 12 | Activity-based timesheet / billable-time suggestions | 5 | 3 | 4 | 2 | 4 | 18 | Year 2 | Time Capture Pack (+$15–20) |
| 13 | Team / account "org memory" | 4 | 5 | 5 | 1 | 3 | 18 | Year 2 | Enterprise |
| 14 | Inbox triage / daily brief (table stakes) | 2 | 2 | 4 | 5 | 5 | 18 | v1.5 | Included |
| 15 | CRM / ServiceNow auto-updates | 4 | 2 | 3 | 3 | 4 | 16 | Year 2 | Sales pack |
| 16 | Communication-coaching analytics (personal first) | 3 | 3 | 4 | 3 | 2 | 15 | Year 2 | L&D add-on |
| 17 | "Out-of-office twin" | 3 | 4 | 4 | 1 | 2 | 14 | Year 2–3 (start with "queue drafts for approval") | Enterprise |
| 18 | Finance compliance recordkeeping | 4 | 4 | 2 | 1 | 1 | 12 | Partner/export only | Connector fee |
| 19 | Frontline / field hands-free notes | 3 | 2 | 3 | 1 | 3 | 12 | Year 3 (with hardware) | Device + capture plan |

Also demanded in 2025–26: **agent governance** (register in Agent 365; Copilot Chat presence), **CFO-grade ROI dashboards** (adoption, time saved, send-without-edit), **bring-your-own-model / residency** for regulated buyers, and **AI-draft authenticity and impersonation controls** [R09 §5].

### 3.5 What we will deliberately not build (now)
A mail/Teams clone; a standalone notetaker or meeting bot; consumer lifelogging; voiceprints; autonomous sending; an out-of-office twin before trust is earned; finance archiving (partner instead); our own hardware before the gates in §9.

---

## 4. Positioning and differentiation

**Positioning statement:** *For client-facing teams in Microsoft 365, PersonaAgent is the voice and follow-through layer that drafts every message the way you'd write it to that specific person, remembers what you and your clients said, and makes sure promises are kept — with US/India residency and redaction your security team will approve. Works with or without Copilot.*

| Alternative | Where it's strong | Where we win |
|---|---|---|
| **Microsoft 365 Copilot** | Native everywhere; bundled (E7) | Learns from sent mail **per relationship**; follow-through ledger; delegate voice; India-resident processing; works for the ~93% of seats without Copilot; ships *inside* Copilot Chat as an agent |
| **Gmail/Gemini** (free) | Free style-matched replies | Not in M365 shops; no cross-channel memory |
| **Superhuman (incl. Grammarly, Fathom)** | Polished client + writing assistant + notes | Outlook/Teams-native in place; relationship-level personas; governance + India |
| **Fyxer** | Proven WTP; drafts in your inbox | Enterprise governance, Teams, India residency, commitments, IT-services workflows |
| **Otter / Fireflies / Read / Granola** | Meeting notes at scale | We don't sell notes; we turn meetings into **your** follow-ups, requirements and commitments, consent-first |
| **Plaud** | Recorder hardware + subscription | Software-first, M365-integrated memory; Plaud is a possible device partner (SDK) |
| **Viven** | Employee digital twins | Narrower, trust-first scope (owner-only persona, approvals); IT-services vertical |

**Moats to build** [R09 §8.7]: org-level relationship graph and shared account context · a proprietary Voice Fidelity Benchmark + per-tenant evals · workflow lock-in (approvals, commitments, Delivery Pack templates, handover) · **US + India compliance moat** (precise redaction profiles, in-India inference, capture policies, BYOK, certifications) · verticalisation (IT services first) · distribution (AWS Marketplace/co-sell, Agent 365/Copilot Chat, IT-services firms as resellers) · memory portability via MCP (become the system of record for persona + commitments).

---

## 5. Pricing and packaging [R09 §6]

### 5.1 United States (USD per user per month)
| Tier | Annual | Monthly | Includes | Fair use |
|---|---|---|---|---|
| Pilot | Free or $2–5k (credited) | 30 days | All Pro features, 10–50 seats | Backfill 90 days |
| **Persona** | **$35** | $42 | Persona from Sent Items + Teams chats; relationship-aware styles; Outlook (incl. server-side drafts for mobile where the tenant approves the Compose permission) + Teams; approvals; basic follow-through; pre-send safety; basic org style guide; Entra SSO | ~1,500 AI actions; 150 premium drafts; 12-month memory |
| **Persona Pro** | **$49** | $59 | + Teams meeting memory & Q&A; pre-meeting briefs; post-meeting follow-ups; cross-channel commitments; delegate (EA) mode; MCP memory API; 10 h/month governed work-mode capture (once the recorder ships) | ~2,500 AI actions; 400 premium drafts |
| **Enterprise** | **from $65** (≥ 100 seats) | Annual only | + policy engine (capture, retention, legal hold, eDiscovery export); advanced redaction profiles (HIPAA/GLBA/PCI; DPDP/Aadhaar/PAN; RBI/SEBI/IRDAI in-India); SCIM; audit API; Agent 365 registration; residency; BYOK; admin analytics; SLA | Pooled credits |

*Memory horizon applies to memory atoms; raw audio is deleted after transcription by default and transcripts are kept 30 days (`02-solution-architecture.md` §8.4). "Premium drafts" = Sonnet-class drafts; everything else routes to Haiku by default (§5.4).*

### 5.2 India (INR per user per month, excl. 18% GST, India-resident processing)
| Tier | Annual | Monthly | ≈ USD (₹88/$) | Notes |
|---|---|---|---|---|
| **Persona Lite** | **₹1,499** | ₹1,799 | ≈ $17 | Reply drafting + basic follow-through; Haiku-only; 6-month memory — for IT-services/GCC volume programmes |
| **Persona** | **₹2,199** | ₹2,599 | ≈ $25 | US Persona scope; capped premium (in-India Opus 5) drafts |
| **Persona Pro** | **₹3,299** | ₹3,899 | ≈ $37.5 | US Pro scope |
| **Enterprise** | **from ₹3,999** (≥ 250 seats) | Annual only | ≈ $45 | In-India processing default; DPDP/CERT-In pack |
| Volume | −10% at 500+, −15% at 1,000+, floor −20% at 5,000+ | | | Never below ~40% GM on optimised COGS; move buyers to Lite rather than discounting |

### 5.3 Add-ons
| Add-on | US | India | Rationale |
|---|---|---|---|
| **Capture+** (governed work-mode recording, ~60 speech-h/month) | +$15 | +₹999 | Margin-positive only on self-hosted STT |
| **IT-Services Delivery Pack** (requirements → BRD/stories/SOW/CR/status; Jira/ADO) | +$12 | +₹799 | Beachhead expansion lever |
| **Power user** (2× AI actions, +500 premium drafts) | +$15 | +₹999 | Moves heavy-user cost onto heavy users |
| Sales Follow-through Pack (Y2) · Time Capture Pack (Y2) · Knowledge Handover (Y2, ~$250/handover) | — | — | Expansion |
| **Dedicated tenancy / BYOC** | Platform fee $4–10k/month + seats (min 500) | ₹3–8 lakh/month | Regulated buyers, BFSI |

### 5.4 Margin math (summary) [R09 §6.4]
| SKU (~10k users) | Price | GM at today's COGS | GM optimised |
|---|---|---|---|
| US Persona | $35 | 49% | ~64% |
| US Persona Pro | $49 | 54% | ~69% |
| US Enterprise | $65 | 58% | ~70% |
| India Persona (₹2,199) | ≈ $25 | 36% (44% with usage capped, Haiku-only) | 55–60% |
| India Persona Lite (₹1,499) | ≈ $17 | 45% | ~59% |
| Capture+ add-on | $15 | **−62% on Transcribe** | **~73% on self-hosted STT** |

**Implications:** don't price US Persona below $30; India seats run at ~55–60% GM until model prices fall (COGS is in USD and similar to the US — so use Lite + caps + annual prepay, not deep discounts); recording must run on self-hosted STT or Teams' own transcripts (self-hosting breaks even at ~25–65 recorder users per region); qualify pilots tightly because each onboarded user costs ~$25 up front; plan for ~10–15% annual price compression in horizontal tiers and shift the mix to packs and Enterprise.

**Deal guardrails:** mid-market ≤ 15% off list; enterprise ≤ 25% with multi-year + case-study rights; ramp deals over deep discounts; build AWS (1.5–3%) and Microsoft (3%) marketplace fees into list prices.

---

## 6. Go-to-market [R09 §7]

### 6.1 Motion
**Admin-approval-led growth, not classic PLG.** A user signs in → hits "needs admin approval" → that request is a sales lead → after approval, expansion inside the tenant needs no new consent. The onboarding "aha" is a private **Persona Snapshot**.

### 6.2 12-month plan (3–6 engineers)
| Window | Product | GTM | Exit criteria |
|---|---|---|---|
| **M0–M3** (Oct–Dec 2026) | MVP (see `03-mvp-plan-and-roadmap.md`) | **6–8 design-partner LOIs** (~4 India mid-tier IT services/GCC delivery orgs; ~3–4 US mid-market IT services/consulting, ideally one via an MSP); security pack v1; SOC 2 Type I readiness; pentest booked; DPA + DPDP notice; publisher verification; **name + trademark decision** | MVP live in 2 internal tenants; 6+ LOIs |
| **M3–M5** | Fidelity fixes; relationship-aware styles; pre-send safety; Persona Snapshot | **30-day pilots** (10–50 seats; $2–5k US / ₹1.5–4 lakh India, credited) | ≥ 4 pilots meet criteria; **first 3–5 paid annual contracts** |
| **M5–M9** | **Persona Pro** (meeting memory, briefs, follow-ups, delegate mode), **Delivery Pack beta**, MCP v0; self-hosted STT when recorder users justify it | **AWS Marketplace listing + FTR**; Microsoft Marketplace/Teams Store (certification started); hire founding AE/SE (India) + CS lead; 2 channel partners (1 India CSP/LSP, 1 US MSP); SOC 2 Type II window | **10 paying customers** (~600–900 seats); ≥ 60% WAU; ≥ 25–30% send-without-edit |
| **M9–M12** | Enterprise policy engine v1; India in-region stack hardened; work-mode capture beta (consent-first) | ISV Accelerate application; US AE; first 1,000+-seat proposal; first GCC → US-parent expansion | **15+ customers, ≈ $0.3M ARR (base)**; ≥ 20% seat growth within accounts |

**First 10 customers (target mix):** 6 India (4 mid-tier IT services, 2 GCCs) + 4 US (2 mid-market IT services/consulting, 1 MSP-referred professional-services firm, 1 exec/EA-led deployment); 50–100 client-facing seats each.

### 6.3 Channels (ranked for a small team)
1. **Founder-led design partners** from the team's AWS/IT-services network (own company as partner #0 if it runs M365).
2. **AWS Marketplace private offers + co-sell** (FTR after customer #2–3; ISV Accelerate later).
3. **Microsoft Marketplace / Teams Store / Agent 365** for discoverability and admin trust (+ Microsoft 365 Certification).
4. **M365 MSPs/CSPs and IT-services firms as resellers** (partner programme after month 9).

### 6.4 Region specifics
- **India:** sell to delivery/practice heads and account leaders (CIO/CISO approve); lead with client-communication quality in your own voice, status/BRD/SOW speed, attrition-proof handover and **in-India processing + DPDP readiness**; Indian entity with GSTIN (customers claim input tax credit on 18% GST); INR invoices against POs; expect net 45–90 and TDS; get tax advice on structure.
- **US:** sell to COO, delivery heads, client-services leaders and executive offices (EAs); lead with measured time saved, voice fidelity, follow-through, Copilot coexistence, SOC 2 and US residency; AWS Marketplace for procurement; MSPs for the 100–1,000-employee mid-market.

---

## 7. Revenue scenarios (exit ARR; Y1 = Oct 2026–Sep 2027) [R09 §8.6]

| Scenario | Y1 | Y2 | Y3 | Key drivers |
|---|---|---|---|---|
| **Conservative** | $0.12M (370 seats) | $1.03M (3,050) | **$2.71M** (7,800) | Pilot→paid 40%; NRR 110%; founders + 1–3 sellers |
| **Base** | $0.32M (940) | $3.28M (9,000) | **$13.4M** (34,600) | Pilot→paid 50%; NRR 120%; 1 / 5 / 12 sellers + 3–4 partners; GM 45–55% → 60–65% → 68–72% |
| **Aggressive** | $1.02M (2,800) | $12.6M (32,000) | **$49.5M** (118,000) | Pilot→paid 60%; NRR 135%; at least one 5–10k-seat channel deal per year |

Sanity checks: Fyxer's self-serve prosumer motion grew faster (from $1M to $17M ARR in ~8 months); our IT-approval-led motion starts slower but should be stickier. The base case at Y3 is ~1.7% of beachhead seats and implies ~35–50 FTE and ~$10–15M of venture funding (rough estimate).

---

## 8. Metrics [R09 §8.5, R05]

| Metric | Pilot target | Scale target (M18) |
|---|---|---|
| Admin approval rate (approvals ÷ consent requests) | ≥ 30% | ≥ 40% |
| Activation (persona built + first draft used within 7 days) | ≥ 70% | ≥ 80% |
| Weekly active / paid seats | ≥ 60% | ≥ 65% |
| **Send-without-edit rate** (≤ 5% character edits) — north star | ≥ 25% by week 4 | **≥ 40%** (replies) |
| Light-edit rate (< 20% edit distance) | ≥ 55% | ≥ 70% |
| "Sounds like me" rating | ≥ 4.0 / 5 | ≥ 4.3 |
| Time-to-send (drafted vs not) | −30% | −40% |
| Commitments captured per WAU per week / precision | ≥ 5 / ≥ 80% | ≥ 8 / ≥ 90% |
| Pilot → paid | ≥ 50% | ≥ 60% |
| NRR / GRR (12-month cohort) | — | ≥ 120% / ≥ 90% |
| COGS per paid seat | tracked weekly | ≤ 30% of ARPU (US), ≤ 40% (India) |
| CAC payback | — | ≤ 12 months (mid-market), ≤ 18 (enterprise) |

---

## 9. Hardware — and how we avoid Humane's and Rabbit's mistakes

### 9.1 What actually happened (evidence: `docs/research/_raw/08a`, `08b`, `08c`; full analysis in [R08])
- **Humane AI Pin** raised ~$230M; shipped Apr 2024 at $699 + $24/month (tied to a T-Mobile line, US only, no phone app). Reviews measured ~6 s answers, repeated thermal shutdowns, 4–5 h battery and a projector unreadable in sunlight; it lacked basics (timers, calendar). ~10k units sold vs a 100k target (~$9M); returns outpaced sales May–Aug 2024; carrier lock made returns e-waste; a charging-case battery recall (~10,500 units). HP bought the team and IP for $116M (Feb 2025) and **devices were shut down on 28 Feb 2025 with 10 days' notice, data deleted, most owners unrefunded**. Culture: a dissenting engineer was fired; demo units were chilled with ice packs.
- **Rabbit R1** ($199, no subscription) sold ~100–130k units but only **~5% used it daily**; its "Large Action Model" was shown to run as an Android app driving cloud browser sessions; **hard-coded third-party API keys leaked** (Jun 2024); on-device chat logs couldn't be deleted; a one-time price couldn't fund ongoing cloud costs; payroll problems from 2025; **its India launch stalled on unnamed regulatory problems** (relevant to our US + India plan); the CEO later conceded "no one wants to carry around two devices."
- **What worked:** **Plaud** — one clear job (record and summarise meetings), minute-based subscriptions, a Team plan ($20–35/user), compliance badges and a **device SDK + transcription API** for third parties (no India region). The market moved toward **press-to-record** (Bee's button + green LED, Pebble Index 01, Sandbar ring "not always listening"); **BLE relay to the phone** is the norm; devices are cheap ($50–400) and **subscriptions carry the business**. Big Tech bought the always-on pendants (Amazon → Bee, Meta → Limitless — which stopped sales and cut off 7 jurisdictions with 14 days to export data).

### 9.2 Failure mode → how PersonaAgent avoids it
| Failure mode | Evidence | Our mitigation |
|---|---|---|
| **No killer use case; tried to replace the phone** | Humane framed as a phone successor; Rabbit ~5% daily use | Software-first: the job is "write like me + remember work"; a future device is a **companion** to the phone and Outlook/Teams, never a replacement |
| **Hardware before the habit** | Both shipped hardware first | **Phone + Teams transcripts prove the memory habit before any device**; hardware only after gates (§9.3) |
| **Cloud latency and thermals** | ~6 s answers; thermal shutdowns | Drafting p95 ≤ 2.5 s target; batch-by-default capture; no on-device heavy AI; a device only streams audio over BLE to the phone |
| **Overpromised demos** | Rabbit "LAM"; Humane staged demos | Publish measured metrics (send-without-edit, recall citations, battery); design-partner pilots; no staged demos |
| **Weak security culture** | Rabbit hard-coded fleet-wide keys; undeletable logs | No vendor keys in clients; per-device keys, secure boot, signed OTA; remote wipe; on-device buffer ≤ 24 h encrypted; external pentests [R10] |
| **Bricking customers** | Humane: 10 days' notice, data deleted; Limitless: regions cut off with 14 days | **No-brick commitments:** contractual end-of-life notice (6–12+ months), open-format export at any time, offline/local mode for devices, escrow/open protocol, pro-rata refunds |
| **Hardware + separate subscription; one-time price that can't fund the cloud** | Humane $699 + $24/mo; Rabbit $199 one-time | **Hardware-as-a-service inside the seat** (Capture+ / 24-month term), priced on measured COGS |
| **Carrier/cellular lock-in** | Humane returns became e-waste | BLE relay to the phone; no own LTE |
| **Regulatory readiness for new regions** | Rabbit's India launch stalled | Plan **FCC (US) and BIS/WPC (India)** certification early; never make cash flow depend on a device launch |
| **Battery/supply-chain recalls** | Humane charge-case recall outlived the company | Certified cells, UN38.3, recall playbook, serialised fleet tracking |
| **Social acceptability / surveillance backlash** | Friend pendant ad backlash; recording lawsuits | Work-only, company-governed; visible LED + physical mute; press-to-record and policy windows; consent ledger; no voiceprints |
| **Culture of positivity over truth** | Humane NYT reporting | Written go/no-go gates; red-team reviews; publish failures internally |

### 9.3 Why a device might eventually earn its place
Phones **cannot start the microphone from the background** [R06], so the phone recorder always needs a tap. A Bluetooth badge with its own mic, button and storage **can start capture itself** and hand audio to the phone as BLE data — Apple and Android documentation support this, but on iOS the app gets only ~10-second wake windows and isn't relaunched after a force-quit, so the badge must buffer and forward later. AirPods/headsets don't solve it. A **2-week BLE prototype** must confirm this before any hardware commitment (Medium confidence until then) [R08 §4.2]. Enterprise precedent cuts both ways: the Vocera hospital badge succeeded (Stryker paid $2.97B), while Glass Enterprise and HoloLens 2 were discontinued — buyers expect multi-year support windows [R08 §3.3].

### 9.4 Hardware roadmap with go/no-go gates [R08 §6]
No phase starts until the previous gate is met; **missing a gate twice shelves the hardware track** (PersonaAgent stays software + partner devices).

| Phase | When (indicative) | What | Team |
|---|---|---|---|
| **0 — Software MVP** | Months 0–3 | Phone work-mode recorder (per MVP plan), Teams transcripts, persona drafting. **No hardware.** Instrument the gate metrics (missed-capture rate, in-person capture hours, memory queries per user per week, weekly capture use) | 0 hardware FTE |
| **1 — Integrate before building** | Months 3–9 | Device-abstraction layer; **Plaud via its Device SDK** (US first; India only once raw audio can bypass Plaud's cloud); **Omi** (open-source) as experimental; Teams-certified headsets/AirPods as call/dictation sources; the 2-week background-BLE spike; 3–5 US + India design partners co-specify a badge; pick test labs; identify an Authorised Indian Representative | ≤ 0.5 FTE + contractor |
| **2 — Pilot hardware** | Months 9–15 | 100–500 pilot badges on an Omi-derived **nRF5340** design running our firmware (policy enforcement, hardware LED/mute, secure boot); FCC via a pre-certified radio module; India pilots only once WPC ETA + battery BIS are in hand (otherwise US-only — the Rabbit lesson) | 1 firmware + 1 HW/ODM manager |
| **3 — Production badge** | Months 15–30 | EVT → DVT → PVT → mass production (9–15 months prototype-to-MP); first run 5–10k units; sold **only as Capture+ hardware-as-a-service seats** (≈ +$6–10/user-month, est.), never retail; BOM ≈ $15–33 ex-factory / $18–46 landed at 10k units (est.) | Hardware lead + 2–3 engineers + ODM/EMS |

**Gate G1 → Phase 1:** ≥ 10 paying tenants **or** ≥ 500 paid seats · phone-capture weekly use ≥ 40% of capture-enabled seats for 4 weeks · evidence of the background-start gap (≥ 25% of eligible in-person meetings uncaptured, or ≥ 30% of users report "forgot to start / phone not with me") · zero Sev-1 privacy/security incidents.
**Gate G2 → Phase 2:** ≥ 2,000 paid seats across ≥ 25 tenants (logo retention ≥ 90%) · capture weekly use ≥ 50% for 8 weeks · ≥ 5 memory queries per active user per week with ≥ 80% accepted as correct · **partner-device users capture ≥ 1.5× more in-person hours** · LOIs for ≥ 300 pilot devices (≥ 1 path to 1,000+) · BLE spike passes on iOS + top-5 Android OEMs (US and India) at ≤ 10% phone battery per workday · software gross margin ≥ 60%.
**Gate G3 → Phase 3:** ≥ 60% of pilot users wear it ≥ 3 days/week after 60 days · ≥ 99% sync success · ≥ 12 h field battery (path to ≥ 16 h) · returns < 3%/quarter · complaint rates below threshold, no open high-severity pentest findings, no regulator/works-council objections · ≥ 5,000 paid seats and ≥ 3 customers committed to ≥ 1,000 devices on Capture+ · fully-loaded unit cost ≤ ~$60 at 10k with ≥ 50% HaaS gross margin · FCC + India (WPC ETA, BIS) plans signed off · **18 months of runway that doesn't count hardware revenue**.
**Stop/pivot signals:** wear-time collapses after week 3 (the novelty curve that killed Rabbit usage); customers reject device capture on privacy grounds; a partner device already delivers ≥ 80% of the value; AI cost per seat wipes out hardware margin.

### 9.5 Commitments we can make now (they win security reviews today)
- **Hardware Trust Spec (2 pages, used in sales now):** a mute switch that physically cuts the mic; a recording LED wired to the mic's power rail; a start chime; **no camera, no voiceprints**; per-device identity, secure boot, signed OTA, encrypted flash, crypto-erase; open protocol and escrow [R08 §4.7–4.10].
- **No-brick terms in the MSA from day one — for software too:** ≥ 12 months' end-of-service notice, ≥ 3 years of security updates for devices, bulk export in open formats, firmware escrow, offline export, change-of-control clause, certified deletion.
- **Certification budget when the time comes:** ≈ $25–60k and 8–14 weeks after design freeze for US + India (incl. the verified ~$11.5–12k Bluetooth listing fee); India via WPC ETA self-declaration + BIS for the battery, an Indian representative, cable-only (no adapter); start ≥ 6 months before India shipments [R08 §4.12].

---

## 10. Strategic risks and triggers to watch
Full register in `04-risk-register.md`. Watch quarterly [R09 §9]: Microsoft shipping automatic style learning in Outlook; Superhuman bundling Fathom into Mail; Fyxer's enterprise push into Microsoft-centric mid-market; Granola/Fireflies moving into email drafting; Viven entering IT services; rulings in *In re Otter.AI* and *Chamberlain v. Granola*; model price cuts (good for margin, but competitors cut prices too).

## 11. Naming
"PersonaAgent" collides with an ACL 2026 research framework (arXiv 2506.06254). Run USPTO and Indian trademark searches and choose a distinctive, ownable brand before public launch; keep "persona" as a feature term [R05, R07, R09].
