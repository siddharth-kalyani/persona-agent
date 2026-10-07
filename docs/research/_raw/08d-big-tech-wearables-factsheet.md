# 08d: Big-tech AI wearables fact sheet (raw input for 08-ai-hardware-lessons.md)

Prepared 2026-10-06. **How this was sourced:** the session's WebSearch budget ran out before this track began, and WebFetch calls kept hitting session limits. Each item is labelled one of two ways:
- **fetched**: read directly in this session. Wikipedia pages were read through a summariser, so check them against the primary source they cite.
- **unverified (memory)**: comes from analyst knowledge (training data up to about mid-2026) and needs a primary-source check before it is quoted.

Format: claim | numbers/dates | source | confidence (H/M/L).

## 1. Meta smart glasses

| Claim | Numbers / dates | Source | Conf. |
|---|---|---|---|
| Ray-Ban Meta Gen 1 launch | Announced 27 Sep 2023; on sale 17 Oct 2023 | https://en.wikipedia.org/wiki/Ray-Ban_Meta (fetched) | H |
| Early sales milestone and capacity plan | ~2M units sold since Oct 2023. Disclosed by EssilorLuxottica with FY2024 results (Feb 2025), together with a goal of 10M units/yr capacity by end-2026 | unverified (memory) | M |
| 2025 momentum | EssilorLuxottica said H1-2025 Ray-Ban Meta revenue was up >200% YoY (Jul 2025). FY2025 units reported at roughly 7M (Feb 2026). Reported talks on lifting capacity toward 20M+ | unverified (memory) | M / L / L |
| Category share | Meta ~73% of global smart-glasses shipments in H1 2025; category +110% YoY (Counterpoint) | unverified (memory) | M |
| Meta–EssilorLuxottica equity | Talks on a ~5% stake reported Jul 2024 (fetched). Meta took ~3% (reported Jul 2025) | https://en.wikipedia.org/wiki/EssilorLuxottica (talks, fetched); stake size unverified (memory) | M / L |
| Ray-Ban Meta Gen 2 | Announced and on sale 17 Sep 2025 (Connect); from $379; ~8h typical battery (about 2x Gen 1); case adds ~48h; 3K video | unverified (memory). The Wikipedia summariser wrongly said "not released", treated here as a summariser error | M |
| Oakley Meta HSTN | Announced 20 Jun 2025; released 26 Aug 2025; $399 ($499 limited edition); ~8h | Dates from Wikipedia (fetched); price and battery unverified (memory) | M |
| Oakley Meta Vanguard (sport) | Announced Sep 2025; $499; ~9h; shipped ~21 Oct 2025; Garmin/Strava integration | Announcement from Wikipedia (fetched); the rest unverified (memory) | M |
| **Meta Ray-Ban Display + Neural Band** | Announced 17 Sep 2025. **$799** including the EMG Neural Band. US sales from **30 Sep 2025** at Best Buy, LensCrafters, Sunglass Hut, Ray-Ban stores and select Verizon stores, with in-person demo and fitting. Glasses up to **6h** mixed use (30h with case); Neural Band up to **18h**. Display sits off to the side and is "not always on". Canada, France, Italy and UK planned for "early 2026" | https://about.fb.com/news/2025/09/meta-ray-ban-display-ai-glasses-emg-wristband/ (fetched) | H |
| Display international rollout paused | Jan 2026 (CES): Meta paused the early-2026 expansion to UK/FR/IT/CA, citing "unprecedented demand and limited inventory", and prioritised the US backlog | unverified (memory); not in the Sep 2025 post | M |
| New 2026 models | Wikipedia lists a "**Meta Glasses**" model announced and released 23 Jun 2026 at **$299**. Meta's DAT docs list a "**Ray-Ban Meta Optics**" model | Wikipedia Ray-Ban Meta (fetched, no primary check); https://wearables.developer.meta.com/docs/develop/ (fetched) | L / H (name only) |
| Reality Labs economics | ~10% of RL jobs cut in 2026; ~$80B cumulative operating losses since late 2020; commercial Quest sales stop 20 Feb 2026 (an exit from enterprise XR) | https://en.wikipedia.org/wiki/Reality_Labs (fetched) | M |
| **India** | Ray-Ban Meta (Gen 1) launched in India in May 2025 from about **₹29,900**. Meta AI in Hindi and UPI Lite voice payments on the glasses announced late 2025. Gen 2 / Oakley India pricing (~₹39,900+) unconfirmed. Ray-Ban Display **not sold in India** | unverified (memory) | M (launch) / L (rest) |
| Enterprise / managed-device programme | None found for the glasses. They are consumer devices tied to personal Meta accounts and the Meta AI app. Meta is also leaving enterprise Quest (row above) | inference + Reality Labs page (fetched) | L-M |

