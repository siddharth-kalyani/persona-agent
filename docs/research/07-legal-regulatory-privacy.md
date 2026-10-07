# 07: Legal, Regulatory and Privacy Risk for PersonaAgent

> **NOT LEGAL ADVICE.** This is founder-level research by a non-lawyer analyst. It is meant to help you scope the product and brief counsel. It does not replace a lawyer. Wherever this report says **"Counsel needed"**, get a qualified opinion before you ship, sign or market. Recording, wiretap and biometric laws carry **criminal penalties and statutory damages per person**. Mistakes in this area are expensive and hard to undo.

| | |
|---|---|
| **Research date** | 5–6 October 2026 |
| **Scope** | Track 07: recording consent, AI note-taker litigation, biometrics, workplace and AI regulation, data protection for email/Teams ingestion, sector rules, AI-generated communications, platform policies, consent UX. Added for Phase 1: a **US + India regulatory data-element map** for the redaction engine. |
| **Founder decisions applied** | First buyer: Microsoft 365 mid-market and enterprise teams (per-seat B2B). v1 regions: **United States and India**, covered in most depth. EU/UK/Canada/Australia are later expansion and covered more briefly. Team of 3–6 engineers, ~3-month MVP. Recorder is **work-only and company-governed** (tenant-admin policies), with no personal lifelogging in v1. Phase-1 redaction targets US and Indian requirements. |
| **Method and limits** | The session's WebSearch budget ran out after about 15 searches, so later checks used WebFetch on primary sources: statutes, regulator pages, Microsoft Learn, CERT-In, court-tracking and law-firm pages. Some sites blocked fetching, including MeitY, Justia and CourtListener dockets. Facts are tagged by how they were checked (see the legend). |

**Confidence and verification legend**

- **High / Med / Low** = the analyst's confidence that the claim is accurate on 6 Oct 2026.
- **[V]** = verified this session against the cited source.
- **[K]** = from the analyst's background knowledge (training data to about mid-2026) and **not re-verified this session**. Re-check before you rely on it.
- **[X]** = confirmed by another PersonaAgent research track (cross-referenced, not re-verified here).

---

## Contents

0. Executive summary
1. What the founder decisions change
2. Recording consent: in-person conversations and calls/meetings (US, India; then EU/UK, Canada, Australia, UAE, Singapore)
3. Lawsuits and enforcement against AI note-takers and recorders (2024–2026)
4. Biometric privacy (voiceprints, speaker identification)
5. Workplace monitoring and AI regulation
6. Data protection for email and Teams ingestion
7. Sector rules: health, financial services, legal, eDiscovery, public sector
8. AI-generated communications, personas and impersonation
9. Platform policies: Microsoft, Apple, Google, Zoom
10. Consent UX: what competitors do and recommended patterns
11. Phase-1 redaction map: US + India data element → regime → required treatment
12. Jurisdiction × feature risk matrix
13. Recommendations for PersonaAgent (guardrails for MVP vs Enterprise, legal document set, DPIA template)
14. Top 10 legal risks (likelihood × impact) with mitigations
15. Risks and watch-outs (dated calendar)
16. Open questions / could not verify
17. Sources

---

## 0. Executive summary

**The short version: Pillar 1 (persona drafting) is a manageable data-protection and contract problem. Pillar 2 (always-on and meeting recording) is where the lawsuits are, and the plaintiffs' theory fits our planned architecture closely.**

1. **AI note-takers are an active class-action target in 2025–2026. Plaintiffs' theory has three parts:**
   - The vendor is a *third-party eavesdropper*, not the user's tool, especially if it keeps or uses recordings for its own purposes such as model training.
   - Consent from the host alone is not enough where all parties must consent.
   - Speaker identification creates a *voiceprint* under Illinois's biometric law (BIPA).

   Key cases:
   - ***In re Otter.AI Privacy Litigation*** (N.D. Cal. No. 5:25-cv-06911). On 13 Aug 2026 the court let federal Wiretap Act, CIPA §631, BIPA, unjust-enrichment and UCL claims proceed. It dismissed the CFAA, CDAFA and Washington claims with leave to amend. [V via secondary reporting, Med-High]
   - ***Chamberlain v. Granola*** (N.D. Cal. No. 3:26-cv-07926, filed 30 Jul 2026) targets **bot-free capture of device audio**: microphone plus system output, with no visible bot. That is the design we are considering for Pillar 2. [V, Med-High]
   - **Fireflies.ai** faces BIPA class actions (*Cruz*, Dec 2025; *Fricker*, Mar 2026). [V, Med-High]
   - A hospital faces CIPA and medical-confidentiality claims over an ambient AI scribe (*Saucedo v. Sharp HealthCare*, Nov 2025). [V, Med-High]
2. **Design to defeat those theories from day one:**
   - **Never record silently.** Use a visible bot or banner, an automatic announcement and an on-screen indicator.
   - **No training on, or independent use of, customer content.** Hold a strict processor/service-provider position in the contract *and* in the code.
   - **No voiceprints in the MVP.**
   - **Capture consent from everyone** in all-party-consent jurisdictions.
   - **Admin-governed defaults.**
3. **US recording map:**
   - Federal law (ECPA) is one-party.
   - About 11 states require all-party consent: CA, DE, FL, IL, MD, MA, MI (at least for non-participants), MT, NH, PA, WA.
   - Split states: CT and NV require all-party consent for phone calls; OR and MO for in-person conversations. HI and ME require it for private places. [V RCFP]
   - CIPA allows **$5,000 per violation** (§637.2).
   - California **SB 690**, signed in 2026, removes private suits only for *website* pen-register claims. **Private §631/§632 wiretap claims remain.** [V]
4. **The work-only, company-governed recorder still needs consent from non-employees.**
   - An employer policy plus written acknowledgement can provide *employee* consent, with notice to employees in NY, CT and DE.
   - Clients, vendors, candidates and visitors are not bound by that policy. They need a per-session announcement and consent mechanism, or the device must ignore them (a "consent mode" that keeps only enrolled, consenting speakers).
   - Default in-person capture to **OFF**. Turn on **consent mode** automatically in all-party states, and in India for third parties.
5. **India (v1 market):**
   - No statute requires all-party consent to record. Recordings made by a participant are regularly admitted as evidence; for example, the Supreme Court admitted spousal recordings in *Vibhor Garg* in 2025. [K, Med]
   - The **DPDP Act 2023 + DPDP Rules 2025** (notified 13 Nov 2025) apply in full from **13 May 2027**. [V DLA Piper; X] From then, every recording or email of a third party needs notice and consent or a "legitimate use".
   - The *employment* legitimate use covers employees, not outsiders. [K, Med]
   - Until May 2027, **IT Act s.43A + SPDI Rules 2011** govern. Biometrics, including voiceprints, are "sensitive personal data" there and need written consent. [K, High]
   - **CERT-In Directions**: report incidents within **6 hours** and keep **180 days of logs in India**. [V primary PDF]
6. **Biometrics:**
   - Avoid voice enrollment and speaker identification in v1.
   - BIPA's 2024 amendment limits damages to one recovery per person per collection method ($1,000 negligent / $5,000 reckless). The 7th Circuit held it **retroactive** (*Clay v. Union Pacific*, 1 Apr 2026). [V via law-firm reporting] Exposure per class is still large.
   - Texas CUBI ($25k per violation, AG-enforced), Washington's My Health My Data Act (private right of action), Colorado's biometric amendment (in force 1 Jul 2025) and GDPR Art. 9 add to the risk.
7. **EU AI Act:**
   - Inferring emotions from **voice** at work has been **prohibited** since 2 Feb 2025 (Art. 5(1)(f)).
   - **Text-only** sentiment or tone falls outside the "emotion recognition" definition, which requires biometric data (Commission guidelines). [V via CMS summary]
   - The **Digital Omnibus on AI (Reg. (EU) 2026/1744, in force 27 Jul 2026)** moved Annex III high-risk duties, including the employment uses, to **2 Dec 2027**. It left **Art. 50 transparency applying from 2 Aug 2026**, with a grace period to **2 Dec 2026** only for Art. 50(2) marking on systems already on the market. [V Cooley, Jones Walker]
   - Do not market or allow PersonaAgent for performance evaluation. That use could make it a high-risk system.
8. **Pillar 1 has three real legal issues:**
   - **Microsoft API Terms.** Email APIs may only be used to sync or back up mail "unless you have use permissions expressly and specifically granted by Customers". The contract and consent screens must grant persona learning explicitly. Keep no copies beyond the intended use, and propagate deletions. [V]
   - **Third-party personal data** inside sent mail. Under CPRA, the contents of email are "sensitive personal information" [X]. GDPR and DPDP also apply.
   - **The persona is an impersonation kit.** Require strong authentication, a human send step (no autonomous sending in v1), and offboarding that deletes or freezes the persona when the employee leaves.
9. **AI-disclosure law does not currently force labels on human-sent, AI-assisted email in the US.** Exceptions: bots meant to mislead in sales or elections (CA SB 1001), Utah's on-request disclosure, and future Colorado ADMT notices (from 1 Jan 2027) for consequential decisions. EU Art. 50(2) may require **machine-readable marking** of generated text. Ship an invisible metadata marker plus an optional visible disclosure that each tenant can configure.
10. **Sector rules can turn our outputs into regulated records:**
    - **FINRA/SEC.** Transcripts, summaries and sent drafts can be business communications that must be retained.
    - **HIPAA.** BAAs are required, and voiceprints appear in Safe Harbor's 18 identifiers.
    - **Privilege.** An AI note-taker in a meeting with lawyers can undermine privilege.
    - **eDiscovery.** Legal hold must override auto-delete and crypto-shredding.
11. **India data residency:**
    - The DPDP Act does **not** generally require localization. Transfers are allowed except to blacklisted countries; only Significant Data Fiduciaries may face localization for specified data. [V DLA Piper]
    - **RBI** (payment system data), **SEBI** (CSCRF/cloud framework for regulated entities) and **IRDAI** (insurance records) impose sector mandates on regulated customers. [K, Med-High]
    - Pin India tenants to AWS Mumbai. Offer in-India inference for BFSI tenants; per the AWS track, only some Claude models are available in-region.
12. **Phase-1 redaction (Section 11)** gives element-by-element rules for US and India. Examples: SSNs, card numbers (PAN), CVVs, account credentials, Aadhaar numbers and Indian tax PANs are **irreversibly masked or deleted at ingestion**, while names and emails are **tokenized**. This keeps PersonaAgent out of PCI DSS and Aadhaar Data Vault scope and makes breach-law exposure much smaller.
13. **Top risks**, in rank order (Section 14):
    1. Wiretap/CIPA class action.
    2. BIPA claims over speaker identification.
    3. Becoming a "third party" or controller through secondary use or training.
    4. Microsoft platform or terms dependency.
    5. Persona misuse for fraud or impersonation.
    6. A breach of a corpus of highly sensitive communications.
    7. Workplace-monitoring and works-council blockers (EU), plus AI Act misuse.
    8. eDiscovery, spoliation and privilege.
    9. Sector recordkeeping, HIPAA and RBI/SEBI duties.
    10. India DPDP/CERT-In readiness, plus trademark (the name "PersonaAgent" is already used by an ACL 2026 research framework [X]).

---

## 1. What the founder decisions change

| Founder decision | Legal effect | Net |
|---|---|---|
| **B2B, Microsoft 365 mid-market and enterprise, per-seat** | The customer (the employer) is the **controller** (GDPR) or **Data Fiduciary** (India DPDP) or **business** (CCPA). We are the **processor / Data Processor / service provider**. This is the right structure, but we only keep it if we **never use customer content for our own purposes**, model training included. That is the line the *Otter* plaintiffs are attacking (Section 3). The customer's admin consent, together with Microsoft's own terms, becomes the legal basis for accessing the M365 data. | Lower risk than a consumer app |
| **US + India first** | The US brings litigation risk: CIPA, BIPA and wiretap class actions with statutory damages. India brings regulatory risk: DPDP from May 2027, CERT-In now, and RBI/SEBI/IRDAI for BFSI customers. India has no class-action culture comparable to the US. Deferring the EU removes the hardest workplace-monitoring regimes for now (works councils, the CNIL, the AI Act ban on inferring emotions from voice). | Focus US effort on recording and biometrics. Focus India effort on DPDP and sector readiness. |
| **3–6 engineers, ~3-month MVP** | We cannot build per-state legal logic for everything. Pick **conservative global defaults**: treat every meeting as all-party consent, no voiceprints, no training on customer data, never record silently. Default-strict is cheaper than jurisdiction-aware. | Simplify by being strict |
| **Work-only, company-governed recorder; no personal lifelogging** | This removes the consumer-household angle and makes the employer the accountable controller. It enables employee consent through policy plus acknowledgement. It also triggers **employee-monitoring rules**: notice laws in NY, CT and DE; works councils and the AI Act in the EU later. It **does not solve consent for non-employees**: clients, vendors, candidates and visitors (Section 2.4). | Necessary but not sufficient |
| **Phase-1 redaction precise to US + India requirements** | This is feasible. The US and Indian regimes are list-based: HIPAA's 18 identifiers, PCI cardholder data, breach-law personal-information elements, SPDI categories, Aadhaar. Masking at ingestion also keeps PersonaAgent out of PCI DSS scope and Aadhaar-vault obligations (Section 11). | High value, low legal risk |

---

## 2. Recording consent

### 2.1 US federal law (ECPA / Wiretap Act)

- **One-party consent.** 18 U.S.C. §2511(2)(d) allows a party to a communication, or someone with one party's prior consent, to intercept it, *"unless such communication is intercepted for the purpose of committing any criminal or tortious act."* [K, High]
- **Penalties.** Civil remedies (§2520) are the greater of **$100/day or $10,000** per plaintiff, plus punitive damages and attorney's fees. Criminal exposure is up to 5 years. [K, High]
- **The crime-tort exception is the live risk for vendors.** In *Otter*, the court accepted, at the pleading stage, that using recordings to train models "for its own pecuniary gain" could be a *tortious purpose*. That would defeat the one-party defence (Section 3). [V via secondary reporting, Med-High]
- **Stored email and Teams messages.** Reading a user's own mailbox and chats with that user's and the tenant admin's authorization fits the Stored Communications Act authorization structure. The real constraints for Pillar 1 are contract and data-protection limits (Sections 6 and 9), not wiretap law. [K, Med-High]

### 2.2 US states: who must consent?

The Reporters Committee (RCFP) recording guide [V] classifies the states as follows.

**All-party consent ("about 11 states")**: California, Delaware, Florida, Illinois, Maryland, Massachusetts, Michigan (at least for recordings by non-participants), Montana, New Hampshire, Pennsylvania and Washington.

**Split rules:**
- **Missouri and Oregon**: all-party for *in-person* conversations, one-party for *phone calls*.
- **Connecticut and Nevada**: all-party for *phone calls*, one-party for *in-person*.
- **Hawaii and Maine**: all-party in *particularly private places*.

| State | Phone / online calls | In-person | Nuances that matter for PersonaAgent | Remedy (indicative) |
|---|---|---|---|---|
| **California** | All-party for "confidential communications" (PC §632). §632.7 covers cellular/cordless calls regardless of confidentiality. §631 covers wiretapping and third-party "eavesdroppers". | All-party (§632) | "Confidential" = an objectively reasonable expectation of not being overheard or recorded (*Flanagan v. Flanagan*, Cal. 2002) [K, High]. Applies to out-of-state callers who record CA residents (*Kearney v. Salomon Smith Barney*, Cal. 2006) [K, High]. Consent must come **before** recording; consent obtained afterwards does not cure it (*Javier v. Assurance IQ*, 9th Cir. 2022) [K, High]. | **$5,000 per violation** or 3× actual damages; no proof of harm needed (§637.2) [K, High] |
| **Florida** | All-party (Fla. Stat. §934.03) | All-party where there is an expectation of privacy | Third-degree felony | Greater of $100/day or $1,000 (§934.10) [K, Med-High] |
| **Illinois** | All-party for "private conversations" (720 ILCS 5/14-2, rewritten in 2014) | Same | Surreptitious recording is the key element. Note **BIPA** for voiceprints (Section 4). | Actual + punitive damages (14-6) [K, Med] |
| **Maryland** | All-party (Cts. & Jud. Proc. §10-402) | All-party (private conversations) | Felony | $100/day or $1,000 [K, Med-High] |
| **Massachusetts** | All-party: G.L. c.272 §99 bans **"secret"** recording | Same | Open, known recording (indicator plus announcement) is generally not "secret" [K, Med] | $100/day or $1,000, punitive damages, fees [K, Med-High] |
| **Montana** | All-party (§45-8-213) | Same | Statute exempts recording where parties were **given warning** [K, Med] | Criminal |
| **New Hampshire** | All-party (RSA 570-A) | Same | Felony | Civil remedy [K, Med] |
| **Pennsylvania** | All-party (18 Pa.C.S. §5703–5704) | All-party where there is an expectation of non-interception | Felony | $100/day or $1,000 [K, Med-High] |
| **Washington** | All-party (RCW 9.73.030) | Same | **Consent is deemed given when one party announces the recording "in any reasonably effective manner" and the announcement itself is recorded.** This is a statutory model for our announcement feature. [K, High] | Up to $1,000 liquidated, plus actual damages and fees [K, Med] |
| **Delaware** | Conflicting statutes: wiretap law (11 Del. C. §2402) is one-party; privacy law (§1335) is all-party | Same conflict | RCFP advises following the stricter rule [V] | Criminal |
| **Michigan** | MCL 750.539c ("eavesdropping") | Same | Participants may record (*Sullivan v. Gray*, 1982), but **non-participant recorders need all-party consent**. A vendor bot could be argued to be a non-participant. [V RCFP] | Felony; civil damages [V] |
| **Connecticut** | **All-party for calls** (civil liability, §52-570d). Consent can be written, verbal at the start and recorded, or given by a warning tone. | One-party | Treat Teams/VoIP calls as all-party [K, Med-High] | Civil |
| **Nevada** | **All-party for wire/phone** (*Lane v. Allstate*, Nev. 1998) | One-party | [V RCFP; K for case] | Civil and criminal |
| **Oregon** | One-party | **All participants must be "specifically informed"** (ORS 165.540(1)(c)) | A 2023 panel decision striking this law was **reversed en banc**. *Project Veritas v. Schmidt*, 125 F.4th 929 (9th Cir. 2025) upheld it (10–2). RCFP's Oregon page appears out of date. [V via search results; cert petition status not verified] | Misdemeanor; civil: greater of actual damages, $100/day or $1,000 (ORS 133.739) [V RCFP] |
| **Missouri** | One-party | All-party per RCFP (§542.402) | Unusual reading; confirm with counsel [V RCFP, Med] | Criminal |
| **Hawaii, Maine** | One-party | All-party in private places | Avoid capture in private spaces (restrooms, lodging) | Criminal |
| **All other states, DC** | One-party | One-party (most protect only conversations with a reasonable expectation of privacy) | One-party consent still requires that **our user is a party**. A recorder left running in an empty meeting room is *not* a party in any state. | ECPA |

