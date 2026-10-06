# 10 — Security Threat Model & Multi-Level Redaction Architecture

**Product:** PersonaAgent (persona writing agent + always-on, work-only memory capture)
**Track:** Security threat model + redaction architecture
**Date:** 2026-10-06 · **Status:** v1 research report for founders & engineers
**Founder decisions applied:** first buyer = Microsoft 365 mid-market & enterprise (per seat) · v1 regions = United States + India · team = 3–6 engineers, ~3-month MVP · recorder = work-only, tenant-governed (no personal lifelogging in v1) · Phase-1 redaction tuned precisely to US + Indian regulatory requirements (EU/UK later).
**Cross-track facts used (confirmed by other analysts, not re-researched here):** MVP Graph scopes are delegated read-only (`Mail.Read`, `Chat.Read`, `User.ReadBasic.All`); drafts are inserted client-side into Outlook/Teams compose; server-side drafts (`Mail.ReadWrite`) and user-approved sends come later under a *separate* app registration; Microsoft's managed default consent policy now blocks *user* consent for mail/chat/calendar/meeting scopes (tenant-admin consent required); labelled emails carry an `MSIP_Labels` internet header readable via Graph; Teams messages expose a DLP `policyViolation` flag but no label; Purview `processContent` lets third-party AI apps run the customer's DLP/audit; Purview has built-in SITs for US SSN/ITIN/ABA/bank account and India Aadhaar/PAN/GST/voter ID/driving licence but *not* Indian passport, IFSC/bank account or UPI IDs; Teams flags outside meeting bots as "Unverified" (since June 2026); Microsoft API Terms (Oct 2025) restrict email-API use to the customer's express purpose, no copying beyond it, deletion on abandonment.

**Confidence legend:** **High** = verified in a primary/official source during this research (or a settled, widely documented fact); **Med** = reported by credible secondary sources or my knowledge not re-verified this session; **Low** = inference, early reporting, or could not verify. Research constraint: the shared web-search budget was exhausted mid-track, so some 2024–25 items are cited from well-known primary URLs without a fresh fetch — these are marked **Med** and listed in §13.

---

## 0. Executive summary

- **PersonaAgent is a textbook "lethal trifecta" system.** It (A) reads attacker-controllable content (every inbound email, Teams message, calendar invite and spoken word near the recorder), (B) holds a person's entire communications history, and (C) emits text that leaves the organisation. Simon Willison's advice is to never combine all three; Meta's "Agents Rule of Two" (31 Oct 2025) says an agent should hold at most two of them per session, otherwise a human must approve. Our architecture has to put the human-approval point in a fixed place, and that place should not be a prompt. (High)
- **Every major assistant vendor has been hit by this attack class, and model-level defences alone have not held.** Examples: zero/one-click exfiltration from M365 Copilot (EchoLeak, CVE-2025-32711, CVSS 9.3; Reprompt, Jan 2026); ChatGPT connectors and Deep Research (AgentFlayer, ShadowLeak, ZombieAgent); Gemini (calendar-invite injection, GeminiJack); Salesforce Agentforce (ForcedLeak, CVSS 9.4); Slack AI; the GitHub MCP server; Grafana (GrafanaGhost, Apr 2026). Adaptive attacks bypassed 12 published defences with >90% success for most (Nasr, Carlini et al., Oct 2025). Even Anthropic's hardened browser agent reports about **1% attack success** against an adaptive attacker and says "no browser agent is immune" (Nov 2025). **Design assumption: some injections will succeed. The architecture must limit what a successful injection can do.** (High)
- **Five architectural decisions for the MVP:**
  1. Read-only delegated Graph scopes, with drafts inserted client-side. No server-side sending.
  2. A *quarantined reader / privileged planner* split (dual-LLM / CaMeL-lite). The model that reads untrusted text has no tools, no egress and no memory-write rights, and returns only schema-validated data.
  3. No internet egress from LLM workers. Drafts are rendered as plain text with no auto-loaded remote content, and URLs are allow-listed.
  4. Persona and style memory is learned **only from user-authored (sent) content**. Anything derived from external senders is quarantined with provenance, a trust score and an **audience ACL**.
  5. A silo-per-tenant data plane: index-per-tenant vectors, per-tenant KMS keys, no shared caches or fine-tunes.
- **Memory and persona are a new persistence surface.**
  - ZombieAgent (Radware; fixed 16 Dec 2025) used ChatGPT memory for persistence and worm-like spread.
  - Microsoft found **31 companies in 14 industries** planting memory instructions through "Summarize with AI" links (10 Feb 2026).
  - MINJA showed memory injection using queries alone.
  - A poisoned "style rule" or "fact" in our KB (new bank details, "always CC X", a link to include) would make PersonaAgent a BEC engine that writes in the victim's own voice.
- **Contextual-integrity leaks are the quiet failure.** In PrivacyLens (NeurIPS 2024), GPT-4 and Llama-3-70B leaked sensitive information in **25.68% / 38.69%** of agentic actions *even with privacy-enhancing prompts*. Without per-memory audience ACLs, drafts to a customer will reuse facts learned from internal threads. (High)
- **Our OAuth token store is the most valuable target we hold.** In Salesloft Drift (Aug 2025), OAuth tokens held by an AI chat vendor were used to bulk-export Salesforce data and read mail in some Google Workspace accounts. The attackers then searched the stolen data for AWS keys, passwords and Snowflake tokens. Mitigations:
  - Use Entra **workload identity federation** with **AWS IAM outbound identity federation**. Entra documents this pairing, and it leaves no client secret to steal.
  - Encrypt tokens per tenant and let only the ingestion role use them.
  - Detect and mask credentials found in mail. (High)
- **Multi-level redaction has four levels, each with a defined set of consumers:**
  - **L0** raw: transient, or customer-keyed archive.
  - **L1** pseudonymised: consistent reversible tokens.
  - **L2** company-sensitive masked.
  - **L3** anonymised/aggregated.

  "Tier-R" regulated identifiers are **irreversibly masked at ingestion and never persisted, even at L0**. This covers card PAN/CVV/track data, full Aadhaar/VID, SSN/ITIN, bank account numbers, passport/DL numbers, health IDs and secrets. It keeps us out of PCI DSS cardholder-data scope (to be confirmed with a QSA), aligns with UIDAI masking / Aadhaar Data Vault rules, and maps to the DPDP Rules' "encryption, obfuscation or masking or the use of virtual tokens".
- **No single detector covers what we need:**
  - Bedrock Guardrails PII has US/CA/UK types but **no Indian types**, does **not inspect tool-call arguments or tool results**, returns the raw matched PII in its trace, and leaves Bedrock invocation logs unmasked.
  - Amazon Comprehend PII handles **English/Spanish only**, but it does include IN_AADHAAR, PAN, VOTER and NREGA.
  - Presidio validates Aadhaar with Verhoeff, while its GSTIN check is structural only.
  - Transcribe PII redaction covers en-IN/en-US but **not Hindi**, and AWS says it "does not meet the requirements for de-identification under … HIPAA".
  - NVIDIA's GLiNER-PII (Oct 2025, English only) reports strict F1 of 0.64–0.87.

  → We need a layered ensemble: our own checksum validators, secret rules, NER (Presidio + GLiNER + directory-derived name lists), an LLM contextual classifier, customer dictionaries and Purview label signals. It must **fail closed** and be measured against our own US/India labelled test sets. (High)
- **US and India regulatory requirements set the defaults (§6.5).** **US:** CPRA treats "contents of a consumer's mail, email, and text messages" as *sensitive personal information*, and HIPAA Safe Harbor's 18 identifiers include voiceprints. **India:** the DPDP Rules were notified 13 Nov 2025, with most obligations live **13 May 2027**. They require masking- or tokenisation-class safeguards, 1-year log retention and 72-hour breach reports to the Board. CERT-In requires **6-hour** incident reporting and **180-day logs kept in India**. (High)
- **A 3–6 engineer team can ship a credible MVP in ~3 months if we:** keep no audio after transcription; do no server-side sending; do no fine-tuning on customer data; use no third-party MCP servers; launch India with English and Hinglish only; and use Guardrails, Presidio and our own validators for redaction. **Enterprise tier** adds a Nitro-Enclave tokenisation vault, BYOK/XKS, Purview `processContent`, AgentCore Policy (Cedar) for server-side actions, SIEM export, a bug bounty and SOC 2 Type II / ISO 27001.

## 1. Scope, assets, trust boundaries and adversaries

### 1.1 What we are protecting (assets)

| ID | Asset | Why it matters | Default data level |
|---|---|---|---|
| A1 | Raw mail / Teams / transcripts fetched from Graph or captured on the phone | Complete communications record; contains every regulated identifier class | L0 (transient) |
| A2 | Persona KB (per-audience style profiles, exemplars, phrase banks) | Lets anyone produce text *indistinguishable from the user*: an impersonation asset | L1 |
| A3 | Long-term memory and relationship graph (facts, commitments, who-knows-whom) | Aggregated, searchable knowledge across the user's career | L1 + audience ACL |
| A4 | Embeddings / vector indexes | **Personal data in their own right**: Vec2Text recovered 92% of 32-token inputs exactly and extracted full names from clinical notes (Morris et al., EMNLP 2023) (High) | L1-equivalent |
| A5 | OAuth token vault (Graph refresh tokens) + app credentials | A 90-day refresh token is bound to user+client and can mint access tokens to any resource the app is consented for (Microsoft docs) (High) | Secret |
| A6 | Tokenisation vault (value ↔ token maps) + keys | Re-identification capability for all L1 data | Secret / L0 |
| A7 | Phone audio buffers, device keys, offline transcripts | Bystander speech; lost-device exposure | L0 |
| A8 | Prompts, generated drafts, model outputs | Mix untrusted inbound text with private memories | L1 (L0 at render) |
| A9 | Logs, traces, analytics, evaluation sets, support tickets | Classic leak path (DeepSeek exposed DB, Jan 2025; Bedrock invocation logs hold unmodified input) | Metadata / L3 |
| A10 | Tenant policies, audit logs, role assignments | Integrity of every other control | Config |

### 1.2 Trust boundaries

```
 External senders / meeting participants / bystanders  (UNTRUSTED CONTENT)
        │ email, Teams msgs, invites, attachments, speech
        ▼
 ┌──────────── Customer M365 tenant (system of record) ────────────┐
 │  Exchange Online · Teams · Entra ID (consent, CA policies)      │
 └───────────────┬──────────────────────────────────────────────────┘
   TB1: OAuth / Graph (delegated, read-only in MVP)
                 ▼
 ┌──────────── PersonaAgent AWS account(s) per region (US, India) ─────────────┐
 │ Ingestion → Redaction (L0→L1/L2) → Vault │ Persona learner │ Memory store    │
 │ TB2: untrusted-data plane (quarantined)  │ TB4: tenant↔tenant isolation      │
 │ Drafting agent (planner + quarantined reader) → Output DLP → Re-hydrator     │
 │ TB3: Bedrock (in-region, no egress)      │ TB5: our staff ↔ customer data   │
 └───────────────┬─────────────────────────────────────────────────────────────┘
   TB6: client surfaces (Outlook add-in, Teams app, Windows app)
   TB7: phone recorder ↔ cloud, phone ↔ bystanders (physical)
   TB8: third-party code (PyPI/npm, SDKs, MCP servers, CI actions, model artifacts)
```

### 1.3 Adversaries (ranked by expected frequency)

1. **Any external sender.** This is the cheapest and most common adversary. Anyone who can email or Teams-message a user, send an invite or speak near the recorder can attempt *indirect prompt injection* or *memory poisoning*. No account compromise is needed. Email remains the primary attack surface (EchoLeak, ShadowLeak and ZombieAgent all started with an email).
2. **Account-takeover attacker** with a session in the victim's M365 or PersonaAgent account. They use the persona to write perfect-voice BEC messages. In the Arup deepfake case (early 2024), a single fraudulent video call cost the company about US$25M. The money was lost to a convincing impersonation, not to a technical exploit. (Med; widely reported, not re-fetched)
3. **Cloud-credential thief / denial-of-wallet.** "LLMjacking" (Sysdig, May 2024) used stolen cloud keys to invoke hosted models, including Bedrock, at an estimated cost of "over $46,000 per day" to the victim. (High)
4. **Supply-chain attacker.** Examples: TeamPCP compromised Trivy, then published malicious LiteLLM 1.82.7/1.82.8 to PyPI (27 Mar 2026), with credential-stealer payloads harvesting AWS/GCP/Azure tokens. Mercor reported ~4 TB stolen. Separately, the malicious `postmark-mcp` server BCC'd every sent email to the attacker (ATLAS AML.CS0053). (High)
5. **Malicious or curious insider at the customer:** a tenant admin, delegate or manager who wants to read an employee's memories or recordings.
6. **Malicious or curious insider at PersonaAgent:** support or SRE staff. The Coinbase support-agent bribery case (May 2025) shows the pattern. (Med)
7. **Nation-state actors targeting executives through OAuth applications.** Midnight Blizzard (Jan 2024) abused OAuth apps to reach Microsoft senior-leadership mailboxes. Storm-2372 used device-code phishing. (Med; well documented by Microsoft, not re-fetched)
8. **Device thief / lost phone.**
9. **"Grey" commercial manipulators.** Microsoft's "AI Recommendation Poisoning" research found real companies, "not hackers or scammers", planting persistent memory instructions. (High)

## 2. What 2024–2026 incidents teach (threat landscape)

### 2.1 Incident register (most relevant to a mailbox/Teams/audio agent)

| # | Incident (date) | Product | Entry vector → exfil channel | Lesson for PersonaAgent | Conf. |
|---|---|---|---|---|---|
| 1 | **EchoLeak, CVE-2025-32711** (disclosed Jun 2025; CVSS 9.3; fixed server-side, no customer action) | M365 Copilot | Crafted inbound email retrieved by Copilot's RAG ("LLM scope violation") → data embedded in links/images pointing at Microsoft Teams/SharePoint URLs | **Zero-click via email.** First-party, CSP-allowed domains can still be exfil channels. Classifier and link-redaction layers were bypassed. | High (CVE/CVSS/mechanism); Med (bypass details) |
| 2 | **Slack AI exfiltration** (PromptArmor, Aug 2024) | Slack AI | Message in a *public* channel → model renders a markdown link carrying private-channel data. Slack initially called it "intended" | Any corpus an outsider can write to is an injection carrier, and rendered links are an exfil channel (ATLAS AML.CS0035) | High |
| 3 | **"Invitation Is All You Need"** (SafeBreach/Tel Aviv Univ./Technion; Aug 2025) | Gemini for Workspace | Prompts in calendar-invite titles, email subjects or doc names → 14 scenarios (smart-home control, Zoom calls, event deletion); 73% rated high-critical | Invites, meeting titles and transcripts are carriers. Google's fix: confirmations + URL sanitisation + classifiers | High |
| 4 | **GitHub MCP "toxic agent flow"** (Invariant Labs, 26 May 2025) | GitHub MCP server + agents | Malicious public issue → agent reads private repos → leaks via a public PR | Architectural, not a code bug: trusted tools combined with untrusted input leak data. Scope each session to one context | High |
| 5 | **AgentFlayer** (Zenity, Black Hat Aug 2025) | ChatGPT Connectors (+ chains vs Copilot Studio, Cursor/Jira, Einstein, Gemini) | ~300 words of 1-px white text in a shared doc → secrets (API keys) exfiltrated | Hidden-text documents work. Never auto-ingest shared docs as instructions | High/Med |
| 6 | **ShadowLeak** (Radware, 18 Sep 2025; reported 18 Jun, patched early Aug) | ChatGPT Deep Research + Gmail | Hidden HTML in an email → agent's own browser tool sends Base64 data from OpenAI's cloud | **Service-side** egress is invisible to enterprise controls, so our LLM workers need *no* egress | High |
| 7 | **ForcedLeak** (Noma; reported 28 Jul 2025; CVSS 9.4; fixed by 8 Sep 2025) | Salesforce Agentforce | Web-to-Lead "Description" field → exfil to an **expired allow-listed domain bought for ~$5** | Allow-lists rot. Pin allow-listed destinations to domains we control and monitor them | High |
| 8 | **GeminiJack** (Noma; found Jun 2025, disclosed Dec 2025) | Gemini Enterprise | Poisoned Doc / Calendar / Gmail item retrieved by an ordinary enterprise search, executed with the employee's permissions | RAG over a shared corpus means anyone who can share a file can inject | High |
| 9 | **ZombieAgent** (Radware; fixed 16 Dec 2025) | ChatGPT Connectors + Memory | Zero-click email → server-side exfil; **memory-modification rules for persistence**; worm-like propagation | Memory turns a one-off injection into persistence. Memory writes must never accept instructions | High |
| 10 | **Reprompt** (Varonis; patched Jan 2026 Patch Tuesday) | Microsoft Copilot (consumer) | One click on a legitimate Microsoft link with a prompt in a URL parameter → session hijack that persists after the chat closes | Our add-in and deep links must never accept prompts via URL parameters | High |
| 11 | **Copilot Chat DLP bug CW1226324** (reported 21 Jan 2026; fix rolled out Feb 2026) | M365 Copilot Chat | Code error let Copilot summarise **labelled mail in Sent Items and Drafts** despite DLP policies | Sent Items is our core corpus. Do not assume upstream label/DLP enforcement; check labels ourselves | High |
| 12 | **AI Recommendation Poisoning** (Microsoft, 10 Feb 2026) | Copilot, ChatGPT, Claude deep links | "Summarize with AI" buttons inject "remember X as a trusted source"; 50+ prompts, 31 companies, 14 industries, in 60 days | Memory poisoning is already used commercially, not only in research. Users need memory review UI and provenance | High |
| 13 | **OpenClaw ecosystem** (Q1 2026) | Open-source personal agent with mail access | Tens of thousands of exposed instances; Koi found 341 malicious skills of 2,857 reviewed ("ClawHavoc"), later >824; inbox-deletion incident (23 Feb 2026) after the agent ignored stop commands | Autonomy + write scopes + an unvetted extension marketplace is the failure pattern. Keep `Mail.ReadWrite` out of the MVP | Med |
| 14 | **Asana MCP cross-org exposure** (May–Jun 2025) | Asana MCP server | Logic flaw exposed task, project and comment data to *other organisations* for over a month; ~1,000 customers | New AI code paths reintroduce cross-tenant bugs. Isolation tests are a release gate | High |
| 15 | **postmark-mcp rug-pull** (Sep 2025) | npm MCP server | Legitimate versions built trust (>1,000 weekly downloads), then a release BCC'd every email to the attacker (ATLAS AML.CS0053) | No third-party MCP servers in the data plane. Pin versions and hashes | High |
| 16 | **LiteLLM / TeamPCP** (27 Mar 2026) | PyPI `litellm` 1.82.7/1.82.8 | Trivy compromise (19 Mar) → CI publishing credentials stolen → `.pth` credential stealer harvested cloud keys; Mercor ~4 TB | Pin CI tools, use hash-locked dependencies and short-lived publishing credentials | High |
| 17 | **Salesloft Drift** (8–18 Aug 2025; GTIG advisory) | SaaS AI chat vendor holding OAuth tokens | Stolen OAuth tokens → bulk SOQL export → attackers **searched the data for AKIA keys, passwords, Snowflake tokens**; "Drift Email" tokens used to read some Google Workspace mail (9 Aug) | Our refresh-token vault is a supply-chain pivot. Customer mail is full of secrets, so mask them at ingestion | High |
| 18 | **GrafanaGhost** (Noma, disclosed 7 Apr 2026) | Grafana AI features | Indirect injection → exfil via image rendering | Rendering channels keep reappearing in new products | Med |
| 19 | **Vertex AI "Double Agent"** (Unit 42, Mar–Apr 2026) | Vertex AI Agent Engine | Over-privileged agent service account → credential exfiltration | Give each agent its own narrowly scoped identity | Med |
| 20 | **LLMjacking** (Sysdig, 6 May 2024) | Bedrock, Azure, Vertex | Stolen cloud credentials → model abuse; "over $46,000 per day" | Denial-of-wallet: SCPs, quotas, budget alarms, no long-lived keys | High |
| 21 | **Windows Recall v1** (2024) → redesign (27 Sep 2024) | Windows | Initial design stored captured history insecurely; redesign made it opt-in with TPM-bound keys, VBS enclaves, Windows Hello gating, and sensitive-content filtering "on by default" | The closest analogue to Pillar 2: opt-in, hardware-bound keys and filtering at capture are the bar | High |
| 22 | **Rabbit R1 hard-coded keys** (Jun 2024) | Consumer AI device | Hard-coded third-party API keys (e.g., ElevenLabs, Azure, Yelp, Google Maps) in the codebase reportedly let anyone read all past device responses | No provider keys in clients or repos; per-device credentials; server-side brokers; rotate keys | Med (primary write-up unavailable during research) |
| 23 | **Coinbase insider bribery** (disclosed May 2025) | Support tooling | Overseas support agents bribed to export customer data | Support staff must never have bulk access to content. Use break-glass with dual approval | Med |