### Privacy design and controversies

| Claim | Detail | Source | Conf. |
|---|---|---|---|
| Capture LED | Hard-wired LED shows when the camera is recording | Wikipedia Ray-Ban Meta (fetched) | H |
| Tamper detection | Gen 1 (2023) refused to capture if the LED was covered (memory). **Jul 2026:** Meta now disables the camera when it detects tampering with or damage to the LED | Wikipedia (fetched) + memory | M |
| LED-defeat mods | 404 Media (Oct 2025) reported a ~$60 hobbyist service that disables the LED | unverified (memory) | M |
| Face-search doxxing demo | Oct 2024: Harvard students (I-XRAY) paired the glasses with PimEyes to identify strangers in real time | Wikipedia (fetched) | H |
| Covert filming | Jan 2026: BBC reported users filming women without their knowledge and posting the clips to TikTok | Wikipedia citing BBC (fetched) | M |
| Facial recognition | **Feb 2026**: NYT reported "Meta Plans to Add Facial Recognition Technology". **Jun 2026**: Wired reported Meta "had begun shipping face-recognition code" | Wikipedia citing NYT and Wired (fetched) | M |
| Data defaults | Apr 2025 policy change: Meta AI camera features on by default unless "Hey Meta" is off; voice recordings stored by default (up to ~1 year), removable only by manual deletion | unverified (memory) | M |

## 2. Meta Wearables Device Access Toolkit (DAT)

| Claim | Detail | Source | Conf. |
|---|---|---|---|
| Announcement | **18 Sep 2025** (Connect); blog updated **4 Dec 2025** | https://developers.meta.com/blog/introducing-meta-wearables-device-access-toolkit/ (fetched) | H |
| Architecture | The SDK lives inside the developer's **iOS/Android phone app**, not on the glasses. Repos: github.com/facebook/meta-wearables-dat-ios and -android | blog + https://raw.githubusercontent.com/facebook/meta-wearables-dat-ios/main/README.md (fetched) | H |
| Initial capabilities | The first-person camera, plus mics and open-ear speakers for "hands-free information retrieval and communication" | blog (fetched) | H |
| Current capabilities (README, Oct 2026) | Video-frame streaming, with photo capture while streaming. "Synchronized PCM audio through Camera Stream (**experimental; unavailable for production publishing**)". Standalone photo capture is also experimental. "Display, inputs, motion, and speech" features on supported glasses (Display features apply to Meta Ray-Ban Display). MockDevice simulator. **v1.0.0** Swift Package | README (fetched; wording via summariser) | H |
| Audio path that can ship today | Apps use the glasses' mic and speakers through **standard Bluetooth headset profiles (HFP/A2DP)**, i.e. narrow/wide-band mono call audio | unverified (memory); consistent with PCM-via-SDK being experimental | M |
| Supported glasses | "Ray-Ban Meta (Gen 1 and Gen 2), Ray-Ban Meta Optics, and Meta Ray-Ban Display". Oakley not listed on that page | https://wearables.developer.meta.com/docs/develop/ (fetched) | H |
| Limits | No Meta AI / "Hey Meta" voice-command access in the initial preview, described as a "key area we're exploring" | blog (fetched) | H |
| Status / GA | Developer preview, with "limited publishing to select partners"; **GA planned "in 2026"**. When fetched in Oct 2026 the README still said "in developer preview", so there is **no evidence GA has happened** | blog + README (fetched) | H / M |
| **Internal / enterprise distribution** | During the preview, developers can "share what they've built to **testers within their organizations and teams**". Only authorised partners may publish publicly. No MDM or fleet-management programme found | blog (fetched); MDM absence unverified | H / L |
| Terms | Meta Wearables Developer Terms and Acceptable Use Policy. The SDK collects usage data (opt-out via Info.plist) | README (fetched) | H |
| Launch partners | 18Birdies, Be My Eyes, HumanWare, Streamlabs, L+R, **Microsoft Seeing AI**, Pixel and Texel, Twitch | blog (fetched) | H |

**What this means for PersonaAgent (analysis):** continuous meeting capture through Meta glasses could only ship over Bluetooth headset audio, with our phone app active the whole time. The SDK's PCM audio feature is experimental and cannot be published. Streaming the mic all day would drain the battery: Gen 2 is rated ~8h of *typical* use, so continuous streaming would be less (an estimate, not tested). The glasses are tied to personal consumer accounts, and the facial-recognition controversy is a reputational risk with enterprise buyers. The internal-tester route lets us run **an optional pilot inside a customer's own organisation**. Do not make the glasses a v1 dependency.

