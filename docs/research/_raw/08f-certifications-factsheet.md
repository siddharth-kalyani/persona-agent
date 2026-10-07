# 08f: Certifications, compliance and social-acceptability fact sheet (raw input)

Prepared on 2026-10-06 as input to `08-ai-hardware-lessons.md`, Section D.

**Scope.** A future body-worn recorder that is always listening, used for work only and governed by the customer company. The radio is BLE, possibly with Wi-Fi. v1 markets are the US and India; the EU and UK come later.

**Method.** The WebSearch budget ran out. **Verified** means the page was fetched in this session. **Unverified (memory)** means it was not. All costs and lead times are estimates, not quotes. Confidence is rated High, Med or Low.

## 1. US: the FCC path

| # | Claim | Ref | Source | Conf. |
|---|---|---|---|---|
| 1.1 | A BLE/Wi-Fi transmitter is a Part 15 intentional radiator. It needs **Certification** (an FCC ID) issued by a **TCB** after testing at an FCC-recognized lab. | §15.201(b), §15.247, §2.960 | unverified (memory) | High |
| 1.2 | **Modular approval:** a host built on a module with a modular grant can carry the label "Contains FCC ID: …". | §15.212 | law.cornell.edu/cfr/text/47/15.212 (confirmed by parent) | High |
| 1.3 | The host still needs **Part 15B** compliance via an **SDoC**, and the responsible party must be **US-located**. | §2.906, §2.1077 | unverified (memory) | Med-High |
| 1.4 | **Catch:** many module grants cover only *mobile* use (20 cm or more from the body). A body-worn host is *portable*, so it needs its own RF-exposure evaluation. It may also need a Class II permissive change or its own FCC ID. | KDB 996369 | unverified (memory) | Med |
| 1.5 | **Portable** = the radiating structure is "within 20 centimeters of the body of the user". | §2.1093(b) | https://www.law.cornell.edu/cfr/text/47/2.1093 (verified) | High |
| 1.6 | **SAR limits:** 1.6 W/kg over any 1 g; 4 W/kg over 10 g for extremities; 0.08 W/kg whole-body. | §1.1310(c) | https://www.law.cornell.edu/cfr/text/47/1.1310 (verified) | High |
| 1.7 | **Blanket exemption:** available maximum time-averaged power of **1 mW or less**, "regardless of separation distance". | §1.1307(b)(3)(i)(A) | https://www.law.cornell.edu/cfr/text/47/1.1307 (verified) | High |
| 1.8 | A **SAR-based exemption formula** covers 0.5–40 cm and 0.3–6 GHz. With multiple transmitters, evaluation is required if the summed exemption ratio exceeds 1. | §1.1307(b)(3)(i)(B) | as above (verified) | High |
| 1.9 | **Formula as recalled:** P_th = ERP_20cm·(d/20)^x, where x = −log10(60/(ERP_20cm·√f GHz)) and ERP_20cm = 3060 mW for 1.5–6 GHz. At **2.45 GHz** that gives **≈2.7 mW at 0.5 cm, ≈10 mW at 1 cm and ≈38 mW at 2 cm**. | my calculation | formula unverified (memory) | Med |
| 1.10 | **Design implications:** BLE at 0 dBm or less is exempt. At +4 dBm, 5 mm of separation or more is probably exempt. At +8 dBm, about 8 mm is needed. Body-worn Wi-Fi at 15–18 dBm will probably need **SAR testing**. | estimate | derived from rows 1.7–1.9 | Med |
| 1.11 | Foreign grantees must name a **US agent** for service of process. 2025 FCC rules restrict TCBs and labs controlled by "foreign adversaries", so confirm the lab's recognition. | §2.911(d); ET Docket 24-136 | unverified (memory) | Med-Low |
| 1.12 | **ISED Canada (optional):** RSS-Gen, RSS-247 and RSS-102 through an ISED-recognized certification body. US labs usually bundle it. | — | unverified (memory) | Med |
| 1.13 | No federal **safety** certification is mandatory. Procurement and retail expect an IEC/UL 62368-1 CB report and an NRTL-listed charger. | — | unverified (memory) | Med |

**Indicative US cost and lead time (estimates)**

| Route | Cost (USD) | Lead time |
|---|---|---|
| A. Pre-certified BLE module whose grant covers portable use, plus Part 15B SDoC and an RF-exposure memo | 2k–6k | 2–4 weeks |
| B. Own radio, or module grant needs a Class II permissive change: Part 15C BLE tests, TCB grant and 15B | 8k–20k | 4–8 weeks, including 1–2 weeks of TCB review |
| Add SAR (Wi-Fi, or BLE above ≈2.7 mW at 5 mm) | +5k–15k | +2–4 weeks |
| Add ISED | +2k–5k | +1–3 weeks |

