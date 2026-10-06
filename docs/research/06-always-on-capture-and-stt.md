# 06 — Always-on capture on phones & wearables, speech-to-text, diarization and cost per user

*Research track 06 · PersonaAgent founding team · prepared 2026-10-05/06 · status: v1.0 (complete)*

**Scope.** Pillar 2 ("always-on memory capture"): phone capture on iOS/Android (later a wearable), voice-activity detection (VAD), speech-to-text (STT), diarization/speaker ID, on-device vs cloud, and cost per user. Teams bot/transcript APIs and desktop capture are covered by track 02; legal consent law by the legal track; redaction design by track 10.

**Founder decisions applied (2026-10-05):** first buyer = Microsoft 365 mid-market & enterprise teams (per-seat B2B) · v1 regions = **United States and India** (EU/UK later) · team of 3–6 engineers, ~3-month MVP · recorder is **work-only and tenant-admin governed** (no personal lifelogging in v1) · Phase-1 redaction targets US + Indian regulatory requirements.

**Confidence labels:** **(High)** = verified in a primary source this session · **(Med)** = secondary source or older primary source · **(Low)** = inference/estimate, reasoning shown. Prices are list prices seen in Oct 2026 unless stated otherwise; re-check them before you sign anything.

---

## 0. Executive summary

- **Phones can record a full workday, but the app can't switch the mic on by itself.**
  - On iOS (`audio` background mode) and on Android (a foreground service, FGS, of type `microphone`), capture runs for 10+ hours once the user starts it in the foreground. Neither platform caps the duration **(High)**.
  - **Neither OS lets a third-party app start the mic from the background.** Calendar events, geofences, alarms, push messages and reboots can't start recording **(High)**.
  - So the "always-on" recorder becomes a **work-mode recorder**:
    - a work session the user starts with one tap, inside admin-set windows
    - calendar prompts that start capture with one tap
    - quick capture from Control Center, the Action button or a Quick Settings tile
  - Policy can **pause** capture automatically. It can't **cold-start** it.
- **Calls are off-limits on both OSes.** No third-party app can get cellular call audio. A VoIP call on the same phone (e.g. Teams) takes the mic away from us **(High)**. Teams calls come from Graph transcripts (track 02). Native call recordings, which announce themselves to participants, can only be brought in through the share sheet.
- **iOS gotchas:**
  - We can't restart recording from the background after a stop. Resuming after a call is expected to work but must be tested on iOS 26/27.
  - **Live Activities end after 8 h.** An `AudioRecordingIntent` recording *requires* a Live Activity.
  - The orange mic dot can't be hidden.
  - Apple Watch is only usable as a remote control and for quick notes.
  - **iOS 27 shipped on 14 Sep 2026** with new audio-session resumption notifications.
  - Review rule 2.5.14 requires explicit consent plus a visible recording indicator.
- **Android gotchas:**
  - Battery killers from the OEMs that dominate India (Xiaomi, Vivo, Oppo, realme, OnePlus, Samsung) are the biggest reliability risk. Plan a per-OEM setup wizard, a heartbeat and gap alerts.
  - Google Play requires a declaration and video for the `microphone` FGS, plus a prominent disclosure. Play can classify us as a "monitoring" app if **admins can browse employees' recordings**, so recordings must stay **private to the user** (admins set policy only).
- **On-device processing:** voice-activity detection (VAD, Silero) and Opus compression on the phone, transcription in the cloud.
  - Silero VAD costs <1 ms per 30 ms frame.
  - Opus at 16 kbps is ≈7.2 MB per speech-hour, so a heavy user uploads ≈0.55 GB/month.
  - Storage, requests and data transfer come to **≈$0.05 per user-month**, which is negligible.
  - Use on-device ASR only for foreground "live" moments. Apple SpeechTranscriber covers en-US and probably en-IN, but **not Hindi**. Android has no platform ASR built for long background use.
- **Amazon Transcribe now costs $0.006/min ($0.36/h) for batch and $0.010/min for streaming**, flat, in both us-east-1 and Mumbai **(High: AWS price file published 2026-09-11)**. The PII add-on is +$0.144/h. It is a good MVP engine for both regions, but at scale it costs **$12 per typical / $28 per heavy user-month**, too much against ≈$13–23 of LLM cost per seat.
- **Cheapest options per audio-hour** (list prices):

  | Engine | $/h |
  |---|---|
  | Self-hosted Parakeet + diarization on L4 GPUs | ≈$0.003–0.02 → **$0.1–1.5 per user-month** |
  | Soniox | $0.10 |
  | Speechmatics Melia | $0.12 |
  | Azure batch | $0.18 |
  | OpenAI gpt-4o-mini-transcribe | $0.18 |
  | AssemblyAI Universal-3.5 Pro (+diarization) | $0.23 |
  | Deepgram Nova-3 | $0.26 |
  | Sarvam | ₹30 ≈ $0.34 |

  A warm GPU floor (≈$250–300 per month per region at business hours, ≈$590–710 at 24×7) breaks even against Transcribe at **~10–25 heavy users per region**.
- **India residency.** Audio stays in India by design only with Transcribe in Mumbai, **Azure Speech Central India** (which processes data only in-region), self-hosted GPUs in ap-south-1, or a vendor with an India-processing contract.
  - Sarvam's privacy policy allows processing on US clouds and training unless you opt out.
  - Google Chirp 3 has no India region.
- **Hinglish is the biggest accuracy unknown.**
  - Only Deepgram `multi`, Sarvam `codemix` and AssemblyAI U3.5 Pro claim real intra-sentence Hindi–English switching. Transcribe and Azure don't do it.
  - We found no independent Hinglish or Indian-English benchmark.
  - Open models: Parakeet is English-only and IndicConformer has no English. NVIDIA's **Nemotron 3.5 ASR (hi-IN)** is the most promising self-hosted Hindi candidate.
  - **Build a ~12 h consented eval set in weeks 2–4.**
- **Speaker attribution.** Use calendar attendees, LLM-based naming and wearer heuristics. **No voiceprints in v1** (biometric law; track 10).
  - The best open diarizer is **NVIDIA Nemotron-3-Diarization**: up to 8 speakers, AMI-SDM DER 11.1, very fast. Its licence needs review. The fallback is pyannote community-1 (AMI 17.0).
  - "Consent mode" (keep only enrolled speakers) is feasible but leaky on far-field audio, and it conflicts with "what did the client say?". Offer it as a per-meeting **self-only** policy, not a global default.
- **Recommended path:**
  - **MVP:** Transcribe batch in both regions, behind an engine abstraction.
  - **Weeks 2–6:** bake-off.
  - **Month 4+:**
    - **US:** self-hosted Parakeet-TDT-0.6B-v2 + Nemotron-3-Diarization (or pyannote) on g6 (≈$0.2–1.5 per heavy user).
    - **India:** route English to self-hosted and Hindi/Hinglish to Transcribe hi-IN or Azure Central India, until an in-region Hindi model wins.
  - **Batch by default.** 60 s micro-batches give 1–3 min freshness. Streaming only for foreground "live" features: it is 1.7–2× the price.