## 3. OpenAI x io (Jony Ive / LoveFrom)

| Claim | Detail | Source | Conf. |
|---|---|---|---|
| io founding | Founded 2024 by Jony Ive, Scott Cannon, Evans Hankey and Tang Tan | https://en.wikipedia.org/wiki/Io_(company) (fetched) | H |
| Acquisition | Announced **21 May 2025**; closed **9 Jul 2025**; **~$6.5B** (all-stock); **~55** staff. Cannon, Hankey and Tan joined OpenAI. Ive and LoveFrom stayed independent and took on design work across OpenAI | Wikipedia (fetched); https://openai.com/sam-and-jony/ (exists, returned 403 to fetch) | H |
| Prior stake | OpenAI already held ~23% of io | Wikipedia (fetched) | M |
| iyO trademark case | iyO v. IO Products (N.D. Cal.): a TRO in Jun 2025 forced OpenAI to take down the "io" branding and launch video. Tang Tan's declaration said the prototype "is not an in-ear device, nor a wearable device" and was at least a year from sale | unverified (memory; The Verge, Jun 2025) | M |
| **Branding dropped, delayed to 2027** | 2026: OpenAI abandoned the "io" name for its hardware and pushed the hardware to **2027**. A court filing reportedly said no customer shipments before **end-Feb 2027** | Wikipedia citing Wired (Maxwell Zeff, "OpenAI Abandons 'io' Branding for Its AI Hardware") (fetched); filing detail unverified (memory) | M |
| Concept | A "third core device" alongside laptop and phone; screenless and context-aware. WSJ: Altman told staff the aim was to ship 100M units faster than anyone has. FT (Oct 2025): palm-sized, with mics, cameras and speaker, held back by compute cost, assistant "personality" and privacy problems with always-listening | unverified (memory) | M |
| Timing statements | Nov 2025, Altman and Ive: launch in "less than" two years. Jan 2026 (Axios, Davos): OpenAI's Chris Lehane said it was "on track" to unveil in H2 2026 | unverified (memory) | L-M |
| Form factor and manufacturing reports | The Information (early 2026): first device a camera-equipped smart speaker at ~$200–300, with glasses and a lamp later. Earlier earbud rumours ("Sweetpea"). Manufacturing linked to Luxshare, later Foxconn | unverified (memory) | L |

## 4. Apple

| Claim | Detail | Source | Conf. |
|---|---|---|---|
| AirPods Pro 3 | Announced **9 Sep 2025**; **$249**; on sale 19 Sep 2025. Up to 8h with ANC (+33%), 10h in transparency/hearing modes. Infrared PPG heart-rate sensor | https://www.apple.com/newsroom/2025/09/introducing-airpods-pro-3-the-ultimate-audio-experience/ (fetched) | H |
| Live Translation on AirPods | Works on AirPods Pro 3, AirPods Pro 2 and AirPods 4 (ANC) with an Apple Intelligence iPhone on iOS 26. EN/FR/DE/PT/ES at launch; IT/JA/KO/ZH (simplified) by end-2025. Beta; "may not be available in all regions" | Apple newsroom (fetched) | H |
| iOS 26 capture features | "Studio-quality" voice recording through AirPods (AirPods 4 / 4 ANC / Pro 2 and later) in Camera, Voice Memos, FaceTime and CallKit apps; stem press works as a camera remote (WWDC, 9 Jun 2025) | unverified (memory) | M |
| Consent norm | iOS 18.1 (Oct 2024): Phone-app call recording plays an **automatic audible notice to all participants**; transcripts and summaries land in Notes | unverified (memory) | M-H |
| Glasses | Bloomberg (Oct 2025): Apple paused a lighter Vision headset to prioritise smart glasses. A display-less model would be unveiled as early as 2026 and ship in 2027 | unverified (memory) | M |
| AI pin / pendant | The Information (Jan 2026): an AirTag-sized AI pin with cameras, mics and speaker, possibly 2027. Bloomberg (Feb 2026): Apple speeding up glasses, a pendant and camera AirPods | unverified (memory) | L |

## 5. Google and Samsung