**Reasonable expectation of privacy.** Most statutes protect only conversations with a reasonable expectation of privacy. Typical outcomes:
- *Usually protected*: closed meeting rooms, 1:1s, HR conversations, phone and video calls.
- *Usually not protected*: public places, speeches, open-floor chatter that others can obviously overhear.

For an office recorder this distinction does not help much. Most valuable work conversations are exactly the kind people expect to stay private. [V RCFP; K]

**Interstate rule.** If any participant is in an all-party state, assume the strictest law applies. [V RCFP]

### 2.3 California CIPA and the litigation wave

- **§631** (wiretapping, including "reads or attempts to learn the contents" of a communication in transit, and aiding others to do so) is the provision used against **vendors** in website-chat, contact-centre AI and note-taker cases.
- **Two tests decide whether a vendor is a "third party":**
  - The *extension* test: the vendor is just the party's tool unless it uses the data for its own purposes.
  - The *capability* test: having the ability to use the data is enough.
- *Ambriz v. Google* (N.D. Cal., 10 Feb 2025) applied the capability test to Google Cloud Contact Center AI and denied dismissal. [V ZwillGen/Goodwin summaries]
- **§632** (recording confidential communications) applies to **parties too**. So in California, a recording made by our *user* still needs all-party consent, whether or not we are a third party.
- **SB 690** started as a broad "commercial business purpose" exemption. It was amended on 1 Jul 2026 to drop that exemption. As **signed by Governor Newsom (reported 1 Oct 2026)** it only (a) makes **§638.51 pen-register / trap-and-trace claims arising from websites and apps enforceable by the Attorney General only**, retroactive to actions filed within two years. It **does not eliminate private claims under §§631 or 632**. [V KTS alert; NatLawReview; Skadden]
- **Lesson.** California will not legislate the note-taker problem away. Our protection has to come from consent capture and processor-only use.

### 2.4 Consent posture for the work-only, company-governed recorder (US)