**Recommendation:** route A, with a BLE-only radio at +4 dBm or less and a module grant that explicitly covers portable/body-worn use.

## 2. India: BIS CRS, WPC ETA and MTCTE

| # | Claim | Source | Conf. |
|---|---|---|---|
| 2.1 | **Relevant CRS categories:** Smart watches, IS 13252 (Part 1):2010 (#44). Wireless headphones/earphones, IS 616:2017 (#56). Li-ion sealed secondary cells/batteries, **IS 16046 (Part 2):2018** (#30). Power banks (#21). Power adaptors for IT, IS 13252 (Part 1) (#27). Power adaptors for AV, IS 616 (#26). SMPS up to 48 V (#59). CCTV cameras/recorders (#41). | https://www.crsbis.in/BIS/products-bis.do (verified 2026-10-05) | High |
| 2.2 | A badge or clip voice recorder does **not obviously fit a notified category**. The **cell and battery pack (IS 16046-2)** are in scope, and so is the **adapter if bundled**. So ship a USB-C cable only and buy cells with existing BIS R-numbers. | my interpretation; confirm with BIS | Med-Low |
| 2.3 | Foreign manufacturers need an **Authorised Indian Representative (AIR)**. Registration is per factory. PersonaAgent India could act as the AIR for an overseas ODM, and making the device in India removes the need. | AIR confirmed by parent (Wikipedia); the rest unverified (memory) | Med-High / Med |
| 2.4 | CRS testing must be done at **BIS-recognised labs in India**. | unverified (memory) | Med-High |
| 2.5 | **CRS fees:** about ₹1,000 to apply plus an annual fee in the tens of thousands of rupees. Registration is valid for about 2 years and can be renewed. | unverified (memory) | Low |
| 2.6 | **CRS timing:** 2–6 weeks of lab testing plus about 4–6 weeks of BIS processing, so **about 2–3 months** in total. | estimate | Low-Med |
| 2.7 | **WPC Equipment Type Approval (ETA)** is needed to import or sell BLE/Wi-Fi devices. De-licensed bands use **self-declaration** backed by accredited RF reports, which **can come from labs outside India**, so FCC and EN 300 328 data can be reused. Licensed bands need certification. | confirmed by parent (Wikipedia); details unverified (memory) | Med-High |
| 2.8 | The ETA portal **moved:** saralsanchar.gov.in now redirects (301) to **eservices.dot.gov.in/saral-sanchar**. | redirect seen 2026-10-06 (verified) | High |
| 2.9 | **ETA cost and timing:** about ₹10,000 per application and about 1–4 weeks to issue. | unverified (memory) / estimate | Low |
| 2.10 | **TEC MTCTE** covers telecom equipment. A BLE-only accessory is generally out of scope. An **LTE/eSIM variant** would probably bring in MTCTE plus the IMEI regime. | unverified (memory); the tec.gov.in fetch failed | Low-Med |
| 2.11 | Producers also need **EPR registration** under the E-Waste Rules 2022 and Battery Waste Management Rules 2022 (CPCB), plus **Legal Metrology** packaging labels. | unverified (memory) | Med |

**India estimate:**

- Battery-pack CRS: ₹1.5–4 lakh (≈US$1.8k–4.8k), covering the lab, BIS fees and a consultant.
- Device or adapter CRS: about the same again, only if in scope.
- ETA: ₹10k–50k.
- AIR: US$1k–3k a year.
- **Total: ≈US$4k–12k over 2–3 months**, run in parallel with the FCC work.

## 3. Battery and shipping

| # | Claim | Source | Conf. |
|---|---|---|---|
| 3.1 | **UN38.3** consists of eight tests (T1–T8): altitude, thermal, vibration, shock, external short, impact/crush, overcharge and forced discharge. A **test summary** must be available along the supply chain (since about 2020). | unverified (memory) | High (tests) / Med (date) |
| 3.2 | **IEC 62133-2:2017** is the portable Li cell safety standard, and IS 16046 (Part 2):2018 is based on it. | unverified (memory) | Med-High |
| 3.3 | **IATA:** batteries contained in or packed with equipment ship as UN3481 (PI 967/966); standalone batteries as UN3480 (PI 965). Section II covers cells up to 20 Wh and batteries up to 100 Wh, so a wearable cell of ≈0.3–1.5 Wh qualifies. | unverified (memory) | Med-High |
| 3.4 | From January 2025, IATA added a packaging requirement for batteries packed with or contained in equipment (PI 966-II, 967-I/II, 969-II, 970-I/II), "as an additional measure for non-UN Specification packaging". | https://www.iata.org/en/programs/cargo/dgr/lithium-batteries/ (verified) | High |
| 3.5 | **State of charge 30% or less:** mandatory for UN3480 since 2016. As recalled, it was extended to batteries packed with equipment from 1 Jan 2026. | unverified (memory) | Med-Low |
| 3.6 | **Cost:** UN38.3 plus IEC 62133-2 runs ≈US$3k–10k per cell/pack, and the vendor often supplies it. Buy a cell or pack that already has UN38.3, IEC 62133-2 and BIS IS 16046-2. | estimate | Low-Med |

## 4. Bluetooth SIG qualification (verified; effective 1 Mar 2026)

| Tier | Annual dues | Fee per product qualification |
|---|---|---|
| Adopter | $0 | $12,000 |
| Contributing Adopter (new) | $3,500 small / $16,500 large | $8,000 for the first each year, then $12,000 |
| Associate | $11,250 small / $52,500 large | $6,000 |

- **Source:** https://www.bluetooth.com/develop-with-bluetooth/qualification-listing/qualification-listing-fees/ (High).
- **No startup programme:** the page names none and gives no "small" revenue threshold.
- **Cheapest single product:** **$11,500 in year 1** as a small Contributing Adopter.

## 5. EU and UK (later, brief)

| # | Claim | Source | Conf. |
|---|---|---|---|
| 5.1 | **RED Delegated Regulation (EU) 2022/30**, Art. 3(3)(d)(e)(f), covers internet-connected radio equipment (including connection via a phone) and **wearables**. It has applied since **1 Aug 2025**. The **EN 18031-1/-2/-3:2024** standards were cited in the OJ via Implementing Decision (EU) 2025/138, with restrictions on password options and some other clauses. | unverified (memory); the EUR-Lex page did not render | Med-High |
| 5.2 | **Cyber Resilience Act:** in force **10 Dec 2024**; reporting obligations from **11 Sep 2026**; main obligations from **11 Dec 2027**. These cover secure design, vulnerability handling and updates for the support period. | https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act (verified) | High |
| 5.3 | **Battery Regulation 2023/1542, Art. 11:** from **18 Feb 2027**, portable batteries must be **removable and replaceable by the end user** with commercial tools and without heat or solvents. Derogations are narrow, e.g. washable devices for wet environments where needed for safety. This is a **design constraint for an EU SKU**. | unverified (memory) | Med |
| 5.4 | **EU AI Act Art. 5(1)(f)** bans **emotion recognition in the workplace** from 2 Feb 2025. Never infer emotions from employees' voices. | unverified (memory) | Med-High |
| 5.5 | In Germany, **works councils** must co-decide on technical devices that can monitor employees (BetrVG §87(1) No. 6). | unverified (memory) | High |
| 5.6 | **UK PSTI** has applied since **29 Apr 2024**. It requires no universal default passwords, a published route for vulnerability reports, and a published minimum security-update period. A statement of compliance must accompany the product, and OPSS enforces it. | https://www.gov.uk/government/publications/the-uk-product-security-and-telecommunications-infrastructure-product-security-regime (verified) | High |
| 5.7 | **PSTI penalties and scope:** fines up to £10m or 4% of global revenue. Scope is *consumer* products, so it is unclear whether an enterprise-only device is covered. The UK recognises CE marking indefinitely for most regimes, which makes UKCA optional. | unverified (memory) | Med |

## 6. Social acceptability, workplace norms and evidence on LEDs and mute switches

| # | Evidence | Source | Conf. |
|---|---|---|---|
| 6.1 | **Google Glass (2013–15):** the "Glasshole" backlash led to bar bans, and the consumer Explorer programme ended in Jan 2015. Face-worn cameras drive bystander hostility. | unverified (memory) | High |
| 6.2 | **Irish DPC and Italian Garante (Sep 2021):** questioned whether the Ray-Ban Stories LED actually warns bystanders, and asked Facebook to prove it was effective and to run awareness campaigns. | unverified (memory; DPC URL returned 404) | Med-High |
| 6.3 | **"I-XRAY" (Oct 2024):** Harvard students combined Meta Ray-Bans with face search to identify strangers live. LEDs alone don't reassure bystanders. | unverified (memory) | High |
| 6.4 | **Meta LED tampering:** Meta glasses block capture if the LED is covered, yet LED-disable mods were reported in 2025. The LED must be **hardware-tied and tamper-evident**. | unverified (memory) | Med-Low |
| 6.5 | **Humane AI Pin:** its "Trust Light" lit whenever the camera, mic or sensors were active, and it had no wake word (touch to engage). | unverified (memory) | Med |
| 6.6 | **Amazon Echo:** the mic-off button **electrically disconnects** the mics. In Mar 2025 Amazon removed the "Do Not Send Voice Recordings" option on some Echos. Changing privacy terms after sale erodes trust. | unverified (memory) | Med-High |
| 6.7 | **Pew (2014):** 53% of US adults said it would be a change for the worse if most people wore devices that constantly show them information about the world around them. | https://www.pewresearch.org/internet/2014/04/17/us-views-of-technology-and-the-future/ (URL from memory) | Med |
| 6.8 | **HCI bystander studies** (Denning, Dehlawi and Kohno, CHI 2014; Hoyle et al., UbiComp 2014): bystanders want to be notified or asked, and favour privacy-mediating tech. Lifeloggers self-censor in sensitive places. | unverified (memory) | Med |
| 6.9 | **US workplaces:** monitoring-notice laws exist, e.g. **NY Civil Rights Law §52-c (from 7 May 2022)**, CT §31-48d and DE tit. 19 §705. NLRB GC Memo 23-02 (Oct 2022) targets surveillance that chills protected activity. About a dozen states require all-party consent (e.g. CA PC §632; see 07-legal). | unverified (memory) | Med-High |
| 6.10 | **India:** DPDP Act 2023 §7(i) treats some employment purposes as legitimate use, and the DPDP Rules were notified in Nov 2025 with a ≈18-month phase-in. IT/BPO offshore centres often ban recording devices in client-secure zones (ISO 27001 physical controls). | unverified (memory) | Med / Low-Med |

**Form factors (analysis)**

- **Badge/lanyard clip:** best fits "work-only, company-governed". It reads as an ID badge, sits near the mouth, and shows its LED to others.
- **Pendant:** carries consumer-lifelogger baggage, as the Friend backlash showed.
- **Ring:** suits push-to-talk notes, not ambient capture.
- **Earbuds:** pick up mostly the wearer's own voice.
- **Glasses:** cause the most bystander friction. Use **no camera**.

**Hardware implications**

1. Wire the LED into the mic power/clock path so firmware cannot record unlit, and add an occlusion sensor.
2. Fit a physical mute slider that cuts mic power, with a distinct LED colour and haptic confirmation.
3. Give admins work-only policies: schedules, geofence or BLE-beacon auto-mute in secure zones, and per-meeting consent prompts.
4. No camera, no wake-word dependency, no emotion inference.

## 7. Indicative certification budget for US + India v1 (estimate)

Assumes BLE only, a pre-certified module, and no adapter in the box.

| Item | USD (estimate) |
|---|---|
| FCC route A (route B in brackets) | 2k–6k (8k–20k) |
| SAR, only if needed | 0 (5k–15k) |
| Bluetooth SIG (verified fee) | 11.5k–12k |
| UN38.3 + IEC 62133-2, if not supplied by the vendor | 0–10k |
| IEC 62368-1 CB report (procurement expectation) | 4k–10k |
| India CRS: pack, plus device/adapter if in scope | 2k–10k |
| India WPC ETA | 0.2k–1k |
| AIR, consultants, pre-scans and one re-test | 3k–10k |
| **Total** | **≈US$25k–60k** (+5k–15k if SAR), over **8–14 weeks** in parallel after design freeze |

- **LTE variant:** adds US carrier and PTCRB certification (plausibly US$50k–150k+) plus MTCTE and IMEI obligations in India. That is a strong reason to stay BLE-to-phone. Low-confidence estimate.
- **EU/UK later:** RED testing (EN 300 328 / 301 489 / 62368-1 / RF exposure / EN 18031), CRA readiness and the Art. 11 battery redesign come to ≈US$15k–40k (estimate).

## 8. Uncertainties / not verified

- **SAR formula and thresholds (rows 1.9–1.10):** the equation did not render on LII. Verify with the test lab against §1.1307(b)(3)(i)(B) and KDB 447498.
- **India CRS scope:** whether BIS would class a wearable voice recorder as a smart watch or wireless earphone, and whether batteries inside non-notified products need IS 16046-2 registration.
- **India fees and procedures:** CRS fees, validity and timing, ETA fee and timing, and MTCTE scope are all unverified, because the tec.gov.in, dot.gov.in and bis.gov.in fetches failed.
- **IATA 2026 state-of-charge changes:** unverified; only the 2025 packaging change was confirmed.
- **EU/UK details:** the EN 18031 OJ restrictions, the exact Art. 11 derogation wording, PSTI scope for business-only products, and UK CE recognition for radio equipment are all from memory.
- **FCC 2025 rules:** the lab-recognition ("bad labs") rules and the U.S. Cyber Trust Mark status are unverified.
- **Costs and lead times:** all are estimates. Get 2–3 lab quotes from labs in the US, Taiwan and India.
- **Section 6:** mostly from memory. Re-verify before citing it externally.
