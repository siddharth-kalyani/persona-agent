# 02 — Integration Surfaces & Meeting Capture

**Track:** Where PersonaAgent lives for the user (Outlook, Teams, Windows desktop, our own web app) and how we capture Teams/Zoom/Meet calls.
**Prepared:** 2026-10-06. **Audience:** founders + engineers making build decisions.
**Founder constraints applied:** first buyer = Microsoft 365 mid-market & enterprise (per-seat B2B); v1 regions = United States + India; 3–6 engineers, ~3-month MVP; always-on recorder is work-only and tenant-admin governed; Phase-1 redaction scoped to US + Indian requirements.

**Method & confidence.** Facts were checked against primary sources (Microsoft Learn, Microsoft 365 Developer Blog, vendor pricing/docs pages) fetched in Oct 2026. The session's web-search budget ran out mid-research, so the last items were verified only by fetching known primary URLs. Anything not verified is marked **Unverified** or **Estimate**. Confidence tags: **[High]** = primary source read this session; **[Med]** = secondary source or older primary source; **[Low]** = inference or memory, not re-verified.

---

## Executive summary

- **Don't build a clone of Outlook or Teams. Put PersonaAgent inside the tools people already use.** The MVP should be: (1) an **Outlook add-in** for drafting in the compose window, (2) **server-side drafts written through Microsoft Graph**, so suggested replies show up natively in every Outlook client, mobile included, (3) a **Teams agent plus a message action**, (4) **post-meeting Teams transcripts pulled through Graph**, and (5) **our own web app as the control center** (consent, persona studio, memory search, privacy, admin). It should not be a mirrored inbox. A full mail client costs us a year or more of effort, puts us in direct competition with Microsoft's UI, increases data exposure, and doesn't match how enterprises buy software.
- **In compose mode, an Outlook add-in can do everything Pillar 1 needs.** Our reading of the API docs:
  - **Reading the thread:** `body.getAsync` with `bodyMode` returns the whole conversation. Compose mode also exposes `inReplyTo` (Mailbox 1.14), `conversationId` and `getComposeTypeAsync` (1.10).
  - **Writing text:** `setSelectedDataAsync` inserts at the cursor. `setAsync` and `prependAsync` replace or prepend, with a 1,000,000-character limit.
  - **Clients:** it runs in new Outlook for Windows, classic Outlook, Outlook on the web and Mac. Mac needs the XML "add-in only" manifest, because the unified manifest still doesn't support Mac or mobile **[High]**.
  - **Mobile gap:** Outlook mobile only runs add-ins in read mode, and `body.setAsync`/`prependAsync` aren't supported in mobile compose **[High]**. **Graph server-side drafts (`createReply`, `Mail.ReadWrite`) fill the mobile gap.**
- **Outlook timelines favor web add-ins.** New Outlook doesn't support COM or VSTO add-ins. Microsoft pushed the enterprise opt-out phase for new Outlook to **March 2027** (MC949965), and classic Outlook stays supported until **at least 2029** **[Med]**. Mailbox requirement set **1.16 went GA on 30 Jun 2026** **[High]**. Legacy Exchange tokens are gone, so we authenticate with **nested app authentication (NAA)** through MSAL.js **[High]**.
- **Teams has no API for putting plain, editable text into the compose box.** Message extensions can only insert *cards*, and the `message` response type just shows text in the extension's popup **[High]**. Ways around it:
  - a deep link or TeamsJS `openChat`/`openGroupChat` with a pre-filled `message` (documented for new chats in draft state; behavior in existing chats needs a prototype);
  - copy to clipboard;
  - sending as the user through Graph after explicit approval;
  - pasting from the Windows companion (Phase 2).
- **The persona agent can live inside Teams and Copilot.** We would build it as a custom engine agent on the **Microsoft 365 Agents SDK (GA)**. Bot Framework SDK support ended in **Dec 2025** and its repo was archived on **5 Jan 2026** **[High]**. Custom engine agents **don't require a Microsoft 365 Copilot license** to appear in Copilot Chat **[High]**.
- **Graph post-meeting transcripts are the cheapest way to capture meetings in the customer's own tenant, but four conditions apply:**
  - The APIs are **free (no longer metered since 25 Aug 2025)** and cover scheduled meetings and **ad hoc 1:1, group and PSTN calls** through `adhocCalls`; some of that is still beta **[High]**.
  - They **only work for meetings in the customer's own tenant**.
  - They **only work when transcription was turned on**.
  - **Since late July 2026 a Teams admin must explicitly turn on "Transcript API access", which is OFF by default.** Speaker attribution is also OFF by default **[High]**. This gate goes straight into onboarding.
- **Microsoft's built-in AI recap API (`aiInsights`) only works for users with a Microsoft 365 Copilot license**, and results can take **up to 4 hours** after the meeting **[High]**. Useful as a bonus, not as a foundation.
- **Real-time Teams media bots are a poor fit for us.** In production they **must run on Windows Server in Azure**, in C#/.NET, with a public IP per VM. That rules out our AWS-only stack, so skip them for the MVP **[High]**.
- **Third-party meeting bots are getting harder to rely on.**
  - Recall.ai charges **$0.50 per recorded hour** (the same price for bots and its Desktop Recording SDK), plus **$0.15/hr** for transcription. The first 5 hours are free, and early-stage startups get **$0.25/hr for their first 10,000 hours** **[High]**.
  - Teams now **detects external bots by default and makes the organizer admit them** (MC1251206: GA June–Oct 2026).
  - From **Aug 2026**, admins can set `BlockDetectedBots` to block detected bots automatically **[Med]**.
  - Bots are therefore unreliable in meetings that other companies host.
- **Bot-free desktop capture is the only option that works for every meeting the user attends.** It records the microphone plus WASAPI loopback, Granola-style, and covers other companies' Teams, Zoom and Meet calls. It also carries the **highest consent risk** (US all-party-consent states; India's DPDP Act, whose obligations phase in through **13 May 2027** **[Med]**).
- **Recommended default capture policy for the US and India:**
  - **Meetings in the customer's tenant:** use Teams native transcription plus Graph. Microsoft's own banners notify every participant.
  - **Meetings hosted by other companies:** capture only when the user starts it, with an automatic disclosure. External capture should be **off by default and controlled by the tenant admin**.
  - **Never capture silently.**
- **MVP for 3–6 engineers over about 12 weeks (estimate ≈ 22–30 engineer-weeks of integration work):** web control center, Outlook add-in, Graph drafts, Teams agent plus message action, and Graph transcript ingestion. **Phase 2:** a Windows companion (hotkey, paste, bot-free recorder, possibly built on Recall's Desktop SDK), bots for external meetings where the host allows them, a Marketplace/Agent Store listing, and Mac.

---

## Contents
1. [A. Outlook add-ins (Office.js, 2025–2026)](#a-outlook-add-ins-officejs-20252026)
2. [B. Microsoft Teams & Microsoft 365 Copilot extensibility](#b-microsoft-teams--microsoft-365-copilot-extensibility)
3. [C. Windows desktop companion](#c-windows-desktop-companion-system-wide)
4. [D. Meeting & call capture](#d-meeting--call-capture)
5. [E. Our own web app — what to build and what not to](#e-our-own-web-app--what-to-build-and-what-not-to)
6. [Matrix 1 — Integration surfaces](#matrix-1--integration-surfaces)
7. [Matrix 2 — Meeting-capture options](#matrix-2--meeting-capture-options)
8. [Recommendations for PersonaAgent (MVP plan)](#recommendations-for-personaagent-mvp-plan)
9. [Risks & watch-outs](#risks--watch-outs)
10. [Open questions / could not verify](#open-questions--could-not-verify)
11. [Sources](#sources)

---

## A. Outlook add-ins (Office.js, 2025–2026)

### A.1 What a compose-mode add-in can read and write

For Pillar 1, the add-in needs to (a) understand the situation: new topic or reply, who the recipients are, what's in the thread; and (b) put text in the user's own voice into the compose window. Office.js covers both.

| Need | API (Office.js) | Min. requirement set | Notes | Conf. |
|---|---|---|---|---|
| Is this a new mail, reply or forward? | `item.getComposeTypeAsync()` | Mailbox 1.10 | Returns `newMail` / `reply` / `forward` plus coercion type. Also enabled on Outlook mobile (Android/iOS 4.2352.0+). | High |
| Which message is being replied to? | `item.inReplyTo` | Mailbox 1.14 | Internet message ID of the original. `null` for new messages. Classic Windows keeps it even if the user edits the subject. | High |
| Thread identity | `item.conversationId` | (base) | Available in reply compose forms. `null` for a brand-new item until it is saved with a subject. Changes if the user edits the reply's subject. | High |
| Thread content | `item.body.getAsync(coercion, {bodyMode})` | Mailbox 1.3 | In OWA, new Outlook and mobile, `bodyMode: FullBody` (the default) returns the **whole conversation body**, and `HostConfig` follows the user's conversation setting. Classic Windows and Mac ignore `bodyMode`. Use HTML coercion: Text "may not always provide reliable formatting" in OWA/new Outlook. | High |
| Recipients (for audience/relationship detection) | `item.to/cc/bcc.getAsync()`, `item.from.getAsync()` (1.7) | 1.1 / 1.7 | Mailbox 1.16 raises the limit to **up to 1,000 recipients** per field. | High |
| Draft's item ID (to look up in Graph) | `item.saveAsync()` (1.3), `item.getItemIdAsync()` (1.8) | 1.3 / 1.8 | Lets our backend fetch the original message, attachments and the full thread through Graph, using `conversationId`/`inReplyTo` lookups. | High |
| User's selected text ("rewrite this") | `item.getSelectedDataAsync()` | Mailbox 1.2 | Returns the selection in the subject or body. Requirement set not re-checked this session. | Med |
| Insert at cursor / replace selection | `item.body.setSelectedDataAsync()` | Mailbox 1.1 | Inserts at the cursor or replaces the selected text. If the cursor was never in the body, it inserts at the top. No inline CSS, no SVG. 1,000,000-character limit. | High |
| Replace whole body | `item.body.setAsync()` | Mailbox 1.3 | ⚠ In OWA/new Outlook the default `FullBody` **replaces the quoted thread too** and briefly flips the user's conversation setting, with a visible notification. **Always pass `bodyMode: HostConfig`** or use `setSelectedDataAsync`. | High |
| Prepend | `item.body.prependAsync()` | Mailbox 1.1 | Cursor behavior varies by client. | High |
| Footer/notice added at send time | `body.appendOnSendAsync()` (1.9), `prependOnSendAsync()` (1.13) | 1.9 / 1.13 | Max 5,000 characters. Can carry an "AI-assisted" disclosure if a customer's policy requires one. Marketplace rules require disclosing this in the listing. | High |
| Signature handling | `body.setSignatureAsync`, `disableClientSignatureAsync` | 1.10 | Also enabled on mobile. | High |

Recent requirement sets: **Mailbox 1.15** (Smart Alerts dialogs with Markdown, run a function from the Smart Alerts dialog, programmatic send, multi-select loading, Base64 attachments in reply forms) **[Med — mirror of Learn page]**. **Mailbox 1.16, GA 30 Jun 2026** (`OnMessageDecrypt`, EWS-callback-token detection, `contentId` for inline attachments, up to 1,000 recipients, `sessionData` up to 2,621,440 characters) **[High]**. Microsoft describes 1.16 as "closing the gap between COM/VSTO and web add-ins".

### A.2 UI surfaces inside Outlook

| Surface | What it is | PersonaAgent use |
|---|---|---|
| **Task pane** (pinnable) | A web UI (our React app) beside the compose or read form | Main surface: *Draft reply*, *Draft new message*, *Rewrite selection in my voice*, tone/length sliders, an "audience detected: client (external)" chip, and "why this wording" citations from memory. |
| **Function command** | A ribbon button that runs JavaScript with no UI | One-click "Draft reply in my voice" that inserts straight into the body. The unified manifest supports `keyboardShortcuts`. |
| **Event-based activation** | Headless handler that runs on events | `OnNewMessageCompose` (1.10) pre-warms persona and thread context. `OnMessageRecipientsChanged` (1.11) switches persona when, say, a manager is added. `OnMessageSend` / Smart Alerts (1.12) can run an optional "tone/PII check before send". Limits: **~300 s timeout, no UI APIs, at most 5 event-based add-ins active, the user must stay on the item**, and auto-launch **requires admin deployment** (or an *unrestricted* Marketplace listing). **[High]** |
| **Smart Alerts** | Can block or warn at send | Optional enterprise feature ("this reply to an external client contains internal project code names"). `block` mode is allowed only for admin-deployed add-ins, not Marketplace listings. **[High]** |

### A.3 Client support matrix (as of Oct 2026)

| Capability | New Outlook (Win) | Classic Outlook (Win) | Outlook on the web | Outlook for Mac (new UI) | iOS / Android |
|---|---|---|---|---|---|
| Web (Office.js) add-ins | ✅ (only kind supported; **no COM/VSTO**) | ✅ (plus legacy COM/VSTO) | ✅ | ✅ | ⚠ **Read mode only** for regular add-ins |
| Compose task pane / insert text | ✅ | ✅ | ✅ | ✅ | ❌ (`body.setAsync`/`prependAsync` unsupported in mobile compose; `displayReplyForm` unsupported) |
| Event-based `OnNewMessageCompose` | ✅ | ✅ (Win10 1903+) | ✅ | ✅ | ✅ (4.2352.0+) |
| `OnMessageRecipientsChanged` | ✅ | ✅ | ✅ | ✅ | ✅ (4.2425.0+) |
| `OnMessageSend` (Smart Alerts) | ✅ | ✅ | ✅ | ✅ | ❌ |
| Unified (JSON) manifest | ✅ | ✅ (v2307+, M365 subscription) | ✅ | ❌ | ❌ |
| Add-in only (XML) manifest | ✅ | ✅ | ✅ | ✅ | ✅ (requires `MobileFormFactor`) |

Sources: event-based activation table, mobile API list, unified-manifest overview **[High]**. Microsoft states that mobile add-ins are "in general, only Message Read mode", with exceptions limited to online-meeting providers, CRM/note-taking appointment logging and event-based add-ins **[High]**. **Consequence:** an in-compose "write it in my voice" experience **cannot run on Outlook mobile**. The mobile answer is Graph server-side drafts (A.7).

**Platform direction.** New Outlook for Windows supports only web add-ins. COM/VSTO and VBA don't run there. Microsoft moved the **enterprise opt-out phase to March 2027** (MC949965, previously April 2026), and classic Outlook remains supported until **at least 2029** **[Med]**. Building on Office.js is the only future-proof option. A COM add-in would be technical debt from day one.

### A.4 Authentication: nested app authentication (NAA)

- Use **MSAL.js `createNestablePublicClientApplication`**. Register an SPA redirect `brk-multihub://<our-domain>`. Check `Office.context.requirements.isSetSupported("NestedAppAuth","1.1")` and fall back to the Office dialog API. The broker group covers Word, Excel, PowerPoint, Outlook and Teams **[High]**.
- NAA supports incremental and dynamic consent, so the add-in should request minimal scopes (e.g., `Mail.Read` to fetch the thread). The heavy scopes stay with our backend's ingestion consent (covered by the Graph-permissions track).
- Microsoft began disabling **legacy Exchange user-identity/callback tokens on 17 Feb 2025**, allowed tenant re-enablement until June 2025, and turned them off for all tenants in **Oct 2025** **[Med — ISV notices summarizing Microsoft's schedule]**. Don't build on `getCallbackTokenAsync` or EWS. Mailbox 1.16 even adds an API to detect whether EWS callback tokens are still supported.
- Event handlers can use SSO only if the JS file is registered at a well-known URI **[High]**.

### A.5 Manifest choice: unified (JSON) vs add-in only (XML)

| | Unified manifest for Microsoft 365 | Add-in only (XML) manifest |
|---|---|---|
| Clients | Web, classic Windows (v2307+), new Outlook. **Not Mac, not mobile** **[High]** | All, including Mac and mobile (read mode) |
| Packaging | One "App for Microsoft 365" can bundle the **Outlook add-in + Teams app/agent**. Deployed as a *Teams app* in Integrated Apps | Separate Office add-in |
| Gaps | Some events missing; Outlook modules and contextual (activation-rule) add-ins not supported | Mature, everything supported |

**Recommendation:** ship the **XML manifest for the MVP** so it works on Windows (new and classic), web and Mac. In Phase 2, add a unified-manifest package that combines add-in, Teams agent and Copilot agent for single-click admin deployment, and keep the XML version for Mac and mobile until Microsoft closes the gap. Microsoft documents this dual-manifest pattern officially.

### A.6 Deployment, Marketplace publishing and timelines

- **Central deployment:** admins deploy from **Microsoft 365 admin center → Settings → Integrated apps**. Roles: Global admin, AI admin, Exchange admin or Azure Application admin. Assignments go to users or **top-level** groups only, not nested groups. Unified-manifest packages upload as a "Teams app". **The Integrated apps portal is not available in sovereign or government clouds** **[High]**, which matters later for US GCC customers. Event-based auto-launch only works when admin-deployed, and **every manifest change to an admin-deployed event-based add-in needs admin re-consent** **[High]**.
- **Propagation time** from deployment to users' clients: **Unverified** in this session. Field experience is typically hours, sometimes up to a day. Plan pilots with a 24-hour buffer **(Estimate)**.
- **Marketplace (formerly AppSource) certification policy 1120** **[High]**:
  - must use the latest Office.js and a released manifest schema;
  - **Outlook add-ins must support Outlook on the web**;
  - **SSO must have a fallback auth method**;
  - **event-based behavior must be disclosed** in the listing;
  - append-on-send must be disclosed;
  - add-ins that declare mobile support get an **extra design review** and must have **no upsell or in-app purchase UI on iOS/Android**.
  - Teams apps (policy 1140) add **Publisher Attestation** and functional and mobile requirements.
- **Review timelines** aren't published. Plan **2–4 calendar weeks** for first certification, including at least one resubmission **(Estimate)**. For an enterprise-first GTM, **we don't need a Marketplace listing for pilots**: customers can upload our package as a custom (LOB) app in Integrated Apps.

### A.7 "Server-side drafts" via Graph (the Fyxer pattern)

**Mechanics.** A Graph change notification fires on a new inbound message. Our triage model decides whether it "needs a reply" and from which persona. Then `POST /me/messages/{id}/createReply` (or `createReplyAll`) creates a **draft (`isDraft: true`) in the user's mailbox**. We set the body through the `comment` or `message.body` parameter (not both), or with a later `PATCH`. **Requires `Mail.ReadWrite` (delegated or application)** **[High]**. The draft is a normal Exchange item. It shows in Drafts and, in conversation view, inside the thread in every Outlook client, including mobile **[Med — standard Exchange behavior, not re-tested]**. The user reviews, edits and sends it like any other draft.

**Who does this.** Fyxer AI markets "Drafts replies in your voice" and states "Fyxer can't send emails on your behalf. We only draft your emails." Pricing: **Starter $22.50 and Professional $37.50 per user/month, billed annually**, with Enterprise bespoke. It supports Gmail and Outlook and includes a meeting notetaker that "joins meetings" **[High — fyxer.com]**.

| Server-side drafts — pros | Server-side drafts — cons |
|---|---|
| Works in **every** client, including iOS/Android, where add-ins can't compose | Needs **`Mail.ReadWrite`**, a broad write scope that triggers more security review and usually admin consent |
| No client install; nothing for IT to deploy beyond consent | Pre-generated **guesses**: the user's intent ("decline politely", "loop in legal") isn't known |
| Proactive: the draft is waiting when the user opens the mail, a strong "wow" moment | **Clutters Drafts**, syncs to every device; needs cleanup of stale drafts, plus dedupe if the user started a reply |
| Pure backend work: runs entirely on AWS | Generated text becomes a **mailbox record** (retention, eDiscovery, legal hold); DLP/sensitivity labels must be respected |
| Same pipeline later supports "follow-up nudges" | Inference cost on inbound volume, so it needs triage; latency is seconds to minutes |

**Verdict:** do **both**. Graph drafts give zero-friction value and mobile coverage, limited to *high-confidence "needs reply" threads* and with a user-level on/off switch. The add-in gives interactive control ("rewrite this", "make it firmer", new messages, delegation emails). Our sent-mail ingestion (another track) closes the loop: we diff what the user sent against our draft and use that as a training signal.

**Competitive note.** Microsoft's own Copilot in Outlook offers "Draft with Copilot" and "Coaching by Copilot" for users with a Copilot license. In this session I **could not verify** whether Copilot now explicitly learns the user's personal writing style from sent items (search budget exhausted). Treat that as a live competitive risk to check before positioning.

## B. Microsoft Teams & Microsoft 365 Copilot extensibility

### B.1 Teams app building blocks and how each maps to PersonaAgent

| Building block | What it gives us | PersonaAgent use | Conf. |
|---|---|---|---|
| **Personal agent (bot) in 1:1 chat** | Conversational UI in Teams. Streaming responses. Built with **Teams SDK** or **Microsoft 365 Agents SDK** | "Draft a reply to Priya about the SOW in my voice", "What did the client ask for in the 4 pm meeting?" (Pillar 2 Q&A), daily brief | High |
| **Message action** (action-type message extension, `context: message`) | "… → More actions → PersonaAgent: Draft reply". **The initial invoke carries the JSON of the message it was invoked from.** Opens a dialog (web view) | Main Teams drafting entry point. We already know thread and relationship context from ingestion. The dialog shows the draft plus tone controls | High |
| **Compose-box message extension** (`context: compose`) | Button under the compose box that opens a dialog. **The result is inserted as a card** | "Compose new message in my voice". Card insertion is the limitation (see B.2) | High |
| **Tabs / personal app** | A full web page inside Teams | Embed our control-center pages (memory timeline, persona studio) so users don't have to leave Teams | High |
| **Meeting apps** | Side panel, meeting stage, in-meeting notifications, TeamsJS `meeting.*` APIs | Pre-meeting brief in the side panel; "PersonaAgent notes are on" disclosure; optional live-stream capture (B.4) | High |
| **Link unfurling** | Cards for our URLs | Low priority (rich previews when sharing a memory or summary link) | High |

**Operational constraints** **[High]**:
- Message-extension invokes must answer within **5 seconds**. Teams retries twice and then shows "Unable to reach the app". Long LLM work belongs in a dialog with async polling or streaming.
- **Third-party message actions are hidden under "More actions" by default.** Only the three most recent appear in the overflow menu, and they can't be pinned. Expect discoverability friction; onboarding should teach the gesture.

### B.2 The critical question: can we put plain text into the Teams compose box?

**No supported API inserts editable plain text into the Teams compose box.** Search and action message extensions return **cards** (thumbnail, hero, connector or Adaptive) that go into the compose area. The `composeExtension` response type `message` only "displays a plain text message" inside the extension popup and inserts nothing **[High — respond-to-search and respond-to-action docs]**. A bot can also post an Adaptive Card *on behalf of* a user, but it renders as "<user> via <bot>" **[High]**. That's the opposite of "sounds exactly like me".

| Option | Result in Teams | Works where | Effort | Verdict |
|---|---|---|---|---|
| ME card insert | A card, not text; obviously app-generated | Chats, channels, meetings | Low | ❌ Wrong UX for "my voice" |
| **Deep link / TeamsJS `chat.openChat` / `openGroupChat` with `message`** | Plain text **pre-filled in the user's compose box**, editable; nothing is sent until the user presses Send | Documented "while the chat is in the draft state" (new chats). TeamsJS: "If a chat already exists, the deep link opens in that chat." **Whether the `message` prefill also applies to an existing chat is unclear → prototype in week 1.** Chats only, not channels | Low | ✅ Best native option if the prototype passes |
| **Copy to clipboard** from the dialog or side panel, then the user presses Ctrl+V | Plain text | Everywhere, including channels and mobile | Trivial | ✅ Always-available fallback |
| Graph `POST /chats/{id}/messages` (delegated `ChatMessage.Send`) | Sent immediately **as the user** (not a draft) | Chats and channels the user can post in | Low–Med | ⚠ Only behind an explicit "Send as me" click, with a preview; risk of sending something wrong |
| Bot `OnBehalfOf` attribution | Card "<user> via PersonaAgent" | Where the bot is installed | Low | ❌ Not persona-native |
| **Windows companion paste** (UI Automation focus check + clipboard + Ctrl+V) | Plain text typed into new Teams' compose box | Desktop only | Med–High | ✅ Phase 2; also covers Slack, WhatsApp Desktop, browsers |

Microsoft's own Copilot "rewrite" inside the Teams compose box is a first-party feature with no third-party hook **[Med]**.

### B.3 Reading the chat context

- **Message action:** we get the invoked message (body, sender, timestamps) directly **[High]**.
- **Whole-chat context:** an app installed in a **group chat or meeting chat** can be granted the application RSC permission **`ChatMessage.Read.Chat`** ("Read this chat's messages"). A **chat member** consents at install, so no tenant-wide admin consent is needed. Teams use `ChannelMessage.Read.Group`. **RSC in the personal scope is limited to `ChatMessageReadReceipt.Read.Chat`** **[High]**.
- **Practical design:** the drafting call doesn't depend on RSC, because our ingestion pipeline (delegated Graph chat permissions, covered by the Graph track) already holds the user's chat history and relationship graph. The Teams client only has to tell our backend *which* chat and message (IDs arrive in the invoke and context). RSC becomes useful when the bot must react in real time inside a group chat without being @mentioned.
- **Meeting-scoped RSC worth knowing** **[High]**: `OnlineMeetingTranscript.Read.Chat`, `OnlineMeetingRecording.Read.Chat`, `OnlineMeeting.ReadBasic.Chat`, `OnlineMeetingNotification.Send.Chat` (application), `Calls.AccessMedia.Chat`, `Calls.JoinGroupCalls.Chat` (application, for media bots). Delegated in-meeting RSC: `OnlineMeetingAudioVideo.Stream.Chat`, `MeetingStage.Write.Chat`, `OnlineMeetingIncomingAudio.Detect.Chat`, `OnlineMeetingParticipant.Read.Chat`.

### B.4 Meeting apps: one unconventional real-time path

TeamsJS exposes **`meeting.requestStartLiveStreaming(streamUrl, streamKey)`**. From the meeting **side panel**, an app can ask the local user to start streaming the meeting (audio and video) to **any RTMP endpoint**. Teams shows the user an "Allow/Cancel" confirmation. The manifest must set `meetingExtensionDefinition.supportsStreaming: true` **[High]**.

In principle this gives real-time meeting audio delivered to **AWS** (e.g., an RTMP ingest service, then audio extraction and streaming STT) without a Windows/Azure media bot. Caveats:
- Teams' RTMP-out feature generally requires the organizer and a `LiveStreamingMode` policy **[Med — Microsoft support article summary]**.
- It only works in meetings where our app is installed, and it's visible to participants.
- Treat it as an **experiment for Phase 3**, not a plan.

### B.5 SDK landscape (2026)

- **Bot Framework SDK:** "final long-term support ending December 2025"; repo **archived 5 Jan 2026**. Microsoft points to the **Microsoft 365 Agents SDK (GA)** **[High]**.
- **Microsoft 365 Agents SDK:** C# (.NET 8), JavaScript (Node 18+), Python (3.9–3.11). **AI-agnostic** ("makes no assumptions about what generates the response"). Has a channel abstraction (Teams, Microsoft 365 Copilot, web, Slack, and more) and built-in turn and state management **[High]**. This means our orchestrator on **Amazon Bedrock AgentCore** can sit behind a thin Agents SDK adapter.
- **Teams SDK** (renamed from Teams AI library) for Teams-specific agent features; GA for JS and C#, Python in preview **[Med]**. **Microsoft 365 Agents Toolkit** (renamed from Teams Toolkit) handles scaffolding and packaging **[High]**.
- **Hosting:** the bot or agent endpoint is our own HTTPS service and can run on AWS. An **Azure Bot resource / Entra app registration** is still needed for channel connectivity; the Teams channel is a standard channel **[Med — pricing page could not be fetched this session]**.

### B.6 Microsoft 365 Copilot extensibility: can PersonaAgent appear inside Copilot?

| Option | How it works | License for end users | Fit for PersonaAgent | Conf. |
|---|---|---|---|---|
| **Custom engine agent** | Our orchestrator and models (Bedrock), surfaced in **Teams and Copilot Chat** through the Agents SDK | **No Copilot license required.** Unlicensed users may incur Copilot-Credit metering *only if the agent uses shared tenant data via SharePoint/Copilot connectors* | ✅ **Best fit.** The same bot serves the Teams 1:1 chat and the Copilot agent picker; our persona model stays in control | High |
| **Declarative agent** | Microsoft's orchestrator and model, with our instructions and actions (API plugins / MCP) | Copilot license, *or* Copilot Chat with usage-based billing for tenant data | ⚠ Microsoft's model writes the final text, which dilutes persona fidelity. Could expose `draftInMyVoice` / `searchMyMemory` as actions for Copilot-licensed customers | High |
| **Copilot connector** (ex-Graph connector) | Push our derived content (meeting summaries, memories) into the tenant's index | Licensed users; metering for Copilot Chat users | Phase 3 option for Copilot-heavy customers. **Increases the data-exposure surface**, so make it opt-in per tenant | High |
| **Microsoft 365 Copilot APIs** (e.g., Meeting AI Insights) | Microsoft-generated insights | **Copilot license required; unlicensed users not supported** | Optional enrichment only | High |
| **Work IQ API** | Natural-language query over M365 work data; billed in Copilot Credits | Consumption | Alternative data path to evaluate (Graph track) | High (existence) |

- **Distribution:** Microsoft Marketplace through Partner Center (Microsoft 365 and Copilot program, with certification) for multi-tenant offers, the organizational catalog for single tenants, or direct sharing for pilots. Publication doesn't approve, deploy or assign; the customer admin does that **[High]**. Marketplace policy 1140.9 covers "Agents for Microsoft 365 Copilot and Agent 365" **[High (exists); details not read]**.
- **Agent 365 / Entra Agent ID:**
  - Agent 365 went **GA on 1 May 2026 at $15/user/month**.
  - **Microsoft 365 E7** ($99/user/month) bundles E5, Copilot, Agent 365 and Entra Suite **[Med — Microsoft Tech Community post title plus licensing blogs]**.
  - Each agent gets an **Entra Agent ID** and shows in the admin center registry. For enterprise buyers, being *governable* as a registered agent is a credible selling point.
  - **Unverified:** the exact onboarding path for third-party custom engine agents into Agent 365. Validate with Microsoft partner contacts.

**Answer to "could our persona agent appear inside Copilot/Teams as an agent the user chats with?"** Yes. Build one custom engine agent on the Agents SDK, enable the Teams and Microsoft 365 channels, and the same agent appears in Teams chat and Copilot Chat without requiring Copilot licenses. What we **can't** do is replace Copilot's own "Draft with Copilot" model in Outlook or the Teams compose box.

### B.7 How competitors integrate (public information)

| Product | Where it lives | Mechanism | Conf. |
|---|---|---|---|
| **Fyxer AI** | Gmail and Outlook inbox; meetings | Server-side drafts "in your voice", inbox organization; **notetaker that joins meetings** (bot) | High (site) |
| **Superhuman** (Mail, **Go**, Docs, Calendar) | Own mail client plus **Go**, a system-wide assistant | Mail "Auto Drafts … in your voice and with your context"; Go: "inline suggestions appear as you type" across tools, "chat about what's on screen" | High (site claims); Med (Grammarly/Superhuman corporate relationship: Grammarly acquired Superhuman in 2025 and adopted the Superhuman name, **not re-verified**) |
| **Grammarly for Windows** | System-wide desktop app | "Works in 1 million+ apps"; "No copying or pasting required"; can be turned off per app. Mechanism (accessibility APIs plus overlay) **not documented publicly**, so inferred | High (claims) / Low (mechanism) |
| **Microsoft Copilot** | Outlook, Teams, Copilot Chat | First-party; deepest UI hooks (compose rewrite, recap) | Med |
| **Granola** | Desktop (Mac, Windows) and mobile | **No bot**: "uses your computer audio, so doesn't invite a bot"; works with Zoom, Meet, Teams "and every other meeting app" | High (site) |
| **Otter, Fireflies, Read.ai, Fathom** | Calendar-driven meeting **bots** (plus apps) | Named by trade press among third-party notetakers affected by Teams' new bot controls | Med |
| **Recall.ai** (infra) | Bot API + Desktop Recording SDK | Powers many notetakers; Teams bots join as anonymous guests by default; signed-in bots only for business Teams meetings | High |

## C. Windows desktop companion (system-wide)

A desktop companion does two jobs no Microsoft API covers: (1) **write anywhere**. It can put plain text into the new Teams compose box, Slack, WhatsApp Desktop, browser-based CRMs and so on. (2) **Capture any call bot-free.** That includes other companies' Teams, Zoom and Meet meetings, softphones and huddles. It is also the most expensive surface to build and support, and the one IT security will scrutinize most.

### C.1 How system-wide writing assistants (Grammarly-style) work: reference architecture

Grammarly markets that it "works in 1 million+ apps" with "no copying or pasting required" and can be turned off per app **[High — product page]**. Its internals aren't publicly documented. The architecture below is the standard Windows approach **[Med — engineering knowledge, not vendor-confirmed]**.

| Function | Primary technique | Fallbacks / notes |
|---|---|---|
| Find the focused text field | **UI Automation (UIA)**: `IUIAutomation::GetFocusedElement`, focus-changed event handlers | Skip password fields (`IsPassword`). Per-app allow/deny list |
| Read text and selection | UIA **TextPattern** (`DocumentRange`, `GetSelection`) or **ValuePattern** | Simulated Ctrl+C into a clipboard snapshot, then restore the clipboard. As a last resort, on-device OCR (Windows AI Text Recognition) for context |
| Position UI near the caret | TextPattern2 caret range or bounding rectangles | Topmost, layered, `WS_EX_NOACTIVATE` overlay so focus is never stolen |
| Summon | Global hotkey (`RegisterHotKey`), e.g. Ctrl+Alt+Space → "Draft in my voice" palette | Tray menu |
| Insert text | **Clipboard (HTML + plain text) then `SendInput` Ctrl+V**, then restore the prior clipboard | `ValuePattern.SetValue` only for simple edit controls (it replaces the whole value and loses undo and rich text). Per-character `SendInput` (`KEYEVENTF_UNICODE`) is slow and conflicts with IME/autocomplete |

**New Teams and new Outlook are WebView2 (Chromium)-based clients** **[Med]**. Chromium exposes its accessibility tree to UIA clients, so reading compose-box text usually works. The compose editors are rich-text `contenteditable` surfaces, though, and **clipboard paste is the dependable way to insert**.

Known limits:
- **UIPI:** a normal process can't automate elevated windows unless built as `uiAccess` (signed and installed under Program Files).
- Secure desktop and lock screen are off-limits.
- **Citrix, AVD and Windows 365** sessions hide remote app text from a locally installed companion, which would have to be installed inside the VDI image.
- **Endpoint DLP (Purview)** policies can block clipboard operations on labeled content **[Med]**.
- Turning on Chromium accessibility adds CPU and memory overhead in the target apps **[Low]**.

All of these must go into the pilot test plan.

### C.2 Windows platform AI features that matter (2025–2026)

| Item | Status (Oct 2026) | Relevance | Conf. |
|---|---|---|---|
| **Windows AI APIs / Windows AI Foundry** (Windows App SDK) | Phi Silica (Limited Access Feature), Conversation Summarization, Text Rewriter Tone, Text Recognition (OCR), **Speech Recognition**, imaging APIs. NPU on Copilot+ PCs; GPU support for Phi Silica (NVIDIA RTX 30+/AMD RX 9060+, 6 GB+); Speech Recognition can also run on CPU (optional, removable model) | **On-device STT and redaction pre-pass** for privacy-sensitive capture is attractive; quality for Indian English and Hindi is **unverified**. Don't rely on NPUs: most enterprise fleets aren't Copilot+ PCs yet **(Estimate)** | High |
| **Phi Silica → "Aion Instruct"** | Microsoft says Phi Silica **is being replaced by Aion Instruct**: Insider rollout Nov 2026, retail Jan 2027, after which Phi Silica will be removed | **Don't build MVP features on Phi Silica** | High |
| **MCP on Windows** (On-device Agent Registry, `odr.exe`, agent connectors) | Documented as prerelease. MCP servers are contained by default; users and IT can control access per agent (Settings, **Intune**); logging and audit; built-in File Explorer and Settings connectors | Phase 3: ship a local **PersonaAgent MCP server** (`draft_in_my_voice`, `search_my_memory`) so Windows agents and other agent hosts can call our persona | High |
| **Recall / Click to Do / App Actions** (Copilot+ PCs) | Not re-verified this session | **Recall's 2024 privacy backlash** (screenshot database seen as a malware target) led Microsoft to delay and rework it: opt-in, Windows Hello gating, encryption/VBS enclaves, sensitive-content filtering. **Lesson for our always-on capture:** opt-in, admin policy, visible indicators, local encryption, app and site exclusions, one-click delete, published retention, third-party audit **[Low–Med, memory]** | Low–Med |

### C.3 Enterprise deployment of a desktop app

- **Packaging:** **MSIX** gives clean install and uninstall, App Installer auto-update and Intune LOB deployment. The alternative is an Intune **Win32 app** (`.intunewin` wrapping MSI or EXE). Admins also need policy controls through registry/ADMX or Intune settings: kill switch, per-app exclusions, capture on/off, external-meeting capture allowed or not.
- **Code signing:** Microsoft's **Trusted Signing is now "Artifact Signing"** **[High]**:
  - fully managed, **FIPS 140-3 Level 3 HSMs**;
  - Basic SKU includes **5,000 signatures/month**, Premium **100,000/month**; dollar prices weren't rendered on the pricing page, so **unverified**;
  - **does not issue EV certificates and has no plans to**;
  - needs a **paid Azure subscription** and organizational identity validation;
  - **"SmartScreen reputation builds up automatically… once the file hash has sufficient download history."**
  - We can sign from AWS CI with a service principal.
  - EV certificates no longer bypass SmartScreen reputation **[Med]**. In managed enterprises, Intune-pushed installs avoid the end-user download prompt anyway **[Med]**.
- **Microphone and system-audio access** is governed by Windows privacy settings that IT can manage by policy **[Med]**. Our recorder must also respect an org-level "no capture" policy.

### C.4 Tech-stack options for the desktop companion

| | **Electron** | **Tauri 2** (Rust + system WebView2) | **.NET WinUI 3 / WPF** | **Flutter** |
|---|---|---|---|---|
| UI from our web codebase | ✅ Same React | ✅ Same React | ❌ XAML | ⚠ Dart |
| UIA (read/insert) | Native Node addon or .NET sidecar | `windows-rs` bindings | ✅ First-class (UIAutomationClient) | Platform channels + native code |
| System audio (WASAPI loopback, process loopback) | Chromium `desktopCapturer` `audio:'loopback'` (limited control) **or Recall Desktop SDK (Electron-only)** | Native WASAPI through Rust | ✅ Mature (WASAPI via NAudio-class libraries) | Native plugin |
| Auto-update | electron-updater/Squirrel; MSIX possible | Built-in updater plugin; MSI/NSIS | MSIX/App Installer | Custom |
| Footprint | Large (bundles Chromium; ~100 MB+) **[Med]** | Small (uses WebView2) | Small–medium | Medium |
| Mac later | ✅ | ✅ | ❌ (separate Swift app) | ✅ |
| Fit for 3–6 TS-heavy engineers | ✅ fastest | ✅ needs some Rust | ⚠ needs C# skills | ⚠ |

**Recommendation:** if we use **Recall.ai's Desktop Recording SDK** to accelerate bot-free capture, **Electron is forced**: the SDK ships as the npm package `@recallai/desktop-sdk` for Electron apps **[High]**. Add a small native module for UIA and clipboard work. If we build capture in-house to keep audio inside our AWS boundary (relevant for India and for customers who reject sub-processors), choose **Tauri 2 with Rust native modules**, or .NET if the hires are C#-heavy. In either case, isolate capture in a separate privileged helper process so the UI can update independently.

### C.5 System audio capture primitives (Windows and later Mac)

- **WASAPI loopback:** captures "the system mix that is being played by the audio engine". **Shared-mode streams only** (exclusive-mode streams can't be looped back). Protected (DRM) content isn't captured. Event-driven loopback works on Windows 10 1703+. Microsoft notes loopback exists "primarily to support acoustic echo cancellation (AEC)" **[High]**.
- **Process loopback** (`ActivateAudioInterfaceAsync` with the process-loopback structure): captures audio from **one process tree only** (e.g., Teams.exe and its children) **or everything except** a process tree. It isn't tied to an endpoint. **Requires Windows 10 build 20348 or later** **[High]**. This is the key primitive for "capture only the meeting app, not Spotify". On older builds we fall back to system loopback.
- **Speaker separation:** mic = the user, loopback = everyone else, so the "me vs them" split comes for free. Diarization is needed only within the remote channel. If the user is on **speakers rather than a headset**, remote audio leaks into the mic. Apply AEC using the loopback signal as reference (WebRTC AEC3 or similar) before STT, or the transcript will double-attribute **[Med]**.
- **Mac (later):** Electron uses Apple's **CoreAudio Tap API on macOS 14.2+** and requires the `NSAudioCaptureUsageDescription` Info.plist key. Without it, the audio stream is silently dead, with no error **[High — Electron docs]**. Core Audio taps (`CATapDescription`, `AudioHardwareCreateProcessTap`) support per-process and global taps behind a TCC prompt **[Med — Apple page rendered partially]**. The Accessibility API (AXUIElement, Accessibility permission) covers reading and writing text. Recall's Desktop SDK supports **macOS 13+ on Apple Silicon only** and needs microphone, accessibility and screen-capture permissions **[High]**.

## D. Meeting & call capture

"All Teams calls" covers several technically different things. No single mechanism captures all of them.

| Call type | In-tenant Graph artifacts? | Notes |
|---|---|---|
| Scheduled meeting **organized in the customer's tenant** (private chat meeting) | ✅ `onlineMeetings/{id}/transcripts`, `/recordings` (v1.0) | Main path. The meeting must be on a calendar: the API "doesn't support meetings created using the create onlineMeeting API that aren't associated with an event on the user's calendar" **[High]** |
| **Ad hoc 1:1 calls, group calls, PSTN calls** | ✅ via **`adhocCalls`** (`/communications/adhocCalls/{callId}/transcripts`, `getAllTranscripts`) | Separate permissions (`CallTranscripts.Read.All`, `CallRecordings.Read.All`). **No RSC for ad hoc calls.** Parts are **beta only**. PSTN artifacts need the beta endpoint, and the call ID must be captured in real time **[High/Med]** |
| **Channel meetings** | ⚠ Beta only. RSC `OnlineMeetingTranscript.Read.Chat` does **not** apply. **Private-channel meetings not supported** by the subscriptions | Use the `.Read.All` permission plus an application access policy **[High]** |
| **Meet Now** | ⚠ Supported by the AI Insights API. Transcript-API coverage not explicitly confirmed | Test in pilot **(Unverified)** |
| Webinars / town halls | ✅ Transcripts: "all meeting types except live events". AI Insights: supported | **[High]** |
| **Meetings organized by another company** (cross-tenant) | ❌ Artifacts live in the **organizer's** tenant | This is the gap for consulting and sales users. Recall.ai: the Graph approach "would only work if the host had installed the Microsoft Teams app on their tenant" **[High/Med]** |

### D.1 Graph post-meeting transcripts and recordings: requirements and gotchas

1. **Cost:** "Starting August 25, 2025, the Teams APIs listed in this article are **no longer metered**, and no billing configuration is required" **[High]**.
2. **Permissions:**
   - Application: `OnlineMeetingTranscript.Read.All` / `OnlineMeetingRecording.Read.All` for meetings; `CallTranscripts.Read.All` / `CallRecordings.Read.All` for ad hoc calls.
   - Per-meeting RSC (application): `OnlineMeetingTranscript.Read.Chat` / `OnlineMeetingRecording.Read.Chat` when our app is installed in the meeting chat. Organizer or presenter consents; no tenant-wide admin consent.
   - Delegated `OnlineMeetingTranscript.Read.All` is also available "to users who are part of the meeting calendar invite".
   - **Application permissions require a Teams application access policy** granted to the users concerned **[High]**.
3. **The new admin gate (late July 2026):**
   - Teams admin center → Meetings → Meeting settings → **Transcript API access**. **"By default, Microsoft Graph access is off, so agents and apps can't access meeting transcripts, regardless of app-level permissions."** Speaker attribution is a second toggle, **also off by default**.
   - PowerShell: `Set-CsTeamsMeetingConfiguration -EnableGraphTranscriptAccess $true -EnableAttributedTranscripts $true`.
   - Failures return `403 GraphAccessToTranscriptsDisabled` and `SpeakerAttributionNotAllowed`. With attribution off, we can still request the unattributed format `application/vnd.microsoft.graph.transcript+text`.
   - Secondary sources date enforcement to **29 Jul 2026** **[High for behavior; Med for exact date]**.
   - **Impact:** our onboarding wizard must walk the Teams admin through both toggles. Without speaker attribution, Pillar 2's "what did the *client* say?" degrades badly.
4. **Transcription must actually happen.** Either users or policy turn on transcription, or our backend sets **auto-transcribe/auto-record** on meetings our users organize via the update onlineMeeting API or meeting options **[High]**. For meetings our users *attend* but don't organize, we depend on the organizer.
5. **Subscriptions:**
   - Scopes: tenant (`communications/onlineMeetings/getAllTranscripts`, application only), per user (`users/{id}/onlineMeetings/getAllTranscripts`, delegated or application), per meeting, and per app-installation (RSC).
   - **Notifications fire only if the subscription exists *before* transcription starts.** Subscriptions longer than 1 hour need a `lifecycleNotificationUrl`.
   - `includeResourceData` requires an encryption certificate.
   - For ad hoc calls, the user-scoped subscription fires when *that user initiates transcription*. Use the tenant-scoped subscription to catch calls where the other party started it **[High]**.
6. **Formats:** WebVTT with `<v Speaker>` tags (when attribution is allowed), unattributed text, `metadataContent`, and recordings as MP4. DOCX transcripts were deprecated on 31 May 2023 **[High]**.
7. **Latency:** artifacts appear "after the meeting ends". Microsoft publishes **no SLA**. Expect minutes, not seconds **(Estimate; Unverified)**. Design Pillar 2 so "what did the client require?" answers can arrive a few minutes after the call; if real time is needed, use desktop capture.
8. **Meeting expiry:** the API works only while the meeting hasn't expired (per Teams limits) **[High]**.

### D.2 Microsoft's AI meeting insights (`aiInsights`)

`GET /copilot/users/{userId}/onlineMeetings/{meetingId}/aiInsights[/{id}]` returns `meetingNotes` (title, text, subpoints), `actionItems` (with owner) and `viewpoint.mentionEvents` (who mentioned whom, with utterances).
- **Requires a Microsoft 365 Copilot license for the user.** Payment models and evaluation mode don't apply.
- Covers private scheduled meetings, town halls, webinars and Meet Now; **not channel meetings**.
- Insights only after the meeting ends, **"up to four hours"** later.
- Transcription or recording must be on **[High]**.

**Use:** optional enrichment for customers who already own Copilot. Our own summarization over the transcript stays primary.

### D.3 Real-time Teams options

| Option | Hard requirements | Verdict for us |
|---|---|---|
| **Graph Communications calling bot with application-hosted media** (Real-time Media Platform) | **"Production application-hosted media bots must be deployed on a Windows Server guest OS in Azure"** (on-prem only for dev/test). **C#/.NET** (incl. .NET 6 SDK support; no Node/C++). Azure Cloud Service, VMSS, IaaS VM or AKS; **not Azure Web Apps**. **Instance-level public IP** plus a per-VM port. ≥2 cores (4 vCPU minimum outside Dv2). Media library must be no more than ~3 months old. Calls are pinned to a VM. The doc still labels the platform "developer preview" **[High]** | ❌ for MVP: breaks the AWS-only architecture and needs .NET and Windows ops. Revisit only if a large customer needs real-time in-tenant capture without desktop installs |
| **Policy-based compliance recording** | Admin-assigned recording policy auto-invites a certified recorder bot to the user's calls. Microsoft certification program; trade press counts **13 certified vendors** **[Med]** | ❌ for a startup MVP. Possible later partnership: ingest from a certified recorder's archive |
| **TeamsJS RTMP live-stream** (B.4) | In-meeting app, side-panel confirmation, organizer/policy constraints | Experimental (Phase 3) |
| **Third-party bot with real-time transcript stream** (Recall.ai etc.) | Bot admitted to the meeting | ⚠ Increasingly blocked (D.4) |
| **Desktop capture** (D.5) | App installed on the user's PC | ✅ Real-time-capable |

### D.4 Third-party meeting-bot infrastructure (cost per meeting-hour)

| Vendor | Price | Platforms | Notes | Conf. |
|---|---|---|---|---|
| **Recall.ai** | **$0.50/recording-hour** PAYG (cut from $0.70 in early 2026); **same price for Desktop Recording SDK**; billed to the second; first 5 h free; **built-in transcription $0.15/h**; storage free 7 days, then **$0.05/h per 30 days**; **startups $0.25/h for first 10,000 h**; no platform fee | Zoom, Meet, Teams, Webex, GoTo, Slack Huddles | Enterprise: SSO, uptime SLAs, **BAA (HIPAA)**, **data residency US/EU/JP** (no India region listed). Teams bots join as **anonymous guests by default**, can't join sign-in-only or CAPTCHA meetings; **signed-in bots only for business Teams meetings**; lobby admission by default | High |
| **Meeting BaaS** | Tokens: 1 token = 1 recorded hour (with diarization); packs **$0.50 → $0.35/token**; transcription +0.25 token/h (BYOK +0.05); plans $0 / $99 / $199 / $299 per month (bot/day and retention limits) | Zoom, Meet, Teams | Artifacts to your own S3-compatible storage | High |
| **Attendee** (open source) | Self-host: infra cost only ("reduce costs 10x vs closed-source vendors") | Teams, Meet, Zoom | Django + Postgres + Redis, single Docker image. Hosted pricing not captured | Med |
| MeetStream | ~$0.35/h | Zoom, Teams, Meet | Secondary source only | Low |

**Platform headwinds for bots (2026):**
- Microsoft **MC1251206** (13 Mar 2026): Teams detects external meeting bots, **labels them "Unverified" in the lobby and requires the organizer to admit them**. "Bot detection will be enabled by default for all tenants." GA early June to end of October 2026 **[High]**.
- A new meeting-policy control, `ExternalBotAccessMode` (`AllowAllBots` / `RequireApprovalWhenDetected` (default) / `BlockDetectedBots`), adds **auto-blocking from August 2026** (roadmap 566201) **[Med]**.
- Reportedly excluded: Copilot, bots registered as Entra apps in the host's own tenant, and authenticated compliance-recording bots **[Low–Med]**.
- **Implication:** a PersonaAgent bot joining **other companies'** Teams meetings will increasingly sit in the lobby or be denied.
- Zoom and Google also require host-initiated notetakers with visible indicators for their own AI features **[Med]**.

### D.5 Bot-free desktop capture (Granola-style)

- **How:** mic (the user) plus **WASAPI process loopback** of the meeting app (everyone else), with chunked upload to our STT pipeline or on-device STT. Granola's public positioning: "Uses your computer audio, so doesn't invite a bot … works with Zoom, Google Meet, Teams and every other meeting app" **[High]**.
- **Coverage:** any app that plays audio on the PC. That includes Teams (desktop and web), Zoom, Meet in a browser, Slack huddles, WhatsApp Desktop, softphones and Webex, **including meetings hosted by other companies.** There's nothing for Teams' bot detection to see.
- **Build vs buy:** Recall's **Desktop Recording SDK** (Electron, `@recallai/desktop-sdk`) supports **Windows 10+ 64-bit (build 1803+): Zoom desktop, Teams desktop only, Meet in Chrome/Edge**; macOS 13+ Apple Silicon (Zoom, Teams, Meet, Slack audio). It has an ad hoc/in-person mode, real-time `transcript.data` events, and **uploads recordings to Recall's cloud** **[High]**. Its docs don't cover consent or notifications, so that's on us.
- **Reliability concerns:**
  - Detecting meeting start and stop: process audio sessions, window titles, calendar join links.
  - Device changes mid-call (Bluetooth headsets).
  - Exclusive-mode apps and DRM can't be looped back.
  - **Speakers vs headset:** AEC required.
  - **Conference rooms:** many voices on the mic channel, so diarization is needed.
  - **VDI:** Citrix/AVD audio redirection complicates which machine to install on.
  - **The user on a phone or tablet** isn't covered; Pillar 2's phone app is the fallback.
- **Speaker separation:** two channels (me / them) give near-perfect attribution of the user's own speech. That's ideal for Pillar 1's persona learning from spoken style (with consent) and for "what did I say at 2 pm".
- **Consent:** no platform banner fires, so **disclosure is entirely our responsibility** (D.7).

### D.6 Zoom RTMS and Google Meet Media API (completeness)

- **Zoom Realtime Media Streams (RTMS):**
  - GA. WebSocket streams of audio, video, transcript, chat and screen share.
  - Must be **enabled by a Zoom admin** at account, group or user level; **the host must approve**; client 6.5.5+.
  - "If an end user joins an external meeting in which they are not the host and the host doesn't enable RTMS, anything reliant exclusively on RTMS will fail" **[Med — Recall.ai analysis]**.
  - Pricing for Meetings isn't public. It's sold through the **Developer Pack** (credits; self-service PAYG, 100- and 500-credit plans since May 2026) **[Med]**. RTMS for Video SDK is listed at $0.01/min ($0.02 with transcription) **[Med]**.
- **Google Meet Media API:**
  - **Developer Preview and "no longer accepting new signups"**.
  - **All conference participants** must be enrolled in the Developer Preview Program.
  - Admin must enable; host can disable mid-call; not available with encryption or watermarks; rejected when underage accounts are present **[High]**.
  - **Not production-usable.** For post-meeting artifacts, Google points to the **Meet REST API** **[High]**.

### D.7 Consent design for US all-party-consent states and India (product default)

- **US:** federal law (ECPA) is **one-party consent**. A dozen or so states require **all-party consent**: the DMLP list names **CA, CT, FL, IL (statute partly struck down 2014), MD, MA (bars "secret" recording), MT, NH, PA, WA**; MI, NV and OR (in person) are often added **[Med — confirm with legal track]**.
  - Participants in one meeting often span states, so **design to the strictest rule: notice to everyone, plus a way to object.**
  - **Litigation signal:** *In re Otter.AI Privacy Litigation* (N.D. Cal., 5:25-cv-06911). Plaintiffs argue that Otter's "make sure you have the necessary permissions" consent model fails in all-party states. Motion-to-dismiss hearing set for 20 May 2026; **outcome not verified** **[Med]**.
- **India:** the **DPDP Act 2023** uses a notice-and-consent model, with "legitimate uses" including employment-related processing. Rules are phased: initial provisions **13 Nov 2025**, more **13 Nov 2026**, remaining **13 May 2027**. Penalties up to **₹250 crore** **[Med — Wikipedia summary; legal track to confirm]**. External participants (clients, vendors) aren't our customer's employees, so treat them as needing notice and consent.

**Recommended default policy (meets the strictest rule we know of):**

| Scenario | Default | Mechanism | Why |
|---|---|---|---|
| In-tenant Teams meetings and calls | **On, for enrolled users** (tenant admin opt-in) | **Teams native transcription + Graph pull** (auto-transcribe on meetings our users organize) | Microsoft's own "transcription has started" notice reaches every participant. No bot, no desktop install, $0 API cost |
| In-tenant meetings where transcription is off | Off | Prompt the organizer to enable transcription; or user-initiated desktop capture with disclosure (below) | Never capture silently |
| **Meetings hosted by other companies** (Teams/Zoom/Meet/Webex) | **Off; tenant admin can enable** | **User-initiated desktop capture** with (1) an auto-posted disclosure in meeting chat where possible, or a one-tap spoken or pasted script; (2) an on-screen indicator; (3) one-click stop and delete; (4) a disclosure audit log | Works for any host. Consent burden handled explicitly. Avoids Teams bot blocking |
| Third-party bot | Off; optional per-tenant | Recall.ai bot named "<User>'s PersonaAgent notetaker (recording)", with join message | Host sees and admits it, but it's increasingly blocked |
| Personal or non-work audio | **Never** (work-only scope) | Allow-list of meeting apps, calendar-linked sessions only | Founder decision #4 |

## E. Our own web app — what to build and what not to

### E.1 Should we rebuild Outlook and Teams with an identical UI? Clear answer: **no**

| Criterion | Full-client strategy (our own inbox/chat UI) | In-place strategy (add-in + Graph drafts + Teams agent + companion) |
|---|---|---|
| Who does it | **Superhuman** (own mail client; also Auto Drafts "in your voice"), **Shortwave**, **Spark**. All built over years for prosumers and teams | **Fyxer** (drafts appear in your existing inbox), **Grammarly / Superhuman Go** (overlay "works where you do"), **Microsoft Copilot** (native) |
| Adoption in M365 enterprises | Low. Users must abandon Outlook and Teams, which are mandated, trained-on and integrated with calendars, shared mailboxes, delegates, sensitivity labels, DLP, S/MIME/IRM, retention and eDiscovery | High. Nothing changes in the user's workflow. IT deploys centrally (Integrated Apps / Intune) |
| Effort | **Estimate: 6–12+ engineer-months** for a credible mail *and* chat client (HTML email rendering and sanitization, threading, attachments, search, offline, mobile, Teams chat semantics); years to reach parity | **Estimate: ~22–30 engineer-weeks** for the MVP surfaces in this report |
| Security and data exposure | We must store and serve **full message content and attachments** for display. That's a bigger breach blast radius, an XSS surface from rendering arbitrary HTML, and IRM/Purview-protected mail we may not be able to render | We store what the persona and memory need (redacted per the security track) and **deep-link back** to Outlook/Teams for the source |
| Microsoft UI churn | We'd re-implement a moving target (new Outlook, new Teams) while users compare us to it daily | Microsoft owns the UI. We ride stable extension points (Office.js requirement sets, Teams app model, Graph v1.0) |
| Competitive dynamics | Head-on competition with Outlook/Teams **and** Copilot | Complements Copilot ("the voice and memory layer"), and can even appear *inside* Copilot Chat as a custom engine agent |

**Recommendation:** the web app is the **control center and memory surface, not a mailbox**. Where users need to see a message (evidence for a persona rule, the email a draft answers), show a **minimal, redacted snippet with an "Open in Outlook/Teams" deep link** (the Graph message `webLink`, Teams message deep links).

### E.2 What the web app should contain (MVP → later)

| Area | MVP contents | Later |
|---|---|---|
| **Onboarding and consent** | Entra sign-in (multi-tenant app); **admin-consent wizard**; checklist: deploy add-in + Teams app in Integrated Apps, **turn on Teams "Transcript API access" + speaker attribution**, create the **application access policy**, choose capture policy (external meetings on/off); per-user consent screens in plain language; data-region choice (**US / India**) | SCIM provisioning, SSO-group mapping |
| **Persona studio** | Learned personas per audience (manager/senior, report/junior, peer, external client, vendor) with **evidence snippets**; sliders (formality, length, warmth); phrase do/don't lists; exclude contacts, threads or domains from learning; **test bench** ("draft a reply to this as me") | Per-language personas (English/Hindi), A/B feedback analytics |
| **Drafts queue** | List of "needs reply" threads with ready drafts, each with **Open in Outlook**; on/off per user; quality feedback (thumbs, edit distance) | Follow-up nudges, delegation tracking |
| **Memory timeline and search** | Day timeline of meetings, calls and phone captures; ask questions ("client requirements in the 4 pm meeting?") with cited transcript spans; speaker-labeled transcripts; action items | Cross-source entity graph (people, projects) |
| **Recordings** | Playback (redacted), retention countdown, delete | Clip sharing with access control |
| **Privacy center** | Mute schedules, app/contact/domain exclusions, **one-click delete / export (DSAR/DPDP rights)**, disclosure log for captured meetings | Per-meeting participant objection workflow |
| **Tenant admin console** | User enrollment, surface toggles (drafts, add-in, recorder, external capture), retention, audit log, usage and billing | DLP/sensitivity-label integration, SIEM export |
| **Platform super-admin** | Tenant lifecycle, health, feature flags, sub-processor registry, **JIT-approved, audited support access** (no standing access to customer content) | Regional cell management |

The web app should also be embedded as a **Teams personal-app tab** (same React build), so users reach it without leaving Teams.

## Matrix 1 — Integration surfaces

Effort is in **engineer-weeks (ew), my estimate** for a competent full-stack TypeScript team that reuses the shared backend (ingestion, persona engine, Bedrock AgentCore agent). Effort covers the surface itself, not the persona or memory core.

| # | Surface | Key capability | Clients reached | Effort (ew, est.) | Phase | Main dependency / risk |
|---|---|---|---|---|---|---|
| 1 | **Web control center** (onboarding/consent wizard, persona studio, drafts queue, memory timeline/search, privacy center, tenant admin, super-admin) | Control + memory | Browser; Teams tab | 8–12 total (integration-specific: onboarding wizard + drafts queue + meeting views ≈ 5–7) | **MVP** | Shared with other tracks |
| 2 | **Outlook add-in** (XML manifest; task pane + function command; NAA; read thread, recipients, compose type; insert at cursor/replace selection) | Interactive drafting in compose | New Outlook, classic Outlook, OWA, Mac (not mobile compose) | 4–6 | **MVP** | Admin deployment; cross-client QA |
| 3 | Outlook event-based handlers (`OnNewMessageCompose` pre-warm, `OnMessageRecipientsChanged` persona switch) | Zero-click context | Same + mobile (limited) | 1–2 | MVP-stretch | Admin deployment required; 300 s limit |
| 4 | Smart Alerts tone/PII check on send | Guardrail | Win, OWA, Mac | 1–2 | Phase 2 | `block` mode not allowed in Marketplace |
| 5 | **Graph server-side drafts** (triage → `createReply` → update; stale-draft cleanup; per-user toggle) | Proactive drafts | **Every Outlook client incl. iOS/Android** | 3–4 | **MVP** | `Mail.ReadWrite` consent; draft clutter |
| 6 | **Teams personal agent** (Agents SDK / Teams SDK, hosted on AWS) | Chat: draft on request, memory Q&A | Teams desktop, web, mobile | 3–4 | **MVP** | Azure Bot registration; 5 s invoke budget |
| 7 | **Teams message action "Draft reply"** + dialog (Copy / Open chat with prefilled text / Send-as-me) | In-context drafting | Teams desktop, web (mobile: dialogs supported **[Med]**) | 2–3 | **MVP** | No plain-text compose-box API; deep-link prefill to be validated |
| 8 | Teams compose-box ME "Compose in my voice" | New messages | Teams; Outlook (compose context; action MEs in Outlook are preview) | ~1 | MVP | Inserts cards only, so output goes to the clipboard |
| 9 | Teams meeting side panel (pre-brief, disclosure banner, live notes) | Meeting UX | Teams desktop/web | 2–3 | Phase 2 | RSC consent by organizer |
| 10 | Copilot Chat exposure (same custom engine agent; Microsoft 365 channel) | Discovery in Copilot | Copilot Chat (no Copilot license needed) | 1–2 | Phase 2 | Marketplace/agent policies |
| 11 | Unified-manifest bundle (add-in + Teams app + agent) | One-click admin deploy | Win/OWA (not Mac/mobile) | 1–2 | Phase 2 | Keep XML twin for Mac/mobile |
| 12 | Marketplace listings + Publisher Attestation (+ Microsoft 365 Certification later) | Self-serve discovery, trust | — | 2–4 ew + 2–6 calendar weeks | Phase 2 | Review cycles; mobile no-upsell rules |
| 13 | **Windows companion: write-anywhere** (hotkey, UIA read, clipboard insert, overlay; MSIX/Intune; Artifact Signing; auto-update) | Teams compose box, Slack, browsers, any app | Windows 10/11 desktops | 6–10 | Phase 2 | EDR/DLP scrutiny; VDI |
| 14 | **Windows companion: bot-free recorder** | Any meeting incl. external orgs | Windows desktops | In-house 6–8; **via Recall Desktop SDK 2–4** | Phase 2 (MVP-stretch if design partners need external capture) | Consent UX; Recall as sub-processor |
| 15 | Mac companion (AX API, Core Audio taps) | Same as 13–14 on Mac | macOS 13/14.2+ | 6–10 | Phase 3 | TCC permissions |
| 16 | Local **MCP server on Windows** (ODR) | Persona as a tool for other agents | Windows (prerelease feature) | 1–2 (after #13) | Phase 3 | Platform still prerelease |
| 17 | Copilot connector (push memories to M365 index) | Copilot grounding | Copilot users | 2–3 | Phase 3, opt-in | Data-exposure increase |
| 18 | ~~Full mail + chat client clone~~ | — | — | 26–52+ | **Not recommended** | See E.1 |

## Matrix 2 — Meeting-capture options

Legend: ✅ works, ⚠ conditional, ❌ no. "Ext. org" = meeting organized by **another company**. Costs exclude our own LLM/STT processing unless stated.

| Option | In-tenant scheduled | In-tenant ad hoc / PSTN | Channel mtgs | **Ext. org (Teams)** | Zoom / Meet / other | Latency | Cost per meeting-hour | Consent / compliance posture | Effort (ew, est.) | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **Graph post-meeting transcripts/recordings** (Teams native transcription) | ✅ | ✅ (`adhocCalls`, partly beta) | ⚠ beta; no private channels | ❌ | ❌ | After meeting end; minutes **(est.)** | **$0** (unmetered since 25 Aug 2025) | **Best:** Microsoft notifies participants; needs admin consent, app access policy, **Transcript API toggle (default OFF)** | 2–3 | **MVP default** |
| Graph per-meeting RSC (app added to meeting) | ✅ (where added) | ❌ | ❌ | ❌ | ❌ | Same | $0 | Organizer/presenter consents; no tenant-wide admin consent; Transcript API toggle still applies | +1 | MVP option for bottom-up pilots |
| Meeting AI Insights (`aiInsights`) | ✅ (Copilot-licensed users) | ❌ | ❌ | ❌ | ❌ | Up to 4 h | $0 incremental (requires Copilot license) | Same as Graph | 1 | Optional enrichment |
| Graph real-time media bot | ✅ | ✅ | ✅ | ⚠ unverified | ❌ | Real time | Azure Windows VMs + ops **(unpriced)** | Visible bot; Azure-only, .NET | 12+ | ❌ Not for us |
| Certified compliance recording partner | ✅ (policy users) | ✅ | ✅ | ⚠ user's own leg **[Low]** | ❌ | Near real time | Partner pricing (unverified) | Regulated-industry grade | Partnership | Phase 3+ |
| **Recall.ai meeting bot** | ✅ | ⚠ (join needed) | ✅ | ⚠ **if admitted; Teams now labels/blocks bots** | ✅ Zoom, Meet, Webex, GoTo, Slack | Real-time stream; artifacts minutes after | **$0.50 + $0.15 STT = $0.65** (startup: $0.25 + $0.15 = $0.40) | Visible named bot + join message; lobby | 1–2 | Phase 2 optional |
| Self-built bots (Attendee OSS / browser automation) | ✅ | ⚠ | ✅ | ⚠ same headwinds | ✅ | Real time | Infra only, plus **high maintenance** (Teams DOM changes) | Same as bots | 8–12 + ongoing | ❌ for a 3–6-person team |
| **Desktop capture, in-house** (mic + WASAPI process loopback) | ✅ | ✅ | ✅ | ✅ | ✅ any app incl. Slack huddles, WhatsApp, softphones | Real time | **$0** infra (+ STT) | **We** must give notice (no platform banner) | 6–8 | Phase 2 |
| **Desktop capture via Recall Desktop SDK** | ✅ (Teams desktop) | ✅ | ✅ | ✅ | ✅ Zoom desktop; Meet in Chrome/Edge; ad hoc mode for others | Real-time transcript events | **$0.50 (+$0.15 STT)** | Same as above; audio goes to Recall cloud (US/EU/JP regions) | 2–4 | Phase 2 / MVP-stretch |
| Zoom RTMS | — | — | — | — | ⚠ Zoom only, **if host's org enabled it and host approves** | Real time | Not public (Developer Pack credits) | Zoom shows app access to participants | 3–4 | Phase 3 |
| Google Meet Media API | — | — | — | — | ❌ Preview, no new signups, all participants must be enrolled | — | — | — | — | ❌ |
| Phone app (Pillar 2) on speaker / in room | ⚠ | ⚠ | ⚠ | ✅ (acoustic) | ✅ (acoustic) | Near real time | STT only | Same notice rules (in-person) | Other track | Complement |

**For consulting and sales users meeting other companies:** only **desktop capture** (ours or Recall's SDK) and **the phone app** work regardless of the host's settings. Bots work only when the host admits them, and that's getting harder. Zoom RTMS works only if the host's org enables it. Graph never works for other tenants' meetings.

## Recommendations for PersonaAgent (MVP plan)

### The direct answer to the founders' question

> *"Do we create a frontend/backend showing all emails and Teams messages with an identical UI, and also have a deployed agent, and also integrate in Teams and Outlook, or directly in Windows?"*

- **No identical-UI clone.** It's costly, slows enterprise adoption, increases data exposure, and pits us against Microsoft's UI.
- **Yes to a deployed agent:** one custom engine agent on Bedrock AgentCore behind the Microsoft 365 Agents SDK. It serves Teams chat now and Copilot Chat later.
- **Yes to Outlook and Teams integration *in place*** in the MVP: add-in, Graph drafts, Teams agent and message action.
- **Windows-native comes in Phase 2,** as a companion for write-anywhere and bot-free capture of external meetings. It isn't the primary surface.
- **Our web app is the control center and memory UI**, embedded in Teams as a tab.

### MVP scope (≈12 weeks, 3–6 engineers)

Integration-track budget **≈ 22–30 engineer-weeks (estimate)**, including about 20% contingency. The remaining capacity goes to ingestion, persona and memory, redaction, the phone app and infrastructure (other tracks).

| Weeks | Workstream | Deliverable | ew (est.) |
|---|---|---|---|
| 1–2 | **De-risking spikes** | (a) Teams `openChat`/deep-link `message` prefill in **existing** chats; (b) add-in insert/read behavior on new Outlook, classic, OWA and Mac, including `bodyMode` thread handling; (c) Graph transcript pipeline in a test tenant with **Transcript API access + speaker attribution ON/OFF**; (d) `createReply` draft visibility on iOS/Android Outlook; (e) consent copy reviewed with the legal track (US all-party + DPDP) | 3 |
| 2–7 | **Outlook add-in** (XML manifest, NAA, task pane + one-click function command; audience chip; rewrite selection; new-message drafting) | Admin-deployable LOB add-in | 5 |
| 3–7 | **Graph server-side drafts** (needs-reply triage, `createReply`, persona selection by recipient relationship, stale-draft cleanup, per-user toggle) | Drafts visible in every Outlook client, incl. mobile | 3.5 |
| 3–8 | **Teams agent + message action + compose ME** (Agents SDK on AWS; dialog with Copy / Open-chat-prefilled / explicit Send-as-me) | Teams app package (LOB upload) | 5 |
| 4–8 | **Teams transcript ingestion** (tenant- or user-scoped subscriptions with lifecycle renewal, adhocCalls, VTT parsing, calendar join, meeting-memory objects; auto-transcribe on meetings organized by enrolled users) | In-tenant meeting memory | 2.5 |
| 2–9 | **Onboarding and admin wizard + drafts queue + meeting views** in the web control center | Self-serve tenant setup | 4 |
| 9–12 | **Pilot hardening** with 1–2 design partners (one US, one India): security questionnaire pack (permission justifications, data flow, sub-processors), admin runbook, telemetry on draft acceptance and edit distance | Pilot-ready | 2–4 |

**MVP-stretch (only if design partners demand external-meeting capture):** a minimal Electron recorder built on the **Recall Desktop Recording SDK** (+3–4 ew), with mandatory disclosure UX. External capture is OFF by default per tenant. Founders must first accept Recall as a sub-processor; its regions are US/EU/JP, not India.

### Tenant-admin onboarding checklist (what our wizard must automate or explain)

1. Admin-consent our multi-tenant Entra app (Graph scopes per the Graph-permissions track: mail and chat read, `Mail.ReadWrite` for drafts, `OnlineMeetingTranscript.Read.All` / `CallTranscripts.Read.All` for meetings).
2. Create and grant the **Teams application access policy** for enrolled users (needed for application-permission meeting APIs).
3. Turn on **Teams admin center → Meetings → Meeting settings → Transcript API access** (Graph access **and** speaker attribution).
4. Make sure meeting policies allow transcription; optionally enable auto-transcription for enrolled organizers.
5. Deploy the Outlook add-in and Teams app from **Integrated apps** to a top-level pilot group.
6. Choose PersonaAgent capture policies: drafts on/off, external-meeting capture off/on, retention, data region (US/India).

### Phase 2 (months 4–6)

- **Windows companion** (Electron; write-anywhere via UIA and clipboard; bot-free recorder, in-house or Recall SDK; MSIX via Intune; Artifact Signing).
- **Copilot Chat exposure** of the same agent, plus the **unified-manifest bundle**.
- **Marketplace listings** with Publisher Attestation.
- Teams meeting side panel (pre-brief plus disclosure).
- Smart Alerts tone/PII guard.
- Optional Recall.ai bot for hosts that welcome notetakers.

### Phase 3 (6–12 months)

Mac companion, local MCP server (Windows ODR), Zoom RTMS for Zoom-heavy customers, Copilot connector (opt-in), certified compliance-recording partnership for regulated customers, US GCC (note: Integrated Apps isn't available in government clouds), in-house capture to replace Recall if India residency demands it.

### Architecture notes for engineers

- **One backend, many thin surfaces.** Every surface calls the same `draft` and `ask` APIs on AgentCore with a **context envelope**:
  - surface (outlook-addin, graph-draft, teams-action, desktop);
  - thread IDs (`conversationId` / `inReplyTo` / Teams chat and message IDs);
  - recipients plus relationship labels;
  - user instruction;
  - selection text.
- **Never let a surface send on its own.** Drafts, prefills and clipboard only. "Send-as-me" is an explicit, previewed click.
- **Close the learning loop.** When the user sends (Graph sent-items ingestion), diff the final text against our draft; store edit distance and accepted spans to tune the persona.
- **Graph subscriptions are infrastructure.** Run a renewal service with lifecycle notifications. Transcript subscriptions must exist *before* transcription starts, so create them at user enrollment (user-scoped) or tenant enrollment (tenant-scoped).

## Risks & watch-outs

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| 1 | **Teams Transcript API access defaults OFF** (late Jul 2026), and speaker attribution defaults OFF, so meeting memory silently returns nothing or loses speaker names | High / High | Onboarding wizard with a live health check (call the API, detect `GraphAccessToTranscriptsDisabled` / `SpeakerAttributionNotAllowed`), admin email templates, an unattributed-format fallback |
| 2 | **Bots blocked or stuck in lobbies** (MC1251206 detection on by default; `BlockDetectedBots` from Aug 2026); hosts at other companies reject notetakers | High / Med | Don't make bots the primary capture path. Use desktop capture plus explicit disclosure for external meetings |
| 3 | **Consent liability** in US all-party-consent states and under India's DPDP (obligations phasing in to May 2027); class actions against notetakers (*In re Otter.AI*) | Med / High | Never capture silently; auto-disclosure; external capture off by default and admin-controlled; deletion on objection; disclosure audit log; legal review of copy |
| 4 | **Admin-consent friction** for broad scopes (`Mail.ReadWrite`, `OnlineMeetingTranscript.Read.All` + access policy) | High / Med | Tiered consent: start with read plus add-in (NAA, delegated), add drafts and meetings as separate toggles; publish a permissions-justification doc; offer the RSC per-meeting path for bottom-up pilots |
| 5 | **No compose-box API in Teams.** Drafting UX may feel clunky (card / copy / prefill) | High / Med | Validate deep-link prefill in week 1; polish the copy-paste flow; the Phase 2 companion pastes directly |
| 6 | **Outlook mobile can't run compose add-ins** | Certain / Med | Graph server-side drafts |
| 7 | **Microsoft ships "write in my style" in Copilot for Outlook/Teams** (status unverified) | Med / High | Differentiate on cross-surface persona (email + Teams + meetings + phone memory), per-audience personas, and working **without** Copilot licenses; integrate *with* Copilot as an agent |
| 8 | **Beta APIs** (channel meetings, ad hoc/PSTN artifacts) change or break | Med / Med | Feature-flag beta paths; v1.0-only for the GA promise |
| 9 | **Real-time media requires Azure/Windows** if a customer insists on real-time in-tenant capture without installs | Low / Med | Desktop capture; or a later dedicated Azure micro-deployment just for media (exception to the AWS-only rule) |
| 10 | **Desktop companion flagged by EDR/DLP** (keystroke injection, clipboard, accessibility hooks resemble malware behavior) | Med / Med | Sign with Artifact Signing; MSIX via Intune; publish a security whitepaper; least privilege (no `uiAccess` unless required); per-app allow-lists |
| 11 | **Draft clutter and mailbox-record implications** of server-side drafts (eDiscovery, retention, legal hold) | Med / Low–Med | Draft only high-confidence threads; auto-delete stale drafts; label drafts; respect sensitivity labels |
| 12 | **Sub-processor and residency for India** (Recall regions US/EU/JP) | Med / Med | Keep Recall optional; plan in-house capture with storage in an AWS India region; confirm with the legal and data-layer tracks |
| 13 | **Microsoft platform churn**: Phi Silica → Aion Instruct (Jan 2027), Bot Framework archived, manifest and requirement-set evolution, new Outlook transition (Mar 2027) | Certain / Low–Med | Build on GA, documented extension points; avoid Phi Silica; track Microsoft 365 Message Center and Teams developer announcements monthly |
| 14 | **Marketplace certification delays** and mobile no-upsell policy | Med / Low (enterprise pilots use LOB upload) | Start Partner Center onboarding in Phase 2; keep the mobile listing free of commerce UI |
| 15 | **US public sector (GCC)**: Integrated Apps portal not available in government clouds | Low (not v1) / Med | Defer GCC; plan the Teams admin center and Exchange admin center deployment paths later |

## Open questions / could not verify

The session's web-search budget ran out partway through. The items below were **not verified** against a primary source, or need a hands-on prototype.

**Needs a prototype (week 1–2 spikes)**
1. Does the Teams deep link / TeamsJS `openChat`/`openGroupChat` `message` prefill text into the compose box of an **existing** chat, on desktop, web and mobile? Docs only guarantee it for new chats in draft state.
2. Do Graph `createReply` drafts appear inside the conversation (not just in Drafts) on Outlook iOS/Android, new Outlook and classic? (Expected yes; untested.)
3. Real-world **latency** from meeting end to transcript-available notification, and its variance (no Microsoft SLA found).
4. Transcript-API coverage of **Meet Now** sessions and **1:1 calls** where the *other* party started transcription.
5. Behavior of add-in `body.getAsync(FullBody)` vs `HostConfig` on long threads in new Outlook (size, quoted-history fidelity).

**Couldn't verify (treat as unknown)**
6. Exact **enforcement date** of the Teams Transcript API admin gate (29 Jul 2026 per secondary sources) and whether existing tenants were defaulted OFF or grandfathered. Microsoft's doc states "By default, Microsoft Graph access is off."
7. Whether **Copilot in Outlook/Teams now drafts in the user's personal writing style** (a competitive threat).
8. **Integrated Apps propagation time** and **Marketplace review durations** (estimates given).
9. **Artifact Signing** dollar prices (SKU quotas verified, prices not rendered), and Azure Bot Service pricing for the Teams channel (page fetch failed).
10. Whether **external bots registered in *our* tenant** are excluded from Teams bot detection when joining *customer* meetings. Secondary sources say bots registered in the *host's* tenant are excluded, which wouldn't cover us.
11. Whether a Graph real-time media bot can join meetings hosted in **other tenants**, and under which policies.
12. Requirements for in-meeting app **RTMP live streaming** (`requestStartLiveStreaming`): organizer-only? `LiveStreamingMode` policy? Participant indicator?
13. **Zoom RTMS pricing** for Zoom Meetings (only Video SDK RTMS pricing found: $0.01–$0.02/min).
14. Recall.ai **India data residency**; Attendee hosted pricing; MeetStream and Nylas Notetaker pricing.
15. Grammarly-for-Windows internals (UIA vs other hooks); the Grammarly ↔ Superhuman corporate relationship and dates.
16. Windows ML GA date; Recall, Click to Do and App Actions current enterprise defaults (from memory only).
17. Third-party onboarding path into **Agent 365** (Entra Agent ID registration for ISV custom engine agents).
18. **Legal (owned by the legal track):** the definitive US all-party-consent state list, and India-specific rules on recording calls between private parties beyond DPDP. Nothing here is legal advice.
19. Mailbox 1.15 feature list was read from a mirror of the Microsoft Learn page; the `getSelectedDataAsync` requirement set (1.2) is from memory.

## Sources

All URLs were accessed 2026-10-05/06 unless noted. P = primary, S = secondary.

**Outlook add-ins / Office.js**
- P: Mailbox requirement set 1.16 GA — https://devblogs.microsoft.com/microsoft365dev/mailbox-requirement-set-1-16-now-available-for-outlook-add-ins/
- P (mirror of Learn): Mailbox requirement set 1.15 — https://star-hk2.eastasia.cloudapp.azure.com/en-us/javascript/api/requirement-sets/outlook/outlook-requirement-set-1-15
- P: Event-based activation (events, clients, limits, deployment) — https://learn.microsoft.com/office/dev/add-ins/develop/event-based-activation
- P: Outlook APIs supported on mobile — https://learn.microsoft.com/en-us/office/dev/add-ins/outlook/outlook-mobile-apis
- P: Add-ins for Outlook on mobile devices — https://learn.microsoft.com/en-us/office/dev/add-ins/outlook/outlook-mobile-addins
- P: Unified manifest overview (client support) — https://learn.microsoft.com/en-us/office/dev/add-ins/develop/unified-manifest-overview
- P: Office.MessageCompose (conversationId, inReplyTo) — https://learn.microsoft.com/javascript/api/outlook/office.messagecompose
- P: Office.Body (getAsync/setAsync/setSelectedDataAsync/prependAsync, bodyMode) — https://learn.microsoft.com/en-us/javascript/api/outlook/office.body
- P: Nested app authentication — https://learn.microsoft.com/en-us/office/dev/add-ins/develop/enable-nested-app-authentication-in-your-add-in
- P: Integrated apps portal — https://learn.microsoft.com/en-us/microsoft-365/admin/manage/test-and-deploy-microsoft-365-apps
- P: Microsoft Marketplace certification policies (1120 Office add-ins, 1140 Teams/Copilot) — https://learn.microsoft.com/en-us/legal/marketplace/certification-policies
- S: Legacy Exchange token deprecation timeline — https://helpdesk.symprex.com/signature-365/nested-app-authentication-naa-and-deprecation-of-exchange-legacy-tokens ; https://office365itpros.com/tag/naa/ ; P (2024 update) https://devblogs.microsoft.com/microsoft365dev/updates-on-deprecating-legacy-exchange-online-tokens-for-outlook-add-ins/
- S: New Outlook opt-out moved to March 2027 (MC949965) — https://kurtsh.com/2026/03/03/info-opt-out-transition-phase-from-classic-to-new-outlook-for-windows-beginning-march-2027-m365-commercial-gcc/ ; https://windowsforum.com/threads/microsoft-delays-enterprise-opt-out-for-new-outlook-to-march-2027.404427/
- S: New Outlook WebView2 / no COM-VSTO, classic support to 2029 — https://www.getmailbird.com/microsoft-outlook-add-in-framework-changes/ ; https://www.getmailbird.com/outlook-classic-extended-power-user-transition-guide/
- P: Graph `message: createReply` — https://learn.microsoft.com/en-us/graph/api/message-createreply?view=graph-rest-1.0

**Teams & Copilot extensibility**
- P: Respond to search command (response types) — https://learn.microsoft.com/en-us/microsoftteams/platform/messaging-extensions/how-to/search-commands/respond-to-search
- P: Respond to action command (card insert, botMessagePreview, OnBehalfOf) — https://learn.microsoft.com/en-us/microsoftteams/platform/messaging-extensions/how-to/action-commands/respond-to-task-module-submit
- P: Define action commands (message context payload, More actions) — https://learn.microsoft.com/en-us/microsoftteams/platform/messaging-extensions/how-to/action-commands/define-action-command
- P: Message extensions in Outlook — https://learn.microsoft.com/en-us/microsoftteams/platform/m365-apps/extend-m365-teams-message-extension
- P: Deep link to a Teams chat (message prefill) — https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/deep-link-teams
- P: Resource-specific consent — https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent
- P: TeamsJS `meeting` module (live streaming, speaking state) — https://learn.microsoft.com/en-us/javascript/api/@microsoft/teams-js/meeting
- P: Microsoft 365 Agents SDK overview — https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/agents-sdk-overview
- P: Agents in Teams overview — https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/overview
- P: Bot Framework SDK retirement notice — https://github.com/microsoft/botframework-sdk
- S: Teams SDK rename/GA — https://www.voitanos.io/blog/microsoft-teams-sdk-evolution-2025/
- P: Copilot extensibility licensing & cost — https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/cost-considerations
- P: Publishing routes for Copilot plugins/agents — https://learn.microsoft.com/microsoft-365-copilot/extensibility/publish
- S/P: Agent 365 GA 1 May 2026 — https://techcommunity.microsoft.com/discussions/agent-365-discussions/agent-365-will-be-generally-available-on-may-1-2026/4500380 ; pricing summaries https://samexpert.com/agent-365/

**Meeting capture**
- P: Fetch meeting transcripts & recordings (unmetered from 25 Aug 2025; adhocCalls) — https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/overview-transcripts
- P: Change notifications for transcripts/recordings — https://learn.microsoft.com/en-us/graph/teams-changenotifications-callrecording-and-calltranscript
- P: Get callTranscript (permissions, access policy, formats, admin controls) — https://learn.microsoft.com/en-us/graph/api/calltranscript-get?view=graph-rest-1.0
- P: Manage transcript API access for Teams meetings (default OFF) — https://learn.microsoft.com/en-us/microsoftteams/meeting-transcript-api-access
- S: Enforcement date 29 Jul 2026 — https://o365reports.com/how-to-manage-teams-transcript-api-access-for-meetings/
- P: Meeting AI Insights API — https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/meeting-transcripts/meeting-insights
- P: Application-hosted media bot requirements (Azure/Windows) — https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots
- P: MC1251206 external bot detection — https://mc.merill.net/message/MC1251206
- S: Bot auto-blocking (`ExternalBotAccessMode`, Aug 2026) — https://www.uctoday.com/unified-communications/microsoft-teams-to-block-external-bots-automatically-as-ai-notetaker-crackdown-hardens/ ; https://basilai.app/articles/2026-07-30-microsoft-teams-block-external-ai-bots-august-2026-it-admin-playbook.html
- S: Otter litigation, Zoom/Google bot controls — https://www.uctoday.com/security-compliance-risk/ai-meeting-bots-controls-microsoft-zoom-google/
- P/S: Compliance recording partners — https://microsoftpartners.microsoft.com/abs/Compliance-Recording-Solutions/ ; https://fintech.global/2026/08/24/why-theta-lake-believes-your-firm-needs-a-microsoft-certified-teams-compliance-recorder/
- P: Recall.ai pricing — https://www.recall.ai/pricing ; https://www.recall.ai/blog/new-recall-ai-pricing-for-2026
- P: Recall.ai Desktop SDK — https://docs.recall.ai/docs/desktop-sdk ; https://docs.recall.ai/docs/dsdk-supported-platforms
- P: Recall.ai Teams bots (anonymous vs signed-in) — https://docs.recall.ai/docs/signed-in-teams-bots-overview ; https://docs.recall.ai/docs/microsoft-teams
- P/S: Recall.ai on Teams bot approaches — https://www.recall.ai/blog/how-to-build-a-microsoft-teams-bot ; on Zoom RTMS — https://www.recall.ai/blog/what-is-zoom-rtms
- P: Meeting BaaS pricing — https://www.meetingbaas.com/pricing
- P: Attendee — https://attendee.dev/ ; https://github.com/attendee-labs/attendee
- S: MeetStream pricing — https://www.nylas.com/blog/best-meeting-bot-apis/
- P: Zoom RTMS — https://www.zoom.com/en/realtime-media-streams/ ; https://devforum.zoom.us/t/rtms-self-service-purchasing-is-now-available/144524 ; S: Video SDK RTMS pricing https://trtc.io/blog/details/zoom-video-sdk-pricing-2026
- P: Google Meet Media API overview — https://developers.google.com/workspace/meet/media-api/guides/overview
- P: Granola — https://www.granola.ai/
- P: Fyxer — https://www.fyxer.com/ ; https://www.fyxer.com/pricing

**Windows / desktop**
- P: Windows AI APIs (Phi Silica → Aion Instruct, Speech Recognition, hardware) — https://learn.microsoft.com/en-us/windows/ai/apis/
- P: MCP on Windows (ODR) — https://learn.microsoft.com/en-us/windows/ai/mcp/overview
- P: Artifact Signing overview / FAQ / pricing — https://learn.microsoft.com/en-us/azure/trusted-signing/overview ; https://learn.microsoft.com/en-us/azure/artifact-signing/faq ; https://azure.microsoft.com/en-us/pricing/details/artifact-signing/
- P: WASAPI loopback recording — https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording
- P: Application (process) loopback sample — https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/
- P: Electron desktopCapturer (loopback; macOS 14.2+ Core Audio Tap) — https://www.electronjs.org/docs/latest/api/desktop-capturer
- P: Apple Core Audio taps — https://developer.apple.com/documentation/coreaudio/capturing-system-audio-with-core-audio-taps
- P: Grammarly for Windows — https://www.grammarly.com/desktop/windows ; Superhuman — https://superhuman.com/

**Legal context (for the legal track to confirm)**
- S: US recording-consent overview (all-party states) — https://www.dmlp.org/legal-guide/recording-phone-calls-and-conversations
- S: India DPDP Act 2023 and Rules timeline — https://en.wikipedia.org/wiki/Digital_Personal_Data_Protection_Act,_2023