| Who is speaking | How consent can be obtained | Adequacy in all-party states | Product mechanism |
|---|---|---|---|
| **Our user** (employee, recorder owner) | Signs up, enables the recorder, accepts the terms | Fine | Onboarding consent, logged |
| **Co-workers in the same tenant** | Employer **recording/monitoring policy plus signed acknowledgement**. This also meets the electronic-monitoring notice laws in NY (Civ. Rights Law §52-c), CT (§31-48d) and DE (19 Del. C. §705) (Section 5.3). Add **real-time notice**: device LED or screen indicator, Teams banner, spoken announcement. | Generally defensible. Prior written consent plus a contemporaneous indicator is the strongest form. A policy alone, without real-time notice, is weaker for in-person "confidential" conversations. | Tenant-admin policy attestation; per-employee acknowledgement captured in-app; "recording" indicators; per-person opt-out ("don't capture me") |
| **External meeting participants** (clients, vendors, candidates) | Not bound by the employer's policy. Need notice **before** capture plus consent. The usual forms are an announcement plus continued participation (implied consent) or an explicit click or verbal "yes". | Implied consent after a clear, prior announcement is widely relied on for calls (WA's statute codifies it). It is **contested** for in-person recording and for silent, bot-free capture (*Granola*). | Teams: native transcription banner. Our bot/app posts a chat notice with a link to the notice. A spoken announcement in all-party mode. "Stop recording me" and "delete my segment" controls. External meetings **off by default** [X planned default] |
| **Bystanders / visitors in the office** (in-person) | Signage reduces expectations but **does not supply consent** to a targeted recording of their conversation | High risk in CA, FL, IL, MD, MA, MT, NH, PA, WA, and under OR's in-person rule | **Consent mode**: keep only the wearer's own speech, or speech from enrolled, consenting colleagues. Discard everyone else at the edge before upload. **Auto-pause zones and calendar-based pauses.** Default in-person capture **OFF** unless the admin enables it. |
| **Minors, patients, privileged meetings** | Special regimes (COPPA/DPDP children's rules; HIPAA/CMIA; privilege) | Highest risk | Hard blocks: health/patient settings unless a BAA is in place and the customer configures it; a "privileged meeting" mode that never records; no use in schools |

**Unresolved tension. Counsel needed.**
- "Consent mode" in the strict sense means recording only voices that consented. That needs some way to tell consenting voices apart. Doing it with **voice enrollment creates a biometric identifier** (Section 4).
- Safer options for v1:
  1. **Wearer-only capture.** Use near-field microphone gain and voice-activity heuristics, with no stored template. This is technically imperfect.
  2. **Manual "everyone here consented" confirmation** before each capture, logged with time and place.
  3. **Text-only memory.** Transcribe on the device or in streaming mode, keep only the user's own utterances plus a summary of others, and never keep raw audio.
- Before choosing, ask counsel whether a summary of other people's statements is itself a "recording" under §632. The safe assumption is yes, if it is created from an unconsented recording.

### 2.5 India: consent posture for recording (v1 market, in depth)

| Layer | Rule | Effect on PersonaAgent | Confidence |
|---|---|---|---|
| **Statutory wiretap rule** | India has **no general statute** requiring all-party consent for a participant to record a private conversation. Lawful interception of telecom by the State is governed by the Telecommunications Act 2023 (replacing Telegraph Act s.5(2)) and the *PUCL* (1997) safeguards. | Participant recording is not per se criminal. **Counsel needed:** whether capture of VoIP or Teams audio by a non-participant vendor service could be "unauthorised interception" under the Telecommunications Act 2023. | [K] Med; interception-offence point Low |
| **Constitution** | *K.S. Puttaswamy v. Union of India* (2017, 9 judges): privacy is a fundamental right (Art. 21). It mainly binds the State; its horizontal application is developing. | Supports regulators' and courts' expectations of notice and consent | [K] High |
| **Evidence** | Courts admit recorded conversations subject to relevance, identification of voices and accuracy (*R.M. Malkani*, 1973; *Yusufalli Esmail Nagree*, 1968). The Supreme Court in ***Vibhor Garg v. Neha* (2025)** allowed secretly recorded spousal calls as evidence in matrimonial proceedings. | Admissibility ≠ lawfulness. It means our recordings and summaries **will** be discoverable and used in disputes (Section 7). | [K] High (older cases); Med (2025 case) |
| **IT Act 2000 + SPDI Rules 2011 (applicable now, until DPDP fully applies)** | **s.43A**: a body corporate handling **sensitive personal data or information (SPDI)** that negligently fails to maintain reasonable security practices is liable to pay compensation. **SPDI Rules 2011, Rule 3** list SPDI: passwords; financial information (bank account, card or other payment-instrument details); physical, physiological and mental health; sexual orientation; medical records and history; **biometric information** (defined to include "voice patterns"). **Rule 5** requires **consent in writing** (letter, fax or email) for SPDI. **s.72A**: disclosure in breach of a lawful contract is punishable (up to 3 years or ₹5 lakh). | Voice biometrics and payment and health data in transcripts trigger SPDI duties **today**: a privacy policy, written consent for SPDI, reasonable security (ISO 27001 is the safe harbour), and transfer only with equal protection | [K] High; [X] |
| **DPDP Act 2023 + DPDP Rules 2025** | Rules notified **13 Nov 2025**. Board provisions immediate; consent managers **13 Nov 2026**; **all other substantive obligations 13 May 2027**. Until then the IT Act and SPDI Rules govern. [V DLA Piper; X] | From May 2027 every recording or transcript of an identifiable person is digital personal data | High |
| | **Lawful grounds**: notice (s.5) plus consent (s.6), which must be "free, specific, informed, unconditional and unambiguous with a clear affirmative action", **or** a "legitimate use" (s.7). s.7(i) covers employment purposes, including protecting the employer from loss or liability, corporate espionage, and confidentiality of trade secrets and IP. s.7(a) covers data **voluntarily provided** for a specified purpose where the person has not objected. | **Employees**: the employer (Data Fiduciary) can plausibly rely on s.7(i) for work-only capture. **Third parties** (clients, vendors): rely on notice plus consent, or perhaps s.7(a) after a clear announcement with an objection option. Counsel needed. | [K] Med |
| | Notices must be **itemised and plain**. Data Principals must be able to read them in English or any **Eighth Schedule language** (s.5(3)). Withdrawing consent must be as easy as giving it. | Localised notice text, "stop recording me" and withdrawal flows | [K] High |
| | **Children** (under 18): verifiable parental consent; **no tracking or behavioural monitoring** of children (s.9) | Work-only scope helps. Add auto-pause rules (for example school settings) and a no-minors clause in the AUP. | [V DLA Piper] High |
| | **Breach**: notify the Board and each affected Data Principal without delay; detailed report to the Board **within 72 hours** [V]. Security safeguards include "**encryption, obfuscation or masking or the use of virtual tokens**" [V]; keep logs and personal data for **one year** for breach investigation [V]. | Our DPA must flow these down. Our incident runbooks must support 72-hour Board reports by the customer. | High |
| **CERT-In Directions (28 Apr 2022)** | Report listed cyber incidents (including **data breach, data leak**, and attacks on **AI/ML** systems) **within 6 hours** of noticing. Keep **logs of all ICT systems for a rolling 180 days within Indian jurisdiction**. Synchronise clocks to NIC/NPL NTP or a traceable source. Designate a CERT-In point of contact. Applies to "service providers, intermediaries, data centres, body corporate and Government organisations". [V primary PDF] | Applies to us as a body corporate serving India, and to our Indian customers. Keep **India-resident log copies** and a 6-hour reporting runbook. | High |

**Recommended India posture for the work-only recorder:**
1. The employer's policy and employment contract include a recording/AI clause; collect the employee's acknowledgement in-app.
2. Every meeting gets an announcement plus the Teams banner. In-person mode defaults to wearer-only.
3. External participants get an opt-out, and "consent mode" is the default.
4. Notices are available in English and Hindi first, with other Eighth Schedule languages on request.
5. **No voice biometrics** before written (electronic) consent; this satisfies SPDI Rule 5 now and the DPDP later.
6. India-resident storage and logs.

### 2.6 EU and UK (later markets, summary)

| Topic | EU | UK |
|---|---|---|
| Lawful basis for recording employees | GDPR Art. 6(1)(f) **legitimate interests** with documented balancing. **Consent is rarely valid for employees** because of the power imbalance (WP29 Opinion 2/2017; EDPB consent guidelines 05/2020). Art. 88 and national employment-data laws apply. [K, High] | UK GDPR as amended by the **Data (Use and Access) Act 2025** (Royal Assent 19 Jun 2025, commencing in phases) [K, Med-High]. ICO *Monitoring workers* guidance (Oct 2023): DPIA, transparency, covert monitoring only in exceptional cases. [K, High] |
| Bystanders and third parties | Art. 13 notice applies at collection, because observation counts as collection from the data subject. Art. 21 right to object. The household exemption does **not** cover work use (CJEU *Ryneš*, C-212/13). [K, High] | Same principles |
| Communications confidentiality | ePrivacy Directive Art. 5(1) as nationally implemented: interception or storage by non-users needs consent. [K, Med-High] | Investigatory Powers Act 2016 (interception offence). The 2018 Business Monitoring Regulations allow business interception if users are informed. [K, Med] |
| Criminal recording laws | **Germany §201 StGB**: recording another person's *non-publicly spoken word* without authorisation, up to 3 years or a fine. **France Art. 226-1 Code pénal**: up to 1 year and €45,000. Several states (for example Italy and Spain) allow a participant to record, but GDPR still applies. [K, High for DE/FR; Med others] | A participant recording is not a crime. Data-protection law applies. [K, High] |
| AI Act | Emotion inference from voice at work is prohibited; Art. 50 transparency (Section 5.1) | Not applicable |

### 2.7 Canada, Australia, UAE, Singapore (brief)

| Jurisdiction | Recording rule | Data-protection overlay | Default for PersonaAgent |
|---|---|---|---|
| **Canada** | **One-party** consent under the Criminal Code s.184(2)(a) [K, High] | PIPEDA (consent and notice for commercial collection). Quebec Law 25 (privacy impact assessments, automated-decision transparency). Alberta and BC PIPA cover employees. Federal reform (Bill C-27) died in Jan 2025. [K, High] | Notice plus consent; consent mode for outsiders |
| **Australia** | State and territory surveillance-device laws differ. **Participant recording is allowed** in Vic, Qld and NT (with limits on publishing). **NSW, WA, SA, Tas and ACT** generally require consent of all principal parties unless the recording is reasonably necessary to protect lawful interests (exact tests vary). The federal Telecommunications (Interception and Access) Act 1979 governs calls. [K, Med] | Privacy Act 1988. The private-sector **employee-records exemption** has limits. A **statutory tort for serious invasions of privacy** started 10 Jun 2025 [K, Med-High]. The **NSW Workplace Surveillance Act 2005** requires 14 days' notice to employees [K, High]. | Treat as all-party |
| **UAE** | Federal Decree-Law 34/2021 (cybercrimes) criminalises eavesdropping on or recording conversations without consent using IT means: imprisonment plus fines, reportedly AED 150k–500k [K, Med] | PDPL (Federal Decree-Law 45/2021); its implementation status should be checked [K, Med] | Treat as **all-party and criminal**. Do not launch the recorder without local counsel. |
| **Singapore** | No general all-party statute for participant recording [K, Med] | PDPA 2012: notification and consent, with deemed consent by notification and a legitimate-interests exception (2020 amendments) [K, Med] | Notice plus opt-out; consent mode for outsiders |

---

## 3. Lawsuits and enforcement against AI note-takers and recorders (2024–2026)

### 3.1 Private litigation

| Matter | Forum and dates | Claims | Status (as known on 6 Oct 2026) | Lesson for PersonaAgent | Conf. |
|---|---|---|---|---|---|
| **In re Otter.AI Privacy Litigation** (lead case *Brewer v. Otter.ai*) | N.D. Cal., No. 5:25-cv-06911-EKL (Judge Eumi K. Lee). First suit filed Aug 2025; consolidated complaint 5 Dec 2025 (7 plaintiffs from CA, IL, WA). | ECPA, CIPA §§631/632, BIPA (voiceprints), CFAA, CDAFA, WA privacy act, intrusion, UCL, unjust enrichment | **13 Aug 2026 order granted the motion to dismiss only in part.** Surviving: federal Wiretap Act, **CIPA §631**, **both BIPA claims**, unjust enrichment, UCL. Dismissed with leave to amend: CFAA, CDAFA, WA Privacy Act, most intrusion claims. The court found it plausible that Otter "independently collects, retains, and uses communications for its own commercial purposes" (a **third-party eavesdropper**). Host-only consent was not enough. Training "for its own pecuniary gain" was plausibly **tortious**, which defeats one-party consent under ECPA. BIPA voiceprint allegations (speaker identification across meetings) were plausible. Amended complaints were due around late Aug 2026; discovery and class certification are ahead. | (1) Never use customer recordings or transcripts to train models or for any purpose of our own. (2) Notify **every** participant, not just the host. (3) Do not build cross-meeting speaker profiles without BIPA-grade consent. (4) Auto-join behaviour (bots joining from a calendar without a fresh decision) was central to the complaints. | Med-High [V secondary: recordinglaw.com, tl;dv, Sheppard Mullin blog title, Courthouse News; docket not fetchable] |
| **Chamberlain v. Granola, Inc. and Granola Labs Ltd.** | N.D. Cal., No. 3:26-cv-07926, filed **30 Jul 2026** (Florida plaintiff, nationwide class plus California subclass) | ECPA, CIPA | Early stage; no response filed as of Oct 2026 reporting | **Bot-free desktop capture** (microphone plus **system audio**, with no visible participant) is pleaded as *designed to hide* recording. The complaint also attacks **training by default** and the inability to delete data once it is in a model. **This is the closest analogue to PersonaAgent's planned bot-free Teams capture.** | Med-High [V secondary: consentpixel, ppc.land, layer3labs] |
| **Cruz v. Fireflies.AI Corp.** (and ***Fricker v. Fireflies.AI***) | Federal court, Illinois. *Cruz* filed 18 Dec 2025; *Fricker* filed Mar 2026 (N.D. Ill.). | BIPA: voiceprints of **non-users** created by "speaker recognition"; no public retention schedule; no notice or written release | Pending (outcome unknown) | Speaker diarization **plus identification** = voiceprint risk. Publish a biometric retention policy *if* you ever process voiceprints. | Med-High [V NatLawReview, Sheppard, Top Class Actions] |
| **Saucedo v. Sharp HealthCare** | Cal. Superior Court (San Diego), filed **Nov 2025** | CIPA (all-party consent) + **CMIA** (medical confidentiality); ambient AI scribe (Abridge) | Pending | Consent cannot be a pre-ticked box or a staff note. In healthcare settings, recording needs documented **patient** consent and a BAA. | Med-High [V Becker's, Fisher Phillips] |
| **Ambriz v. Google** (Contact Center AI) | N.D. Cal., MTD denied **10 Feb 2025** | CIPA §631, §637.5 | Proceeding | Under the **capability test**, merely being *able* to use intercepted data for your own purposes can make you a third party. Contract terms and technical controls (no human access, no training, tenant-scoped keys) must make "no independent use" provable. | High [V ZwillGen, Goodwin] |
| **Lopez v. Apple** (Siri accidental activations) | N.D. Cal.; **$95M** settlement (2024–25) | Wiretap/privacy claims over false-wake recordings reviewed by contractors | Settled | **False activations and human review of audio** are a class-action theory. Log activation causes, and ban human review without opt-in. | High [K] |
| **In re Google Assistant Privacy Litigation** | N.D. Cal.; settlement reported early 2026 (about **$68M**) | Same theory | Settled (reported) | Same | Med [K] |
| **Texas v. Meta** (CUBI, face templates) | Texas AG; **$1.4B** settlement, Jul 2024 | Texas biometric law | Settled | State AGs can enforce biometric laws without a private right of action, at very large scale | High [K] |
| **Texas v. Google** | Texas AG; **$1.375B**, May 2025 | Included biometric (voice and face) and location claims | Settled | Same; **voiceprints** are in scope | High [K] |
| **In re Zoom Video Communications Privacy Litigation** | N.D. Cal.; **$85M** settlement (2021–22) | Data sharing, "Zoombombing" | Settled | Vendor marketing claims about encryption and privacy must be accurate (see also FTC v. Zoom, 2020–21) | High [K] |

**Searched for but not found (search budget exhausted, so this is not proof of absence):** wiretap or BIPA suits specifically against **Read.ai, Gong, Limitless, Bee or Plaud**, or against **Microsoft Teams/Recall**, over recording consent. Flag for counsel's docket search. [Low]

### 3.2 Regulator actions and guidance relevant to us

| Regulator | Action | Year | Relevance | Conf. |
|---|---|---|---|---|
| **FTC + DOJ v. Amazon (Alexa)** | $25M; Amazon kept children's voice recordings and geolocation indefinitely and used them to train; ordered deletion | 2023 | **Retention of voice data "for training" is itself a violation risk.** Algorithm/data deletion remedies exist. | High [K] |
| **FTC v. Ring** | $5.8M; employees and contractors had unrestricted access to customers' private videos | 2023 | **Insider access to recordings** = an unfair practice. Least-privilege access, audit logs, no default human review. | High [K] |
| **FTC guidance** | "AI companies: uphold your privacy and confidentiality commitments" (Jan 2024). Quietly changing terms to allow AI training may be unfair or deceptive (Feb 2024). | 2024 | Never retro-fit a training right through a terms-of-service change | High [K] |
| **FTC v. Rite Aid** | Ban on facial recognition after failures of biometric governance | 2023 | Biometric AI needs testing, governance, and notice | High [K] |
| **CNIL (France) v. Amazon France Logistique** | **€32M** for excessively intrusive employee monitoring (scanner idle-time and speed indicators, retention) | Dec 2023 / Jan 2024 | Continuous, granular monitoring of workers is disproportionate. Relevant when we expand to the EU. | High [K]; appeal status not verified |
| **Hamburg DPA v. H&M** | **€35.3M** for profiles of employees' private lives built from managers' notes | 2020 | **Our long-term "memory" could build exactly such profiles of colleagues** (illnesses, family events). Add memory-content controls (Section 13). | High [K] |
| **ICO (UK) v. Serco Leisure** | Enforcement notices: stop facial/fingerprint attendance biometrics; employees had no real choice | Feb 2024 | Biometrics at work need a genuine alternative | High [K] |
| **Italian Garante** | OpenAI **€15M** (Dec 2024); Luka/Replika **€5M** (2025) | 2024–25 | EU DPAs act directly against generative-AI providers on lawful basis and transparency | High / Med-High [K] |
| **ICO and others on Microsoft Recall** | Regulatory inquiries in 2024; Microsoft redesigned Recall as opt-in, with encryption and Windows Hello, before release in 2025 | 2024–25 | "Capture everything" features are redesigned under regulatory pressure. Opt-in plus local controls became the norm. | High [K] |

### 3.3 Market signals (product exits and pivots)

- **Humane** (AI Pin): shut down in Feb 2025; assets sold to HP. [K, High]
- **Limitless**: acquired by **Meta** (Dec 2025). Desktop and web capture ended, and Rewind capture was disabled on 19 Dec 2025. [X hardware track; K]
- **Bee**: acquired by **Amazon** (Jul 2025). Uses a button and a green LED, and says audio is "not saved, stored, or used for AI training". [X]
- **The market is moving away from silent, always-on capture**, towards press-to-record, visible LEDs and no stored audio. Treat this as a strong signal for Pillar 2's design. [X]

---

## 4. Biometric privacy (voiceprints and speaker identification)

### 4.1 Why this matters

Three planned features can create a **voiceprint**, meaning a voice template that can identify a person:
- speaker identification ("that was Priya");
- voice enrollment for "consent mode";
- cross-meeting speaker memory.

Raw audio and anonymous transcripts are lower risk. **Using voice to identify a person is what triggers biometric law.**

### 4.2 Regimes

| Regime | Covers voice? | Core duties | Remedies | Conf. |
|---|---|---|---|---|
| **Illinois BIPA** (740 ILCS 14) | "Voiceprint" is listed as a biometric identifier | **§15(a)**: a *public* written retention and destruction policy; destroy when the purpose is satisfied or within **3 years** of the last interaction, whichever is first. **§15(b)**: written notice of purpose and term, and a **written release** before collection (an e-signature is valid since 2024). §15(c): no profiting. §15(d): no disclosure without consent. §15(e): reasonable security. | Private right of action: **$1,000 negligent / $5,000 intentional or reckless** per violation, plus fees. The **2024 amendment (P.A. 103-0769)** allows one recovery per person per collection method. The 7th Circuit held this **retroactive** (*Clay v. Union Pacific*, No. 25-2185, 1 Apr 2026). | High [K text]; [V Jackson Lewis/SGR on *Clay*] |
| **Texas CUBI** (Bus. & Com. Code §503.001) | Voiceprint included | Inform and get consent before capture for a commercial purpose; no sale; destroy within a reasonable time, no later than **1 year** after the purpose expires | **AG only**, up to **$25,000 per violation** (Meta $1.4B; Google $1.375B) | High [K] |
| **Washington My Health My Data Act** (RCW 19.373) | "Biometric data" includes "**voice recordings, from which an identifier template can be extracted**" | Consent to collect, separate consent to share; a consumer health privacy policy | **Private right of action** (via the Consumer Protection Act). **Note:** "consumer" **excludes individuals acting in an employment context**. This lowers the risk for internal meetings but not for consumer-facing uses. | High [V RCW 19.373.010] |
| **Washington RCW 19.375** | Biometric identifiers enrolled for a commercial purpose | Notice, consent or opt-out mechanism | AG only | Med [K] |
| **Colorado (HB24-1130, amending the Colorado Privacy Act)** | Biometric identifiers (voiceprint is understood to be included) | In force **1 Jul 2025** [V]. Notice and consent; a retention schedule; deletion deadlines. **Applies to employers for employees' biometrics, with limits on when consent may be required.** Understood to apply regardless of the CPA's general volume thresholds. | AG / district attorneys | Effective date High [V]; details Med [K] |
| **Other US state privacy laws** (about 20 states) | Biometric data processed to identify = "sensitive data" | **Opt-in consent** for consumers; processor contract terms | AG enforcement | High [K] |
| **California CPRA** | Processing biometric information to uniquely identify = **sensitive personal information**; applies to employees too | Notice at collection, right to limit, risk assessment (CPPA regs, Section 5.3) | CPPA/AG; private action only for breaches | High [K] |
| **GDPR Art. 9** | Biometric data "for the purpose of uniquely identifying" a person. Voice recordings alone are **not** biometric data; voice-based identification **is**. | **Explicit consent** or another Art. 9(2) exception. Employee consent is doubtful. EDPB Guidelines 02/2021 (voice assistants): voice identification needs explicit consent and an alternative. | DPAs; fines up to 4% | High [K] |
| **EU AI Act** | Comparing a speaker's voice against a reference database **without their active involvement** may be "**remote biometric identification**" (Art. 3(41)): **Annex III(1)(a) high-risk** from 2 Dec 2027. Emotion inference from voice at work is **prohibited** (Section 5.1). | High-risk obligations if this applies | — | Classification Med-Low [K]; **counsel needed** |
| **India** | SPDI Rules 2011 define biometrics to include "**voice patterns**" | Written consent; reasonable security; s.43A compensation. DPDP has no special category, but consent or legitimate use is needed. | Compensation; DPDP penalties up to ₹250 crore (security failures) | High [K] |

### 4.3 The open question for PersonaAgent: does diarization create a voiceprint?

- **Diarization** ("Speaker 1 / Speaker 2" within one recording, using temporary embeddings that are not stored and not linked to a name) is the **lowest-risk** form.
- **But** the *Otter* and *Fireflies* plaintiffs plead that speaker recognition creates voiceprints. BIPA's "collect, capture" language may reach even temporary templates.
- **Speaker identification across meetings** (a stored template linked to a name) is **squarely** a voiceprint.
- **The filtering paradox.** A "consent mode" that discards *non-consenting* voices must compute something about those voices to discard them. Counsel needs to decide whether ephemeral, on-device, never-stored embeddings used only to *exclude* a speaker are "biometric identifiers". This is unresolved. [Low-Med]

### 4.4 Recommended "biometric posture" by tier

| Tier | Rule |
|---|---|
| **MVP** | **No voiceprints and no voice enrollment.** Attribute speakers from **Microsoft Teams' own transcript speaker labels** (Teams is the customer's processor for that data) or from the user's manual tags. For in-person capture, use "me vs. others" based on the wearer's microphone channel, with **no stored templates**. Do not build cross-meeting voice profiles. State this publicly; it is a sales and litigation asset. |
| **Enterprise add-on (later)** | Opt-in **voice enrollment** per person, with a BIPA-grade **written release** (e-signature), purpose and term notice, a public retention policy (destroy at the earliest of: purpose met, offboarding, **1 year** (TX) or 3 years (IL)), encrypted templates per tenant, no matching against non-enrolled people, a non-biometric alternative, and per-state enablement. In the EU it is **off** until counsel clears the AI Act and Art. 9 analysis. |

---

## 5. Workplace monitoring and AI regulation

### 5.1 EU AI Act (matters at EU expansion; design for it now)

**Article 5(1)(f): emotion recognition at work. Prohibited since 2 Feb 2025.**
- **Definition (Art. 3(39)).** An "emotion recognition system" is an AI system "for the purpose of identifying or inferring **emotions or intentions** of natural persons **on the basis of their biometric data**". [V]
- **What the Commission guidelines (Feb 2025) say:**
  - Using "webcams and **voice recognition** systems by a call centre to track their **employee's** emotions, such as anger" is prohibited.
  - "AI systems inferring emotions from **written text** and not based on biometric data" are **outside** the prohibition.
  - Tracking **customers'** emotions is outside Art. 5(1)(f), but becomes high-risk under Annex III(1)(c) and needs Art. 50(3) notice.
  - Medical and safety uses are exempt. So is detecting physical states such as fatigue. [V CMS summary of the guidelines]
- **For PersonaAgent:**
  - **Text** tone/style modelling for persona drafting is **not** emotion recognition. [V]
  - **Do not** infer emotions or intentions of employees from **voice** in meetings or in-person capture. Examples to avoid: "Raj sounded frustrated", stress or engagement scores, "sentiment by speaker" from audio prosody.
  - Summaries of what people *said* ("the client said they are unhappy with delivery") are content, not biometric inference. Keep the models working on the **transcript text**, not on acoustic features. [K, Med-High]

**Article 50: transparency, from 2 Aug 2026.** [V artificialintelligenceact.eu; Jones Walker; Cooley]

| Para. | Duty | Applies to us? |
|---|---|---|
| 50(1) | Providers must design systems so people know they are **interacting with an AI**, unless that is obvious | Our UI with our own user: obvious. **If PersonaAgent ever replies autonomously to third parties, they are interacting with an AI.** That is a strong reason to keep v1 human-in-the-loop. |
| 50(2) | Providers of systems generating synthetic **text**, audio, image or video must **mark outputs in a machine-readable format** as AI-generated. *Exception*: "assistive function for standard editing" or output that does "not substantially alter the input data". | Likely **yes** for full-draft generation (beyond "standard editing"). Grace period to **2 Dec 2026** only for systems on the EU market before 2 Aug 2026. A Commission-facilitated **Code of Practice** on marking and labelling was found adequate on 8 Jul 2026. Draft Art. 50 guidelines were consulted on in May–June 2026. |
| 50(3) | Deployers of emotion recognition or biometric categorisation must inform exposed persons | Only if we add such features. Don't. |
| 50(4) | Deepfakes; AI text published to inform the public on matters of public interest (unless there is human editorial control) | Not private email. Relevant to a future **voice clone** (deepfake audio). |

**Digital Omnibus on AI, Regulation (EU) 2026/1744.** Published in the OJ on 24 Jul 2026; in force 27 Jul 2026. [V Cooley]
- Annex III high-risk obligations move to **2 Dec 2027**; Annex I to 2 Aug 2028.
- Art. 50 is unchanged except for the 50(2) grace period above.
- The AI-literacy duty (Art. 4) is softened to Commission and member-state support.

**Annex III point 4: high-risk employment uses** (applies from 2 Dec 2027). [V text]
- Systems "to make decisions affecting terms of work-related relationships, the promotion or termination … to allocate tasks based on individual behaviour or personal traits or characteristics or **to monitor and evaluate the performance and behaviour of persons**".
- **PersonaAgent must not have that intended purpose.** Concretely:
  - no per-employee productivity or behaviour analytics for admins or managers;
  - AUP ban on using memories or transcripts for performance evaluation or discipline;
  - marketing that never claims "insight into your team".
- If a customer repurposes the system, it may become a **provider** of a high-risk system (Art. 25). Employer-deployers of high-risk AI must inform workers' representatives (Art. 26(7)). [K, High]

**Speaker identification** may be "remote biometric identification" (Art. 3(41)); see Section 4. [V definition; classification Med-Low]

### 5.2 Employee-monitoring law outside the US (summary for later markets)

| Jurisdiction | Key rule | Practical consequence |
|---|---|---|
| **Germany** | **BetrVG §87(1) no. 6**: the works council has co-determination rights over introducing and using technical devices "designed" to monitor employee behaviour or performance. The Federal Labour Court (BAG) reads this as *objectively suitable* to monitor, whatever the intent. Plus GDPR, and §26 BDSG (uncertain after CJEU C-34/21, 2023). [K, High] | **A works-council agreement (Betriebsvereinbarung) is effectively a deal prerequisite.** Provide a template annex: purposes, no performance evaluation, access rights, retention. |
| **France** | Labour Code L1222-4 (no undisclosed collection devices) and L2312-38 (consult the CSE before introducing monitoring tools). The CNIL treats permanent call recording at work as disproportionate except in specific cases. The *Amazon* €32M fine is the benchmark. [K, Med-High] | CSE consultation; no default "record everything" |
| **UK** | ICO *Monitoring workers* guidance: DPIA, transparency, proportionality; covert monitoring only exceptionally [K, High] | DPIA template plus a worker notice |
| **India** | No dedicated employee-monitoring statute. Employment contracts and policies, plus the **DPDP s.7(i)** employment legitimate use from May 2027. SPDI Rules apply now for sensitive categories. [K, Med] | Contract clause plus acknowledgement; keep "work-only" scoping |

### 5.3 United States: employee-monitoring and AI-in-employment laws

| Law | Requirement | Applies to PersonaAgent customers? | Conf. |
|---|---|---|---|
| **NY Civil Rights Law §52-c** (since 7 May 2022) | Employers that monitor employees' phone, email or internet use must give **prior written notice on hiring**, get an **acknowledgement** (written or electronic) and **post** a notice. Civil penalties of $500 / $1,000 / $3,000 (AG). | **Yes**: ingesting email and Teams, and recording, are "monitoring". Ship an in-product acknowledgement plus a notice template. | High [K] |
| **Connecticut Gen. Stat. §31-48d** | Prior written notice of the types of electronic monitoring, posted conspicuously; similar penalties | Yes | High [K] |
| **Delaware 19 Del. C. §705** | Notice before monitoring phone, email or internet use: a one-time acknowledged notice or a daily electronic notice; $100 per violation | Yes | High [K] |
| **California CCPA/CPRA (covers employees since 1 Jan 2023)** plus **CPPA regulations** approved by OAL on **22 Sep 2025**, effective **1 Jan 2026** [V CPPA] | **Email contents** = SPI unless the business is the intended recipient [X]. Notice at collection to employees. **ADMT** duties for "significant decisions" (including employment) from **1 Jan 2027**. **Risk assessments** for processing SPI and similar triggers; assessments of pre-2026 processing due by **31 Dec 2027**, with attestations to the CPPA from **Apr 2028**. **Cybersecurity audits** phased **Apr 2028–Apr 2030** by revenue. | Customers (as "businesses") need risk assessments covering PersonaAgent. We must contractually assist as **service provider** (and may need our own assessment for any processing we do as a business). | Dates: effective date [V]; phased dates Med [K] |
| **Colorado SB 26-189** (signed 14 May 2026; replaces the never-effective SB 24-205 AI Act) | ADMT that "materially influences" **consequential decisions, including employment**: pre-use notice, explanation of adverse outcomes within 30 days, correction rights, **meaningful human review**; developer documentation; AG-only enforcement with a 60-day cure period. **Effective 1 Jan 2027.** | Only if PersonaAgent influences employment decisions. The AUP should prohibit that. | High [V Holland & Knight, Baker Botts] |
| **Illinois HB 3773** (Human Rights Act amendment, effective 1 Jan 2026) | No discriminatory AI in employment decisions; **notice** when AI is used for them | Same as above | High [K] |
| **NYC Local Law 144** (AEDT) | Bias audits and notices for automated hiring and promotion tools | No, unless misused | High [K] |
| **Federal preemption push** | A Dec 2025 executive order created an AI Litigation Task Force to challenge "onerous" state AI laws | Watch item; it does not override privacy or wiretap statutes | Med [K] |
| **NLRA** | Employer surveillance of protected concerted activity can be an unfair labor practice. The NLRB General Counsel's 2022 monitoring memo was rescinded in 2025. | Unionised customers: recording may need bargaining. | Med [K] |

**Recommendation.** Ship an **"Employee Notice & Acknowledgement" pack**: a NY/CT/DE-compliant notice text, an in-app acknowledgement with a stored timestamp, and a California notice-at-collection addendum. Make the employer attest during admin onboarding that notices were given.

---

## 6. Data protection for email and Teams ingestion

### 6.1 Roles: customer = controller / Data Fiduciary / business; PersonaAgent = processor

| Activity | Our role | What would turn us into a controller / "third party" (avoid) |
|---|---|---|
| Ingesting a user's sent mail and Teams messages; building the persona and memory; drafting | **Processor** (GDPR), **service provider** (CCPA), **Data Processor** (DPDP) acting on the customer's documented instructions | Training or fine-tuning *shared* models on customer content. Cross-tenant "benchmarks". Using content for marketing. Selling or sharing. Human review without instruction. Keeping data after termination. Under CCPA, combining data across customers except for permitted business purposes. [K, High] |
| Service telemetry (counts, latency, errors), billing, security logs | Controller for our own business purposes (permitted) | Keep telemetry content-free: no message text, no transcripts |
| Consumer sign-ups (no tenant) | Would make us a **controller** | **Not in v1.** Block personal Microsoft accounts and "free" self-serve. |
| Anthropic (via Amazon Bedrock), STT vendors, AWS | **Sub-processors** | On Bedrock, AWS states that prompts and outputs are not shared with model providers or used to train base models [K, High; confirm against current AWS terms]. Need DPAs and sub-processor notice with an objection right. |

**Lesson from Section 3.** The processor position is a **legal defence against wiretap claims**, not just a contract label. A processor with no independent use fits the "extension of the user" theory. Both *Otter* and *Granola* turn on alleged training and use by default. **Hard-code "no training on customer data"**: no code path, an audit log, and a public trust-centre statement.

### 6.2 Lawful basis for third parties' data inside email, chat and recordings

| Jurisdiction | Employees of the customer | External people (recipients, meeting guests) |
|---|---|---|
| **EU/UK (later)** | Controller's legitimate interests (Art. 6(1)(f)) with a documented balancing test. Consent is not suitable. | Legitimate interests. **Art. 14** notice for data *not* obtained from the person (email recipients); the "disproportionate effort" exemption (Art. 14(5)(b)) may apply to mail archives. **Art. 13** notice at the point of capture for **meeting recordings** (an announcement plus a link). Right to object (Art. 21). [K, High] |
| **US** | CCPA notice at collection (CA). NY/CT/DE monitoring notices. Otherwise contract and policy. | CCPA applies to B2B contacts (the B2B exemption expired 1 Jan 2023); the customer's privacy notice should mention AI assistants. Recording consent rules as in Section 2. [K, High] |
| **India** | DPDP s.7(i) employment legitimate use (from May 2027). SPDI written consent now for SPDI categories. | **Hardest case.** Under DPDP, a *new purpose* (persona learning) applied to an outsider's data in old emails is not obviously covered by consent or s.7(a). **Mitigate by design**: learn *style* from the **user's own text**; strip or tokenize third-party identifiers before storage; keep no third-party profiles in memory unless the user explicitly saves a fact. **Counsel needed.** [K, Med] |

### 6.3 Minimisation and purpose limitation (product requirements)

- Ingest **only the user's own authored content** (Sent Items, the user's Teams posts), plus the **minimum quoted context** needed to classify the thread type and recipient relationship. Do not ingest whole mailboxes, attachments by default, or other people's chats.
- **Respect Microsoft Purview sensitivity and retention labels.** Exclude "Highly Confidential", "Privileged", "HR" and "Medical" labels and folders by default. Tenant admins can add exclusions such as legal and HR distribution lists or external domains.
- **Store derivatives, not raw content, by default** [X planned]: style features, redacted snippets, and memories with provenance links back to M365, not copies. An optional encrypted raw vault is an Enterprise feature.
- **Mask regulated identifiers at ingestion** (Section 11).
- Treat the "relationship graph" (manager, junior, client) as personal data. It reveals reporting lines and client relationships. Admin-visible only in aggregate. **Never expose individual persona or memory content to admins** except under the legal-hold/eDiscovery process.

### 6.4 DPIA and risk-assessment expectations

- **GDPR Art. 35**: a DPIA is effectively **mandatory** here: systematic monitoring, employees, new technology, large-scale communications, possibly biometrics. UK ICO likewise.
- **California**: CPPA risk assessments (Section 5.3).
- **India**: Significant Data Fiduciaries need a **DPIA plus audit every 12 months** [V DLA Piper]. Large Indian BFSI and telecom customers may be designated SDFs and will flow this down to us.
- **Deliverable**: a customer-facing **DPIA template** pre-filled with our processing description (Section 13.3).

### 6.5 Cross-border transfers and data residency

| Flow | Mechanism | Status / notes | Conf. |
|---|---|---|---|
| EU/UK → US | **EU-US Data Privacy Framework** (self-certify), or **SCCs (2021/914)** plus a transfer impact assessment; UK Extension / IDTA | DPF upheld by the EU General Court in *Latombe v Commission* (T-553/23, 3 Sep 2025); an appeal to the CJEU is reported pending. Keep SCCs as a fallback. | High (GC ruling) [K]; Med (appeal) [K] |
| India → anywhere | **DPDP s.16**: transfers allowed **except** to countries the government blacklists (no list known to be notified). DPDP Rules let the government impose requirements on making data available to foreign states. Until May 2027, **SPDI Rule 7** applies: transfer only where the recipient ensures the same level of protection *and* it is necessary for a contract or consented to. | No general localisation duty for us or most customers | Med-High [V DLA Piper; K] |
| India (regulated customers) | **Sector mandates**: RBI payment-system data stored only in India; SEBI CSCRF and cloud framework (regulated-entity data and logs within India); IRDAI (insurance records in India) | **Legal mandate for those customers**; see Section 7.2 | Med-High [K] |
| India (SDF-specified data) | DPDP Rules: an SDF must ensure **specified** personal data and its traffic data are **not transferred outside India** | Only once the government "specifies" data; watch item | High (rule) [V]; nothing specified yet [K, Med] |
| US data → countries of concern | **DOJ "bulk sensitive data" rule** (28 CFR Part 202, in force 8 Apr 2025) restricts access by China, Russia, Iran, North Korea, Cuba, Venezuela and covered persons, including vendor and employee access | **India is not a country of concern.** Ensure no engineer or vendor access from countries of concern. | High [K] |

**Answer to the cross-track question (in-India LLM inference):**
- **For most Indian customers, in-India inference is a contractual and commercial expectation, not a legal requirement.** DPDP permits transfers unless the destination is blacklisted.
- **It becomes a legal requirement** in three cases:
  - **RBI** payment-system operators and their service providers, for payment data;
  - **SEBI** regulated entities under the CSCRF/cloud framework;
  - **IRDAI** insurers, for records.
- It may also arise later for SDF-specified data.
- **Recommendation.** India tenants are stored in AWS Mumbai by default. Offer an **"India-only processing" tenant flag** that restricts inference to in-region models (Haiku 4.5 / Opus 5 per the AWS track [X]) and keeps logs in India (CERT-In). Make it **mandatory for BFSI tenants**. [Med]

### 6.6 Retention defaults (proposed)

| Data | Default | Why |
|---|---|---|
| Raw meeting or in-person audio | **Not stored** (stream → transcript → discard) | Reduces wiretap, biometric and breach exposure |
| Raw transcripts | 30 days (tenant-configurable 0–365) | Lets users fix errors; limits exposure |
| Summaries, memories, persona features | Until the user deletes them, or offboarding + 30 days | User control; Microsoft API terms require deletion on abandonment [V] |
| Source mirrors | **Track source deletions**: if a mail is deleted in M365, delete derived items | Microsoft API Terms §5(b) require keeping data up to date, "including deletion" [V] |
| Security and audit logs | ≥ **1 year** (DPDP Rules) and **180 days kept in India** (CERT-In) for India tenants | [V] |
| Legal hold | Overrides **all** deletion, including crypto-shredding | Spoliation risk (Section 7.4) |

### 6.7 Data-subject rights, including non-users

- **Non-users have rights too.** A client in a recording, or an email recipient, can ask the *customer* (controller) for access or erasure: GDPR Arts 15–17, DPDP ss.11–13, CCPA.
- **Required tooling**: search by name, email address or phone number across transcripts, memories and persona artefacts. Support export and redaction or erasure, and keep an audit trail. Do not use voice search; that is biometric.
- **Why no training matters for deletion.** Fine-tuning on content creates deletion and "unlearning" problems. Keep the persona as **retrieval plus compact, deletable style descriptors**. The *Granola* complaint explicitly attacks data that "cannot be cleanly extracted or deleted" once trained into models. [V secondary]
- **India specifics**: grievance-redressal contact; the right to nominate; rights notices in Eighth Schedule languages on request. [K, Med]

### 6.8 Microsoft platform terms that work like law for Pillar 1 [V Microsoft APIs Terms of Use, Oct 2025]

1. **§3(c): email APIs** may be used only to sync or back up mail, calendar and contacts, "unless you have use permissions **expressly and specifically granted by Customers** in connection with using your Application". **Persona learning needs an explicit customer grant** in the order form, admin consent screen and DPA.
2. **§3(b)(4)–(5)**: no copies or databases "except as necessary to enable an intended usage scenario"; request the **minimum** data and permissions.
3. **§3(b)(11)–(12)**: no use outside the permissions customers granted. **No advertising or marketing use** of API data, including derived or anonymised data.
4. **§5**: comply with privacy, **biometric** and **confidentiality-of-communications** laws.
   - Obtain all necessary consents.
   - **Reflect source corrections and deletions.**
   - Delete everything when the user abandons the app or closes the account.
   - Keep a privacy statement **at least as protective as Microsoft's**.
   - Link to the Microsoft consent-revocation pages.
5. **§4**: security warranty. Report breaches to MSRC; no public statements about API-related breaches without permission. Microsoft has **audit rights**, including up to two full-featured test instances.
6. **§10(b)**: on termination, follow the customer's instruction to return or delete data.
7. [X] Microsoft's managed default consent policy (late 2025) blocks *user* consent to scopes like Mail.Read and Chat.Read, so **tenant-admin consent is required**. Treat this as an advantage: the admin consent flow is where the "express and specific grant" is captured.

---

## 7. Sector rules

### 7.1 Healthcare

| Rule | Implication | Conf. |
|---|---|---|
| **HIPAA** (US) | If a covered entity or business associate puts PHI into email, Teams or recordings, **we are a business associate**: a BAA is required, and we flow it down to sub-processors. Amazon Bedrock is HIPAA-eligible under the AWS BAA [K, High]. STT vendors must sign BAAs too. Safe Harbor's 18 identifiers include **voice prints** [X], so audio cannot be "de-identified" by Safe Harbor while the voice remains. | High |
| HIPAA Security Rule update | NPRM of Jan 2025 (mandatory encryption, MFA, asset inventories); final status not verified | Med [K] |
| **42 CFR Part 2** (substance-use-disorder records) | 2024 final rule, with compliance by Feb 2026 | Med-High [K] |
| **California CMIA** | *Saucedo v. Sharp* (Section 3) pairs CMIA with CIPA for ambient recording | Med-High [V] |
| **California AB 3030** (from 1 Jan 2025) | Generative-AI patient communications with clinical information need an AI disclaimer **unless a licensed provider reads and reviews them**. Our human-send design helps. | Med-High [K] |
| **India** | Health data = SPDI (written consent, security). Telemedicine Practice Guidelines 2020 and ABDM policies apply to health customers. | Med [K] |

**MVP stance:** **no healthcare tenants** (or "BAA-ready" with clinical capture disabled) until we have a BAA, a patient-consent flow and per-state review.

### 7.2 Financial services

**US**

| Rule | What it means for transcripts, summaries and drafts | Conf. |
|---|---|---|
| **SEA Rule 17a-4(b)(4)** (broker-dealers): keep communications "relating to its business as such" (3 years). **17a-4(f)** electronic-storage standard. **FINRA Rule 4511**; **Rule 3110(b)(4)** review of correspondence. **Advisers Act Rule 204-2** (advisers: 5 years). | **Sent** AI-drafted emails and Teams messages are communications. Because we send them through Outlook/Teams, they land in the firm's existing archive, which is good. **Transcripts and summaries that are distributed or used in the business are likely records.** In-person recordings of client conversations are a grey area. Under **CFTC Rule 1.35**, FCMs and swap dealers must **record and retain oral communications** leading to trades. | High (rules) [K]; Med (application) |
| **FINRA Regulatory Notice 24-09** (27 Jun 2024) | FINRA rules are technology-neutral. "The content standards of Rule 2210 … apply whether member firms' communications are generated by a human or technology tool." | High [V] |
| **FINRA 2026 Oversight Report (GenAI section)** | Summarisation is the top GenAI use case. Firms should consider "storing prompt and output logs for accountability … tracking which model version was used". Human-in-the-loop for AI agents. | High [V] |
| **SEC/CFTC off-channel sweep** | Since late 2021, more than $2B in combined penalties [K, Med-High]. On **13 Jan 2025** another 12 firms paid **$63.1M** [V]. 2025–26 enforcement intensity under new SEC leadership is unverified, but **the rule has not changed.** | — |
| **SEC Reg S-P amendments** (2024) | **Service providers must notify the covered institution within 72 hours** of a breach; customer notice within 30 days. Compliance Dec 2025 (large) / Jun 2026 (small). | High [K] |
| **GLBA Safeguards Rule** (FTC; non-bank financial institutions) | Service-provider oversight, encryption, MFA, disposal within 2 years. **FTC notice within 30 days** for incidents affecting ≥500 consumers (since 13 May 2024). | High [K] |
| **Bank incident rule** (OCC/Fed/FDIC) | **Bank service providers must notify the bank as soon as possible** when an incident disrupts covered services for 4+ hours (36-hour rule for banks) | High [K] |

**Product implications for FS tenants:**
- A **"regulated recordkeeping" mode**: journal transcripts, summaries and AI drafts to the firm's archive (Purview, Smarsh, Global Relay) or keep them in WORM storage.
- No auto-delete while that mode is on.
- Prompt and output logs with the model version.
- Supervision export.
- **Default in-person capture OFF** for registered representatives.

**India**

| Regulator | Rule | Implication | Conf. |
|---|---|---|---|
| **RBI** | **Storage of Payment System Data** (RBI/2017-18/153, **6 Apr 2018**): "the entire data relating to payment systems … stored in a system only in India", including "full end-to-end transaction details". Applies to system providers *and* their service providers and vendors. | Payment-operator tenants: India-only storage and processing for payment data. Plus **masking of card and account data** at ingestion. | High [V] |
| RBI | **Card-on-file storage ban / tokenisation** (CoFT circulars 2021–22; merchants and PAs barred from storing card data from 1 Oct 2022) | Never store full card numbers (Section 11) | High [K] |
| RBI | **Master Direction on Outsourcing of IT Services** (Apr 2023; from 1 Oct 2023): audit and inspection rights for RBI, data confidentiality, location visibility, incident reporting, BCP. **IT Governance Master Direction** (from Apr 2024). Banks report cyber incidents to RBI within 6 hours. | Contract annex for bank and NBFC tenants | Med-High [K] |
| **SEBI** | **CSCRF** (SEBI/HO/ITD-1/ITD_CSC_EXT/P/CIR/2024/113, **20 Aug 2024**) [V]. Plus SEBI's **cloud framework** (2023): regulated entities must keep data and logs within India's legal boundaries; incident reporting; audit rights. | Broker/AMC tenants: India-only processing mode; log localisation | Circular [V]; localisation details Med [K] |
| **IRDAI** | Information & Cyber Security Guidelines (2023); Maintenance of Insurance Records Regulations (records in data centres in India) | Insurer tenants: India-only mode | Med [K] |

### 7.3 Legal profession and privilege

- **ABA Formal Opinion 512** (29 Jul 2024): lawyers using generative AI must meet duties of competence and **confidentiality**. Informed client consent is needed before inputting client information into self-learning tools. Duties of communication, supervision and reasonable fees also apply. [K, High]
- **Privilege risk:**
  1. A third-party AI vendor that **retains or uses** content for its own purposes weakens the "necessary agent" argument against waiver.
  2. Summaries of privileged meetings are new documents that may be discoverable if privilege fails.
  3. A widely reported Feb 2026 S.D.N.Y. ruling (*United States v. Heppner*, Judge Rakoff) held that a defendant's own exchanges with a public AI chatbot were **not** privileged or work product. [K, Med; **not verified this session**]
- **India**: professional-communication privilege now sits in the **Bharatiya Sakshya Adhiniyam 2023** (formerly Evidence Act ss.126–129). [K, High]
- **Product:**
  - **"Privileged / legal" meeting mode**: auto-detect meetings with counsel domains or labels, **never record**, and require explicit override with confirmation.
  - Admin rules by domain (outside counsel).
  - Persona ingestion **excludes** privileged labels and folders.

### 7.4 eDiscovery, legal hold and spoliation

- Transcripts, summaries, memories and persona artefacts are **ESI**: discoverable under FRCP 26/34. **FRCP 37(e)** sanctions apply for failure to take reasonable steps to preserve ESI, including adverse inferences on intent to deprive. [K, High]
- Courts have ordered **AI providers to preserve output logs** (*In re OpenAI* copyright litigation, May 2025, later narrowed) [K, Med-High]. Courts have also sanctioned auto-deleting chat (*Epic v. Google*, 2023). [K, High]
- **Requirements:**
  - **Legal-hold API and UI** per custodian or tenant that **suspends all deletion, including crypto-shredding, TTL expiry and user-initiated delete** (users see "held").
  - Export with metadata: source, timestamps, model version, AI-generated flag.
  - Ideally **write summaries back into M365** (mailbox or OneDrive) so the customer's Purview retention and eDiscovery apply natively.
  - Label AI outputs as AI-generated, with links to the source transcript. Accuracy disputes are foreseeable.

### 7.5 Public sector

- **US**: FedRAMP / StateRAMP / CJIS. State public-records and open-meetings laws can make AI transcripts public records. [K, High]
- **India**: MeitY cloud empanelment, in-country data, STQC audits. [K, Med]
- **Recommendation**: **exclude public-sector tenants from v1.**

---

## 8. AI-generated communications, personas and impersonation

### 8.1 Must an AI-drafted message say it is AI-generated?