### 2.2 Cross-cutting patterns

- **Entry points seen so far:** inbound email (1, 6, 9), shared docs (5, 8), calendar invites and titles (3), chat messages (2), public tickets/issues/forms (4, 7), **URL parameters / deep links** (10, 12), package and extension registries (13, 15, 16) and tool descriptions (ATLAS AML.T0110). For PersonaAgent, add **spoken words** captured by the recorder.
- **Exfiltration channels seen so far:**
  - Client-rendered images and links (ATLAS **AML.T0077 LLM Response Rendering**: 1, 2, 5, 18)
  - Allow-listed domains (1, 7)
  - The agent's own browsing (6)
  - Write-capable tools such as PRs, emails and CRM updates (ATLAS **AML.T0086**: 4, 15)
  - Memory, used for persistence (9, 12)
- **What vendors shipped as fixes:**
  - Deterministic egress blocking (markdown image/link stripping, URL sanitisation)
  - User confirmation for actions
  - Injection classifiers
  - Narrower trust levels per data source
  - Memory controls

  Microsoft's published defence-in-depth (MSRC, 29 Jul 2025) is the same mix: Spotlighting (delimiting, datamarking, encoding), Prompt Shields, data governance/labels, deterministic blocking of exfil techniques such as markdown images, human-in-the-loop (citing Outlook draft approval), FIDES information-flow control and TaskTracker. **This combination is the baseline we should match, not a ceiling.** (High)

## 3. Framework mapping (OWASP LLM Top 10 2025, OWASP Agentic Top 10 2026, OWASP Agentic T&M, MITRE ATLAS)

### 3.1 Reference lists used

- **OWASP Top 10 for LLM Applications 2025** (High):
  - LLM01 Prompt Injection
  - LLM02 Sensitive Information Disclosure
  - LLM03 Supply Chain
  - LLM04 Data and Model Poisoning
  - LLM05 Improper Output Handling
  - LLM06 Excessive Agency
  - LLM07 System Prompt Leakage
  - LLM08 Vector and Embedding Weaknesses
  - LLM09 Misinformation
  - LLM10 Unbounded Consumption
- **OWASP Top 10 for Agentic Applications 2026** (published 9 Dec 2025):
  - ASI01 Agent Goal Hijack
  - ASI02 Tool Misuse & Exploitation
  - ASI03 Identity & Privilege Abuse
  - ASI04 Agentic Supply Chain Vulnerabilities
  - ASI05 Unexpected Code Execution
  - ASI06 Memory & Context Poisoning
  - ASI07 Insecure Inter-Agent Communication
  - ASI08 Cascading Failures
  - ASI09 Human-Agent Trust Exploitation
  - ASI10 Rogue Agents

  Confidence: High for ASI01/02/03/06/10 and the date. Med for the exact wording of ASI04/05/07/08/09, which comes from secondary summaries.
- **OWASP Agentic AI – Threats & Mitigations (T1–T15):**
  - T1 Memory Poisoning
  - T2 Tool Misuse
  - T3 Privilege Compromise
  - T4 Resource Overload
  - T5 Cascading Hallucination
  - T6 Intent Breaking & Goal Manipulation
  - T7 Misaligned & Deceptive Behaviours
  - T8 Repudiation & Untraceability
  - T9 Identity Spoofing & Impersonation
  - T10 Overwhelming Human-in-the-Loop
  - T11 Unexpected RCE & Code Attacks
  - T12 Agent Communication Poisoning
  - T13 Rogue Agents
  - T14 Human Attacks on Multi-Agent Systems
  - T15 Human Manipulation

  Confidence: High for T1/T2/T3/T15. Med for the others.
- **MITRE ATLAS** (IDs verified via ATLAS-derived pages):
  - AML.T0051 LLM Prompt Injection (.000 Direct, .001 Indirect, .002 Triggered)
  - AML.T0080 AI Agent Context Poisoning (.000 Memory, .001 Thread)
  - AML.T0086 Exfiltration via AI Agent Tool Invocation
  - AML.T0077 LLM Response Rendering
  - AML.T0057 LLM Data Leakage
  - AML.T0070 RAG Poisoning
  - AML.T0034 Cost Harvesting
  - AML.T0010.005 AI Supply Chain Compromise: AI Agent Tool
  - AML.T0109 AI Supply Chain Rug Pull
  - AML.T0110 AI Agent Tool Poisoning
  - AML.T0073 Impersonation
  - Case studies: AML.CS0035 (Slack AI), AML.CS0037 (Copilot Studio exfil via agent tools), AML.CS0039 (Jira Service Management "living off AI"), AML.CS0045 (MCP server used by Cursor), AML.CS0053 (postmark-mcp).
- **Watch:** genai.owasp.org lists newer documents that could not be inspected during this research: "OWASP GenAI LLM Top 10 2026" (dated 3 Aug 2026), "Agent Control Standard (ACS)" and "GenAI Security Industry Framework Crosswalk" (both 1 Sep 2026), and "GenAI Data Security Risks & Mitigations 2026". Re-map against them before the security review with the first enterprise customer.

### 3.2 PersonaAgent threats → frameworks

| PA-ID | Threat (detail in §4) | OWASP LLM 2025 | OWASP Agentic 2026 | OWASP T&M | MITRE ATLAS / ATT&CK |
|---|---|---|---|---|---|
| PA-01..04 | Indirect prompt injection via email, Teams, attachments, invites/transcripts | LLM01 | ASI01 | T6 | AML.T0051.001 (.002 for delayed triggers) |
| PA-05 | Spoken injection / adversarial audio | LLM01 | ASI01 | T6 | AML.T0051.001 |
| PA-06 | Exfil via rendered images/links/unfurls | LLM05, LLM02 | ASI01 | – | AML.T0077, AML.T0057 |
| PA-07 | Exfil via drafted replies / recipient manipulation | LLM02, LLM06 | ASI09 | T10, T15 | AML.T0057, AML.T0086 (once sending exists) |
| PA-08 | Tool-call abuse (future send/write/fetch) | LLM06 | ASI02 | T2 | AML.T0086 |
| PA-09 | Memory / persona-KB poisoning | LLM04, LLM08 | ASI06 | T1 | AML.T0080.000, AML.T0070 |
| PA-10 | Persona hijack / impersonation for BEC | LLM06 | ASI03, ASI09 | T9, T15 | AML.T0073 |
| PA-11 | Contextual-integrity leakage across audiences | LLM02 | ASI06 | – | AML.T0057 |
| PA-12 | Cross-user / cross-tenant leakage | LLM02, LLM08 | ASI03 | T3 | AML.T0057 |
| PA-13/14 | Memorisation, embedding inversion | LLM02, LLM08 | – | – | (exfil via inference API; Med) |
| PA-15/16 | OAuth consent phishing; refresh-token theft | – | ASI03 | T3, T9 | ATT&CK T1528 Steal Application Access Token; T1550.001 (Med) |
| PA-19 | Supply chain (PyPI/npm/CI/MCP/SDK) | LLM03 | ASI04 | – | AML.T0010.005, AML.T0109, AML.T0110 |
| PA-22 | Denial of wallet / LLMjacking | LLM10 | ASI08 | T4 | AML.T0034 |
| PA-23 | Logs/traces/support leakage | LLM02, LLM07 | – | T8 | – |
| PA-27 | Over-privileged scopes / unsafe autonomy | LLM06 | ASI02, ASI10 | T2, T13 | – |
| PA-29 | Client-surface attacks (deep-link prompts, add-in XSS) | LLM05, LLM01 | ASI01 | – | AML.T0051.000 |

## 4. Threat model table (deliverable D1)

Impact and likelihood are rated **C**ritical / **H**igh / **M**edium / **L**ow for PersonaAgent's v1 architecture, assuming the MVP decisions in §0. "Tier" says when the mitigation set must exist: **MVP** = before the first paying tenant; **Ent** = enterprise tier or Phase 2.

| PA-ID | Threat | Example / precedent | Impact | Likelihood | Key mitigations | Tier |
|---|---|---|---|---|---|---|
| PA-01 | Indirect prompt injection in **inbound email** (hidden HTML, white/1-px text, `display:none`, zero-width & Unicode tag chars) | EchoLeak; ShadowLeak; ZombieAgent | C | H | Normalise HTML→text, strip hidden/invisible content and flag that it existed. Spotlighting/datamarking. **Quarantined reader** (no tools, schema output). Injection classifier as a *signal* (Guardrails prompt-attack + own). No egress. Output DLP. Human approval of all outbound text. Persona learned only from sent items | MVP |
| PA-02 | Injection via **Teams** (external/federated chats, guests, channel posts, meeting chat) | Slack AI public-channel case | H | M-H | Sender trust classes (internal / guest / federated / external). External Teams treated like external email. Tenant option to exclude external chats from memory | MVP |
| PA-03 | Injection via **attachments, shared docs, links** | AgentFlayer; GeminiJack | H | M | MVP: do not ingest attachment bodies or linked docs into memory/persona; never fetch links server-side. Ent: sandboxed extraction under the same untrusted handling | MVP / Ent |
| PA-04 | Injection via **calendar invites, meeting titles, Teams transcripts** | "Invitation Is All You Need"; GeminiJack | H | M | Invites from external organisers are untrusted. Transcript utterances attributed by speaker; non-user speech is untrusted data. Summaries produced by the quarantined reader only | MVP |
| PA-05 | **Spoken** injection and adversarial audio (hidden/ultrasonic commands, ASR hijack) | Academic attacks on ASR (DolphinAttack 2017; universal adversarial audio vs Whisper-class models; Med) | M-H | L-M | **No voice-command channel in v1** (no wake word; queries only via the authenticated app). Transcripts are data. Others' speech gets low memory trust. Ent: audio/transcript anomaly detectors | MVP / Ent |
| PA-06 | Exfil via **rendered content** (markdown images/links, unfurls, HTML) | EchoLeak; Slack AI; AgentFlayer; GrafanaGhost (ATLAS AML.T0077) | C | H if rendering allowed | Render model output as **plain text**. Strip images/HTML. No auto-fetch, no unfurl. Links allowed only if they exist in the thread or the user's own history **and** pass the tenant allow-list. Strict CSP in add-in/Teams app. Detect encoded payloads (Base64, long query strings) | MVP |
| PA-07 | Exfil via **drafted replies** / recipient manipulation | Injected mail asks the agent to "summarise our pricing" in the reply; PrivacyLens leakage | C | M-H | API returns **body text only**; recipients are never set by the model. Audience-ACL check on every entity in the draft. Tier-R entities blocked from drafts. "Facts used" provenance panel. Extra friction for external recipients | MVP |
| PA-08 | **Tool-call** abuse once write tools exist (send, server drafts, calendar, web) | GitHub MCP toxic flow; ShadowLeak browser tool | C | M (Phase 2) | MVP has no server write tools. Phase 2: separate app registration; AgentCore Gateway + **Policy** (Cedar/temporal: approval before send, rate limits, recipient rules, "untrusted content in session ⇒ no send"); CaMeL-style taint on data | Ent |
| PA-09 | **Memory / persona-KB poisoning** (false facts, standing rules, links, bank details) | ZombieAgent; AI Recommendation Poisoning; MINJA | H | M-H | Provenance on every memory. **Style only from user-authored text.** External-derived facts low-trust and quarantined. Memory-write classifier (imperatives, "always/remember", payment/contact changes, URLs). User memory review/delete. TTL for low-trust items. Periodic poisoning scans | MVP |
| PA-10 | **Persona hijack / impersonation** for BEC (account takeover, insider, delegate misuse) | Arup US$25M deepfake call (Med); BEC playbooks | C | M | Entra SSO + customer Conditional Access + CAE. Own-persona only; delegates need Exchange delegation **and** exec opt-in. **BEC heuristics on drafts** (payment/bank change, gift cards, urgency, secrecy) → hard warning, no one-click insert. Generation rate limits / anomaly detection. No voice cloning. Generation audit log | MVP |
| PA-11 | **Contextual-integrity** leakage across audiences inside a user's own data | PrivacyLens: 25.68% (GPT-4) / 38.69% (Llama-3-70B) leakage with privacy prompts | H | H | **Per-memory audience ACL** from source recipients and labels. Retrieval filtered by current recipients. Output check for "novel" entities not visible to all recipients. Source-explanation UI | MVP |
| PA-12 | **Cross-user / cross-tenant** leakage (vector filters, caches, queues, logs, shared fine-tunes) | Asana MCP (~1,000 orgs exposed); ChatGPT 2023 cache bug (Med) | C | M | **Index-per-tenant** vectors. Per-tenant KMS keys. Tenant ID taken only from the verified token (`tid`). ABAC session tags. Aurora RLS. Cache keys include tenant+user. No cross-tenant prompt cache or fine-tune. Isolation tests in CI + canary tenants | MVP |
| PA-13 | **Memorisation/regurgitation** from fine-tuned weights | Training-data extraction literature (Med) | H | L (no fine-tune) | No fine-tuning on customer content in MVP. Ent per-user adapters only on L1 data, isolated, deleted on offboarding. Never cross-tenant training. Bedrock does not share prompts with model providers | MVP policy / Ent |
| PA-14 | **Embedding inversion** / vector theft | Vec2Text: 92% exact recovery of 32-token texts | H | L-M | Embed **L1** text. Encrypt with tenant keys. Treat vectors as personal data (residency, deletion). No vector export | MVP |
| PA-15 | **OAuth consent phishing**, look-alike apps, device-code phishing against our users | Midnight Blizzard; Storm-2372 (Med) | H | M | Publisher verification. **Admin-consent onboarding** (Microsoft default policy now requires it for mail/chat scopes). Publish our app IDs and redirect URIs. M365 App Compliance programme. Never use device-code flow. Validate `iss`/`tid`; key on `oid`, not email | MVP |
| PA-16 | **Refresh-token / credential theft** from our systems | Salesloft Drift (2025) | C | M | **Workload identity federation** (AWS IAM outbound → Entra federated credential), so no client secret exists. Tokens encrypted under per-tenant CMK (AgentCore Identity token vault supports CMKs). Only the ingestion role decrypts. Anomaly detection on Graph usage. Per-tenant kill switch | MVP |
| PA-17 | **Insider at PersonaAgent** (support/SRE/admin) | Coinbase support bribery (Med) | C | L-M | No standing data-plane access. Break-glass with dual approval + customer approval + session recording. KMS key policies exclude admin roles. SCPs. Ent: **Nitro Enclave vault** (operator-blind) | MVP / Ent |
| PA-18 | **Customer-side insider** (tenant admin, manager, EA overreach) | Manager requests an employee's recordings | H | M | Tenant admins cannot read content by default. eDiscovery/legal-hold export behind dual approval + user notice. Managers get aggregates (k ≥ 5) only. EA access mirrors mailbox permissions plus exec opt-in; private-memory flag | MVP / Ent |
| PA-19 | **Supply chain** (PyPI/npm, CI tools, MCP servers, SDKs, add-in deps) | LiteLLM/TeamPCP; postmark-mcp; OpenClaw skills | C | M-H | Hash-pinned lockfiles. Private mirror with malware scan and **new-version quarantine** (e.g., 7 days). Actions pinned by SHA. OIDC short-lived CI credentials. SBOM + provenance (Sigstore/SLSA). No third-party MCP in the data plane. No content-reading analytics SDKs | MVP / Ent |
| PA-20 | **Lost/stolen phone** | – | H | M | ≤24 h encrypted on-device buffer, then purge. iOS Data Protection *Complete* / Android Keystore (StrongBox). App lock. Remote wipe. Ent: Intune MAM policies | MVP / Ent |
| PA-21 | **Recorder misuse** (out-of-policy capture, privileged/HR meetings, bystanders, all-party-consent jurisdictions) | Legal track | H | M-H | Tenant policies: schedules, locations, auto-mute on HR/legal/medical calendar categories, visible indicator, consent prompts. "Privileged" marker stops capture. **No voiceprint enrolment** | MVP |
| PA-22 | **Denial of wallet** / LLMjacking / inbox flooding | Sysdig: >US$46k/day | M-H | M | Per-tenant/user token budgets + circuit breakers. Per-sender ingestion caps. Cheap prefilters before LLM. SCPs limiting model invocation to roles/regions/models. No long-lived keys. Budgets & anomaly alarms. GuardDuty | MVP |
| PA-23 | **Logs / traces / support** leakage | Bedrock invocation logs keep unmodified input; Guardrails trace returns raw PII | H | H | Invocation logging **off** in prod. Content-free structured logs. CloudWatch Logs data protection as backstop. OTel content capture off. Support sees metadata only. Log scanning with our detectors | MVP |
| PA-24 | **Redaction false negatives** and re-identification (incl. stylometry) | Transcribe/Comprehend accuracy disclaimers | H | H | Layered detectors + validators. Recall SLOs. Second-pass audit. Fail-closed. L3 excludes free text and style vectors. HIPAA-aware surrogate IDs (§6.5) | MVP / Ent |
| PA-25 | **Token spoofing** against the re-hydrator (attacker writes token-like strings) | Novel; follows from the token design | H | L-M | Neutralise token-like strings at ingestion. Unguessable, tenant-MAC'd token IDs. Re-hydrate only tokens present in *this* request's authorised context and allowed by audience ACL | MVP |
| PA-26 | **Upstream label/DLP gaps** and encrypted mail | Copilot CW1226324 | H | M | Read `MSIP_Labels`. Tenant rules per label (exclude / L2-only). Honour Teams `policyViolation`. Skip RMS-encrypted mail in MVP. Ent: Purview `processContent` on drafts | MVP / Ent |
| PA-27 | **Over-privileged scopes / unsafe autonomy** | OpenClaw inbox deletion (Feb 2026) | H | L (MVP) | Read-only scopes. No autonomous actions. Write scopes on a separate app registration later, policy-gated and reversible-first | MVP / Ent |
| PA-28 | **Deletion/retention** failures (residual copies; API terms; DPDP erasure) | Vectors, caches, backups, logs retain data | H | M-H | Lineage keys (Graph item ID → every derived artifact). **Crypto-shredding** with per-user branch keys. Deletion SLAs + verification tests. Backups under the same keys | MVP |
| PA-29 | **Client-surface** attacks (prompt via URL, add-in XSS, token misuse) | Reprompt (Jan 2026) | H | M | Never accept prompts from URLs. Strict CSP. Sanitised or plain-text rendering. Office SSO/NAA + OBO with audience checks | MVP |
| PA-30 | System-prompt / policy leakage, guardrail evasion | Common | L-M | H | No secrets in prompts. All policy enforced outside the model. Assume prompts are public | MVP |

