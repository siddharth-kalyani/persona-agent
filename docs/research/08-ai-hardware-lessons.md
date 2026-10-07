# 08 — AI Hardware Lessons: Humane, Rabbit, the 2024–2026 AI-Wearables Wave, and PersonaAgent's Path to a Work Recorder

> **Track:** AI hardware lessons (Humane / Rabbit post-mortems, AI-wearables landscape, device strategy for Pillar 2)
> **Prepared:** 2026-10-06 (research run 2026-10-05/06) · **Audience:** PersonaAgent founding team
> **Founder decisions applied (Oct 2026):** (1) first buyer = Microsoft 365 mid-market & enterprise teams, per-seat B2B; (2) v1 regions = **United States and India** (EU/UK later); (3) team = 3–6 engineers, ~3-month **phone-first** MVP — hardware is a later move; (4) always-on recorder is **work-only and company-governed** (tenant-admin policies), no personal lifelogging in v1; (5) Phase-1 redaction tuned precisely to US and Indian regulatory requirements.
>
> **Confidence legend:** **High** = primary source (company/regulator/court) or ≥2 reputable outlets; **Med** = one reputable outlet or an unaudited vendor claim; **Low** = estimate, inference, or memory not re-confirmed this session. *Estimates are labelled as estimates.*
>
> **Method & limits:** The session's web-search budget ran out mid-research, and theverge.com, wired.com, nytimes.com and reuters.com could not be fetched. Facts originally reported by those outlets are taken from secondary coverage (Engadget, TechCrunch, MacRumors, Inverse, Fortune, Wikipedia reference lists) and marked as such. Vendor pages were read on 2026-10-05/06; vendor statements are claims, not audits.

---

## Executive summary

**Humane AI Pin failed because it tried to replace the phone and was worse than the phone at everything.** **(High)**
- **Funding and price:** about $230M raised. $699 + $24/mo for a T-Mobile line, US-only.
- **Timeline:** announced 9 Nov 2023, shipped Apr 2024 after a slip.
- **Reviews:** ~6 s answers, repeated thermal shutdowns, 4–5 h battery, a projector unreadable in sunlight.
- **Sales:** ~10,000 units vs a 100,000 target, ~$9M in sales, and returns exceeding new sales May–Aug 2024. Returns couldn't be refurbished (carrier lock).
- **Recall:** CPSC recalled ~10,500 Charge Cases for fire risk (31 Oct 2024).
- **Price cut:** to $499 (Oct 2024).
- **Exit:** HP bought the team, CosmOS and IP for **$116M** (18 Feb 2025), about half the capital raised. **Every Pin was bricked on 28 Feb 2025 with 10 days' notice, customer data deleted, refunds only within 90 days.**
- **Root causes:** no killer use case; cloud-only latency; thermal and battery limits; a hardware + carrier-subscription model; hype ahead of readiness (TED, Paris runway, TIME award before shipping); and a culture that, per the NYT, discouraged criticism.

**Rabbit R1 failed as hardware.** **(High)**
- **Launch:** $199, no subscription, unveiled at CES on 9 Jan 2024. 10,000 preorders in 24 h; Rabbit claimed >100,000 units by May 2024.
- **The "Large Action Model":** turned out to be an Android 13 app plus cloud-run browser (VNC) sessions.
- **Security:** fleet-wide **API keys were hard-coded** (exposed by Rabbitude, Jun 2024), and the device kept undeletable chat logs.
- **Usage:** only **~5,000 daily users (~5%)** by Sep 2024.
- **Since then:** Rabbit pivoted to software (Rabbit Intern at $99.99/mo, rabbitOS 2 in Sep 2025, rabbitOS 3 in Sep 2026) amid reported payroll arrears. **Its India launch stalled on unnamed "regulation complications" despite units being ready in May 2024.**

**What worked in 2024–2026: companions with one job, not general assistants.**
- **Plaud** is the clear winner. It is recorder-first, claims 2.5M+ professional users, monetises by minutes ($17.99–$29.99/mo), sells a **Team plan at $20–35/user/mo**, and offers a **Device SDK + Transcription API** (but no India cloud region). **(High for offering; Med for traction)**
- **Ray-Ban Meta** is the mass-market winner (millions of units; exact figures not re-verified): a fashion-brand phone companion with a visible LED and no subscription.
- **Bee** (bought by Amazon, Jul 2025) and **Limitless** (bought by Meta, 5 Dec 2025) were absorbed by Big Tech. **Limitless stopped sales the same day and cut off service in 7 jurisdictions with 14 days to export.** **(High)**
- **Friend's** always-listening companion drew public backlash (vandalised >$1M subway campaign).
- The OpenAI/io device has **slipped to 2027**, and OpenAI dropped the "io" name. **(Med: Wired via Wikipedia)**

**The market has moved from "always-on" to press-to-record with visible indicators:** Bee (button + green LED), Pebble Index 01 and Sandbar Stream (record only while pressed or touched), Meta (tamper-checked capture LED). PersonaAgent's "always-on" pillar should be expressed as **always-ready, policy-windowed work capture**, matching founder decision #4. **(High for trend)**

**The strongest reason for PersonaAgent to build its own device is a platform gap (cross-track, High).** iOS and Android don't let an app start the mic from the background. A **BLE badge with its own mic, button, LED and flash buffer** can start capture itself and hand audio to the phone as BLE data, not as phone-mic input.
- Apple's Core Bluetooth guide and Android's companion-device and foreground-service rules support this. **(High for the platform rules)**
- On iOS the app only gets **~10 s wake windows**, so the badge must **buffer and forward** rather than stream live.
- A **2-week spike** should confirm it on iOS and the main Android OEMs (Samsung, Xiaomi, Vivo/Oppo). **(Med until prototyped)**
- Note that AirPods and standard headsets do *not* get around the rule.

**Recommended path: phone-first, integrate before building, badge last.**
- **Phase 0 (months 0–3):** software only.
- **Phase 1 (3–9):** bring-your-own devices (Plaud SDK, Omi open protocol, headsets) plus the BLE spike.
- **Phase 2 (9–15):** 100–500 pilot badges running our firmware.
- **Phase 3 (15–30):** production **enterprise badge/clip**, sold only as **hardware-as-a-service inside a "Capture+" seat** (illustrative +$6–10/user/month; estimate).
- **Cost:** indicative badge BOM ≈ **$15–33 ex-factory / $18–46 landed** at 10k units, on an nRF5340-class design (estimate). Prototype to mass production takes ≈ 9–15 months, plus slack.
- **Go/no-go gates (§6):**
  - G1: ≥500 paid seats and ≥40% weekly capture use.
  - G2: ≥2,000 seats, ≥50% weekly use, BYO-device users capturing ≥1.5× more, and ≥300 devices under pilot letters of intent.
  - G3: ≥5,000 seats, ≥3 customers committing ≥1,000 devices, pilot wear ≥3 days/week, fully-loaded unit cost ≤ ~$60.

**Non-negotiable trust design:**
- a hardware mute switch and a recording LED wired to the mic power;
- a start chime;
- no camera, no voiceprints;
- per-device keys, secure boot, signed OTA, encrypted flash;
- **contractual no-brick terms:** ≥12-month end-of-life notice, ≥3 years of security updates, offline USB export in open formats, a published protocol, firmware escrow, and a change-of-control clause.

**US + India certification (§4.12).** Assumes a BLE-only badge on a pre-certified module, with no adapter in the box.
- **Cost and time:** ≈ **US$25k–60k** and **~8–14 weeks** after design freeze (estimate). That includes the **Bluetooth SIG listing fee of $11.5k–12k** (verified, 2026 schedule).
- **US:** FCC Part 15.
  - The module route (§15.212) avoids a full radio certification, but the module's grant must cover **body-worn (portable) use**.
  - A ≤1 mW time-averaged radio is exempt from RF-exposure evaluation.
  - Keeping BLE at ≤ +4 dBm should avoid SAR testing (our calculation).
- **India:** **WPC ETA** (self-declaration for Bluetooth); **BIS CRS** covers Li-ion cells (IS 16046-2) and adapters.
  - A badge recorder is **not obviously a CRS-listed category**, so ship a USB-C cable only and use BIS-registered cells.
  - Foreign makers need an **Authorised Indian Representative**, and CRS testing happens in India.
  - Start **≥6 months ahead** of shipping (the Rabbit lesson).
- **LTE would add $50k–150k+** of carrier certification, which is one more reason to stay BLE-only.

---

## 1. Humane AI Pin (2018–2025): the full story

**One-line verdict:** Humane spent about $230M building a cloud-dependent, carrier-locked phone replacement. It did nothing better than a phone and many things worse: ~6 s answers, thermal shutdowns, 4–5 h battery. It shipped ~10% of its first-year unit target and sold its team and IP to HP for $116M. Then it bricked every customer's device with 10 days' notice.

### 1.1 Timeline