- **Market lessons:**
  - Speaker attribution draws the most complaints (Limitless, Bee).
  - Battery claims mean standby. Plaud's 20 h is local recording.
  - The market is moving from "always listening" to explicit capture (Bee's button + LED).
  - Omi's open backend uses Silero VAD gating, Soniox and self-hosted Parakeet to cut STT cost.
  - Acquisitions (Limitless→Meta, Bee→Amazon) show why the ASR layer must be swappable.

---

## 1. Usage profile and assumptions

| Parameter | **Heavy user** (brief) | **Typical user** (our assumption) | Lifelog variant (out of v1 scope) |
|---|---|---|---|
| Device worn / app armed | 10 h/day | 8 h/day | 14+ h/day |
| Speech left after on-device VAD | 3–4 h/day (3.5 h midpoint) | ~1.5 h/day | 3–4 h/day |
| Days per month | 22 workdays | 22 workdays | 30 |
| **Speech hours per month sent to STT** | **77 h** (66–88) | **33 h** | **105 h** (90–120) |
| Raw armed hours per month (before VAD) | 220 h | 176 h | 420 h |
| Upload volume at Opus 16 kbps (≈7.2 MB per speech-hour) | ≈0.55 GB/month | ≈0.24 GB/month | ≈0.76 GB/month |

Notes:

- **Work-only scope cuts STT volume.** Internal Teams meetings come from Microsoft Graph post-meeting transcripts (track 02; unmetered since 25 Aug 2025, tenant admin must enable transcript API access since ~29 Jul 2026), so the phone pipeline mainly pays STT for **in-person conversations, hallway/whiteboard talk, and meetings run on other companies' platforms**. The heavy profile assumes the worst case: all 3.5 h/day go through our STT.
- "Typical user" (1.5 h/day) is an **estimate** (Low): it assumes a knowledge worker who spends about half of their talking time in Teams meetings that Graph already transcribes.
- Bitrate arithmetic: 16 kbit/s × 3,600 s ÷ 8 = 7.2 MB per hour; 24 kbit/s gives 10.8 MB/h; 12 kbit/s gives 5.4 MB/h.
- All costs are per seat per month in USD. India prices are converted at ≈ ₹88 = $1 (Low: an assumed rate; check it when you build the model).

## 2. iOS capture (iOS 26 / watchOS 26)

> Note: **iOS 27 shipped on 14 Sep 2026** (MacRumors). Everything below holds for iOS 26 and 27 unless noted; iOS 27 changes are called out.

### 2.1 Can a third-party app record for many hours in the background?

**Yes, as long as the recording is started while the app is in the foreground.**

- **Required setup:** `UIBackgroundModes` → `audio`, plus an `AVAudioSession` category of `.playAndRecord` (Apple-recommended) or `.record`. With these, recording continues when the user switches apps or locks the screen **(High)**. `.record` silences almost all other audio output, so use `.playAndRecord` with `.mixWithOthers` / `.allowBluetoothHFP` as needed.
- **No documented duration cap.** Just Press Record advertises "unlimited recording time" **(Med)**. What actually ends a session:
  - memory-pressure termination (jetsam),
  - crashes,
  - the user force-quitting the app,
  - an interruption the app fails to recover from (§2.2).
- **An app cannot start (or restart) recording from the background.**
  - Apple Frameworks Engineer (Dec 2024): *"You can't initiate recording in the background but assuming it was started this way … an app can record in the background."*
  - The rule dates from iOS 12.4, for "overriding privacy considerations". The error is `AVAudioSession.ErrorCode.cannotStartRecording` ('!rec', 561145187) **(High)**.
  - **This one rule shapes our whole iOS design (§2.8).**
- **Resuming after an interruption while in the background.** Since iOS 13.1, an app that was already recording can resume after a Siri or phone-call interruption ends **(Med: 2019 developer-forum reports)**. Restarting after an AirPods route change while in the background was reported to fail **(Low–Med: current behaviour unverified)**.
- **New lifecycle notifications in iOS 27:**
  - `didBecomeActiveNotification`
  - `didBecomeInactiveNotification`, with a `DeactivationContext` that tells you whether the app or the system deactivated the session
  - `resumptionRecommendationNotification` (`.shouldResume` / `.shouldNotResume`), which is not tied to the interrupting app's end signal, so apps don't get stuck "interrupted"
  
  The legacy `interruptionNotification` is deprecated after the 26 releases **(High)**. Build the session manager against both APIs.

### 2.2 Interruptions, concurrency and audio routes

| Event | What happens to our recording | Mitigation |
|---|---|---|
| **Incoming cellular / FaceTime call** | The ring alert can interrupt us. With `setPrefersNoInterruptionsFromSystemAlerts(true)` (iOS 14.5+) and banner-style call display, we're interrupted only if the user **accepts** the call. Full-screen call display still interrupts **(High)**. | Set the flag. On interruption, close the current chunk and mark a gap. Resume when told `.shouldResume`. |
| **Teams / Zoom / WhatsApp VoIP call on the same iPhone** | **We lose the mic**: "generally no, 2 apps cannot access the microphone at the same time" (Apple engineer, Dec 2024) **(High)** | Expected and acceptable: Teams audio comes from Graph transcripts (track 02). Detect the gap and label it "in a call". |
| Siri, alarms, other non-mixable sessions | Interruption, then resume (see §2.1) | Same handling as a phone call |
| **AirPods / Bluetooth connect or disconnect** | Since iOS 17, a route disconnect interrupts only "Now Playing" sessions. `setPrefersInterruptionOnRouteDisconnect` controls this **(High)**. Bluetooth HFP mics are 16 kHz narrow-ish and lower ASR accuracy (Granola says so in its docs). | Prefer the built-in mic. Log the route per chunk. |
| **iOS 26 `bluetoothHighQualityRecording`** | Full-bandwidth AirPods recording. Falls back to HFP. **Not available in the EU.** May add latency **(High)**. | Worth enabling for US/India users who wear AirPods |
| iOS 26 `AVInputPickerInteraction` | In-app mic picker with level meter and mic modes. An AirPods stem press can start/stop recording **(High/Med)**. | A nice UX touch, not required |

### 2.3 Indicators, Live Activities and quick-capture entry points

- **Indicator:** while any app uses the mic, iOS shows an **orange dot** in the status bar **(High)**. We found no API to suppress it, and we wouldn't want one: App Review 2.5.14 requires a visible indication (§2.6).
- **Live Activity / Dynamic Island** for the "recording" state is now standard: Otter has Lock Screen pause/resume/stop, Granola shows "taking notes" plus a timer.
- **ActivityKit limits (High):**
  - A Live Activity runs up to **8 h**, then the system ends it. It can stay on the Lock Screen for up to 4 more hours (**12 h maximum**).
  - 4 KB data limit.
  - The user can disable Live Activities per app.
  - It is normally started in the foreground. A `LiveActivityIntent` (for example from a Control) can start one from the background.
- **`AudioRecordingIntent` (iOS 18+)** is the official way to start recording from Control Center, the Lock Screen, the Action button or Siri. The rule (High): *"you must start a Live Activity when you begin the audio recording and keep it active as long as you record audio. If you don't start a Live Activity, the audio recording stops."*
  - **For a 10-hour work session this matters.** Whether the 8-hour Live Activity expiry also stops an intent-started recording is **unverified**.
  - **Design rule:** start the long work session from the app UI (foreground tap). Use `AudioRecordingIntent` only for short "quick capture" notes. Refresh or replace the Live Activity before 8 h.
- A Feb 2026 forum report says triggering `AudioRecordingIntent` from a Shortcut or the Action button while the app isn't active failed with "Target is not foreground" **(Med)**. **Prototype this in week 1.**

### 2.4 Apple Watch

- watchOS documents the `audio` background mode for **playback**. Long-form audio needs a Bluetooth route.
- Extended runtime sessions are short (self-care 10 min, mindfulness 1 h, physical therapy 1 h, smart alarm 30 min), must start while the app is active, and get cancelled under high CPU **(High)**.
- Just Press Record and Bee offer Watch capture, but for **user-initiated** notes **(Med)**.
- SpeechAnalyzer is **not** available on watchOS **(High)**.
- **Conclusion:** the Watch is a remote control and a quick-note mic. It is not an all-day work-session recorder. Don't plan v1 around it.

### 2.5 Battery

- We found no first-party %/hour measurement.
- **Estimate (Low):** screen-off mic capture, VAD and Opus/AAC encoding cost on the order of 1–3 %/hour on a recent iPhone (≈13–15 Wh battery). That is roughly 10–25 % over a 10-hour day, mostly from keeping the audio stack and CPU awake. Batched uploads add little.
- **Continuous on-device ASR costs materially more** (§4.4).
- **Action:** measure with MetricKit (`MXCPUMetric`, `MXCellularConditionMetric`) and Xcode energy reports on iPhone 13/15/16 before promising a number to customers.

### 2.6 App Store Review Guidelines (current page)

- **2.5.14:** *"Apps must request explicit user consent and provide a clear visual and/or audible indication when recording, logging, or otherwise making a record of user activity. This includes any use of the device camera, microphone…"* **(High)**
- **2.5.4:** background services may be used only "for their intended purposes: VoIP, audio playback, location, task completion, local notifications, etc." Recording audio is an intended purpose of the `audio` mode. **Playing silent audio to stay alive is a classic rejection reason (Med).**
- **5.1.1 / 5.1.2:**
  - The purpose string (`NSMicrophoneUsageDescription`) must describe the use clearly and completely.
  - The privacy policy must cover retention, deletion and how to revoke consent.
  - Data minimization applies.
  - No repurposing without consent **(High)**.
- **Practical guidance:**
  - Show an in-app recording state plus a Live Activity.
  - Send an onboarding consent screen that names the tenant's policy.
  - Give reviewers a demo tenant.
  - Explain the work-only governance in the review notes.
  - Enterprise distribution via Apple Business Manager custom apps is an option for large customers.

### 2.7 Phone calls on iPhone

- **Third-party apps cannot access cellular call audio.** Apple engineer (2020): *"I also don't know of a way to 'read' the audio from the call, I am pretty sure that's not possible."* The only related API injects synthesized speech *into* a call (`AVSpeechSynthesizer.mixToTelephonyUplink`). CallKit exposes no audio **(High in practice)**.
- **Native call recording (iOS 18.1+):** recording started in the Phone app **notifies all participants automatically** and produces a transcript/summary in Notes **(High)**. We found **no API** that exposes these recordings or transcripts **(Med: absence of evidence)**. The only route is the user manually sharing or exporting the audio or transcript into our app (Share Extension). That is worth building as a low-cost feature.
- The iOS 27 feature-availability page lists Call Screening for English (US) and English (India). It is not an API.

### 2.8 Implications for a work-only, admin-governed recorder on iOS

1. **The mic cannot be auto-started at 09:00, on arriving at the office, or when a calendar meeting begins** if the app isn't already recording. Everything that starts capture needs **one user tap**:
   - a local notification ("Client meeting in 2 min: tap to capture"),
   - a Live Activity button,
   - a Control or Action button,
   - opening the app.
2. **Auto-pause is easy** with:
   - region monitoring (`CLMonitor`, up to 20 conditions, relaunches the app in the background),
   - Focus filters (`SetFocusFilterIntent`),
   - calendar/end-of-day timers,
   - interruption events.
3. **Auto-resume after a pause has two options:**
   - **(a) "Soft pause":** keep the audio session running and discard samples. Auto-resume works, but **the orange dot stays on**, the user may believe they are being recorded, and it costs battery.
   - **(b) "Hard stop":** stop the session, then resume with one tap (notification or Live Activity).
   - **Recommendation:** use (b) for privacy-sensitive pauses (outside hours, leaving the office, private calendar events). Allow (a) only for short gaps of a few minutes, such as a phone-call interruption or between back-to-back meetings, and say clearly in the UI that "the mic is on, nothing is saved".
4. **Teams calls on the phone** take the mic away from us. This is fine, because Graph covers them.
5. **Apple Watch** is a quick-capture accessory only.

## 3. Android capture (Android 14 / 15 / 16)

> Android 17 (API 37) reportedly reached Pixels in June 2026 **(Med: press reports)**. Its background-audio hardening targets *playback*, audio focus and volume, not capture **(High)**.

### 3.1 The microphone foreground service (FGS)

- **Setup:**
  - Manifest: `android:foregroundServiceType="microphone"`
  - Permissions: `FOREGROUND_SERVICE_MICROPHONE` (normal) and `RECORD_AUDIO` (runtime)
  - Call `startForeground(..., FOREGROUND_SERVICE_TYPE_MICROPHONE)` **(High)**
- **Starting it requires a visible app ("while-in-use" rule).** Microphone is a while-in-use permission.
  - On Android 14+ targets, creating a microphone FGS while the app is in the background throws `SecurityException`.
  - `checkSelfPermission()` still returns GRANTED, so it won't tell you **(High)**.
- **Allowed exemptions** **(High)**:
  - started by a system component
  - user interaction with **our notification** or **widget**
  - a PendingIntent from a *visible* other app
  - device-owner DPC
  - the default assistant
  - privileged `START_ACTIVITIES_FROM_BACKGROUND`
- **Not exemptions** for mic capture **(High)**:
  - geofence or activity-recognition events
  - exact alarms
  - high-priority FCM pushes
  - `BOOT_COMPLETED`
  - battery-optimization exemption
  - Companion Device Manager
- **Implication: as on iOS, nothing can cold-start the mic at 09:00, at the office, or at meeting start.** A *notification tap* is a legal trigger, so "Meeting starting: tap to capture" works.
- **No runtime cap for type `microphone`.** Android 15 added 6 h/24 h caps only for `dataSync` and `mediaProcessing`, and ~3 min for `shortService`. **A 10-hour microphone FGS is allowed by the platform (High)**. OEM killers are the practical risk (§3.3).
- **Soft pause / auto-resume.** Keep one microphone FGS alive (started from the foreground) and stop/start `AudioRecord` inside it. An FGS started while visible keeps while-in-use access, so this should work **(Med: inferred from docs; test on Samsung/Xiaomi/Vivo/Oppo)**. While paused this way, Android's mic indicator turns off because `AudioRecord` is stopped. **That is a privacy advantage over iOS** (§2.8).
- **Android 16 / 17:**
  - Jobs that run while an FGS is running now count toward job runtime quotas. Keep VAD and encoding inside the FGS, not in WorkManager **(High)**.
  - Android 17 adds RAM-based app memory limits, so large on-device ASR models are at risk ("MemoryLimiter:AnonSwap") **(High fact / Med impact)**.

### 3.2 Notification, indicators and user control

- **Persistent FGS notification:** mandatory. If `POST_NOTIFICATIONS` is denied, the FGS still runs but appears only in the FGS Task Manager **(High)**.
- **Dismissal (Android 14+):** users can dismiss the notification and the service keeps running **(High/Med)**.
- **Task Manager stop (Android 13+):** kills the app with no callback. Detect it later via `ApplicationExitInfo.REASON_USER_REQUESTED` and show a "capture stopped" gap **(High)**.
- **Mic indicator (Android 12+):** a status-bar icon appears whenever an app uses the mic **(High)**.
- **Global mic toggle:** the app receives **silent audio**. Detect all-zero PCM and tell the user **(High)**.

### 3.3 Doze, battery policy and OEM killers (critical for India)

- **Doze and standby:** an app with a running FGS is not "idle" for App Standby **(High)**.
  - Whether a mic FGS keeps network access during Doze is unverified.
  - Design for local buffering plus opportunistic upload (§8.5).
- **Battery-optimization exemption.** Google Play prohibits asking for a direct exemption (`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`) unless core function is impaired, and there is no "recorder" category **(High)**. Deep-link users to the settings screen instead.
- **Play vitals: excessive wake locks** is a core vital since 2025-11-10, enforced from 2026-03-01 **(High)**.
  - A session is excessive at ≥2 h of non-exempt partial wake locks per 24 h; the bad-behaviour threshold is >5 % of sessions over 28 days.
  - Penalty: hidden from discovery surfaces, plus a battery warning.
  - Mic capture is not explicitly exempt.
  - **Don't hold app wake locks.** The audio pipeline inside the FGS keeps the CPU running.
- **OEM killers.** dontkillmyapp ranks Huawei #1, Xiaomi #2, OnePlus #3, Samsung #4, Oppo #8, Vivo #11 and realme #12, which together are most of the Indian market.
  - Required manual settings:
    - Xiaomi/Redmi/POCO: Autostart, Battery saver set to "No restrictions", lock in recents.
    - Oppo ColorOS: kills services when the screen goes off unless "Run in background" and Auto start-up are on.
    - Vivo: Autostart plus high background power consumption.
    - realme: allow background activity and auto-launch.
    - OnePlus: settings reportedly revert at random.
    - Samsung: "Never sleeping apps" and Unrestricted battery. Samsung said FGS of apps targeting Android 14 are guaranteed from One UI 6.0 **(Med)**.
  - dontkillmyapp often says "no known solution on dev end" **(High)**.
  - **Build into v1:**
    - a per-OEM onboarding wizard
    - a server-side heartbeat (expect N chunks per hour while armed)
    - gap detection with a push notification "capture stopped: tap to resume"
    - a supported-device list for enterprise pilots

### 3.4 Calls, VoIP and concurrent capture

- **During a cellular or VoIP call (Teams, WhatsApp) "the call always receives audio".** Other apps get silence unless they are an accessibility service or a privileged app holding `CAPTURE_AUDIO_OUTPUT` **(High)**. Our app records silence during calls on the same phone; detect it with `AudioRecordingCallback` / `isClientSilenced()` **(High)**.
- **No third-party access to call audio.** `VOICE_CALL` capture requires the privileged `CAPTURE_AUDIO_OUTPUT` **(High)**.
- **Native call recording** in the Google Phone app (where available), Samsung Phone and others announces itself to participants and stores recordings on the device. There is no third-party API **(High/Med)**. Offer a share-sheet import instead.
- **Use `VOICE_RECOGNITION` or `MIC` as the audio source**, never `VOICE_COMMUNICATION`, which would starve other apps **(Med)**.

### 3.5 Google Play policy

- **Accessibility API** can't be used for remote call-audio recording. As of 2026 it also prohibits any use that lets an app "autonomously initiate, plan, and execute actions" **(High)**. That matters for Pillar 1 agent features on Android too.
- **FGS declaration** in Play Console: per type, a description, user impact, a **video** of how the user starts it, and a use case. Microphone use cases include "voice recording" **(High)**. A policy preview effective 2027-01-27 exists; details unverified.
- **Spyware / stalkerware rules.** "Recording audio … not tied to compliant functionality" is spyware. Enterprise monitoring apps need:
  - a persistent notification
  - a unique icon
  - the `IsMonitoringTool` manifest flag
  - store-listing disclosure
  - **Risk:** if tenant admins can browse employees' recordings, Play may class us as a *monitoring tool* **(Med)**.
  - **Design consequence:** admins set *policy*; recordings and transcripts are **private to the user** by default (sharing is user-initiated). This also helps under privacy law.
- **User Data policy:** in-app *prominent disclosure* plus affirmative consent for background audio collection. The Data safety form must match **(High)**.

### 3.6 On-device speech on Android, and reference apps

- **`SpeechRecognizer` is not for long-form background capture.** Per its own docs it may stream to servers and is "not intended to be used for continuous recognition" **(High)**. `createOnDeviceSpeechRecognizer` exists but throws `UnsupportedOperationException` when unavailable.
- **ML Kit GenAI Speech Recognition** (alpha, page updated 2026-09-28) **(High)**:
  - *Basic* mode: classic on-device model, API 31+, en-US plus 14 beta locales **incl. hi-IN**.
  - *Advanced* mode: Gemini Nano class, **Pixel 10/11 only**.
  - **en-IN is not listed in either mode.**
  - ML Kit GenAI/AICore inference is generally "permitted only when the app is the top foreground application" **(High)**, so it's not a background engine.
- **Pixel Recorder:**
  - Transcription in ~40 languages incl. **English (India) and Hindi**; "re-transcribe may process audio files on Google servers".
  - Summaries in English, Hindi and five other languages for 5 min–1 h recordings (Pixel 8+).
  - **Speaker labels only for US English**, computed on device, and Google says the voice models "may be considered biometric data" **(High)**.
- **Samsung Galaxy AI Transcript Assist:** 22 languages incl. **Hindi**; works on Voice Recorder, call recordings and Notes; files under 3 h; on-device or cloud processing selectable **(High)**.
- **Conclusion:** there is no platform ASR on Android suitable for 10 h of background transcription. Use our own on-device models (sherpa-onnx/ONNX Runtime) only for foreground "live" moments, and send the bulk to the cloud.

### 3.7 Managed devices (Intune / Android Enterprise)

- **Intune app configuration policies** can push tenant ID, capture policy, allowed hours and retention to Managed Google Play apps. Supported variables include UPN and Entra device ID **(High)**. Use these for zero-touch tenant binding.
- **Admins cannot pre-grant the microphone:** no Record-audio auto-grant on work-profile devices since Android 12, and only opt-in grants on fully managed devices. **Admins *can* deny it**, which is a usable kill switch **(High)**.
- **Policy implications:**
  - The user must still consent on-device, which helps us under App/Play policy and the law.
  - Admins can enforce "off".
  - The device-owner FGS exemption applies only to the DPC itself, not to our app **(Med)**.

## 4. On-device processing: VAD, on-device ASR, battery and the hybrid design

### 4.1 Voice-activity detection (runs on every device, always)

| VAD | Size / speed | Licence | Notes |
|---|---|---|---|
| **Silero VAD** (v6.2.3, 23 Sep 2026) | ~2 MB (JIT). A 30+ ms chunk takes **<1 ms on one CPU thread**. 8/16 kHz input. ONNX available **(High)** | MIT, no telemetry/keys | Trained on 6,000+ languages. v6 claims 16 % fewer errors on noisy real-life audio. The de-facto default. Omi's production gate settings: 512-sample (32 ms) windows, threshold 0.65, 300 ms pre-roll, 4 s hangover **(High)** |
| **TEN VAD** (Agora/TEN, ONNX since Jun 2025) | 306–731 KB library. RTF 0.005 on an iPhone 8 (A11), 0.057 on a Galaxy J6+ **(High: vendor)** | "Apache 2.0 **with conditions**" → **legal review needed** | Vendor benchmarks claim better precision/recall than Silero and faster speech→silence transitions (Silero lags by "several hundred ms") |
| WebRTC VAD (GMM) | Tiny | BSD | Older, noisier decisions. Use only as a fallback |

**Recommended settings (start here, then tune on our eval set; Med):**

- 16 kHz mono, 32 ms frames, Silero threshold 0.5–0.65
- 300 ms pre-roll and 1–2 s hangover for *segmentation*; minimum speech 250 ms
- Merge gaps under ~1 s; force-split segments longer than 60–120 s at the lowest-energy point

The brief's assumption is "10 h armed → 3–4 h of speech". **No public source for daily speech ratio was found. Measure it in the pilot.**

### 4.2 On-device ASR options

| Engine | Platforms | Languages relevant to us | Speed / accuracy | Caveats |
|---|---|---|---|---|
| **Apple SpeechAnalyzer + SpeechTranscriber** (iOS/macOS 26+) | iPhone, iPad, Mac (not Watch) | **en-US ✔**. **en-IN likely ✔**: English (India) is listed for Notes audio transcription and on-device Dictation, both built on it **(Med)**. **hi-IN ✘ on-device** **(Med–High)** | Designed for long-form and distant speakers. Models are system assets that run outside the app's memory. Argmax measured **14.0 % WER on Earnings22 at ~70× real time** vs Parakeet-v2 11.7 % at 359× **(High)**. MacStories: a 34-min file in 45 s | No custom vocabulary at launch; `contextualStrings` exists but its effect is unverified. Concurrent-analysis limits apply (`insufficientResources`). **Whether it runs while the app is backgrounded is unverified.** |
| **FluidAudio** (Apache-2.0; v0.17.5, 1 Oct 2026) | iOS 17+ / macOS (Neural Engine) | Parakeet v2 (EN), v3 (25 European languages + Japanese) | ~155–190× real time on M4 Pro. Also has VAD and on-device diarization (LS-EEND ≤10 speakers, Sortformer, pyannote 3.1). **On iPhone 16 Pro Max:** 3.4 s encoder compile on first load, then 162 ms. ANE models are ~95–200 MB **(High: vendor benchmarks)** | Phones are slower than an M4 Pro. The int8 encoder fails on A16 (iPhone 14 Pro). No Hindi |
| **WhisperKit / Argmax** (repo now `argmax-oss-swift`, v1.1.0, Aug 2026; MIT; Pro SDK commercial) | iOS/macOS; **Pro SDK adds Android** | Whisper (99 languages incl. Hindi); large-v3-turbo compressed is 626 MB; SpeakerKit = pyannote v4 | Pro SDK: real-time transcription with speakers, custom vocabulary | Whisper hallucination risk on silence, so gate with VAD. Large models plus background memory limits risk jetsam |
| **Moonshine** (MIT) | iOS/Android/edge | **English only** | Medium-streaming (245M): 6.65 % WER. Small (123M): 7.84 %. Tiny (34M): 12.0 %. **~0.4 s latency on a Pixel 10a** **(High)** | Good for live English captions on Android; no Hindi |
| **Kyutai STT** | Server; MLX builds for iPhone | en/fr (1B, 0.5 s delay); en (2.6B, 2.5 s delay) | Semantic VAD built in | No Hindi |
| **sherpa-onnx** (v1.13.8, Sep 2026) | **Android, iOS, WearOS** | Whatever model is loaded (incl. Whisper, Paraformer, Zipformer) | ASR + VAD + speaker ID toolkit **(High)** | The practical Android runtime for any on-device features |
| Android: `SpeechRecognizer` / ML Kit GenAI | Android | ML Kit Basic: en-US + hi-IN (beta). **No en-IN** | — | Not for continuous or background use (§3.6) |
| Android: own models via ONNX Runtime / sherpa-onnx / whisper.cpp | Android | Whatever we ship | Device-dependent | Fragmentation, thermal throttling, Android 17 memory limits |

### 4.3 Background-execution limits that decide the architecture

- **iOS: Metal GPU work is blocked in the background.** Command buffers fail with `notPermitted` **(High)**.
- **iOS 26 `BGContinuedProcessingTask`:**
  - must start from a user action in the foreground
  - shows progress, and the user can cancel it
  - background GPU needs a special entitlement
  - the system may kill it **(High)**
  
  It suits a "transcribe this file now" job, not continuous ASR. Neural Engine use from a backgrounded recording app is unverified.
- **Android:** AICore/Gemini Nano inference is foreground-only **(High)**, and Android 17 adds memory limits.

**Conclusion (High-confidence direction, Med on details): plan for on-device VAD + compression, and leave transcription to the server.** Treat on-device ASR as a *foreground* feature or a *while-charging* catch-up, not as the main pipeline.

### 4.4 Battery and thermal (estimates; measure before promising)

- **Capture + VAD + Opus encode, screen off:**
  - Estimated ~1–3 %/h on a recent iPhone (13–15 Wh battery), mostly keeping the audio stack and CPU awake. That is ~10–25 % across a 10 h day **(Low)**.
  - Silero/TEN VAD costs are negligible: <1 ms per 30 ms frame.
- **Uploads:**
  - 16 kbps Opus is ~7.2 MB per speech-hour. Energy is dominated by cellular radio "tail" time, not bytes.
  - Batch uploads every 2–5 min on cellular and immediately on Wi-Fi. Avoid per-30-second uploads on LTE/5G **(Med: general mobile-radio behaviour)**.
- **On-device ASR as a burst job:**
  - Neural Engine speeds of 70–190× (Mac-class figures) mean a 3.5 h day is a few minutes of accelerator time.
  - Energy for that burst is likely **<1–2 % of battery** if run while charging **(Low: back-of-envelope)**.
  - The blockers are not energy. They are background-execution rules, memory or jetsam, accuracy (no hi-IN on-device on iOS) and model download size (≈0.2–0.6 GB).
- **Continuous streaming ASR all day** keeps models resident and the CPU awake. Expect noticeably higher drain and heat. Avoid it.
- **Plan:** measure with MetricKit / Xcode Energy Organizer (iOS) and Battery Historian / Play vitals (Android) on iPhone 13/15/16, Galaxy A-series, Redmi Note and Vivo/Oppo mid-range devices.

### 4.5 Hybrid strategy (recommended)

1. **Always on device:**
   - capture → Silero VAD → segment → Opus 16 kbps → AES-GCM encryption → durable local queue
   - upload in-region (us-east-1 / ap-south-1)
2. **Server:**
   - assemble each session (calendar-bounded)
   - batch ASR + diarization (vendor in the MVP, self-hosted at scale)
   - redaction (track 10)
   - memory (track 05)
3. **On-device ASR only for:**
   - (a) **foreground "live" moments**: a quick voice note, live captions while the app is open, "what did they just say?". Use Apple SpeechTranscriber for en-US/en-IN, and FluidAudio/Parakeet for English.
   - (b) a future **"audio never leaves the device"** tenant option: transcribe while charging and upload transcripts only. It needs on-device diarization and gives lower accuracy and no Hindi on iOS, so it's a v2+ feature.
4. **No continuous on-device streaming ASR in v1.**

## 5. Cloud speech-to-text compared (US + India focus)

### 5.1 Price and feature table (list prices, USD per audio hour, checked 5–6 Oct 2026)

**Big change since 2025 (High).** Amazon Transcribe standard pricing is now flat **$0.006/min batch ($0.36/h)** and **$0.010/min streaming ($0.60/h)**, billed per second with no tiers. It is the same in us-east-1 and ap-south-1, per AWS's public price-list file published 2026-09-11 and the pricing page. Older blog posts still quote $0.024/min. We could not find the announcement date.

| Vendor / model | Batch $/h | Streaming $/h | Diarization | PII redaction | US-EN / en-IN / hi-IN / Hinglish | Data use & retention | Processes in India? |
|---|---|---|---|---|---|---|---|
| **Amazon Transcribe** | **0.36** | **0.60** | Speaker partitioning; no separate fee seen **(Med)** | Add-on **+$0.144/h** (≤250k min/mo), falling to $0.09 → $0.061 → $0.047/h at volume. **en-US and en-IN only; no hi-IN** **(High)**. Batch PII available in Mumbai; streaming PII not in Mumbai **(High)** | ✔ / ✔ (batch + streaming; custom vocabulary) / ✔ (batch + streaming; custom language model in batch) / ✘ no intra-sentence code-switching; batch multi-language ID can't be combined with redaction **(High)** | May store content to improve the service unless the org applies the AWS AI-services **opt-out policy** **(High)** | **Yes: ap-south-1 Mumbai (batch + streaming). Not ap-south-2.** |
| **Azure AI Speech** | **0.18** batch; 0.36 fast transcription (promo meter $0.10 from 2026-09-01) | 1.00 | Batch: yes. Real-time diarization is a paid add-on (price hidden) | Not verified | ✔ / ✔ / ✔. MAI-Transcribe-1.5/2 models in "LLM speech" regions incl. **centralindia** / ✘ (multilingual refinement excludes hi-IN) | *"doesn't store or process your data outside the region of your Azure Speech resource"* **(High)** | **Yes: Central India** has real-time, fast and batch transcription plus MAI-Transcribe **(High)** |
| **Deepgram Nova-3** (mono / multi) | 0.258 / 0.312 PAYG (0.216 / 0.258 Growth) | 0.288 / 0.348 (promo) | Included in batch; +$0.12/h streaming | +$0.12/h. Entity redaction **English-only** | ✔ / ✔ (mono) / ✔ / **✔ `multi` code-switching incl. Hindi–English** | Model Improvement Program **on by default**; opt out per request (`mip_opt_out`) | Not verified (US; EU endpoint exists) |
| Deepgram **Flux** (streaming conversational) | — | 0.39 / 0.468 (promo) | +$0.12/h | Numbers only | Flux Multilingual incl. Hindi | same | same |
| **AssemblyAI Universal-3.5 Pro** (async, Jul 2026) / U3.5 Pro Realtime | **0.21** | 0.45 | +$0.02/h | Text +$0.08/h; **audio** redaction +$0.05/h. Language coverage not verified | ✔ / (no en-IN locale) / ✔ / "native code-switching" claimed, Hindi–English not benchmarked | Trains by default; **free opt-out on paid plans**; EU data never used for training; async deletion 24–48 h | US/EU. India: not verified |
| AssemblyAI Universal-2 / Universal-Streaming | 0.15 | 0.15 (no Hindi in streaming) | +$0.02/h | as above | Hindi in the 10–25 % WER tier (vendor) | same | same |
| **OpenAI** gpt-4o-mini-transcribe / **gpt-transcribe** (≈Jul 2026) / gpt-4o-transcribe-diarize | 0.18 / **0.27** / 0.36 | 1.02 (gpt-live-transcribe) | Only via the diarize model (up to 4 known-speaker reference clips) | None | ✔ / hints / ✔ / unverified | **Not used for training by default**; audio endpoint is zero-data-retention (ZDR) eligible | India data residency listed by OpenAI; **not verified for audio endpoints** |
| **Google Chirp 3** (STT V2) | ≈0.96 **(Low)** | not verified | Batch only | None built in | ✔ / ✔ / ✔ / "auto" picks the dominant language (no real code-switching) | not verified | **No**: Chirp 3 is in `us`/`eu` multi-regions only |
| **Speechmatics** Melia 1 / Standard / Enhanced | **0.12** / 0.23 / 0.38 | not listed | **Included** | not verified | ✔ / ? / ✔ / no Hindi–English bilingual pack | No data logging for training by default | Multi-region SaaS; on-prem available for enterprise |
| **Soniox** v5 | **≈0.10** | ≈0.12 | Included | not verified | ✔ / ? / ✔ (60+ languages) / code-switching claimed but not verified | not verified | not verified |
| **ElevenLabs Scribe v2** / v2 Realtime | 0.22 | 0.39 | Included (≤32 speakers) | Entity *detection* only (+$0.07/h) | ✔ / ? / ✔ (5–10 % WER tier, vendor) / ? | not verified | not verified |
| **Mistral Voxtral Mini Transcribe 2** | 0.18 | 0.36 | Supported | None | ✔ / ? / ✔ (13 languages) / ? | not verified | Older Voxtral Mini 3B / Small 24B (2507) are on **Amazon Bedrock in ap-south-1**, but as chat-style audio models, not the Transcribe 2 API; Mini 3B is "Legacy", EOL 2027-03-30 |
| Gladia Solaria | 0.61 starter → "as low as" 0.20 | 0.75 → 0.25 | Included | not verified | 100+ languages, auto-switching; Hindi not verified | Training opt-out automatic on Growth tier | not verified |
| Rev.ai Reverb | 0.20 (EN), 0.30 (other) | not verified | not verified | not verified | — | — | US |
| **Sarvam AI** saaras:v4 | **₹30/h ≈ $0.34**; **₹45/h with diarization** (batch only) | ₹30/h | Batch only (+₹15/h) | not verified | ✔ / ✔ / ✔ (22 Indian languages + en-IN) / **✔ `codemix` mode** (English words in Latin script, Hindi in Devanagari) | Privacy policy: content may be **processed outside India (US clouds)**; inputs/outputs kept 30 days after last access by default; **used for training unless you opt out** **(Med: policy may target consumer apps; negotiate an enterprise DPA)** | **Not guaranteed**: needs a contract for India-only processing |
| Gnani.ai (Prisma v2.5) | not public | not public | ? | ? | 10+ Indian languages | ? | ? |
| Reverie | not verified (pricing page 404) | | | | | | |
| **AI4Bharat IndicConformer-600M** (open, MIT) | self-host | self-host | — | — | 22 Indian languages; **no English, no code-mixed** | yours | yours (ap-south-1) |

**What the table means for us**

- **India residency.** For India tenants, only four STT paths keep audio in India *by design*:
  - Amazon Transcribe ap-south-1
  - Azure Speech Central India (a Microsoft subprocessor, which M365 customers usually accept easily)
  - self-hosted models on ap-south-1 GPUs
  - a vendor under a negotiated India-processing contract
  
  Sarvam, Deepgram, AssemblyAI, ElevenLabs, Speechmatics SaaS, Soniox and Google Chirp 3 all **send audio abroad** unless contractually arranged otherwise.
- **PII redaction for India.** Only Transcribe (en-IN) offers built-in transcript redaction for Indian English, and it has **no Aadhaar or PAN entity types and no hi-IN support** (track 10). Plan our own redaction pass on every transcript regardless of engine. Treat vendor redaction as a first pass only.
- **Hinglish.** Engines that claim real intra-sentence Hindi–English code-switching: **Deepgram Nova-3 `multi`, Sarvam `codemix`, AssemblyAI U3.5 Pro**, and possibly Soniox, ElevenLabs and Speechmatics Melia (unverified). **Transcribe and Azure do not.** They transcribe the dominant language and may transliterate English words into Devanagari (or the reverse). For an Indian workplace this is the single biggest accuracy risk, and we found **no independent Hinglish benchmark**.

### 5.2 Accuracy evidence (read with care)

- **English, independent.** Artificial Analysis AA-WER is a blend of agent-style talk, VoxPopuli and Earnings22, about 8 h, English-heavy and with no Indian English. Extracted values **(Med)**:
  - MAI-Transcribe-2 (Azure): 2.0 %
  - ElevenLabs Scribe v2: 2.2 %
  - MAI-Transcribe-1.5: 2.4 %
  - AssemblyAI Universal-3 Pro: 3.1 %
  - OpenAI gpt-transcribe: 3.3 %
  - Soniox v5: 3.8 %
  - Amazon Transcribe: 4.1 %
  - Whisper large-v3: 4.1 %
  - Google Chirp 3: 4.3 %
  - gpt-4o-mini-transcribe: 4.5 %
  - Speechmatics Melia: 4.9 %
  - Deepgram Nova-3: 5.2 %
  - Rev AI: 5.9 %
  
  Treat differences of less than ~1 point as noise for our audio.
- **Open models (HF Open ASR Leaderboard figures on model cards, High).**

  | Model | Avg WER | AMI (meetings) | Earnings22 |
  |---|---|---|---|
  | Parakeet-TDT-0.6B-v2 | 6.05 % | 11.16 % | 11.15 % |
  | Parakeet-TDT-0.6B-v3 | 6.34 % | — | — |
  | Canary-Qwen-2.5B | 5.63 % | 10.18 % | 10.42 % |
  | Whisper large-v3-turbo | 7.83 % | — | — |

  Parakeet v2 under noise: 6.05 % clean → 6.95 % at 10 dB SNR → 8.23 % at 5 dB → 11.88 % at 0 dB.
- **On-device, Apple.** Argmax (Jun 2025), on Earnings22 (WER and speed):

  | Model | WER | Speed |
  |---|---|---|
  | Apple SpeechTranscriber | 14.0 % | 70× real time |
  | whisper-small.en | 12.8 % | — |
  | Parakeet-v2 (Argmax Pro) | 11.7 % | 359× |
- **Hindi.** Most published numbers are vendor-run or dated:
  - **Vistaar (AI4Bharat, 2023):** IndicWhisper averaged 13.6 % Hindi WER vs Azure 20.0 % and Google 23.9 %. On noisy telephony (Gramvaani) it scored 26.8 % vs Google 59.9 %.
  - **IndicConformer-600M:** 13.2 % on Vaani.
  - **Vendor tiers:** ElevenLabs puts Hindi at 5–10 %; AssemblyAI Universal-2 at 10–25 %.
- **Indian English and Hinglish.** We found **no independent 2026 benchmark**. Engines with an explicit en-IN option: Transcribe, Deepgram (mono), Google, Azure, Sarvam.
- **Far-field / in-pocket audio** (our real condition) is not covered by any of these benchmarks. AMI and Earnings22 are the closest proxies, and WER there is roughly 2× clean-speech WER.

**Evaluation plan (do this in weeks 2–4; Low cost, High value).** Build a consented internal eval set of **~12 h**:

- 3 h US English meetings (phone on table / in pocket / wearable)
- 3 h Indian English
- 3 h Hinglish
- 1.5 h Hindi
- 1.5 h noisy hallway/cafeteria

Score each engine on:

- WER / CER (for Hindi, measure CER after script normalization)
- **entity error rate** (names, numbers, dates, product terms)
- code-switch MER
- DER (diarization error)
- latency
- $/h

Engines to run:

- **Managed:** Transcribe (en-US / en-IN / hi-IN), Azure (standard + MAI-Transcribe; eastus / centralindia), AssemblyAI U3.5 Pro, Deepgram Nova-3 `multi`, ElevenLabs Scribe v2, Soniox, Speechmatics, Sarvam `codemix`
- **Self-hosted:** Parakeet v2, Whisper-turbo, IndicConformer, Nemotron 3.5 ASR (hi-IN)

Use **internal, consented** recordings, so residency rules don't block evaluating foreign vendors.

Pick engines per region with data, not with leaderboards.

## 6. Self-hosted STT on AWS (us-east-1 and ap-south-1)

### 6.1 Candidate open models

| Model | Languages | Licence | Avg WER (Open ASR LB) | RTFx (LB, A100-class, batched) | Long-form | Fit for us |
|---|---|---|---|---|---|---|
| **NVIDIA Parakeet-TDT-0.6B-v2** | English | CC-BY-4.0 | **6.05 %** (AMI 11.16, Earnings22 11.15) | **3,386** | Up to 24 min per pass (full attention). Word/segment timestamps. Robust to 8 kHz μ-law (6.32 %) | **US English default.** Indian-English accuracy unknown: test it. |
| NVIDIA Parakeet-TDT-0.6B-v3 (Aug 2025) | 25 European languages, **no Hindi** | CC-BY-4.0 | 6.34 % | 3,333 | 24 min full attention / **3 h local attention**. Auto language ID. | EU expansion later |
| NVIDIA Canary-Qwen-2.5B | English | CC-BY-4.0 | **5.63 %** (AMI 10.18) | 418 | Trained on ≤40 s segments. No timestamps mentioned. | Accuracy upgrade path; 8× slower; no timestamps |
| OpenAI Whisper large-v3-turbo | 99 languages incl. Hindi | MIT | 7.83 % | 200 | 30 s chunked decoding. Can hallucinate on silence/noise (needs VAD) | **Hindi/Hinglish fallback** and fine-tuning base |
| AI4Bharat IndicConformer-600M | 22 Indian languages, **no English / code-mix** | MIT | Hindi 13.2 % (Vaani) | n/a | CTC/RNNT, ONNX | Pure-Hindi segments only |
| IndicWhisper (Vistaar) | Indian languages | open | Hindi avg 13.6 % (2023); FLEURS-hi 15.0 | n/a | Whisper-style | Baseline for a Hinglish fine-tune |
| **NVIDIA Nemotron 3.5 ASR streaming 0.6B** (4 Jun 2026) | 40 locales, **hi-IN "transcription-ready"**; no en-IN | OpenMDW-1.1 per HF card (another page says NVIDIA Open Model License): **licence check** | Hindi 6.81 % at 1.12 s chunks (test set not named) **(Med)** | streaming | No timestamps; code-switching not mentioned | **Most promising self-hosted Hindi candidate.** Evaluate on Hinglish |
| NVIDIA Parakeet 1.1b RNNT Multilingual (NIM) | incl. **hi-IN** | NVIDIA | n/a | n/a | NIM supports A10/A40/L4/L40; needs up to ~50 GB GPU memory | Alternative Hindi path via NIM |
| NVIDIA Canary-1b-v2 | 25 languages, no Hindi | CC-BY-4.0 | 7.15 % | 749 | Timestamps | EU later |
| Cohere Transcribe (26 Mar 2026) | 14 languages, no Hindi | Apache-2.0 | 5.42 % (AMI 8.15) | 525 | No timestamps / diarization | Strong English accuracy, but no timestamps hurts citations |
| NVIDIA Nemotron Speech Streaming EN 0.6B (2026) | English | NVIDIA | 6.93 % at 1.12 s chunks (AMI 11.73) | streaming | Cache-aware, 80 ms–1.12 s chunks | Live English captions later |
| distil-whisper large-v3.5 | English | MIT | 7.08 % short-form | ~1.5× turbo | — | Cheaper Whisper for English |
| Meta Omnilingual ASR (Nov 2025) | 1,600+ languages | Apache-2.0 | CER <10 for 78 % of languages; no Hindi figure found | — | — | Research option |

**API-only India models:**

- Sarvam **Saaras V3** (Feb 2026): ~19 % WER on IndicVoices, code-mixing, diarization. **No open weights.**
- IBM Granite Speech 4.1 2B tops the English leaderboard at 5.33 % **(Med: secondary source)** but has no Hindi.

**Benchmark caveats:**

- The Open ASR Leaderboard now measures RTFx on **1× H200**, and has added Hindi to its multilingual track. **Leaderboard RTFx does not transfer to L4/A10G** **(High)**.
- Omi's open-source backend has a self-hosted **Parakeet** endpoint alongside Soniox (§10).

### 6.2 Throughput and $ per audio-hour

Instance prices are from AWS's own price files. On-demand prices were published 2026-09-25. Spot prices are a snapshot taken 2026-10-06 and are volatile.

| Instance (GPU) | us-east-1 on-demand | us-east-1 spot | ap-south-1 on-demand | ap-south-1 spot |
|---|---|---|---|---|
| g4dn.xlarge (T4 16 GB) | $0.526 | $0.220 | $0.579 | $0.190 |
| g5.xlarge (A10G 24 GB) | $1.006 | $0.501 | $1.208 | $0.507 |
| **g6.xlarge (L4 24 GB)** | **$0.805** | $0.105–0.60 (volatile: AWS spot feed showed $0.105, Vantage $0.603; Spot Advisor average saving 49 %) | **$0.966** | not listed in spot feed (Spot Advisor: 53 % saving) |
| g6e.xlarge (L40S 48 GB) | $1.861 | ≈ on-demand | $2.235 | not listed |
| inf2.xlarge (Inferentia2) | $0.758 | $0.318 | $0.986 | $0.298 |

Fractional-GPU `g6f` sizes are listed in Mumbai, e.g. g6f.xlarge at $0.285/h. They may suit a small always-on floor; this is unverified for ASR.

**Spot facts (AWS Spot Advisor, Oct 2026, High):**

| Instance | Saving vs on-demand: us-east-1 / ap-south-1 | Interruption rate |
|---|---|---|
| g6.xlarge | 49 % / 53 % | **>20 %** |
| g5.xlarge | 56 % / 54 % | >20 % |
| g4dn.xlarge | 60 % / 54 % | 10–20 % |
| inf2.xlarge | 84 % / 69 % | — |

- **g6f.xlarge** (⅛ L4, 3 GB) costs $0.2375 (us-east-1) / $0.2852 (Mumbai). Its interruption rate is lower (5–10 % / <5 %).
- Hyderabad (ap-south-2) lists g6/g6e at Mumbai prices.
- **Spot is fine for batch re-processing (checkpoint per chunk), not for the warm floor.**

**Measured throughput data points (High, but on other hardware):**

- faster-whisper large-v2 on an RTX 3070 Ti: a 13-min file in 17 s with batch 8 (~46× real time). WhisperX reaches ~70× on large-v2.
- NVIDIA Riva streaming:
  - Parakeet-CTC-0.6B on **L4**: 32 concurrent streams at RTFx ≈ 32 (160 ms chunks; tested concurrency, not the maximum).
  - Parakeet-RNNT-1.1B on L40: 256 streams.
- Kyutai STT: L40S serves 64 connections at 3× real time.

**Effective throughput assumption (Low: estimate, to be benchmarked).** The leaderboard's RTFx ~3,400 for Parakeet is large-batch inference on top-end hardware. Derating it for our pipeline:

- L4 delivers roughly ⅓–½ of that.
- We add VAD segmentation, resampling, timestamps and diarization (pyannote community-1 or Sortformer).
- Utilization is about 40 %.

That leaves an **effective 50–200× real time per g6.xlarge**.

| Effective speed | g6.xlarge us-east-1 on-demand | g6.xlarge ap-south-1 on-demand | g5.xlarge spot (either region) |
|---|---|---|---|
| 50× | $0.016 /audio-h → **$1.24 heavy / $0.53 typical** per user-month | $0.019 → $1.49 / $0.64 | $0.010 → $0.77 / $0.33 |
| 100× | $0.008 → $0.62 / $0.27 | $0.010 → $0.74 / $0.32 | $0.005 → $0.39 / $0.17 |
| 200× | $0.004 → $0.31 / $0.13 | $0.005 → $0.37 / $0.16 | $0.0025 → $0.19 / $0.08 |

**The catch is the fixed floor, not the marginal cost.**

- One g6.xlarge kept warm costs **$588/month** in us-east-1 or **$706/month** in Mumbai.
- Running it only 14 h × 22 business days costs $248 / $298.
- Against a 24×7 warm instance, the break-even with vendors is:

  | Vendor | Break-even (audio h/month) | Heavy users | Typical users |
  |---|---|---|---|
  | Transcribe ($0.36/h) | ~1,630 | ~21 | ~50 |
  | AssemblyAI U3.5 Pro ($0.23/h) | ~2,550 | ~33 | ~77 |
  | Soniox ($0.10/h) | ~5,900 | ~76 | ~178 |

- In Mumbai the break-even is about 20 % higher.

**One L4 has huge headroom.** At 100× it processes about 100 audio-hours per wall-clock hour (~70k audio-h/month), so one or two instances per region serve thousands of seats.

**Diarization choice moves the number by about 5×.** Independent estimate from the self-hosted research pass (on-demand us-east-1, g6.xlarge, 50 % utilization):

| Pipeline | Assumed RTFx | $/audio-h |
|---|---|---|
| Parakeet batch, no diarization | ~300× | ~$0.0027 |
| + Sortformer / Nemotron-3-Diarization | ~150× | ~$0.0054 |
| + pyannote community-1 (diarization becomes the bottleneck) | ~40× | ~$0.020 |
| faster-whisper turbo (Hindi) on g5 | ~60× | ~$0.017 |

Either way it comes to **≈ $0.10–2 per heavy user-month**, consistent with the table above.

**Serving options on AWS** (track 03 covers the AWS AI stack):

- ECS/EKS GPU service with a warm floor during business hours plus queue-driven scale-out, or
- **SageMaker Asynchronous Inference** (S3-in/S3-out, scales to zero, minutes of cold start), or
- AWS Batch on Spot for re-processing.

**Use NVIDIA NeMo / Riva / NIM or ONNX-Runtime-GPU for Parakeet, and faster-whisper (CTranslate2) for Whisper.**

### 6.3 Practical view for a 3–6 person team

- **US:** self-hosting Parakeet-v2 plus diarization is a ~3–5 engineer-week job to production quality. It covers inference service, batching, timestamps, diarization merge, monitoring and a regression eval set. **Not month-1 work.** Ship on a managed API first and swap behind an interface once volume passes ~50–100 seats per region.
- **India:** no open model is *proven* on Hinglish:
  - Parakeet is English-only.
  - IndicConformer has no English.
  - Whisper-turbo's code-switch quality is unknown and it is prone to hallucination.
  - NVIDIA Nemotron 3.5 ASR lists hi-IN but is untested on code-mixing. Evaluate it first.

  A credible in-region self-hosted Hinglish path is likely a **fine-tune project** on Whisper-turbo, a Conformer or Nemotron, with ≥50–100 h of consented in-domain data. Plan it for after the MVP. Until then, use an India-resident managed engine (§9.3).

## 7. Diarization, speaker identification and "consent mode"

### 7.1 Diarization options

| Option | Quality evidence | Speed / limits | Cost | Notes |
|---|---|---|---|---|
| **pyannote community-1** (open, CC-BY-4.0, pyannote.audio 4.x, Sep 2025) | DER **AMI 17.0 / DIHARD3 20.2 / VoxConverse 11.2 / AliMeeting 20.3** vs legacy 3.1 at 18.8 / 21.4 / 11.2 / 24.5 **(High)** | GPU; speaker count can be bounded (`min/max_speakers`); "exclusive" mode for clean ASR alignment | Self-host | Default open choice for batch |
| **pyannoteAI premium** (precision-2 on card; pricing page now lists "Precision-3") | DER **AMI 12.9 / DIHARD3 14.7 / VoxConverse 8.5 / AliMeeting 15.2** (precision-2) **(High: vendor)** | Hosted API, 300 ms streaming latency, on-prem for enterprise | See the Precision-3 row. Speaker identification **€0.096/h**; voiceprints **€0.015 each** **(High)** | Best accuracy per euro, but audio leaves AWS (EU company) unless on-prem |
| **NVIDIA Streaming Sortformer 4spk-v2** (CC-BY-4.0) | DIHARD3 DER 13.24 % (≤4 speakers) but 42.56 % (≥5); CALLHOME 6.6–12.4 % for 2–4 speakers **(High)** | **Max 4 speakers.** Latency modes from 0.32 s (RTF 0.18) to 30 s (RTF 0.002). Card says it degrades on non-English and noisy audio | Self-host | Good for *live* 1:1s and small meetings; weak for big rooms and India |
| **NVIDIA Nemotron-3-Diarization** (23 Sep 2026) | DER **DIHARD III 12.73 / AMI-SDM 11.14 / NOTSOFAR1-SC 11.00** at 30.4 s latency; 13.55 on DIHARD at 0.32 s **(High: model card)** | **Up to 8 speakers.** ~12,000× real time at batch 32 | Self-host. **OpenMDW-1.1 licence: legal check** | **Best open candidate for our batch pipeline** (fast and far-field meeting sets). Validate on Indian meetings |
| pyannoteAI **Precision-3** (17 Sep 2026) | 16.4 % DER averaged over 8 datasets, vs 18.8 % precision-2 and 24.9 % community-1 **(Med: vendor)** | Hosted; Live-1 streaming option | €0.112/h; hosted community-1 **€0.035/h**; Live-1 €0.198/h | Accuracy benchmark and fallback |
| On-device: FluidAudio (LS-EEND up to 10 speakers, Sortformer, pyannote 3.1 on the Neural Engine), Argmax SpeakerKit (pyannote community-1) | not benchmarked here | iOS 16–17+ | SDK (Apache/MIT; Argmax Pro is commercial) | Enables a "transcript-only, audio never leaves the phone" mode later |
| Vendor-bundled diarization | AssemblyAI U3.5 Pro reports cpWER 30.17 across hard diarization conditions (vendor) | — | Included (Speechmatics, Deepgram batch, ElevenLabs, Soniox, Transcribe); AssemblyAI +$0.02/h; Sarvam +₹15/h | Fine for MVP. Quality varies most on far-field multi-speaker audio |

**Practical rules**

- **Use the calendar.** Bound `max_speakers` with attendee count + 1.
- **Diarize per conversation, not per upload chunk.** Run it on the assembled session (§8.4) so speaker labels stay stable. Link clusters across sessions only with consented voiceprints (see §7.3).
- **Name speakers without biometrics first:**
  - self-introductions and addressing ("Thanks, Priya") via LLM
  - attendee lists from the calendar
  - Teams/Graph transcripts for internal meetings (track 02), which already carry names
- **Expect overlapping speech in multi-party meetings.** It's a known main contributor to DER, and the overlap ratio wasn't verified this session (Low). Exclusive-mode diarization assigns each instant to one speaker. The memory layer should accept "uncertain speaker" and show confidence.

### 7.2 Wearer vs others ("who said that?")

- **Most valuable signal:** "did *I* say it, or did the client?"
- **Options in increasing legal sensitivity:**
  - **(a) Acoustic heuristics, no enrollment.** On a chest-worn wearable the wearer is the loudest, highest-SNR, most direct speaker. Dual-mic devices can add direction of arrival. This is weak on a phone in a pocket or on a table.
  - **(b) Session-local clustering.** No persistent template is stored.
  - **(c) An enrolled voiceprint of the wearer**: 30–60 s of read speech, embedding compared against clusters. This works well in practice (Limitless "label once"; pyannoteAI and OpenAI accept reference clips).
  - **(d) A tenant-wide voiceprint registry** of colleagues.
- **(c) and (d) are biometric processing.** Track 10 has already decided **no server-side voiceprint enrollment in v1**: voiceprints are a HIPAA Safe-Harbor identifier and biometric data under US state laws such as Illinois BIPA, and consent is needed under India's DPDP Act (legal track).
- **Accuracy evidence for (c):**
  - Speaker-verification equal error rate (EER) on clean VoxCeleb, multi-second clips:
    - NVIDIA TitaNet-L: **0.66 %**
    - WeSpeaker ResNet34: 0.87 % (0.66 % with score normalisation)
    - harder VoxCeleb1-H trials: **1.4–2.3 %** **(High)**
  - Picovoice Eagle (on-device) claims 0.18 % EER with a 4.5 MB model **(Med: vendor benchmark)**.
- **Vendor options:**
  - Speechmatics supports enrollment from 5–30 s clips, up to 50 identifiers per session, batch and real-time **(High)**.
  - AssemblyAI's "speaker identification" infers *names from what is said* (LLM) and **does not enroll voices** **(High)**. That is a non-biometric option worth copying.
- **Research:** "Personal VAD", a ~130k-parameter target-speaker VAD, beats a VAD + verification cascade **(High: paper)**. It points to a tiny on-device "is this the wearer?" gate.
- **Recommendation:**
  - **v1:** (a) + (b), plus a manual "that was me" correction.
  - **v1.5:** offer opt-in **on-device-only** wearer enrollment. The template stays in the Secure Enclave/Keystore-protected app store and is never uploaded. Gate it on legal sign-off.

### 7.3 "Consent mode" (keep only consented/enrolled speakers, drop others)

- **Mechanism:** VAD → diarize → embed each cluster → cosine-match against the enrolled templates → keep matched clusters; drop audio and text of unmatched clusters before upload, or before storage if done server-side.
- **Feasibility: technically feasible, product-limited.**
  - Speaker verification is very accurate on clean, longer utterances. Error rates rise sharply for **short turns (<2 s), far-field or pocketed audio, overlap, and similar voices**.
  - **Estimate (Low):** 5–15 % of other people's speech would leak through, or the wearer's own speech would be dropped, on phone-in-pocket audio. Tune the threshold toward dropping, which means losing some of the wearer's own words.
  - Limitless announced a consent mode in 2024 (pause until a new voice says it consents). Sources disagree on whether it shipped **(Low)**.
- **Product conflict:** the flagship question, "what were the **client's** requirements?", is exactly the speech consent mode would drop.
- **Recommendation: make it a per-meeting/per-policy mode, not a global default.** Options:
  - "Self-only" (drop others) for unannounced in-person encounters, e.g. hallway capture outside scheduled meetings.
  - "Full capture" only for calendar meetings where a notice was given, such as an invite footer or verbal announcement (legal track decides the wording).
  - Tenant admins choose the default.

## 8. Capture pipeline design for a work-only, admin-governed recorder

### 8.1 Capture modes (v1)

| Mode | How it starts | When it stops/pauses | Notes |
|---|---|---|---|
| **Work session** (the "always-on" mode, scoped to work) | **User taps "Start work session"** in the app. Must be inside an admin-allowed window (days and hours per tenant time zone). | Auto-stops at the end of the window or max hours. Auto-pauses on policy events (below). Manual pause/stop from the notification or Live Activity. | The only mode that records continuously. Both OSes need a foreground start (§2.1, §3.1). |
| **Meeting capture** (calendar-driven) | ~2 min before an in-person, hybrid or **external-platform** meeting, a local notification or Live Activity says "Capture '<subject>'?". **One tap starts it** (allowed on both OSes). Auto-starts silently only if a work session is already running. | Calendar end time + grace period, or manual | Internal Teams meetings are skipped by default: Graph transcripts cover them (track 02) |
| **Quick capture** | iOS: Control Center / Action button / Lock Screen control via `AudioRecordingIntent` (needs a Live Activity). Android: Quick Settings tile or notification action | Manual or ~5 min idle | For "remember this idea" |
| **Import** | Share sheet: native call recordings (iOS 18.1+ Phone, Google/Samsung dialers), voice memos | — | Legal route for phone calls; the call recording itself announces to participants |

### 8.2 Tenant policy object (admin-governed, pushed from backend and optionally via Intune app config)

- **Time:**
  - `allowed_windows` (per weekday, tenant/user time zone)
  - `max_hours_per_day`
  - `hard_stop_outside_window` (default true)
- **Place (optional):**
  - `allowed_sites` (office geofences or Wi-Fi BSSIDs) **or** "any location"
  - Geofencing needs location permission. On Android, background location brings its own Play declaration, so prefer "pause when leaving site", which iOS `CLMonitor` handles well. Store only a site label, not raw GPS.
- **Calendar rules:**
  - auto-prompt for in-person or external meetings
  - **never capture events marked Private** (Outlook `sensitivity = private`), personal or HR categories, or keyword deny-lists (e.g. "medical", "1:1 HR")
  - skip internal Teams meetings that will have Graph transcripts
- **Capture scope:**
  - "full" vs **"self-only"** for unscheduled encounters (§7.3)
  - minimum notice requirements, e.g. append a capture notice to invites (legal track)
- **Retention:**
  - raw audio **30 days** default (cross-track), configurable 0–90
  - transcripts kept, redacted
  - "discard audio after transcription" option
- **Data region:** pinned per tenant (US or India). Upload endpoints, S3 buckets, STT engines and keys are all in-region (§8.6).
- **Visibility:** recordings are **private to the user**. Admins see policy compliance and metadata counts, never content (Play stalkerware rule, §3.5).

### 8.3 Pause/resume semantics (identical UX on both platforms)

- **Hard pause.** The mic is fully released and the OS indicator goes off. Resume needs one tap: notification, Live Activity or tile. Used for:
  - leaving an allowed site
  - outside allowed hours
  - private calendar events
  - user "Pause"
  - voice command "pause recording" (later; needs on-device keyword spotting)
- **Soft pause** (short gaps only). Used for interruptions such as phone calls, back-to-back meeting gaps, or a "pause 5 min" button:
  - **Android:** keep the FGS and stop `AudioRecord`. The indicator goes off and later resume is silent (§3.1; verify per OEM).
  - **iOS:** keep the session alive and discard buffers. **The orange dot stays on**, so say so in the UI and cap it at a few minutes.
- **The OS will interrupt us during calls** (both platforms). Close the chunk, record a gap marker, and resume when allowed.

### 8.4 On-device chain and chunking

1. **Capture:** 16 kHz mono PCM via `AVAudioEngine` / `AudioRecord` (source `VOICE_RECOGNITION` or `MIC`). Keep the OS voice-processing (AEC/NS) **off** unless testing shows it helps far-field ASR.
2. **VAD:** Silero (§4.1). Drop non-speech. Keep 300 ms pre-roll and 1–2 s hangover.
3. **Encode:** Opus, 16 kbps VBR wideband, 20 ms frames, in Ogg.
   - Android 10+ has a native Opus encoder (Ogg/WebM) **(High)**.
   - On iOS, bundle libopus, or fall back to AAC-LC around 32 kbps.
   - Opus guidance: 10–24 kbps for VoIP, ~10 kbps already wideband **(High)**.
   - Amazon Transcribe batch accepts Ogg/WebM directly; streaming accepts Ogg-Opus **(High)**, so no re-encode is needed.
   - **ASR impact of 16 kbps vs lossless is unmeasured here.** AWS recommends lossless for best results. A/B test 16 vs 24 kbps vs FLAC on the eval set. Storage barely changes the decision (§9.1).
4. **Chunk:** **60 s upload chunks** (~120 KB at 16 kbps).
   - Each has a header: `device_id`, `session_id`, `seq`, monotonic start (`mach_continuous_time` / `elapsedRealtimeNanos`), UTC start, sample count, audio route, VAD stats and policy state.
   - The server **re-assembles sessions** (calendar-bounded, ≤8 h, since Transcribe batch accepts up to 28,800 s / 2 GB per file **(High)**) before diarization, so speaker labels stay consistent.
   - A first-pass transcript of each chunk gives "recent" answers fast; a second pass at session level gives the final diarized transcript.
5. **Encrypt** each chunk with AES-256-GCM using a per-chunk data key. Wrap the key with a per-tenant, per-region KMS key via the backend. Store it in iOS Data Protection class "complete until first user authentication" or Android Keystore-backed storage.
6. **Delete locally only after the server acknowledges a checksum.**

### 8.5 Upload policy and offline

- **Cellular use is small:** a heavy user uploads ~0.55 GB/month, so Wi-Fi-only is not needed for cost. Offer a "Wi-Fi only" toggle for India users on metered plans.
- **Cadence:** every 2–5 min on cellular, immediately on Wi-Fi, and every ~60 s only while a "live" question is pending.
- **Mechanics:** iOS background `URLSession` (survives suspension) and Android WorkManager or uploads from inside the FGS. Resumable, idempotent uploads keyed by (`session_id`, `seq`).
- **Offline:** an encrypted ring buffer of up to ~48 h of *speech* (≈350 MB). When storage is low, **stop capture with a warning rather than silently dropping audio**. A server heartbeat detects gaps (killed app, mic toggle, OEM killer) and nudges the user.

### 8.6 Regionality and data residency

- **US tenants:** everything stays in **us-east-1**: S3, ASR and the LLM.
- **India tenants:** upload endpoint, S3, KMS, ASR and redaction all in **ap-south-1 (Mumbai)**. Transcribe exists there, not in Hyderabad (ap-south-2). Self-hosted GPUs are available in Mumbai (g4dn, g5, g6, g6e, inf2, g6f all listed).
- **Third-party STT for India only under India-processing contracts**, e.g. Azure Speech Central India, which processes data only in the resource's region (§5.1).

### 8.7 Time alignment, calendar linking and de-duplication

- **Clocks:**
  - Use the device monotonic clock inside a session plus OS (NTP-synced) UTC at chunk start. The server fits drift per session.
  - Phone UTC error is typically sub-second **(Low: assumption)**, which is enough for calendar linking.
  - For exact alignment with other sources, use content-based alignment (below).
- **Calendar-first episode segmentation (track 05):** each session is split and labeled by overlapping Graph calendar events. Attendees give `max_speakers` and candidate names; location gives a site label.
- **Phone + desktop + Teams de-duplication.** Priority order:
  1. Graph Teams transcript (authoritative speakers)
  2. Desktop capture (mic = user, loopback = others; track 02)
  3. Phone mic
  
  Detect duplicates by user, time overlap with the same calendar event or Teams join URL, and text similarity of transcripts (e.g. 5-gram shingle Jaccard ≥0.3 within a ±2 min window). Optionally add audio fingerprint cross-correlation. Keep the authoritative source. Keep phone audio only where it adds content, such as the in-room side conversation in a hybrid meeting.
- **Citations:** answers cite a transcript span and an **audio snippet** (start/end offsets into the session) while raw audio is still retained. After expiry, citations fall back to text only.

## 9. Cost model per user (US and India tenants)

### 9.1 STT cost per user-month

Volumes come from §1: typical 33 h, heavy 77 h (22 workdays), lifelog 105 h (30 days; out of v1 scope). Prices are list prices from §5 and §6.

| Option | $/audio-h | **Typical (33 h)** | **Heavy (77 h)** | Lifelog (105 h) | Region fit |
|---|---|---|---|---|---|
| Amazon Transcribe **batch** | 0.36 | 11.88 | 27.72 | 37.80 | US ✔, **India ✔ (Mumbai)** |
| Transcribe batch + PII redaction (tier 1) | 0.504 | 16.63 | 38.81 | 52.92 | US ✔, India ✔ (en-IN only) |
| Transcribe **streaming** | 0.60 | 19.80 | 46.20 | 63.00 | US ✔, India ✔ |
| Azure Speech batch | 0.18 | 5.94 | 13.86 | 18.90 | US ✔, **India ✔ (Central India)** |
| Deepgram Nova-3 batch (mono / multi) | 0.258 / 0.312 | 8.51 / 10.30 | 19.87 / 24.02 | 27.09 / 32.76 | US ✔; India ✘ (not verified) |
| AssemblyAI U3.5 Pro + diarization | 0.23 | 7.59 | 17.71 | 24.15 | US ✔; India ✘ |
| AssemblyAI U3.5 Pro + diarization + PII | 0.31 | 10.23 | 23.87 | 32.55 | US ✔ |
| OpenAI gpt-4o-mini-transcribe (no diarization) / gpt-transcribe | 0.18 / 0.27 | 5.94 / 8.91 | 13.86 / 20.79 | 18.90 / 28.35 | US ✔; India unverified |
| ElevenLabs Scribe v2 (diarization incl.) | 0.22 | 7.26 | 16.94 | 23.10 | US ✔ |
| Speechmatics Melia (diarization incl.) | 0.12 | 3.96 | 9.24 | 12.60 | US ✔ |
| Soniox v5 async (diarization incl.) | 0.10 | 3.30 | 7.70 | 10.50 | US ✔ (policies unverified) |
| Sarvam (₹30/h; ₹45/h with diarization) | 0.34 / 0.51 | 11.25 / 16.88 | 26.25 / 39.38 | 35.80 / 53.69 | India ✔ *only with an India-processing contract* |
| **Self-hosted Parakeet/Whisper + diarization, g6.xlarge on-demand, 50–200× effective** | 0.004–0.019 | **0.13–0.64** | **0.31–1.49** | 0.42–2.03 | US ✔, India ✔ (in-region) |
| Self-hosted on Spot (g5/g4dn/g6 snapshot prices) | 0.001–0.010 | 0.03–0.33 | 0.07–0.78 | 0.10–1.06 | US ✔, India ✔ |
| On-device only | 0 (cloud) | 0 | 0 | 0 | Quality and hi-IN limits (§4) |

**Fixed costs for self-hosting** (not in the per-user figures):

- A warm g6.xlarge costs **$588/month** in us-east-1 or **$706/month** in Mumbai running 24×7, or **$248 / $298/month** during business hours only (14 h × 22 d).
- Break-even against Transcribe is about **21 heavy or 50 typical users per region**; against Soniox or Speechmatics, about **65–90 heavy or 150–210 typical users** (§6.2).
- Engineering: ~3–5 engineer-weeks to production, plus ongoing MLOps.

**Storage, requests and transfer per user** (Opus 16 kbps, 30-day raw-audio expiry):

- S3 Standard ≈ $0.013/month (0.55 GB × $0.023/GB-month in us-east-1).
- PUTs for 60 s chunks ≈ $0.02 (4,620 × $0.005/1k).
- KMS data-key calls ≈ $0.01–0.02.
- Data transfer *into* AWS is free.
- **≈ $0.05 per user-month all-in, so storage is irrelevant to the decision.** Even keeping a year of audio at S3 Standard-IA ($0.0125/GB-month) is ≈ $0.08/month.

### 9.2 Does it fit a $30–50 seat?

Cross-track inputs:

- LLM cost per typical user is ≈ **$23/month (US, Sonnet 5.5)** and **≈ $13 (India, Haiku 4.5 in-region)**.
- Non-AI infrastructure ≈ $0.44.

| Typical user, monthly COGS | STT on Transcribe batch | STT on Azure batch / AssemblyAI | STT self-hosted (~$0.5) |
|---|---|---|---|
| **US** (LLM $23 + infra $0.44) | ≈ $35.3: **too high** for a $40 seat | ≈ $29.4–31.0: thin margin | **≈ $24**: ~40–50 % gross margin at $40–50 |
| **India** (LLM $13 + infra $0.44) | ≈ $25.3: **too high** for a ~$30 seat | ≈ $19.4 (Azure batch) | **≈ $14**: ~50 % margin at $30 |

**Conclusion:**

- A managed STT engine at $0.18–0.36/h is affordable for pilots but **not at scale**.
- At scale, STT needs to land at **≤ $1–3 per typical user-month**. That means self-hosted in-region models, or a sub-$0.10/h managed engine that proves itself in the bake-off.
- Policy also lowers STT volume:
  - work windows
  - VAD
  - "self-only" for unscheduled encounters
  - Graph transcripts for internal Teams meetings

### 9.3 Recommended STT strategy

| Phase | US tenants (us-east-1) | India tenants (ap-south-1) |
|---|---|---|
| **MVP, months 0–3, pilots** | **Amazon Transcribe batch** ($0.36/h) with diarization. PII *identification* for en-US as a first pass; our redaction runs after it. Est. **$12 typical / $28 heavy** per user-month: fine for ≤100 pilot seats. | **Amazon Transcribe batch in Mumbai**, `en-IN` by default. Per tenant or user, choose `hi-IN` or batch multi-language ID for Hindi-heavy users. Est. **$12 / $28**. In parallel, put **Azure Speech Central India** ($0.18/h batch; MAI-Transcribe in Central India) through the bake-off as a cheaper in-country option. |
| **Bake-off (weeks 2–6)** | On our own eval set (§5.2): Transcribe vs self-hosted Parakeet-v2 (+ Nemotron-3-Diarization or pyannote community-1) vs AssemblyAI U3.5 Pro vs Soniox / Speechmatics vs Azure MAI-Transcribe. | Transcribe en-IN/hi-IN vs Azure Central India (standard + MAI-Transcribe) vs self-hosted Nemotron 3.5 ASR (hi-IN) / Whisper-turbo / IndicConformer / Parakeet (for Indian English) vs Sarvam `codemix` (scoring only, unless an India-processing DPA is signed). |
| **Scale, from month 4 (or >~50 seats per region)** | **Self-hosted Parakeet-TDT-0.6B-v2 + Nemotron-3-Diarization** (fallback: pyannote community-1 if the OpenMDW licence fails review) **on g6.xlarge**: warm floor during business hours, queue-driven scale-out, Spot for re-processing. Est. **≈ $0.2–1.5 per heavy user** plus the floor. Transcribe stays as failover. | **Route by language:** English-dominant sessions go to self-hosted (Parakeet or Whisper-turbo, whichever wins on Indian English). Hindi/Hinglish sessions go to the best in-country managed engine (Transcribe hi-IN or Azure) **until an in-region open model wins**. Lead candidate: **NVIDIA Nemotron 3.5 ASR (hi-IN)**; others are Whisper-turbo or Conformer fine-tuned on ≥50–100 h of consented Hinglish. Target **≤ $3 per typical user-month**. |

**Streaming vs batch:**

- **Batch is the default.**
  - It's ~1.7–2× cheaper: Transcribe $0.36 vs $0.60/h; AssemblyAI $0.21 vs $0.45/h.
  - It's more accurate: full context and session-level diarization.
  - It suits mobile background constraints: no long-lived sockets through Doze or app suspension.
- **Get freshness from micro-batching.** With 60 s chunks and a first-pass ASR, "what did the client just say?" is answerable about 1–3 min after the speech.
- **Use streaming only for explicit live features in a foreground app** (live captions, real-time assist). Transcribe's default quota is 25 concurrent streams per account per region (adjustable), which also argues against per-user always-on streams.

**Lifelog variant** (out of v1 scope): multiply heavy-user STT by ≈1.36 (105 h vs 77 h). Only self-hosted makes it affordable.

## 10. Lessons from existing products' capture tech

| Product | Capture approach | Battery: claimed vs reported | Processing / STT | Audio retention | Notable lessons |
|---|---|---|---|---|---|
| **Limitless Pendant** (acquired by Meta, 5 Dec 2025) | Clip-on pendant. Streams/syncs over BLE to the phone app, which uploads to the cloud. Desktop app captured meetings. | Marketed as "100 h". A 2026 review says reviewers saw 6–7 h of continuous recording **(Low: secondary source)**. | Cloud ("Confidential Cloud"). Speaker ID shipped ("label once, remembered"). A "Consent Mode" (record new voices only after verbal consent) was announced in Apr 2024; sources disagree on whether it shipped **(Low)**. | Kept, with a configurable auto-delete | After the acquisition, hardware sales stopped, support continues for 1 year, and the Rewind app was wound down **(High, TechCrunch)**. Service reportedly ended in the EU, UK, Brazil, South Korea, Israel and Turkey **(Med)**. Reviewers complained about mislabeled speakers. |
| **Bee** (acquired by Amazon; announced Jul 2025) | $49.99 wrist/clip device. **Single button press starts/stops capture, with a green LED while capturing** (Amazon, 2026). Also works through the phone apps and an Apple Watch. | Claims "up to 160 h". Reviews report ~2 days of active use and extra drain on the paired phone **(Low)**. | Cloud models ("a combination of AI models"). Up to 40 languages. | **No audio stored**: audio is processed and discarded after transcription **(High: Amazon/TechCrunch)** | Discarding audio helps privacy, but users can't check the transcript against the recording. Reviews say it is weak with multiple speakers and can't tell the wearer from others **(Low)**. Since 2026 it is moving toward explicit capture (button + LED) and "Actions" into email and calendar. |
| **Plaud NotePin / NotePin S / Note Pro** | Records offline to 64 GB on-device storage, then syncs through the phone app. NotePin S ($179, Jan 2026) has 2 MEMS mics and a ~3 m range. The desktop app captures system audio and detects meetings. | **20 h continuous recording**, 40 days standby (NotePin) **(High: vendor)** | Cloud transcription in 112 languages, with speaker labels. Plans: 300 free min/month, Pro 1,200 min, Unlimited. | Kept | More than 1.5 M devices sold **(Med, TechCrunch)**. Compliance badges are part of the pitch: ISO 27001/27701, SOC 2, HIPAA, GDPR, EN 18031. The hardware-lessons track notes a device SDK and transcription API but no India region. |
| **Omi** (open source) | Pendant: nRF5340 BLE SoC, 2 PDM mics, 150 mAh battery, 8 GB NAND. **Opus at 16 kHz is the default BLE codec since firmware v1.0.3**, sent as 160 samples per packet. Phone app relays to the backend. | Claims 10–14 h per charge (omi.me). The README says "24 h+ continuous capture" **(Med)**. | Backend code has **Soniox** streaming STT, a **self-hosted Parakeet** option, a Deepgram key and a Modulate fallback. It also has a **Silero-VAD "gate"** (512-sample = 32 ms windows, threshold 0.65, 300 ms pre-roll, 4 s hangover, 5 s keep-alives, so silence never reaches the paid STT), speaker embeddings, voiceprints and clustering **(High: GitHub source)**. | Kept (speech profiles in a cloud bucket) | Even a consumer device optimizes STT cost: VAD gating, a cheap streaming vendor and self-hosted Parakeet. This is the closest public reference architecture to ours. |
| **Otter (iOS)** | Phone mic, Bluetooth or AirPods. Recording continues in the background. **Live Activities give one-tap pause, resume and stop on the Lock Screen**. Siri Shortcut and widget start. | n/a | Cloud. English, Spanish, French and Japanese only. | Kept | Lock Screen controls are now the expected UX. Cellular calls can't be recorded (OS restriction). |
| **Granola** | No meeting bot. On desktop it captures system audio plus mic. On iPhone it records the active mic input (built-in or Bluetooth). **The Live Activity shows "taking notes" plus a duration, and the Dynamic Island shows a timer.** | n/a | Cloud STT (reported to be Deepgram and AssemblyAI, **Med**) and LLMs from OpenAI/Anthropic | **Audio cached only until transcription finishes, then deleted** | The docs say recordings of about 10 h or more may fail to process, so sessions must be chunked. Bluetooth mics lower accuracy. |
| **Fireflies mobile** | The phone app records in-person meetings. | n/a | Cloud | Kept | Mobile recordings are exempt from upload rate limits. File uploads are capped at 100 MB / 150 min. |
| **Just Press Record** | iPhone, iPad, Mac and **standalone Apple Watch recording** (complication or Siri). iCloud sync. | n/a | Transcription in 30+ languages | Kept | Shows that Watch capture works for user-initiated recording, not as an all-day logger (see §2.4). |
| **Pixel Recorder / Samsung Galaxy AI** | First-party apps that get privileged OS integration | see §3.6 | On-device ASR and summarization | Kept on device | Users' baseline expectation: on-device transcription with speaker labels at no marginal cost. |

**Lessons we're applying**

1. **Plan for one workday of capture plus overnight charging.** Wearable battery claims are standby-heavy, and real continuous-capture figures are much lower (Plaud's 20 h is the outlier because it records locally with no live BLE streaming). On phones, the battery cost is the radio and the CPU wake-ups, not the mic (§4.4).
2. **Speaker attribution draws the most accuracy complaints** (Limitless, Bee). Diarization and naming wearer vs others needs real investment, plus confidence UI and one-click relabel (§7).
3. **Keeping audio is a product choice.** Bee and Granola delete audio after STT. Plaud, Omi and Limitless keep it. Our default (cross-track): raw audio in S3 with a ~30-day expiry so answers can cite an audio snippet. Tenants can choose "discard after transcription".
4. **The market is moving from always-on to explicit or activity-detected capture**: Bee's button + LED, Pebble Index 01 records only while pressed, the Sandbar ring is "not always listening" (hardware-lessons track). That fits our work-only scope: a work session armed by the user, calendar-driven prompts, and tap-to-capture (§8).
5. **The standard topology is a BLE relay to the phone with Opus at 16 kHz** (Omi), plus on-device flash for offline (Plaud 64 GB, Omi 8 GB). Our phone pipeline should treat "phone mic" and "wearable over BLE" as two sources feeding one upload/ASR path.
6. **Lock Screen and Dynamic Island state is expected on iOS** (Otter, Granola), and the persistent notification is mandatory on Android (§3).
7. **Acquisition risk is real.** Limitless was absorbed by Meta (EU/UK service ended); Bee by Amazon. B2B buyers will ask about our STT vendors' continuity, so keep the ASR layer swappable.

## 11. Recommendations for PersonaAgent

**Capture product (v1)**

1. **Ship a "work-mode recorder", not a cold-start always-on recorder.** Neither iOS nor Android lets a third-party app start the mic from the background. Both allow many hours of capture once the user starts it in the foreground.
   - Build three modes (§8.1):
     - **Work session** (tap to start; runs inside admin-set windows)
     - **Meeting capture** (a calendar prompt, one tap)
     - **Quick capture** (Control Center / Action button / Quick Settings tile)
   - Add **share-sheet import** for native call recordings.
   - This matches the market's move to explicit capture (Bee button + LED, Pebble Index, Sandbar) and our work-only scope.
2. **iOS specifics:**
   - Session and recording:
     - `.playAndRecord` + `audio` background mode
     - `setPrefersNoInterruptionsFromSystemAlerts(true)`
     - an interruption/resumption manager covering both the iOS 26 interruption API and iOS 27 `resumptionRecommendationNotification`
   - State and controls:
     - a Live Activity/Dynamic Island with pause/resume/stop, refreshed before its 8 h limit
     - `AudioRecordingIntent` only for quick capture
   - Hard vs soft pause as defined in §8.3.
   - No Watch dependency.
   - **Prototype in week 1:** background resume after a call, AirPods route changes, and Action-button capture.
3. **Android specifics:**
   - Service and audio:
     - one `microphone` FGS started from the foreground
     - soft pause by stopping `AudioRecord` inside the FGS
     - `VOICE_RECOGNITION` source
     - `isClientSilenced` gap logging
   - Reliability:
     - **per-OEM onboarding wizard** (Xiaomi, Vivo, Oppo, realme, Samsung, OnePlus)
     - server heartbeat plus "capture stopped" nudges
   - Play Console:
     - FGS declaration with video
     - prominent-disclosure consent screen
     - an accurate Data safety form
4. **Keep recordings private to the user** (admins govern policy, not content). This keeps us out of Play's "monitoring tool" category, reduces legal exposure and builds trust. Integrate **Intune app configuration** for tenant binding and policy. Admins can MDM-deny the mic as a kill switch.

**Pipeline**

5. On device:
   - **Silero VAD → 60 s Opus 16 kbps chunks → AES-GCM → in-region S3** (us-east-1 / ap-south-1)
   - local encrypted buffer, upload every 2–5 min on cellular
   
   Then on the server:
   - session assembly (calendar-bounded) → batch ASR + diarization → our redaction → memory
   
   Answers cite transcript and audio-snippet offsets (§8).
6. **De-duplicate against Graph Teams transcripts and desktop capture.** Graph wins for internal Teams meetings. Phone capture targets in-person and external meetings, which also keeps STT volume (and cost) down.

**Speech stack**

7. **MVP STT = Amazon Transcribe batch in both regions** ($0.36/h; in-region; en-US/en-IN PII first pass; hi-IN supported). Put it behind an `AsrEngine` interface with per-tenant routing from day 1.
8. **Run the bake-off in weeks 2–6** on a ~12 h consented eval set (US English, Indian English, Hinglish, Hindi, noisy/far-field). Measure WER/CER, entity errors, code-switch error rate, DER, latency and $/h (§5.2).
9. **Scale STT (month 4+):**
   - **US:** self-hosted **Parakeet-TDT-0.6B-v2 + Nemotron-3-Diarization** (or pyannote community-1) on g6 (L4), ≈ $0.2–1.5 per heavy user-month.
   - **India:** route by language. English-dominant sessions go to self-hosted. Hindi/Hinglish sessions go to the best in-country managed engine (Transcribe hi-IN or **Azure Speech Central India**) until an in-region open model wins. Candidates: NVIDIA Nemotron 3.5 ASR (hi-IN), or a Whisper-turbo/Conformer Hinglish fine-tune.
   - **Sarvam** is strong on paper for Hinglish (`codemix`), but use it only under a contract that guarantees India-only processing and no training.
10. **Batch by default; streaming only for foreground "live" features.** Micro-batches give ~1–3 min freshness.
11. **Diarization:**
    - v1 uses calendar and LLM naming plus wearer heuristics, with **no voiceprints** (track 10).
    - A per-meeting **"self-only" mode** covers unscheduled encounters.
    - Opt-in, on-device-only wearer enrollment comes in v1.5, subject to legal sign-off.
12. **Redaction:** never rely on vendor PII alone. Transcribe has no Aadhaar/PAN and no hi-IN. Run track 10's detectors on every transcript. If audio is retained, mute PII spans using word timestamps.

**Indicative 3-month plan for 3–6 engineers**

- **M1:**
  - iOS/Android capture apps (work session + meeting prompt)
  - VAD/Opus/encrypted upload
  - S3 in two regions
  - Transcribe batch, basic transcript viewer
  - start eval data collection under consent
- **M2:**
  - session assembly + diarization + calendar linking
  - Graph de-dup
  - redaction pass
  - tenant policy engine + Intune config
  - OEM wizard and heartbeat
  - battery measurements
- **M3:**
  - pilot hardening (interruptions, gaps, offline)
  - bake-off decision per region
  - self-hosted Parakeet prototype in us-east-1
  - App Store / Play submissions with reviewer demo tenant

## 12. Risks & watch-outs

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | **App Review / Play policy friction.** Apple 2.5.14 (consent + visible indication) and 2.5.4 (background modes). Play spyware/stalkerware rules, FGS declaration, and the "monitoring tool" classification if admins can see content | Med / High | Visible state everywhere (Live Activity, notification). Explicit consent. Recordings private to the user. Reviewer demo tenant. Don't play silent audio to stay alive. Never use the Accessibility API |
| R2 | **Capture gaps.** OEM killers (Xiaomi, Vivo, Oppo, realme, OnePlus, Samsung), Task-Manager stops, iOS jetsam, failed resume after calls or route changes, mic toggle | High (India) / High | Heartbeat + gap UI. Per-OEM wizard. Supported-device list. Local buffer. Week-1 prototypes on real devices |
| R3 | **Hinglish / Indian-English accuracy** is unknown for every engine. Transcribe and Azure don't code-switch. Open models lack Hinglish | High / High (India) | Eval set first. Language routing. Fine-tune plan. Show citations with audio so users can verify |
| R4 | **Cost overrun.** Usage beyond assumptions (heavy users, lifelog creep), streaming adoption, managed-STT list prices at scale | Med / High | Batch by default. Policy windows and caps. VAD tuning. Self-only for unscheduled encounters. Self-host from month 4. Monitor $/user/day |
| R5 | **Data residency.** India audio leaving India via vendor APIs or global endpoints | Med / High | Region-pinned tenants. In-region engines only (Transcribe Mumbai, self-hosted ap-south-1, Azure Central India). DPA clauses. Egress allow-lists |
| R6 | **Speaker misattribution** ("the client said X" when the user said it) poisons memory answers | High / Med | Calendar-bounded speaker counts. Confidence labels. Answers cite audio. Easy relabel. Wearer heuristics; enrollment later |
| R7 | **Biometric / consent law.** Voiceprints (BIPA-type laws, HIPAA identifiers, DPDP consent); all-party-consent recording laws | Med / High | No server voiceprints in v1. Self-only mode. Notices on invites. Tenant-configurable consent flows (legal track) |
| R8 | **Battery and heat complaints**, especially with continuous uploads or on-device ASR | Med / Med | No continuous on-device ASR. Batched uploads. Measure %/h per device class before GA. Android 17 memory limits |
| R9 | **Platform API drift.** iOS 27 interruption API changes; Live Activity 8 h cap; `AudioRecordingIntent` semantics; Android 16/17 quota and memory rules | Med / Med | Abstract the session manager. Track the betas each June |
| R10 | **Vendor and price volatility.** Transcribe moved from tiered $0.024/min to flat $0.006/min. Deepgram and Azure have promotional meters. Acquisitions (Limitless→Meta, Bee→Amazon) | Med / Med | `AsrEngine` interface. Quarterly price check. Self-host path |
| R11 | **Whisper-family hallucinations** on silence or noise produce fabricated text in memory | Med / Med | Strict VAD gating. Avoid Whisper for English. Hallucination filters (repetition/no-speech probability) |
| R12 | **Compression artefacts** (Opus 16 kbps) costing ASR accuracy; AWS recommends lossless | Low–Med / Low | A/B test 16 vs 24 kbps vs FLAC. Storage cost is negligible either way, so raise the bitrate if needed |
| R13 | **Transcribe PII limits.** Streaming PII is not offered in Mumbai. PII redaction can't be combined with multi-language ID. AWS says its redaction doesn't meet HIPAA de-identification | High / Med | Use batch PII identification only as a first pass. Run our own redaction everywhere |

## 13. Open questions / could not verify

**Platform (prototype these in weeks 1–2)**

1. **iOS:**
   - Does background *resume* after a phone call or Siri still work on iOS 26/27? Restart after an AirPods route change in the background was reported to fail in 2019; is that still the case?
   - Does the 8 h Live Activity expiry stop an `AudioRecordingIntent` recording?
   - Can Shortcuts or the Action button start an `AudioRecordingIntent` while the app is not active? (A 2026 report says "Target is not foreground".)
2. **iOS on-device speech:**
   - Do SpeechAnalyzer and Core ML on the Neural Engine run while a recording app is backgrounded?
   - We need the official SpeechTranscriber locale list: en-IN is likely (Med), hi-IN is not on-device (Med–High).
   - Does SpeechTranscriber honour `contextualStrings`?
3. **Android:**
   - Can `AudioRecord` be stopped and restarted from the background inside an already-running microphone FGS? (Inferred yes; test per OEM.)
   - Does a mic FGS keep network access in Doze?
   - Do mic-capture wake locks count toward Play's excessive-wake-lock vital?
   - How do HyperOS and One UI 7/8 behave in practice?
4. **Battery:** we found no first-party %/hour figures for continuous capture on iPhone, Apple Watch or Android. Measure them ourselves.
5. **Apple Watch:** no documented multi-hour background *recording* mode.

**Speech stack**

6. **Accuracy gaps:**
   - We found no independent **Indian-English, Hinglish or far-field** benchmark for 2026 engines. Our own eval set is mandatory.
   - The test set behind Nemotron 3.5's 6.81 % Hindi WER is unknown.
   - We found no open model with verified Hinglish code-switching accuracy.
7. **Unverified prices and terms:**
   - Amazon Transcribe: the official date of the change to flat $0.006/min; whether diarization is still free (Med).
   - Azure: MAI-Transcribe-1.5/2 list prices (Artificial Analysis implies about $0.10/h, Low); real-time diarization add-on price; PII support for STT.
   - Deepgram: non-promotional streaming prices; India region; whether opting out of the Model Improvement Program changes the price.
   - AssemblyAI: PII language coverage (en-IN?); "Universal-3.5 vs 3.6 Pro Realtime" naming.
   - Speechmatics: real-time prices; Melia's Hindi coverage.
   - Others: Soniox and Gladia data policies and regions; ElevenLabs zero data retention and residency; Rev.ai streaming.
   - Sarvam: India-only processing for the **API** (its privacy policy allows processing in US clouds), training opt-out for enterprise, Saaras v4 benchmarks. Gnani and Reverie pricing.
   - OpenAI: whether India data residency covers audio endpoints; Hindi/Hinglish quality of gpt-transcribe.
8. **Self-hosted:**
   - Real effective throughput of Parakeet, Nemotron-3-Diarization, Whisper-turbo and IndicConformer on L4/A10G in our pipeline.
   - Inferentia2 performance for these models.
   - Licence review for OpenMDW-1.1 (Nemotron models) and TEN VAD's "Apache 2.0 with conditions".
9. **Audio format:** the WER impact of Opus at 16 kbps vs 24 kbps vs FLAC on our audio.
10. **Usage assumptions:**
    - the real share of speech per armed hour in offices (brief: 3–4 h out of 10 h)
    - the overlap ratio in Indian meetings
    - the share of meetings that are in person vs internal Teams vs external platforms (this drives STT volume)
11. **Speaker ID:** accuracy of wearer verification on pocketed or table phone audio and short turns. No published numbers found.

**Products**

12. **Limitless:** whether "Consent Mode" ever shipped (sources conflict); its real continuous-recording battery life.
13. **Bee:** architecture (where ASR runs); real battery life.
14. **Plaud:** STT vendors.
15. **Otter:** official iOS background-recording limits.

## 14. Sources

*Accessed 5–6 Oct 2026. Some Apple documentation URLs are the `.md` variants that were fetched.*

**iOS / Apple**

- AVAudioSession `.record` category: https://developer.apple.com/tutorials/data/documentation/avfaudio/avaudiosession/category-swift.struct/record.md
- Apple Developer Forums:
  - no recording start in background, single mic owner: https://developer.apple.com/forums/thread/770698
  - background start / resume history: https://developer.apple.com/forums/thread/120038 (and ?page=2, ?page=3)
  - https://developer.apple.com/forums/thread/674632
  - AudioRecordingIntent "Target is not foreground": https://developer.apple.com/forums/thread/815725
  - no access to call audio: https://developer.apple.com/forums/thread/651540
- Handling audio interruptions (iOS 27 changes): https://developer.apple.com/documentation/avfaudio/handling-audio-interruptions.md
- `setPrefersNoInterruptionsFromSystemAlerts`: https://developer.apple.com/documentation/avfaudio/avaudiosession/setprefersnointerruptionsfromsystemalerts(_:).md
- `setPrefersInterruptionOnRouteDisconnect`: https://developer.apple.com/documentation/avfaudio/avaudiosession/setprefersinterruptiononroutedisconnect(_:).md
- `bluetoothHighQualityRecording`: https://developer.apple.com/documentation/avfaudio/avaudiosession/categoryoptions-swift.struct/bluetoothhighqualityrecording.md
- WWDC25 audio recording session: https://developer.apple.com/videos/play/wwdc2025/251/
- WWDC25 SpeechAnalyzer session: https://developer.apple.com/videos/play/wwdc2025/277/
- Recording indicator: https://support.apple.com/en-us/HT211876
- `AudioRecordingIntent`: https://developer.apple.com/documentation/appintents/audiorecordingintent.md
- Live Activities limits: https://developer.apple.com/documentation/activitykit/displaying-live-data-with-live-activities.md
- Background modes: https://developer.apple.com/documentation/xcode/configuring-background-execution-modes.md
- watchOS background audio: https://developer.apple.com/documentation/watchkit/playing-background-audio.md
- watchOS extended runtime sessions: https://developer.apple.com/documentation/watchkit/using-extended-runtime-sessions.md
- App Store Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
- iOS 18.1 call recording: https://www.apple.com/newsroom/2024/10/apple-intelligence-is-available-today-on-iphone-ipad-and-mac/
- iOS feature availability (locales): https://www.apple.com/ios/feature-availability/
- iOS 27 release date: https://macrumors.com/2026/09/09/apple-announces-ios-27-release-date/
- Speech framework:
  - SpeechTranscriber: https://developer.apple.com/documentation/speech/speechtranscriber.md
  - SpeechAnalyzer: https://developer.apple.com/documentation/speech/speechanalyzer.md
  - Speech updates: https://developer.apple.com/documentation/updates/speech.md
  - SFSpeechRecognizer: https://developer.apple.com/documentation/speech/sfspeechrecognizer.md
  - AnalysisContext: https://developer.apple.com/documentation/speech/analysiscontext.md
- SpeechAnalyzer locale list (community): https://antongubarenko.substack.com/p/ios-26-speechanalyzer-guide
- Argmax: Apple vs Argmax: https://www.argmaxinc.com/blog/apple-and-argmax
- MacStories speech API test: https://www.macstories.net/stories/hands-on-how-apples-new-speech-apis-outpace-whisper-for-lightning-fast-transcription/
- Metal in background: https://developer.apple.com/documentation/metal/preparing-your-metal-app-to-run-in-the-background.md
- BGContinuedProcessingTask: https://developer.apple.com/documentation/backgroundtasks/performing-long-running-tasks-on-ios-and-ipados.md
- Region monitoring: https://developer.apple.com/documentation/corelocation/monitoring-the-user-s-proximity-to-geographic-regions.md
- Focus filters: https://developer.apple.com/documentation/appintents/setfocusfilterintent.md
- Intent supported modes: https://developer.apple.com/documentation/appintents/appintent/supportedmodes.md
- Controls: https://developer.apple.com/documentation/widgetkit/creating-controls-to-perform-actions-across-the-system.md

**Android / Google**

- Foreground services:
  - Service types: https://developer.android.com/develop/background-work/services/fgs/service-types
  - Background-start restrictions: https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
  - User stopping: https://developer.android.com/develop/background-work/services/fgs/handle-user-stopping
  - Launching: https://developer.android.com/develop/background-work/services/fgs/launch
  - Android 11 FGS privacy: https://developer.android.com/about/versions/11/privacy/foreground-services
- Behaviour changes:
  - Android 14: https://developer.android.com/about/versions/14/behavior-changes-all
  - Android 15: https://developer.android.com/about/versions/15/behavior-changes-15
  - Android 16: https://developer.android.com/about/versions/16/behavior-changes-all and https://developer.android.com/about/versions/16/behavior-changes-16
  - Android 17 background audio: https://developer.android.com/about/versions/17/changes/bg-audio
  - Android 17: https://developer.android.com/about/versions/17/behavior-changes-all
- Notifications, permissions, power:
  - Notification permission: https://developer.android.com/develop/ui/views/notifications/notification-permission
  - Explaining access: https://developer.android.com/training/permissions/explaining-access
  - Doze and standby: https://developer.android.com/training/monitoring-device-state/doze-standby
  - Excessive wake locks: https://developer.android.com/google/play/vitals/excessive-wakelock
  - Battery-performance bar raise: https://android-developers.googleblog.com/2025/11/raising-bar-on-battery-performance.html
- Audio:
  - Sharing audio input: https://developer.android.com/media/platform/sharing-audio-input
  - Supported formats (Opus encoder Android 10+): https://developer.android.com/media/platform/supported-formats
- Play policy:
  - Accessibility API: https://support.google.com/googleplay/android-developer/answer/9888170 and https://support.google.com/googleplay/android-developer/answer/10964491
  - FGS declaration: https://support.google.com/googleplay/android-developer/answer/13392821
  - Spyware/stalkerware (malware policy): https://support.google.com/googleplay/android-developer/answer/9888380
  - User Data: https://support.google.com/googleplay/android-developer/answer/10144311
- OEM killers: https://dontkillmyapp.com/ (plus /samsung, /xiaomi, /oneplus, /oppo, /realme, /vivo, /huawei)
- On-device speech:
  - ML Kit GenAI speech recognition: https://developers.google.com/ml-kit/genai/speech-recognition/android
  - ML Kit GenAI: https://developers.google.com/ml-kit/genai
  - SpeechRecognizer source: https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/speech/SpeechRecognizer.java
- Pixel Recorder: https://support.google.com/pixelphone/answer/16267698 and https://support.google.com/pixelphone/answer/16269004
- Galaxy AI: https://www.samsung.com/us/galaxy-ai/ and https://www.samsung.com/in/galaxy-ai/
- Google Phone call recording: https://support.google.com/phoneapp/answer/9803950
- Intune app configuration (Android): https://learn.microsoft.com/en-us/intune/intune-service/apps/app-configuration-policies-use-android
- Android 12 work profile changes: https://developer.android.com/work/versions/android-12

**Cloud STT, pricing, regions**

- Amazon Transcribe:
  - Pricing: https://aws.amazon.com/transcribe/pricing/
  - AWS price-list file (published 2026-09-11): https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/transcribe/USD/current/transcribe.json
  - Input formats: https://docs.aws.amazon.com/transcribe/latest/dg/how-input.html
  - Endpoints and quotas: https://docs.aws.amazon.com/general/latest/gr/transcribe.html
  - Supported languages: https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html
  - PII redaction: https://docs.aws.amazon.com/transcribe/latest/dg/pii-redaction-batch.html and https://docs.aws.amazon.com/transcribe/latest/dg/pii-redaction-stream.html
- Azure:
  - Speech regions and data residency: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions
  - Retail prices: https://prices.azure.com/api/retail/prices
  - Language support: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt
- Deepgram:
  - Pricing: https://deepgram.com/pricing
  - Models and languages: https://developers.deepgram.com/docs/models-languages-overview
  - Redaction: https://developers.deepgram.com/docs/redaction
  - Model Improvement Program: https://developers.deepgram.com/docs/the-deepgram-model-improvement-partnership-program
- AssemblyAI:
  - Pricing: https://www.assemblyai.com/pricing
  - Models: https://www.assemblyai.com/docs/getting-started/models
  - Supported languages: https://www.assemblyai.com/docs/pre-recorded-audio/supported-languages
  - Data retention and training: https://www.assemblyai.com/docs/data-retention-and-model-training
  - Universal-3.5 Pro launch: https://www.assemblyai.com/blog/universal-3-5-pro-async
- OpenAI:
  - Pricing: https://developers.openai.com/api/docs/pricing
  - Speech-to-text: https://developers.openai.com/api/docs/guides/speech-to-text
  - Your data: https://developers.openai.com/api/docs/guides/your-data
  - gpt-transcribe launch coverage: https://alphasignal.ai/news/openai-replaces-whisper-with-gpt-transcribe-slashing-errors-by-52
- Google Chirp 3: https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3
- Speechmatics: https://www.speechmatics.com/pricing and https://docs.speechmatics.com/speech-to-text/languages
- Gladia: https://www.gladia.io/pricing
- ElevenLabs: https://elevenlabs.io/pricing/api and https://elevenlabs.io/docs/capabilities/speech-to-text
- Mistral: https://mistral.ai/pricing/api and https://docs.mistral.ai/capabilities/audio_transcription
- Amazon Bedrock model cards: https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html and https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-mistral-ai-voxtral-mini-3b-2507.html
- Soniox: https://soniox.com/pricing and https://soniox.com/docs/stt/concepts/supported-languages
- Rev.ai: https://www.rev.ai/pricing
- Sarvam:
  - API pricing: https://www.sarvam.ai/api-pricing
  - Privacy policy: https://www.sarvam.ai/privacy-policy
  - Transcribe API: https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe
  - Saaras model: https://docs.sarvam.ai/api-reference-docs/getting-started/models/saaras
  - ASR blog: https://www.sarvam.ai/blogs/asr
- Gnani: https://docs.gnani.ai
- Artificial Analysis STT leaderboard: https://artificialanalysis.ai/speech-to-text
- AI4Bharat Vistaar: https://github.com/AI4Bharat/vistaar and https://arxiv.org/abs/2305.15386

**Self-hosted models, AWS compute**

- NVIDIA models on Hugging Face:
  - https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
  - https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
  - https://huggingface.co/nvidia/canary-qwen-2.5b
  - https://huggingface.co/nvidia/canary-1b-v2
  - https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b
  - https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b
- NVIDIA NIM ASR support matrix: https://docs.nvidia.com/nim/speech/latest/reference/support-matrix/asr.html
- Other model cards:
  - https://huggingface.co/CohereLabs/cohere-transcribe-03-2026
  - https://huggingface.co/openai/whisper-large-v3-turbo
  - https://huggingface.co/distil-whisper/distil-large-v3.5
  - https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual
  - https://huggingface.co/Trelis/tara
- Open ASR Leaderboard methodology: https://github.com/huggingface/open_asr_leaderboard
- Serving and runtimes:
  - https://github.com/SYSTRAN/faster-whisper
  - https://github.com/m-bain/whisperX
  - https://github.com/kyutai-labs/delayed-streams-modeling
  - NVIDIA Riva ASR performance page (docs.nvidia.com, Riva user guide)
- AWS EC2 prices:
  - On-demand price files (published 2026-09-25): https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/US%20East%20(N.%20Virginia)/Linux/index.json and the "Asia Pacific (Mumbai)" equivalent
  - Spot prices: https://website.spot.ec2.aws.a2z.com/spot.js
  - Spot Advisor: https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json
  - Instance pages: https://instances.vantage.sh/aws/ec2/g6.xlarge (and g5.xlarge, g6e.xlarge, inf2.xlarge)
- S3 pricing: https://aws.amazon.com/s3/pricing/

**On-device ASR, VAD, diarization, speaker ID**

- On-device ASR:
  - https://github.com/FluidInference/FluidAudio
  - https://github.com/argmaxinc/WhisperKit (now argmax-oss-swift)
  - https://github.com/moonshine-ai/moonshine
  - https://github.com/k2-fsa/sherpa-onnx
- VAD:
  - https://github.com/snakers4/silero-vad
  - https://github.com/TEN-framework/ten-vad
- Opus recommended settings: https://wiki.xiph.org/Opus_Recommended_Settings
- Diarization:
  - https://huggingface.co/pyannote/speaker-diarization-community-1
  - https://www.pyannote.ai/pricing
  - https://pyannote.ai/blog/precision-3-benchmarks
  - https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2
  - https://huggingface.co/nvidia/nemotron-3-diarization
- Speaker ID:
  - https://github.com/Picovoice/speaker-recognition-benchmark
  - Personal VAD: https://arxiv.org/abs/1908.04284

**Products**

- Limitless:
  - https://techcrunch.com/2025/12/05/meta-acquires-ai-device-startup-limitless/
  - https://www.fast.io/resources/limitless-ai-review-2026.md
  - https://WWW.BUSINESSINSIDER.IN/limitless-ai-pendant-clips-clothes-hears-records-everything-2024-4
- Bee:
  - https://www.bee.computer/
  - https://www.aboutamazon.com/news/devices/bee-amazon-wearable-ai-device-new-features
  - https://techcrunch.com/2026/01/12/why-amazon-bought-bee-an-ai-wearable/
  - https://www.engadget.com/wearables/bee-has-been-busy-since-its-acquisition-by-amazon-last-year-150025311.html
  - https://www.consumeraffairs.com/news/amazon-acquires-a-wearable-company-whose-product-is-always-listening-072425.html
  - https://ticnote.com/en/blog/bee-wearable-ai-review (Low)
- Plaud:
  - https://www.plaud.ai/products/notepin
  - https://techcrunch.com/2026/01/04/plaud-launches-a-new-ai-pin-and-a-desktop-meeting-notetaker
- Omi:
  - https://www.omi.me/
  - https://docs.omi.me/doc/developer/Protocol
  - https://docs.omi.me/doc/developer/backend/Backend_Setup
  - https://github.com/BasedHardware/omi
  - https://github.com/BasedHardware/omi/tree/main/backend/utils/stt
  - https://raw.githubusercontent.com/BasedHardware/omi/main/backend/utils/stt/vad_gate.py
- Otter: https://apps.apple.com/us/app/otter-ai-voice-notes/id1276437113
- Granola: https://docs.granola.ai/help-center/ios/transcription
- Fireflies: https://guide.fireflies.ai/articles/8937818258-learn-about-fireflies-mobile-app
- Just Press Record: https://www.openplanetsoftware.com/just-press-record/

**Cross-track inputs used** (not re-researched): track 02 (Teams/Graph transcripts, desktop capture), track 03 (AWS AI stack, LLM unit costs), track 04 (regional cells, S3 retention), track 05 (calendar-first memory), track 10 (redaction: Transcribe PII limits, no voiceprints in v1), and the hardware-lessons and market tracks (wearable capture trends).