## 5. Defenses and design patterns

### 5.1 Principles

1. **Assume the model will sometimes be steered.** CaMeL (Google DeepMind / ETH, Mar 2025) solved **77%** of AgentDojo tasks *with provable security* vs **84%** undefended. Security came from the system design, not from the model, which works "even when underlying models are susceptible to attacks". Adaptive attacks defeated 12 published defences at >90% success for most (Oct 2025). (High)
2. **Enforce the Rule of Two per session.** In any session where the agent has seen untrusted content *and* private data, it must not be able to change state or communicate externally without a human approval it cannot forge (Meta, Oct 2025). (High)
3. **Controls live outside the model:** IAM, Cedar policies, schema validation, egress rules, ACL filters, token budgets. Prompts are advisory only.
4. **Human approval must carry information.** OWASP T&M lists *T10 Overwhelming Human-in-the-Loop* as a threat. Approval screens must show *what is new or risky*: sources used, external recipients, links, money words. A bare "OK" is not enough.
5. **Bound the blast radius with data, not instructions.** If retrieval only returns memories the current recipients are already entitled to see (§5.6), a successful injection can leak little that the attacker could not already learn.

### 5.2 Reference architecture for the drafting agent

```
User in Outlook/Teams clicks "Draft reply"  (recipients & thread ID come from the client, not the model)
   │
   ▼
[Context builder — deterministic code]
   • fetch live thread (L0) → redact to L1 tokens on the fly
   • retrieval query built from structured fields (participants, subject keywords)
   • memory/persona retrieval FILTERED by audience ACL ⊇ current recipients (+ tenant label rules)
   │                                   │
   ▼                                   ▼
[Quarantined reader LLM]          [Generator LLM]
 sees untrusted thread text        sees: user instruction, persona profile, ACL-filtered L1 memories,
 (spotlighted, nonce-delimited)    reader's JSON, the thread (spotlighted)
 NO tools, NO memory writes        NO tools, NO network; output = draft text with tokens
 output: strict JSON (intent,      │
 asks, entities, risk flags)       ▼
                         [Output gate — deterministic + small classifier]
                          • schema/size checks • strip markup/images • URL policy
                          • Tier-R entity block • audience-ACL check on every token
                          • BEC heuristics • secrets scan • injection-echo detection
                                   │
                                   ▼
                         [Re-hydrator — separate service with vault access]
                          • only tokens present in this request's authorised context
                                   │
                                   ▼
                     Client shows PLAIN-TEXT draft + provenance + warnings → user edits → user inserts/sends
```

Design notes:
- The planner/reader split follows the **dual-LLM pattern** (Willison, 2023) and the design-pattern catalogue of Beurer-Kellner et al. (2025): action-selector, plan-then-execute, map-reduce, dual LLM, code-then-execute, context-minimisation. In the MVP the "planner" is mostly *deterministic code*. That is the cheapest and strongest form of the pattern: untrusted text never decides which memories are fetched or which tools run.
- **Tokens act as taint markers.** Because memories enter the prompt as L1 tokens (`⟦CLIENT_a91f⟧`, `⟦PERSON_3c2e⟧`), the output gate can check deterministically whether a draft cites an entity whose source ACL excludes a recipient. This is a cheap, partial form of CaMeL-style information-flow control. It misses paraphrased facts, so Enterprise adds an LLM-judge pass for "facts not supported by thread or permitted memories".
- **Spotlighting** (Hines et al., Microsoft, Mar 2024) cut attack success "from over 50% to below 2%" in their GPT-family tests. Use nonce-delimited blocks plus datamarking for untrusted text, plus an instruction-hierarchy system prompt stating that data blocks never carry instructions. It is useful but not sufficient on its own (see §5.1). (High)
- **Bedrock Guardrails** add value as a *signal*: prompt-attack detection on tagged untrusted input, and PII masking of model I/O. Hard limits (High, AWS docs): the sensitive-information filter **does not evaluate tool-call arguments, tool results or tool definitions**. PII masking does **not** apply to model-invocation logs. The trace `match` field returns the **original PII**. Guardrails cannot be the redaction layer; they are a backstop.

### 5.3 Output controls (draft DLP) — applied before anything reaches the user's screen

1. **Format:** plain text only. Markdown images, HTML, `data:` URIs and tracking-pixel patterns are removed. The draft is length-capped.
2. **URL policy:** a URL may appear only if it occurs in the current thread or the user's own sent history, and its domain is on the tenant allow-list. Full URLs are always shown. Query strings longer than N characters, or containing Base64/hex blobs, are flagged as exfil-shaped.
3. **Entity policy:** Tier-R entities (§6.4) never appear in drafts. If the user needs one, they type it themselves. Tokens whose memory ACL excludes any recipient are blocked; tokens from low-trust memories are flagged.
4. **Recipient policy:** the model cannot add, remove or edit recipients, CC or BCC (the API returns body text only). External recipients raise the warning level.
5. **BEC heuristics:** a classifier plus rules for payment instructions, bank/IBAN/IFSC/UPI changes, gift cards, urgency + secrecy, credential requests and "new account details". These cause a hard-stop warning and disable one-click insert.
6. **Injection-echo detection:** flag drafts that contain instruction-like text copied from the inbound mail, or that address the AI ("as an AI…", "ignore…").
7. **Enterprise:** send the final draft to **Purview `processContent`** so the customer's own DLP/audit applies (cross-track fact). Customers already invest in Purview policies, and this reuses them.

### 5.4 UI rendering rules (Outlook add-in, Teams app, Windows app, phone)

- No remote resources. CSP limits `img-src`/`connect-src` to our API origin. No link unfurling or previews of model-produced links.
- Drafts are inserted into compose by the client (MVP, cross-track decision). We never auto-send. Insert-and-send is two separate user gestures.
- **No prompt intake from URLs or deep-link parameters** (Reprompt and Recommendation Poisoning both abused URL-carried prompts).
- Show provenance: "Used 3 memories: … (from internal thread with X)". Show a warning banner when the inbound mail had hidden content or injection signals.
- Memory review UI: list, search, edit and delete memories, with source and trust level. Users can pause memory per contact or thread.

### 5.5 Least-privilege tools and policy engine

- **MVP:** delegated `Mail.Read`, `Chat.Read`, `User.ReadBasic.All` (cross-track). No write tools exist server-side, so most of ASI02/T2 does not apply yet.
- **Phase 2 (server drafts / user-approved sends):**
  - A *separate* Entra app registration with `Mail.ReadWrite` / `Mail.Send`, admin-consented separately. This lets tenants grant read-only first.
  - All write calls go through **AgentCore Gateway with Policy in AgentCore**. Policy intercepts every tool call through the Gateway and evaluates it against Cedar policies before allowing it. It supports fine-grained conditions on user identity and tool input parameters, natural-language authoring with automated-reasoning checks for over-permissive or unsatisfiable rules, and CloudWatch-logged decisions. The current docs also describe **temporal (session-aware) conditions**, for example "approval granted before transfer" or "budget totals", plus signals from Guardrails, via the Dogwood policy language. (High, AWS docs; check GA status per region.)
  - Example policy intent (pseudo-Cedar, illustrative only):

```cedar
// Allow SendMail only with a fresh, user-bound approval and no untrusted taint on recipients/body links
permit (principal, action == Action::"SendMail", resource)
when { context.approval.userConfirmed && context.approval.ageSeconds < 300
       && !context.taint.recipientsFromUntrusted && !context.taint.linksFromUntrusted };
forbid (principal, action == Action::"SendMail", resource)
when { context.recipientDomains.containsAny(resource.tenant.blockedDomains) };
```

### 5.6 Memory-write validation and audience ACLs (contextual integrity)

**Write path:** candidate memory → provenance stamp → type classifier → policy → (quarantine) → store.

| Step | Rule |
|---|---|
| Provenance | Each memory carries: source item ID(s) (Graph IDs), channel, author class (`user` / `internal` / `guest` / `external-known` / `external-unknown` / `transcript-other-speaker`), timestamp, sensitivity label, extraction model version |
| Type | `style` · `preference` · `fact` · `commitment` · `relationship` · `contact-detail` · `instruction-like` |
| Policy | **`style` and `preference` only from `user`-authored content.** `instruction-like` is always rejected; we store no standing instructions from content. `contact-detail` and payment changes need explicit user confirmation. External-derived `fact`s are low-trust and never used for external drafts without corroboration |
| Trust score (example) | user 1.0 · internal 0.7 · external-known 0.4 · external-unknown 0.2 · other-speaker transcript 0.3, × corroboration (independent sources) × recency decay. Below 0.5 → not retrievable for drafting, visible in review UI |
| Quarantine | Suspicious writes (imperatives, "always/never/remember/from now on", URLs, bank/UPI/IFSC/IBAN, "new address/number") go to a user-review queue and expire unreviewed after N days |

**Audience ACL** is derived from the source's sender and recipients, plus label and tenant rules:
- `PRIVATE`: user-only notes and drafts; Highly-Confidential labels by default.
- `NAMED`: the specific people on the source thread.
- `INTERNAL-ALL`: all-company announcements.
- `EXT-ORG:<domain>`: threads with a given external organisation.
- `PUBLIC`.

At draft time, retrieval returns only memories whose audience covers **every** recipient. This one control addresses PA-07, PA-11 and much of PA-01's impact.

### 5.7 Tenant isolation (and metadata-filter pitfalls)

- **Silo the data plane per tenant:**
  - Vector index (or collection) per tenant.
  - Per-tenant KMS CMK.
  - Separate AgentCore Memory resources (or strictly namespaced actor IDs) per tenant.
  - Aurora PostgreSQL row-level security keyed on a session variable set from the **verified token's `tid`**, never from request parameters.
  - Large enterprise tenants can get dedicated schemas or clusters.
  - If a graph store is adopted, enforce tenancy in a single data-access layer.
  - (Details on cost and limits are in the data-layer track.)
- **Common pitfalls:**
  - (1) Filters built from client-supplied IDs.
  - (2) New code paths (re-indexers, analytics, admin tools, eval jobs) that skip the filter.
  - (3) Post-filtering after approximate kNN, which drops recall; engineers then "fix" it by loosening filters.
  - (4) Shared caches keyed without tenant/user. The ChatGPT Mar 2023 incident was a cache-layer bug (Med).
  - (5) Shared prompt-cache prefixes containing tenant data.
- **Controls:**
  - A mandatory `TenantContext` type in the data-access layer; constructors that bypass it are blocked in CI.
  - Two always-on **canary tenants** seeded with unique marker strings.
  - Property-based tests asserting no query ever returns another tenant's canary.
  - Per-tenant encryption so that a bad filter returns undecryptable ciphertext rather than plaintext. This is a strong reason for per-tenant keys at the application layer.

### 5.8 Identity, OAuth and token management

- **App credentials:** use Entra **workload identity federation**. Microsoft documents AWS workloads obtaining a JWT from **IAM Outbound Identity Federation** (`sts:GetWebIdentityToken`) and presenting it as a federated credential. There is then **no client secret or certificate to steal**, and token issuance is IAM-policy-controlled and logged. (High, Microsoft + AWS docs.) Verify in the PoC that this works for our multi-tenant, delegated auth-code + refresh flow; if not, use a certificate whose private key lives in KMS and sign client assertions via `kms:Sign`.
- **Refresh tokens:** default lifetime is 90 days; they are bound to user+client and can mint tokens for any consented resource; old ones are not revoked on use (Microsoft docs). Storage rules:
  - Encrypt under per-tenant keys (AgentCore Identity token vault supports customer-managed KMS keys).
  - Delete superseded tokens.
  - Only the ingestion role may decrypt.
  - Alert on any decrypt by another principal.
  - Offer the tenant a one-click "revoke all PersonaAgent sessions".
- **Consent posture:** we are now admin-consent-only for mail/chat scopes (cross-track). Supporting steps:
  - Publisher verification.
  - Microsoft 365 App Compliance attestation, then certification for Enterprise (Med).
  - A security page listing our app IDs, scopes and redirect URIs, so customers can spot look-alike consent phishing.
  - Validate `iss`/`tid` on every token and key users on `oid`+`tid`, never on email (the "nOAuth" class; Med).
- **Customer-side detection we should document:** sign-in and Graph activity logs for our app ID, Conditional Access for workload identities (Med), and CAE support so revocations take effect quickly.

### 5.9 Encryption and key hierarchy

- **Envelope encryption everywhere:** per-tenant KMS CMK → **per-user branch keys** using the AWS **KMS Hierarchical keyring** (Database Encryption SDK). Branch keys live in a DynamoDB key store wrapped by KMS, and branch-key materials are cached locally. The docs give an example of one KMS call serving 10,000 encrypt operations within the cache TTL, and recommend a branch-key-ID supplier for multi-tenant data. (High)
- **Searchable encryption beacons** (HMAC-based, from the same SDK) let the vault find "the token for this value" without decrypting the table. (High: feature documented; fit for our vault is my design inference.)
- **Crypto-shredding:** deleting a user's branch key makes every vault entry and field-encrypted record for that user unreadable, including in backups. This is the backbone of deletion guarantees (Microsoft API Terms, DPDP erasure, offboarding).
- **BYOK / HYOK (Enterprise):** tenant-owned KMS key via cross-account grants, or **KMS External Key Store (XKS)** for keys held outside AWS (Med). Revoking the key acts as a tenant kill switch.

### 5.10 Confidential computing for the tokenisation vault (Enterprise option)

AWS **Nitro Enclaves** integrate with KMS attestation. Key policies can require `kms:RecipientAttestation:ImageSha384` and PCR values, so **only a specific measured enclave image** can decrypt. KMS responses are encrypted to the enclave's key, so even root on the parent instance cannot read them (High, AWS docs). Run token re-hydration and vault lookups inside an enclave so our own operators cannot reveal values. That is an "operator-blind" claim Enterprise buyers value.

Costs:
- EC2-based (not Lambda), with vsock-only I/O.
- More complex build and reproducibility pipeline.
- ~1–2 engineer-months.

Defer past the MVP.

### 5.11 Detection, monitoring and response

- **Agent-action anomaly detection:** generation volume per user, new external domains in drafts, drafts with money or bank terms, unusual re-hydration counts, memory-write bursts from a single external sender, Graph read volume spikes, and token decrypts by unexpected roles.
- **Platform:** CloudTrail (management + data events for KMS and S3), GuardDuty, Security Hub, AWS Budgets / Cost Anomaly Detection (denial of wallet), SCPs restricting `bedrock:InvokeModel*` to specific roles, models and regions.
- **Incident clocks we must meet:**
  - **CERT-In: 6 hours** to report (India).
  - **DPDP: 72 hours** detailed report to the Board once Phase III applies (13 May 2027).
  - US state breach-notification timelines (per state; legal track).
  - **GLBA/FTC Safeguards** notification for financial-institution customers' data (Med; see §6.5).

  Runbooks must name who files what.

### 5.12 Red-teaming, testing and assurance

- **Tools:**
  - **garak** (NVIDIA): LLM vulnerability scanner.
  - **PyRIT** (Microsoft): red-teaming orchestration.
  - **promptfoo**: eval and red-team configs in CI.
  - **AgentDojo**: agent prompt-injection benchmark used by the CaMeL paper.

  Ownership and licensing changes are possible in this fast-moving space (e.g., reported acquisitions in 2026; *not verified here*), so pin versions and review licences.