| Law | Scope | Applies to PersonaAgent? | Conf. |
|---|---|---|---|
| **California SB 1001** (B&P Code §§17940–17943, since Jul 2019) | Unlawful to use a **"bot"** (an automated online account whose actions are substantially not the result of a person) to communicate with a person in California **with intent to mislead** about its artificial identity, either to **incentivise a sale** or to **influence a vote**. Clear disclosure is a safe harbour. | **No** for human-reviewed, human-sent drafts. **Yes, risk** if we add **autonomous replies** in sales or customer contexts. | High [K] |
| **Utah AI Policy Act** (2024, amended 2025) | Disclose generative-AI interaction **when asked** in consumer transactions; proactive disclosure in high-risk interactions within regulated occupations | Only for autonomous agents talking to consumers | Med [K] |
| **Colorado SB 26-189** (from 1 Jan 2027) | Notices where ADMT materially influences consequential decisions; reported duty to notify consumers interacting with AI in covered contexts | Only if used in consequential decisions | Med [V summaries] |
| **Maine 2025 chatbot law** | Disclosure when AI chatbots in trade could mislead consumers into thinking they are human | Autonomous agents only | Low-Med [K] |
| **California AI Transparency Act (SB 942, as amended)** | Large GenAI providers (>1M monthly users) of **image, video, audio**: latent disclosures and detection tools; operative date reportedly 2 Aug 2026 | **Not text.** Relevant to a future **voice clone**. | Med [K] |
| **EU AI Act Art. 50(1)/(2)** | Interaction disclosure; machine-readable marking of synthetic text | See Section 5.1 | High [V] |
| **FTC Act §5 / state UDAP laws** | Deception: AI-written messages that misrepresent facts or the sender's identity | Misuse risk | High [K] |
| **India: IT Act s.66D**; **BNS 2023 s.319** (cheating by personation) | Criminal liability for impersonation using a computer resource | Misuse risk | High [K] |
| **India: IT Rules amendments on "synthetically generated information"** | Draft Oct 2025, aimed at intermediaries and mainly audio-visual content; final form and scope not verified | Watch item (voice clone) | Low-Med [K] |

**Conclusion.** In the **US and India, no law currently requires labelling a human-reviewed, human-sent email that was drafted with AI.** [Med-High] Plan anyway for:
- (a) an invisible **machine-readable marker**, such as an `X-AI-Assisted` MIME header or message property, which the EU will expect;
- (b) a **tenant-configurable visible disclosure** (some customers will want it; Teams Store rules require AI disclaimers in the app UI, Section 9);
- (c) **no autonomous sending in v1.**

### 8.2 Digital-replica and impersonation laws: text persona now, voice clone later

| Law | What it protects | Text persona (v1) | Voice clone (future) | Conf. |
|---|---|---|---|---|
| **Tennessee ELVIS Act** (from 1 Jul 2024) | Voice and likeness. Liability also for distributing tools whose **primary purpose** is producing an individual's voice without authorisation. | Low | **High.** Need written authorisation from the voice owner; never clone third parties. | High [K] |
| **NO FAKES Act** (federal; reintroduced Apr 2025) | A federal right over digital replicas of voice and visual likeness | — | High if enacted. **Enactment not verified; believed pending.** | Med [K] |
| **California** Civ. Code §3344 (publicity); **AB 2602** (digital-replica contract terms, from 2025); AB 1836 (deceased persons) | Commercial use of name, voice or likeness; contract terms for replicas | Low (no advertising use) | High | High [K] |
| **New York** Civil Rights Law §§50–51; 2024–25 digital-replica laws | Use of name, portrait or voice for trade; digital-replica contracts and ad disclosures | Low | High | Med-High [K] |
| **Illinois** Right of Publicity Act amendments and Digital Voice & Likeness Protection Act (2024) | Digital replicas | Low | High | Med [K] |
| **India: personality rights** (Delhi and Bombay HC injunctions against AI voice and likeness misuse for celebrities, 2022–2024) | Name, voice, likeness | Low | High | Med-High [K] |
| **FTC Impersonation Rule** (16 CFR 461, in force Apr 2024 for government and business impersonation). A 2024 proposal would extend it to **individuals** and to **"means and instrumentalities"** (AI tool providers). | Impersonation fraud | **Medium.** A persona tool sold without misuse controls is the target of the proposed extension (status not verified). | Med | Med [K] |

### 8.3 Fraud and misuse: the persona is an impersonation kit [X]

A persona plus memory (style, relationships, current deals) is close to a perfect **business-email-compromise kit**. Other tracks note that 50–100 emails are enough to mimic a person's style. [X]

**Legal exposure:**
- primary liability falls on the customer and the fraudster;
- we face secondary exposure through negligence, UDAP and the proposed FTC "means and instrumentalities" theory;
- contract claims if our controls are weak.

**Required guardrails:**
1. **A persona is usable only by the person it models.** No "act as" another user. No admin impersonation. No persona sharing, export or download.
2. Generation is bound to the user's own Entra ID session with **phishing-resistant MFA and Conditional Access**. Re-authenticate for high-risk actions, such as drafts that contain payment or bank-detail changes.
3. **Drafts go only into the user's own compose window.** v1 has **no autonomous send**.
4. **Payment-instruction guard.** Warn when a draft adds or changes bank details or wire instructions, and never auto-fill them from memory.
5. Audit log of every generation (user, time, prompt hash, output hash, model version); rate limits; anomaly detection.
6. AUP bans generating content to deceive, harass, defame, impersonate others, or evade monitoring.

### 8.4 Who owns the persona, and what happens when the employee leaves?

- **Business records** (sent mail, meeting summaries shared with the team) belong to the **employer**: work made for hire and employer records. [K, High]
- **The persona itself** (a model of a person's writing style, preferences and private memories) is **the employee's personal data** under GDPR, CCPA and DPDP. It also touches **name and voice publicity rights**, which stay with the individual. [K, High]
  - The employer is the controller.
  - The employee keeps access and erasure rights, subject to employer exceptions.
  - Under DPDP, the employment legitimate use ends with employment, apart from record-keeping.
- **Using an ex-employee's persona to keep writing "as" them** would be **deceptive** (FTC Act / UDAP, misrepresentation), unfair under GDPR, and potentially a publicity-rights violation. [K, Med-High]

**Recommended offboarding policy (contract plus product):**

| Data | On departure (Entra ID account disabled or deleted, detected by change notification) | Then |
|---|---|---|
| Persona style model / descriptors | **Frozen immediately** (no generation) | **Deleted after 30 days** (configurable 0–90) unless under legal hold |
| Personal memories (private notes, in-person captures) | Frozen; hidden from everyone | Deleted after the same window unless on hold |
| Team knowledge (summaries already shared to channels or mail) | Stays in M365 under the customer's retention | Customer-governed |
| Successor hand-over | **Allowed only for team knowledge**, never for persona or style | — |

**State this split in the ToS, DPA and admin UI**: "Team knowledge belongs to the organisation; a person's persona is never transferable."

### 8.5 Name / trademark

"PersonaAgent" is reportedly also the name of an **ACL 2026 research framework**. [X] Run a **trademark clearance** before public launch (USPTO, the Indian Trade Marks Registry, EUIPO/UKIPO) and check domain and app-store name conflicts. **Counsel needed.**

---

## 9. Platform policies

### 9.1 Microsoft (the most important platform for us)

| Rule | Requirement | Product consequence | Conf. |
|---|---|---|---|
| **Graph Cloud Communications: media access restriction** | "You may NOT use the Media Access API to record or otherwise persist media content from calls or meetings … **or data derived from that media content** … without first calling the **updateRecordingStatus** API to indicate that recording has begun, and receiving a success reply." The API "requires the use of the Teams policy-based recording solution." | Any bot that turns live Teams media into **transcripts or summaries** must **signal recording**, which triggers Teams' recording notice. **No silent bot transcription.** | High [V Microsoft Learn] |
| **Application-hosted media bots** | Production media bots "must be deployed on a Windows Server guest OS **in Azure**" (C#/.NET) | A real-time media bot cannot run purely on AWS. This is a **platform constraint and a sub-processor (Azure) implication** for the DPA. | High [V] |
| **Microsoft APIs Terms of Use (Oct 2025)** | Email-API purpose limit; minimum data; no copies beyond the intended scenario; no advertising use; reflect deletions; delete on abandonment; comply with **biometric** and **confidentiality-of-communications** laws; MSRC breach notice; Microsoft audit rights | Section 6.8 | High [V] |
| **Teams Store validation guidelines** (apps with generative AI) | **Must fix**: "The AI disclaimer must be clearly visible in the UI where users interact with generative AI content." Users need a mechanism to **report inappropriate AI content**, and reports must be acted on in time. Privacy-policy and terms-of-use links must be public, HTTPS, on our domain, and identical in the manifest and AppSource. | AI disclaimer in the compose pane; "Report output" button; public legal pages | High [V] |
| **Teams external-bot detection** | Microsoft **MC1251206** (13 Mar 2026): Teams labels external meeting bots **"Unverified"** in the lobby, and the organiser must admit them; on by default, GA Jun–Oct 2026 | Do not rely on bots in **other companies'** meetings. Prefer Microsoft's own transcript or recording artefacts for internal meetings. | High [X] |
| **Admin consent** | The managed default consent policy blocks user consent to Mail.Read and Chat.Read | The admin onboarding flow is mandatory; capture the "express and specific" grant there | High [X] |
| **Teams "explicit recording consent"** policy | Admins can require participants to consent before their audio, video or screen is included in recordings and transcripts | If customers enable it, **our capture must honour it.** Do not route around it with device-audio capture. | Med [K]; Microsoft Learn page moved (404) |
| **Microsoft 365 App Compliance** (Publisher Attestation / Microsoft 365 Certification) | Security and privacy attestation programme for Teams and M365 apps | Enterprise buyers ask for it; plan Publisher Attestation at launch and Certification within 6–12 months | High [K] |

### 9.2 Apple (phone app)

- **Guideline 2.5.14**: "Apps must request **explicit user consent** and provide a **clear visual and/or audible indication** when recording, logging, or otherwise making a record of user activity. This includes any use of the device camera, **microphone**…" [V]
- **Guideline 5.1.2(i)**: "You must clearly disclose where personal data will be shared with third parties, **including with third-party AI**, and obtain explicit permission before doing so." [V] Name Anthropic/Bedrock and the STT vendor in the in-app consent.
- **Guideline 2.5.4**: background services only for their intended purposes (audio and so on). [V] **Always-on background recording** gets App Review scrutiny. Use the background-audio mode with a visible Live Activity or recording indicator. iOS also shows its own microphone indicator. [K, High]
- iOS gives apps **no access to cellular call audio**. Phone-call capture is not feasible on iPhone. [K, High]

### 9.3 Google Play / Android

- **Malware policy: spyware.** "Recording audio or recording calls made to the phone" without adequate notice or consent is a spyware violation. [V]
- **Stalkerware.** Monitoring apps are permitted only for parental or **enterprise employee** oversight. They "must present users with a **persistent notification** at all times when the app is running and a unique icon". They may not present as secret surveillance. Monitoring features must be disclosed in the listing. [V]
- **Android platform.** Microphone use in the background needs a declared `microphone` foreground-service type and a persistent notification. A microphone foreground service cannot start from the background. Play requires declaring foreground-service types. Call recording through Accessibility APIs is banned. [K, High]

### 9.4 Zoom and Google Meet (later)

- **Google Meet Media API**:
  - "no longer accepting new signups";
  - host or organiser consent through an initiation dialog;
  - "anyone can stop the Meet Media API during the call";
  - connections are rejected when underage accounts are present or the meeting is encrypted or watermarked. [V]
- **Zoom**: Marketplace review; recording and "AI" indicators shown to participants. Real-Time Media Streams (2025) gives approved apps media with host/admin approval. **Details not verified** this session. [K, Med]

**Platform takeaway.** Every major platform now requires **visible indicators and consent** for recording. Silent capture is a legal risk *and* grounds for **delisting or API termination**. Microsoft can terminate API access "in its sole discretion" (ToU §10). [V]

---

## 10. Consent UX: what competitors do and recommended patterns

### 10.1 What others do (vendor behaviour; mostly [K] or [X]; verify before citing externally)

| Product | Capture model | Consent and notice mechanics | Lesson |
|---|---|---|---|
| **Microsoft Teams** (native) | Recording and transcription by Microsoft | Banner shown to **all** participants with a privacy link; an admin "explicit recording consent" policy; Copilot can run without keeping a transcript [K, Med] | Using Teams' own artefacts lets Microsoft's notice do the work [X] |
| **Zoom / Google Meet** | Native recording, AI Companion, Gemini notes | Pop-up "this meeting is being recorded" consent; persistent icons [K, Med-High]. Meet Media API needs host consent, and anyone can stop it [V] | Industry norm = **persistent, visible indicator plus a consent prompt** |
| **Otter** | Auto-joining bot (OtterPilot) from the calendar; post-meeting summaries emailed | Notice mostly to the host [V complaint allegations] | **Sued.** Auto-join plus host-only consent plus training |
| **Fireflies** | Visible bot | Bot name visible; speaker recognition [V complaint] | **Sued under BIPA** for speaker recognition |
| **Granola** | **Bot-free** device audio (microphone plus system output) | User's responsibility [V complaint] | **Sued.** Bot-free = "hidden" in the plaintiffs' framing |
| **Read.ai** | Visible bot | Recording notice; participants can opt out [K, Low-Med] | Opt-out commands are a good pattern |
| **Limitless** (Meta, Dec 2025) | Pendant | **"Consent mode"**: keeps the wearer's voice and only the voices of people who consented [K, Med]. Capture products wound down after the acquisition [X]. | Good concept, but it relies on voice recognition (biometric tension) |
| **Bee** (Amazon, Jul 2025) | Wristband / clip | **Button press**, **green LED** while capturing; audio "not saved, stored, or used for AI training" [X] | Visible, press-to-capture, no stored audio |
| **Plaud** | Recorder / card | Physical switch; consent is the user's responsibility [K, Low] | Hardware switch = clear user intent, but **no bystander protection** |

### 10.2 Recommended consent UX for PersonaAgent

**Principles:**
- **Visible, prior, persistent, reversible, logged.**
- **Strict by default; relaxed only by the admin, per jurisdiction, with a record.**

1. **Indicators.**
   - Desktop: a persistent "PersonaAgent is capturing" pill.
   - Phone: Live Activity / persistent notification (Android requires one).
   - Wearable (later): a hardware LED that cannot be disabled in firmware, plus a physical mute.
   - Teams: Microsoft's banner, via Microsoft transcripts or `updateRecordingStatus`.
2. **Announcement at start.**
   - Teams: a chat card ("Notes are being taken for [user] by PersonaAgent. [What this means] [Don't capture me] [Stop]").
   - Calls and in-person (all-party mode): a spoken TTS line. This matches Washington's "announced and recorded" model.
   - Repeat the reminder when new people join.
3. **External meetings OFF by default** [X]. Users opt in per meeting. The announcement is mandatory.
4. **Consent ledger.** For every session, store who was notified, how, when, any objections and the actions taken. It is evidence for litigation, and customers can export it.
5. **Bystander protection (in-person).**
   - "Wearer-only" default: drop non-wearer audio **on the device** before upload, using no biometric templates.
   - Auto-pause on calendar tags (HR, legal, medical, interview, 1:1-personal) and location zones (restrooms, clinics, reception, other companies' premises).
   - Pause on spoken cues ("off the record", "please don't record").
6. **Hard blocks.** No capture of minors' settings, healthcare encounters (unless the HIPAA tier is on), privileged meetings or public-sector meetings. No capture when the device is outside configured work hours or locations.
7. **User controls.** "Forget the last 5 min / this meeting / today". Search and delete across memories. Export.
8. **Third-party request portal.** A public page: "Were you recorded or mentioned by someone using PersonaAgent?" It routes requests to the right tenant (controller) without revealing tenant data. It supports DSAR obligations under GDPR, CCPA and DPDP.
9. **Admin policy set.** Features per group or region; external-meeting policy; retention; India-only processing; regulated-recordkeeping mode; legal hold; consent-mode enforcement; an audit-log export.
10. **No dark patterns.** Declining capture must be as easy as accepting (DPDP: withdrawal as easy as giving consent; FTC dark-patterns enforcement). [K, High]

---

## 11. Phase-1 redaction map: US + India

This section turns US and Indian rules into **implementable treatments** for the Phase-1 redaction engine. It uses the security track's tiers (doc 10) [X]:
- **Tier-R**: regulated identifiers and secrets, irreversibly masked at first touch;
- **Tier-P**: personal identifiers, consistent reversible tokens;
- **Tier-S**: special-category content, live context only and excluded from long-term memory;
- **Tier-C**: company-sensitive, per tenant policy.

The **"legal requirement"** column is what the law demands. The **"treatment"** column is our (stricter) product rule.

### 11.1 Treatment vocabulary

| Code | Meaning |
|---|---|
| **MASK-X** | Irreversible mask **at ingestion, before any persistence, logging, embedding or LLM call**. Keep a typed placeholder and at most the last 4 characters (`⟦SSN:***-**-1234⟧`). |
| **DELETE** | Remove the value entirely. Do not even keep the last 4. |
| **TOKENIZE** | Consistent, reversible token held in a per-tenant vault. Re-hydrate only for the entitled user at display time. FF1 format-preserving encryption is allowed; FF3/FF3-1 is withdrawn by NIST. [X] |
| **ENCRYPT** | Field- or object-level encryption with per-tenant / per-user keys (enables crypto-shredding) |
| **MINIMIZE** | Do not collect or derive; process on device; generalise (for example GPS → city) |
| **EXCLUDE** | Skip the whole message or segment from ingestion; notify the admin if policy requires |
| **LOCALIZE** | Store and process in India (AWS Mumbai/Hyderabad); keep an India copy of logs |
| **RETAIN(n)** | Minimum retention (logs, regulated records); legal hold overrides deletion |

### 11.2 United States: data element → regime → required treatment

| # | Data element | Regime(s) | What the law requires | PersonaAgent treatment | Tier | Detection hints |
|---|---|---|---|---|---|---|
| U1 | **SSN** | State SSN-protection laws (e.g., Cal. Civ. Code §1798.85: no public display, no unencrypted internet transmission); all state breach laws; CCPA SPI; HIPAA identifier (G); GLBA NPI in a financial context | Limit display and transmission; protect; breach notice if acquired unencrypted with a name | **MASK-X** (last 4) | R | `\b(?!000|666|9\d\d)\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b` plus context ("SSN", "social security"); exclude ITIN ranges |
| U2 | **ITIN / taxpayer ID** | Breach laws (e.g., CA lists "tax identification number"); IRS confidentiality | As U1 | **MASK-X** | R | `9\d{2}-?(5\d|6[0-5]|7\d|8[0-8]|9[0-2]|9[4-9])-?\d{4}` |
| U3 | **Driver's licence / state ID** | Breach laws; CCPA SPI; HIPAA (K) | Protect; breach notice | **MASK-X** | R | Per-state formats plus context ("DL", "license #") |
| U4 | **Passport number** | Breach laws (many states); CCPA SPI | Protect | **MASK-X** | R | 9 digits, or letter + 8 digits, plus context "passport" |
| U5 | **Payment card PAN** | **PCI DSS v4.0.1**: Req. 3.4.1 (mask when displayed, at most BIN + last 4); Req. 3.5.1 (unreadable wherever stored); Req. 12.10.7 (incident procedure if PAN is found where it is not expected). Breach laws (card + code); CCPA SPI; GLBA | Never keep a clear PAN in storage or logs | **MASK-X at first touch** (last 4). Never in prompts, vectors or logs. A QSA should confirm that transient in-memory handling keeps us out of scope [X]. | R | 13–19 digits, **Luhn** check, IIN ranges (Visa 4; MC 51–55 / 2221–2720; Amex 34/37; Discover 6011/65/644–649; RuPay 60/65/81/82/508) |
| U6 | **CVV/CVC/CID, PIN / PIN block, full track or chip data** (sensitive authentication data) | **PCI DSS Req. 3.3.1**: SAD **must not be stored after authorisation, even encrypted** | Never store | **DELETE** | R | 3–4 digits next to "CVV/CVC/CID/security code"; track patterns `%B\d{13,19}\^`, `;\d{13,19}=\d{4}` |
| U7 | **Card expiry, cardholder name** (with PAN) | PCI cardholder data | Protect when stored with PAN | Mask the expiry when it is near a PAN; the name → TOKENIZE (U12) | R/P | `(0[1-9]|1[0-2])\/?\d{2,4}` near a PAN |
| U8 | **Bank account + routing numbers** | Breach laws (account number + access code); GLBA NPI; CCPA SPI (with credentials); NACHA rules (account numbers unreadable when stored) | Protect; breach notice | Account → **MASK-X** (last 4). ABA routing number may stay (public), but not adjacent to an account number. | R | ABA 9 digits with 3-7-1 checksum; account 4–17 digits plus context; IBAN mod-97 |
| U9 | **Credentials**: username/email + password, security Q&A, OTPs, API keys, private keys, tokens | Breach laws (e.g., Cal. Civ. Code §1798.82(h)(2)); CCPA SPI (log-in + password) | Breach notice if acquired | **DELETE** (keep a typed placeholder `⟦SECRET:aws_key⟧`); optionally warn the user | R | "password:", `AKIA[0-9A-Z]{16}`, `ghp_`, `xox[abp]-`, `sk-`, JWT `eyJ…`, `-----BEGIN … PRIVATE KEY-----` |
| U10 | **Health information**: diagnoses, treatment, medications; **MRN, health-plan member IDs, Medicare MBI** | **HIPAA** (PHI for covered entities and business associates, BAA); breach laws (medical and health-insurance info); CCPA SPI (health); **WA MHMDA** (consumer health data); CA CMIA | Under a BAA: minimum necessary, safeguards, breach notice. Outside: sensitive-data rules. | IDs → **MASK-X**. Clinical content → **Tier-S**: live context only, **excluded from long-term memory** by default. HIPAA tenants only with a BAA. | R/S | MRN plus context; MBI 11-char pattern; ICD-10 `[A-TV-Z]\d[0-9AB](\.\w{1,4})?`; drug lexicon; NPI (provider, public): 10 digits starting 1/2, Luhn with the 80840 prefix |
| U11 | **HIPAA Safe Harbor 18 identifiers** (names; geography below state, ZIP3 allowed if population >20k; dates except year, and ages >89; phone; fax; email; SSN; MRN; plan #; account #; licence #; vehicle IDs and plates; device IDs and serials; URLs; IPs; **biometric identifiers incl. voice prints**; full-face photos; any other unique code) | 45 CFR 164.514(b)(2) | Needed **only to call data "de-identified"** (analytics, QA, eval sets) | For any **de-identified dataset** (telemetry, evals), remove all 18. **Raw audio can never be Safe-Harbor de-identified** because it contains the voice. | P/R | Combined detectors U1–U17 plus date, ZIP, IP, URL, device-ID patterns |
| U12 | **Names, emails, phone numbers, postal addresses** of third parties | CCPA PI; breach laws only in combination; GDPR/DPDP later | Notice; security; DSAR | **TOKENIZE** in stored artefacts; clear in the live drafting context (needed to write "Hi Priya") | P | NER plus email/phone regexes (E.164, NANP) |
| U13 | **Biometric identifiers** (voiceprints, face geometry) | **BIPA**, TX CUBI, CO, WA, CPRA SPI, HIPAA (P) | Written release, retention policy, destruction | **MINIMIZE: do not create** (MVP). Enterprise opt-in only with ENCRYPT and RETAIN ≤ 1 year after purpose | R | n/a (architectural) |
| U14 | **Precise geolocation** (≤1,850 ft) | CCPA SPI; state sensitive data | Opt-in (states) / right to limit (CA) | **MINIMIZE**: process auto-pause geofences **on device**; store at most city | S | GPS coordinates, addresses with context |
| U15 | Race/ethnicity, religion, union membership, sexual orientation, citizenship/immigration, genetic and **neural** data | CCPA SPI; state sensitive data | Opt-in / limit | **Tier-S**: exclude from memory; **never infer** | S | Lexicons plus a classifier |
| U16 | **Email/message contents** generally | **CCPA SPI** unless the business is the intended recipient [X] | Use only to provide the requested service; risk assessment | **ENCRYPT** (per-tenant keys); no secondary use; derivatives-only by default | — | — |
| U17 | **GLBA NPI** (customers' account data, balances, transactions, "being a customer") for FI tenants | GLBA Privacy Rule; **Safeguards Rule** (encryption in transit and at rest, MFA, disposal within 2 years, FTC notice ≥500 within 30 days); SEC Reg S-P (service-provider 72-hour notice) | Encrypt, oversee, notify | **ENCRYPT** plus **TOKENIZE** account identifiers; retention limits; 72-hour notice to FI customers in the DPA | P/R | Account context, transaction tables |
| U18 | **CUI** (defence contractors) | DFARS 252.204-7012 / NIST SP 800-171; CMMC (32 CFR 170) | Systems handling CUI need 800-171 controls; cloud at FedRAMP Moderate equivalent | **EXCLUDE** in v1 (block and alert). Do not sell to defence contractors for CUI use. | — | Banner markings: "CUI", "CONTROLLED UNCLASSIFIED INFORMATION", "CUI//SP-…" |
| U19 | **ITAR / EAR technical data** | 22 CFR 120–130; 15 CFR 730–774 (deemed exports to foreign persons) | No foreign-person access without a licence; encryption carve-outs are narrow | **EXCLUDE** in v1; US-region and US-person-only support if ever offered | — | "ITAR", "USML Category", "ECCN", "EAR99", "Export Controlled" |
| U20 | **MNPI** (material non-public information) | Securities laws / insider-trading policies | Information barriers | **Tier-C**: tenant policy (tokenize or exclude); no cross-user memory | C | Deal codenames, "confidential – MNPI" labels, Purview labels |
| U21 | **Privileged legal communications** | Privilege doctrine | Preserve confidentiality | **EXCLUDE** (labels, counsel domains) | C | Purview labels; "Privileged & Confidential"; law-firm domains list |
| U22 | **Children's data** (<13 COPPA; <16 CA sale/share) | COPPA; CCPA | Parental consent | **EXCLUDE** / auto-pause | S | Context ("my son", school), age mentions |

**US breach-notification overlay (customers' and our duties).** All 50 states, DC and the territories have breach laws.
- **Core triggers**: name + {SSN, DL/ID, financial account/card + code}. Many states add medical and health-insurance information, biometrics, credentials, passport and taxpayer IDs.
- **Encryption safe harbour**: most states exempt encrypted data if the key was not compromised.
- **Deadlines**: commonly 30–60 days or "most expedient" (for example FL, CO and WA 30 days; TX 60 days with AG notice). [K, Med] **Verify per state** in the incident runbook.
- **Masking Tier-R at ingestion removes most triggers from our stores.** That is the main legal payoff.

### 11.3 India: data element → regime → required treatment

| # | Data element | Regime(s) | What the law requires | PersonaAgent treatment | Tier | Detection hints |
|---|---|---|---|---|---|---|
| I1 | **Aadhaar number** (12 digits) / **VID** (16 digits) | **Aadhaar Act 2016 s.29** (no publishing or display); Aadhaar (Data Security) and (Sharing of Information) Regulations 2016; UIDAI **Aadhaar Data Vault** circular (2017): entities that *store* Aadhaar numbers must encrypt them in an ADV and use **reference-key tokens**. **Masked Aadhaar** shows only the last 4 digits. | Never display in full; vault and tokenise if stored | **MASK-X** to `XXXX XXXX 1234` at first touch. **Never store the full number**, which avoids ADV obligations. Never send it to the LLM. | R | `[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}` plus **Verhoeff** check plus context ("Aadhaar", "UID", "आधार"); reject palindromes; VID 16 digits plus "VID" [X] |
| I2 | **Aadhaar core biometrics** (fingerprint, iris) and e-Aadhaar images | Aadhaar Act s.29(1): core biometrics **never shared** except as the Act permits | Do not collect | **EXCLUDE** (attachments not ingested by default; image OCR off) | R | Attachment names "eAadhaar", PDF metadata |
| I3 | **PAN** (income-tax Permanent Account Number) | Income-tax / KYC rules; DPDP personal data; IT Act s.43A security | Protect | Individual PAN (4th character **P**) → **MASK-X**. Company PAN (4th character C/F/T…) → Tier-C (tenant policy) | R/C | `[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]` plus context |
| I4 | **Card data** (debit/credit/RuPay PAN, CVV, expiry) | **RBI tokenisation / CoF storage ban** (merchants and PAs may not store card data since 1 Oct 2022); **SPDI Rule 3** ("credit card, debit card or other payment instrument details"); PCI DSS | Do not store; tokenise via the network or issuer only | PAN → **MASK-X**; CVV → **DELETE** (as U5–U6) | R | Luhn; RuPay IINs; "CVV", "expiry" |
| I5 | **Bank account number** (with IFSC) | **SPDI Rule 3** (bank account details); RBI | Written consent (SPDI); reasonable security | Account → **MASK-X**. IFSC may stay (public branch code). | R | IFSC `[A-Z]{4}0[A-Z0-9]{6}`; account 9–18 digits plus context ("A/c", "account no") |
| I6 | **UPI ID / VPA** | SPDI (payment-instrument details); RBI payment data | As I5 | **TOKENIZE** (it is also a contact handle) | P | `[\w.\-]{2,256}@(okicici|okhdfcbank|oksbi|okaxis|ybl|ibl|axl|paytm|upi|apl|…)` with no TLD dot |
| I7 | **Passwords, OTPs, PINs** | **SPDI Rule 3(i)** (password) | Protect | **DELETE** | R | "OTP is \d{4,8}", "password", "PIN" |
| I8 | **Health**: physical, physiological or mental condition; medical records; **ABHA** number or address | **SPDI Rule 3** (health, medical records); DPDP | Written consent (SPDI); security | ABHA → **MASK-X**. Clinical content → **Tier-S** (no long-term memory) | R/S | ABHA `\d{2}-\d{4}-\d{4}-\d{4}`; `name@abdm`; medical lexicon (Hindi/English) |
| I9 | **Sexual orientation** | SPDI Rule 3 | As above | **Tier-S**; never infer | S | Classifier |
| I10 | **Biometric information** (incl. **voice patterns**) | SPDI Rule 3 and the definition of biometrics | Written consent; security | **MINIMIZE**: no voiceprints (MVP) | R | Architectural |
| I11 | **Passport** (Indian) | DPDP; s.43A security | Protect | **MASK-X** | R | `[A-PR-WY][1-9]\d\s?\d{4}[1-9]` (letter + 7 digits) plus context |
| I12 | **Voter ID (EPIC)**, **driving licence** | DPDP | Protect | **MASK-X** | R | EPIC `[A-Z]{3}\d{7}`; DL `[A-Z]{2}\d{2}[ -]?\d{4}\d{7}` plus context |
| I13 | **GSTIN** | Business identifier (it embeds the PAN) | — | Tier-C (tenant policy); mask the embedded PAN if the 6th character is P (individual proprietor) | C | `\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]` (checksum) |
| I14 | **Names, mobile numbers (+91), emails, addresses, PIN codes** | **DPDP** (all personal data; no "sensitive" tier); SPDI Rules apply to SPDI only | Notice, consent or legitimate use; security incl. "**encryption, obfuscation or masking or the use of virtual tokens**" (DPDP Rules) [V] | **TOKENIZE** in stored artefacts; clear in the live context | P | `(\+91[- ]?)?[6-9]\d{9}`; PIN `[1-9]\d{5}`; NER for Indian names (Indic scripts too) |
| I15 | **Children's data** (<18) | **DPDP s.9**: verifiable parental consent; **no tracking or behavioural monitoring** | Do not process without parental consent | **EXCLUDE** / auto-pause | S | Context, age mentions |
| I16 | **Caste, religion, political opinion** | Not SPDI, and DPDP has no special category, but highly sensitive in India (discrimination law) | — | **Tier-S**: exclude from memory; never infer [X] | S | Lexicons |
| I17 | **UPSI** (listed-company tenants) | **SEBI PIT Regulations 2015** (sharing of UPSI; structured digital database) | Restrict and track UPSI sharing | **Tier-C**: exclude or tokenize; no cross-user memory | C | Labels, "UPSI", results dates |
| I18 | **Payment-system data** (end-to-end transaction details) of PSO tenants | **RBI 6 Apr 2018** circular: stored **only in India** [V] | Localise | **LOCALIZE** (India-only processing flag) plus MASK-X on card and account numbers | — | Tenant flag (PSO), transaction-log patterns |
| I19 | **SEBI-regulated entity data and logs** | **CSCRF** (20 Aug 2024) [V] plus the cloud framework (data and logs within India) [K, Med] | Localise; audit | **LOCALIZE** (mandatory India-only for SEBI REs) | — | Tenant flag |
| I20 | **Insurance records** | IRDAI records and cyber guidelines [K, Med] | Records in India | **LOCALIZE** for insurer tenants | — | Tenant flag |
| I21 | **ICT system logs** | **CERT-In**: 180 days **within Indian jurisdiction** [V]; **DPDP Rules**: logs and personal data kept **1 year** for breach investigation [V] | Retain and localise | **RETAIN(≥1 yr)** plus **LOCALIZE** an India copy; **mask Tier-R in logs** | — | — |
| I22 | **Breach records** | DPDP: Board + Data Principals, detailed report **≤72 h** [V]; CERT-In **≤6 h** [V] | Report | Incident runbook with a 6-hour CERT-In path and 72-hour DPDP support for customers | — | — |

### 11.4 Cross-cutting rules for the engine

1. **Order of operations:** detect → MASK-X/DELETE (Tier-R) → TOKENIZE (Tier-P) → classify Tier-S/Tier-C → persist or embed → LLM. **Tier-R never reaches Bedrock, logs, vectors or analytics.**
2. **Locale-aware detection.** Indian text mixes English, Hindi (Devanagari) and Hinglish. Amazon Comprehend PII is English/Spanish only but has IN_AADHAAR/PAN/VOTER/NREGA types; Presidio validates Aadhaar with Verhoeff. [X]
3. **Pseudonymised ≠ anonymous.** Tokenized data remains personal data under DPDP and CPRA, and PHI under HIPAA. [X]
4. **Audit evidence.** Log *that* a redaction happened (type, count, rule version), never the value. That evidence supports the "reasonable security practices" defence under s.43A and FTC/state UDAP.
5. **Attachments OFF by default** (KYC scans, payslips and medical reports are where Aadhaar, PAN and health data concentrate).

### 11.5 Points to confirm with specialists

- **QSA**: whether transient in-memory PAN handling at ingestion keeps all of PersonaAgent out of PCI DSS scope, or only out of the cardholder-data environment.
- **Indian counsel**: whether incidental receipt of Aadhaar numbers in email triggers any UIDAI duty beyond masking, given we never store them.
- **Indian counsel**: whether SEBI/IRDAI localisation reaches **AI inference** (transient processing) or only storage.

---

## 12. Jurisdiction × feature risk matrix

Ratings are **inherent risk without guardrails** → **residual risk with the Section 13 MVP guardrails**.
- **H** = likely claims or regulatory action with large exposure.
- **M** = real but manageable.
- **L** = low.
- Confidence in the ratings is **Med**; they are analyst judgement built on Sections 2–11.

| Feature ↓ / Jurisdiction → | US one-party states | US all-party states (CA, FL, IL, MD, MA, MT, NH, PA, WA, DE, MI*; split CT/NV/OR/MO) | India (v1) | EU (later) | UK (later) | Canada | Australia |
|---|---|---|---|---|---|---|---|
| **Always-on in-person recording** (work-only) | **M → L-M**. User is a party, so one-party consent holds. Risks: a recorder left running without the user present; crime-tort exception if the vendor uses the data; NY/CT/DE notice laws. | **H → M**. All-party consent needed for "confidential" conversations. Bystanders and visitors are the problem. CIPA $5,000 per violation. Wearer-only / consent mode is essential. | **M → L-M**. No all-party statute. SPDI now; DPDP consent or legitimate use from May 2027; outsiders need notice and consent. | **H → M-H**. GDPR Art. 13 notice, legitimate-interest balancing, works councils, DE §201 / FR 226-1 criminal laws. Emotion inference from voice prohibited. | **M-H → M**. ICO monitoring guidance; DPIA | **M → L-M**. One-party (Criminal Code), plus PIPEDA notice | **H → M**. NSW/WA/SA/Tas/ACT all-party-style rules; NSW workplace-surveillance notice |
| **Meeting / call recording** (Teams) | **M → L**. Use Microsoft transcription or bots that signal `updateRecordingStatus`, which triggers the banner. | **H → M**. Host-only consent is insufficient (*Otter*). Announce to every participant; external meetings off by default. Bot-free silent capture → *Granola*-type claims. | **M → L**. Banner plus announcement plus policy; CERT-In logging | **M-H → M**. Art. 13 notice at the meeting; DPIA; works council | **M → L-M** | **M → L** | **M-H → M** |
| **Voiceprints / speaker ID** | **M-H → L** (not built in MVP). TX CUBI and CO apply even in one-party states. | **H → L** (not built). IL **BIPA** with a private right of action; WA MHMDA for consumers. | **M → L**. SPDI biometrics need written consent. | **H → L**. Art. 9 explicit consent; possible AI Act "remote biometric identification" high-risk | **H → L** | **M → L** | **M → L** |
| **Email / Teams ingestion** (persona learning) | **M → L**. Microsoft API Terms (express and specific grant); CCPA if CA residents; NY/CT/DE notice | **M → L**. CA: email contents = SPI; CPPA risk assessment | **M → L-M**. Third parties in old emails (new purpose) under DPDP; SPDI categories → mask at ingestion | **M-H → M**. Legitimate interests; Art. 14 notices; DPIA; works council | **M → L-M** | **M → L** | **M → L** |
| **Persona drafting** (human-sent) | **L-M → L**. No AI-label law for human-sent mail; misuse/fraud is the main risk. | **L-M → L**. Same; CA SB 1001 only for misleading **bots** in sales or elections | **L-M → L**. IT Act s.66D / BNS s.319 for misuse | **M → L-M**. **Art. 50(2) machine-readable marking** of generated text likely; Art. 50(1) if autonomous | **L-M → L** | **L → L** | **L → L** |
| **Autonomous sending** (not in v1) | **M** (UDAP, fraud, Utah disclosure on request) | **M-H** (SB 1001 for sales contexts) | **M** | **M-H** (Art. 50(1)) | **M** | **M** | **M** |
| **Voice clone** (future) | **H** (ELVIS Act, NO FAKES if enacted, CA §3344/AB 2602, NY §50-51) | **H** | **H** (personality-rights injunctions) | **H** (Art. 50(4) deepfakes; GDPR) | **H** | **M-H** | **M-H** |

\*Michigan: all-party consent at least for non-participant recorders.

**Reading the matrix:**
- The **two red zones in v1** are (1) in-person and meeting recording in US all-party states and (2) any voiceprint feature.
- **India's risk is mostly regulatory and contractual readiness** (DPDP 2027, CERT-In, BFSI localisation) rather than litigation.
- The EU is high-friction (works councils, the AI Act). Deferring it is the right call.

---

## 13. Recommendations for PersonaAgent

### 13.1 Legal-guardrail product requirements: MVP (≈3 months, 3–6 engineers) vs Enterprise

| ID | Requirement | MVP | Enterprise | Driver (section) |
|---|---|---|---|---|
| **G1** | **No training or independent use** of customer content (no fine-tuning on tenant data, no cross-tenant learning, no human review without a ticketed customer instruction). Enforced in code, IAM and contracts; public trust-centre statement. | ✅ | ✅ plus third-party audit attestation | 3, 6.1 |
| **G2** | **Admin-consent onboarding** that records the customer's **"express and specific" grant** for persona learning from email and Teams (Microsoft API Terms §3(c)); least-privilege scopes; a purpose statement | ✅ | ✅ | 6.8, 9.1 |
| **G3** | **Never record silently.** Teams: use Microsoft transcripts or a bot that calls `updateRecordingStatus` (banner). Desktop/phone: persistent indicator. Wearable (later): hardware LED + physical mute. | ✅ | ✅ | 2, 9 |
| **G4** | **Announcement + consent ledger** for every capture session (who, how and when notified; objections; actions) | ✅ (chat card + spoken notice in strict mode) | ✅ plus customer export and API | 2.4, 10 |
| **G5** | **Strict-by-default jurisdiction profile**: treat every session as all-party consent. External-company meetings **OFF** by default. In-person capture **OFF** until an admin enables it. | ✅ | ✅ plus per-region policy overrides with an admin attestation | 2, 12 |
| **G6** | **Wearer-only / consent mode** for in-person capture: drop non-wearer audio on device; no biometric templates | ✅ (heuristic wearer-only + manual "all consented" confirmation) | ✅ plus optional enrolled-consent mode (G10) | 2.4, 4.3 |
| **G7** | **Auto-pause and hard blocks**: privileged / HR / medical / interview calendar tags; zones; "off the record" cues; minors; healthcare; public sector | ✅ (calendar tags + manual + cue words) | ✅ plus geofences and Purview-label triggers | 7, 10 |
| **G8** | **Derivatives-only storage**: no raw audio; transcripts with TTL (30 days default); summaries and memories user-controlled | ✅ | ✅ plus optional encrypted raw vault (customer key) | 6.6 |
| **G9** | **Phase-1 redaction (Section 11)**: Tier-R MASK-X/DELETE before persistence or LLM; Tier-P tokenize; Tier-S excluded from memory; attachments off | ✅ (US + India detectors) | ✅ plus tenant custom dictionaries (Tier-C), more locales | 11 |
| **G10** | **No voiceprints in MVP.** Speaker labels from Teams metadata or manual tags only. | ✅ | Opt-in enrollment with BIPA-grade written release, public retention policy, ≤1-year destruction after purpose, state gating | 4 |
| **G11** | **No emotion or intention inference from voice**; models run on text only; no per-employee performance analytics; AUP ban | ✅ | ✅ | 5.1 |
| **G12** | **Persona anti-impersonation**: persona usable only by its owner; Entra ID session with MFA/Conditional Access; drafts only into the owner's compose window; **no autonomous send**; payment-instruction guard; generation audit log | ✅ | ✅ plus anomaly detection and tenant kill switch | 8.3 |
| **G13** | **Offboarding**: freeze the persona on account disable; delete after 30 days (configurable); team knowledge stays in M365; no persona transfer | ✅ | ✅ plus HR-system triggers | 8.4 |
| **G14** | **Deletion propagation**: mirror M365 deletions (delta queries); delete all on uninstall or abandonment; crypto-shredding per user | ✅ | ✅ | 6.6, 6.8 |
| **G15** | **Legal hold** overrides all deletion (including crypto-shred and TTL); eDiscovery export with metadata (source, time, model version, AI flag) | ✅ (tenant-level hold + export) | ✅ plus per-custodian holds, Purview write-back, regulated-recordkeeping (WORM/journaling) mode for FS | 7.4, 7.2 |
| **G16** | **AI disclosure**: Teams-Store-compliant AI disclaimer in the UI; "report output" button; invisible `X-AI-Assisted` marker on drafts; optional visible footer per tenant | ✅ | ✅ plus EU Art. 50(2) marking aligned with the Code of Practice | 5.1, 8.1, 9.1 |
| **G17** | **Employee notice pack**: in-app acknowledgement (NY §52-c / CT / DE), CA notice-at-collection addendum, India policy clause; admin attestation | ✅ | ✅ plus works-council agreement template (EU) | 5.3 |
| **G18** | **Data residency**: US tenants → US regions; India tenants → AWS Mumbai; **India-only processing flag** (in-region models, India logs), mandatory for BFSI | ✅ (storage + logs) | ✅ plus in-region inference for BFSI | 6.5, 11 |
| **G19** | **Incident response**: CERT-In 6-hour path; customer notice for DPDP 72-hour, Reg S-P 72-hour, bank 36-hour and state-law deadlines; MSRC notice | ✅ (runbook + contacts) | ✅ plus tabletop tests and named PoC | 2.5, 7.2, 9.1 |
| **G20** | **Third-party request portal** ("Were you recorded or mentioned?") routing to the controller tenant; DSAR tooling (search, export, erase across artefacts) | ✅ (email intake + admin tooling) | ✅ plus self-service portal and SLA reporting | 6.7 |
| **G21** | **Tenant eligibility gates**: no consumer/personal accounts; no healthcare (until a BAA is in place), public sector, defence/CUI, or schools in v1 | ✅ | Healthcare tier (BAA) later | 6.1, 7 |

### 13.2 Legal document set

| Document | Purpose | Must-have clauses specific to PersonaAgent | When |
|---|---|---|---|
| **Master Subscription Agreement / ToS (B2B)** | Commercial terms | Customer is controller; customer **warrants it has given employee notices and obtained recording consents** and will use consent features; **AUP incorporated**; no performance-evaluation use; indemnity allocation for unlawful recording **by customer users**; our warranties: no training, security; suspension rights for misuse; persona non-transferability | Before the first paid pilot |
| **Acceptable Use Policy** | Prohibited uses | No covert recording; no recording where prohibited; no use on minors or patients (unless the healthcare tier); no impersonation, fraud or BEC; no harassment; no performance or discipline scoring; no evading monitoring; no use with CUI/ITAR; no voice cloning of others | MVP |
| **Data Processing Agreement (DPA)** | GDPR Art. 28 / CCPA service-provider / DPDP s.8(2) contract | Instructions; confidentiality; sub-processors with notice and objection; **security annex** (masking, encryption, keys); breach notice (**≤48h** to customer to support DPDP 72h; **≤72h** Reg S-P); assistance with DSARs, DPIAs and risk assessments; deletion and return; audits; SCCs/UK addendum (later); India annex (CERT-In, localisation options); **CCPA service-provider certifications** (no sell/share, no combining) | MVP |
| **Sub-processor list** | Transparency | AWS (hosting, Bedrock), Anthropic via Bedrock (model; data not shared per AWS terms, to verify), STT vendor(s), Azure (if real-time media bots), email delivery, support tooling. Regions per tenant. 30-day change notice. | MVP |
| **Privacy Policy** (website/app) | Our own controller processing + transparency about the product | Must be **at least as protective as Microsoft's privacy statement** and link to Microsoft consent-revocation pages (API Terms §5); third-party AI disclosure (Apple 5.1.2(i)); India grievance officer; data-principal rights | MVP |
| **AI Transparency Notice / Model Card** | Explain AI functions and limits | What is generated, the models used, no training on customer data, known limits (hallucination), the human-send requirement, marking practice, a statement that text tone modelling does not infer emotions, how to report outputs (Teams Store) | MVP |
| **Recording & Capture Notice templates** | For customers to give employees and outsiders | (a) Employee monitoring notice + acknowledgement (NY/CT/DE compliant); (b) meeting announcement text; (c) external-participant notice page (link in chat card); (d) office signage; (e) India notice in English + Hindi (others on request) | MVP |
| **Customer DPIA / risk-assessment template** | Help customers meet GDPR Art. 35 / CPPA / DPDP SDF duties | See 13.3 | MVP (US/India version), EU version later |
| **Biometric Policy + Written Release** | BIPA/CUBI/CO compliance if voice enrollment ships | Public retention schedule; purpose; destruction; e-sign release per person | Enterprise (only if G10 enrollment ships) |
| **BAA** | HIPAA | Flow-down to AWS and STT; breach terms | Healthcare tier only |
| **Regulated-customer annexes** | BFSI India/US | RBI outsourcing and audit rights; SEBI CSCRF/cloud localisation; IRDAI records; FINRA/SEC recordkeeping cooperation | Enterprise |
| **Works-council agreement template** (EU later) | BetrVG §87(1) no. 6 | Purposes, exclusions (no performance monitoring), access, retention, evaluation bans | EU expansion |
| **Security whitepaper / trust centre** | Sales enablement | Architecture, redaction, keys, residency, certifications (SOC 2 / ISO 27001 roadmap; ISO 27001 also helps as the SPDI Rule 8 safe harbour) | MVP (whitepaper), certs in 6–12 months |
| **Trademark clearance memo** | Brand | "PersonaAgent" conflict check | Before public launch |

### 13.3 Customer DPIA / risk-assessment template (outline)

1. **Description**: features enabled (persona drafting, meeting notes, in-person capture); data categories (email and chat content, transcripts; Tier-R masked; no voiceprints); data subjects (employees, external contacts, bystanders); recipients and sub-processors; regions.
2. **Purposes and lawful basis**: per jurisdiction (US notices/consents; India SPDI consent or DPDP s.7(i) / consent; EU legitimate interests with balancing).
3. **Necessity and proportionality**: minimisation (user-authored content only; derivatives-only; TTLs); alternatives considered.
4. **Risks to individuals**: covert recording; chilling effects on staff; profiling of colleagues ("memory"); impersonation; breach of a sensitive corpus; discrimination via misuse; non-users' rights.
5. **Controls**: G1–G21 mapping; admin configuration chosen; consent ledger; DSAR process; legal hold.
6. **Employee and representative consultation** (works council / unions where applicable).
7. **Residual risk and sign-off**; review cadence (12 months; aligns with the DPDP SDF annual DPIA).

### 13.4 Sequencing (what to do with counsel first)

1. **US privacy/litigation counsel (first 4–6 weeks)**:
   - CIPA/ECPA review of the meeting and in-person capture flows; the announcement wording;
   - whether a summary of an unconsented recording is itself a §632 problem;
   - the BIPA "filtering paradox";
   - MSA/AUP/DPA drafting.
2. **Indian counsel (parallel)**:
   - DPDP readiness (May 2027);
   - SPDI consent language now;
   - Telecommunications Act interception question;
   - SEBI/RBI/IRDAI localisation scope (storage vs inference);
   - Aadhaar handling confirmation.
3. **QSA** for PCI scoping of ingestion; **trademark counsel** for the name.
4. Before EU launch: AI Act Art. 50 and remote-biometric classification; works-council templates; DPF certification.

---

## 14. Top 10 legal risks

Scale: **Likelihood (L)** and **Impact (I)** from 1 to 5; **score = L × I**. The score is **inherent** (without mitigations). **Residual** is after the Section 13 MVP guardrails. Ranking is analyst judgement (Med confidence).

| # | Risk | L | I | Score | Why (evidence) | Key mitigations | Residual |
|---|---|---|---|---|---|---|---|
| 1 | **Wiretap / CIPA / all-party-consent class action** over meeting or in-person capture (users *and* PersonaAgent named) | 4 | 5 | **20** | *Otter* survived dismissal (Aug 2026); *Granola* targets bot-free capture (Jul 2026); CIPA $5,000 per violation; SB 690 left §§631/632 intact | G3–G7 (never silent, announcements, external meetings off, wearer-only, auto-pause), G1 (no independent use), consent ledger, AUP and customer warranties, privacy and cyber insurance | **M** (8–10) |
| 2 | **Biometric (BIPA / CUBI / CO / WA) claims** from speaker ID, voice enrollment or "consent mode" | 3 | 5 | **15** | *Fireflies* and *Otter* BIPA counts; 7th Cir. *Clay* caps per-person damages, but class exposure remains | G10: no voiceprints in MVP; enrollment only with written release and state gating; counsel opinion on ephemeral filtering | **L** (3–4) |
| 3 | **Losing the processor/"tool" position** through secondary use: training, cross-tenant analytics, human review, or retaining data after termination. This turns us into a "third-party eavesdropper" and controller, and breaks CCPA service-provider status. | 3 | 5 | **15** | *Otter*: training plausibly tortious and third-party; *Ambriz* capability test; FTC Amazon/Ring orders | G1 enforced technically and contractually; content-free telemetry; deletion on termination; annual third-party attestation | **L-M** (4–6) |
| 4 | **Breach of the communications corpus or token vault** → 50-state + DPDP + CERT-In notices, class actions, Microsoft API termination | 3 | 5 | **15** | Customer mail is full of secrets (security track: Salesloft Drift 2025); India 6h / 72h clocks | G9 masking at ingestion (removes breach-law triggers); per-tenant keys; crypto-shredding; no standing access; G19 runbooks (security track details) | **M** (6–8) |
| 5 | **Microsoft platform dependency**: API Terms purpose limits, admin-consent policy, external-bot labelling, media-bot rules, termination "in its sole discretion" | 3 | 4 | **12** | Verified ToU §§3(c), 5, 10; `updateRecordingStatus` restriction; MC1251206 [X] | G2 express grant at admin consent; least privilege; use Microsoft's own transcripts; Publisher Attestation / Certification; no silent media capture | **M** (6) |
| 6 | **Persona misuse: impersonation / BEC fraud**, insider "act-as", ex-employee persona use | 3 | 4 | **12** | Persona = impersonation kit (50–100 emails) [X]; proposed FTC "means and instrumentalities" theory; IT Act s.66D | G12 (owner-only, MFA, no autonomous send, payment guard, audit), G13 offboarding, AUP, anomaly detection | **L-M** (4–6) |
| 7 | **Workplace-monitoring and AI-governance violations**: NY/CT/DE notices; CPPA risk assessments; Colorado ADMT (2027); later EU works councils, the AI Act (voice emotion ban, Annex III) | 3 | 3 | **9** | Verified AI Act text and guidelines; CO SB 26-189; CPPA regs | G11 (no voice emotion, no performance analytics), G17 notice pack, AUP, DPIA template; EU deferred | **L-M** (4) |
| 8 | **eDiscovery / spoliation / privilege** (auto-delete during a hold; privileged meetings captured; inaccurate AI summaries as evidence) | 3 | 3 | **9** | FRCP 37(e); AI-log preservation orders (2025); privilege-waiver arguments | G15 legal hold overrides all deletion; privileged mode (G7); AI-generated labels + source links; Purview write-back | **L-M** (4) |
| 9 | **Sector non-compliance** (FINRA/SEC recordkeeping; HIPAA/CMIA; RBI/SEBI/IRDAI localisation and outsourcing rules) | 2 | 4 | **8** | FINRA 24-09 and 2026 report; SEC $63.1M sweep (Jan 2025); *Sharp* suit; RBI 2018 circular | G21 tenant gating (no healthcare/public sector in v1); regulated-recordkeeping mode; India-only processing flag; BFSI annexes | **L** (3–4) |
| 10 | **India readiness**: CERT-In 6h / 180-day India logs now; DPDP (May 2027) consent and notice for third parties; SPDI written consent; penalties up to ₹250 crore | 2 | 4 | **8** | Verified CERT-In Directions and DLA Piper DPDP summary | G18 residency + India log copies; G19 CERT-In runbook; consent / notice texts (English + Hindi); DPDP gap assessment Q1 2027 | **L** (3) |
| — | *Also track:* **trademark conflict** over "PersonaAgent" (L3 × I2 = 6) | | | 6 | ACL 2026 framework name [X] | Clearance search; rename early if needed | L |

---

## 15. Risks and watch-outs (dated calendar)

### 15.1 Dated calendar (as of 6 Oct 2026)

| Date | Event | Relevance | Source / conf. |
|---|---|---|---|
| 28 Apr 2022 (in force) | CERT-In Directions: 6-hour reporting, 180-day logs in India | Applies now to India operations | [V] |
| 2 Feb 2025 (in force) | EU AI Act prohibitions, including emotion recognition at work | Design constraint for EU | [V] |
| 1 Jul 2025 (in force) | Colorado biometric amendment (HB24-1130) | Voice enrollment | [V] |
| 1 Jan 2026 (in force) | CPPA regulations (ADMT, risk assessments, cybersecurity audits) effective; Illinois HB 3773 | CA customers' risk assessments | [V] / [K] |
| 1 Apr 2026 | 7th Cir. *Clay v. Union Pacific*: BIPA damages amendment retroactive | Lower per-person exposure | [V secondary] |
| 2 Aug 2026 (in force) | EU AI Act Art. 50 transparency | EU expansion: marking / disclosure | [V] |
| 13 Aug 2026 | *Otter* motion-to-dismiss order (ECPA, CIPA §631, BIPA survive) | Litigation template | [V secondary] |
| ~Sep–Oct 2026 | *Otter* amended complaint and renewed motions; *Granola* first response | Watch for rulings on bot-free capture and consent by announcement | [Unverified timing] |
| By end Oct 2026 | Teams external-bot "Unverified" labelling GA completes | Bot strategy | [X] |
| Oct 2026 | California SB 690 signed (pen-register claims → AG only; §§631/632 untouched); effective date likely 1 Jan 2027 | No relief for wiretap/recording claims | [V] signing; [K] effective date |
| **13 Nov 2026** | DPDP: consent-manager provisions commence | India consent architecture | [V] |
| **2 Dec 2026** | AI Act Art. 50(2) grace ends for legacy systems; new Art. 5 prohibitions (nudifier/CSAM) apply | EU marking | [V] |
| **1 Jan 2027** | Colorado SB 26-189 (ADMT) effective; CCPA ADMT compliance date | AUP and employment-use ban | [V] / [K] |
| **13 May 2027** | **DPDP Act: all substantive obligations apply**; SPDI regime/s.43A replaced | India v1 must be fully DPDP-ready | [V] |
| 2 Dec 2027 | AI Act Annex III high-risk obligations (employment, biometrics) | EU intended-purpose discipline | [V] |
| 31 Dec 2027 / Apr 2028 | CPPA: risk assessments for pre-2026 processing due; attestations from Apr 2028; first cybersecurity audits (largest businesses) Apr 2028 | Customer asks of us | [K, Med] |
| 2 Aug 2028 | AI Act Annex I high-risk | Not core to us | [V] |

### 15.2 Watch-outs (not dated)

- **Note-taker litigation copycats.** Expect more suits against bot-free and wearable recorders. Any marketing line such as "invisible", "no bot", or "nobody will know" will be used as Exhibit A. **Never market stealth.**
- **Plaintiffs' use of our own documents.** Privacy-policy wording about "improving our services" was central in *Otter*-style complaints. Keep the policy literal: **no training on customer data.**
- **FTC.** Possible finalisation of the impersonation-rule extension to individuals and "means and instrumentalities". Continued scrutiny of AI data-retention claims (Alexa precedent).
- **Federal preemption push** against state AI laws (Dec 2025 executive order). It is unlikely to touch wiretap or biometric statutes.
- **India.**
  - Significant Data Fiduciary designations, which would flow down to us through large customers.
  - Any notified **transfer blacklist** under DPDP s.16.
  - Final IT Rules on synthetic content (relevant to a voice clone).
  - SEBI/RBI AI-governance guidance for regulated entities.
  - MeitY AI Governance Guidelines (reported Nov 2025; principles-based, no new statute). [K, Med; not verified]
- **EU.**
  - CJEU appeal against the DPF (*Latombe*).
  - Final Commission Art. 50 guidelines.
  - Works-council practice on generative AI (German DPAs and labour courts).
- **Microsoft.** Changes to the API Terms, metered/protected Teams APIs, and the bot-admission policy (MC1251206). Microsoft's own Copilot features competing on the same data, which also bear on platform-policy enforcement.

---

## 16. Open questions / could not verify

### 16.1 Could not verify this session

The WebSearch budget ran out after about 15 searches. Several primary sites blocked fetching: Justia, CourtListener, Courthouse News PDFs, leginfo, ilga.gov, MeitY.

| Item | Status | What to do |
|---|---|---|
| *In re Otter.AI* 13 Aug 2026 order: exact holdings and quotes | Taken from secondary reporting (recordinglaw.com, tl;dv, consentpixel); the docket and order PDF were not reachable | Counsel to pull the order (N.D. Cal. 5:25-cv-06911, ECF ~68) and the post-ruling docket |
| *Chamberlain v. Granola* (3:26-cv-07926) details | Secondary sources only | Pull the complaint |
| *Cruz v. Fireflies* court/district; *Fricker* filing details | The court was not identified by the source fetched | Docket search |
| Suits against **Read.ai, Gong, Limitless, Plaud, Microsoft Teams/Recall, Meta glasses, Amazon/Bee** | Not searched (budget exhausted) | Docket / news search |
| SB 690 **signing date and effective date** | Signing confirmed (KTS, 1 Oct 2026); dates not confirmed | Check leginfo |
| *Project Veritas v. Schmidt* cert petition (No. 24-1061) outcome | Not verified | Check the SCOTUS docket |
| **Missouri** in-person all-party rule (RCFP reading of §542.402) | Unusual; RCFP only | Counsel confirmation |
| *United States v. Heppner* (S.D.N.Y. 2026, AI chats not privileged) | Background knowledge only | Verify before citing |
| Google Assistant settlement (~$68M); CNIL *Amazon* appeal; Siri settlement details | Background knowledge | Verify before external use |
| CPPA **phased deadlines** (ADMT 2027; risk assessments 2027/2028; audits 2028–2030) | Only the OAL approval date (22 Sep 2025) and the 1 Jan 2026 effective date were verified | Read the final regulation text |
| Colorado HB24-1130 details (voiceprint inclusion, deletion deadlines, applicability below CPA thresholds) | Only the effective date was verified | Read the bill text |
| **India**: DPDP Rules full text (transfer rule wording, rule numbers); Telecommunications Act 2023 interception offence applied to VoIP capture; UIDAI ADV duties for incidental receipt; SEBI CSCRF and IRDAI localisation wording; MeitY AI Governance Guidelines (Nov 2025); final IT Rules on synthetic content; *Vibhor Garg* citation | DLA Piper summary + background knowledge | Indian counsel review (Section 13.4) |
| EU: DPF appeal status; final Art. 50 guidelines; Code of Practice text for **text** marking | Partially verified (Code adequacy 8 Jul 2026 via Jones Walker) | Re-check at EU expansion |
| Microsoft "explicit recording consent" policy page (404); whether it governs third-party bots and device capture | Not verified | Check Microsoft Learn's new location |
| AWS Bedrock statement that prompts and outputs are not shared with model providers | Background knowledge | Confirm against current AWS service terms (AWS track) |
| Zoom RTMS / Marketplace consent rules | Not verified | Before the Zoom integration |
| Washington, Oregon and Michigan civil-damages specifics | RCFP summaries + background knowledge | Counsel |

### 16.2 Open legal questions for counsel (priority order)

1. **CIPA §632 / all-party states.** Is a **text summary or memory** derived from an unconsented in-person conversation itself actionable? Does "wearer-only" capture with on-device discard of others' audio avoid "recording" those others?
2. **BIPA "filtering paradox".** Are ephemeral, never-stored voice embeddings used only to **exclude** non-consenting speakers "biometric identifiers" that are "collected or captured"?
3. **Consent by announcement.** Is implied consent from a recorded announcement plus continued participation sufficient in CA, FL, IL, MD, MA, PA and WA for (a) Teams meetings and (b) in-person meetings? Is a click-through needed for external participants?
4. **Microsoft API Terms §3(c).** Is the admin-consent screen plus order-form language enough to be an "express and specific" grant for persona learning? Do we need a separate written instrument?
5. **India DPDP.** Can **s.7(a)** (voluntarily provided, no objection) or **s.7(i)** (employment) cover third parties in meetings and historical emails, or is explicit consent needed? Does the **Telecommunications Act 2023** reach vendor capture of VoIP audio?
6. **India sector rules.** Do SEBI/RBI/IRDAI localisation rules cover **transient LLM inference** abroad, or only storage?
7. **Persona ownership.** Does an employee have any **publicity-right or moral claim** to their style model after leaving? Can the employer require deletion even where the employee wants a copy (DSAR)?
8. **EU (later).** Is cross-meeting speaker ID "remote biometric identification" (Annex III(1)(a))? Does persona drafting fall within the Art. 50(2) "assistive function for standard editing" exception?
9. **PCI.** Can transient PAN handling during ingestion be scoped out by a QSA?
10. **Insurance.** Does cyber/tech E&O cover statutory wiretap and BIPA damages? Many policies exclude biometric and wiretap claims.

---

## 17. Sources

All accessed 5–6 Oct 2026. **[F]** = fetched and read this session. **[S]** = seen only as a search-result summary. **[R]** = reference for counsel, not fetched this session.

**Litigation: AI note-takers, biometrics, CIPA**
- [S] In re Otter.AI Privacy Litigation docket, N.D. Cal. 5:25-cv-06911: https://www.courtlistener.com/docket/71118721/brewer-v-otterai-inc/
- [S] Justia: order granting in part the motion to dismiss (ECF 68): https://docs.justia.com/cases/federal/district-courts/california/candce/5:2025cv06911/454675/68
- [F] RecordingLaw, Otter ruling explained: https://www.recordinglaw.com/news/otter-ai-wiretap-lawsuit-explained/
- [S] Sheppard Mullin, "When AI Takes Notes": https://www.sheppard.com/insights/blogs/when-ai-takes-notes-court-allows-privacy-claims-against-otterai-to-proceed
- [S] tl;dv, AI meeting recorder lawsuits 2026: https://tldv.io/blog/ai-meeting-recorder-lawsuits/
- [S] Courthouse News, Otter filing PDF: https://www.courthousenews.com/wp-content/uploads/2026/08/otter-ai-privacy-class-action.pdf
- [F] ConsentPixel, *Chamberlain v. Granola*: https://consentpixel.com/blogs/granola-ai-notetaker-wiretap-litigation/
- [S] PPC Land, Granola suit: https://ppc.land/granola-sued-for-recording-meetings-without-consent-to-train-ai-models/
- [S] Layer3 Labs, Granola lawsuit: https://www.layer3labs.io/guides/granola-lawsuit
- [F] National Law Review, BIPA suit targets AI note-takers (Fireflies): https://natlawreview.com/article/illinois-bipa-suit-targets-ai-note-takers-practical-lessons-meeting-transcription
- [S] Top Class Actions, Fireflies: https://topclassactions.com/lawsuit-settlements/lawsuit-news/fireflies-ai-sued-over-alleged-unlawful-data-collection-from-meeting-participants/
- [S] SGR, AI note-takers and BIPA damages: https://www.sgrlaw.com/newsroom/publications/ai-note-takers-biometric-privacy-and-the-battle-over-bipa-damages-what-businesses-need-to-know-now
- [S] Jackson Lewis, 7th Cir. BIPA retroactivity (*Clay v. Union Pacific*): https://www.jacksonlewis.com/insights/bipa-cases-7th-circuit-rules-change-illinois-laws-damages-provision-retroactively-limits-defendant-exposure
- [S] SGR, 7th Cir. BIPA: https://www.sgrlaw.com/newsroom/publications/seventh-circuit-holds-bipa-damages-amendment-applies-retroactively
- [S] Becker's, Sharp HealthCare ambient-AI suit: https://www.beckershospitalreview.com/healthcare-information-technology/ai/patient-sues-sharp-healthcare-over-ambient-ai-use/
- [S] Fisher Phillips, healthcare AI recordings class action: https://www.fisherphillips.com/en/news-insights/new-class-action-targets-healthcare-ai-recordings.html
- [S] ZwillGen, *Ambriz v. Google*: https://www.zwillgen.com/privacy/federal-judge-allows-google-customer-service-ai-class-action-to-proceed/
- [S] Goodwin, AI voice products and CIPA: https://www.goodwinlaw.com/en/insights/publications/2025/02/alerts-practices-dpc-ftec-ai-voice-products-subject-to-california-invasion-of-privacy-claims

**US recording law and CIPA reform**
- [F] RCFP Reporter's Recording Guide (introduction): https://www.rcfp.org/introduction-to-reporters-recording-guide/
- [F] RCFP state pages: https://www.rcfp.org/reporters-recording-guide/missouri/ · https://www.rcfp.org/reporters-recording-guide/oregon/ · https://www.rcfp.org/reporters-recording-guide/delaware/ · https://www.rcfp.org/reporters-recording-guide/michigan/
- [S] Snell & Wilmer, Ninth Circuit upholds Oregon recording law: https://www.swlaw.com/publication/ninth-circuit-upholds-oregons-ban-on-unannounced-audio-recordings-rejects-first-amendment-challenge/
- [S] Project Veritas cert petition (No. 24-1061): https://www.supremecourt.gov/DocketPDF/24/24-1061/354931/20250407155521527_24-%20Petition.pdf
- [F] Kilpatrick (KTS), SB 690 signed: https://ktslaw.com/en/insights/alert/2026/10/what%20sb%20690%20means%20for%20pending%20pen%20register%20claims
- [S] NatLawReview, SB 690 amended: https://natlawreview.com/article/senate-bill-690-amended-california-scales-back-its-proposed-cipa-overhaul
- [S] Skadden, "CIPA Is Still a Mess": https://www.skadden.com/insights/publications/2026/06/cipa-is-still-a-mess
- [S] Assembly committee analysis of SB 690: https://apcp.assembly.ca.gov/system/files/2026-06/sb-690-caballero-apcp-analysis.pdf

**US privacy, biometrics, AI and employment statutes**
- [F] Washington MHMDA definitions, RCW 19.373.010: https://app.leg.wa.gov/RCW/default.aspx?cite=19.373.010
- [F] Colorado HB24-1130: https://leg.colorado.gov/bills/hb24-1130
- [F] Holland & Knight, Colorado SB 26-189: https://www.hklaw.com/en/insights/publications/2026/05/colorado-governor-signs-sb-189
- [S] Baker Botts, Colorado repeals and replaces AI Act: https://ourtake.bakerbotts.com/post/102msga/colorado-repeals-and-replaces-ai-act
- [F] CPPA, CCPA regulation updates: https://cppa.ca.gov/regulations/ccpa_updates.html
- [R] BIPA, 740 ILCS 14: https://www.ilga.gov/legislation/ilcs/ilcs3.asp?ActID=3004&ChapterID=57
- [R] Cal. Penal Code §632: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=PEN&sectionNum=632
- [R] 18 U.S.C. §2511: https://www.law.cornell.edu/uscode/text/18/2511
- [R] NY Civil Rights Law §52-c: https://www.nysenate.gov/legislation/laws/CVR/52-C
- [R] HIPAA de-identification, 45 CFR 164.514: https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-E/section-164.514
- [R] ABA Formal Opinion 512: https://www.americanbar.org/content/dam/aba/administrative/professional_responsibility/ethics-opinions/aba-formal-opinion-512.pdf

**Financial services**
- [F] FINRA Regulatory Notice 24-09: https://www.finra.org/rules-guidance/notices/24-09
- [F] FINRA 2026 Annual Regulatory Oversight Report, GenAI: https://www.finra.org/rules-guidance/guidance/reports/2026-finra-annual-regulatory-oversight-report/gen-ai
- [F] SEC press release 2025-6 (off-channel, $63.1M): https://www.sec.gov/newsroom/press-releases/2025-6

**EU AI Act**
- [F] Article 50: https://artificialintelligenceact.eu/article/50/
- [F] Annex III: https://artificialintelligenceact.eu/annex/3/
- [F] Article 3 (definitions): https://artificialintelligenceact.eu/article/3/
- [F] Cooley, Digital AI Omnibus (Reg. (EU) 2026/1744): https://cdp.cooley.com/digital-ai-omnibus-delays-key-deadlines-introduces-new-rules/
- [F] Jones Walker, "August 2 still matters": https://www.joneswalker.com/en/insights/blogs/ai-law-blog/yes-august-2-still-matters-the-eu-approved-a-high-risk-ai-delay-but-most-trans.html?id=102nbon
- [F] CMS, Commission guidelines on prohibited AI practices (part II): https://cms.law/en/gbr/legal-updates/eu-commission-issues-guidelines-on-prohibited-ai-practices-part-ii
- [R] Commission guidelines on prohibited AI practices: https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-prohibited-artificial-intelligence-practices-defined-ai-act
- [R] EDPB Guidelines 02/2021 on virtual voice assistants: https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-022021-virtual-voice-assistants_en
- [R] ICO, Monitoring workers: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/employment/monitoring-workers/
- [R] German StGB §201: https://www.gesetze-im-internet.de/stgb/__201.html
- [R] BetrVG §87: https://www.gesetze-im-internet.de/betrvg/__87.html

**India**
- [F] DLA Piper Data Protection Laws of the World, India (DPDP Act and Rules 2025): https://www.dlapiperdataprotection.com/index.html?t=law&c=IN
- [F] CERT-In Directions under s.70B(6), 28 Apr 2022 (primary PDF): https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf
- [F] RBI, Storage of Payment System Data (6 Apr 2018): https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11244&Mode=0
- [F] SEBI CSCRF circular (20 Aug 2024): https://www.sebi.gov.in/legal/circulars/aug-2024/cybersecurity-and-cyber-resilience-framework-cscrf-for-sebi-regulated-entities-res-_85964.html

**Platforms**
- [F] Microsoft Graph `call: updateRecordingStatus` (media restriction): https://learn.microsoft.com/en-us/graph/api/call-updaterecordingstatus?view=graph-rest-1.0
- [F] Microsoft APIs Terms of Use (Oct 2025): https://learn.microsoft.com/en-us/legal/microsoft-apis/terms-of-use
- [F] Teams Store validation guidelines: https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/deploy-and-publish/appsource/prepare/teams-store-validation-guidelines
- [F] Application-hosted media bots (Azure/Windows requirement): https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots
- [R] Teams explicit recording consent (returned 404): https://learn.microsoft.com/en-us/microsoftteams/explicit-recording-consent
- [F] Apple App Store Review Guidelines (2.5.4, 2.5.14, 5.1.2(i)): https://developer.apple.com/app-store/review/guidelines/
- [F] Google Play Malware policy (spyware, stalkerware): https://support.google.com/googleplay/android-developer/answer/9888380
- [F] Google Meet Media API overview: https://developers.google.com/workspace/meet/media-api/guides/overview

**Cross-track PersonaAgent documents** [X]
- `docs/research/02-integration-surfaces-and-meeting-capture.md`: Teams bot detection MC1251206, admin consent
- `docs/research/10-security-threats-and-redaction.md`: Tier-R/P/S/C model, Aadhaar Verhoeff detection, FF3 withdrawal, CPRA email-contents SPI
- `docs/research/_raw/08c-ai-memory-wearables-factsheet.md`: Bee LED/no-audio-storage, Limitless wind-down
- Coordinator-relayed cross-track facts: DPDP dates, Microsoft consent policy, India in-region model availability, persona-impersonation threshold, the "PersonaAgent" ACL 2026 name collision