| Date | Event | Source | Conf. |
|---|---|---|---|
| 2018 | Founded in San Francisco by ex-Apple Imran Chaudhri (design/UI) and Bethany Bongiorno (software; CEO); out of stealth 2021 | [Wikipedia](https://en.wikipedia.org/wiki/Humane_Inc.), [TechCrunch 2023](https://techcrunch.com/2023/03/08/humane-the-secretive-ai-startup-founded-by-ex-apple-employees-raises-another-100m/) | High |
| Sep 2021 | $100M Series B | [TechCrunch 2021](https://techcrunch.com/2021/09/01/humane-a-stealthy-hardware-and-software-startup-co-founded-by-an-ex-apple-designer-and-engineer-raises-100m/) (via Wikipedia) | Med-High |
| 8 Mar 2023 | $100M Series C led by Kindred Ventures (with SK Networks, LG Technology Ventures, Microsoft, Volvo Cars Tech Fund, Tiger Global, Qualcomm Ventures, Sam Altman). Total raised ≈ **$230M**; ~200 staff | [TechCrunch](https://techcrunch.com/2023/03/08/humane-the-secretive-ai-startup-founded-by-ex-apple-employees-raises-another-100m/) | High |
| ~20 Apr 2023 | TED2023 demo by Chaudhri (video public ~9 May) | [Axios](https://www.axios.com/2023/04/21/humane-ai-powered-wearable) | Med |
| 30 Sep 2023 | Runway debut at Paris Fashion Week (Coperni) | [TechCrunch](https://techcrunch.com/2023/09/30/humanes-ai-pin-debuts-on-the-paris-runway/) | High |
| Oct 2023 | Named one of TIME's Best Inventions of 2023, **six months before shipping** | [TIME](https://time.com/collection/best-inventions-2023/6327143/humane-ai-pin/) | High |
| 9 Nov 2023 | Official announcement: $699 + $24/month; preorders from 16 Nov | Wikipedia ([Ai Pin](https://en.wikipedia.org/wiki/Ai_Pin)) | High |
| 9–10 Jan 2024 | ~10 staff (~4%) cut for "budget reductions"; CTO Patrick Gates moved to an advisory role | [Engadget](https://www.engadget.com/humane-lays-off-staff-before-its-ai-pin-begins-shipping-103548514.html) | High |
| 23 Feb 2024 | Shipping slips from March to mid-April | [TechCrunch](https://techcrunch.com/2024/02/23/humane-pushes-ai-pin-ship-date-to-mid-april/) | High |
| 11 Apr 2024 | Reviews published (The Verge, MKBHD, Inverse, Engadget…) | [Inverse](https://www.inverse.com/tech/humane-ai-pin-in-depth-review) | High |
| 22 May 2024 | Bloomberg: Humane exploring a sale at **$750M–$1B** | [Bloomberg](https://www.bloomberg.com/news/articles/2024-05-22/wearable-ai-startup-humane-is-said-to-explore-potential-sale) (via TechCrunch/Fortune) | High |
| Jun 2024 | Customers told to stop using the Charge Case (battery-cell supplier problem). Exact advisory date unverified | [Liliputing](https://liliputing.com/humane-ai-pin-gets-a-200-price-cut-still-costs-499-24-monthly-subscription/) | Med |
| 6 Jun 2024 | NYT investigation into culture and launch readiness ("'This Is Going to Be Painful': How a Bold A.I. Device Flopped") | [NYT](https://www.nytimes.com/2024/06/06/technology/humane-ai-pin.html) (via Wikipedia; not fetchable) | Med-High |
| 7 Aug 2024 | The Verge: **returns outpacing sales**; ~10,000 units sold vs 100,000 target | via [MacRumors](https://www.macrumors.com/2024/08/07/humane-ai-pin-returns), [Engadget](https://www.engadget.com/ai/people-are-returning-humane-ai-pins-faster-than-the-company-can-sell-them-191523105.html) | High |
| 23–24 Oct 2024 | Price cut to **$499** (Charge Case no longer included); $24/mo unchanged | [Liliputing](https://liliputing.com/humane-ai-pin-gets-a-200-price-cut-still-costs-499-24-monthly-subscription/) | High |
| 31 Oct 2024 | CPSC recall No. 25-026: ~10,500 Charge Cases (fire hazard) | [CPSC](https://www.cpsc.gov/Recalls/2025/Humane-Recalls-Charge-Case-Accessory-for-Ai-Pin-Due-to-Lithium-Battery-Fire-Hazard) | High |
| 18 Feb 2025 | **HP buys Humane's team, CosmOS platform and IP for $116M**; AI Pin discontinued | [Bloomberg](https://www.bloomberg.com/news/articles/2025-02-18/hp-116-million-deal-for-humane-includes-ip-but-no-ai-pin-device), [The Verge](https://www.theverge.com/news/614883/humane-ai-hp-acquisition-pin-shutdown), [Fortune](https://www.fortune.com/2025/02/19/hp-humane-deal-ai-pin-shutting-down) | High |
| 27 Feb 2025 | Refund-request deadline | [Humane consumer FAQ](https://support.humane.com/hc/en-us/articles/34243204841997-Ai-Pin-Consumers-FAQ) (now offline); Engadget; Fortune | High |
| **28 Feb 2025, 12:00 PT** | Servers off: calls, texts, AI queries and cloud access end, and customer data is deleted. Only offline basics (e.g., battery level) keep working | TechCrunch; Engadget; [Ars Technica](https://arstechnica.com/gadgets/2025/02/truly-a-middle-finger-humane-bricking-700-ai-pins-with-limited-refunds/) | High |

### 1.2 Product, pricing and architecture

| Item | Detail | Conf. |
|---|---|---|
| Price | $699 device + **$24/month** (own phone number on T-Mobile 4G LTE, calls/texts, "unlimited" AI queries, cloud storage; TIDAL trial). US only. No native phone app, only a browser portal ("Humane.Center") | High |
| SoC | Qualcomm Snapdragon **720G**, "a four-year-old chipset" (Inverse); Engadget says only "Snapdragon" | Med |
| Display | Monochrome green **"Laser Ink"** projector onto the palm (720p). Usable indoors, poor in sunlight; projector sessions capped at ~9 min for thermal reasons | Med |
| Camera / input | 13 MP ultra-wide camera; touchpad + palm gestures (Inverse: ~5 days to learn); touch-to-talk, no wake word *(memory)* | Med-High |
| Power | Front unit + magnetic rear "Battery Booster" (two included) + Charge Case. Measured 4–5 h on the Pin alone, 8–9 h with a booster | Med-High |
| Software | **CosmOS**, a custom Android distribution; almost everything (AI, calls, messages, storage) depends on the cloud; OpenAI models on Microsoft Azure | High |
| Missing at launch | Timers, alarms, calendar, navigation, time-based reminders, email, photo sharing via SMS; voice notes capped at 30 s | High |

### 1.3 Reviews and measured problems

- **The Verge (David Pierce):** *"After many days of testing, the one and only thing I can truly rely on the AI Pin to do is tell me the time."* (quote via Wikipedia; widely remembered score 4/10 not re-confirmed). **(Quote Med-High)**
- **MKBHD:** video titled *"The Worst Product I've Ever Reviewed… For Now"*, citing slowness, unreliability and battery. **(High for title)**
- **Inverse (Raymond Wong):** ~**6 s** to answer "What's the weather?". The Pin overheated "at least a dozen times" in a week, with multi-minute thermal shutdowns. Photos were poor, and the Vision beta hallucinated. Verdict: the "textbook definition of a first-generation product". **(High)**
- **Engadget:** *"the solution to none of technology's problems."* **Fast Company:** *"Almost everything about the pin was a UX disaster."* **(Med-High)**
- The November 2023 launch video contained factual errors (eclipse location, almond nutrition) and was later edited. **(Low: memory, not re-confirmed)**

### 1.4 Commercial results and the recall

- **Target vs actual:** internal target of **100,000 units in year one**. By August 2024 roughly **10,000** had shipped, ~7,000 remained with customers, total sales were ~**$9M**, and ~**$1M** had been returned. From May to August 2024 **returns exceeded new sales**, and 1,000+ preorders were cancelled after the reviews. Humane cited unspecified "inaccuracies". **(High, as reported by The Verge via MacRumors/Engadget)**
- **Returned units became e-waste:** T-Mobile restrictions prevented reassigning a returned Pin to a new customer, so Humane could not refurbish or resell returns. **(High, as reported)**
- **Charge Case recall:** a battery-cell supplier "no longer" met Humane's quality standards. CPSC recall 25-026 (31 Oct 2024) covered ~**10,500** units sold Nov 2023–May 2024, with one case overheating or melting while charging and no injuries. The remedy was a $129–$149 refund or a replacement in 3–6 months. After the shutdown, CPSC lists the remedy as *unavailable*, Humane as "no longer in business", and tells owners to "destroy and discard". **(High)**
- **Simple arithmetic (inputs High):** ~$9M lifetime hardware sales against ~$230M raised. The $116M exit is ≈ **0.5×** capital raised and ≈ **1/7** of the $750M–$1B price sought nine months earlier.

### 1.5 The exit: HP deal, shutdown, refunds

- **What HP bought ($116M):** most employees, the CosmOS software platform and IP (Wikipedia says "300+ patents and applications": **Med**). The AI Pin business was **excluded**. The team became **HP IQ**, *"an AI innovation lab focused on building an intelligent ecosystem across HP's products and services for the future of work"* (TechCrunch). Both founders joined HP; their titles were not verified. **(High)**
- **Shutdown:** 10 days' notice. On 28 Feb 2025 at 12:00 PT, calling, messaging, AI queries and cloud access ended, the support desk closed, and **all customer data was deleted**. Users had to download it before the deadline. **(High)**
- **Refunds:** only for devices still inside the 90-day return window (shipped on/after ~15 Nov 2024), requested by 27 Feb 2025, plus Charge Case refunds for people waiting on replacements. **Everyone else got nothing.** Ars Technica's headline called it *"truly a middle finger"*. **(High)**
- **Enterprise relevance:** HP IQ's "future of work" remit makes HP a plausible future competitor or partner in AI-assisted work devices. **(Med: inference)**

### 1.6 Root-cause analysis

| Dimension | What went wrong | Evidence | Lesson for PersonaAgent |
|---|---|---|---|
| **Product** | Positioned as "the device that comes after the smartphone" yet better than the phone at nothing; no killer use case; launched without basics | NYT framing (Nov 2023); missing timers/calendar/navigation; no phone app; "the one and only thing I can truly rely on… is tell me the time" | Lead with one job users already do (meeting and conversation memory). The device is an **accessory to the phone and to Teams**, never a replacement. |
| **Technology** | Cloud round-trips on every query plus an old SoC gave ~6 s answers. A sealed, tiny thermal envelope with a laser projector caused shutdowns; 4–5 h battery; projector unreadable in sun | Inverse measurements; 9-min projector cap; NYT: demo units chilled with ice packs | No screen, no projector, no LTE, no on-device LLM. A low-power mic + MCU + BLE "dumb capture" device; heavy compute on phone and cloud, where latency doesn't block the wearer. |
| **Business model** | $699 + $24/mo with a mandatory T-Mobile line. Carrier lock blocked refurbishment, turning returns into e-waste. US-only | $288/yr subscription; T-Mobile restriction | Fold hardware into the enterprise seat (HaaS). No cellular, so no carrier dependence. Design for refurbish/re-issue across a fleet. |
| **Go-to-market** | Hype ran far ahead of readiness: TED, runway and TIME award before shipping; staged demos; date slipped | TED/Paris/TIME timeline; edited launch video; ice-packed demo units | Sell through **design-partner pilots with measured metrics**, not keynotes. Publish measured battery, latency and accuracy figures. |
| **Organisation** | Leadership discouraged criticism; a senior engineer who questioned launch readiness was fired; CTO stepped back months before launch | NYT 6 Jun 2024 (via Wikipedia); Engadget Jan 2024 | Formal launch-readiness gates owned by engineering and security, with a "red team" review. Dissent is a gate input, not a firing offence. |
| **Trust / lifecycle** | Bricked devices with 10 days' notice, deleted data, refunds only within 90 days; a recall that outlived the company | TechCrunch/Engadget/CPSC | Contractual **no-brick commitments**: end-of-life notice, export, offline mode, open protocol, escrow. Enterprise RFPs will ask for these. |


## 2. Rabbit R1 (2023–2026): the full story

**One-line verdict:** Rabbit sold a cheap, beautifully designed $199 box on the promise of a "Large Action Model" that would operate your apps. What shipped was an Android launcher plus cloud-scripted browser sessions, with fleet-wide API keys hard-coded in the code. Five months after shipping, only ~5% of buyers used it daily. It survived by pivoting to software (web agents, rabbitOS 2/OS3), amid reported payroll trouble.

### 2.1 Timeline

| Date | Event | Source | Conf. |
|---|---|---|---|
| Nov 2021 | Founder Jesse Lyu's earlier company, Cyber Manufacturing Co., raises $6M for the "GAMA" NFT project. Coffeezilla later alleged it was abandoned with ~$1M unrefunded; Rabbit said NFTs can't be "refunded" and that GAMA was "given back to the community" | [ReadWrite](https://readwrite.com/youtuber-coffeezilla-destroys-rabbit-r1-ai-company-in-latest-investigation/) | Med (allegations) |
| 4 Oct 2023 | $20M (Khosla Ventures, Synergis Capital, Kakao Investment) | [Rabbit](https://www.rabbit.tech/newsroom/rabbit-raises-20m), [TechCrunch](https://techcrunch.com/2023/10/04/rabbit-is-building-an-ai-model-that-understands-how-software-works/) | High |
| late 2023 | Cyber Manufacturing renamed Rabbit (~2 months before launch) | [Wikipedia](https://en.wikipedia.org/wiki/Rabbit_r1) | Med-High |
| 21 Dec 2023 | +$10M from Khosla, ≈ **$30M** total | [Rabbit](https://www.rabbit.tech/newsroom/rabbit-raises-additional-10m), [SiliconANGLE](https://siliconangle.com/2023/12/21/consumer-ai-startup-rabbit-raises-10m-khosla-ventures/) | High |
| 9 Jan 2024 | CES unveiling of R1, an "AI pocket companion" designed with Teenage Engineering: **$199, no subscription** | [Rabbit](https://www.rabbit.tech/newsroom/introducing-r1) | High |
| 10–11 Jan 2024 | **10,000 preorders in 24 h** (internal hope: 500); ~$10M in preorders soon after | [Shacknews](https://www.shacknews.com/article/138258/rabbit-r1-ai-companion-10000-sales), [MobileSyrup](https://mobilesyrup.com/2024/01/11/rabbit-r1-sold-10000-24-hours/), Fast Company (headline) | High |
| Mar–Apr 2024 | First shipments; NYC launch event ~23 Apr 2024 | Rabbit newsroom; date from memory | Med |
| 30 Apr–1 May 2024 | Android Authority runs the R1 launcher APK on a Pixel 6a: rabbitOS = AOSP Android 13 | [Android Authority](https://www.androidauthority.com/rabbit-r1-is-an-android-app-3438805/) | High |
| 3 May 2024 | Engadget review **40/100**. Rabbit claims ">100,000 units sold" and "idle battery performance improved up to 5x" | [Engadget](https://www.engadget.com/rabbit-r1-review-a-199-ai-toy-that-fails-at-almost-everything-161043050.html), [Rabbit Q1 update](https://www.rabbit.tech/newsroom/quarterly-update-2024-q1) | High |
| ~21 May 2024 | Coffeezilla investigation (GAMA history) | ReadWrite | Med |
| 18 Jun 2024 | Forbes: **130,000 units** sold, early bugs "mostly fixed" | [Forbes](https://www.forbes.com/sites/johnkoetsier/2024/06/18/rabbit-sells-130000-r1-units-says-early-bugs-mostly-fixed/) (headline via Wikipedia) | Med |
| 25–26 Jun 2024 | **Rabbitude discloses hard-coded API keys** | [Engadget](https://www.engadget.com/rabbit-r1-security-issue-allegedly-leaves-sensitive-user-data-accessible-to-anybody-120024215.html), [TechRadar](https://www.techradar.com/pro/security/rabbit-r1-jailbreakers-uncover-huge-security-flaws-including-some-that-let-internal-data-be-viewed-by-literally-anyone) | High |
| Jul 2024 | Device found storing all chats with no way to delete them; factory reset added afterwards | ZDNet via Wikipedia | Med |
| 30 Jul 2024 | Rabbit security update: an employee "who has since been terminated" leaked keys; secrets moved to AWS Secrets Manager; third-party pentest | [Rabbit](https://www.rabbit.tech/newsroom/security-pentest) | High (company account) |
| 13 & 21 Aug 2024 | EU/UK and Singapore launches | [Rabbit newsroom](https://www.rabbit.tech/newsroom) | High |
| 25–26 Sep 2024 | Lyu: **~5,000 daily users** out of ~100,000 buyers (~5%) | [9to5Google](https://9to5google.com/?p=642646); The Verge headline | High |
| 23 Sep–Oct 2024 | "LAM Playground" web agent | [TechCrunch](https://techcrunch.com/2024/09/23/rabbits-web-based-large-action-model-agent-arrives-on-r1-as-early-as-this-week/) | High |
| 21 Nov 2024 | Teach Mode beta | [Rabbit](https://www.rabbit.tech/newsroom/teach-mode-beta) | High |
| Jan 2025 → | Payroll paid late every month from Jan 2025; some staff/contractors unpaid from Jul 2025 (reported Nov 2025) | Tom's Guide via [Yahoo](https://finance.yahoo.com/news/next-rabbit-employees-haven-t-151201843.html) | High (that it was reported) |
| 13 Jun 2025 | **Rabbit Intern** web agent (no R1 needed): $99.99/mo for 30 tasks | [Rabbit](https://www.rabbit.tech/newsroom/rabbit-intern-launch) | High |
| 8 Sep 2025 | **rabbitOS 2**: card UI, "creations" (vibe-coded mini-apps), on-device Intern, **local meeting recordings with transcripts and AI summaries** | [Rabbit](https://www.rabbit.tech/newsroom/rabbitos-2-launch) | High |
| 6 Oct 2025 | Lyu asks users for "a second chance"; *"no one wants to carry around two devices"* | [Engadget](https://www.engadget.com/rabbit-plots-its-redemption-arc-120000271.html) | High |
| 13 Nov 2025 | 26 employees; Lyu says a "legally binding term" sheet is signed (investor unnamed). India launch stalled: *"we had R1 units ready in May last year. Then all of a sudden, there's some regulation complications"* | Tom's Guide via [Yahoo](https://finance.yahoo.com/news/next-rabbit-employees-haven-t-151201843.html) | High (statements) |
| 22 Sep 2026 | **rabbitOS 3**, an "agentic OS" for Windows/Mac/Linux PCs, cloud VMs, the R1 and an upcoming "cyberdeck"; memory stored on Rabbit servers | [Rabbit](https://www.rabbit.tech/newsroom/rabbitos-3-launch) | High (company claim) |

### 2.2 Product and the "Large Action Model" claims vs reality

- **Hardware:** MediaTek Helio P35, 4 GB RAM, 128 GB storage, 2.88" touchscreen, 8 MP rotating camera, Wi-Fi + SIM, scroll wheel. The battery drained while idle and wouldn't last a day at review time, until the "up to 5x" idle fix. **(High)**
- **Claim:** a "Large Action Model" (LAM) that learns and operates apps for you. At launch it had four integrations (Spotify, Uber, DoorDash, Midjourney). **Reality in reviews:** Uber failed to load, DoorDash was slow with thin menus, Midjourney often failed, and answers were wrong (weather when asked about traffic). Engadget called it *"a chunkier and dumber phone"* and *"Don't buy the R1."* MKBHD titled his review "barely reviewable" (~9M views). **(High)**
- **"It's an Android app":** Android Authority showed the launcher APK running on a Pixel. Lyu replied *"rabbit r1 is not an Android app"* and that *"rabbit OS and LAM run on the cloud with very bespoke AOSP and lower level firmware modifications."* **(High)** Both statements can be true. **The device was a thin Android client; the "intelligence" was cloud automation.**
- **What LAM actually was:** Rabbit's own security write-up refers to **"VNC sessions"**: third-party accounts were driven through cloud-hosted browser sessions that Rabbit controlled (High). Reports that the integrations were scripted Playwright automation rather than a novel model are widely repeated but **could not be re-verified** this session (Low).

### 2.3 Security incidents, through an enterprise security reviewer's eyes

- **Hard-coded keys (Jun 2024):** Rabbitude, which had codebase access from 16 May 2024, found **hard-coded keys** for ElevenLabs (TTS), Azure (speech), Yelp and Google Maps. These keys would allow reading *every R1 response ever given*, including personal data, bricking devices, altering responses and replacing the voice. A fifth key (email from an r1.rabbit.tech subdomain) was withheld. Rabbit said it learned of the issue on 25 Jun and was "not aware of any customer data being leaked". Revoking the ElevenLabs key temporarily broke devices, and Rabbitude alleged Rabbit had known for ~1 month. **(High)**
- **On-device data:** the R1 logged chats and pairing data with **no deletion option**, a lost-or-stolen risk. Factory reset and reduced log storage came only after press coverage. **(Med)**
- **The reviewer's red flags:**
  - secrets embedded in client code;
  - **fleet-wide, not per-device, credentials**;
  - an insider leak;
  - no remote wipe or crypto-erase;
  - third-party credentials and sessions living in vendor-run browsers (versus PersonaAgent's delegated OAuth to Microsoft Graph);
  - a disputed disclosure timeline.

  Any one of these would fail a typical enterprise security questionnaire.

### 2.4 Usage, evolution and status in 2026

- **Usage:** ~5,000 daily users vs ~100,000 buyers about five months after shipping (Lyu to Fast Company, Sep 2024). That was after 16 software updates. **(High)**
- **Evolution:** LAM Playground (Sep–Oct 2024), then Teach Mode (Nov 2024), then Rabbit Intern, a subscription web agent (Jun 2025, $99.99/mo), then rabbitOS 2 (Sep 2025), then rabbitOS 3 for PCs and VMs (Sep 2026). Rabbit is now a **software/agent company that happens to have a device**. rabbitOS 2's *local meeting recording with transcripts and summaries* shows meeting capture is becoming a commodity feature even on fringe devices. **(High)**
- **Status:** the R1 still works and is a supported OS3 device (company claim, Sep 2026). Reported payroll arrears through 2025, 26 staff, a signed but unconfirmed new round, and India revenue "derailed" by regulation. A January 2026 "new device" appeared only in search snippets and is **unverified**.

### 2.5 Root-cause analysis

| Dimension | What went wrong | Evidence | Lesson for PersonaAgent |
|---|---|---|---|
| **Overpromise** | Sold a capability (LAM) that didn't exist in robust form | Broken integrations at launch; Android app; VNC browser sessions | Demo only what a design-partner tenant runs today. Name model limits. No "magic" claims in sales material. |
| **Redundancy with the phone** | A second device doing phone things worse | ~5% daily use; CEO: *"no one wants to carry around two devices"* | The device must do something the phone **cannot** (see §4.2: background-start capture, all-day mic placement). |
| **Security culture** | Fleet-wide hard-coded keys; non-deletable logs; insider leak | Rabbitude; Rabbit's own write-up; ZDNet | Per-device identity, no secrets on device, secure boot, signed OTA, crypto-erase, a published vulnerability-disclosure policy before launch. |
| **Business model** | One-time $199 against open-ended cloud costs (Perplexity, ElevenLabs, LLMs); later a $99.99/mo agent; payroll stress | Rabbit Intern pricing; Tom's Guide | Recurring per-seat revenue that covers AI COGS (≈$15–27/user-month across tracks). Hardware priced inside the seat. |
| **Founder credibility** | GAMA history amplified every problem | Coffeezilla/ReadWrite | Enterprise buyers diligence founders. Be transparent, keep audits current, publish a trust centre. |
| **Regulatory readiness** | India launch stalled on unnamed regulatory problems with units ready in May 2024 | Lyu, Nov 2025 | **Start BIS CRS / WPC ETA work before the first India hardware commitment.** Never let cash flow depend on a hardware launch date. |


## 3. The wider field, 2024–2026: what worked, what didn't, and why

### 3.1 Memory pendants and AI voice recorders

| Device (company) | Price & plan | Capture model / specs | Traction & status (Oct 2026) | Lesson for us | Conf. |
|---|---|---|---|---|---|
| **Limitless Pendant** (ex-Rewind AI; >$33M from a16z, First Round, NEA) | $99 | Always-on pendant streaming to phone app | **Meta acquired Limitless on 5 Dec 2025** (price undisclosed) and folded the team into Reality Labs wearables. **Pendant sales stopped the same day.** Existing users are supported "for at least another year" and moved to the free Unlimited plan. **Service ended in Brazil, China, EU, Israel, South Korea, Turkey and the UK, with 14 days (to 19 Dec 2025) to download data.** Desktop/Rewind capture was switched off 19 Dec 2025 | Even a well-funded capture vendor can disappear overnight; region cut-offs with two weeks' notice = de-facto bricking. **Enterprises will demand EOL and exit terms.** | High ([TechCrunch](https://techcrunch.com/2025/12/05/meta-acquires-ai-device-startup-limitless/), [limitless.ai](https://www.limitless.ai/)) |
| **Bee Pioneer** (Bee → Amazon) | $49.99 + $19/mo (pre-deal) | Wristband or clip; **"A single press of the button starts and stops capturing"**; LED **"green when Bee is capturing and off when it is not"**; dual mics; up to 7 days (160 h) battery; audio "not saved, stored, or used for AI training" (policy) | Amazon acquisition announced **22 Jul 2025** (terms undisclosed). In Oct 2026 bee.computer, footer "©2026 Amazon.com", still sells Pioneer ($49.99, US-only, iOS-only). Bee CLI exports to markdown; MCP server; no documented audio API | Press-to-record + explicit LED. Developer export via CLI/MCP. Acquirer focus now consumer/Alexa | High ([TechCrunch](https://techcrunch.com/2025/07/22/amazon-acquires-bee-the-ai-wearable-that-records-everything-you-say/), [bee.computer](https://www.bee.computer/), [docs](https://docs.bee.computer/)) |
| **Plaud** (Note, NotePin, Note Pro, NotePin S, Plaud One preorder, Desktop) | NotePin **$159** (High, [plaud.ai](https://www.plaud.ai/products/notepin)); other devices ≈ $159–179 *(memory)*. AI plans: **Starter free (300 min/mo); Pro $17.99/mo or $8.33/mo annual (1,200 min); Unlimited $29.99/mo or $19.99/mo annual**. **Team plan $20/user/mo annual (launch offer to 30 Nov 2026, then $25); $28→$35 monthly** | Recorder-first (press to record, standalone storage). Team admin: seats, **device assign/reassign**, offboarding, workspace data residency. AWS in US/EU/Singapore/Japan, **no India region** | "Trusted by over **2.5 million professionals**" (vendor claim). Compliance badges: SOC 2 Type II, HIPAA, ISO 27001/27701, GDPR, EN 18031 (vendor; reports not reviewed). **Developer platform: Device SDK (iOS/Android, BLE pairing, start/stop recordings, retrieve audio files) + Transcription API; developers pay per transcription and per connected device** | The clear commercial winner: **one job (meetings), monetised by minutes, sold to professionals and now teams**. A real partner path (SDK), with an India-residency gap | High for plans/SDK ([pricing](https://www.plaud.ai/pages/plaud-ai-plan-pricing), [team](https://www.plaud.ai/pages/plaud-team), [dev.plaud.ai](https://dev.plaud.ai/)); Med for traction |
| **Omi** (Based Hardware) | $129 promo / $179. Free: unlimited on-phone + 300 cloud min/mo; Unlimited $29.99/mo | **Fully open source (MIT)**: pendant firmware on **Nordic nRF5340** + Zephyr/nRF Connect SDK (Opus encoding on-chip), Omi Glass dev kit on ESP32-S3, Flutter app, Python backend. 10–14 h battery; 2 mics; BLE + Wi-Fi | "300,000+ professionals" (vendor). Unaudited "SOC 2 + HIPAA" claim. No business plan, LED or mute switch on product page. ~13.6k GitHub stars | **Open BLE protocol and reference firmware** we can integrate with, or learn from, without building from scratch | High (repo, [omi.me](https://www.omi.me/pages/product)); Med (claims) |
| **Friend** (Avi Schiffmann) | $129 (Sep 2025) | Always-listening "companion" neck pendant; replies by text on phone | Spent **$1.8M of ~$2.5M raised on the friend.com domain**. **>$1M NYC subway campaign** (11,000+ car cards, 1,000 platform posters, 130 urban panels, Sep 2025) was **vandalised** ("surveillance capitalism", "get real friends"). Wired: "I Hate My AI Friend"; The Atlantic called him NYC's "most reviled tech CEO"; founder: "I don't have much money left". Sales/2026 status unverified | **Always-listening + no utility = public backlash.** Consumer "companion" positioning is toxic for a recorder | High ([TechCrunch](https://techcrunch.com/2025/09/27/ai-startup-friend-spent-more-than-1m-on-all-those-subway-ads/), [404 Media](https://www.404media.co/ai-friend-company-spent-1-8-million-and-most-its-funds-on-domain-name/)); Med (Atlantic via Wikipedia) |
| **Sandbar Stream** ring | $249 preorder ($349 list); free tier + $10/mo "Data Plan" | "Private voice ring": **touch-activated mic, "not always listening"**; haptics; dictation into any iOS/Mac app | Shipping in limited batches ("Batch 5: mid-Dec"); US first; 30-day returns. Founders/funding unverified | The press-to-talk trend, moving to rings | High (page text: [sandbar.com](https://www.sandbar.com/), [shop](https://shop.sandbar.com/)) |
| **Pebble Index 01** ring (Core Devices) | $75 preorder → $99; **no subscription** | **Records only while the button is pressed**; buffers up to 5 min on the ring when the phone is away; non-rechargeable silver-oxide cell (~12–15 h total recording, "up to 2 years"); STT and LLM run **on the phone**, open source | Announced 9 Dec 2025; promised March 2026 → **mass production week of 24 Jul 2026**; >13,000 preorders; most shipped by end Aug, last variants Sept. Known issues: sizing, mic-hole clogging, button wear | Minimal, cheap, local-first. **Schedules slip about 4 months even for veteran hardware teams** | High ([repebble.com blog](https://repebble.com/blog/meet-pebble-index-01-external-memory-for-your-brain), [mass-production post](https://repebble.com/blog/index-01-is-in-mass-production)) |
| **Brilliant Labs Halo** glasses | $399 now (≈$299 at Jul 2025 announcement, *memory*) | Open-source hardware and software; Alif B1 (Cortex-M55 + NPU); 2 mics with audio-activity detection; BT 5.3; ~14 h claim; ~40 g | Shipping from "early August" (year not stated); developer/enthusiast audience | Open-hardware glasses are viable for developers, not enterprise fleets. Price creep | High (vendor pages [brilliant.xyz](https://brilliant.xyz/products/halo)) |

Other recorders with reported traction (Anker Soundcore Work, Mobvoi TicNote, HiDock, Viaim, Taya) could not be verified in this session. Treat them as leads only.


### 3.2 Smart glasses and Big Tech

**Meta: the one mass-market success, and still a consumer product**

| Item | Detail | Conf. |
|---|---|---|
| Ray-Ban Meta | Gen 1 announced 27 Sep 2023, on sale 17 Oct 2023. EssilorLuxottica reported ~**2M units** sold by Feb 2025 and a goal of **10M units/yr capacity by end-2026**. H1-2025 Ray-Ban Meta revenue reportedly up >200% YoY; ~7M units in 2025 reported (Feb 2026) | Launch High ([Wikipedia](https://en.wikipedia.org/wiki/Ray-Ban_Meta)); **unit figures Med/Low: memory, not re-fetched** |
| Line-up | Ray-Ban Meta Gen 2 (Sep 2025; ~$379; ~8 h typical, *memory*). Oakley Meta HSTN (released 26 Aug 2025). Oakley Meta Vanguard (announced Sep 2025). A $299 "Meta Glasses" model went on sale **23 Jun 2026** (Wired via Wikipedia) | Med |
| **Meta Ray-Ban Display + Neural Band** | Announced 17 Sep 2025; **$799** incl. EMG Neural Band; US sales from **30 Sep 2025** only via retail with in-person demo and fitting. Glasses up to 6 h mixed use (30 h with case), band up to 18 h. Canada/France/Italy/UK planned for "early 2026", reportedly paused in Jan 2026 for "unprecedented demand and limited inventory" (*memory*) | High ([Meta newsroom](https://about.fb.com/news/2025/09/meta-ray-ban-display-ai-glasses-emg-wristband/)); pause Med |
| Privacy design & controversy | Hard-wired capture LED. Camera disabled when LED tampering/damage is detected (Jul 2026). Hobbyist LED-defeat mods (404 Media, Oct 2025, *memory*). Harvard I-XRAY face-search demo (Oct 2024). BBC on covert filming of women (Jan 2026). **NYT (Feb 2026): Meta plans facial recognition; Wired (Jun 2026): face-recognition code shipping** | Med-High (via Wikipedia) |
| Economics | Reality Labs ≈ **$80B cumulative operating losses** since late 2020; ~10% of RL jobs cut in 2026; commercial Quest sales stopped 20 Feb 2026 (an exit from enterprise XR) | Med ([Wikipedia](https://en.wikipedia.org/wiki/Reality_Labs)) |
| India | Ray-Ban Meta launched in India in May 2025 from ~₹29,900. Hindi Meta AI and UPI Lite voice payments announced late 2025. Display not sold in India | Med/Low (*memory*) |
| Enterprise | No managed-device or fleet programme found. Glasses are tied to personal Meta accounts | Low-Med |

**Meta Wearables Device Access Toolkit (DAT).** Announced **18 Sep 2025** (blog updated 4 Dec 2025).
- **How it works:** the SDK lives inside **our iOS/Android phone app**, not on the glasses. It exposes the camera (video-frame streaming, photo capture) and, per the GitHub README in Oct 2026, "synchronized PCM audio through Camera Stream (**experimental; unavailable for production publishing**)". There is no Meta AI / "Hey Meta" access in the preview.
- **Status:** v1.0.0, still **developer preview** in Oct 2026, with publishing limited to select partners. General availability was planned "in 2026" and is not yet evidenced.
- **Useful for us:** preview builds can be shared with "**testers within their organizations and teams**", so an internal pilot inside a customer tenant is possible.
- **Launch partners** include **Microsoft Seeing AI**.
- **Implication:** all-day meeting capture through Meta glasses is not a shippable v1 path today. It is limited to Bluetooth headset audio, with our app active. **(High: [Meta blog](https://developers.meta.com/blog/introducing-meta-wearables-device-access-toolkit/), [README](https://github.com/facebook/meta-wearables-dat-ios), [docs](https://wearables.developer.meta.com/docs/develop/))**

**OpenAI × io (Jony Ive / LoveFrom).**
- io was founded in 2024 by Ive, Scott Cannon, Evans Hankey and Tang Tan. OpenAI announced the acquisition on **21 May 2025** and closed on **9 Jul 2025**: **~$6.5B all-stock**, ~55 staff. Ive and LoveFrom remain independent and lead design across OpenAI. **(High: [Wikipedia](https://en.wikipedia.org/wiki/Io_(company)))**
- An iyO trademark TRO (Jun 2025) forced removal of the "io" branding. A Tang Tan declaration said the prototype was "not an in-ear device, nor a wearable device" *(memory; Med)*.
- **In 2026 OpenAI abandoned the "io" name and pushed hardware to 2027** (Wired via Wikipedia: Med). Reported challenges are compute cost, assistant "personality" and privacy of always-listening (FT, Oct 2025, *memory*).
- **Lesson:** the best-funded team in AI still hasn't shipped an ambient-AI device. The hard problems are privacy and social acceptance as much as engineering.

**Apple.**
- AirPods Pro 3 (announced 9 Sep 2025, $249): Live Translation across AirPods Pro 3/Pro 2/AirPods 4 ANC on iOS 26. **(High: [Apple Newsroom](https://www.apple.com/newsroom/2025/09/introducing-airpods-pro-3-the-ultimate-audio-experience/))**
- iOS 26 adds `bluetoothHighQualityRecording` (full-bandwidth AirPods recording; not available in the EU) and AirPods stem-press capture control. **(High, track 06)**
- iOS 18.1+ native call recording **announces itself to all participants**. **(High, track 06)**
- Reported Apple glasses (2026 unveil, 2027 ship) and an AirTag-sized AI pin are **rumour-stage** *(memory; Low-Med)*.

**Google / Samsung.**
- Android XR was announced 12 Dec 2024; Samsung Galaxy XR headset launched Oct 2025 (~$1,799, *memory*). **(High for announcement)**
- Android XR glasses with Warby Parker, Gentle Monster and Samsung were promised for 2026. **Whether they shipped by Oct 2026 could not be verified.**
- Phone-side capture is strong and native: Pixel Recorder; Samsung Galaxy AI Transcript Assist, which supports **Hindi** among 22 languages (High, track 06).

**Amazon / Microsoft.**
- **Amazon:** Bee (above); Alexa+ (Feb 2025, *memory*); Echo Frames are audio-only.
- **Microsoft:** no capture wearable. **HoloLens 2 was discontinued in Oct 2024, with software updates until 31 Dec 2027** ([Wikipedia](https://en.wikipedia.org/wiki/HoloLens_2), citing The Verge).
- Microsoft's 2024 Windows Recall backlash led to an opt-in, encrypted relaunch (*memory*), a direct lesson for always-on capture.
- **Dragon Copilot** does ambient capture of "multi-party, multilingual conversations" at the point of care without a dedicated wearable. Intermountain Health reports **2,500+ active clinician users** and a **27% reduction in time in notes per appointment** ([Microsoft](https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot); High as vendor case study).


### 3.3 Enterprise-wearable precedents

Our buyer is an IT/security organisation, not a gadget enthusiast. The most relevant precedents are therefore **enterprise-issued wearables**.

| Precedent | Facts | Why it matters for PersonaAgent | Conf. |
|---|---|---|---|
| **Vocera badge** (hospitals; Stryker) | Stryker bought Vocera for **$2.97B** (announced Jan 2022; completed **23 Feb 2022**). The current **Vocera Smartbadge**: 2.4" touchscreen, **89 g**, IP54, **swappable battery (4 h active / 40 h standby)**, dedicated **panic, call and Do-Not-Disturb buttons**, "OK Vocera" wake phrase, worn as a badge. Integrates with "more than 150 clinical and operational systems" via Vocera Engage | The closest analogue to a **company-issued work badge**. It succeeded because it is a **workflow tool bought by the organisation**: shared and fleet-managed, with swappable batteries for shift work, physical buttons for critical actions, and deep integration into the systems staff already use | High ([Stryker](https://www.stryker.com/us/en/about/news/2022/stryker-completes-acquisition-of-vocera-communications.html), [Smartbadge](https://www.stryker.com/us/en/smart-care/products/vocera-smartbadge.html), [Wikipedia](https://en.wikipedia.org/wiki/Vocera_Communications)) |
| **Google Glass Enterprise Edition** | EE launched Jul 2017 (Boeing, GE factories), EE2 May 2019. **Production and sales stopped 15 Mar 2023; support ended 15 Sep 2023**, six months' notice | Even Google abandons enterprise wearables. Customers need contractual support windows | High ([Wikipedia](https://en.wikipedia.org/wiki/Google_Glass)) |
| **Microsoft HoloLens 2** | Launched 7 Nov 2019 at **$3,500** (+$125/mo enterprise option). **Discontinued Oct 2024; software updates until 31 Dec 2027** | Sets the enterprise expectation of **~3 years of security updates after end-of-sale**, the bar our no-brick policy should meet | High ([Wikipedia](https://en.wikipedia.org/wiki/HoloLens_2)) |
| **Microsoft Dragon Copilot** (ambient clinical documentation) | Ambient capture of "multi-party, multilingual conversations… at the point of care". Intermountain: **2,500+ active clinician users**, 27% less time in notes per appointment | **Enterprise ambient capture at scale works without a dedicated wearable.** Value comes from the workflow (notes in the system of record), not the gadget | High (vendor case study) |
| **Google Glass consumer backlash** (2013–14) | San Francisco bar confrontation over being recorded; MPAA/NATO cinema ban on wearables (**29 Oct 2014**); Las Vegas casino bans | Visible cameras and recorders trigger bystander backlash. Audio-only, a clear indicator and context-bounded use (work, meetings) lower the risk | High ([Wikipedia](https://en.wikipedia.org/wiki/Google_Glass)) |


### 3.4 Scorecard

| Device | Outcome (Oct 2026) | Primary reason |
|---|---|---|
| Humane AI Pin | **FAILED**: bricked 28 Feb 2025; assets to HP for $116M | Phone replacement that was worse than the phone; cloud latency; thermals; carrier-locked subscription; hype |
| Rabbit R1 | **FAILED (as hardware)**; company survives as a software/agent vendor | Overpromised LAM; redundant second device (~5% daily use); security lapses; one-time price vs cloud COGS |
| Friend pendant | **FAILED (reputational)**; commercial status unverified | Always-listening "companion" with little utility; backlash; capital misallocated |
| Limitless Pendant | **ACQUIRED** (Meta, Dec 2025) → discontinued, regions cut off | Good tech, but stand-alone consumer economics were weak (inference); customers stranded |
| Bee | **ACQUIRED** (Amazon, Jul 2025); still sold US-only | Cheap ($49.99), press-to-record, LED; value as a consumer-AI on-ramp for Amazon |
| **Plaud** | **SUCCEEDED** (2.5M+ users claimed; Team plan; SDK; compliance badges) | One job (meetings/calls), recorder-first, minutes-based subscription, professional buyers, steady product line |
| Omi | **NICHE** (open-source community; 300k users claimed) | Open hardware, developer ecosystem, low price |
| Pebble Index 01 / Sandbar Stream | **EARLY** (shipping 2026) | Minimal press-to-record rings; too early to judge |
| Brilliant Labs Halo | **NICHE** (developers) | Open-source glasses |
| **Ray-Ban Meta** | **SUCCEEDED** (category leader, millions of units; figures memory-only) | Fashion brand + retail, phone companion, everyday utility first, ≤$499, no subscription, visible LED |
| Meta Ray-Ban Display | **EARLY**: promising, supply-constrained, US-only | $799, display + EMG band; in-store fitting |
| OpenAI device | **PENDING**: delayed to 2027 | Compute, "personality", always-listening privacy |
| **Vocera badge** | **SUCCEEDED** (enterprise; $2.97B exit) | Org-bought workflow badge, fleet-managed, integrated |
| Glass EE / HoloLens 2 | **DISCONTINUED** (2023 / 2024) | Narrow enterprise demand; vendor priorities shifted |


### 3.5 Patterns

1. **Companions win, replacements lose.**
   - Every survivor (Plaud, Meta glasses, Bee, Omi, Index 01) relays through the phone and does less than the phone, but does it from a better place: the collar, the wrist, the face, the finger.
   - Both phone-replacement attempts (Humane, Rabbit) failed. Rabbit's founder conceded *"no one wants to carry around two devices."* **(High)**
2. **One job, done reliably, monetised recurringly.**
   - Plaud sells "record and summarise meetings" with minute quotas ($17.99–$29.99/mo; Team $20–35/user/mo).
   - Generalist companions (Humane, Rabbit, Friend) had no job users would pay monthly for. **(High)**
3. **The market moved from always-on to press-to-record with explicit indicators.**
   - Bee: one-press start/stop plus a green LED. Index 01 and Stream: record only while pressed or touched. Halo: audio-activity detection. Meta: a hard-wired, tamper-checked LED.
   - **PersonaAgent's "always-on" pillar has to be re-expressed as *always-ready, policy-windowed work capture*:** on by tenant policy during work contexts, visibly indicated, instantly mutable. This matches founder decision #4. **(High for trend; design is a recommendation)**
4. **BLE relay to the phone is the norm.** No surviving recorder uses its own LTE. Humane's carrier line was a liability (cost, lock-in, no refurbishment). **(High)**
5. **Hardware is cheap; software carries the margin.**
   - Devices cost $49.99–$399. Subscriptions are $10–$35 per user per month.
   - Our AI COGS is already ≈ **$15–27 per user-month** (cross-track estimate), so hardware has to be bundled in a way that does not erase software margin. **(Med)**
6. **Acquisitions strand customers.** Limitless was cut off in 7 jurisdictions with 14 days to export. Humane gave 10 days and deleted data. **No-brick and exit commitments are now a procurement requirement, not a nicety.** **(High)**
7. **Hardware schedules slip:**
   - Humane: March → April 2024.
   - Index 01: March → July–September 2026.
   - Halo: about a year, with a price rise.
   - OpenAI: 2026 → 2027.

   Plan 4–9 months of slack, and never let revenue depend on a device date. **(High)**
8. **Trust incidents are existential:**
   - Rabbit's keys and logs.
   - Humane's recall that outlived the company.
   - Meta's facial-recognition controversy.
   - Friend's vandalised ads.
   - Windows Recall's forced redesign.

   An enterprise recorder must be *more* conservative than consumer devices, not less. **(High)**
9. **Enterprise wearables succeed when the organisation buys them for a workflow** (Vocera) and fail when they are a technology looking for a use case (Glass EE, HoloLens 2). Buyers expect **multi-year support windows** (HoloLens: ~3 years after end-of-sale). **(High)**


## 4. Principles for PersonaAgent's hardware path

These principles turn the evidence above into design rules for a **work-only, company-governed recorder sold per seat to Microsoft 365 organisations in the US and India**.

### 4.1 Phone-first: the device is an accessory, never a replacement

- **The ~3-month MVP (3–6 engineers) should contain zero custom hardware.** Capture comes from:
  - the phone "work-mode recorder", which is user-started (track 06);
  - Teams meetings via Graph transcripts (track 02);
  - desktop capture where relevant.

  Humane and Rabbit both built hardware before proving any software habit. Plaud built a subscription business on a device that does one thing.
- **Hardware enters only after the phone product proves daily habit and willingness to pay** (gates in §6).
- **Device philosophy: "a microphone with a button, a light and a mute switch."**
  - No screen, projector, camera, speaker, cellular modem or on-device LLM.
  - All intelligence runs on the phone and in AWS.
  - This removes Humane's thermal/latency/battery trap by construction. It also avoids Rabbit's "phone in a worse box" redundancy: the device does nothing the phone already does well.

### 4.2 Why build a device at all: the background-start gap

**The phone's hard limit (track 06, High):** on both iOS and Android an app **cannot start the microphone from the background**. A calendar event, geofence or push cannot cold-start capture; the user must tap. People forget to tap, so the "good idea at 2 pm" is often never recorded. This is the strongest product argument for our own device.

**What a BLE peripheral changes:**
1. **Capture starts on the device**, from a button press or a tenant-approved device-side schedule, whatever state the phone app is in. Audio is encrypted into the device's own flash buffer from the first second.
2. **Audio reaches the phone as BLE data, not as the phone's microphone input.** The OS "while-in-use microphone" rules therefore don't govern it. On iOS, the `bluetooth-central` background mode lets the app be woken to process data from a connected peripheral. On Android, a companion app can keep a connected-device service running. Details and caveats are in §4.5. Treat this as **Med confidence until prototyped**.
3. **Better mic placement and independence.** A chest-level badge captures the people you talk to far better than a phone in a pocket or bag. It keeps recording while the phone's mic is taken by a Teams or VoIP call; Teams audio comes from Graph anyway.

**What does *not* solve it:** AirPods and standard Bluetooth headsets use system audio routes (HFP, LE Audio). These are governed by the same audio-session and while-in-use rules. Only a **custom GATT data stream** (Omi-style) sidesteps them. iOS does **not** relaunch an app the user has force-quit, or after Bluetooth is toggled off ([Apple QA1962](https://developer.apple.com/library/archive/qa/qa1962/_index.html); High). The device must therefore buffer hours of audio and sync later, and the app should tell users not to force-quit it. Apple's App Review rule 2.5.14 still requires a visible recording indication, so we need the device LED *and* an in-app Live Activity.

**Validation step (Phase 1, ~2 weeks, 1 engineer):** prove background wake plus sustained streaming on iOS 26/27 and Android 15–17. Test on Samsung, Xiaomi, Vivo/Oppo (common in India) and Pixel, using an Omi dev kit or Nordic DK. Measure gaps, reconnects and phone battery cost.

### 4.3 Work-only, company-governed by design

Policies flow from tenant admin → PersonaAgent cloud (AWS) → phone app → device. They are enforced **on the device** wherever possible, so a lost phone or compromised app can't widen capture.

| Policy | Example settings | Enforced at |
|---|---|---|
| Capture windows | Working hours (e.g., Mon–Fri 09:00–19:00 local); calendar events tagged capture-allowed; max session length | Device clock + phone |
| Start mode | **Press-to-start (default)**; admin opt-in "auto-arm in scheduled meetings" only with a mandatory chime + LED | Device |
| Location | Office geofences (phone-side); optional "no-record rooms" (e.g., HR, health). Beacon approach is an idea, not validated | Phone (+ device) |
| Secure zones | **Auto-mute (or "device not permitted") on client-secure floors.** Indian IT/BPO offshore delivery centres often ban recording devices in client zones under ISO 27001 physical controls (memory; Low-Med). Admin-defined zones via geofence or beacon; export the device inventory to physical-security teams | Device + phone |
| Notice & consent | Start chime/voice prompt; LED always on while capturing; meeting-invite disclosure text; external-party consent tap where policy requires (all-party-consent states, per the legal track) | Device + app |
| Retention | Raw audio deleted after transcription (default) or kept N days; transcripts N days; legal hold | Cloud |
| Redaction | US and India regulatory profiles (Phase 1 decision #5) | Cloud |
| Kill switch | Remote disarm, lost-mode, crypto-erase; offboarding on Entra ID account disable | Device on next sync + cloud |
| Personal use | **None in v1.** Device disarms outside policy windows; no personal lifelogging mode | Device |

Every session writes an **audit record**: who, when, policy version, notice given, mute/pause events. It is visible to the employee (transparency) and to admins (governance).

### 4.4 Form factor and social acceptability

| Form factor | Mic quality for conversations | Social legibility at work | Battery room | Enterprise fit | Verdict |
|---|---|---|---|---|---|
| **Badge / clip** (lanyard or magnetic) | Good: chest, ~20–40 cm from speakers | **High**: reads as a work badge; LED where others can see it | Medium | **High**: issued, tracked, docked (the Vocera precedent) | **Recommended first device** |
| Desk / table puck (1:1s, small rooms) | Very good for meetings | High: visibly "on the table" | High | High (can be shared or room-bound) | **Second SKU candidate**; overlaps with Teams Rooms |
| Pendant / necklace | Good | Medium–low: reads as a consumer gadget (Limitless, Friend backlash) | Medium | Medium | Not v1 |
| Ring | Poor for others' speech (hand-mounted); fine for own voice notes | Invisible, which raises covert-recording concerns | Very low | Low | Voice notes only; integrate, don't build |
| Glasses | Good for own voice; camera raises bystander concerns | Low (camera, facial-recognition controversy) | Low (6–8 h typical) | Low (consumer accounts; toolkit in preview) | Internal pilot only (§3.2) |
| Earbuds / headsets | Excellent for own voice; poor for others (beamformed to the wearer) | High | Low | High (already issued; Teams-certified) | Support as an audio source for calls and dictation, not in-person capture |
| Phone (status quo) | Medium (pocket muffling) | High | n/a | High | MVP |

**Social design rules:**
- a front-facing, wide-angle recording LED;
- an audible start chime;
- a physical mute that bystanders can *see*;
- a printed line on the badge face ("Notes in progress: ask me to pause");
- no camera in v1, and never covert operation.

These directly address the backlash pattern (Glass 2014, Friend 2025, Meta 2026). They also match the press-to-record and LED norm set by Bee, Index 01 and Stream.

**Supporting evidence.** These items are from memory and need re-checking before external use.
- **LEDs alone don't reassure bystanders:**
  - In 2021 the Irish DPC and Italy's Garante asked Facebook to prove that the Ray-Ban Stories LED actually warns people (Med-High).
  - In 2024 Harvard's I-XRAY demo paired Meta glasses with face search to identify strangers (High, via Wikipedia).
  - The answer is a tamper-evident hardware LED **plus** policy and notice.
- **HCI research on bystanders:** studies (e.g., Denning et al., CHI 2014; Hoyle et al., UbiComp 2014) find bystanders want to be asked or notified, and lifeloggers themselves avoid recording in sensitive places (Med).
- **Public attitudes:** Pew (2014) found 53% of US adults thought it would be a change for the worse if most people wore devices that constantly showed them information about the world around them (Med).
- **US workplace notice rules:** New York Civil Rights Law §52-c (since 7 May 2022) requires written notice of electronic monitoring. Connecticut and Delaware have similar rules. The NLRB General Counsel memo GC 23-02 targets surveillance that chills protected activity. Employee-facing notice and transparency are therefore required, not optional (Med-High; detail in the legal track).

### 4.5 Connectivity architecture: BLE relay, store-and-forward, no LTE

```
[Badge]  2× MEMS mic → nRF5340-class MCU (VAD, Opus 16–24 kb/s, AES per chunk)
         → encrypted SPI flash buffer (≥ 1 workday) ── hardware mute cuts mic power; LED on mic rail
   │  BLE GATT (LE Secure Connections + app-layer E2E encryption)
   ▼
[Managed phone app]  (Intune-managed app config) drains the buffer on every wake → uploads over TLS
   │                                   ▲
   ▼                                   │ USB-C dock at the desk: charge + bulk sync via the
[PersonaAgent on AWS]  STT → redaction → memory index / Q&A      PersonaAgent Windows app (Pillar 1)
```

- **Codec.** Xiph's bandwidth-transition table moves voice to wideband at ~**10 kb/s** and fullband at ~**16 kb/s**. For VoIP it notes "10 Kb/s will deliver narrowband most of the time, 24 Kb/s should give fullband". The default frame is 20 ms ([Xiph](https://wiki.xiph.org/Opus_Recommended_Settings); High). **Omi already encodes Opus on an nRF5340 in production** ([GitHub](https://github.com/BasedHardware/omi); High). Use 16–24 kb/s, 16 kHz mono, which matches track 06's pipeline.
- **Buffer sizing (arithmetic).** Opus at 16 kb/s = 7.2 MB/h; at 24 kb/s = 10.8 MB/h. A **128 MB** buffer holds ≈ 17.8 h at 16 kb/s or ≈ 11.9 h at 24 kb/s. Raw 16-bit PCM would need 115 MB/h. Specify **256 MB** for headroom (multi-day offline).
- **iOS reality** ([Apple Core Bluetooth background guide](https://developer.apple.com/library/archive/documentation/NetworkingInternetWeb/Conceptual/CoreBluetooth_concepts/CoreBluetoothBackgroundProcessingForIOSApps/PerformingTasksWhileYourAppIsInTheBackground.html); High):
  - With `bluetooth-central`, the system wakes the app when "a peripheral sends updated characteristic values".
  - Each wake gives "around 10 seconds". Heavy background use can get the app "throttled back… or killed".
  - State restoration relaunches the app into the background after the *system* terminated it.
  - Apple asks such apps to be "session based".
  - **Design consequence: store-and-forward, not live streaming.** The badge buffers continuously, and the phone drains bursts on each wake. Live streaming may work most of the time but must not be relied on.
  - Apple QA1962 relaunches the app after it was removed from memory, crashed, or the device restarted (after first unlock). It does **not** relaunch after a **user force-quit** or **Bluetooth power toggle**, and only "if… it is pending on a specific Bluetooth event" ([QA1962](https://developer.apple.com/library/archive/qa/qa1962/_index.html); High). The flash buffer covers these gaps.
- **Android reality** (developer.android.com; High):
  - Since Android 12 an app can't start a foreground service from the background, **except** with a **Companion Device Manager (CDM) association** plus `REQUEST_COMPANION_START_FOREGROUND_SERVICES_FROM_BACKGROUND` / `REQUEST_COMPANION_RUN_IN_BACKGROUND` ([restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start)).
  - A `connectedDevice` foreground service needs `FOREGROUND_SERVICE_CONNECTED_DEVICE` plus e.g. `BLUETOOTH_CONNECT`, **not `RECORD_AUDIO`** ([service types](https://developer.android.com/develop/background-work/services/fgs/service-types)).
  - Android 16's `startObservingDevicePresence` binds the app's `CompanionDeviceService` when the badge is in range ([CDM](https://developer.android.com/develop/connectivity/bluetooth/companion-device-pairing)).
  - **Risk:** OEM battery killers (Xiaomi, Vivo, Oppo, Samsung, all common in India) need a test matrix.
- **Conclusion (Med–High, prototype required):** a dedicated BLE recorder **does sidestep the "no background mic start" rule** on both platforms, because the audio arrives as Bluetooth data. On iOS the device must be designed for **buffer-and-burst sync**.
- **Wi-Fi:** not on the personal badge in v1 (802.1X/EAP-TLS provisioning, captive portals, power, extra certification). Omi's board files include an nRF70 Wi-Fi option, so it remains possible for a future **room puck**. **LTE: never** for the badge (the Humane lesson).
- **Throughput:** BLE 2M PHY with data-length extension reaches hundreds of kb/s, so an 8-hour backlog (~58 MB at 16 kb/s) drains in minutes, at ≥10× real time (*memory*; verify per phone model).

### 4.6 Battery and power targets

| Benchmark | Claimed battery | Capture model | Source | Conf. |
|---|---|---|---|---|
| Plaud NotePin | 20 h recording, 40 days standby; 16.6 g | Press-to-record | [plaud.ai](https://www.plaud.ai/products/notepin) | High (vendor) |
| Plaud NotePin S / Note Pro | 20 h / 30–50 h | Press-to-record | [dev.plaud.ai](https://dev.plaud.ai/) | High (vendor) |
| Omi | 10–14 h (product page) vs "24h+ continuous capture" (README) | Continuous | omi.me; GitHub | Med (conflict) |
| Bee Pioneer | up to 7 days (160 h) | Press-to-record | bee.computer | High (vendor) |
| Pebble Index 01 | ~12–15 h total recording over life (non-rechargeable) | Press-and-hold | repebble.com | High |
| Vocera Smartbadge | 4 h active / 40 h standby, **swappable** | Push-to-talk | Stryker | High |
| Humane AI Pin | 4–5 h (8–9 h with booster) | Phone-class SoC + projector | Inverse | Med-High |

**Power budget (estimate, nRF5340-class, continuous capture):**

| Block | Estimated average current |
|---|---|
| 2 mics | ~1.0 mA |
| MCU (capture, DSP, Opus) | 2.5–3.5 mA |
| BLE batched notifications | 0.5–1.0 mA |
| Flash writes | 0.2–0.4 mA |
| PMIC, LED at ~10% duty, misc. | 0.3–0.5 mA |
| **Total** | **≈ 4.5–6.4 mA (plan on 5.5 mA)** |

**Required capacity = hours × mA ÷ 0.8 (derating):**
- **24 h continuous:** ≈ **165 mAh**.
- **48 h continuous:** ≈ **330 mAh**.
- **With wake-on-sound** (TDK T5838 Acoustic Activity Detect at "as low as 20 µA", [TDK](https://invensense.tdk.com/products/digital/t5838/); High), with speech ~35% of the time: ≈ 2.1 mA average, so a ~136 mAh cell covers **five 10-hour workdays**. (Estimate)

**Targets (recommendation):**
- ≥ **16 h active capture** per charge, so a full workday plus commute with margin.
- ≥ **1 work-week** of policy-windowed capture with wake-on-sound.
- Charge in ≤ 90 min; dock charging.
- **150–250 mAh** Li-polymer cell (≈ 0.6–0.9 Wh, far below IATA small-cell thresholds).
- Weight ≤ 25 g (NotePin 16.6 g; Vocera badge 89 g).
- ≥ 80% capacity after 500 cycles.

Wake-on-sound fits the work-only policy model: the badge only captures speech, and only inside policy windows.

### 4.7 Trust hardware (non-negotiable)

1. **Physical mute slide switch** that electrically cuts mic power/data (not a firmware flag), with a visible red state. Amazon's Echo "mic-off" button is the familiar consumer precedent *(memory; Med)*.
2. **Recording LED wired to the mic power rail**, so firmware cannot capture with the LED dark. Add tamper detection (Meta disables capture if the LED is tampered with or damaged).
3. **Start/stop chime + haptic**; optional spoken notice for external meetings.
4. **Consent and audit log** per session (§4.3).
5. **No voiceprints or speaker biometrics in v1.** Under BIPA (Illinois) and India's SPDI Rules, voice biometrics need written consent (legal track). Diarization labels ("Speaker 2") are fine; enrolment-based speaker ID is not.
6. **"Pause 15 min" and "delete the last N minutes" gestures**, so a bystander's request can be honoured on the spot.

### 4.8 Latency targets

| Interaction | Target (recommendation) | Why |
|---|---|---|
| Button → LED/haptic acknowledgement | ≤ 100 ms | Feels instantaneous; trust signal |
| Mute switch → mic off | Immediate (hardware cut) | Trust |
| Reconnect → buffered sync starts | ≤ 5 s | Prevents "lost" audio anxiety |
| In-person speech → searchable transcript (while connected) | ≤ 2 min median | Supports "what did I just say?" |
| Meeting end → summary and action items | ≤ 5 min | Matches Teams recap expectations |
| Memory question (e.g., "what were the client's requirements at 4 pm?") → first streamed token / full answer | ≤ 2 s / ≤ 6 s p50 (≤ 10 s p95), on phone/desktop | Humane took ~6 s just for the weather and answered by voice. We answer as streaming text on a screen |
| Cloud outage | Device keeps capturing to flash; nothing on the device waits on the cloud | Offline-first |

### 4.9 Security baseline (Rabbit's mistakes, inverted)

- **Per-device identity:** a unique key pair generated or injected at manufacture, a certificate signed by our CA, and attestation to the cloud via the phone.
- **No secrets in firmware or the app:** no API keys anywhere on the device. The app uses short-lived tokens from Entra ID OAuth. The device never calls third-party APIs.
- **Secure boot** with an immutable bootloader. **Signed and encrypted OTA** with anti-rollback. Debug ports locked in production.
- **Encrypted flash** with device-unique keys; crypto-erase on unpair, offboarding or remote wipe.
- **BLE LE Secure Connections pairing** with out-of-band (QR/NFC) binding at provisioning.
- **Application-layer end-to-end encryption** from device to our cloud, so the phone OS and other apps only ever see ciphertext.
- **SBOM, a published vulnerability-disclosure policy and bug bounty, and an independent pentest** before any pilot.
- Map controls to ETSI EN 303 645 / NIST IR 8259A now. Map to EN 18031 (EU RED) and UK PSTI before EU/UK expansion.
- Incident reporting obligations (e.g., India CERT-In's 6-hour rule) are covered by the security and legal tracks.

### 4.10 No-brick and data-portability commitments (put them in the contract)

Humane gave 10 days' notice and deleted data. Limitless cut off 7 jurisdictions with 14 days to export. Glass Enterprise got 6 months; HoloLens 2 got ~3 years of updates after end-of-sale. Enterprise RFPs will ask for:
1. **≥12 months' notice** before end of device service; **security updates ≥3 years** after end-of-sale (the HoloLens benchmark).
2. **Offline mode:** the device records to flash and exports over USB to the desktop app in **open formats** (Opus/WAV audio + JSON/Markdown transcripts) without our cloud.
3. **Open, documented BLE/GATT and file protocol.** Firmware source in **escrow**, released on insolvency or end-of-life. Commit to open-sourcing firmware at end-of-life. The Pebble precedent:
   - Fitbit bought Pebble (Dec 2016) and shut its services on **30 Jun 2018**.
   - The **Rebble** community restored the app store and firmware services the same day.
   - Google **open-sourced PebbleOS in Jan 2025**, which enabled Core Devices' revival.

   Open protocols turn a shutdown into a hand-over ([Wikipedia](https://en.wikipedia.org/wiki/Pebble_(watch)); Med-High).
4. **Bulk tenant export at any time** (API + S3 bundle) and certified deletion at termination.
5. **Change-of-control clause:** an acquirer must honour the notice and export terms. **No region cut-off with less than 90 days' notice.**
6. **Pro-rata credit** for the unused hardware-as-a-service term if we end service early.

### 4.11 Pricing, bundling and hardware-as-a-service

- **Context:**
  - Our AI cost of goods is already ≈ **$15–27 per user-month**: LLM $13–23, STT $0.13–$11.88, infrastructure $1–3 (cross-track).
  - Market references: Plaud Team **$20–35/user/mo** plus a ~$159–179 device; Omi Unlimited $29.99/mo; Bee $19/mo before the acquisition.
  - Retail hardware margins are thin, and Rabbit's one-time $199 could not fund cloud costs.
- **Recommended model: hardware-as-a-service inside a "Capture+" seat**, sold only to organisations, never at retail. The device is included with a 12–24-month commitment and stays company property, with replacement and RMA included.
- **Illustrative uplift (estimate, Low):**
  - Fully-loaded device cost ≈ **$30–60**: landed $18–46 (§4.13) plus ~$10–15/unit of amortised design, tooling and certification over the first 10k units.
  - Add logistics and support of $15–25, plus a 10%/yr failure/loss reserve.
  - Over 24 months that is ≈ **$2.5–4.5/user-month**.
  - At a ~60% hardware gross margin, that implies a **+$6–10/user-month** uplift on the Capture+ seat.
  - Recalculate once real quotes and RMA data exist.
- **Alternatives:** outright purchase at cost-plus ($99–149) for capex-preferring buyers; **free pilot kits** (10–50 units) for design partners.
- **India:** price the seat in INR. Hardware landed cost is exposed to import duty on finished wearables, which favours local assembly at scale (§4.13).

### 4.12 Certification paths: US and India first (EU/UK later)

**Bottom line (estimate, Low–Med).** Assume a **BLE-only badge on a pre-certified module, with no power adapter in the box**.
- **US + India certification ≈ US$25k–60k.** That includes the US$11.5k–12k Bluetooth SIG listing fee and an IEC 62368-1 CB report.
- **Time: ~8–14 weeks** of parallel work after design freeze.
- **Add US$5k–15k** if SAR testing turns out to be needed.
- **An LTE variant** would add carrier/PTCRB certification (plausibly US$50k–150k+) plus India MTCTE/IMEI obligations. That is another reason to stay BLE-only.

**United States (FCC)**

| Item | Requirement | Cost / lead time (estimate) | Conf. |
|---|---|---|---|
| Radio (BLE, 2.4 GHz) | Part 15 Subpart C intentional radiator, normally **Certification** (FCC ID) by a TCB after testing at an FCC-recognised lab (§15.247). **Or** use a **modular transmitter** with its own grant (§15.212) and label the host "Contains Transmitter Module FCC ID: …" | **Route A** (module whose grant covers portable use): **$2k–6k, 2–4 weeks** (Part 15B SDoC + RF-exposure memo). **Route B** (own radio, or the module needs a Class II permissive change): **$8k–20k, 4–8 weeks**, including 1–2 weeks of TCB review | Rule High ([LII §15.212](https://www.law.cornell.edu/cfr/text/47/15.212)); costs Low-Med |
| **Body-worn catch** | Many module grants cover only *mobile* use (≥20 cm from the body). A badge is a **portable** device (radiating structure "within 20 centimeters of the body of the user", §2.1093), so it needs its own RF-exposure evaluation and possibly a Class II permissive change | Pick a module whose grant explicitly covers portable/body-worn use | Definition High ([LII §2.1093](https://www.law.cornell.edu/cfr/text/47/2.1093)); module practice Med |
| RF exposure / SAR | Exempt if "the available maximum time-averaged power is no more than 1 mW, regardless of separation distance" (§1.1307(b)(3)(i)(A)). Above that, a SAR-based exemption formula applies at 0.5–40 cm and 0.3–6 GHz. General-population limit: 1.6 W/kg over 1 g (§1.1310) | Our calculation from the formula (recalled from memory; verify with the lab): threshold ≈ **2.7 mW at 5 mm, 10 mW at 10 mm, 38 mW at 20 mm** at 2.45 GHz. **Keep BLE at ≤ +4 dBm and ≥5 mm from the skin to avoid SAR testing.** Body-worn Wi-Fi at 15–18 dBm would probably need SAR (+$5k–15k, +2–4 weeks) | Rules High ([LII §1.1307](https://www.law.cornell.edu/cfr/text/47/1.1307), [§1.1310](https://www.law.cornell.edu/cfr/text/47/1.1310)); calculation Med |
| Unintentional emissions | Part 15 Subpart B via **Supplier's Declaration of Conformity**; the responsible party must be US-based | Included above | Med-High (memory) |
| Foreign applicants | Need a US agent for service of process. 2025 FCC rules restrict recognition of TCBs/labs owned or controlled by "foreign adversary" entities, so confirm the lab's status | — | Med-Low (memory) |
| Product safety | No federal mandate for a battery wearable, but enterprise procurement expects an **IEC/UL 62368-1 CB report** and an NRTL-listed charger | $4k–10k | Med (memory) |
| **Bluetooth SIG** | Qualification and listing are needed to use the Bluetooth name and logo. **Fee schedule from 1 Mar 2026:**<br>• Adopter: $0 dues + **$12,000 per product**<br>• Small Contributing Adopter: $3,500/yr + **$8,000 for the first product** (= $11,500)<br>• Small Associate: $11,250/yr + $6,000 per product | Reusing a qualified module or stack cuts testing work, not the fee | High ([Bluetooth SIG](https://www.bluetooth.com/develop-with-bluetooth/qualification-listing/qualification-listing-fees/)) |
| ISED Canada | Optional (RSS-Gen, RSS-247, RSS-102) | +$2k–5k, bundled with FCC testing | Med (memory) |

**India**

| Item | Requirement | Cost / lead time (estimate) | Conf. |
|---|---|---|---|
| **BIS CRS categories (verified list)** | The CRS list includes:<br>• **Smart watches**: IS 13252 (Part 1)<br>• **Wireless headphones & earphones**: IS 616:2017<br>• **Sealed secondary lithium cells/batteries**: IS 16046 (Part 2):2018<br>• **Power adaptors for IT equipment**: IS 13252 (Part 1)<br>• power banks; standalone SMPS ≤48 V; CCTV cameras/recorders | — | High ([crsbis.in product list](https://www.crsbis.in/BIS/products-bis.do)) |
| **Does the badge itself need CRS?** | A badge/clip voice recorder **does not obviously fit a notified category**. Its **Li-ion cell/pack (IS 16046-2)** does, and so would a **bundled adapter**. So **ship with a USB-C cable only** and buy **cells/packs that already hold BIS R-numbers**. Get a written classification opinion, watching for "smart watch" or "wireless earphone" analogies | Battery-pack CRS ≈ ₹1.5–4 lakh (~$1.8k–4.8k). Device or adapter similar *if* in scope. **~2–3 months** per registration | Interpretation Med-Low |
| CRS process | Foreign manufacturers appoint an **Authorised Indian Representative** (registration is per factory). **Testing must be at BIS-recognised labs in India**; foreign reports aren't accepted. Validity ~2 years, renewable. **Manufacturing in India removes the need for an AIR** | AIR/consultant ≈ $1k–3k/yr | AIR High ([Wikipedia](https://en.wikipedia.org/wiki/Bureau_of_Indian_Standards)); rest Med (memory) |
| **WPC Equipment Type Approval** | Required to import or sell Bluetooth/Wi-Fi devices. **Self-declaration ETA** for de-licensed bands, backed by accredited-lab RF reports. Those may come from outside India, so FCC and EN 300 328 data can be reused. Portal moved to **eservices.dot.gov.in/saral-sanchar** | ≈ ₹10k–50k; ~1–4 weeks | Requirement Med-High ([Wikipedia](https://en.wikipedia.org/wiki/Wireless_Planning_and_Coordination_Wing)); portal High; fees Low |
| TEC MTCTE | Covers telecom-network equipment. A **BLE-only accessory is generally out of scope**; an LTE/eSIM variant would bring in MTCTE and IMEI rules | — | Low-Med (memory) |
| Other producer duties | **EPR registration** under the E-Waste (Management) Rules 2022 and the Battery Waste Management Rules 2022 (CPCB portal). **Legal Metrology** packaging labels (MRP, importer details) | Low | Med (memory) |
| Lesson | Rabbit's India units sat idle on "regulation complications" | Start **≥6 months** before India shipments | High |

India subtotal (estimate): **~US$4k–12k and 2–3 months**, run in parallel with the FCC work.

**Battery and shipping**
- **UN38.3** (eight tests, T1–T8): a test summary must be available along the supply chain.
- **IEC 62133-2:2017**: India's IS 16046-2 is based on it, but an Indian lab must re-test.
- **IATA Section II** covers cells ≤20 Wh and batteries ≤100 Wh, so our ~0.6–0.9 Wh cell qualifies easily.
- **From January 2025, IATA added a packaging requirement** for lithium batteries packed with or contained in equipment ([IATA](https://www.iata.org/en/programs/cargo/dgr/lithium-batteries/); High).
- Recommendation: buy a cell/pack that **already has UN38.3 + IEC 62133-2 + BIS IS 16046-2**.

**EU/UK (later expansion; budget ≈ US$15k–40k, estimate)**
- **RED cybersecurity:** Delegated Regulation (EU) 2022/30 applies to wearable radio equipment, including devices that connect via a phone, since **1 Aug 2025**. EN 18031-1/-2/-3 are harmonised, with restrictions (Med-High, memory). Plaud already claims EN 18031.
- **Cyber Resilience Act:** in force 10 Dec 2024; reporting obligations from **11 Sep 2026**; main obligations from **11 Dec 2027** ([European Commission](https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act); High).
- **EU Battery Regulation 2023/1542, Article 11:** portable batteries must be readily removable and replaceable by end users from **18 Feb 2027**, with narrow derogations. This is a design constraint for any EU SKU (Med, memory).
- **EU AI Act, Art. 5(1)(f):** emotion recognition in the workplace has been prohibited since 2 Feb 2025. **Never infer emotion from employees' voices** (Med-High, memory).
- **Germany:** works councils have co-determination rights over monitoring-capable devices, BetrVG §87(1) no. 6 (memory).
- **UK PSTI** (since 29 Apr 2024):
  - no universal default passwords;
  - a published vulnerability-reporting route;
  - a published minimum security-update period.

  Source: [GOV.UK](https://www.gov.uk/government/publications/the-uk-product-security-and-telecommunications-infrastructure-product-security-regime) (High). Whether it applies to enterprise-only products is unclear.

### 4.13 Reference design, BOM, manufacturing options and timeline

**Recommended reference design (badge v1):**
- **Nordic nRF5340**:
  - dual Cortex-M33: application core 128/64 MHz with 1 MB flash / 512 KB RAM; network core with 256 KB flash / 64 KB RAM;
  - BLE with LE Audio;
  - TrustZone, CryptoCell-312, key management unit, **PSA Certified Level 2**;
  - proven in Omi.

  Sources: [Nordic](https://www.nordicsemi.com/Products/nRF5340), Omi repo (High).
- **Other parts:**
  - 2× TDK T5838 mics (SNR 68 dB, wake-on-sound);
  - 128–256 MB SPI NAND;
  - nPM1300-class PMIC and fuel gauge;
  - 150–250 mAh LiPo;
  - **hardware mute slide**;
  - **LED on the mic power rail** with light pipe;
  - haptic;
  - USB-C/pogo dock.
- **Cost-down v2:** **nRF54L15** (RX 3.4 mA / TX 4.8 mA at 0 dBm; 1.5 MB NVM / 256 KB RAM; tamper detection). Check that Opus fits in 256 KB of RAM; the page doesn't mention LE Audio, which we don't need ([Nordic](https://www.nordicsemi.com/Products/nRF54L15); High).
- **Not for the badge:** ESP32-S3. It is Wi-Fi-centric, with no LE Audio listed, and better suited to a camera device or a Wi-Fi room puck ([Espressif](https://www.espressif.com/en/products/socs/esp32-s3); High for specs).
- **Ultra-low-power alternative:** Ambiq **Apollo510B** (Cortex-M55, BLE 5.4, always-on audio ADC, PUF), with a smaller ecosystem ([Ambiq](https://ambiq.com/apollo510/)).

**Indicative BOM at 10k units: ESTIMATE (Low; replace with distributor and ODM quotes)**

| Item | US$ (est.) |
|---|---|
| nRF5340 + crystals, RF matching, antenna | 4.5–7.0 |
| 2 MEMS mics | 0.6–1.5 |
| 128 MB SPI flash | 1.0–2.5 |
| PMIC / charger / fuel gauge | 1.0–2.0 |
| 150–250 mAh LiPo (UN38.3) | 1.0–2.5 |
| Optional secure element | 0.6–2.0 |
| Mute slide, button, LED + light pipe, haptic | 0.6–1.5 |
| PCB, assembly, test | 2.0–4.0 |
| Enclosure, clip / lanyard | 1.5–5.0 |
| Dock / pogo + cable | 1.0–3.0 |
| Packaging | 1.0–2.5 |
| **Ex-factory** | **≈ 15–33** |
| **Landed** (freight, duty, yield, warranty +20–40%) | **≈ 18–46** |

**One-time costs (estimate):**
- Industrial and mechanical design: $20–100k.
- Tooling: $10–60k.
- Certification: US + India ≈ $25–60k (§4.12); EU/UK later +$15–40k.
- Firmware and electrical engineering: ~2 engineers × 6–9 months.

Retail anchors: Plaud NotePin $159, Index 01 $75–99 (High).

**Timeline (estimate):**

| Stage | Units | Duration |
|---|---|---|
| Proof of concept (dev kits / Omi / Plaud) | 5–20 | 0–2 months |
| Works-like / looks-like | 20–50 | 2–4 months |
| EVT | 50–200 | 2–3 months |
| DVT (hard tooling, certification, reliability) | 200–1,000 | 2–4 months |
| PVT | 500–2,000 | 1–2 months |
| **Prototype → mass production** | | **≈ 9–15 months**, plus the 4–9 months of slack history says to expect |

**MOQ (estimate):**
- Custom-tooled runs: 1k–5k units.
- White-label ODM recorders: 500–3,000.
- Small-run EMS: 100–1,000 boards.

**Manufacturing options.** Every name and figure below is from memory and was not verified this session; confirm before outreach.

| Option | Fit for us | Notes |
|---|---|---|
| **VVDN Technologies** (Gurugram/Manesar) | **Best low-volume India fit** (design + manufacturing ODM) | Could own EE/ME + build for Phase 2–3 |
| Dixon Technologies (Noida) | Scale India EMS | Reportedly builds wearables/hearables for Indian brands; Phase 3+ volumes |
| Optiemus Electronics (Noida) | Scale India EMS (wearables/hearables) | Reportedly partners with Indian audio/wearable brands |
| Kaynes Technology (Mysuru), Syrma SGS (Chennai) | IoT/industrial EMS | Mid-volume options |
| Tata Electronics (Hosur) | Apple-scale | Not a small-run partner |
| US: MacroFab, Screaming Circuits, Sierra Circuits | Small-run boards (Phase 2 pilots) | Jabil/Flex/Sanmina only at large programme scale |
| Shenzhen white-label AI-recorder ODMs | Fastest pilot hardware | Firmware/security quality and supply-chain/tariff risk; we must own firmware and keys |

- **India incentives and duties** (memory, Low):
  - PLI schemes target phones and IT hardware rather than wearables.
  - The 2025 electronics-component scheme (~₹22,919 crore) benefits component makers, so it reaches us only indirectly via EMS partners.
  - Import duty on finished wearables is reportedly ~20%, which **favours Indian assembly for India volumes**.
- **US tariffs** on electronics changed repeatedly in 2025–26. Model China, India and other-origin scenarios at sourcing time.
- **Enterprise supply checklist:**
  - serial numbers bound to keys at the factory;
  - signing keys in an HSM;
  - country-of-origin documents;
  - a 2–3-year replacement pool;
  - second sources for mics, flash and battery.

### 4.14 Fleet provisioning and device management

- **Zero-touch binding:** devices ship with factory identity. An admin claims serials or QR codes into the tenant and assigns them to Entra ID users or groups. The phone app (Intune-managed) receives tenant ID, capture policy and allowed hours via **Intune app configuration policies**, which track 06 confirms can carry UPN and Entra device ID (High).
- **MDM scope:** Intune manages the *phone and our app*, not BLE accessories. Device management lives in **our admin console**:
  - inventory and assignment;
  - firmware version and battery health;
  - last-sync time;
  - remote disarm, lost-mode and wipe;
  - audit trail.

  These are exposed to Intune, Sentinel and ServiceNow through APIs and webhooks. That Intune has no native BLE-accessory management is an inference; confirm with Microsoft.
- **Kill switch via MDM:** admins can *deny* the microphone permission to the app on managed Android devices (track 06), which gives a tenant-wide off switch for phone capture.
- **Shared devices:** table pucks bind to rooms (e.g., Teams Rooms resource accounts) rather than people.
- **RMA / refurbish:** crypto-erase → re-provision → re-issue. No carrier lock, so the Humane e-waste problem doesn't arise.
- **Offboarding:** disabling the Entra ID account triggers disarm and wipe on next sync; data is retained per tenant policy.

### 4.15 Partner vs build

| Option | What we get | Gaps / risks | Verdict | Conf. |
|---|---|---|---|---|
| **Plaud Embedded** (Device SDK + Transcription API) | iOS 14+/Android 5.0+ SDK with "BLE device pairing out-of-the-box". Start/stop recordings from **our** app. Audio syncs to **our backend** over BLE/Wi-Fi, and we can optionally pass a `file_url` to Plaud for transcription (112 languages). Each device **binds to one app** (theft protection). **Free tier 300 h + 50 devices**. Note Pro (4-mic array) and NotePin S. Apache-2.0 Swift SDK. Vendor claims SOC 2, HIPAA, ISO 27001, EN 18031 | No India cloud region (avoid by using our own STT on SDK-retrieved audio; **verify raw audio never transits Plaud**). Per-device pricing beyond the free tier unknown. No tenant-policy enforcement on the device. Press-to-record only. Dependence on a vendor that could be acquired | **Best Phase-1 "bring-your-own recorder" integration** (US first, India once the data path is verified) | High (docs: [dev.plaud.ai](https://dev.plaud.ai/), [docs.plaud.ai](https://docs.plaud.ai/plaud-embedded/overview)) |
| **Omi** (MIT open hardware/firmware) | nRF5340 + Zephyr firmware, Opus over BLE, documented OTA, SDKs; we can fork it and add policy enforcement, LED/mute | Consumer-grade; unaudited compliance claims; no LED or mute switch on the product page; supply continuity | **Prototyping platform and reference design for our pilot badge** (Phase 1 spike, Phase 2) | High (repo) / Low (enterprise readiness) |
| Teams-certified headsets / AirPods | Excellent own-voice audio for calls and dictation; already issued by IT | System audio route, so phone-mic background rules still apply; poor at capturing others in the room | **Support as audio sources**, not as the room recorder | Med |
| Meta glasses (Device Access Toolkit) | Camera + (experimental) audio via our phone app; internal-tester distribution inside an organisation | PCM audio "unavailable for production publishing"; consumer accounts; facial-recognition controversy; ~6–8 h battery | **Optional internal pilot only** | High (docs) |
| Bee / Limitless | — | Acquired; Limitless discontinued; Bee consumer, US-only, iOS-only | **No** | High |
| White-label ODM recorder | Fast, cheap pilot hardware | Firmware quality, keys, certification under our name, supply/tariff risk | Phase 2 candidate only if we own firmware and keys | Low (unverified vendors) |
| **Our own badge** | Policy enforcement on the device; hardware trust features; HaaS margin; brand | Capital, team, 9–15+ months, certification, RMA logistics | **Phase 3, only after Gate G3** | — |

## 5. Failure mode → evidence → how PersonaAgent avoids it

| # | Failure mode (who) | Evidence | How PersonaAgent avoids it: product & technical | How PersonaAgent avoids it: business & trust |
|---|---|---|---|---|
| 1 | **Tried to replace the phone; no killer use case** (Humane, Rabbit) | Humane shipped without timers/calendar/navigation; Rabbit ~5% daily use; *"no one wants to carry around two devices"* | Device = accessory for **one job** (work conversation capture). Phone, Teams and desktop do everything else | Sell outcomes per seat (meeting memory + drafting in your voice), not a gadget |
| 2 | **Overpromised capabilities / staged demos** (Rabbit LAM; Humane TED, ice packs, edited video) | Android app + VNC browser sessions; NYT on chilled demo units | Demo only features running in a real customer tenant. Publish measured accuracy, latency and battery | Design-partner pilots and references instead of keynotes. Engineering + legal review all claims |
| 3 | **Cloud round-trip latency on the wearable** (Humane ~6 s) | Inverse review | Answers stream as text on phone/desktop. The device never waits on the cloud (§4.8) | Availability SLA, status page |
| 4 | **Thermals and battery** (Humane shutdowns, 4–5 h; Rabbit idle drain) | Inverse; Engadget | No screen, projector, camera or LTE; MCU + BLE only. **≥12 h active capture** target, verified by power profiling at EVT | Measured battery published. Replacement included in hardware-as-a-service |
| 5 | **Battery-safety recall outliving the company** (Humane Charge Case) | CPSC recall 25-026, ~10,500 units | No separate battery case in v1. Qualified cell vendors; IEC 62133-2 / UN38.3 / India IS 16046; incoming QC; serial-level traceability | Recall reserve and product-liability insurance. Recall playbook tied to the fleet inventory |
| 6 | **Hardware + separate subscription + carrier lock** (Humane $24/mo T-Mobile line) | Returns couldn't be refurbished because of T-Mobile restrictions | No SIM; BLE relay through the managed phone | Hardware inside the enterprise seat. Re-issuable fleet devices (crypto-erase → re-provision) |
| 7 | **One-time price vs recurring AI cost** (Rabbit $199) | Reported payroll arrears 2025; pivot to a $99.99/mo agent | Cost controls on STT/LLM (tracks 03/06): VAD gating, batch transcription, work-only scope | Per-seat recurring revenue. Target AI cost ≤ ~35% of seat price (recommendation) |
| 8 | **Weak security engineering** (Rabbit hard-coded keys, undeletable logs, insider leak) | Rabbitude; Rabbit's own write-up; ZDNet | Per-device identity; no secrets on the device; secure boot; signed OTA; encrypted flash; crypto-erase; least-privilege insider access | Independent pentest before pilots; devices in SOC 2 scope; published vulnerability-disclosure policy and bug bounty |
| 9 | **Bricking / stranding customers** (Humane 10 days; Limitless 14 days, 7 jurisdictions) | TechCrunch; limitless.ai; Ars Technica | Offline mode; USB export in open formats; documented protocol; firmware in escrow | Contract: ≥12-month end-of-life notice, ≥3 years of security updates, change-of-control clause, pro-rata credits |
| 10 | **Hype-driven consumer go-to-market** (Humane runway/TIME; Friend $1M subway ads) | TechCrunch; TIME | Work-only positioning; no consumer SKU in v1 | Enterprise sales motion via M365 admins and IT; conservative messaging |
| 11 | **Culture that punished dissent** (Humane) | NYT, 6 Jun 2024 (via Wikipedia) | Launch-readiness gates that engineering, security and privacy can veto; red-team reviews | Board-level hardware gate reviews (§6). Blameless post-mortems |
| 12 | **Social backlash to always-listening** (Friend, Glass 2014, Meta 2026) | TechCrunch; The Atlantic; BBC via Wikipedia | Policy-windowed, press-to-start default; LED + chime + visible mute; no camera; no face or voice biometrics | Bystander controls (pause/delete). Employee transparency dashboard. Works-council-ready documentation for later EU entry |
| 13 | **Regulatory unreadiness in a new market** (Rabbit India) | Lyu: units ready May 2024, then "regulation complications" | Design to Indian standards from EVT (battery IS 16046, charger/adapter) | Start WPC ETA / BIS CRS work **≥6 months before** India hardware shipments. Appoint an Authorised Indian Representative |
| 14 | **Credibility of founders and claims** (Rabbit GAMA) | Coffeezilla via ReadWrite | n/a | Trust centre, audited metrics, customer references, transparent leadership |
| 15 | **Dependence on a partner device that gets acquired** (Limitless → Meta, Bee → Amazon) | TechCrunch | Multi-device abstraction layer; swappable ASR (track 06) | Partner contracts with exit and notice terms. Our own device only after gates |
| 16 | **Hardware schedule slips** (Humane, Index 01 +4 months, Halo ~1 year, OpenAI → 2027) | Vendor posts; Wikipedia | EVT/DVT/PVT gates with explicit exit criteria | **Never tie revenue or fundraising milestones to a device ship date.** Budget 4–9 months of slack |


## 6. Recommended hardware roadmap with go/no-go gates

The roadmap has four phases. **No phase starts until the previous gate is met.** If a gate is missed twice, the hardware track is shelved and PersonaAgent stays software-plus-partner-devices. Thresholds are recommendations, calibrated to the founders' per-seat B2B plan. Revisit them once the market & pricing track (09) lands.

| Phase | When (indicative) | What we build / do | Team cost |
|---|---|---|---|
| **0: Software MVP** | Months 0–3 | Phone work-mode recorder (iOS/Android), Teams via Graph transcripts, persona drafting, tenant policies, US/India redaction. **No hardware.** | 0 hardware FTE |
| **1: Integrate before building** | Months 3–9 | **Bring-your-own devices:** Plaud via its Device SDK (US tenants first; verify the India data path); Omi as "experimental"; Teams-certified headsets / AirPods as call and dictation sources; optional Meta-glasses internal pilot. **2-week background-BLE spike** (§4.2). 3–5 design partners co-specify the badge. Pick US and India test labs; identify an Authorised Indian Representative | ≤0.5 FTE + contractor |
| **2: Pilot hardware** | Months 9–15 | 100–500 pilot badges: an Omi-derived or white-label ODM board running **our firmware** (policy enforcement, hardware LED/mute, secure boot), small-run enclosure, FCC route via a pre-certified radio module. India pilots only once WPC ETA + battery BIS are in hand (otherwise US-only pilots) | 1 firmware + 1 HW/ODM manager (contract OK) |
| **3: Production badge** | Months 15–30 | Custom badge (and maybe a table puck) through EVT → DVT → PVT → mass production; FCC + India certification; first run 5k–10k units; India assembly when volume justifies it. Sold only as **Capture+ seats** (hardware-as-a-service) | Hardware lead + 2–3 engineers + ODM/EMS |

**Gate G1: enter Phase 1 (month ~3+).** *All* of:
- ≥10 paying tenants **or** ≥500 paid seats.
- Phone-capture weekly active use ≥40% of capture-enabled seats, for 4 consecutive weeks.
- **Evidence of the background-start gap:** ≥25% of policy-eligible in-person meetings go uncaptured, *or* ≥30% of active users report "forgot to start / phone not with me".
- Zero Sev-1 privacy or security incidents.

**Gate G2: enter Phase 2 (pilot hardware).** *All* of:
- ≥2,000 paid seats across ≥25 tenants; logo retention ≥90%.
- Capture weekly active use ≥50% for 8 weeks.
- ≥5 memory queries per active user per week, with ≥80% of answers accepted as correct.
- **BYO-device users capture ≥1.5× more in-person hours per week than phone-only users.** This is the evidence that a device adds value.
- ≥3 design partners sign paid pilot letters of intent for ≥300 devices total, and ≥1 has a path to ≥1,000 units.
- Background-BLE spike passes on iOS and the top-5 Android OEMs in the US and India, with phone battery cost ≤10% per workday.
- Software gross margin ≥60% at current AI cost.

**Gate G3: enter Phase 3 (production).** *All* of:
- **Pilot usage:**
  - ≥60% of pilot users wear the badge ≥3 days/week after 60 days;
  - ≥99% of captured audio minutes sync successfully;
  - field battery ≥12 h active capture on pilot hardware, with a credible path to the ≥16 h production target (§4.6);
  - return/repair rate <3% per quarter.
- **Trust:**
  - bystander and employee complaint rate below an agreed threshold;
  - no high-severity findings open from the independent pentest;
  - no regulator or works-council objections in pilot customers.
- **Commercial:**
  - ≥5,000 paid seats;
  - ≥3 customers committed to ≥1,000 devices on Capture+ seats;
  - the Capture+ uplift is accepted in ≥2 price tests.
- **Unit economics:** fully-loaded unit cost ≤ ~$60 at 10k units (landed + amortised design, tooling and certification), with ≥50% hardware-as-a-service gross margin.
- **Readiness:**
  - FCC and India (WPC ETA, BIS CRS) plans and budgets signed off with labs;
  - an Authorised Indian Representative appointed;
  - **18 months of runway that does not count hardware revenue.**

**Stop / pivot signals at any point:**
- Pilot wear-time collapses after week 3 (the novelty curve that killed Rabbit usage).
- Customers reject device-side capture on privacy grounds.
- A partner device (Plaud, headset, glasses) already delivers ≥80% of the value at lower risk.
- AI cost per seat rises enough to wipe out hardware margin.


## Recommendations for PersonaAgent

**Now (MVP, months 0–3)**
1. **Build no hardware in the MVP.** Make the phone "work-mode recorder" excellent at the *one tap* the platforms require: meeting-start notifications, Live Activity, Action button/Control, Android notification tap (track 06). Get Teams audio from Graph.
2. **Reframe Pillar 2's language** from "always listening unless muted" to **"always-ready, policy-governed work capture: on during your work sessions, visibly indicated, instantly mutable."** Friend, Glass and Meta show that "always listening" invites backlash. Founder decision #4 already points this way.
3. **Instrument the MVP for the hardware gates (§6):**
   - missed-capture rate (policy-eligible meetings not captured);
   - in-person capture hours per user;
   - memory queries per user per week and answer acceptance;
   - weekly active use by tenant.
4. **Write a 2-page "Hardware Trust Spec"** and use it in sales conversations now. It covers:
   - hardware mute and an LED on the mic rail, plus a start chime;
   - no camera, no voiceprints;
   - per-device identity, secure boot, signed OTA, encrypted flash, crypto-erase;
   - an open protocol, escrow and the no-brick terms.

   It signals seriousness to security reviewers and differentiates us from Humane and Rabbit.
5. **Put no-brick and exit terms in the MSA template from day one**, for software too: ≥12-month end-of-service notice, bulk export in open formats, change-of-control clause, certified deletion.

**Phase 1 (months 3–9): integrate before building**
6. **Build a device-abstraction layer** (any audio source → the common capture pipeline). Integrate **Plaud Embedded** for US tenants first; for India, enable it only once raw audio can be pulled without transiting Plaud's cloud. Add **Omi** as experimental. Treat Teams-certified headsets and AirPods as call/dictation sources.
7. **Run the 2-week background-BLE spike** (Omi dev kit or nRF5340 DK) on iOS 26/27 and Android 15–17, including Samsung, Xiaomi, Vivo and Oppo. Write a decision memo: buffer-and-burst behaviour, reconnect gaps, phone battery cost.
8. **Recruit 3–5 design-partner tenants across the US and India** (e.g., professional services, consulting, sales-heavy teams) to co-specify the badge. Cover policies (hours, rooms, external parties), docking, form factor and IT logistics.
9. **Start India regulatory groundwork early:**
   - shortlist a BIS-recognised lab and a WPC-capable consultant;
   - identify an **Authorised Indian Representative**;
   - get a classification opinion on whether the badge falls under a CRS-listed category or only its battery and adapter do.

   Keep pilots **US-only** until India approvals are in hand (the Rabbit lesson).

**Phase 2–3 (months 9–30, only after gates)**
10. **Pilot on an Omi-derived nRF5340 design running our firmware** (100–500 units) from a small-run EMS (US) or VVDN (India). Certify for the FCC via a **pre-certified BLE module**.
11. **Production badge only after G3**, sold exclusively as **Capture+ hardware-as-a-service seats**: device included, company-owned, replaced on failure. Free pilot kits for design partners; never retail.
12. **Make in India for India volumes** once quotes confirm the duty advantage, with a Shenzhen ODM quote as benchmark. Model US tariff scenarios at sourcing time.
13. **Governance:**
    - a hardware gate review with explicit kill criteria;
    - engineering, security and privacy each hold a veto on launch readiness;
    - no consumer launch event, and every public claim backed by measured data.
14. **Re-evaluate partner vs build at Gate G2** against:
    - Plaud's roadmap (India region, team admin depth);
    - Meta's toolkit going generally available;
    - HP IQ, OpenAI (2027) and Apple wearables.

## Risks & watch-outs

| Risk | Why it matters | Mitigation | Likelihood / impact |
|---|---|---|---|
| **Recording-law and consent exposure from device capture** | **Litigation:** in In re Otter.AI (N.D. Cal.), wiretap/CIPA/BIPA claims were allowed to proceed (13 Aug 2026). Chamberlain v. Granola (Jul 2026) targets bot-free device-audio capture.<br>**Consent:** ~11 US all-party-consent states. Employer policy covers employees, not clients or visitors.<br>India: DPDP obligations (legal track) | Press-to-start default; LED + chime; external-party consent flows; consent logs; no voiceprints; legal sign-off per tenant policy template | High / High |
| **"Employer surveillance" perception** | A company-governed recorder can read as monitoring of employees, not a tool for them | Employee-controlled pause/mute; transparency dashboard; contractual limits on using captures for performance monitoring (raise with legal); visible indicators | Med / High |
| **Platform rule changes** | Apple asks for "session-based" BLE apps and may throttle heavy background use. App Review 2.5.14 requires a visible recording indication. Android OEMs kill background apps | Buffer-and-burst design; Live Activity + device LED; OEM test matrix; graceful degradation to on-device storage | Med / High |
| **Hardware execution distracts a 3–6-person team** | Hardware is capital- and attention-intensive; every peer slipped 4–12 months | Gates; partner devices first; contract hardware expertise; never tie revenue to device dates | High / High |
| **Battery safety / recall** | Humane's Charge Case recall outlived the company | Qualified cells (IEC 62133-2, UN38.3, IS 16046), no separate battery case, serial traceability, recall reserve and insurance | Low / High |
| **Security incident on device or companion app** | One incident like Rabbit's would end enterprise deals | Trust Spec controls; pentest before pilots; bug bounty; devices in SOC 2 scope; HSM-held signing keys | Med / High |
| **Partner-device vendor acquired or pivots** | Limitless → Meta, Bee → Amazon; Plaud could follow | Multi-device abstraction; exit terms in partner contracts; our own badge as the long-term hedge | Med / Med |
| **India-specific friction** | BIS/WPC timelines and CRS classification; EPR (e-waste and battery) and Legal Metrology duties; import duty (~20% on finished wearables, memory); Rabbit's stalled India launch; Plaud has no India region. **Client-secure floors in IT/BPO delivery centres often ban recording devices outright** | Early regulatory work; Authorised Indian Representative (or Indian manufacture); India assembly at volume; our own STT path for India data residency; admin-defined secure-zone auto-mute and a device inventory for physical-security teams | Med / Med |
| **Workplace-monitoring notice rules** | NY Civil Rights Law §52-c and similar state laws; NLRB GC 23-02; later the EU AI Act ban on workplace emotion recognition and German works councils | Written employee notice templates; no emotion or performance inference from audio; transparency dashboard | Med / Med |
| **Unit economics** | AI cost already ≈ $15–27/user-month; device loss and breakage in the field | Hardware-as-a-service uplift sized to recover the fully-loaded device in ≤24 months; loss and replacement policy; usage-based STT controls | Med / Med |
| **Commoditisation and Big Tech** | Meeting recording is now a feature (rabbitOS 2, Pixel, Samsung, Apple call recording). Plaud is moving into teams. Microsoft, HP IQ, Meta, Apple, OpenAI (2027) may bundle devices | Differentiate on the **M365-native persona + memory** software, tenant governance and India/US regulatory redaction, not on the gadget | High / Med |
| **EU/UK expansion later** | RED cybersecurity (EN 18031, from 1 Aug 2025). EU Battery Regulation Article 11 user-replaceable batteries from 18 Feb 2027 (with exemptions; verify). CRA obligations from 2026–27. UK PSTI. Works councils | Design for EN 18031 from EVT; assess battery replaceability before the EU SKU; works-council documentation pack | Med / Med (later) |

## Open questions / could not verify

**Could not verify this session.** The web-search budget was exhausted and The Verge, Wired, NYT and Reuters blocked fetching. Do not quote these without checking.
- **Humane:**
  - ~$850M valuation (aggregators only);
  - any 2024 convertible/debt raise;
  - The Verge's review score (4/10 remembered);
  - MKBHD view count;
  - device weight, Trust Light and depth-sensor specs;
  - the GPT-4o update;
  - the exact date of the Charge Case advisory;
  - founders' HP titles and HP IQ output in 2025–26;
  - any customer lawsuits.

  Conflicts:
  - shutdown at noon PT (TechCrunch/Engadget) vs midnight (Wikipedia);
  - layoffs ~4% vs "10%";
  - $7M (NYT, Jun 2024) vs $9M (Verge, Aug 2024) in sales (different dates).
- **Rabbit:**
  - The Verge's 3/10 score;
  - the 1,000 mAh battery;
  - Perplexity Pro bundle terms;
  - that LAM was Playwright scripting (widely reported; only "VNC sessions" confirmed);
  - total funding beyond ~$30M and whether the late-2025 round closed;
  - return rates;
  - a rumoured January 2026 device / "cyberdeck" (OS3 names an upcoming cyberdeck).

  Unit claims vary: >100k (Rabbit, May 2024) vs 130k (Forbes headline).
- **Memory wearables:**
  - Plaud revenue, units, funding and device prices (2.5M users is a vendor claim);
  - whether Plaud Embedded can return raw audio **without** transiting Plaud's cloud, and its per-device pricing;
  - Limitless pre-acquisition plans and any 2026 Meta integration;
  - Bee's current subscription and Alexa+ integration;
  - Friend's sales and 2026 status;
  - Sandbar's founders and funding;
  - Omi battery (10–14 h on the product page vs "24h+" in the README);
  - Anker Soundcore Work, Mobvoi TicNote, HiDock, Viaim and Taya (leads only).
- **Big Tech:**
  - all Ray-Ban Meta unit and capacity numbers (2M by Feb 2025; ~7M in 2025; 10M/yr capacity), which are memory only;
  - the Ray-Ban Display international pause (Jan 2026);
  - whether the Meta toolkit reached general availability (README still says preview in Oct 2026);
  - the OpenAI device's form factor (reports conflict) and exact timing beyond "2027";
  - Apple pin/glasses timelines;
  - whether Android XR glasses shipped in 2026;
  - India pricing for Ray-Ban Meta Gen 2/Oakley.
- **Hardware:**
  - chip prices and the whole BOM (estimates);
  - real-world BLE throughput per phone model;
  - (iOS behaviour after a user force-quit is now **verified**: no relaunch, per Apple QA1962);
  - Android OEM background killers;
  - that Intune cannot manage BLE accessories (inference);
  - Indian EMS capabilities, incentive schemes and duty rates;
  - current US tariff rates.
- **Certification:**
  - the exact §1.1307(b)(3)(i)(B) SAR-exemption formula (thresholds calculated from memory; confirm with the lab and KDB 447498);
  - whether BIS treats a badge recorder as a smart watch or wireless earphone;
  - whether cells inside *non-notified* products need IS 16046-2 registration;
  - CRS and WPC fees and lead times;
  - MTCTE scope;
  - IATA's 2026 state-of-charge rules;
  - EN 18031 citation details, Battery Regulation Article 11 derogation wording, and PSTI scope for enterprise-only products;
  - FCC 2025 lab-recognition rules;
  - all certification cost figures (estimates; get 2–3 lab quotes).

  Verified: Bluetooth SIG fees, the CRS product list, CRA dates, PSTI requirements, the IATA 2025 packaging change, the FCC module rule, the 1 mW exemption, and the portable-device definition.

**Open questions for the founders and other tracks:**
1. Will design-partner customers accept **device-side capture of external parties** (clients, visitors) at all, or only internal meetings? This decides whether the badge is viable in the US all-party-consent states (legal track).
2. Should the badge default to **press-to-start** (Bee, Plaud, Index 01 norm) or **policy-armed auto-start** in scheduled meetings? Settle this with legal and two design partners before EVT.
3. Is a **table puck** (meeting rooms, 1:1s) a better first device than a personal badge for M365 buyers who already have Teams Rooms? Test both in Phase 2 discovery.
4. Can we get **India data residency** for partner-device audio (Plaud) and STT, or must India tenants wait for our own badge plus an India-region STT (track 06)?
5. What hardware-as-a-service price uplift do mid-market vs enterprise buyers accept ($6–10/user-month estimate)? This needs the market & pricing track (09).
6. Does HP IQ (ex-Humane) plan enterprise capture devices that could become a partner or competitor?

## Sources

Raw fact sheets behind this report, with per-claim confidence: `docs/research/_raw/08a-rabbit-r1-factsheet.md`, `08b-humane-ai-pin-factsheet.md`, `08c-ai-memory-wearables-factsheet.md`, `08d-big-tech-wearables-factsheet.md`, `08e-hardware-engineering-factsheet.md`, `08f-certifications-factsheet.md`. Cross-track inputs: `06-always-on-capture-and-stt.md` (phone background-mic rules, Intune app config, STT cost), `07-legal-regulatory-privacy.md` (consent, BIPA, India SPDI/DPDP), `02-integration-surfaces-and-meeting-capture.md` (Graph transcripts).

**Humane AI Pin**
- https://en.wikipedia.org/wiki/Humane_Inc. · https://en.wikipedia.org/wiki/Ai_Pin
- https://techcrunch.com/2023/03/08/humane-the-secretive-ai-startup-founded-by-ex-apple-employees-raises-another-100m/
- https://techcrunch.com/2021/09/01/humane-a-stealthy-hardware-and-software-startup-co-founded-by-an-ex-apple-designer-and-engineer-raises-100m/
- https://www.axios.com/2023/04/21/humane-ai-powered-wearable
- https://techcrunch.com/2023/09/30/humanes-ai-pin-debuts-on-the-paris-runway/
- https://time.com/collection/best-inventions-2023/6327143/humane-ai-pin/
- https://www.engadget.com/humane-lays-off-staff-before-its-ai-pin-begins-shipping-103548514.html
- https://techcrunch.com/2024/02/23/humane-pushes-ai-pin-ship-date-to-mid-april/
- https://www.inverse.com/tech/humane-ai-pin-in-depth-review
- https://www.theverge.com/24126502/humane-ai-pin-review (not fetchable; quoted via Wikipedia)
- https://www.youtube.com/watch?v=TitZV6k8zfA (MKBHD)
- https://www.fastcompany.com/91092156/humanes-ai-pin-was-never-going-to-be-great
- https://www.bloomberg.com/news/articles/2024-05-22/wearable-ai-startup-humane-is-said-to-explore-potential-sale
- https://www.nytimes.com/2024/06/06/technology/humane-ai-pin.html (not fetchable; via Wikipedia)
- https://www.macrumors.com/2024/08/07/humane-ai-pin-returns
- https://www.engadget.com/ai/people-are-returning-humane-ai-pins-faster-than-the-company-can-sell-them-191523105.html
- https://liliputing.com/humane-ai-pin-gets-a-200-price-cut-still-costs-499-24-monthly-subscription/
- https://www.cpsc.gov/Recalls/2025/Humane-Recalls-Charge-Case-Accessory-for-Ai-Pin-Due-to-Lithium-Battery-Fire-Hazard
- https://www.bloomberg.com/news/articles/2025-02-18/hp-116-million-deal-for-humane-includes-ip-but-no-ai-pin-device
- https://www.theverge.com/news/614883/humane-ai-hp-acquisition-pin-shutdown
- https://www.fortune.com/2025/02/19/hp-humane-deal-ai-pin-shutting-down
- https://support.humane.com/hc/en-us/articles/34243204841997-Ai-Pin-Consumers-FAQ (offline since shutdown)
- https://arstechnica.com/gadgets/2025/02/truly-a-middle-finger-humane-bricking-700-ai-pins-with-limited-refunds/

**Rabbit R1**
- https://www.rabbit.tech/newsroom/introducing-r1 · https://www.rabbit.tech/newsroom/rabbit-raises-20m · https://www.rabbit.tech/newsroom/rabbit-raises-additional-10m
- https://techcrunch.com/2023/10/04/rabbit-is-building-an-ai-model-that-understands-how-software-works/
- https://siliconangle.com/2023/12/21/consumer-ai-startup-rabbit-raises-10m-khosla-ventures/
- https://en.wikipedia.org/wiki/Rabbit_r1
- https://readwrite.com/youtuber-coffeezilla-destroys-rabbit-r1-ai-company-in-latest-investigation/
- https://www.shacknews.com/article/138258/rabbit-r1-ai-companion-10000-sales · https://mobilesyrup.com/2024/01/11/rabbit-r1-sold-10000-24-hours/
- https://www.fastcompany.com/91013196/how-design-drove-10m-in-pre-orders-for-rabbit-r1-ai-hardware (headline only)
- https://www.rabbit.tech/newsroom/quarterly-update-2024-q1
- https://www.forbes.com/sites/johnkoetsier/2024/06/18/rabbit-sells-130000-r1-units-says-early-bugs-mostly-fixed/ (headline only)
- https://www.androidauthority.com/rabbit-r1-is-an-android-app-3438805/
- https://www.techradar.com/computing/artificial-intelligence/rabbit-denies-that-the-rabbit-r1-is-fundamentally-just-an-android-app
- https://www.engadget.com/rabbit-r1-review-a-199-ai-toy-that-fails-at-almost-everything-161043050.html
- https://www.engadget.com/rabbit-r1-security-issue-allegedly-leaves-sensitive-user-data-accessible-to-anybody-120024215.html
- https://www.techradar.com/pro/security/rabbit-r1-jailbreakers-uncover-huge-security-flaws-including-some-that-let-internal-data-be-viewed-by-literally-anyone
- https://www.rabbit.tech/newsroom/security-pentest
- https://www.zdnet.com/article/rabbit-r1-ai-assistant-has-secretly-been-storing-user-chats-that-cant-be-deleted/ (via Wikipedia)
- https://9to5google.com/?p=642646 · https://www.theverge.com/2024/9/25/24254253/rabbit-r1-5000-daily-users-ai-gadget (headline)
- https://techcrunch.com/2024/09/23/rabbits-web-based-large-action-model-agent-arrives-on-r1-as-early-as-this-week/
- https://www.rabbit.tech/newsroom/teach-mode-beta · https://www.rabbit.tech/newsroom/rabbit-intern-launch · https://www.rabbit.tech/newsroom/rabbitos-2-launch · https://www.rabbit.tech/newsroom/rabbitos-3-launch
- https://www.techradar.com/ai-platforms-assistants/rabbitos-2-gives-the-rabbit-r1-a-bold-new-look-and-some-very-cool-ai-powers
- https://www.engadget.com/rabbit-plots-its-redemption-arc-120000271.html
- https://finance.yahoo.com/news/next-rabbit-employees-haven-t-151201843.html (Tom's Guide syndication)

**Memory wearables and recorders**
- https://techcrunch.com/2025/12/05/meta-acquires-ai-device-startup-limitless/ · https://www.limitless.ai/ · https://help.limitless.ai/
- https://techcrunch.com/2025/07/22/amazon-acquires-bee-the-ai-wearable-that-records-everything-you-say/ · https://www.bee.computer/ · https://docs.bee.computer/
- https://www.plaud.ai/ · https://www.plaud.ai/pages/plaud-ai-plan-pricing · https://www.plaud.ai/pages/plaud-team · https://www.plaud.ai/pages/bulk-order · https://www.plaud.ai/pages/trust · https://www.plaud.ai/products/notepin
- https://dev.plaud.ai/ · https://docs.plaud.ai/plaud-embedded/overview · https://docs.plaud.ai/documentation/plaud_app/mcp · https://github.com/Plaud-AI
- https://github.com/BasedHardware/omi · https://www.omi.me/pages/product
- https://en.wikipedia.org/wiki/Avi_Schiffmann · https://www.404media.co/ai-friend-company-spent-1-8-million-and-most-its-funds-on-domain-name/ · https://techcrunch.com/2025/09/27/ai-startup-friend-spent-more-than-1m-on-all-those-subway-ads/ · https://www.theatlantic.com/technology/2025/10/friend-ai-companion-ads/684451/
- https://www.sandbar.com/ · https://shop.sandbar.com/
- https://repebble.com/blog/meet-pebble-index-01-external-memory-for-your-brain · https://repebble.com/blog/index-01-is-in-mass-production · https://repebble.com/index
- https://brilliant.xyz/ · https://brilliant.xyz/products/halo

**Big Tech**
- https://en.wikipedia.org/wiki/Ray-Ban_Meta · https://en.wikipedia.org/wiki/Reality_Labs · https://en.wikipedia.org/wiki/EssilorLuxottica
- https://about.fb.com/news/2025/09/meta-ray-ban-display-ai-glasses-emg-wristband/
- https://developers.meta.com/blog/introducing-meta-wearables-device-access-toolkit/ · https://github.com/facebook/meta-wearables-dat-ios · https://wearables.developer.meta.com/docs/develop/
- https://en.wikipedia.org/wiki/Io_(company) · https://openai.com/sam-and-jony/
- https://www.apple.com/newsroom/2025/09/introducing-airpods-pro-3-the-ultimate-audio-experience/
- https://en.wikipedia.org/wiki/Android_XR
- https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot

**Enterprise-wearable precedents**
- https://www.stryker.com/us/en/about/news/2022/stryker-completes-acquisition-of-vocera-communications.html · https://www.stryker.com/us/en/smart-care/products/vocera-smartbadge.html · https://en.wikipedia.org/wiki/Vocera_Communications
- https://en.wikipedia.org/wiki/Google_Glass · https://en.wikipedia.org/wiki/HoloLens_2 · https://en.wikipedia.org/wiki/Pebble_(watch) (Pebble shutdown, Rebble, PebbleOS open-sourced)

**Hardware, platforms and device management**
- https://www.nordicsemi.com/Products/nRF5340 · https://www.nordicsemi.com/Products/nRF54L15 · https://www.nordicsemi.com/Products/nRF54H20
- https://www.espressif.com/en/products/socs/esp32-s3 · https://ambiq.com/apollo510/ · https://invensense.tdk.com/products/digital/t5838/
- https://wiki.xiph.org/Opus_Recommended_Settings · https://github.com/BasedHardware/omi/tree/main/omi/firmware/boards/omi
- https://developer.apple.com/library/archive/documentation/NetworkingInternetWeb/Conceptual/CoreBluetooth_concepts/CoreBluetoothBackgroundProcessingForIOSApps/PerformingTasksWhileYourAppIsInTheBackground.html
- https://developer.apple.com/library/archive/qa/qa1962/_index.html (Bluetooth state-restoration relaunch conditions)
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start · https://developer.android.com/develop/background-work/services/fgs/service-types · https://developer.android.com/develop/connectivity/bluetooth/companion-device-pairing
- https://learn.microsoft.com/en-us/intune/intune-service/apps/app-configuration-policies-overview

**Certification and regulation**
- https://www.law.cornell.edu/cfr/text/47/15.212 (FCC modular transmitters)
- https://www.law.cornell.edu/cfr/text/47/1.1307 (RF-exposure exemptions)
- https://en.wikipedia.org/wiki/Bureau_of_Indian_Standards (CRS, Authorised Indian Representative)
- https://en.wikipedia.org/wiki/Wireless_Planning_and_Coordination_Wing (WPC/ETA for Bluetooth imports)
- https://www.law.cornell.edu/cfr/text/47/2.1093 (portable-device definition) · https://www.law.cornell.edu/cfr/text/47/1.1310 (SAR limits)
- https://www.crsbis.in/BIS/products-bis.do (BIS CRS product list)
- https://eservices.dot.gov.in/saral-sanchar (WPC ETA portal; saralsanchar.gov.in redirects here)
- https://www.bluetooth.com/develop-with-bluetooth/qualification-listing/qualification-listing-fees/ (fees effective 1 Mar 2026)
- https://www.iata.org/en/programs/cargo/dgr/lithium-batteries/ (2025 packaging change)
- https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act (CRA dates)
- https://www.gov.uk/government/publications/the-uk-product-security-and-telecommunications-infrastructure-product-security-regime (UK PSTI)
- https://www.pewresearch.org/internet/2014/04/17/us-views-of-technology-and-the-future/ (Pew 2014; URL recalled, not re-fetched)
- https://wiki.xiph.org/Opus_Recommended_Settings (Opus bitrates)