- **Our own corpus:** a few hundred realistic malicious emails, Teams messages, invites and transcripts (US + India, English + Hinglish) covering every §2 technique. Run it on every model or prompt change, and track attack success rate as a release metric.
- **External assurance:**
  - Pentest (web, add-in, mobile per OWASP MASVS) before GA.
  - Private bug bounty at beta, public at GA.
  - SOC 2 Type I → Type II.
  - ISO 27001 (also relevant in India because the SPDI Rules treat IS/ISO/IEC 27001 as a reasonable-security standard).

### 5.13 Secure SDLC and supply chain (lessons from LiteLLM, postmark-mcp, Rabbit R1)

- Hash-pinned lockfiles. A private registry proxy with malware scanning and a **cool-down period for new versions**. GitHub Actions and CI tools pinned by commit SHA (the LiteLLM chain started from an unpinned Trivy). OIDC-based short-lived CI credentials. Signed artefacts with provenance.
- No third-party MCP servers or agent "skills" in the data plane. Internal tools only, behind AgentCore Gateway.
- **Rabbit R1 lesson:** no vendor API keys in clients, repos or mobile apps. Clients call our backend with user-bound tokens; backend services use workload identities; keys are scoped, rotated and monitored. Use secret scanning (gitleaks) in pre-commit and CI.
- Threat-model every feature touching untrusted content, memory, recipients or egress, and have a security reviewer sign off on prompts and policies like code.

### 5.14 Phone / recorder security (Pillar 2, work-only)

- **Capture policy is set by the tenant:** allowed hours and locations, auto-mute for calendar categories (HR, legal, medical, interviews), mandatory visible and haptic indicator, a one-tap mute that also deletes the last N minutes, and consent prompts or announcements per legal-track guidance.
- **Device protections:** audio buffered encrypted (iOS Data Protection *Complete* / Android Keystore, StrongBox where available), uploaded over TLS with certificate pinning, then purged (target ≤24 h on device). No audio in OS backups. Biometric app lock. Short-lived device tokens. Remote wipe. Enterprise: Intune MAM app-protection policies.
- **Server side:** transcribe, then discard audio by default (§6.9). No voiceprint enrolment in v1 (voiceprints are HIPAA Safe-Harbor identifiers and biometric data under US state laws).
- **Benchmark to meet:** Microsoft's Recall redesign. Opt-in, TPM-bound keys, VBS enclave processing, Windows Hello gating with timeouts, and sensitive-content filtering "on by default" for passwords, national IDs and card numbers. (High)

## 6. Multi-level redaction architecture (deep dive)

### 6.1 Design principles

1. **Minimise first, redact second.** M365 stays the system of record. In the MVP we store **no raw (L0) content at all**: processing happens in memory and failures re-fetch by Graph ID. This also follows the Microsoft API Terms constraint (no copying beyond the intended use; deletion on abandonment).
2. **Irreversible for regulated identifiers, reversible for everyday PII, contextual for company secrets.**
3. **Data levels are contracts.** Every component declares the highest level it may read, and IAM, KMS key policies and code-level types enforce it.
4. **Fail closed.** If detection cannot run or is unsure, the item does not progress.
5. **Measure.** Every detector class has a recall SLO tested on US and India corpora (§6.12).

### 6.2 Data levels and who may consume them

| Level | Definition | Persistence | Legal character |
|---|---|---|---|
| **L0 Raw** | Content exactly as fetched from Graph or produced by STT | **MVP: none** (in-memory only; re-fetch by ID). Enterprise option: customer-keyed raw archive for re-processing, ≤N days | Personal data / PHI / CPRA SPI |
| **L1 Pseudonymised** | Tier-R values **irreversibly masked**; Tier-P values replaced by **consistent reversible tokens**; Tier-S flagged and generalised for memory; Tier-C per tenant policy (default: dictionary terms tokenised) | Stored (memory, persona KB, vectors), per-tenant/per-user keys | Still personal data (pseudonymised data stays personal data under DPDP/CPRA; PHI under HIPAA) |
| **L2 Business-masked** | L1 + Tier-C masked or generalised (amounts → magnitude buckets, codenames → `⟦PROJECT⟧`, privileged/HR passages dropped) | Derived views only | Personal data (reduced) |
| **L3 Anonymised / aggregate** | No free text, no tokens, **no style vectors**; counts/rates with k ≥ 10 (optional DP noise); for HIPAA tenants, Safe-Harbor-compliant only | Analytics store | Intended to be non-personal; re-identification risk reviewed |
| **Display (re-identified)** | L1 + vault re-hydration for the entitled user/delegate | **Never stored**; rendered in client session only | – |

| Component | L0 | L1 | L2 | L3 | Vault |
|---|---|---|---|---|---|
| Graph fetcher / ingestion worker | transient (in memory) | write | – | – | – |
| Redaction service | transient read | write | write | – | create / lookup (no reveal API) |
| Persona learner | – | read (**user-authored only**) | read (if tenant chooses L2 persona) | – | – |
| Memory extractor (quarantined reader) | – | read/write (provenance + ACL) | – | – | – |
| Drafting generator (LLM) | live thread → L1 on the fly | read (ACL-filtered) | – | – | – |
| Re-hydrator | – | read draft | – | – | **reveal**, allow-listed tokens for this request |
| Memory Q&A for the user | – | read | – | – | reveal (user session) |
| Product analytics / billing | – | – | – | read | – |
| Evals / model improvement | – | synthetic or **consented** L1 only | – | read | – |
| Platform support | – | break-glass only (§8) | break-glass default view | metadata | never |
| Logs / traces / alerts | – | – | – | metadata only | never |

### 6.3 Entity tiers and default actions