| Claim | Detail | Source | Conf. |
|---|---|---|---|
| Android XR | Announced 12 Dec 2024 | https://en.wikipedia.org/wiki/Android_XR (fetched), citing https://www.theverge.com/2024/12/12/24319528/google-android-xr-samsung-project-moohan-smart-glasses | H |
| Samsung Galaxy XR headset | Launched Oct 2025 (Wikipedia says 20 Oct; memory says 21–22 Oct, US/KR); **$1,799** | date fetched; price unverified (memory) | M |
| Glasses partners | I/O, 20 May 2025: Gentle Monster, Warby Parker and Samsung. Google committed up to $150M to Warby Parker ($75M development plus up to $75M equity). Kering Eyewear joined later | unverified (memory) | M |
| 2026 glasses | Dec 2025 (Android Show: XR Edition): first Android XR glasses due in 2026 in two types, screen-free AI glasses and display glasses, from Samsung, Warby Parker and Gentle Monster; Xreal Project Aura | unverified (memory) | L-M |
| Shipped by Oct 2026? | **Could not verify** | n/a | n/a |
| Phone-side capture | Pixel Recorder: on-device transcription and Gemini summaries. Pixel 9 Call Notes (Aug 2024): call recording with participant notice. Samsung Galaxy AI Transcript Assist and call transcription. Gemini Live on Pixel Buds and Galaxy Buds | unverified (memory) | M |

## 6. Amazon and Microsoft

| Claim | Detail | Source | Conf. |
|---|---|---|---|
| Amazon x Bee | Acquisition announced 22 Jul 2025 ($49.99 wrist/clip recorder). Amazon said Bee would continue and integrate with Alexa over time; features shown at CES 2026 | unverified (memory); see track 08c | M |
| Alexa+ | Announced 26 Feb 2025; free with Prime, otherwise $19.99/mo; US rollout through 2025–26 | unverified (memory) | M |
| Echo Frames and glasses | Echo Frames (3rd gen, 2023, $269.99) are audio-only, with no camera. Delivery-driver glasses ("Amelia") Oct 2025. Consumer display glasses reported for late 2026/27 | unverified (memory) | M / L |
| Microsoft | No capture wearable. HoloLens 2 production ended Oct 2024; IVAS moved to Anduril (2025). **Seeing AI is a DAT launch partner** (fetched). The 2024 Windows Recall backlash ended in an opt-in, encrypted relaunch (2025), a direct lesson for always-on capture. Dragon Copilot (Mar 2025) does phone-based ambient clinical capture in an enterprise setting | DAT blog (fetched); the rest unverified (memory) | M |

## 7. Patterns (analysis)

- **Why Meta glasses work:**
  - A fashion-first form factor with EssilorLuxottica retail and prescription distribution.
  - A **phone companion** that offloads compute and connectivity to the phone.
  - Everyday utility first (photos, open-ear audio, calls), with AI layered on top.
  - **$299–$499 with no subscription.**
  - Three generations of iteration since Ray-Ban Stories (2021).
  - A visible, tamper-checked capture LED.
- **Where Meta struggles:**
  - Display units are supply-limited, and the international rollout was paused (memory).
  - Privacy and facial-recognition backlash.
  - About $80B of Reality Labs losses.
  - Developer access is still in preview, with audio streaming experimental.
  - Consumer accounts don't suit company-governed deployments.
- **Even the best-funded teams are slow.** OpenAI/io slipped to 2027 and Apple/Google AI glasses are not confirmed shipping, so always-on ambient AI hardware is hard (compute, privacy, "personality").
- **Platform consent norms.** Apple, Google and Samsung all announce call recording to participants. PersonaAgent's work-only, company-governed recorder should match or exceed that (LED, audible or visual notice, admin policy).
- **Enterprise implication.** Phone-first capture, plus headsets and earbuds that companies already issue, carries less risk than glasses. Treat Meta glasses as an optional pilot through internal-tester distribution, not a platform dependency.

## Conflicts and unverified items

1. Display announcement date: the newsroom says 17 Sep 2025 and Wikipedia says 18 Sep. Use 17 Sep.
2. Galaxy XR launch date: 20 Oct versus 21–22 Oct 2025.
3. Every unit and capacity figure (2M, >200%, ~7M, 10M/20M) and the Counterpoint shares are **memory only**. Check them against EssilorLuxottica results releases and earnings calls.
4. The Display international pause (Jan 2026) is memory only.
5. "Meta Glasses" ($299, 23 Jun 2026) and "Ray-Ban Meta Optics" appeared in fetched pages but were not checked against Meta primary sources.
6. Reports on OpenAI's device form factor conflict with each other (screenless pocket device, camera smart speaker, earbuds). Only the 2027 delay is backed by a fetched source.
7. DAT general availability is not confirmed as of Oct 2026, and no enterprise MDM or fleet programme was found.
8. India pricing (Gen 2, Oakley) and the Hindi/UPI features need confirming on Ray-Ban India and the Meta India newsroom.
9. The Apple pin/glasses timelines and Google's 2026 glasses launches come from rumour-stage reporting held in memory only.
