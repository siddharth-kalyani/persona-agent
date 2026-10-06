# 01 - Microsoft 365 data access via Microsoft Graph: ingestion, write-back, consent, compliance and platform risk

**Track:** M365 / Microsoft Graph data access (PersonaAgent research series, doc 01)
**Prepared:** 2026-10-05/06 (research cut-off for this doc). All facts were checked against primary sources (Microsoft Learn, Microsoft message-center notices, vendor terms) where a URL is cited. Anything not verified is labelled **[UNVERIFIED]** or **[ESTIMATE]** with reasoning.
**Founder decisions applied:** first buyer = M365 mid-market & enterprise (per seat); v1 regions = United States + India (EU/UK covered briefly); team = 3-6 engineers, ~3-month MVP; recorder = work-only, tenant-governed; Phase-1 redaction tuned to US + Indian regulatory requirements.

**Confidence legend:** **(High)** = read in a current primary source; **(Med)** = primary source but ambiguous/older, or strong secondary source; **(Low)** = inference, forum/secondary source, or test-required.

---

## Executive summary

**The single most important change since 2025: admin consent is now mandatory in practice.**
- Since the Oct-Nov 2025 "Secure by Default" rollout (message center MC1163922, published 2025-10-02), the **Microsoft-managed default user-consent policy** (the default for new tenants, and applied to tenants using the Microsoft-managed setting) **blocks end-user consent for Mail.Read, Mail.ReadBasic, Mail.ReadWrite, Mail.Read.Shared, Calendars.\*, Chat.Read, Chat.ReadWrite, OnlineMeetings.\*, MailboxSettings.\*, People.Read**, Files/Sites.\*, Contacts/Tasks write and EWS/EAS/IMAP/POP. Existing grants keep working. **(High)** Combined with the long-standing enterprise habit of disabling user consent, PersonaAgent cannot rely on bottom-up self-sign-up: **every customer tenant will need a tenant admin to grant consent**. Design the sales motion, onboarding UX and security pack around the IT/security buyer from day 1.
- **Teams APIs are free again.** Microsoft stopped metering Teams export (`getAllMessages`, `getAllRetainedMessages`), Teams change notifications, transcripts and recordings on **2025-08-25** (MC1122144); the `model=A/B` parameter is ignored. Remaining paid/licensed exceptions: Meeting AI Insights API (needs a Microsoft 365 Copilot licence) and DLP `PATCH policyViolation` (needs a Communications DLP plan). **(High)** The separate "protected API" request-form page now returns 404 and the export docs no longer mention a form; treat the form as probably retired but **test** before relying on it **(Low-Med)**.
- **EWS is dead for us.** Exchange Web Services in Exchange Online is **disabled by default from 2026-10-01** (admins can temporarily re-enable with `EWSEnabled=True` + an AppID allow-list) and **permanently shut off on 2027-04-01** (MC1227454). Build Graph-only. **(High)**

**Ingestion is technically very feasible; the bottlenecks are consent, trust and Teams throttling - not Outlook.**
- Outlook: read Sent Items with `GET /me/mailFolders('sentitems')/messages/delta` (supports `$select`, `$top`, `$expand`, `Prefer: odata.maxpagesize`; deletes/moves come back as `@removed`). Limits are **per app per mailbox: 10,000 requests / 10 min, 4 concurrent requests, 150 MB upload / 5 min**; `$batch` = max 20 sub-requests, Outlook executes 4 at a time. **(High)** A 50k-message sent-items backfill is **~10-60 minutes per mailbox [ESTIMATE]**, and mailboxes are throttled independently, so tenant-wide mail backfill parallelises well.
- Thread/reply detection: use `uniqueBody` (new text only, `$select` required) for style learning and `body` (with quoted history) for context; classify new-thread vs reply/forward with **`conversationIndex` length (22-byte header, +5 bytes per reply/forward)**, MAPI `PidTagInReplyToId` (0x1042) / `PidTagInternetReferences` (0x1039) via extended properties, and subject prefixes. **(High for structure, Med for edge cases)**
- Teams: delegated `Chat.Read` lets us list the user's chats and read `/chats/{id}/messages` (max `$top`=50; filter/order on `lastModifiedDateTime`). Teams read throttles are **per app per tenant: 20 requests/s for chat-message GETs and 1 request/s per chat** - so a 100k-message user is minutes, but **a 1,000-user tenant backfill via delegated reads is ~1.5-3 days [ESTIMATE]**. The app-only export API (`/users/{id}/chats/getAllMessages`, `Chat.Read.All`, 200 requests/s per tenant, filter by sender) cuts that to hours but requires the most sensitive Teams permission. **(High for limits)**
- Real-time: delegated subscriptions to `/users/{id}/chats/getAllMessages` (Chat.Read) and Outlook message subscriptions are available, but Teams has a **hard org-wide quota of 10,000 Teams subscriptions shared by all apps** and **10 per user**; Outlook allows 1,000 subscriptions per mailbox for all apps. Teams subscriptions last up to 3 days (needs a lifecycle URL beyond 1 hour); Outlook up to ~7 days (1 day with resource data). **(High)**

**Write-back: drafts, not autonomous sends.**
- Outlook: `createReply` / `createReplyAll` / `createForward` / `POST /me/messages` create in-thread drafts (needs `Mail.ReadWrite`); sending needs `Mail.Send`. Teams has **no draft API**: posting as the user needs delegated `ChatMessage.Send` (app-only posting is only allowed for migration via `Teamwork.Migrate.All`), and `replyWithQuote` (v1.0) gives in-thread quoting. **(High)** For the MVP, insert text into the compose box via the Outlook add-in / Teams message extension (neighbouring track) so the **backend stays read-only** - this is the single best lever for security-review approval.

**Compliance and terms.**
- Microsoft APIs Terms of Use (updated Oct 2025): no clause bans AI training, but they **prohibit copying data "except as necessary to enable an intended usage scenario"**, require minimum data/permissions, require you to keep copies in sync (corrections/deletions) and delete on abandonment/termination, and - critically - **restrict use of the email APIs to sync/backup unless the customer has "expressly and specifically" granted other use permissions**. Put that permission in the customer contract and admin-consent flow. Microsoft may change, charge for or terminate API access at any time. **(High)**
- Purview: labelled email carries an `MSIP_Labels` header readable via `internetMessageHeaders` (label GUID/name) **(High for format; Med for availability on Sent-Items copies)**; Teams messages carry `policyViolation` (DLP) but no per-message sensitivity label. Microsoft now offers **Purview `processContent` (Graph v1.0, `Content.Process.User`)** so a third-party AI app can submit content/prompts/responses for the tenant's DLP evaluation and audit - a strong enterprise-trust feature. **(High that it exists; Med on behaviour/cost)**
- Data residency: tenants whose default geography is **India or the United States** get Microsoft Product-Terms commitments that Exchange mailbox content and Teams chat messages stay **at rest in-country**; India (not the US) can also buy Advanced Data Residency. Our AWS copies are outside those commitments, so **pin each tenant to an in-geo AWS region (India -> ap-south-1, US -> us-east-1) including LLM inference**. **(High for Microsoft facts)**

**Platform risk.**
- Microsoft's own stack is converging on our space: **Microsoft Agent 365 went GA on 2026-05-01** (per-user licence; included in Microsoft 365 E7; can auto-surface Amazon Bedrock and Google Vertex agents in the M365 admin center) and **Entra Agent ID** gives agents first-class identities. Copilot APIs (Retrieval, Chat, Meeting Insights) **require Microsoft 365 Copilot licences** and the Retrieval API does **not** cover mail or Teams, so they are not a substitute for Graph ingestion. **(High)**
- Expansion: **Slack's API Terms (effective 2025-10-10) forbid using API data to train an LLM and forbid persistent copies/indexes of other organisations' data**, and non-Marketplace apps installed since 2025-05-29 get 1 request/min (15 messages) on `conversations.history`. Slack is effectively closed to a persistent persona-memory design. Gmail is feasible but needs Google's CASA assessment for restricted scopes and allows per-user personalised models only. **(High)**

**MVP permission set (delegated only, read-only):** `openid profile email offline_access User.Read` + `Mail.Read` + `Chat.Read` + `User.ReadBasic.All` (+ optional `User.Read.All` for manager/title). No application permissions, no write scopes, admin-consented and scoped to a pilot group via "assignment required". Details in the blueprint section.

---

## Contents
- A. Outlook mail (sent items): read, thread context, throttling, bulk options, write-back
- B. Microsoft Teams messages: read, licensing, change notifications, send, throttling
- C. Organisational context (senior / junior / peer / external) and calendar
- D. Consent, app registration, publisher trust, certification, tokens, security-review objections
- E. Compliance and data governance in the customer tenant (labels, SITs for US/India, DLP, retention, eDiscovery, residency, API terms)
- F. Platform risk and Microsoft roadmap (EWS, Copilot APIs, Agent 365, Entra Agent ID)
- G. Google Workspace and Slack (for later expansion)
- H. Ingestion and write-back blueprint (permissions, call sequences, estimates, hard blockers)
- Recommendations for PersonaAgent
- Risks and watch-outs
- Open questions / could not verify
- Sources

---

## A. Outlook mail (sent items)

### A1. Endpoints for reading all sent mail

| Need | Call | Notes |
|---|---|---|
| Initial + incremental sync of Sent Items | `GET /me/mailFolders('sentitems')/messages/delta` (delegated) or `/users/{id}/mailFolders('sentitems')/messages/delta` (app-only) | Supports `$select`, `$top`, `$expand`; `$filter` only `receivedDateTime ge/gt {value}`; `$orderby` only `receivedDateTime desc`; no `$search`. Page size via `Prefer: odata.maxpagesize={n}`. Returns `@odata.nextLink` (skipToken) until done, then `@odata.deltaLink` (deltaToken) to store. Optional `changeType=created|updated|deleted`. **(High)** |
| Deletions / moves | Same delta round | Deleted or moved-out items arrive as `@removed: {"reason":"deleted"}`; read/unread changes also surface even if they don't match the filter. **(High)** |
| Simple paging (alternative) | `GET /me/mailFolders('sentitems')/messages?$select=...&$top=...` | Default page 10, `$top` 1-1000; big pages with full bodies can trigger HTTP 504, so tune `$select`/`$top`. Don't parse `$skip` from `nextLink`. **(High)** |
| Body format | Header `Prefer: outlook.body-content-type="text"` | Returns `body` and `uniqueBody` as text instead of HTML (list docs also say list returns HTML only - **test** which wins). `Prefer: outlook.allow-unsafe-html` returns original HTML. **(High/Med)** |
| Stable IDs | Header `Prefer: IdType="ImmutableId"` | Default message IDs change when an item is moved; immutable IDs make dedupe/delta reconciliation safe. **(High)** |
| Batch | `POST /v1.0/$batch` | Max **20** requests per batch; each sub-request is throttled individually (429 per item with its own `Retry-After`); for Outlook, Graph runs **up to 4** sub-requests of a batch concurrently, or use `dependsOn` to serialise. SDKs do not auto-retry throttled sub-requests. **(High)** |

**Permissions.** `Mail.ReadBasic` (delegated) is the least-privileged scope for list/delta, but it **excludes body, bodyPreview, attachments and all extended properties** (per Exchange's role description), so it is useless for style learning; it is still handy for a metadata-only "relationship graph" tier. `Mail.Read` is required for bodies/`uniqueBody`/headers/extended properties. `Mail.ReadWrite` adds create/update/delete (drafts); `Mail.Send` sends. There is **no folder-scoped mail permission**: `Mail.Read` grants the whole mailbox, so "we only read Sent Items" is a self-imposed control you must prove with logging. **(High)**

### A2. Fields that give thread and audience context

| Field | Use for PersonaAgent | Caveats |
|---|---|---|
| `uniqueBody` | Only the part unique to this message - the user's own words. Primary input for style learning. | Not returned by default (`$select=uniqueBody`). Exchange-computed; still strip signatures/disclaimers. Support inside a **delta** `$select` not confirmed - test; fallback is per-message GET in `$batch`. **(High/Low)** |
| `body` | Full body incl. quoted history -> gives the *context the user was replying to* without fetching the parent from the Inbox. | HTML by default. |
| `bodyPreview` | First 255 chars, text. | |
| `conversationId` | Groups the thread. | |
| `conversationIndex` (binary) | **Position in thread.** Header block = 22 bytes; each reply/forward appends a 5-byte child block. Length 22 => thread starter; >=27 => reply/forward; depth = (len-22)/5. | Some non-Outlook clients/gateways can reset it; validate on real data. **(High for format)** |
| `internetMessageId` | RFC 2822 ID; join key with `In-Reply-To`/`References`. | |
| `internetMessageHeaders` | RFC 5322 headers (incl. `In-Reply-To`, `References`, `MSIP_Labels`). | `$select` only, read-only. Whether transport headers are present on the **Sent Items copy** is not documented - prefer MAPI extended properties below. **(Med/Low)** |
| `singleValueExtendedProperties` | `$expand=singleValueExtendedProperties($filter=id eq 'String 0x1042' or id eq 'String 0x1039')` -> `PidTagInReplyToId` (= parent's Internet-Message-ID, set on replies) and `PidTagInternetReferences` (References header). `Integer 0x0036` = classic Outlook "sensitivity" flag (Normal/Personal/Private/Confidential). | MAPI tags from MS-OXPROPS; 0x0036 tag **[UNVERIFIED in this session]**. |
| `toRecipients`, `ccRecipients`, `bccRecipients`, `replyTo` | Audience (role resolution in section C); breadth (1:1 vs broadcast). | Max 500 recipients total per message sent from EXO via Graph. |
| `from` vs `sender` | Detect **send-on-behalf** (exec assistant: `sender`=EA, `from`=exec) and **send-as**. | Must not train the exec's persona on the EA's writing without consent; model it as an "EA writing as exec" persona. |
| `importance`, `flag`, `categories`, `inferenceClassification`, `hasAttachments`, `isDraft`, `sentDateTime`, `webLink` | Urgency/tone features, follow-up behaviour, filtering drafts. | `hasAttachments` ignores inline attachments. |

**Classifying new-thread vs reply vs forward (recommended rule set):**
1. `conversationIndex` byte length = 22 -> **new thread** (also check no `PidTagInReplyToId`).
2. `PidTagInReplyToId` present -> **reply**; subject prefix (`RE:` and localized forms such as `AW:`, `SV:`, `RV:`) disambiguates reply vs reply-all by recipient set vs parent.
3. Child blocks present, no `In-Reply-To`, subject prefix `FW:`/`FWD:`/`WG:`/`TR:`/`RV:` or an embedded "From: ... Sent: ..." block in `body` -> **forward** (often = *delegation*: forward + short instruction to a junior is a high-value training signal).
4. New thread whose recipients are direct reports and whose text contains imperatives/deadlines -> **delegated new work** (classifier, not a Graph field).
5. Optional cross-check from the received side: `PidTagLastVerbExecuted` (0x1081) on the *original* message records the last action (Outlook EXCHIVERB values 102 reply, 103 reply-all, 104 forward). **(Med)**

### A3. Throttling and backfill engineering

| Limit (Outlook service, per app ID per mailbox) | Value |
|---|---|
| Requests | **10,000 per 10 minutes** (v1.0 and beta) |
| Concurrency | **4 concurrent requests** |
| Upload (PATCH/POST/PUT) | **150 MB per 5 minutes** |
| Global Graph limit (per app, all tenants) | 130,000 requests per 10 seconds |

Source: Graph throttling limits (Outlook include) - limits are per mailbox, so throttling one user does not affect others. **(High)** On 429, wait exactly `Retry-After`; if absent use exponential backoff; avoid immediate retries because throttled calls still count. **(High)**

**Backfill recipe (per mailbox):** 4 workers, each taking a date slice of Sent Items (e.g., by `sentDateTime` ranges using list + `$filter`, or one delta stream plus three list-based historical slices), `$select` only needed fields, `Prefer: odata.maxpagesize=50-100`, immutable IDs, text bodies. Persist the `deltaLink` at the end.

**Backfill time for 50,000 sent emails [ESTIMATE]:**
- *If* `uniqueBody` + `body` come back in the delta/list pages: ~500-1,000 page requests (50-100 msgs/page). Requests are far below 10k/10min; latency dominates (assume 1-5 s per full-body page) -> **~10-40 min with 4 parallel slices**.
- *If* `uniqueBody` needs per-message GETs: 50,000 extra requests -> the 10,000/10-min cap alone forces >= 50 min; with 4-way concurrency at ~200-400 ms each you get ~10-17 req/s -> **~50-90 min**.
- 500k-message mailboxes scale linearly (~2-15 h). Run backfill newest-first so the persona is usable within the first hour.

**Microsoft Graph Data Connect (GDC) as a bulk alternative.** GDC is **Azure-only**: data is delivered via Azure Data Factory / Synapse / Microsoft Fabric into Azure storage sinks (ADLS Gen2, Blob, Azure SQL DB via mapping data flows, Fabric OneLake) in an Azure region that matches the M365 region (India -> South/Central India; North America -> several US regions). Datasets include `SentItems_v0/v1`, `Message_v0/v1`, `TeamChat_v1/v2`, `TeamsStandardChannelMessages_v0`, `Manager_v0`, `DirectReport_v0`, `User_v0/v1`, `CalendarView_v0`, `TeamsTranscript_v1`. Microsoft's throttling guidance says large extractions "should use" GDC because it is not subject to Graph throttling; consent is approved in the M365 admin center. Price: **USD 0.75 per 1,000 objects** per Microsoft's 2023 pricing announcement; the Azure pricing page did not render a number in this session **[verify current price]**. For PersonaAgent it means an Azure footprint in every customer geo and ~USD 112 per user for 150k objects **[ESTIMATE]** - not worth it for the MVP; revisit for 10k+ seat tenants. **(High for mechanics)**

**Exchange "RBAC for Applications" (for future app-only mode).** Replaces Application Access Policies. Admins assign Exchange application roles (`Application Mail.Read`, `Application Mail.ReadBasic`, `Application Mail.ReadWrite`, `Application Mail.Send`, `Application Calendars.Read`, `Application MailboxItem.Read`, ...) to our service principal, scoped by a **management scope** (recipient filter, e.g., group membership) or an **administrative unit**. Grants are a *union* with Entra app permissions, so the tenant must **remove the unscoped Entra `Mail.Read` app permission** or scoping is void; changes take 30 min-2 h to propagate; `Test-ServicePrincipalAuthorization` verifies scope; up to 10,000 apps per org; covers Graph and EWS only (not Teams). This is the right answer when an enterprise prefers app-only mail access limited to enrolled users. **(High)**

### A4. Shared and delegated mailboxes (executive assistants)
- `Mail.Read.Shared` / `Mail.Send.Shared` (delegated) let the signed-in user read/send from mailboxes shared with them; `from`/`sender` encode send-as vs send-on-behalf. Both `.Shared` read scopes are in the Microsoft-managed admin-consent list. **(High)**
- Product rule: an exec's persona may only be trained from the exec's own mailbox with the exec's consent; EA-authored items are tagged `ghostwritten` and kept out of the exec persona unless the exec opts in.

### A5. Write-back (Outlook)

| Action | API | Permission | Security-review weight |
|---|---|---|---|
| Draft reply in-thread | `POST /me/messages/{id}/createReply` (or `createReplyAll`, `createForward`), then `PATCH` body | `Mail.ReadWrite` | Medium-high: write/delete over whole mailbox |
| New draft | `POST /me/messages` | `Mail.ReadWrite` | same |
| Send a draft | `POST /me/messages/{id}/send` | `Mail.Send` | High (BEC/impersonation vector) |
| Send in one step | `POST /me/sendMail` (`saveToSentItems`) | `Mail.Send` | High |

Drafts land in Drafts by default; `isDraft` distinguishes them. Sending limits that apply to anything we send: **10,000 recipients/day, 30 messages/minute per mailbox**, recipient limit per message customizable up to 1,000 (Graph documents 500 total To/Cc/Bcc per message). **(High)**
**Recommendation:** MVP inserts generated text client-side (Outlook add-in compose APIs - neighbouring track) and keeps the backend at `Mail.Read`. Add server-side drafts (`Mail.ReadWrite`) only for an explicit "prepare drafts for me" feature, and never request `Mail.Send` until customers ask for it.

## B. Microsoft Teams messages

### B1. Read paths and permissions

| Need | Call | Permission (least) | Notes |
|---|---|---|---|
| List user's chats | `GET /me/chats` (`$expand=members,lastMessagePreview`, `$orderby=lastMessagePreview/createdDateTime desc`) | `Chat.ReadBasic` (delegated) | `$top` max 50; `$expand=members` returns at most **25 members**; `chatType` = `oneOnOne` / `group` / `meeting`; `viewpoint.isHidden` flags hidden chats. **(High)** |
| Messages in a chat | `GET /chats/{id}/messages` | `Chat.Read` (delegated); app-only `Chat.Read.All` or RSC `ChatMessage.Read.Chat` | `$top` max **50**; `$orderby` `lastModifiedDateTime` (default) or `createdDateTime`, desc only; `$filter` on `lastModifiedDateTime gt/lt` (or `createdDateTime lt`) only when `$orderby` uses the same property. No delegated delta for chats - incremental sync = filter by `lastModifiedDateTime`. **(High)** |
| All messages of a user, all chats (export) | `GET /users/{id}/chats/getAllMessages` | **App-only** `Chat.Read.All` (delegated not supported) | Filters: `from/user/id eq '{oid}'` (sender), `userIdentityType`, `messageType ne 'systemEventMessage'`, combined with `lastModifiedDateTime` range. Messages deleted by users stay exportable for 21 days; requires users to have a Teams licence. Recommended `$top` up to 250 (docs example uses 50; responses may return fewer than `$top`). **(High)** |
| Delta across all chats | `GET /users/{id}/chats/getAllMessages/delta` | App-only `Chat.Read.All` | **Only the last eight months**; `$top` max 50; filter `lastModifiedDateTime gt`. **(High)** |
| Channel messages | `GET /teams/{t}/channels/{c}/messages` (+ `/replies`, `$expand=replies`) | `ChannelMessage.Read.All` (delegated, **admin consent required**); app-only `ChannelMessage.Read.All` or RSC `ChannelMessage.Read.Group` | Root posts only; `$top` default 20, max 50; replies via `$expand=replies` (paged with `replies@odata.nextLink`) or the replies endpoint. Tenant-wide export: `/teams/{id}/channels/getAllMessages` (app-only). **(High)** |

**Context fields on `chatMessage`:** `replyToId` (channel threads only - *not* chats), `attachments` with `contentType: "messageReference"` (quoted replies in chats, including `messagePreview` and the quoted sender), `mentions`, `reactions`, `messageHistory`, `importance` (normal/high/urgent), `messageType` (`message`, `systemEventMessage`, ...), `eventDetail` (membership/rename events), `from.user.userIdentityType` (`aadUser`, `federatedUser`, `anonymousGuest`, ...) and `from.user.tenantId` (external detection), `lastEditedDateTime`, `deletedDateTime` (soft delete), `policyViolation` (DLP), `hostedContents` (images). Body is HTML whenever mentions exist; `locale` is always `en-us`. **(High)**

**Practical rules for Teams persona learning:** a user "turn" = consecutive messages by the user in a chat within N minutes (Teams users split thoughts across messages); "new topic vs reply" in chats = time gap + `messageReference` attachments + no prior message within window; in channels = root post (`replyToId` null) vs reply. Use `chatType` and member count to separate 1:1, small group, large group and meeting chats.

**Caveat:** a Microsoft Q&A answer reports that interactive list endpoints can stop paginating on very old messages and points bulk archiving to the export APIs **(Low - forum answer; test on a 3-year-old chat)**.

### B2. Licensing, metering and "protected APIs" - current state (Oct 2026)
- **Metering ended 2025-08-25** for Teams chat/channel export, retained-message export, Teams chat/channel/member change notifications, message `PATCH`, meeting transcripts and recordings; no billing configuration needed; `model` parameter ignored (Microsoft "Metered APIs" page and the deprecated "Payment models" page; MC1122144). The old models (A = security/compliance apps with E5-class licences; B = other apps at a per-message price; evaluation mode = 500 messages or 600 minutes per month) are history; the payment-models article was marked for removal in June 2026. **(High)**
- Still licensed: **Meeting AI Insights API** (Microsoft 365 Copilot licence) and **DLP `PATCH`** of `policyViolation` (Communications DLP service plan). The only Graph item still metered on the list is SharePoint/OneDrive `assignSensitivityLabel` (USD 0.00185/call). **(High)**
- **Protected APIs:** the export docs still call these "protected APIs" but now say you can call them "as long as the requirements for accessing without a user are met"; the dedicated protected-API page (`/graph/teams-protected-apis`) returns 404 and Veeam's Aug-2025 KB lists only permissions. **Probably no request form any more - verify in a test tenant (Low-Med).** Historically the form was `aka.ms/teamsgraph/requestaccess` with ~1-2 week turnaround.
- Which paths were never metered: all delegated reads (`/me/chats`, `/chats/{id}/messages`, channel messages). Today nothing in our path is metered.

### B3. Change notifications (real-time ingestion)

| Resource | Delegated? | Quotas | Max lifetime |
|---|---|---|---|
| `/users/{id}/chats/getAllMessages` (all chats a user is in) | **Yes** (`Chat.Read`) and app-only | **10 per user**; counts toward the **org-wide 10,000 Teams subscriptions shared by all apps** (403 when exceeded) | 4,320 min (3 days); `lifecycleNotificationUrl` required if > 1 h |
| `/chats/{id}/messages` (one chat) | Yes (`Chat.Read`) | 1 per app per chat; org quota | same |
| `/chats/getAllMessages` (whole tenant) | App-only `Chat.Read.All` | org quota | same |
| `/teams/{t}/channels/{c}/messages` | Yes (`ChannelMessage.Read.All`) | 1 per app per channel; org quota | same |
| `/me/messages`, `/me/mailFolders('inbox')/messages` (Outlook) | Yes (`Mail.Read`) | **1,000 active subscriptions per mailbox across all apps** | 10,080 min (~7 days); **1,440 min with resource data** |

- Rich notifications (`includeResourceData: true`) need an `encryptionCertificate`; payload is encrypted and signed with validation tokens. Latency: Teams `chatMessage` average < 10 s (max 1 min); Outlook `message` average < 1 min (max 3 min). Subscription API limits: 500 create/update/delete per 20 s per tenant (2,000 global); reauthorize 1,000 per 20 s per tenant. Delivery options: webhooks, Azure Event Hubs, Azure Event Grid - on AWS use HTTPS webhooks (API Gateway/ALB -> SQS). **(High)**
- The Teams overview page says subscriptions last "maximum 60 minutes" while the subscription reference says 3 days with a lifecycle URL - treat 1 h as the limit *without* `lifecycleNotificationUrl`. **(Med)**
- Outlook folder-level subscriptions are documented for Inbox; subscribing to `mailFolders('sentitems')/messages` is expected to work but **test it**; fallback is `/me/messages` + filter on `parentFolderId`, with delta as the source of truth. **(Med)**
- **Design consequence:** per-user Teams subscriptions are fine for pilots and mid-market (hundreds to low thousands of seats). For tenants approaching the 10,000 shared quota (other vendors - archiving, DLP, backup - also consume it), switch to scheduled polling (`getAllMessages` filtered by sender and `lastModifiedDateTime`, app-only) rather than a tenant-wide `/chats/getAllMessages` subscription, which would deliver *non-enrolled* users' messages to us (data-minimisation problem).

### B4. Sending as the user (write-back)

| Action | API | Permission | Notes |
|---|---|---|---|
| Post in a 1:1/group chat | `POST /chats/{id}/messages` | Delegated `ChatMessage.Send` | App-only only via `Teamwork.Migrate.All` for **import/migration mode** - an app cannot post as a user without the user's token. Can't create chats. Microsoft: using Teams "as a log file" violates the terms. **(High)** |
| Reply quoting specific messages | `POST /chats/{id}/messages/replyWithQuote` (v1.0) | Delegated `ChatMessage.Send` | Up to 10 quoted messages; produces `messageReference` attachments. **(High)** |
| Channel post / reply | `POST /teams/{t}/channels/{c}/messages` (`/replies`) | Delegated `ChannelMessage.Send` | |
| Drafts | **No Graph draft concept in Teams** | - | Use a Teams message extension / compose insertion (neighbouring track). |
| Rate | 1 POST per second per user per chat/channel; 20 rps per app per tenant for chat POST; 50 rps for channel POST | | **(High)** |

### B5. Teams throttling (per app)

| Operation | Per app per tenant | Per app, all tenants | Per resource |
|---|---|---|---|
| GET 1:1/group chat message | **20 rps** | 200 rps | **1 rps per chat** |
| GET channel message | 20 rps | 200 rps | 1 rps per channel |
| GET `getAllMessages` (chats or channels), `getAllRetainedMessages` | **200 rps** | 1,000 rps | - |
| POST chat message | 20 rps | 200 rps | 1 rps |
| POST channel message | 50 rps | 500 rps | 1 rps |
| GET members / channels | 60 rps | 1,200 rps | |
| Other GETs | 30 rps | 1,500 rps | 1 rps |
| List/Get chats | 5 rps **per user** | | |
| Any request on a given team | 4 rps per app | | |

Source: Graph throttling limits, Teams include. **(High)** These per-tenant ceilings - not Outlook - are what make tenant-wide Teams backfill slow (see section H).

## C. Organisational context: senior vs junior vs peer vs external

### C1. Directory signals

| Signal | Call | Permission | Notes |
|---|---|---|---|
| User's manager | `GET /me/manager` | **`User.Read.All` (delegated) is the documented least-privileged scope** -> admin consent | 404 if no manager. **(High)** |
| Full management chain | `GET /me?$expand=manager($levels=max;$select=id,displayName,jobTitle)` + header `ConsistencyLevel: eventual` | `User.Read.All` | `$levels` = `max` or 1-1000; only on a single user, not on a list. **(High)** |
| Whole org chart in bulk | `GET /users?$select=id,displayName,jobTitle,department,employeeType,userType,mail&$expand=manager($select=id)` | `User.Read.All` | Single-level manager per user; build the tree ourselves. |
| Direct reports | `GET /me/directReports` | `User.Read.All` (assumed same as manager - **verify**) | |
| Basic profile of colleagues | `GET /users/{id}` | `User.ReadBasic.All` (no admin consent by definition) | Basic set = display name, first/last name, email, photo (per permission description); **does not include `jobTitle`/`department`** **(Med)** |
| Relevance ranking ("who I talk to") | `GET /me/people` | `People.Read` | **People API is in maintenance mode**; Microsoft recommends the Search API (`POST /search/query`, `entityTypes:["person"]`). `People.Read` is also in the Microsoft-managed admin-consent list. **(High)** |
| Tenant domains (internal vs external) | `GET /organization` -> `verifiedDomains` | `User.Read` believed sufficient **[UNVERIFIED]** | Compare recipient SMTP domains; also treat `userType eq 'Guest'` and Teams `federatedUser`/`anonymousGuest`/foreign `tenantId` as external. |
| Multi-Geo location | `user.preferredDataLocation` | `User.Read.All` **[UNVERIFIED property semantics for routing]** | Lets us route each user's data to the matching AWS region in Multi-Geo tenants. |

**Cost of traversal:** directory reads use Entra's resource-unit throttling: per app+tenant **3,500 RU/10 s (tenant < 50 users), 5,000 (50-500), 8,000 (> 500)**; most reads cost 1 RU, `$select` -1, `$expand` +1, `$top` < 20 -1; per app across tenants 150,000 RU/20 s. A 10,000-user org chart is ~11 paged calls - negligible. Refresh weekly plus on `user` change notifications (lifetime up to 41,760 min). **(High)**

### C2. How reliable is org data, and fallbacks
No authoritative statistic on manager/title completeness in real tenants was found **[UNVERIFIED]**. Field experience (and the fact that Microsoft's own Viva Insights asks customers to upload HR attributes) suggests `manager`, `jobTitle`, `department`, `employeeType` are often missing, stale or free-text, especially in mid-market tenants without HR-driven provisioning **[ESTIMATE]**. Design for graceful degradation:
1. **Directory first** (manager chain, direct reports, title keywords such as CEO/VP/Director/Manager/Lead/Intern).
2. **Behavioural inference**: who initiates vs responds, response latency, delegation verbs, salutation/sign-off formality, CC patterns (a person the user always CCs their manager on is likely external/senior).
3. **Domain rules**: tenant verified domains = internal; per-tenant admin lists of *client* and *vendor* domains (or CRM sync later) for external sub-types.
4. **User confirmation**: show the top ~30 contacts with a guessed relationship (manager / senior / peer / report / client / vendor) and let the user correct; store as ground truth with provenance.
5. Store relationships in the graph DB with `source` and `confidence`, re-evaluated as the directory changes.

### C3. Calendar (meeting linking)
- `GET /me/calendarView?startDateTime=...&endDateTime=...` (+ `/calendarView/delta` for sync) with `Calendars.ReadBasic` (no bodies) or `Calendars.Read`; events expose organizer, attendees (required/optional), `isOnlineMeeting`, `onlineMeeting.joinUrl` to join with Teams meeting chats (`chatType: meeting`) and transcripts. **(Med - standard API, not re-read in this session)**
- All `Calendars.*` delegated scopes are in the Microsoft-managed admin-consent list. **(High)** For Pillar 1 the MVP can skip calendar; Pillar 2 (meeting memory) needs it.

## D. Consent, app registration and trust

### D1. App registration model
- One **multi-tenant** Entra app per *permission tier* is the cleanest for enterprise review: e.g., `PersonaAgent - Read` (delegated read scopes), `PersonaAgent - Compose` (adds `Mail.ReadWrite`/`ChatMessage.Send`, optional), and later `PersonaAgent - Org Sync (app-only)`. Admins can approve and revoke tiers independently, and Microsoft 365 Certification's least-privilege review is easier. (Microsoft's Copilot API terms explicitly require ISVs to register as multi-tenant rather than proxying single-tenant apps in customer tenants.) **(Med - design recommendation)**
- Use certificate credentials (not client secrets) held in AWS KMS/Secrets Manager; publish a stable redirect domain matching the verified publisher domain.

### D2. Consent policies in 2025-2026

| Tenant user-consent setting | What end users can consent to |
|---|---|
| Do not allow user consent | Nothing - admin consent for everything (very common in enterprises) |
| Allow user consent for apps from verified publishers, for selected permissions (`microsoft-user-default-low`) | Only permissions the admin classified as "low impact", only verified-publisher or in-tenant apps |
| **Let Microsoft manage your consent settings** (`microsoft-user-default-recommended`; **default for new tenants**) | Any user-consentable delegated permission **except** Files.Read(Write).All, Sites.Read(Write).All, **Mail.Read, Mail.ReadWrite, Mail.ReadBasic, Mail.Read.Shared, Mail.ReadBasic.Shared, Mail.ReadWrite.Shared, MailboxItem.Read, Calendars.Read/ReadBasic/ReadWrite/Read.Shared/ReadWrite.Shared, Chat.Read, Chat.ReadWrite, OnlineMeetings.Read/ReadWrite, MailboxFolder.Read/ReadWrite, MailboxSettings.Read/ReadWrite, Contacts.ReadWrite (+ .Shared), Tasks.\*, People.Read**, plus Exchange EAS/EWS/IMAP/POP `AccessAsUser.All`. A companion policy still lets users consent to a few named mail clients (Apple Mail, Spark, eM Client, Thunderbird, Android/Samsung mail). |
| Allow user consent for apps (`microsoft-user-default-legacy`) | Anything not requiring admin consent, any app (shrinking) |

Timeline: files/sites blocked from mid-July 2025 (MC1097272); Exchange/Teams mail, calendar, chat and meeting scopes added in a rollout from end-Oct to late-Nov 2025 (MC1163922, published 2025-10-02); further additions (People.Read, Contacts, Tasks) appear in the current policy text (updated 2026). Only tenants on the Microsoft-managed setting are affected; existing user grants keep working; Microsoft updates this policy automatically. Apps with "assignment required" always need admin consent. **(High)**

Also: since November 2020, with risk-based step-up consent, users cannot consent to multi-tenant apps registered after 2020-11-08 from **unverified publishers** that request more than sign-in/basic profile. **(High)**

**What forces admin consent for PersonaAgent:**

| Scope | Admin consent by definition? | In Microsoft-managed block list? | Practical outcome |
|---|---|---|---|
| `User.Read`, `openid`, `profile`, `email`, `offline_access` | No | No | User can consent |
| `User.ReadBasic.All` | No | No | User can consent (unless consent disabled) |
| `Mail.Read` / `Mail.ReadBasic` / `Mail.ReadWrite` | No | **Yes** | **Admin** |
| `Mail.Send` | No | No | User (but security teams will challenge) |
| `Chat.Read` / `Chat.ReadWrite` | No | **Yes** | **Admin** |
| `Chat.ReadBasic`, `ChatMessage.Send` | No | No | User |
| `ChannelMessage.Read.All` (delegated) | **Yes** | - | **Admin** |
| `User.Read.All` (delegated) | **Yes** | - | **Admin** |
| `Calendars.Read(Basic)`, `OnlineMeetings.Read`, `People.Read`, `MailboxSettings.Read` | No | **Yes** | **Admin** |
| `OnlineMeetingTranscript.Read.All` (delegated) | **Yes** | **Yes** | **Admin** |
| Any application permission (`Mail.Read`, `Chat.Read.All`, ...) | **Yes** | - | **Admin**; Graph app roles can only be approved by Global Admins via the consent workflow |

Sources: Graph permissions reference; Entra "Manage app consent policies". **(High for block list; Med for per-scope "admin consent by definition" values as extracted)**

### D3. Admin consent workflow
Users who hit a consent wall can send a request to designated reviewers (users, groups or roles) by email; reviewers can approve only if their own role allows that grant, and **only Global Administrators can approve requests that include Microsoft Graph application permissions**; request expiry is configurable; enabling takes up to an hour. **(High)** Product implication: ship (1) a direct admin-consent link (`/adminconsent` endpoint) for IT-led onboarding, (2) a "request access from your admin" path for bottom-up interest, and (3) a one-page permission justification that maps each scope to a feature (also required by Microsoft 365 Certification).

### D4. Publisher verification (do it in week 1)
Free; requires a verified **Microsoft AI Cloud Partner Program** Partner Global Account, an app registered with a work account in a tenant associated with that account, a publisher domain matching the verified email domain (not `*.onmicrosoft.com`), MFA, and Application/Cloud Application Administrator + Partner Center admin roles. "Can be verified in minutes" once prerequisites exist; gives the blue "verified" badge and unlocks `microsoft-user-default-low`-style policies. **(High)**

### D5. Microsoft 365 App Compliance Program
- **Publisher Attestation** - free self-assessment, "most can be completed in one hour or less"; published on Microsoft Learn and shown in admin centers. Prerequisite for certification. **(High)**
- **Microsoft 365 Certification** - annual independent audit by **Claranet Limited** (ISV contracts and pays directly); covers Application Security, Operational Security, and Data Handling/Security/Privacy, plus **Graph permission validation** (least privilege, cross-checked against the attestation) and **Responsible-AI controls**. Process: Stage 1 initial documents (14 days), Stage 2 evidence review (**60 days**, one extension of up to 60 days), annual recertification (start up to 90 days early; lighter "satellite" audits possible in years 2-3). **Penetration testing is mandatory for apps that connect to external services not hosted by Microsoft** (i.e., our AWS backend), annually, by a reputable third party, covering the full external footprint; critical/high findings fixed within a month. Example controls: 30 days of security logs immediately available and 90 days retained; patching SLAs (critical 14 days, high 30 days). Claranet quotes a fixed-price SOW (standard assessment ~6.5 consultancy days, optional 3-day gap analysis); **price not published [UNVERIFIED]**; budget **~USD 15-40k/year incl. pentest [ESTIMATE]**. Microsoft's **ACAT** (App Compliance Automation Tool) can automate evidence for apps on Azure, **AWS** or hybrid. Microsoft notes certification "may be required for apps to be enabled" in some tenants. **(High except price)**
- Recommendation: Publisher verification + Attestation before the first pilot; start Certification at month 3-4 so it lands within ~6-9 months.

### D6. Tokens, Conditional Access, CAE, revocation
- Refresh tokens: **90 days** default (24 h for SPA redirect URIs), replaced on every use; tokens issued to **confidential clients** survive a user's own password change but are revoked when an admin resets the password in the Entra/M365 admin center, when the user or an admin revokes sessions, or on account disable. Handle `invalid_grant` by pausing that user's sync and prompting re-auth. **(High)**
- Access tokens: 1 h by default; **up to 28 h** for CAE-capable clients. CAE critical events (account disabled/deleted, password change/reset, MFA enabled, admin "revoke sessions", high user risk) propagate to Exchange, SharePoint, Teams and Graph near-real-time (up to ~15 min). Implement claims-challenge handling (401 + `WWW-Authenticate` `insufficient_claims` -> re-acquire token with claims; declare client capability `cp1` in MSAL). **(High)**
- **IP-based Conditional Access is a real deployment risk:** every background token refresh from AWS is a non-interactive sign-in evaluated against the tenant's CA policies, and CAE enforces IP named-location policies instantly at Exchange/Teams/Graph. Provide **static egress IPs per region** (NAT gateway EIPs) for customers to add as trusted named locations, and document required CA exclusions. CA/group changes can take up to a day to replicate; guest accounts don't get CAE. **(High for mechanism; Med for how often customers hit it)**

### D7. Objections an enterprise security review will raise (and our answers)
1. *"Mail.Read is the whole mailbox, not Sent Items."* -> There is no folder-scoped Graph permission. Offer: read-only scopes, code-level folder allow-list, per-request audit log exported to the customer's SIEM, and an app-only RBAC-for-Applications option limited to enrolled users.
2. *"Chat.Read exposes colleagues' and external parties' messages."* -> Store others' messages only as redacted context windows, configurable to zero; no persona is ever built for non-consenting people.
3. *"You copy our data to AWS and train AI on it."* -> No cross-customer training; per-user persona artefacts only; region pinning (India/US); deletion SLAs; DPA + sub-processor list (LLM provider, region).
4. *"A system that writes exactly like our CEO is a BEC/deepfake weapon."* -> Never send autonomously; drafts/insertion only; exec personas disabled by default and admin-controllable; watermark/audit trail of AI-assisted messages; no cross-user persona access.
5. *"offline_access means you hold long-lived tokens."* -> KMS-encrypted per tenant, isolated, rotated; immediate purge on revoke; CAE support.
6. *"Labelled 'Highly Confidential' and encrypted content."* -> Label-aware skip/metadata-only ingestion (section E).
7. *"Legal hold / eDiscovery / retention."* -> Delete-propagation within N hours, customer-initiated export and hold of our copies, audit logs.
8. *"Where is the data and who can see it?"* -> In-geo storage and inference, zero standing access for staff, break-glass with customer approval.
9. *"Certifications?"* -> SOC 2 Type II / ISO 27001 roadmap, Microsoft 365 Certification, annual pentest, Publisher Attestation.
10. *"Conditional Access / compliant device / location policies."* -> Static IPs, CAE, documented CA guidance.
11. *"Defender for Cloud Apps App Governance flags high-volume Graph readers."* -> Pre-brief admins on expected volumes; throttle-aware backfill windows.
12. *"Employee monitoring and works-council concerns."* -> Opt-in per user, user-visible data inventory, user-level deletion (EU later).

## E. Compliance and data governance in the customer tenant

### E1. Reading sensitivity labels and classification signals before ingestion

| Signal | How a third-party app reads it | Confidence |
|---|---|---|
| **Email sensitivity label** | Labelled mail carries a single header **`MSIP_Labels`** with `MSIP_Label_{GUID}_Enabled=true; ..._Name=...; ..._SiteId=...; ..._Method=Standard/Privileged; ..._ContentBits=...` (MIP SDK metadata spec). Read via `$select=internetMessageHeaders` (or the MIP SDK). Map GUID -> label name/priority from the tenant's label catalogue (Graph information-protection label APIs / MIP SDK policy - **endpoint and permission not re-verified in this session**; `InformationProtectionPolicy.Read` is admin-consent). | High (format); **Med** that the header is present on Sent-Items copies - test |
| **Encrypted mail** (label with encryption, OME/IRM) | Content is rights-protected; without RMS rights we cannot read it. Treat as metadata-only and record "protected - skipped". | Med **[UNVERIFIED payload shape]** |
| **Teams DLP** | `chatMessage.policyViolation` (set by a DLP application, e.g., Purview Communication DLP) - skip or quarantine those messages. Teams chat messages have **no per-message sensitivity label** (labels apply to teams/groups/sites and, with Teams Premium, meetings **[UNVERIFIED for meetings]**). | High (field) |
| **Tenant DLP verdict on arbitrary text** | **Purview `processContent`** (Graph **v1.0**): `POST /me/dataSecurityAndGovernance/processContent` (or `/users/{id}/...`) with `Content.Process.User` (delegated or application; `Content.Process.All` higher). Send text plus activity/app metadata; response returns `policyActions` and `protectionScopeState`; pair with `protectionScopes/compute` and `If-None-Match` ETag caching. Built for non-Microsoft AI apps to apply the customer's own DLP/audit to prompts and responses. **Billing/licensing for third-party apps not verified [UNVERIFIED]**. | High (API exists); Med (behaviour) |
| **SIT match details** | Graph does not hand third parties per-item Sensitive Information Type results for mail/chat (no such API found in this session). Replicate Microsoft's published SIT definitions in our own pre-ingestion detectors. | Med |

**Recommended pre-ingestion gate (per item, in memory, before anything is persisted):**
1. Label check (`MSIP_Labels`) -> tenant policy: e.g., *Highly Confidential* / *Restricted* => **do not ingest body**, keep minimal metadata (or nothing); *Confidential* => ingest with stricter redaction; encrypted => skip.
2. Teams `policyViolation` present => skip.
3. Run US + India SIT detectors (below) + PII/NER (Amazon Comprehend etc., neighbouring track) => redact/tokenise.
4. Optionally call `processContent` on **generated drafts** before they're shown/inserted, so the customer's DLP and audit see AI output - a strong differentiator for regulated buyers.

### E2. Microsoft Purview built-in sensitive information types (SITs) for the US and India
Microsoft's confidence mapping: low <= 65, medium = 75, high = 85; detection typically = pattern + keyword within 300 characters (+ checksum where applicable). **(High)**

| Jurisdiction | Built-in SIT (Purview name) | Pattern / validation (as published) |
|---|---|---|
| India | **India unique identification (Aadhaar) number** | 12 digits, optional spaces/dashes in 4-4-4 groups, first digit not 0 or 1, **checksum: yes** (the Aadhaar check digit is Verhoeff - algorithm name not stated on the page); keywords: aadhaar, aadhar, aadhar#, uid, uidai, "आधार"; high (85) with keyword + checksum, medium (75) checksum only. **(High)** |
| India | **India permanent account number (PAN)** | 10 chars: 3 letters + 1 letter in {C,P,H,F,A,T,B,L,J,G} + 1 letter + 4 digits + alphabetic check letter; **no checksum**; keywords "Permanent Account Number", "PAN"; 85 with keyword, 65 without. **(High)** |
| India | India GST Number; India driver's license number; India Voter Id Card | Built-in (definitions not re-read here). **(High that they exist)** |
| India | *Not in the built-in list:* India passport, bank account / IFSC, UPI IDs, mobile numbers | Need **custom SITs/regex** in our detector. **(Med - based on Purview SIT index page)** |
| US | **U.S. social security number (SSN)** | 9 digits formatted (ddd-dd-dddd / spaces) or unformatted; separate functions for pre-2011 "strong format" and post-2011 randomized SSNs; **no checksum**; keywords incl. SSN, SSA Number, social security #, Soc Sec, SS#, SSID; confidence 85/75/65/55 by pattern type, all requiring a keyword. **(High)** |
| US | U.S. individual taxpayer identification number (ITIN); U.S. bank account number; ABA routing number; U.S. driver's license number; U.S./U.K. passport number; Credit card number; U.S. physical addresses; Drug Enforcement Agency (DEA) number; Medicare Beneficiary Identifier (MBI); ICD-9/ICD-10-CM; "All medical terms and conditions" | Built-in (details not re-read here) - map to HIPAA (PHI), GLBA (NPI) and PCI DSS (PAN data) handling. **(High that they exist)** |
| Both | Credentials: All credential types, General password, Microsoft Entra client secret / user credentials, Amazon S3 client secret access key, GitHub PAT, Slack access token, client secret/API key | Secrets in email/chat must never enter the persona store. **(High that they exist)** |

India-specific handling note: UIDAI rules on Aadhaar display/storage (e.g., masking all but the last 4 digits) and the DPDP Act/Rules obligations belong to the legal and security tracks **[UNVERIFIED here]**; the detector above gives the precise building block.

### E3. Retention, deletion propagation and derived data
- **Outlook:** deletions and moves out of Sent Items arrive as `@removed` in the next delta round; items removed by the customer's retention policies disappear the same way. **(High)**
- **Teams:** soft-deleted messages carry `deletedDateTime` and fire `deleted` change notifications; export APIs can still read user-deleted messages for 21 days (`getAllRetainedMessages` covers held/edited versions where retention policies exist). For delegated polling, re-scan recent windows to catch deletes/edits. **(High/Med)**
- **Microsoft API Terms s.5(b)-(c)** require copies to be kept up to date, "including corrections, restrictions ... or deletion", with retention/deletion policies and full deletion when a user abandons/uninstalls - i.e., **delete propagation is a contractual obligation, not just good practice**. **(High)**
- Build **lineage** from every derived artefact (chunks, embeddings, persona features, graph edges) back to source item IDs (immutable IDs), so a delete can cascade within an SLA (target <= 24 h). Prefer persona features that are aggregates and re-computable rather than fine-tuned weights that can't forget a message.

### E4. eDiscovery and legal hold
Copies in PersonaAgent sit outside Purview eDiscovery/holds. If a custodian is on legal hold, the customer may still have preservation duties over copies held by its processor **[legal track to confirm]**. Provide: tenant-admin "hold" flag per user that suspends delete-propagation for that user's copies (while still honouring user-visible deletion in the UI), admin export of a user's stored items and derived summaries, and immutable audit logs of access. Retention-driven deletes must not be propagated while a hold flag is set.

### E5. Data residency: India and US tenants vs our AWS copies
- **Microsoft's commitments (Product Terms):** for tenants whose **default geography is India or the United States**, Microsoft stores at rest in that geography: Exchange Online mailbox content (bodies, calendar entries, attachments), SharePoint/OneDrive content, **Teams chat messages (1:1, group, channel, meeting, images)**, and Microsoft 365 Copilot interaction content. India datacenter metros: **Chennai, Mumbai, Pune**; US: Boydton, Cheyenne, Chicago, Des Moines, Quincy, San Antonio, Santa Clara, San Jose. India is a "Local Region Geography" where **Advanced Data Residency (ADR)** can also be bought (covers more services incl. Purview components); the **US has Product-Terms and Multi-Geo commitments but no ADR**. Multi-Geo lets a tenant place individual users in other geos. **(High)**
- **What this means for us:** Microsoft's commitments end when we copy data out. Indian customers that chose India residency (especially ADR buyers, BFSI, public sector) will expect **storage and processing (including LLM inference and backups) in India** -> pin India tenants to **AWS ap-south-1 (Mumbai)** (DR in another Indian region, e.g., ap-south-2 Hyderabad), and US tenants to **us-east-1** (DR us-west-2). Detect the tenant's geography at onboarding (default geography / admin attestation; per-user location for Multi-Geo tenants **[UNVERIFIED property semantics]**) and refuse to process outside the pinned region. Ensure Bedrock/LLM cross-region inference profiles do not route Indian data outside India (AWS track to verify). **(High for principle)**
- Graph calls go to the global endpoint; at-rest location in Microsoft is unaffected by where our caller runs. Graph Data Connect, if ever used, must run in the Azure region mapped to the tenant (India -> South India/Central India). **(High)**
- Regulatory context (brief; legal track owns it): India's DPDP Act 2023 and its Rules, CERT-In 2022 directions (log retention/incident reporting), RBI/SEBI sectoral localisation and cloud rules; US sectoral regimes (HIPAA, GLBA, state privacy laws). **[UNVERIFIED details in this doc]** US government tenants (GCC High/DoD) use separate national-cloud Graph endpoints and app registrations - exclude from MVP. **(Med)**

### E6. Microsoft API terms, AI use and storage outside Microsoft
Microsoft APIs Terms of Use (last updated **October 2025**) - the clauses that matter:
- s.3(b)(4): you may not "**scrape, build databases or otherwise create copies** of any data accessed or obtained using the Microsoft APIs, **except as necessary to enable an intended usage scenario** for your Application" -> our persona store must be framed (contract + docs) as the intended usage scenario, with no extra copies. **(High)**
- s.3(b)(5): request only the minimum data and permissions needed. s.3(b)(11): no use outside permissions expressly granted by Customers. s.3(b)(12): no advertising/marketing use of API data (incl. derived/anonymised). s.3(b)(14): no redistribution/resale of API data. **(High)**
- **s.3(c): unless the Customer has expressly and specifically granted use permissions, the Microsoft email protocols and APIs (incl. Outlook APIs in Graph) may only be used for syncing or backing up email, calendar and contacts.** Persona learning is neither, so **the customer agreement and the admin-consent experience must contain an express, specific grant**. **(High)**
- s.4: secure systems; Microsoft may monitor/audit (up to two full-feature instances), report vulnerabilities and breaches to MSRC; no public statements about breaches without permission. s.5: comply with privacy laws, obtain consents, keep data current, delete on abandonment, privacy statement "as protective as" Microsoft's with a link to revoke consent (`myapps.microsoft.com`). s.6/s.10: Microsoft may change, charge for, limit or terminate API access at any time; on termination, follow the Customer's instruction to return/delete data. s.11(j): EU Teams commitments (case AT.40721) override these terms where they conflict (EU only). **(High)**
- **No clause bans using API data for AI/ML training** in the October-2025 Microsoft API terms (contrast Slack). The Microsoft 365 **Copilot** API terms (preview, Dec 2025) add "you may not create an Application that is not human directed, such as bots, multiplexing or similar" and require Copilot licences - relevant only if we call Copilot APIs. **(High)**
- No 2025-2026 Microsoft policy was found that blocks third-party AI apps from Graph mail/chat data; Microsoft's moves were (a) Secure-by-Default consent tightening, (b) first-party governance for agents (Agent 365, Entra Agent ID, Purview for AI), (c) making Teams export APIs free. **(Med - absence of evidence)** If we publish a Teams app / Outlook add-in in Microsoft's store, store certification policies (incl. AI disclosures) apply **[UNVERIFIED specifics - neighbouring track]**.

## F. Platform risk and Microsoft roadmap

### F1. EWS retirement - we must be Graph-only
- **2026-10-01:** EWS in Exchange Online is disabled by default, tenant by tenant; admins who still need it must set `EWSEnabled=True` and maintain an **AppID allow-list** (Microsoft asked admins to do this before August 2026). **2027-04-01:** permanent shutdown, no re-enablement. On-premises Exchange Server is unaffected. Source: MC1227454 (published 2026-02-05) and the EWS deprecation page. **(High)**
- Implication: no EWS fallbacks (e.g., for conversation actions or MIME export); all features must exist in Graph. On-prem Exchange customers are out of scope for the MVP.

### F2. Microsoft 365 Copilot APIs (what they are, whether we can use them)

| API | Status (Aug-Oct 2026) | What it does | Usable for PersonaAgent? |
|---|---|---|---|
| Retrieval API | GA (pay-as-you-go option in preview) | RAG chunks from **SharePoint, OneDrive, Copilot connectors only** (not mail, not Teams chats); max 25 results; 200 requests/user/hour; needs `Files.Read.All` + `Sites.Read.All` (or `ExternalItem.Read.All`) | Not for persona learning; maybe later for document-grounded drafting. |
| Search API | Preview | Hybrid semantic search over OneDrive | Marginal |
| Chat API | Preview | Copilot conversational answers in your app; text only, no actions | No (competitor surface) |
| Meeting Insights API | Available | AI notes, action items, mentions for Teams meetings (`/copilot/users/{id}/onlineMeetings/{id}/aiInsights`) | Pillar 2 option **only for users with Copilot licences** |
| Interaction Export API / AI-interaction change notifications | Available / preview | Capture users' Copilot interactions for compliance | No |
| Usage reports, Package management | Available | Admin analytics, agent inventory | No |

Licensing: **every user who accesses Copilot functionality via these APIs needs a Microsoft 365 Copilot licence** (on top of E3/E5-class subscriptions), except the Retrieval API's pay-as-you-go preview for tenant-level sources. The Copilot API terms (preview) forbid non-human-directed apps ("bots, multiplexing or similar") and building databases from the data except as necessary. **(High)** Conclusion: Copilot APIs are **not** a route to mail/Teams persona data; Graph remains the only path. They are a later "bring Copilot customers' meeting insights into our memory" option.

### F3. Microsoft Agent 365 and Entra Agent ID
- **Agent 365** - "observe, govern, secure" control plane for agents: central **agent registry** and agent map in the Microsoft 365 admin center, lifecycle/access governance via Entra and Purview, Defender threat protection. **Generally available for the Commercial segment since 2026-05-01**, licensed **per user**; works best with Microsoft E5; at least one user needs an Agent 365 licence; **included in Microsoft 365 E7** and available as an add-on to Microsoft E5/A5/Business Premium (or Defender Suite + Purview Suite). Launch partners include Box, Canva, Zendesk, Zoho, Miro, Genspark, Manus, n8n, Kore, Kasisto (ready-to-deploy agents and "agent factories"). Notably, **agents built on Amazon Bedrock or Google Vertex AI can be made visible in the M365 admin center automatically**, and the Agent 365 SDK gives partner agents an Entra Agent ID, observability and Purview audit. **(High)**
- **Entra Agent ID** - agent identities (and agent identity blueprints) as a distinct identity type; supports autonomous access (own permissions) and delegated access on behalf of users, optional paired "agent user accounts", sign-in logs that mark activity as AI-agent activity. Available to all Entra customers; extending Entra security features (e.g., Conditional Access for agents) requires Agent 365 licensing. **(High)**
- **Implications for PersonaAgent:**
  1. Must we register? **No** - a normal multi-tenant Entra app with delegated Graph permissions works today. **Should we?** Plan for it: enterprises standardising on Agent 365 will increasingly expect agents to appear in the registry with an Agent ID, observability and Purview audit. Treat "Agent 365-ready" (Agent ID + SDK telemetry) as a **v2 enterprise feature** (month 6-12), not MVP.
  2. Because our runtime is AWS (Bedrock AgentCore), the tenant may already see our agent via Agent 365's Bedrock registration feature - provide clean names/descriptions/owners.
  3. Competitive: Microsoft owns the Outlook/Teams surfaces, the consent defaults and now the agent control plane; Copilot is the default "draft my reply" option in E3/E5 + Copilot tenants. Our wedge must be persona fidelity, cross-surface memory (incl. Pillar 2) and governance - not raw drafting. **(Med)**
- Also noted on the Graph docs hub (2026): a **"Microsoft MCP Server for Enterprise"** for Graph **[UNVERIFIED - not evaluated]**; Copilot connectors (formerly Graph connectors) could later push PersonaAgent memories into the Microsoft 365 index so Copilot can use them (partnership angle) **[UNVERIFIED permissions]**.

### F4. Other platform risks to track
- Terms can change or access can be terminated "at any time for any reason" (API ToU s.6, s.10); the Microsoft-managed consent policy auto-updates (it grew twice in 2025-2026). **(High)**
- Throttling limits are Microsoft-defined and can be tightened; EU Teams commitments (AT.40721) constrain Microsoft only for EU interoperability. **(High)**
- Licensing creep: Microsoft has moved Teams APIs from metered to free (2025), but meeting AI is tied to Copilot licences - Pillar 2 features that depend on Microsoft AI outputs inherit that dependency. **(High)**

## G. Google Workspace and Slack (later expansion)

### G1. Gmail / Google Workspace
- **Reading sent mail:** `users.messages.list` with `labelIds=SENT` (or `q=in:sent`), then `users.messages.get` (`format=full` or `metadata` for headers such as `In-Reply-To`, `References`, `Subject`, plus `threadId`); incremental sync with `users.history.list` from a stored `historyId`; push via `users.watch` + Cloud Pub/Sub. **(Med - standard API, not re-read in this session)**
- **Quotas (current page):** **1,200,000 quota units/min per project; 6,000 units/min per user**; costs: `messages.list` 5, **`messages.get` 20**, `history.list` 2, `threads.get` 40, `drafts.create` 10, `messages.send` 100; a **daily threshold of 80,000,000 units per project before billing applies** ("billing details later in 2026"); 500 recipients per message. **(High - but note this is a 2026 change worth re-checking before building)**
- **Backfill estimate [ESTIMATE]:** 50,000 sent messages x 20 units = 1.0M units -> at 6,000 units/min/user ~ **2.8 hours per mailbox**; and the 80M/day project threshold equals only ~80 such mailbox backfills per day before billing starts.
- **Policy:** Google Workspace API User Data and Developer Policy (updated 2026-09-03) forbids "using user data to create, train, or improve a machine learning or artificial intelligence model **beyond that specific user's personalized model**" - per-user persona models are allowed, cross-customer/global models are not; humans may not read user data except with consent, for security, legal compliance or aggregated/anonymised operations; restricted scopes (Gmail read) require a periodic **CASA** security assessment with a Letter of Assessment from a Google-designated assessor. The policy also points to Google's terms prohibiting "scraping, building databases (including databases for model training purposes), or otherwise creating permanent copies of Google User data" beyond cache limits - **needs legal review against a long-term persona/memory store**. **(High for quoted text; applicability = legal question)**
- **Google Chat API:** `spaces.messages.list` for spaces the user belongs to (user-auth scopes) **[UNVERIFIED scopes/quotas in this session]**.

### G2. Slack
- **Rate limits (since 2025-05-29):** for **commercially distributed apps not listed in the Slack Marketplace**, `conversations.history` and `conversations.replies` drop to **1 request per minute with at most 15 objects per request** for newly created apps and for *new installations* of existing unlisted apps; internal customer-built apps keep 50+ requests/min and 1,000 messages per request; Marketplace apps are unchanged. **(High)**
- **Slack API Terms of Service (effective 2025-10-10):** "you may not: (A) **use API Data to train a large language model**; (B) **bulk export** Slack message and file data except where expressly allowed by an additional agreement" (e.g., Discovery API for approved compliance use cases); and "you may not create **persistent copies, archives, indexes or long-term data stores** of other organisations' API Data" - only limited, temporary caching essential to immediate operation, deleted promptly. **(High)**
- **Implication:** a persistent Slack-derived persona/memory store is **prohibited for a third-party distributed app**. Any Slack support would have to be ephemeral (real-time search at generation time, no retention) or run as a customer-owned internal app under the customer's own agreement - both need legal review. Treat Slack as **out of scope** unless Slack's terms change. Contrast: Microsoft's API terms have no LLM-training ban (section E6).

## H. Ingestion and write-back blueprint

### H1. Permission sets

**MVP (3-month build) - "read-only, delegated, minimal" - maximises the chance of tenant-admin approval**

| Scope (delegated) | Why | Admin consent? |
|---|---|---|
| `openid`, `profile`, `email`, `User.Read` | Sign-in, user identity | No |
| `offline_access` | Background sync without the user present | No |
| `Mail.Read` | Sent Items (+ quoted context, headers, MAPI props, labels) | **Yes in practice** (Microsoft-managed policy) |
| `Chat.Read` | 1:1, group and meeting chats + messages; delegated chat subscriptions | **Yes in practice** |
| `User.ReadBasic.All` | Resolve recipients' names/emails/photos | No |
| *(optional)* `User.Read.All` | Manager chain, job title, department, employee type | **Yes** (by definition) - include only if the customer accepts; otherwise infer relationships (section C2) |

Deliberately **excluded from the MVP:** all application permissions, `Mail.ReadWrite`, `Mail.Send`, `ChatMessage.Send`, `ChannelMessage.Read.All`, `Calendars.*`, `People.Read`, `.Shared` scopes. Write-back happens client-side (Outlook add-in / Teams message extension insert text into the compose box - neighbouring track). Admin grants consent once for the tenant; set the enterprise app to **"Assignment required"** and assign a pilot group so only enrolled users can use it. Back it with: verified publisher, Publisher Attestation, a scope-by-scope justification sheet, static egress IPs, and the express "persona learning" data-use grant required by API ToU s.3(c).

**v1.1-v2 additions (separate "Compose" and "Org" app registrations where possible)**

| Scope | Feature | Notes |
|---|---|---|
| `ChannelMessage.Read.All` (delegated) | Channel posts/replies in persona | Admin consent |
| `Calendars.ReadBasic` -> `Calendars.Read` | Meeting linking, Pillar 2 context | Admin consent in practice |
| `Mail.ReadWrite` | Server-side in-thread drafts (`createReply*`) | Prefer a separate app tier |
| `ChatMessage.Send`, `ChannelMessage.Send` | Post exactly what the user approved (`replyWithQuote` for in-thread) | User click required per send |
| `Mail.Send` | Only if customers ask; user-approved sends | Highest scrutiny |
| `Mail.Read.Shared` | Exec-assistant / shared-mailbox scenarios | Admin consent in practice |
| `Content.Process.User` | Purview DLP evaluation + audit of AI drafts | Strong enterprise feature |
| `OnlineMeetings.Read`, `OnlineMeetingTranscript.Read.All` | Pillar 2 Teams meeting capture (see neighbouring track) | Admin consent |

**Enterprise app-only tier (optional, large tenants):** `Mail.Read` (application) **granted through Exchange RBAC for Applications scoped to an enrolled-users group/admin unit** (remove the unscoped Entra grant); `Chat.Read.All` (application) for the export API (`getAllMessages` filtered by sender) - fast and free, but tenant-wide and not scopable (RSC `ChatMessage.Read.Chat` only covers chats where our Teams app is installed); `User.Read.All` (application) for org sync. Offer only when the customer's security team prefers it.

### H2. Call sequence

**Onboarding (per tenant)**
1. Admin consent via the `/adminconsent` endpoint -> create tenant; record geography -> **pin AWS region** (India -> ap-south-1, US -> us-east-1).
2. `GET /organization` (verified domains); if `User.Read.All`: `GET /users?$select=id,displayName,mail,jobTitle,department,employeeType,userType&$expand=manager($select=id)` -> relationship graph.

**Per-user backfill**
3. User signs in (auth code + PKCE to our confidential backend) -> KMS-encrypted refresh token.
4. Mail: `GET /me/mailFolders('sentitems')/messages/delta?$select=id,subject,from,sender,toRecipients,ccRecipients,bccRecipients,replyTo,sentDateTime,conversationId,conversationIndex,internetMessageId,importance,categories,flag,hasAttachments,isDraft,uniqueBody,body` with `Prefer: odata.maxpagesize=50, IdType="ImmutableId", outlook.body-content-type="text"`; follow `nextLink` to `deltaLink`; in parallel up to 3 list-based historical slices (4 concurrent per mailbox max).
5. Enrichment if needed: `$batch` (20 per batch, 4 concurrent) of `GET /me/messages/{id}?$select=uniqueBody,internetMessageHeaders&$expand=singleValueExtendedProperties($filter=id eq 'String 0x1042' or id eq 'String 0x1039')`.
6. Teams: `GET /me/chats?$top=50&$expand=members` (call `/chats/{id}/members` when > 25 members); then per chat, newest first, `GET /chats/{id}/messages?$top=50&$orderby=lastModifiedDateTime desc`; store a per-chat high-water mark; respect **1 rps per chat and 20 rps per tenant**.
7. Every item passes the pre-ingestion gate (E1) -> redaction (US/India SITs) -> raw store (optional, encrypted) -> features/embeddings with lineage.

**Incremental**
8. `POST /subscriptions`: (a) Outlook Sent Items messages (`created,updated,deleted`, no resource data, ~7-day expiry, renew daily); (b) `/users/{id}/chats/getAllMessages` delegated **with resource data** (encrypted; avoids a GET per message), `lifecycleNotificationUrl`, renew before 3 days. Handle `reauthorizationRequired`, `subscriptionRemoved`, `missed` -> resync.
9. On mail notification -> run the stored `deltaLink` (cheap, idempotent). On Teams notification -> decrypt payload; if subscriptions are unavailable (quota), poll active chats with `$filter=lastModifiedDateTime gt {HWM}`.
10. Safety nets: hourly mail delta; nightly Teams re-scan of the last 7 days to catch edits/deletes; cascade `@removed` / `deletedDateTime` within 24 h.

**Write-back**
11. MVP: client-side insertion (no Graph write scope). Later: `POST /me/messages/{id}/createReply` -> `PATCH` body -> user reviews in Outlook; Teams `POST /chats/{id}/messages` or `/messages/replyWithQuote` only on explicit user action; never autonomous.

### H3. Estimates for the reference user: 50,000 sent emails + 100,000 sent Teams messages [ESTIMATE - assumptions stated]

| Workload | Assumptions | API calls | Backfill time |
|---|---|---|---|
| Mail, bodies in delta pages | 50-100 msgs/page, 1-5 s/page, 4 parallel slices | ~500-1,000 | **~10-40 min** |
| Mail, per-message enrichment needed | +50,000 GETs via 2,500 `$batch` calls; capped by 10k req/10 min | ~51,000 sub-requests | **~50-90 min** |
| Teams, delegated | user's 100k sent ~ 40% of messages in their chats -> ~250k messages; ~1,500 chats; 50/page | ~6,500 | ~6 min theoretical at 20 rps; **~15-45 min realistic** if the tenant is otherwise idle |
| Teams, app-only export (alt.) | `getAllMessages` filtered by sender, 50/page (250/page if honoured) | ~2,000 (~400) | **~5-15 min** (200 rps/tenant ceiling) |
| **Whole tenant, 1,000 such users** | Mail throttles are per mailbox (parallel); Teams delegated reads share **20 rps per tenant** | Teams: ~6.5M calls | Mail: hours. **Teams delegated: ~2-4 days** (less with chat-level dedupe) -> onboard in waves of 100-300 users/day. **Teams app-only export: ~1-3 h.** |
| Steady state | ~50 sent mails + ~150 sent chats per user per day | a few hundred/user/day | Trivial vs limits; use rich Teams notifications to avoid GET-per-message near the 20 rps tenant ceiling |

Rough raw text volume: ~0.2 GB mail text + ~0.1 GB Teams text per such user before embeddings **[ESTIMATE]**.

### H4. Hard blockers and near-blockers

| # | Blocker | Severity | Mitigation |
|---|---|---|---|
| 1 | **Tenant admin consent required** for `Mail.Read`/`Chat.Read` in essentially all target tenants (Microsoft-managed policy since late 2025; enterprises that disable user consent) | Hard | IT-led sales motion; consent request workflow; minimal read-only scope set; verified publisher + attestation + certification |
| 2 | **API ToU s.3(c)**: email APIs limited to sync/backup unless the customer expressly and specifically grants other use | Hard (contractual) | Explicit data-use grant in MSA/DPA and consent screen |
| 3 | **No app-only posting as a user; no Teams drafts** | Hard (design) | Client-side insertion; delegated `ChatMessage.Send` with explicit user action |
| 4 | **No folder-scoped mail permission** (`Mail.Read` = whole mailbox) | Near-hard (trust) | Code-level folder allow-list + customer-visible audit log; RBAC-scoped app-only option |
| 5 | **Teams subscription quotas** (10 per user; 10,000 per org shared by all vendors); chat **delta is app-only and 8-months-only** | Near-hard at scale | Per-user subs for <= low thousands of seats; polling/app-only export above |
| 6 | **Teams read ceilings** (20 rps/tenant delegated; 1 rps/chat) | Scale constraint | Wave onboarding; dedupe shared chats; app-only export for large tenants |
| 7 | **EWS** off by default 2026-10-01, gone 2027-04-01 | Hard (for EWS) | Graph-only |
| 8 | **Encrypted/labelled content** unreadable or excluded by policy | Coverage gap | Label-aware gating; explain coverage to users |
| 9 | **IP-based Conditional Access/CAE** can block background sync from AWS | Deployment blocker in strict tenants | Static egress IPs per region; CA guidance; claims-challenge handling |
| 10 | **In-country expectations** for Indian (and some US) customers | Commercial blocker | Region pinning incl. LLM inference; DR in-country |
| 11 | **Slack ToS** forbids LLM training and persistent stores | Hard (expansion) | Keep Slack out of scope |

No longer blockers: Teams API metering/billing (ended 2025-08-25); Teams "protected API" request form (apparently retired - verify).

## Recommendations for PersonaAgent

**Build decisions for the 3-month MVP**
1. **Graph-only, delegated, read-only.** Ship with `User.Read`, `offline_access`, `Mail.Read`, `Chat.Read`, `User.ReadBasic.All` (+ optional `User.Read.All`). No application permissions, no write/send scopes, no channels/calendar in v1. This is the smallest set that still learns from both email and Teams, and every scope maps to a visible feature.
2. **Client-side write-back.** Insert generated text into the Outlook/Teams compose box (add-in / message extension). Add server-side drafts (`Mail.ReadWrite`) and user-approved sends (`ChatMessage.Send`) later, in a separate "Compose" app registration.
3. **Ingestion engine = throttle-aware scheduler.** Budget per mailbox (10,000 req/10 min, 4 concurrent, Retry-After honoured per `$batch` sub-request) and per tenant for Teams (20 rps chat-message GETs, 1 rps per chat, 5 rps list-chats per user). Outlook via delta + immutable IDs; Teams via per-chat high-water marks + delegated `/users/{id}/chats/getAllMessages` rich notifications; nightly re-scan for edits/deletes. Backfill newest-first so the persona is useful within the first hour.
4. **Thread semantics:** `uniqueBody` (style) + `body` (context), `conversationIndex` length, `PidTagInReplyToId`/`PidTagInternetReferences`, subject prefixes; Teams turn segmentation + `messageReference` quotes; tag *new thread / reply / reply-all / forward / delegation* and audience role on every sample.
5. **Pre-ingestion privacy gate (before persistence):** `MSIP_Labels` label policy (skip "Highly Confidential", skip encrypted), Teams `policyViolation`, US + India SIT detectors replicating Purview definitions (SSN, ITIN, bank/ABA, card with Luhn, Aadhaar with checksum, PAN, GSTIN, voter ID, DL) plus custom detectors for India passport, IFSC/bank account, UPI IDs and phone numbers; secrets/credentials always dropped. Minimise third-party content (colleagues' and clients' messages) to short redacted context windows.
6. **Lineage + deletion:** every derived artefact points to source immutable IDs; cascade deletes within 24 h; tenant legal-hold flag; admin export; immutable access logs. This is an API-terms obligation (s.5), not optional.
7. **Region pinning from day 1:** India tenants -> ap-south-1, US tenants -> us-east-1, including LLM inference, vector DB, logs and backups; per-user routing for Multi-Geo tenants later.

**Go-to-market / trust actions (start in week 1)**
8. Create the Partner Center (AI Cloud Partner Program) account and **verify the publisher**; complete **Publisher Attestation** before the first pilot; plan **Microsoft 365 Certification** (Claranet) to start ~month 3-4 with an annual third-party pentest of the AWS footprint; budget ~USD 15-40k/yr **[ESTIMATE]**.
9. Put an **express "persona learning" data-use grant** (API ToU s.3(c)) into the MSA/DPA and the admin-consent landing page; state no cross-customer training, region, retention, deletion SLA, sub-processors.
10. Admin onboarding kit: admin-consent link, consent-request flow, "assignment required" pilot group, scope justification sheet, static egress IPs + Conditional Access guidance, expected Graph volumes (to pre-empt Defender for Cloud Apps alerts).
11. Offer an **enterprise app-only option** later: Exchange RBAC for Applications-scoped `Mail.Read` + `Chat.Read.All` export for fast Teams backfill in 1,000+ seat tenants.

**Spikes to run in weeks 1-2 (each ~0.5-2 days in a dev tenant)**
12. `uniqueBody` in delta `$select`; `internetMessageHeaders`/`MSIP_Labels` on Sent Items copies; `mailFolders('sentitems')` subscriptions; text-body `Prefer` header on list/delta; pagination depth of `/chats/{id}/messages` on multi-year chats; `getAllMessages` access without any request form; `processContent` licensing/billing; behaviour of encrypted mail via Graph.

**Platform watch**
13. Track Message Center for consent-policy and Teams API changes; design an "Agent 365-ready" v2 (Entra Agent ID, Agent 365 SDK telemetry, Purview audit); consider Copilot Meeting Insights only for Copilot-licensed tenants; expand to Gmail before Slack (budget CASA; Slack out of scope under current terms).

## Risks and watch-outs

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Admin-consent friction lengthens sales cycles; no self-serve virality | High | High | IT-first motion, pilot groups, trust pack, certification |
| Security teams reject `Mail.Read`/`Chat.Read` for an AI start-up (whole-mailbox + colleagues' chats) | Med | High | Read-only minimal set, audit logs to customer SIEM, data minimisation, app-only RBAC option |
| Microsoft tightens consent defaults again / changes or terminates API access (ToU s.6, s.10) | Med | High | Keep scope minimal; diversify (Gmail later); monitor Message Center; maintain Microsoft partner relationship |
| Microsoft ships native "write like me"/memory features in Copilot **[UNVERIFIED specifics]** | Med | High | Differentiate on persona fidelity, cross-surface memory (Pillar 2), governance; consider Agent 365 listing |
| Teams throttling/quotas in 1,000+ seat tenants (20 rps/tenant, 10k shared subscriptions) | High | Med | Wave onboarding, dedupe, rich notifications, app-only export option |
| Delete-propagation or legal-hold failure (contractual + legal exposure) | Med | High | Lineage, 24 h SLA, hold flag, automated tests |
| Persona used for impersonation / BEC | Med | High | No autonomous send, exec personas off by default, audit + watermarking, per-user isolation |
| Over-collection of non-users' personal data (colleagues, clients) | High | High | Context windows only, redaction, configurable to zero, DPIA |
| Indian customers require in-India processing incl. LLM | Med | High | ap-south-1 pinning; confirm model availability (AWS track) |
| IP-based Conditional Access blocks background sync | Med | Med | Static egress IPs, CA documentation, CAE handling |
| Refresh-token expiry/revocation causes silent gaps | High | Med | Per-user health monitor, re-auth nudges, coverage indicator |
| Encrypted/labelled content excluded -> weaker personas for executives (who label most) | Med | Med | Explain coverage; allow user-approved samples |
| Certification cost/time diverts a small team | Med | Med | ACAT automation, start after MVP, reuse SOC 2 evidence |
| Undocumented API behaviours (uniqueBody in delta, Sent-Items headers, pagination depth) | Med | Med | Week-1 spikes, fallbacks designed in |
| Expansion constraints (Slack ToS; Gmail CASA and quotas) | High | Med | Gmail first; Slack out unless terms change |

## Open questions / could not verify

Session note: the shared web-search budget was exhausted mid-research; remaining facts were verified by fetching primary URLs directly. Items below could not be confirmed and should be tested or checked by the named track.

1. **`uniqueBody` inside a delta `$select`** - not stated in docs; test (fallback: per-message `$batch`).
2. **`internetMessageHeaders` (incl. `In-Reply-To`, `References`, `MSIP_Labels`) on the Sent Items copy** - not documented; test; MAPI extended properties are the fallback for threading.
3. **Folder-scoped Outlook subscriptions on Sent Items** - docs list Inbox examples only; test.
4. **Teams "protected API" request form** - the dedicated page is gone (404) and export docs no longer mention a form; confirm with a fresh tenant that `getAllMessages` works with only `Chat.Read.All` + admin consent.
5. **Graph Data Connect current price** - the Azure pricing page didn't render a number; USD 0.75/1K objects is from Microsoft's 2023 announcement.
6. **Microsoft 365 Certification fees** - Claranet quotes per SOW; the USD 15-40k/yr figure is an estimate.
7. **Purview `processContent` licensing/billing for third-party apps** - API and permissions verified; commercial terms not.
8. **Sensitivity-label catalogue API** (endpoint, v1.0 vs beta, permission) for mapping label GUIDs to names - not re-verified.
9. **Exact property set of `User.ReadBasic.All`**, least-privileged permission for `/organization` and `/me/directReports`, and `preferredDataLocation` routing semantics.
10. **Org-data completeness statistics** (manager/title coverage in real tenants) - none found; treat as unknown.
11. **Pagination depth of delegated `/chats/{id}/messages` on very old chats** - only a Microsoft Q&A answer claims a cut-off.
12. **Teams subscription lifetime wording** (60 min on the Teams overview vs 4,320 min with lifecycle URL in the subscription reference).
13. **Export API page size** (recommended up to 250 vs documented `$top` 50).
14. **What Graph returns for encrypted (IRM/OME) messages** and whether delegated users' rights let us read them.
15. **Microsoft Copilot native personalisation/"sound like me" features** - competitive question for the market track.
16. **Agent 365 per-user price** - licensing confirmed, price not captured.
17. **India legal specifics** (DPDP Rules timelines, UIDAI Aadhaar masking/storage rules, CERT-In log-retention, RBI/SEBI localisation) and **US sectoral rules** - legal/security tracks.
18. **Google Chat API scopes/quotas**, Gmail post-threshold billing ("details later in 2026"), CASA cost/tier.
19. **"Microsoft MCP Server for Enterprise"** for Graph - listed on the Graph docs hub; not evaluated.
20. **MAPI tag `0x0036` (classic sensitivity)** and Outlook `PidTagLastVerbExecuted` values in Exchange Online via Graph - from MAPI references, not re-tested.

## Sources

All accessed 2026-10-05/06 unless noted. "Updated" dates are from page metadata where available.

**Microsoft Graph - Outlook mail**
- message: delta (updated 2026-06) - https://learn.microsoft.com/en-us/graph/api/message-delta?view=graph-rest-1.0
- message resource type (updated 2026-04) - https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
- List messages (updated 2026-06) - https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0
- Create/send messages guidance - https://learn.microsoft.com/en-us/graph/outlook-create-send-messages
- MS-OXOMSG PidTagConversationIndex - https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxomsg/9e994fbb-b839-495f-84e3-2c8c02c7dd9b
- Tracking Conversations (conversation index structure) - https://msdn.microsoft.com/en-us/library/cc765583.aspx
- PidTagInReplyToId - https://learn.microsoft.com/en-us/previous-versions/office/developer/office-2010/cc839776(v=office.14)
- PidTagInternetReferences - https://msdn.microsoft.com/en-us/library/office/cc839592
- PidTagLastVerbExecuted - https://msdn.microsoft.com/library/cc841968.aspx
- Exchange Online limits (sending limits; updated 2026-09) - https://learn.microsoft.com/en-us/office365/servicedescriptions/exchange-online-service-description/exchange-online-limits
- RBAC for Applications in Exchange Online (updated 2026-08) - https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac

**Microsoft Graph - throttling, batching, notifications**
- Throttling limits - https://learn.microsoft.com/en-us/graph/throttling-limits (Outlook/Teams/subscription includes: https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/includes/throttling-outlook.md, https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/includes/throttling-teams.md, https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/includes/throttling-subscription-services.md)
- Throttling guidance - https://learn.microsoft.com/en-us/graph/throttling
- JSON batching - https://learn.microsoft.com/en-us/graph/json-batching
- Change notifications overview (updated 2026-04) - https://learn.microsoft.com/en-us/graph/change-notifications-overview
- subscription resource (lifetimes, latency; updated 2026-09) - https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0
- Teams chat/channel message notifications - https://learn.microsoft.com/en-us/graph/teams-changenotifications-chatmessage
- Teams change notifications overview (updated 2026-09) - https://learn.microsoft.com/en-us/graph/teams-change-notification-in-microsoft-teams-overview

**Microsoft Graph - Teams**
- List chats - https://learn.microsoft.com/en-us/graph/api/chat-list?view=graph-rest-1.0
- List messages in a chat - https://learn.microsoft.com/en-us/graph/api/chat-list-messages?view=graph-rest-1.0
- chats: getAllMessages (updated 2026-09) - https://learn.microsoft.com/en-us/graph/api/chats-getallmessages?view=graph-rest-1.0
- getAllMessages delta (8-month window) - https://learn.microsoft.com/en-us/graph/api/chatmessage-delta?view=graph-rest-1.0
- List channel messages - https://learn.microsoft.com/en-us/graph/api/channel-list-messages?view=graph-rest-1.0
- chatMessage resource - https://learn.microsoft.com/en-us/graph/api/resources/chatmessage?view=graph-rest-1.0
- Send message in a chat - https://learn.microsoft.com/en-us/graph/api/chat-post-messages?view=graph-rest-1.0
- replyWithQuote - https://learn.microsoft.com/en-us/graph/api/chatmessage-replywithquote?view=graph-rest-1.0
- Export content with the Teams Export APIs (updated 2026-08) - https://learn.microsoft.com/en-us/microsoftteams/export-teams-content
- Payment models / licensing (deprecated; metering ended 2025-08-25) - https://learn.microsoft.com/en-us/graph/teams-licenses and source https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/concepts/teams-licenses.md
- Metered APIs list (updated 2026-04) - https://learn.microsoft.com/en-us/graph/metered-api-list
- Microsoft Q&A on export billing (2026) - https://learn.microsoft.com/en-us/answers/questions/5828700/payment-for-teams-export-apis-getallmessages-and-g
- Microsoft Q&A on large chat export - https://learn.microsoft.com/en-us/answers/questions/5639321/how-to-work-around-microsoft-graph-api-limitations
- Empowering.cloud on MC1122144 - https://empowering.cloud/microsoft-ends-charges-for-select-teams-metered-graph-apis/
- Veeam KB4322 (updated 2025-08-28) - https://www.veeam.com/kb4322
- Commvault note on Export API - https://community.commvault.com/platform-updates-47/microsoft-teams-chat-backup-simplified-export-api-now-enabled-by-default-11431

**Microsoft Graph - directory, people, bulk**
- Permissions reference - https://learn.microsoft.com/en-us/graph/permissions-reference
- List manager - https://learn.microsoft.com/en-us/graph/api/user-list-manager?view=graph-rest-1.0
- List people (maintenance mode) - https://learn.microsoft.com/en-us/graph/api/user-list-people?view=graph-rest-1.0
- Graph Data Connect overview - https://learn.microsoft.com/en-us/graph/data-connect-concept-overview
- GDC datasets, regions, sinks - https://learn.microsoft.com/en-us/graph/data-connect-datasets
- GDC pricing page - https://azure.microsoft.com/en-us/pricing/details/graph-data-connect/
- GDC pricing update (2023) - https://devblogs.microsoft.com/microsoft365dev/microsoft-graph-data-connect-pricing-updates-2
- Graph docs hub (MCP Server for Enterprise listing) - https://learn.microsoft.com/en-us/graph/

**Entra ID: consent, publisher, tokens, agents**
- Configure user consent - https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent
- Manage app consent policies (Microsoft-managed policy list; updated 2026-08) - https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/manage-app-consent-policies
- MC1163922 (Secure by Default for Exchange and Teams APIs) - https://mc.merill.net/message/MC1163922
- AdminDroid summary of MC1163922 - https://blog.admindroid.com/microsoft-requires-admin-consent-for-apps-accessing-exchange-teams-apis/
- AppGov on MC1097272 - https://www.appgovscore.com/blog/microsoft-disables-user-consent-by-default-are-you-ready-for-mc1097272
- Admin consent workflow - https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-admin-consent-workflow
- Publisher verification - https://learn.microsoft.com/en-us/entra/identity-platform/publisher-verification-overview
- Refresh tokens - https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens
- Continuous access evaluation (updated 2026-09) - https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-continuous-access-evaluation
- Entra Agent ID - https://learn.microsoft.com/en-us/entra/agent-id/what-are-agent-identities

**Microsoft 365 App Compliance**
- Program overview - https://learn.microsoft.com/en-us/microsoft-365-app-certification/overview
- Certification framework (updated 2026-09) - https://learn.microsoft.com/en-us/microsoft-365-app-certification/docs/certification
- Claranet certification service - https://www.claranet.com/uk/microsoft-365-app-compliance-certification/

**Purview, labels, residency, terms**
- SIT entity definitions index - https://learn.microsoft.com/en-us/purview/sit-sensitive-information-type-entity-definitions
- India Aadhaar SIT - https://learn.microsoft.com/en-us/purview/sit-defn-india-unique-identification-number
- India PAN SIT - https://learn.microsoft.com/en-us/purview/sit-defn-india-permanent-account-number
- US SSN SIT - https://learn.microsoft.com/en-us/purview/sit-defn-us-social-security-number
- MIP SDK label metadata (MSIP_Labels email header; updated 2026-09) - https://learn.microsoft.com/en-us/information-protection/develop/concept-mip-metadata
- Purview processContent (Graph v1.0) - https://learn.microsoft.com/en-us/graph/api/userdatasecurityandgovernance-processcontent?view=graph-rest-1.0
- M365 data residency overview (updated 2026-09) - https://learn.microsoft.com/en-us/microsoft-365/enterprise/m365-dr-overview
- Product Terms data residency (updated 2026-09) - https://learn.microsoft.com/en-us/microsoft-365/enterprise/m365-dr-product-terms-dr
- Microsoft APIs Terms of Use (Oct 2025) - https://learn.microsoft.com/en-us/legal/microsoft-apis/terms-of-use
- Microsoft 365 Copilot APIs Terms of Use (preview, Dec 2025) - https://learn.microsoft.com/en-us/legal/m365-copilot-apis/terms-of-use

**Platform: EWS, Copilot APIs, Agent 365**
- MC1227454 EWS retirement update (2026-02-05) - https://mc.merill.net/message/MC1227454 ; Microsoft deprecation page - https://learn.microsoft.com/exchange/clients-and-mobile-in-exchange-online/deprecation-of-ews-exchange-online
- Copilot APIs overview (updated 2026-08) - https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/copilot-apis-overview
- Copilot Retrieval API (updated 2026-08) - https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/retrieval/overview
- Agent 365 overview (GA 2026-05-01) - https://learn.microsoft.com/en-us/microsoft-agent-365/overview
- Agent 365 partner agents (updated 2026-10-01) - https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents

**Google and Slack**
- Gmail API quotas - https://developers.google.com/workspace/gmail/api/reference/quota
- Google Workspace API User Data and Developer Policy (updated 2026-09-03) - https://developers.google.com/workspace/workspace-api-user-data-developer-policy
- Slack rate-limit changes for non-Marketplace apps (2025-05-29) - https://docs.slack.dev/changelog/2025/05/29/rate-limit-changes-for-non-marketplace-apps
- Slack API Terms of Service (effective 2025-10-10) - https://slack.com/terms-of-service/api