| Tier | Examples | L1 | L2 | L3 | May the LLM ever see the raw value? |
|---|---|---|---|---|---|
| **R: Regulated identifiers & secrets** | Card PAN/CVV/expiry/track/PIN · SSN/ITIN · Aadhaar/VID · passport · driver's licence · bank account numbers / IBAN · health IDs (MBI, ABHA, MRN, member IDs) · passwords/OTPs/API keys/private keys/tokens · biometric identifiers | **Irreversible mask at first touch**, e.g. `⟦AADHAAR:XXXX-XXXX-1234⟧`, `⟦CARD:****1234⟧`, `⟦SECRET:aws_access_key⟧`; no vault entry | same | removed | **No** |
| **P: Direct personal identifiers** | Names, emails, phones, postal addresses, UPI IDs, personal PAN, EPIC, DOB, employee IDs, IPs, personal URLs, vehicle regs | Consistent reversible token `⟦PERSON_7a2c⟧` (+ surface-form variants) | token or generalised (DOB → year) | removed | Only via re-hydration in the user's session |
| **S: Special-category content** | Health conditions, disability, sexual orientation, religion/**caste**, political/union, criminal history, financial hardship, children's data, precise location | Kept in live-thread context; **excluded from long-term memory by default**; named entities tokenised; flagged | masked | removed | Live thread only |
| **C: Company-sensitive** | Client names, codenames, unreleased financials, M&A, pricing/discounts, legal-privileged, HR matters, security incidents, MNPI/UPSI | Tenant policy: keep / tokenise (`⟦CLIENT_x⟧`, `⟦PROJECT_y⟧`) / exclude | masked/generalised | removed | Per tenant policy |

### 6.4 Detector catalog — Phase 1 (United States + India), with validation logic

**Pre-normalisation for every detector:**
- NFKC Unicode normalisation.
- Strip zero-width and Unicode tag characters.
- Map **Devanagari digits ०–९ → 0–9** and full-width digits → ASCII.
- Collapse separators inside digit runs (spaces, dots, dashes, slashes).
- Inverse text normalisation for spoken numbers, including Indian-English "double five" / "triple zero".
- Homoglyph folding for Latin/Cyrillic look-alikes.

Detection runs on both the normalised and the original text, and offsets are mapped back to the original.

**Context lexicons** are bilingual. They include English, romanised Hindi and Devanagari cues: *aadhar/आधार*, *khata sankhya/खाता संख्या* (account number), *PAN card*, *UPI ID*, *bhejo* (send) near numbers, and so on.

#### 6.4.1 United States

| Identifier | Pattern (sketch) | Validation logic | Context cues | FP risks / notes | Tier → default action | Conf. |
|---|---|---|---|---|---|---|
| **SSN** | `\d{3}[- ]?\d{2}[- ]?\d{4}` | Area ∉ {000, 666, 900–999}; group ≠ 00; serial ≠ 0000. Since SSA randomisation (25 Jun 2011), do **not** use legacy "highest group" tables. Treat famous invalid/advertising numbers (e.g., 078-05-1120) as test values but still mask | SSN, social security, SS#, soc sec, "last four" | Unformatted 9-digit runs collide with ZIP+4, order IDs and phone extensions, so require context when unformatted. Partial "last 4 of SSN" → mask | **R** → `⟦SSN:***-**-1234⟧` (last-4 optional) | High (rules); Med (invalid-number list) |
| **ITIN** | `9\d{2}[- ]?\d{2}[- ]?\d{4}` | First digit 9; 4th–5th digits within IRS-issued ranges (50–65, 70–88, 90–92, 94–99) | ITIN, taxpayer identification | AWS Comprehend/Guardrails define ITIN as "7 or 8 as the fourth digit", which **may miss 5x/6x/9x ranges**. Add our own recogniser and test it | **R** | Med (IRS ranges from IRS guidance, not re-fetched); High (AWS definition) |
| **EIN** | `\d{2}-\d{7}` (unformatted needs context) | Prefix ∈ IRS valid set **01–06, 10–16, 20–27, 30–48, 50–68, 71–77, 80–88, 90–95, 98–99**. Invalid: 00, 07–09, 17–19, 28–29, 49, 69–70, 78–79, 89, 96–97 | EIN, FEIN, employer ID, tax ID | Business ID, except sole proprietors | **P/C** → token | High (IRS prefix list) |
| **US passport** | `[A-Z]?\d{8,9}` | Book: 9 digits (legacy) or 1 letter + 8 digits (Next Generation); passport card: `C` + 8 digits | passport, PPT, passport card | Many 9-digit collisions, so context is required | **R** | Med |
| **Driver's licence** (largest states) | CA `[A-Z]\d{7}`; TX `\d{7,8}`; FL `[A-Z]\d{12}`; NY `\d{9}` (+ legacy); IL `[A-Z]\d{11}`; PA `\d{8}`; NJ `[A-Z]\d{14}`; WA `WDL[A-Z0-9]{9}` | Format only; no public checksums (FL/IL derive parts from name and DOB) | DL, DLN, driver's licen[cs]e, state names | High collision rate, so context is mandatory. Validate against AAMVA sample data | **R** | Med |
| **ABA routing** | `\d{9}` | Prefix 00–12, 21–32, 61–72, 80. Checksum `3(d1+d4+d7) + 7(d2+d5+d8) + (d3+d6+d9) ≡ 0 (mod 10)` | routing, ABA, RTN, wire | Public bank ID; **routing + account = financial account** | P (keep/token); escalates the paired account to **R** | High (checksum); Med (prefixes) |
| **US bank account** | `\d{4,17}` | None (no standard). Requires context or adjacency to a valid ABA/SWIFT/IBAN | acct, account no., checking, savings, beneficiary, a/c | Very FP-prone without context | **R** → `⟦BANK_ACCT:…1234⟧` | High |
| **Payment card (PAN)** | 12–19 digits with optional separators | **Luhn mod-10** + IIN ranges: Visa 4; Mastercard 51–55, 2221–2720; Amex 34/37 (15 digits); Discover 6011, 644–649, 65; JCB 3528–3589; Diners 300–305/36/38–39; UnionPay 62; **RuPay** 60/65/81/82/508 | card, credit, debit, Visa, MC, CVV | Also detect **CVV** (3–4 digits near CVV/CVC/CID), **expiry** (MM/YY near card terms), **track data** (`%B…^…^`, `;…=…`), PIN | **R** → truncate to last 4 in memory at first touch; drop CVV/expiry/track/PIN; never persisted | High (Luhn, major IINs); Med (RuPay ranges) |
| **Medicare MBI** | `[1-9][AC-HJKMNP-RT-Y][AC-HJKMNP-RT-Y0-9]\d[AC-HJKMNP-RT-Y][AC-HJKMNP-RT-Y0-9]\d[AC-HJKMNP-RT-Y]{2}\d{2}` | CMS: 11 chars. Pos 1 = 1–9; pos 2, 5, 8, 9 = letters excluding S, L, O, I, B, Z; pos 3, 6 = letter or digit; pos 4, 7, 10, 11 = digits; dashes are not part of the ID | Medicare, MBI, beneficiary | Low FP thanks to the structure | **R** (PHI) | High (CMS) |
| **NPI** | `[12]\d{9}` | Luhn over the prefix `80840` + first 9 digits (equivalently, add 24 to the Luhn sum) must give digit 10 | NPI, provider, prescriber | Public registry, so mainly a **PHI-context signal** | P → token | High (CMS standard) |
| **DEA number** | `[A-Z][A-Z9]\d{7}` | `(d1+d3+d5) + 2·(d2+d4+d6)`; last digit = d7. Letter 2 = initial of registrant's surname or business | DEA, Rx, controlled substance | Fraud-sensitive provider ID | P/C → token | High (checksum); Med (letter semantics) |
| **Health plan member ID / MRN / claim no.** | No standard | Context-driven (Presidio ships US_HEALTH_INSURANCE_MEMBER_ID, US_CLAIM_NUMBER, US_PRIOR_AUTHORIZATION_NUMBER recognisers) | member ID, MRN, medical record, policy, claim | Tenant-specific formats via custom regex | **R** | High (no standard exists) |
| **HIPAA dates / ages / geography** | Date parsers; address NER | Dates tied to an individual (DOB, admission, discharge, death) → token in L1, **year only** in L2/L3. Ages > 89 → "90+". ZIP → first 3 digits in L3, `000` where ≤ 20,000 people | DOB, born, admitted, discharged | – | P (+ HIPAA preset rules) | High (45 CFR 164.514(b)(2)) |
| Phone / fax / email / IP / URL / VIN / device serials | libphonenumber (US), RFC 5322, IPv4/IPv6, VIN check digit (pos. 9, North America) | Standard validators | – | Signature blocks are the main source | **P** → token | High |

#### 6.4.2 India

| Identifier | Pattern (sketch) | Validation logic | Context cues | FP risks / notes | Tier → default action | Conf. |
|---|---|---|---|---|---|---|
| **Aadhaar** | `[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}` | 12 digits; first digit 2–9; **Verhoeff** check digit; reject palindromes (Presidio's IN_AADHAAR implements all three). Also recognise masked forms `XXXX XXXX 1234` | Aadhaar, Aadhar, UID, UIDAI, आधार, e-Aadhaar | A random 12-digit number passes Verhoeff ~10% of the time, so keep context scoring. Collides with UAN | **R** → keep **last 4 only**, never stored in full | High |
| **Virtual ID (VID)** | 16 digits (`\d{4}( ?\d{4}){3}`) | Checksum scheme not confirmed, so **context required**. If Luhn + IIN valid → treat as card instead | VID, virtual ID | Collides with card numbers | **R** → last 4 | Med-Low |
| **PAN** | `[A-Z]{3}[ABCFGHJLPT][A-Z]\d{4}[A-Z]` | 4th char = holder type (P individual, C company, H HUF, F firm/LLP, A AOP, T trust, B BOI, L local authority, J artificial juridical person, G government); 5th = surname/entity initial; 10th = check letter (algorithm not public) | PAN, permanent account number, ITR, TDS, Form 16 | Company PANs on invoices are low sensitivity | **P** (holder `P`) → token; entity PAN → C/P | High (structure); Med (category list) |
| **GSTIN** | `\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]` | State code (01–38, 97); embedded PAN; 13th = entity number; 14th = `Z`; 15th = check char by **mod-36 (Luhn-mod-N)**: map 0–9/A–Z → 0–35, multiply positions 1–14 alternately by 1, 2, sum `⌊p/36⌋ + p mod 36`, check = `(36 − sum mod 36) mod 36`. Presidio validates **structure only** | GSTIN, GST no., GST registration | Sole-proprietor GSTIN embeds a **personal PAN** | P/C → token; mask the embedded PAN if 4th char = `P` | High (structure); Med (checksum, codes 38/97) |
| **TAN** | `[A-Z]{4}\d{5}[A-Z]` | Structure only | TAN, TDS | Business | C → token | Med |
| **Voter ID (EPIC)** | `[A-Z]{3}\d{7}` | Structure only. Legacy state formats with slashes need context | EPIC, voter ID, election card | – | **P** → token | High (current format, per AWS); Med (legacy) |
| **Indian passport** | `[A-Z]\d{7}` | Structure only. Context mandatory (**no Purview SIT**, so our own detector) | passport, passport no., file no. | 8-char collisions | **R** | Med |
| **Driving licence** | `[A-Z]{2}[ -]?\d{2}[ -]?(19\|20)\d{2}[ -]?\d{7}` | State code + RTO code + issue year + 7-digit serial; legacy formats vary by state | DL, driving licence | Context mandatory | **R** | Med |
| **IFSC** | `[A-Z]{4}0[A-Z0-9]{6}` | 5th char always `0` | IFSC, NEFT, RTGS, IMPS | Public branch code; **pairs with account → R** | P (keep); escalates paired account | High |
| **Indian bank account** | `\d{9,18}` | None. Context or adjacency to IFSC required | A/c, account no., SB/CA, beneficiary, खाता संख्या | Very FP-prone without context | **R** → last 4 | High (no standard) |
| **UPI ID / VPA** | `[A-Za-z0-9._-]{2,256}@[A-Za-z][A-Za-z0-9]{2,64}` with **no dot after `@`** (separates it from email) | Boost on known PSP handles (e.g., `@okhdfcbank`, `@okicici`, `@oksbi`, `@okaxis`, `@ybl`, `@ibl`, `@axl`, `@paytm`, `@upi`); maintain the list from NPCI | UPI, GPay, PhonePe, Paytm, BHIM | Local part is often a **mobile number** (double PII). **No Purview SIT** | **P** → token; **BEC alert** if it appears in a "new payment details" context | Med |
| **Indian mobile** | `(\+?91[\s-]?\|0)?[6-9]\d{9}` | libphonenumber `IN`; groupings like `98765 43210` | mobile, mob., ph., WhatsApp | – | **P** → token | High |
| **CKYC number** | `\d{14}` | Context only | CKYC, KYC identifier, CERSAI, KIN | 14-digit collisions (incl. ABHA) | P/R → token | Med |
| **ABHA number / address** | `\d{2}-\d{4}-\d{4}-\d{4}`; `name@abdm` | Context; health-ID semantics | ABHA, Ayushman Bharat, ABDM, health ID | Health identifier | **R** | Med |
| **UAN (EPFO)** | `\d{12}` | Context, plus failing Verhoeff makes it less likely to be Aadhaar | UAN, EPF, PF | Collides with Aadhaar | P → token | Med |
| **Vehicle registration** | `[A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{1,3}[ -]?\d{4}`; BH series `\d{2}BH\d{4}[A-Z]{1,2}` | Presidio IN_VEHICLE_REGISTRATION available | vehicle, RC, registration | – | P → token | Med |
| **CIN** (company) | `[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}` | Structure | CIN, MCA | Company identifier | C (keep/token) | Med |
| **NREGA job card** | 2 letters + 14 digits | Structure (AWS `IN_NREGA`) | NREGA, job card | – | P → token | High |

#### 6.4.3 Secrets and credentials (both regions)

Use **gitleaks-style provider rules** (patterns only) for:
- AWS (`AKIA`/`ASIA` + 16 chars; 40-char secret near an access-key ID)
- GitHub (`ghp_`, `gho_`, `ghs_`, `github_pat_`)
- Slack (`xox[abprs]-`)
- Google API keys (`AIza…`)
- Stripe (`sk_live_`)
- JWTs (`eyJ….eyJ….`)
- PEM private-key blocks
- Azure storage `AccountKey=` / SAS `sig=`
- DB connection strings with credentials
- `user:pass@` in URLs
- Context-cued passwords and OTPs ("password:", "pwd", "OTP is 482913")

**Disable all "live verification".** TruffleHog-style verification calls the provider with the secret, which would itself be a data egress and a misuse of customer credentials.

Action: **R**, irreversible mask, plus an optional "credential exposed in mail" notice to the user/tenant. Salesloft Drift attackers specifically mined stolen data for `AKIA` keys, passwords and Snowflake tokens (GTIG). Credentials never enter memory or persona.

#### 6.4.4 Company-sensitive (Tier C) detection

| Category | Primary signals | Secondary signals |
|---|---|---|
| Client / customer names | Tenant dictionary (CRM export, top accounts) | Email domains of external participants; LLM classifier |
| Project codenames | Tenant codename list | Capitalised unknown terms + "Project/Operation/Codename" cues |
| Unreleased financials | Number + finance terms (revenue, EBITDA, guidance, forecast, "unaudited", ₹ crore/lakh, $M) | Sender role (Finance), labels |
| M&A / deals | LOI, term sheet, NDA, data room, valuation, "target" + org entity | Legal/corp-dev participants |
| Pricing & discounts | price/discount/% off/rate card near client tokens | Sales threads |
| Legal-privileged | "Privileged & Confidential", "attorney-client", "without prejudice", counsel domains | Outside-counsel participants |
| HR matters | performance, PIP, termination, compensation, grievance, **POSH** complaint, medical leave | HR participants; Tier-S overlap |
| MNPI / UPSI | Listed-company results before release, deal talks | Tenant flag "listed entity" |
| Purview signals | `MSIP_Labels` header (label GUID → tenant mapping); Teams `policyViolation` | Customer SIT matches (Enterprise, via Purview APIs) |

The classifier runs on L1 text using a constrained schema (`category`, `span`, `confidence`, `rationale`). Its output is treated as **untrusted labels**: an attacker can try to inject the classifier too, so labels can only *add* restrictions, never remove them.

### 6.5 Regulatory treatment mapping (implementation-oriented; the legal track owns the authoritative map)

#### United States

| Regime | When it reaches PersonaAgent | Data classes | What it requires / implies | How the design satisfies it | Conf. |
|---|---|---|---|---|---|
| **HIPAA** (Privacy & Security Rules) | A covered-entity or business-associate tenant puts PHI in mail, Teams or meetings → we are a **business associate** (BAA required) | 18 Safe-Harbor identifiers: names; sub-state geography (ZIP 3-digit rule); dates except year and ages > 89; phone; fax; email; SSN; MRN; health-plan beneficiary no.; account no.; certificate/licence no.; vehicle IDs; device IDs; URLs; IPs; **biometrics incl. voiceprints**; full-face photos; any other unique ID (45 CFR 164.514(b)(2)) | Security Rule safeguards (risk analysis, access control, audit, integrity, transmission security). De-identification only via Safe Harbor (plus "no actual knowledge") or Expert Determination. **Re-identification codes must not be derived from identifiers** (164.514(c)) | `US-HIPAA` preset: all 18 identifiers handled as R/P. L3 = Safe-Harbor rules (year-only dates, ZIP3/000, 90+). **No token IDs or blind indexes in L3** (our tokens are random IDs; the derived blind index never leaves the vault). No voiceprints. Use HIPAA-eligible AWS services under AWS's BAA (confirm Bedrock/AgentCore eligibility per region). We note AWS states Transcribe redaction "does not meet the requirements for de-identification under … HIPAA" | High (rule text); Med (service eligibility) |
| **GLBA** (Privacy Rule + FTC Safeguards Rule, 16 CFR 314) | Tenants that are "financial institutions" (banks, lenders, brokers, fintech, tax preparers) → we are their **service provider** | NPI: account numbers, balances, SSNs, income/credit data, the fact of a customer relationship | Written infosec programme: risk assessment, access controls, **encryption in transit and at rest**, MFA, secure disposal (≈ 2 years after last use unless needed), change management, monitoring, annual pentest + 6-monthly vulnerability scans, IR plan; FTC notice within 30 days for "notification events" involving ≥ 500 consumers' unencrypted data (since May 2024) | `US-GLBA-FI` preset: account numbers R; customer names P; per-customer financial figures C/S; retention schedule; vendor-assurance pack (SOC 2, pentest, IR SLAs) | Med (well known; not re-fetched) |
| **PCI DSS v4.0.1** | Users email card numbers (it happens) | PAN; sensitive authentication data (CVV2, full track, PIN) | **3.3.1** SAD not retained after authorisation, even encrypted. **3.4.1** display at most BIN + last 4. **3.5.1** PAN unreadable wherever stored (truncation, hashing of the full PAN, index tokens, strong crypto) | **Truncate PAN to last 4 in memory at first touch; drop CVV/expiry/track/PIN; never persist**; drafts cannot contain PANs. Aim: our systems never *store* CHD. Confirm scoping with a QSA | High (requirements); Med (scoping) |
| **CCPA/CPRA** (Cal. Civ. Code §1798.100 ff.) | Tenants that are CPRA "businesses"; employee and B2B data in scope | **SPI includes "contents of a consumer's mail, email, and text messages unless the business is the intended recipient"**, plus SSN/DL/state ID/passport, account log-in or card number with access code, precise geolocation, biometrics, health, sex life, neural data (§1798.140(ae)) | Service-provider contract limits (purpose limitation, **no combining data across customers**), security, help with consumer requests, limits on SPI use | All ingested content is treated as SPI. Single purpose (the user's own persona and memory). **No cross-tenant learning.** Deletion and export workflows. Contract templates | High (SPI text) |
| **State breach-notification laws** | Any breach of tenant data | Name + SSN / DL / state ID / financial account or card with code; many states add username + password, biometrics, health/insurance data, passport, TIN | Notice to individuals/AGs; timelines vary (legal track). **Encryption safe harbour** if keys are not compromised | Tier R removes most triggering elements. Per-tenant keys held separately from data keep the safe harbour. Per-tenant inventory of held elements speeds breach scoping | Med |
| **Illinois BIPA & similar biometric laws; all-party-consent wiretap laws** | Recorder (Pillar 2) | Voiceprints / speaker embeddings; recorded conversations | Written release, retention schedule (BIPA, private right of action); consent rules per state | **No voiceprint enrolment in v1**; per-session diarisation only. Tenant recorder policies + consent prompts (legal track) | Med |

#### India

| Regime | When it reaches PersonaAgent | Data classes | What it requires / implies | How the design satisfies it | Conf. |
|---|---|---|---|---|---|
| **DPDP Act 2023 + DPDP Rules 2025** | Tenant = Data Fiduciary for employee/contact data; we = **Data Processor** under contract (Fiduciary for our own account data) | All digital personal data (no special categories in the Act) | Rules notified **13 Nov 2025**: Board provisions immediate; consent managers +12 months (**13 Nov 2026**); substantive obligations +18 months (**13 May 2027**). Security safeguards incl. "**encryption, obfuscation or masking or the use of virtual tokens**", access control, monitoring logs, backups; **retain logs/personal data ≥ 1 year** for specified purposes; breach intimation to the Board within **72 h** (detailed) and to affected principals; erasure when purpose ends or consent is withdrawn; cross-border transfer allowed except to notified countries; SDF duties (India-based DPO, DPIA, audit, algorithmic due diligence, possible localisation). Penalty up to **₹250 crore** for security-safeguard failures | `India-DPDP` preset: tokenisation vault = "virtual tokens"; per-tenant keys; metadata logs kept 1 year in-region; 72 h breach runbook; crypto-shredding for erasure; **India tenants pinned to AWS India regions** by default; DPIA support pack for SDF customers | High (DLA Piper summary of the Rules) |
| **IT Act s.43A + SPDI Rules 2011** | Still applies **until DPDP Phase III (13 May 2027)** | "Sensitive personal data": **passwords; financial info (bank account, card, payment instrument); physical/physiological/mental health; sexual orientation; medical records; biometrics** | Reasonable security practices (IS/ISO/IEC 27001 recognised), consent/disclosure limits, grievance officer | SPD classes → Tier R/S; ISO 27001 roadmap; grievance contact in the India DPA | High (continuity); Med (rule text from memory) |
| **Aadhaar Act 2016 + UIDAI regulations/circulars** | Aadhaar numbers appear incidentally (HR onboarding, KYC, vendor forms) | Aadhaar number, VID, e-Aadhaar PDFs/QR | No public display/publication of Aadhaar numbers except as regulations allow; redact/mask in records; entities that **store** Aadhaar must use an encrypted, access-controlled **Aadhaar Data Vault** with **reference-key tokens** and HSM-protected keys (UIDAI circular, 2017) | **Never store full Aadhaar or VID**: irreversible mask to `XXXX XXXX 1234` at first touch. Skip e-Aadhaar attachments and secure QR codes. If a BFSI tenant ever needs reversibility, only via an ADV-grade vault (Nitro Enclave + KMS, reference tokens), Enterprise only | Med (circular not re-fetched) |
| **RBI directions** | BFSI tenants (banks, NBFCs, payment firms) | Card data; payment data; outsourced IT | Card-on-file tokenisation: only issuers/networks store actual card data (since Oct 2022); payment-data localisation for payment system operators; IT-outsourcing / IT-governance directions → vendor due diligence, audit rights, incident reporting to the regulated entity | `India-BFSI` preset: India-region pinning, **no cross-region inference**, card data R, audit-rights clause, incident notice to the RE well inside 6 h | Med |
| **CERT-In Directions (28 Apr 2022)** | We are a service provider / body corporate operating in India | Logs, incidents | Report specified incidents within **6 hours**; keep ICT logs for **180 days within Indian jurisdiction**; sync clocks to NIC/NPL NTP | India log archive in ap-south-1/ap-south-2 (metadata-only logs); NTP sources per the directions; IR runbook with a CERT-In filing step | High |
| **SEBI PIT Regulations (UPSI)** | Listed-company tenants | Unpublished price-sensitive information in mail/meetings | Insider-trading controls on UPSI sharing | Tenant flag "listed entity" → stricter Tier-C defaults; UPSI excluded from memory unless enabled; access logging | Med |

**EU/UK (later phase, brief):**
- GDPR: pseudonymised data is still personal data; Art. 9 special categories; DPIAs.
- National IDs with checksums: UK NINO, NHS (mod 11), IBAN (mod 97), ES DNI/NIE (letter check), IT Codice Fiscale, DE Steuer-ID, FR NIR (key 97), NL BSN (11-proof), PL PESEL. Presidio already ships recognisers for many of these.

### 6.6 Detection techniques and tools (what each is good for)

| Tool | Strengths | Gaps for PersonaAgent | Role in our stack | Conf. |
|---|---|---|---|---|
| **Amazon Comprehend PII** | Managed; universal types + **IN_AADHAAR, IN_PERMANENT_ACCOUNT_NUMBER, IN_VOTER_NUMBER, IN_NREGA**, US SSN/ITIN/bank/routing/passport; offsets + scores; ≤100 KB real-time, async batch redaction | **English and Spanish only**: no Hindi/Devanagari; per-character pricing (see track 03) | Optional secondary NER for English names/addresses; Indian-ID signal | High |
| **Bedrock Guardrails sensitive-info filters** | Inline on model I/O; BLOCK / ANONYMIZE / detect-only, separately for input and output; custom regex (≤500 chars, **no look-around**); code-aware | **No India types**; **does not evaluate tool-call args, tool results or tool definitions**; trace `match` returns raw PII; invocation logs keep the original input | Last-line backstop on every LLM call; custom regexes for Aadhaar/PAN/UPI/IFSC; prompt-attack signal | High |
| **Microsoft Presidio** (OSS) | Pluggable recognisers with context words; checksum validation (Aadhaar Verhoeff + palindrome; cards; IBAN; NPI…); US_MBI, US_NPI, health member/claim IDs; IN_PAN/AADHAAR/GSTIN/VOTER/PASSPORT/VEHICLE_REGISTRATION; anonymiser with custom operators | Default spaCy NER is weak on Indian names and Hinglish; GSTIN check is **structural only**; we own accuracy and ops | **Orchestration + deterministic layer**, extended with our validators (§6.4) | High |
| **GLiNER / NVIDIA GLiNER-PII** (Oct 2025) | Label-set-at-inference NER; 55+ PII/PHI types; ~570M params; strict F1 **0.70** (Argilla PII), **0.64** (AI4Privacy), **0.87** (Nemotron-PII) at threshold 0.3 | NVIDIA model is **English only**; GPU needed for throughput; NVIDIA Open Model License | NER layer for names, addresses and contextual IDs; fine-tune a multilingual GLiNER variant on synthetic Indian data | High (model card) |
| **ai4privacy open-pii-masking-500k** | 580k rows, **8 languages incl. Hindi and Telugu**, CC-BY-4.0 | Synthetic; generic label set | Training/eval data for Indian slices | High |
| **IndicNER / Naamapadam** (AI4Bharat, ACL 2023) | 400k+ sentences, 11 Indic languages; F1 > 80 on 7 of 9 test languages | PER/LOC/ORG only; native scripts; news-like text | Devanagari slice of the ensemble | High |
| **LLM contextual classifier** (Claude on Bedrock, small/fast tier) | Understands context: company secrets, privilege, HR, health, Hinglish | Cost/latency; non-deterministic; injection-susceptible | Tier C/S classification; adjudicates uncertain spans; constrained JSON output; can only add restrictions | Med (design) |
| **Secret scanners** (gitleaks rules; TruffleHog-style detectors) | Large provider-specific rule sets | Built for code; verification makes network calls | Credentials layer, **verification disabled** | High |
| **Purview signals** | Customer's own labels/SITs; `MSIP_Labels`; Teams `policyViolation`; `processContent` | Depends on customer licensing; no SITs for IN passport/IFSC/UPI | Policy inputs; Enterprise draft DLP | High (cross-track) |
| **Amazon Transcribe PII** | Batch + streaming; **en-IN and en-US supported**; identification-only mode (streaming) | **No hi-IN**; streaming PII is applied only after segments complete; AWS: may miss PII, not HIPAA de-identification | First pass on transcripts; our text pipeline runs second | High |

**Public precision/recall evidence is thin and not comparable across tools.** Vendors (AWS) publish no accuracy figures. GLiNER-PII's numbers come from its own model card. No public benchmark was found for **Indian business email or Hinglish chat PII**. → We must build our own test sets (§6.12). (High: absence noted after searching.)

### 6.7 Reversible tokenisation vault

- **Token syntax.** `⟦TYPE_id⟧` uses U+27E6/U+27E7 brackets. `TYPE` comes from a closed set. `id` is a random 6–8-char base32 identifier unique per tenant (not derived from the value). Variant suffixes carry surface forms: `⟦PERSON_7a2c.first⟧`, `.full`, `.nick`. This lets the persona learn "uses a nickname with this contact" without ever seeing the name.
- **Determinism.** The same normalised value maps to the same token **within a tenant**. Normalisation rules:
  - lower-cased emails
  - E.164 phones
  - names stripped of honorifics (Mr/Ms/Dr/Shri/Smt/ji)
  - initials expanded where possible
  - Indian transliteration variants folded (aa/a, ee/i, v/w, sh/s)

  Lookup uses a **blind index** (HMAC with a per-tenant beacon key, via the AWS Database Encryption SDK's searchable encryption). The blind index stays inside the vault. Tier-S entities can use per-user scope to limit linkage.
- **Entity resolution.** "Rahul", "Rahul Sharma", "R. Sharma" and `rahul.sharma@contoso.com` are clustered using **M365 directory data and message headers** (From/To/CC display names). This is a high-precision, per-tenant name gazetteer we already have legitimate access to.
- **Storage and keys:**
  - The vault runs in a separate AWS account.
  - Values are encrypted with AES-256-GCM under per-user branch keys (hierarchical keyring), and the tenant CMK wraps the branch keys.
  - Only two roles can touch it: the redaction service (`create`/`lookup`, no reveal) and the re-hydrator (`reveal`).
  - KMS key policies deny everyone else, including platform admins.
- **Re-identification boundary.**
  - `reveal` requires user session context (tenant, user, request ID) and only covers tokens present in that request's authorised context.
  - Delegates are allowed only via policy.
  - Every reveal is audit-logged (token ID, type, purpose, requester) and rate-limited.
  - Re-hydration happens just before the client renders: the server-side re-hydrator in the MVP, and optionally client-side in the add-in later.
- **Token-spoofing defence (PA-25).**
  - Token-like strings in inbound content are escaped at ingestion.
  - Unknown or out-of-context tokens are never revealed.
  - Anomalies are alerted.
- **Format-preserving encryption: avoid it.** Our consumers are LLMs and our own code, so format preservation adds nothing. If ever required, use **FF1 only**. NIST SP 800-38G Rev. 1 (2nd public draft, Feb 2025) **removes FF3/FF3-1** because of a tweak-schedule weakness and requires a minimum domain size of 1,000,000. (High)
- **Performance.**
  - Per-request in-memory token maps.
  - The branch-key cache TTL (e.g., 5–15 min) amortises KMS calls (the AWS docs give an example of one KMS call for 10,000 operations).
  - Expect single-digit-millisecond lookups in-region. This is an estimate; benchmark it in the PoC.
- **Deletion.** Crypto-shred the user's branch key, then purge rows asynchronously.
- **Enterprise option.** A Nitro-Enclave vault (§5.10), for operator-blind claims and for an ADV-grade posture for Indian BFSI tenants.

### 6.8 Keeping persona quality while redacting

- **What the persona needs is mostly identity-free:**
  - greeting and sign-off habits
  - formality and directness per audience
  - sentence length and structure
  - hedging
  - bullets vs prose
  - emoji and punctuation
  - **code-switching patterns** (English↔Hinglish)
  - how the user delegates, pushes back or escalates

  Consistent tokens preserve all of this ("Hi ⟦PERSON_7a2c.first⟧ —").
- **Relationship modelling** uses token IDs plus directory attributes (title, department, internal/external, manager chain), not names.
- **Numbers** stay as-is in L1 unless they are Tier R, or the tenant's Tier-C policy generalises them (e.g., "₹⟦AMOUNT~10L⟧").
- **At draft time** the re-hydrator inserts the surface form this user actually uses for that recipient (nickname vs first name). For new contacts the client uses the header display name.
- **Over-redaction is a real quality risk.** Common Indian first names that are also ordinary words (Asha, Kiran, Pooja, Raja, Bharat) can be over-detected. Track precision per class; use context and directory confirmation before tokenising single-token names.
- **Validation.** Run an A/B test with consenting internal users: persona built on L0 (ephemeral, in-memory) vs L1. Measure with blind pairwise human preference plus stylometric distance. Hypothesis: no significant loss. **Unverified; needs our own experiment.**

### 6.9 Audio redaction (Pillar 2, work-only)

- **Pipeline:**
  1. Phone VAD.
  2. Encrypted upload.
  3. Amazon Transcribe streaming (`en-IN` / `en-US`) with **PII identification**, which gives entity spans and keeps the transcript intact for our own pass.
  4. Our text pipeline (§6.4) on the transcript.
  5. L1 transcript stored.
  6. **Audio deleted after transcript confirmation (MVP default).**
- **If a tenant chooses to retain audio:** we silence the PII segments ourselves using word-level timestamps of detected spans, encrypt under tenant keys, and enforce a TTL. Transcribe Call Analytics redacted-audio output is a possible alternative; *not verified this session*.
- **Hindi segments:** Transcribe PII redaction does not cover `hi-IN`, so our detectors run on Devanagari and romanised transcript text. Inverse text normalisation must handle "double/triple" digit idioms.
- **Teams meetings:** use Graph post-meeting transcripts (cross-track). This is the same text pipeline with no audio handling.
- **Speakers:** per-session diarisation labels only; **no persistent voiceprints** (HIPAA biometric identifier; BIPA). Other speakers' content gets low memory trust (§5.6).

### 6.10 Redaction in logs, traces and observability

- **Bedrock model-invocation logging:** disabled by default. When enabled it captures full request and response bodies (≤100 KB inline, larger bodies to S3), and Guardrails masking does **not** apply to those logs.
  - **Policy:** off in production.
  - Enable only for synthetic or test tenants.
  - For a support case, use a dedicated per-tenant-key bucket with a 7-day lifecycle behind break-glass. (High)
- **Never log Guardrails trace objects.** Their `match` field contains raw PII. (High)
- **Application logs:**
  - A logging wrapper accepts only allow-listed structured fields: IDs, counts, latencies, classes.
  - A CI test fails on content-bearing log calls.
  - **CloudWatch Logs data protection** policies act as a backstop.
  - A nightly scan of log samples runs with our detectors, plus canary strings.
- **Traces (OpenTelemetry / AgentCore Observability):** disable prompt/completion content capture and strip span attributes carrying text.
- **Crash and analytics SDKs (mobile, add-in):** no breadcrumbs with content and no screenshots; L3 events only.
- **CERT-In log retention:** keep metadata logs (not content) for 180 days in India.

### 6.11 Fail-closed behaviour, human review and tenant policy

- **Fail-closed rules:**
  - Any detector error or timeout → the item is not persisted; retry by re-fetching; after N failures, record an "un-ingested" marker with metadata only and alert.
  - Unknown language/script, or language-ID confidence below threshold → strict profile (all capitalised tokens and digit runs masked), or skip persona ingestion.
  - Unparseable MIME → skip.
  - Daily canary recall below SLO → **pause ingestion** for the affected class or tenant.
- **Human review:**
  - Tenant-designated reviewers (privacy officer or compliance auditor) see **sampled** detections and misses at L1 with spans, inside their tenant.
  - **PersonaAgent staff never review customer content.** Our improvements come from synthetic data and an opt-in labelled-data programme under a DPA addendum.
  - End users can flag "this draft revealed X", which opens an incident.
- **Tenant policy (versioned JSON, with dry-run preview):**
  - per entity class → action per level
  - per sensitivity label → ingest / exclude / L2-only
  - external-sender trust
  - retention per level
  - recorder rules
  - presets: `US-Default`, `US-HIPAA`, `US-GLBA-FI`, `PCI-Strict`, `India-DPDP`, `India-BFSI`

  Every policy change is audited and shows a diff.

### 6.12 Evaluation methodology and recall targets (US + India)

**Test sets** (kept out of training data; versioned):
1. **Synthetic US corpus.** Realistic emails, Teams threads and transcripts (finance, healthcare, HR, sales), with programmatically inserted **valid** identifiers (correct checksums and prefixes) plus **hard negatives** (invoice/order IDs, ZIP+4, phone numbers that look like SSNs, look-alike routing numbers).
2. **Synthetic India corpus.** Same structure with Faker `en_IN`/`hi_IN` plus LLM-generated context:
   - Aadhaar (valid Verhoeff), VID, PAN by holder type, GSTIN (valid check char), EPIC, passport, DL, IFSC + account, UPI, mobile, ABHA, UAN collisions
   - **Indian names** across regions and communities, single-name individuals, initials-first South-Indian forms ("K. S. Raghavan"), honorifics (ji, Sir/Madam, bhai)
   - **Hinglish (romanised Hindi)**, Devanagari, mixed scripts, Devanagari digits
3. **Public sets.** ai4privacy open-pii-masking-500k (Hindi/Telugu slices), NVIDIA Nemotron-PII, Naamapadam (Indic NER), plus a hand-labelled subset of the public Enron email corpus (US business email).
4. **Design-partner sets.** Labelled by the customer's reviewers inside their tenant; never exported.
5. **Adversarial set.** Spaced, dotted or spelled digits; homoglyphs; zero-width characters; numbers split across lines; IDs in signatures, tables and forwarded quotes; text in images (out of MVP scope, but measured).

**Metrics:**
- Entity-level recall/precision/F1 per class (strict and partial overlap).
- **Document leak rate** (% of items with ≥1 missed Tier-R entity).
- "Raw-to-LLM" rate (Tier-R strings reaching any prompt).
- Over-redaction impact on persona quality.
- p95 latency and cost per 1,000 items.

**Proposed launch gates** (to be validated with data; these are targets, not measured results):

| Class | Recall target | Precision target |
|---|---|---|
| Checksum-validated IDs (cards, Aadhaar, ABA, MBI, NPI, GSTIN) — well-formed | ≥ 99.9% | ≥ 98% |
| Same, obfuscated variants | ≥ 99% | ≥ 95% |
| Non-checksum Tier R with context (SSN, ITIN, passport, DL, bank accounts, UPI) | ≥ 99% | ≥ 95% |
| Secrets/credentials | ≥ 99% | ≥ 90% |
| Emails, phones | ≥ 99.5% | ≥ 98% |
| Person names — US English business email | ≥ 97% | ≥ 92% |
| Person names — Indian English business email | ≥ 95% (gate for India launch) | ≥ 90% |
| Person names — Hinglish chat/transcripts | ≥ 93% (stretch 95%) | ≥ 88% |
| Company-sensitive (dictionary terms) | ≥ 99.9% | ≥ 95% |
| Company-sensitive (LLM-classified categories) | ≥ 90% | ≥ 80% |
| **Document-level Tier-R leak rate** | ≤ 0.1% (MVP) → ≤ 0.01% (Enterprise) | – |

**Process:**
- Regression suite in CI on every detector, model or prompt change.
- Per-release accuracy report.
- Weekly drift check on canaries.
- Results published to tenants as a "redaction quality statement".

### 6.13 Indian names and Hinglish — accuracy approach

**Evidence:**
- Comprehend PII is English/Spanish only.
- Guardrails has no India types.
- Transcribe PII excludes Hindi.
- NVIDIA GLiNER-PII is English only.
- IndicNER reaches F1 > 80 on most Indic languages, but on news-style native-script text with only PER/LOC/ORG.
- **No public benchmark was found for PII in Indian business email or Hinglish chats.** Treat any vendor claim as unverified until it is tested on our India set.

**Known failure modes:**
- Names that are common words (Asha, Kiran, Pooja, Raja, Prakash).
- Names that equal places or brands (Bharat, Tata).
- Mononyms.
- Initials-first forms.
- Lower-cased names in chat ("rahul ko bol do").
- Honorific suffixes ("Sharma ji").
- Kinship terms used as names (bhaiya, didi).
- Transliteration variance (Mohd/Mohammed/Muhammad).

**Approach:**
1. **Tenant directory and header gazetteer.** Exact and fuzzy match on known people. Highest precision.
2. A curated Indian first-name/surname lexicon with transliteration folding.
3. Multilingual GLiNER fine-tuned on synthetic Indian business text, plus IndicNER for Devanagari.
4. LLM adjudication only for uncertain spans.
5. Precision guards: a common-word allow-list, and capitalisation/position features.

Report results per script (Latin/Devanagari), per register (email vs chat vs transcript) and per community-name distribution, to avoid hidden bias.

### 6.14 Throughput and cost notes (estimates; pricing belongs to track 03)

- **Corpus size is parametric:** users × backfill items × ~1–3 KB of text after quote and signature stripping. Example: 1,000 users × 30k items × 2 KB ≈ **60 GB** of text for backfill. This is an illustrative estimate.
- **Regex and validators:** negligible CPU. Presidio + spaCy runs on CPU containers. GLiNER-large needs a GPU for backfill throughput (benchmark it in the PoC).
- **The LLM classifier dominates cost.** Run it only on (a) user-authored items used for persona, (b) items selected for memory, and (c) items flagged by cheap prefilters (dictionary hits, finance or legal cues). Never run it on the whole mailbox by default.
- **Comprehend/Guardrails per-character pricing** makes "run everything through managed PII" expensive at backfill scale. Use them where they add unique value (Guardrails as a backstop on LLM I/O).

### 6.15 Auditing

Every one of the following is logged:
- reveal (re-identification)
- break-glass access
- policy change
- export
- deletion
- delegate action
- memory edit

Logs go to an append-only store: CloudTrail Lake or S3 Object Lock, under a per-tenant key. Compliance auditors (tenant role) can query their tenant's audit trail. End users can see who accessed their data.

## 7. Redaction pipeline design with stages and AWS services (deliverable D2)

### 7.1 Flow

```
 Graph change notification / delta  ─┐      Teams post-meeting transcript ─┐     Phone audio (work-only) ─┐
                                     ▼                                     ▼                              ▼
 S0  Intake: API Gateway (validate clientState) → SQS (per-tenant message group) → Step Functions / ECS workers
 S1  Fetch (in memory only): delegated token from AgentCore Identity token vault (tenant CMK) → Graph GET by ID
 S2  Parse & normalise: MIME/HTML→text · quotes/signatures/disclaimers split · hidden-content & Unicode-tag detection
     · NFKC, Devanagari digits, ITN · language/script ID · sender class · MSIP_Labels / policyViolation
 S3  Policy pre-check: label rules · sender/size caps (denial-of-wallet) · recorder policy · "privileged" markers
 S4  Deterministic detectors: §6.4 regex+validators (US/IN) + secrets rules ──► Tier R masked IN MEMORY, immediately
 S5  NER ensemble: Presidio(+spaCy) · GLiNER (GPU endpoint) · IndicNER (Devanagari) · tenant directory/header gazetteer
     · [optional] Comprehend (English)
 S6  Contextual classifier (selected items only): Bedrock small model + Guardrails, JSON schema → Tier C/S labels
 S7  Merge & decide: span merge (R > S > C > P), tenant policy engine → action per span per level
 S8  Tokenise: vault service (separate account; DynamoDB + DB-ESDK hierarchical keyring; tenant CMK) → L1 (+ L2 view)
 S9  Verify: second-pass detectors on L1 output; any Tier-R residual ⇒ BLOCK item + alert; sample → tenant review queue
 S10 Persist L1: S3 (SSE-KMS tenant key) · Aurora PG (RLS) · vector index per tenant · lineage record (Graph ID → artifacts)
 S11 Memory extraction (quarantined reader) → memory-write validation (§5.6) → memory store with provenance + audience ACL
 S12 Draft path (online): live thread → S2–S9 fast path → generator → output gate (§5.3) → re-hydrator → client (plain text)
 S13 Backstops: Macie scans of L1 buckets (custom identifiers for Aadhaar/PAN/UPI) · CloudWatch Logs data protection
     · canary recall jobs · GuardDuty/Security Hub
```

### 7.2 Stage table

| Stage | What happens | AWS services (suggested) | Output / level | Failure behaviour |
|---|---|---|---|---|
| S0 Intake | Validate notification (clientState / signatures); enqueue; per-tenant rate limits | API Gateway, SQS FIFO (message group = tenant), EventBridge | Work item (IDs only) | Drop invalid; dead-letter after N tries |
| S1 Fetch | Get token (ingestion role only); Graph read of selected fields | AgentCore Identity (token vault, CMK), ECS Fargate (or Lambda), VPC endpoints + egress allow-list to Graph | L0 in memory | Token failure → mark tenant degraded; no fallback storage |
| S2 Parse | MIME/HTML sanitise; hidden-content flag; normalisation; language ID | ECS task (libraries) | Normalised text + metadata | Unparseable → skip + metric |
| S3 Pre-policy | Labels, sender trust, caps, recorder rules | In-process policy engine (tenant JSON from DynamoDB/AppConfig) | Allow / exclude / L2-only | Excluded items leave a metadata-only stub |
| S4 Deterministic | US/IN validators, secrets rules | In-process (Presidio custom recognisers) | Tier R masked | Detector crash → item blocked (fail-closed) |
| S5 NER | Ensemble + gazetteer | ECS CPU tasks; SageMaker real-time/async (GLiNER, IndicNER); optional Comprehend | Candidate spans + scores | Model endpoint down → queue; no bypass |
| S6 Contextual | Tier C/S classification for selected items | Bedrock (small Claude tier) + Guardrails; Batch inference for backfill | Labels (untrusted, restrictive-only) | Timeout → apply stricter tenant default |
| S7 Decide | Merge, resolve conflicts, apply tenant policy | In-process | Action plan | Policy missing → strictest preset |
| S8 Tokenise | Lookup/create tokens; build L1/L2 | Vault service (separate account), DynamoDB, KMS (tenant CMK), DB-ESDK | L1 / L2 text | Vault unavailable → block |
| S9 Verify | Residual scan; sampling to review | In-process + review UI (tenant) | Pass/block | Residual Tier R → block + alert |
| S10 Persist | Store L1; vectors; lineage | S3 (SSE-KMS, per-tenant prefixes/buckets), Aurora PostgreSQL (RLS), S3 Vectors or OpenSearch (index per tenant) | Durable L1 | Partial write → compensating delete |
| S11 Memory | Extract → validate → store | Bedrock (quarantined reader), AgentCore Memory or own store | Memories with provenance + ACL | Suspicious → quarantine queue |
| S12 Draft | Online redaction, generation, gating, re-hydration | AgentCore Runtime (agent), Bedrock + Guardrails, re-hydrator (Lambda/ECS in vault account) | Plain-text draft | Any gate failure → no draft (explain why) |
| S13 Backstops | Residual PII scans; log protection; canaries | Macie, CloudWatch Logs data protection, CloudTrail, GuardDuty, Security Hub | Findings | Findings ≥ threshold → pause tenant pipeline |

**Network posture.** Workers reach only Graph and AWS service endpoints (VPC endpoints plus DNS/Network Firewall allow-list). The LLM-calling tasks reach **only Bedrock**. Nothing in the data plane can reach the open internet. This matters because ShadowLeak showed that service-side egress is invisible to the customer.

**Latency budget (draft path, estimate):** ≤1–1.5 s for S2–S9 on a typical thread using the fast path (deterministic + cached gazetteer + CPU NER; no LLM classifier). Measure in the PoC.

## 8. Role × data-level access matrix (deliverable D3)

Legend: ✅ allowed · ⚠ conditional (see notes) · ❌ never · "own" = the user's own data. "Display" = the re-identified view (L1 + vault re-hydration), which is never stored.

| Role | L0 raw | L1 (pseudonymised) | Display (re-identified) | L2 | L3 | Vault reveal / keys | OAuth tokens | Audit logs | Tenant policies |
|---|---|---|---|---|---|---|---|---|---|
| **Platform super-admin** | ❌ | ⚠ B1 | ❌ | ⚠ B1 | ✅ | ❌ (KMS policy deny) | ❌ | ✅ platform | Platform config only |
| **Platform SRE / on-call** | ❌ | ❌ | ❌ | ❌ | ✅ ops metrics | ❌ | ❌ | ✅ ops | ❌ (CI/CD only) |
| **Platform support (break-glass)** | ❌ | ⚠ B2 | ❌ | ⚠ B2 (default view) | ✅ | ❌ | ❌ | Own actions | Read with tenant consent |
| **Platform security / IR** | ❌ | ⚠ B3 | ❌ | ⚠ B3 | ✅ | ❌ (Ent: enclave-only forensic job with tenant approval) | Revoke only | ✅ | Read |
| **Tenant admin** | ❌ (has M365 itself) | ⚠ E1 | ❌ | ⚠ E1 | ✅ tenant aggregates | ❌ | Revoke-all ✅, read ❌ | ✅ tenant | ✅ write (audited, versioned) |
| **Compliance auditor (tenant)** | ❌ | ⚠ A1 | ⚠ A2 | ⚠ A1 | ✅ | ❌ | ❌ | ✅ read/export | ✅ read |
| **Team manager** | ❌ | ❌ | ❌ | ❌ | ✅ team aggregates (k ≥ 10) | ❌ | ❌ | Own actions | ❌ |
| **End user** | Own, via M365 (we store none) | ✅ own | ✅ own | ✅ own | – | Indirect (re-hydrator, own tokens) | Own revoke | ✅ own access history | Personal prefs within tenant bounds |
| **Delegate / EA** | ❌ | ⚠ D1 | ⚠ D1 | ⚠ D1 | ❌ | Indirect ⚠ D1 | ❌ | Own actions (visible to principal) | ❌ |
| **Svc: ingestion & redaction** | ✅ transient (memory) | write | ❌ | write | ❌ | create/lookup (no reveal) | **use** (ingestion role only) | write | read |
| **Svc: persona learner / memory extractor** | ❌ | read/write (tenant + user scoped) | ❌ | read (if tenant opts) | ❌ | ❌ | ❌ | write | read |
| **Svc: drafting agent** | Live thread → L1 before prompt | read (ACL-filtered) | ❌ | ❌ | ❌ | ❌ | User's **live OBO token** for the thread fetch (not the stored refresh token) | write | read |
| **Svc: re-hydrator (vault account)** | ❌ | read draft | produce (transient) | ❌ | ❌ | **reveal** allow-listed tokens | ❌ | write | read |
| **Svc: analytics / evals** | ❌ | ❌ (evals: synthetic or consented only) | ❌ | ❌ | ✅ | ❌ | ❌ | write | ❌ |

**Notes:**
- **B1 (super-admin):** no standing access. Emergency only: two PersonaAgent approvers **plus** tenant-admin approval; time-boxed; session recorded; L2 view by default.
- **B2 (support):** a ticket referencing specific item IDs, approved by **the affected user and the tenant admin**; ≤ 4 h; recorded; L2 view by default, L1 only if strictly needed; never the vault.
- **B3 (security/IR):** a declared incident with legal sign-off; analysis in an isolated forensic account; tenant notified.
- **E1 (tenant admin):** no default content access. An **eDiscovery / legal-hold export** path exists, with dual approval (tenant admin + legal/compliance), user notification where lawful, and a full audit trail. This mirrors the customer's existing obligations over the M365 source data.
- **A1 (auditor):** sampled redaction-QA spans and DLP-incident items only.
- **A2 (auditor):** a formal investigation workflow co-approved by the tenant admin.
- **D1 (delegate):** only where the EA already has Exchange/Teams delegate access to the same items, **and** the principal has enabled delegation in PersonaAgent. Excludes `PRIVATE` memories and recorder data. Drafts are labelled "prepared by delegate" in our audit log, and the EA cannot modify the principal's persona.
- **Enforcement points:** IAM roles per service (one role per stage); KMS key policies (vault keys deny all humans); Aurora RLS; per-tenant indexes; an application-layer ABAC check (Cedar or equivalent) on every API call; immutable audit logs.

## 9. Security requirements checklist — MVP vs Enterprise (deliverable D4)

✔ = required at that tier · ○ = optional/tenant-configurable · – = not applicable yet.

| # | Requirement | MVP | Ent |
|---|---|---|---|
| **Identity, OAuth & access** | | | |
| SR-01 | Entra multi-tenant app, publisher-verified; admin-consent onboarding; published app IDs/scopes/redirect URIs | ✔ | ✔ |
| SR-02 | Delegated **read-only** scopes only (`Mail.Read`, `Chat.Read`, `User.ReadBasic.All`); write scopes on a separate app registration later | ✔ | ✔ |
| SR-03 | No client secrets: workload identity federation (AWS IAM outbound → Entra FIC); fallback cert key in KMS (`kms:Sign`) | ✔ | ✔ |
| SR-04 | Refresh tokens encrypted with per-tenant CMK; superseded tokens deleted; only the ingestion role can decrypt; per-tenant revoke-all | ✔ | ✔ |
| SR-05 | Token validation: `iss`/`tid`/`aud`; identity keyed on `oid`+`tid` (never email); CAE-aware clients | ✔ | ✔ |
| SR-06 | No standing human access to data plane; break-glass with dual + customer approval, recorded | ✔ | ✔ |
| SR-07 | Phishing-resistant MFA for all staff; separate prod-data AWS accounts; SCPs | ✔ | ✔ |
| SR-08 | Microsoft 365 App Compliance (attestation → certification) | ○ | ✔ |
| **Tenant isolation** | | | |
| SR-09 | Index-per-tenant vectors; per-tenant CMK; Aurora RLS from verified `tid`; tenant-scoped cache keys; no cross-tenant prompt cache or fine-tune | ✔ | ✔ |
| SR-10 | Canary tenants + automated isolation tests as a release gate | ✔ | ✔ |
| SR-11 | Dedicated cells/accounts for large tenants; region pinning (US / India) | ○ | ✔ |
| **Data protection & keys** | | | |
| SR-12 | **No L0 persistence**; re-fetch by Graph ID; lineage map for every derived artifact | ✔ | ✔ (opt-in customer-keyed archive) |
| SR-13 | Envelope encryption: tenant CMK → per-user branch keys (hierarchical keyring); crypto-shredding deletion | ✔ | ✔ |
| SR-14 | BYOK (tenant-owned KMS) / HYOK (XKS) | – | ✔ |
| SR-15 | Nitro Enclave tokenisation vault (operator-blind) | – | ✔ |
| SR-16 | Deletion SLAs (user offboarding, tenant exit, DPDP erasure, Microsoft API Terms "abandonment") with verification | ✔ | ✔ |
| **Redaction** | | | |
| SR-17 | Tier-R irreversible masking at first touch (US + India catalog §6.4), incl. secrets; verification pass; fail-closed | ✔ | ✔ |
| SR-18 | Consistent reversible tokens (vault) for Tier P; token-spoofing defences | ✔ | ✔ |
| SR-19 | Tenant policy presets (`US-Default`, `US-HIPAA`, `US-GLBA-FI`, `PCI-Strict`, `India-DPDP`, `India-BFSI`) with dry-run | ✔ (2–3 presets) | ✔ (all + custom) |
| SR-20 | Label-aware ingestion (`MSIP_Labels`), Teams `policyViolation`; skip RMS-encrypted mail | ✔ | ✔ |
| SR-21 | LLM contextual classifier for Tier C/S; tenant dictionaries | ✔ (basic) | ✔ |
| SR-22 | Recall SLOs met on US + India test sets (§6.12); published redaction-quality statement | ✔ | ✔ |
| SR-23 | Tenant review queue for sampled detections | ○ | ✔ |
| **Agent / LLM safety** | | | |
| SR-24 | No autonomous outbound actions; drafts inserted client-side; send = separate user gesture | ✔ | ✔ |
| SR-25 | Quarantined reader for all untrusted content; spotlighting; instruction-hierarchy prompts | ✔ | ✔ |
| SR-26 | **No internet egress** from LLM/data-plane workers; Bedrock via VPC endpoint | ✔ | ✔ |
| SR-27 | Output gate: plain text, URL policy, Tier-R block, audience-ACL check, BEC heuristics, secrets scan | ✔ | ✔ |
| SR-28 | Bedrock Guardrails on every model call (prompt attack + PII backstop + custom India regex) | ✔ | ✔ |
| SR-29 | AgentCore Gateway + Policy (Cedar/temporal) for any server-side write tool | – | ✔ |
| SR-30 | Purview `processContent` DLP/audit on drafts | – | ✔ |
| SR-31 | LLM-judge "unsupported facts" check (paraphrase leakage) | ○ | ✔ |
| **Memory & persona** | | | |
| SR-32 | Provenance on every memory; style learned only from user-authored content; instruction-like memories rejected | ✔ | ✔ |
| SR-33 | Audience ACLs on memories; retrieval filtered by recipients | ✔ | ✔ |
| SR-34 | User memory review/edit/delete UI; quarantine queue for suspicious writes | ✔ | ✔ |
| SR-35 | No fine-tuning on customer data (Ent adapters: L1 only, per-user isolated, deletable) | ✔ | ✔ |
| **Client surfaces** | | | |
| SR-36 | Strict CSP; no remote content; no URL-carried prompts; sanitised rendering; OBO/NAA token flows | ✔ | ✔ |
| **Recorder / mobile** | | | |
| SR-37 | Tenant capture policies (hours/locations/categories), visible indicator, mute + delete-last-N-min, consent prompts | ✔ | ✔ |
| SR-38 | ≤24 h encrypted on-device buffer; Data Protection Complete / Keystore; app lock; remote wipe; no backups | ✔ | ✔ |
| SR-39 | No voiceprints; audio deleted after transcription by default | ✔ | ✔ (opt-in redacted audio retention) |
| SR-40 | Intune MAM app-protection support | – | ✔ |
| **Logging, monitoring & IR** | | | |
| SR-41 | Content-free logging; invocation logging off in prod; Guardrails traces not logged; CloudWatch Logs data protection | ✔ | ✔ |
| SR-42 | Immutable audit log (reveals, break-glass, policy changes, exports, deletions, delegate actions) | ✔ | ✔ |
| SR-43 | Anomaly detection (Graph volume, generation spikes, re-hydration spikes, memory-write bursts, cost) | ✔ (basic) | ✔ (SIEM export) |
| SR-44 | IR runbooks with clocks: CERT-In 6 h; DPDP 72 h (from 13 May 2027); US state laws; customer contractual SLAs | ✔ | ✔ |
| SR-45 | India: 180-day metadata logs in India; NTP per CERT-In | ✔ (India tenants) | ✔ |
| **Supply chain & SDLC** | | | |
| SR-46 | Hash-pinned dependencies, registry proxy with new-version cool-down, SHA-pinned CI actions, OIDC CI creds | ✔ | ✔ |
| SR-47 | No third-party MCP servers/skills in data plane; no vendor keys in clients (Rabbit R1 lesson) | ✔ | ✔ |
| SR-48 | SBOM + signed builds/provenance (SLSA-style) | ○ | ✔ |
| SR-49 | Threat model per feature; security review of prompts/policies as code | ✔ | ✔ |
| **Assurance & compliance** | | | |
| SR-50 | External pentest (web, add-in, mobile/MASVS, cloud) before first paying tenant | ✔ | ✔ (annual + major releases) |
| SR-51 | Private bug bounty (beta) → public (GA) | ○ | ✔ |
| SR-52 | SOC 2 Type I → Type II; ISO 27001 (India relevance under SPDI Rules) | Type I target | ✔ |
| SR-53 | DPA templates (US: CPRA service-provider terms; HIPAA BAA; India: DPDP processor contract, RBI outsourcing clauses) | ✔ (US + India DPA) | ✔ (BAA, RBI addenda) |

## 10. Pre-launch security test plan (deliverable D5)

"Gate" = must pass before the first paying tenant (MVP) or before Enterprise GA (Ent).

| ID | Area | Test | Method / tools | Pass criterion | Gate |
|---|---|---|---|---|---|
| ST-01 | Prompt injection (email) | Corpus of ≥300 malicious emails: visible instructions, white/1-px text, `display:none`, HTML comments, zero-width & **Unicode tag** smuggling, Base64/ROT13, multilingual (Hindi/Hinglish), reference-style markdown | Own harness + promptfoo/PyRIT orchestration; garak probes | 0 successful exfil (no data reaches attacker-visible channel); injected instructions never alter recipients, links or memory; ASR tracked per release | MVP |
| ST-02 | Prompt injection (Teams / invites / transcripts) | Same payloads via external Teams chat, guest posts, invite titles/bodies, meeting transcripts, **spoken payloads** played into the recorder | Harness + test tenants | Same as ST-01 | MVP |
| ST-03 | Exfil channels | Model output containing markdown images, links, `data:` URIs, long query strings, unicode-obfuscated URLs | Unit + E2E UI tests; CSP violation reports | Nothing auto-fetched; URL policy blocks non-allow-listed links; CSP blocks remote loads | MVP |
| ST-04 | Draft leakage / contextual integrity | Seed internal-only facts; request drafts to external recipients; adversarial "please include…" emails | Scenario suite modelled on PrivacyLens | 0 ACL-violating tokens in drafts; paraphrase-leak rate measured (Ent target set) | MVP |
| ST-05 | Recipient manipulation | Injections asking to add CC/BCC or change recipients | E2E | Impossible by construction (API returns body only) | MVP |
| ST-06 | Memory poisoning | Inbound emails with "remember…", "from now on…", new bank/UPI/IFSC details, links; ZombieAgent-style rules; MINJA-style query sequences | Harness | No instruction-like memory stored; payment/contact changes quarantined; style memories only from sent items | MVP |
| ST-07 | BEC misuse | Generate drafts requesting payment changes, gift cards, urgent wires; bulk generation as a compromised account | Harness + anomaly detector | Hard warnings shown; one-click insert disabled; anomaly alert fires | MVP |
| ST-08 | Tenant isolation | Two canary tenants; fuzz every API with forged tenant/user IDs; omit filters in test builds; vector search with crafted metadata; cache-key collision tests; re-index/backfill jobs | Property-based tests, DAST, code scan for raw data-access calls | 0 cross-tenant canary hits; requests with mismatched `tid` rejected | MVP |
| ST-09 | IDOR / authz | Access other users' memory IDs, drafts, audit entries; delegate escalation; manager access to individual data | Automated authz matrix tests (role × endpoint) | All denied as per §8 | MVP |
| ST-10 | Token vault compromise drill | Simulate DB dump of token store; attempt token redemption without workload identity | Red-team exercise | Stolen ciphertext unusable; no client secret exists; alerts on anomalous decrypt | MVP |
| ST-11 | OAuth flows | Redirect URI validation, `state`/PKCE, multi-tenant issuer validation, email-claim takeover (nOAuth class), consent screen review, no device-code flow | Manual + automated (Burp) | All pass | MVP |
| ST-12 | Redaction recall | US + India test sets (§6.12), incl. adversarial obfuscations, Devanagari digits, Hinglish | CI regression suite | Meets launch gates in §6.12 | MVP |
| ST-13 | Fail-closed | Kill NER endpoint, vault, KMS, classifier mid-pipeline | Chaos tests | No item persisted without full redaction; alerts fire | MVP |
| ST-14 | Token spoofing | Inbound content containing token-like strings, guessed IDs | Harness | No reveal of out-of-context tokens | MVP |
| ST-15 | Logs & telemetry leakage | Inject canary PII; grep logs, traces, metrics, crash reports, analytics, support tools | Automated scanners with our detectors | 0 canaries outside L1 stores | MVP |
| ST-16 | Bedrock config | Verify invocation logging off; Guardrails attached to every call; no cross-region inference for India tenants | AWS Config rules / custom checks | Compliant | MVP |
| ST-17 | Egress | From every data-plane task attempt outbound internet, DNS exfil | Network tests; DNS Firewall logs | Blocked and alerted | MVP |
| ST-18 | Denial of wallet | Inbox flood (10k large emails), giant attachments, recursive threads; stolen-key simulation | Load tests; SCP checks | Caps and circuit breakers hold; cost alarms fire; SCPs block unauthorised model invocation | MVP |
| ST-19 | Supply chain | SBOM review; verify hash pinning; attempt to install a typo-squat or fresh version in CI | CI policy tests | Blocked by registry proxy / cool-down | MVP |
| ST-20 | Mobile app | OWASP MASVS L2-style testing: storage, crypto, network (pinning), platform, resilience; lost-device scenario | External pentest | No high/critical findings; on-device data ≤24 h, encrypted | MVP (if recorder in MVP) |
| ST-21 | Add-in / Teams app | XSS via email HTML, CSP bypass, postMessage origin checks, token handling, deep-link prompt injection | External pentest | No high/critical findings | MVP |
| ST-22 | Recorder policy | Auto-mute on HR/legal categories, schedule/location windows, indicator, delete-last-N-min | E2E on devices | Policies enforced; deleted audio/transcripts unrecoverable | MVP (if recorder) |
| ST-23 | Deletion | Offboard a user/tenant; verify crypto-shred, vector purge, cache purge, backup unreadability | Automated deletion audit | No recoverable data post-SLA | MVP |
| ST-24 | Break-glass | Exercise support access with/without approvals; verify recording and customer-visible audit | Tabletop + technical test | No access without approvals; full audit trail | MVP |
| ST-25 | Incident response | Tabletop: token theft, cross-tenant leak, CERT-In 6 h report, DPDP 72 h report, US notices | Tabletop | Runbooks executed within clocks | MVP |
| ST-26 | Adaptive red team | External red team with system knowledge (white-box prompts/policies), per "The Attacker Moves Second" | Third-party engagement | Findings triaged; no critical open at GA | Ent |
| ST-27 | Policy engine | Cedar/AgentCore Policy unit tests; automated-reasoning checks; temporal rules (approval before send) | Policy test suite | All negative tests denied | Ent |
| ST-28 | Enclave vault | Attestation-gated KMS decrypt; parent-instance compromise simulation | Specialist review | Parent cannot read plaintext | Ent |
| ST-29 | Bug bounty | Private programme with AI-specific scope (injection→exfil, isolation, memory poisoning) | Platform of choice | Running ≥ 4 weeks before GA | Ent |

## 11. Recommendations for PersonaAgent

### 11.1 Product invariants (write them into the architecture doc and test them)

1. **No raw content at rest.** M365 is the system of record, and L0 lives only in memory.
2. **Tier-R identifiers are irreversibly masked at first touch**, never stored, and never shown to an LLM.
3. **No model output leaves the system without a human gesture.** In the MVP, drafts are inserted client-side as plain text.
4. **The model that reads untrusted content has no tools, no egress and no memory-write rights.**
5. **Style is learned only from what the user wrote.** Everything else is a low-trust fact with provenance and an audience ACL.
6. **One tenant, one key, one index.** Isolation failures should yield ciphertext, not data.
7. **Nobody at PersonaAgent can read customer content without the customer's approval**, and every such access is visible to the customer.

### 11.2 Prioritised actions for a 3–6 engineer, ~3-month MVP

| Month | Security / redaction work items | Owner |
|---|---|---|
| **1** | Separate AWS accounts (data plane, vault, ops/logging, India + US regions); no-egress VPC with Bedrock/Graph endpoints only; per-tenant CMKs + hierarchical keyring; Entra app with publisher verification + **workload identity federation**; token vault; content-free logging library; Bedrock invocation logging off; deterministic US/India detector library + secrets rules (§6.4) with unit tests; synthetic US/India test sets v0 | Platform/security lead (1 FTE) + 1 backend |
| **2** | Presidio orchestration + GLiNER/IndicNER + directory gazetteer; tokenisation vault + re-hydrator; L1 stores per tenant (index-per-tenant); memory provenance, trust scores and **audience ACLs**; quarantined reader; output gate (plain text, URL policy, Tier-R block, ACL check, BEC heuristics); CSP + no-URL-prompt rule in add-in/Teams app; injection corpus v1; canary tenants + isolation tests in CI | Security lead + 2 engineers |
| **3** | Recorder (if in MVP): tenant policies, indicator, mute/delete, Transcribe en-IN/en-US, delete audio; recall gates met (§6.12); fail-closed chaos tests; IR runbooks (CERT-In 6 h, DPDP 72 h, US states); DPA templates (US CPRA service-provider terms; India DPDP processor terms); **external pentest**; SOC 2 Type I readiness; private bug bounty for design partners | Whole team; external pentester |

### 11.3 Specific recommendations

1. **Make a named engineer own security and redaction full-time from day 1.** Redaction is a core product requirement and a buying criterion, not a compliance chore. Add a fractional CISO or advisor for customer security reviews.
2. **Build our own US + India detector library (validators) on top of Presidio.** Use Guardrails and Comprehend as backstops, not the foundation. AWS managed PII lacks India types (Guardrails) or non-English support (Comprehend), and Purview lacks Indian passport, IFSC and UPI.
3. **Use the M365 directory and message headers as a name gazetteer.** It is the highest-leverage fix for Indian-name recall.
4. **Invest early in evaluation data.** Ship a "redaction quality statement" with per-class recall on our US/India sets. Never claim "100% PII removal".
5. **Treat memory as a security boundary.** Users must be able to review, edit and delete memories. Show provenance in drafts. Quarantine payment and contact changes.
6. **Ship BEC guardrails as a feature** ("PersonaAgent won't help anyone, including you, change bank details by email without a warning"). It turns the impersonation risk into a trust signal.
7. **Pin India tenants to AWS India regions**, and verify that the chosen Claude models and Guardrails run there *without* cross-region routing outside India. Coordinate with track 03.
8. **US healthcare and financial customers:** offer the `US-HIPAA` preset and BAA only after confirming HIPAA eligibility of every service in the path (Bedrock, AgentCore, Transcribe). Offer `US-GLBA-FI` with a vendor-assurance pack.
9. **Phase 2 server-side actions:**
   - a separate app registration
   - AgentCore Gateway + Policy (Cedar/temporal "approval before send")
   - taint tracking (untrusted-derived recipients or links ⇒ no send)
   - reversible actions first (drafts before sends)
10. **Enterprise differentiators, roughly in order:** BYOK; Purview `processContent` on drafts; SIEM export; Nitro-Enclave operator-blind vault; dedicated cells; ISO 27001; M365 App Compliance certification.
11. **Publish a trust centre** with app IDs, scopes, sub-processors, data flows, regions, retention, redaction-quality statement, pentest letter and incident contacts. It speeds up security reviews and helps customers spot consent-phishing look-alikes.

## 12. Risks & watch-outs

| Risk | Why it matters | Mitigation / signal to watch |
|---|---|---|
| **Residual prompt-injection risk can't be eliminated** | Even hardened frontier agents report ~1% adaptive-attack success; new channels keep appearing (URL prompts, MCP, transcripts) | Keep the human gesture plus no-egress invariants even when customers ask for "auto-send". Track attack success rate per release. Subscribe to OWASP GenAI exploit round-ups |
| **Approval fatigue** (OWASP T10) | Users rubber-stamp drafts, so the human check becomes theatre | Risk-proportional friction: warnings only when something new or risky appears; highlight external recipients, links, money terms |
| **Redaction false negatives**, especially Indian names, Hinglish and transcripts | No public benchmark exists; vendors publish no accuracy numbers | Own test sets, CI gates, canary monitoring, conservative claims |
| **Over-redaction hurts persona quality** | Users churn if drafts feel generic | Per-tenant policies; measure persona quality on L1 vs L0 in a controlled study |
| **The persona as an impersonation weapon** | Reputational damage if PersonaAgent output is used in BEC | BEC guardrails, generation audit, rate limits, no voice cloning; consider a provenance marker for generated drafts (tenant-configurable) |
| **Microsoft platform dependency** | Consent policy changes (admin consent now required), API Terms restricting email-API use to the customer's express purpose, Teams labelling outside bots "Unverified" | Admin-consent onboarding as the default; purpose statements in consent and contracts; read-only scopes; certification |
| **Data residency vs model availability (India)** | Cross-region inference could route Indian tenants' prompts outside India | Verify per-model regional availability; disable cross-region profiles for India tenants; contract language |
| **Regulatory clocks** | DPDP substantive obligations start **13 May 2027**; CPRA regulations (risk assessments, cybersecurity audits); US state law churn; EU later | Legal-track calendar; design already meets the stricter reading (masking/tokens, 72 h, 1-year logs) |
| **Customer insiders asking for employee data** | Managers or HR may demand recordings or memories; labour-law and trust implications | Clear defaults (no admin content access), documented eDiscovery path, user transparency |
| **eDiscovery / legal hold vs deletion** | Our L1 store may be discoverable; holds conflict with crypto-shredding | Legal-hold flag that suspends shredding for named custodians; legal track to define |
| **MNPI / UPSI in memory** | Listed customers face insider-trading control obligations | "Listed entity" preset; UPSI excluded from memory by default |
| **AgentCore Policy / Dogwood maturity and regional availability** | Policy features documented in 2026 may vary by region or GA status | Verify before Phase 2 design freeze; keep a self-hosted Cedar fallback |
| **Supply-chain velocity** | AI libraries ship weekly; pinning delays patches | Weekly dependency review; cool-down exceptions for security patches |
| **Small team capacity** | Security tasks compete with features | Dedicated owner; invariants enforced by tests rather than reviews |

## 13. Open questions / could not verify

**Research constraint.** The session's shared web-search budget ran out mid-track, so the items below were not verified against primary sources here. Items marked Med or Low in the text depend on them.

1. **OWASP:** contents of "OWASP GenAI LLM Top 10 2026" (listed 3 Aug 2026), "Agent Control Standard" and "Framework Crosswalk" (1 Sep 2026). The exact titles of ASI04/05/07/08/09 come from secondary summaries.
2. **EchoLeak bypass specifics.** The Aim Labs write-up returned HTTP 403. The mechanism comes from secondary reporting (classifier and link-redaction bypass, Teams/SharePoint exfil).
3. **Rabbit R1 primary disclosure** (rabbitu.de returned HTTP 500). The list of exposed keys comes from memory and contemporaneous reporting.
4. **UIDAI Aadhaar Data Vault circular (2017)** and the Aadhaar (Sharing of Information) Regulations wording (UIDAI URL returned 404). Requirements are summarised from memory; legal track to confirm.
5. **US identifier rules not re-fetched:** SSA SSN rules (403), IRS ITIN ranges, NPI check-digit spec, DEA algorithm, state DL formats, US passport formats, RuPay IIN ranges. All need validation against official sources and real samples before launch.
6. **India identifier formats:** GSTIN check-character algorithm and full state-code list (38/97), VID checksum, Indian passport and DL formats, CKYC/ABHA/UAN formats, NPCI UPI handle list.
7. **Microsoft:**
   - Whether Entra federated identity credentials with AWS IAM outbound federation work for our **multi-tenant, delegated auth-code + refresh** flow (the docs show the client-credentials flow).
   - Current naming and scope of the M365 App Compliance programme.
   - Whether `MSIP_Labels` persists on Sent Items copies (cross-track flagged).
8. **AWS:**
   - HIPAA eligibility of Bedrock, AgentCore and Transcribe in the target regions.
   - Claude and Guardrails availability in ap-south-1/ap-south-2 without cross-region routing.
   - AgentCore Policy GA and regional status.
   - Transcribe Call Analytics redacted-audio output.
   - Transcribe `hi-IN` transcription support.
   - Current KMS request quotas.
9. **Accuracy:**
   - No public precision/recall benchmark found for PII in Indian business email or Hinglish chat.
   - Multilingual GLiNER performance on Indian names is unknown.
   - Persona-quality impact of pseudonymisation needs our own experiment.
   - The §6.12 targets are proposals, not measured results.
10. **PCI DSS scoping** of transient in-memory processing of incidental PANs needs a QSA opinion. **CERT-In NTP** compatibility with Amazon Time Sync needs confirmation.
11. **Not used because unverified:** MINJA success-rate numbers; Check Point's 2025 Teams spoofing research; reported 2026 ownership changes of red-team tools (e.g., promptfoo).

## 14. Sources

**Incidents and threat research**
- EchoLeak (CVE-2025-32711): https://thehackernews.com/2025/06/zero-click-ai-vulnerability-exposes.html · Aim Labs write-up (403 during research): https://www.aim.security/lp/aim-labs-echoleak-blogpost
- Slack AI exfiltration: https://promptarmor.com/resources/data-exfiltration-from-slack-ai-via-indirect-prompt-injection · https://simonwillison.net/2024/Aug/20/data-exfiltration-from-slack-ai/
- Gemini calendar-invite attacks: https://www.techrepublic.com/article/news-google-gemini-indirect-prompt-injection-attack/ · https://www.bitdefender.com/en-us/blog/hotforsecurity/gemini-ai-compromised-through-malicious-calendar-invites-researchers-warn
- GitHub MCP toxic flow: https://invariantlabs.ai/blog/mcp-github-vulnerability
- AgentFlayer: https://labs.zenity.io/p/agentflayer-chatgpt-connectors-0click-attack-5b41 · https://hackread.com/agentflayer-0-click-exploit-chatgpt-connectors-steal-data/
- ShadowLeak: https://thehackernews.com/2025/09/shadowleak-zero-click-flaw-leaks-gmail.html · https://therecord.media/openai-fixes-zero-click-shadowleak-vulnerability
- ForcedLeak: https://thehackernews.com/2025/09/salesforce-patches-critical-forcedleak.html · https://securityaffairs.com/182676/hacking/forcedleak-flaw-in-salesforce-agentforce-exposes-crm-data-via-prompt-injection.html
- GeminiJack: https://www.infosecurity-magazine.com/news/google-fixes-gemini-enterprise-flaw · https://www.securityweek.com/google-patches-gemini-enterprise-vulnerability-exposing-corporate-data/
- ZombieAgent: https://www.securityweek.com/zombieagent-attack-let-researchers-take-over-chatgpt/ · https://www.techradar.com/pro/security/this-zombieagent-zero-click-vulnerability-allows-for-silent-account-takeover-heres-what-we-know
- Reprompt: https://www.varonis.com/blog/reprompt · https://bleepingcomputer.com/news/security/reprompt-attack-let-hackers-hijack-microsoft-copilot-sessions/
- Copilot DLP bug CW1226324: https://bleepingcomputer.com/news/microsoft/microsoft-says-bug-causes-copilot-to-summarize-confidential-emails · https://petri.com/microsoft-365-copilot-bug-confidential-emails/
- AI Recommendation Poisoning (Microsoft, 10 Feb 2026): https://www.microsoft.com/en-us/security/blog/2026/02/10/ai-recommendation-poisoning/
- OWASP GenAI Exploit Round-up Q1 2026: https://genai.owasp.org/2026/04/14/owasp-genai-exploit-round-up-report-q1-2026/
- OpenClaw: https://thehackernews.com/2026/03/openclaw-ai-agent-flaws-could-enable.html · https://adversa.ai/blog/openclaw-security-101-vulnerabilities-hardening-2026/
- Asana MCP exposure: https://www.bleepingcomputer.com/news/security/asana-warns-mcp-ai-feature-exposed-customer-data-to-other-orgs/
- postmark-mcp (ATLAS AML.CS0053): https://www.startupdefense.io/mitre-atlas-case-studies/aml-cs0053-poisoned-postmark-mcp-server-email-exfiltration
- LiteLLM / TeamPCP: https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-teampcp-supply-chain-campaign/ · https://www.stepsecurity.io/blog/litellm-credential-stealer-hidden-in-pypi-wheel · https://www.securityweek.com/mercor-hit-by-litellm-supply-chain-attack/
- Salesloft Drift (GTIG): https://cloud.google.com/blog/topics/threat-intelligence/data-theft-salesforce-instances-via-salesloft-drift
- LLMjacking (Sysdig): https://sysdig.com/blog/llmjacking-stolen-cloud-credentials-used-in-new-ai-attack/
- Windows Recall redesign: https://blogs.windows.com/windowsexperience/2024/09/27/update-on-recall-security-and-privacy-architecture/
- Rabbit R1 disclosure (unavailable during research): https://rabbitu.de/articles/security-disclosure-1

**Frameworks**
- OWASP Top 10 for LLM Applications 2025: https://genai.owasp.org/llm-top-10/
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/ · summary: https://goteleport.com/blog/owasp-top-10-agentic-applications
- OWASP Agentic AI Threats & Mitigations: https://genai.owasp.org/initiatives/agentic-ai-threats-and-mitigations/
- MITRE ATLAS technique pages (via ATLAS-derived mirror): https://www.startupdefense.io/mitre-atlas-techniques/aml-t0051-llm-prompt-injection · https://www.startupdefense.io/mitre-atlas-techniques/aml-t0080-ai-agent-context-poisoning · https://www.startupdefense.io/mitre-atlas-techniques/aml-t0086-exfiltration-via-ai-agent-tool-invocation · https://www.startupdefense.io/mitre-atlas-techniques/aml-t0077-llm-response-rendering · https://www.startupdefense.io/mitre-atlas-techniques/aml-t0057-llm-data-leakage · https://www.startupdefense.io/mitre-atlas-techniques/aml-t0070-rag-poisoning · https://www.startupdefense.io/mitre-atlas-techniques/aml-t0034-cost-harvesting · MITRE D3FEND view of AML.T0086: https://d3fend.mitre.org/offensive-technique/attack/AML.T0086/

**Defences and research**
- CaMeL, "Defeating Prompt Injections by Design": https://arxiv.org/abs/2503.18813
- "Design Patterns for Securing LLM Agents against Prompt Injections": https://arxiv.org/abs/2506.08837
- Spotlighting: https://arxiv.org/abs/2403.14720
- "The Attacker Moves Second": https://arxiv.org/abs/2510.09023
- Lethal trifecta: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Meta "Agents Rule of Two": https://ai.meta.com/blog/practical-ai-agent-security/
- Microsoft MSRC defence-in-depth vs indirect prompt injection: https://www.microsoft.com/en-us/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks
- Anthropic prompt-injection defences (Nov 2025): https://www.anthropic.com/research/prompt-injection-defenses
- PrivacyLens: https://arxiv.org/abs/2409.00138
- Vec2Text, "Text Embeddings Reveal (Almost) As Much As Text": https://arxiv.org/abs/2310.06816
- MINJA memory injection: https://arxiv.org/abs/2503.03704

**AWS documentation**
- Policy in AgentCore: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html
- AgentCore Memory: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
- AgentCore Identity: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html · data protection: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-data-protection.html
- Guardrails sensitive-information filters: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html
- Bedrock model-invocation logging: https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html · Bedrock data protection: https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html
- Comprehend PII: https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html
- Transcribe PII: https://docs.aws.amazon.com/transcribe/latest/dg/pii-redaction.html · batch: https://docs.aws.amazon.com/transcribe/latest/dg/pii-redaction-batch.html · streaming: https://docs.aws.amazon.com/transcribe/latest/dg/pii-redaction-stream.html
- Nitro Enclaves + KMS attestation: https://docs.aws.amazon.com/enclaves/latest/user/kms.html
- KMS Hierarchical keyring (Database Encryption SDK): https://docs.aws.amazon.com/database-encryption-sdk/latest/devguide/use-hierarchical-keyring.html
- IAM outbound identity federation: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound.html

**Microsoft documentation**
- Refresh tokens: https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens
- Workload identity federation (incl. AWS via IAM outbound federation): https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation

**Redaction tooling and data**
- Presidio supported entities: https://raw.githubusercontent.com/microsoft/presidio/main/docs/supported_entities.md
- Presidio IN_AADHAAR recogniser: https://raw.githubusercontent.com/microsoft/presidio/main/presidio-analyzer/presidio_analyzer/predefined_recognizers/country_specific/india/in_aadhaar_recognizer.py
- Presidio IN_GSTIN recogniser: https://raw.githubusercontent.com/microsoft/presidio/main/presidio-analyzer/presidio_analyzer/predefined_recognizers/country_specific/india/in_gstin_recognizer.py
- NVIDIA GLiNER-PII: https://huggingface.co/nvidia/gliner-PII
- ai4privacy open-pii-masking-500k: https://huggingface.co/datasets/ai4privacy/open-pii-masking-500k-ai4privacy
- Naamapadam / IndicNER: https://arxiv.org/abs/2212.10168
- NIST SP 800-38G Rev. 1 (2nd public draft): https://csrc.nist.gov/pubs/sp/800/38/g/r1/2pd

**Regulatory and official identifier sources**
- HIPAA de-identification, 45 CFR 164.514: https://www.law.cornell.edu/cfr/text/45/164.514
- CPRA "sensitive personal information", Cal. Civ. Code §1798.140: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.140
- IRS valid EIN prefixes: https://www.irs.gov/businesses/small-businesses-self-employed/how-eins-are-assigned-and-valid-ein-prefixes
- CMS MBI format: https://www.cms.gov/medicare/new-medicare-card/understanding-the-mbi.pdf
- SSA SSN randomization (403 during research): https://www.ssa.gov/employer/randomization.html
- CMS NPI check digit (not fetched): https://www.cms.gov/Regulations-and-Guidance/Administrative-Simplification/NationalProvIdentStand/Downloads/NPIcheckdigit.pdf
- India DPDP Act and Rules 2025 (DLA Piper summary): https://www.dlapiperdataprotection.com/index.html?t=law&c=IN
- CERT-In Directions (28 Apr 2022): https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf
