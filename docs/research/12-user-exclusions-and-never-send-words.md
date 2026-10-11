# 12 - User-controlled exclusions ("do not use") and the never-send words list

**Track:** User-facing data controls (PersonaAgent research series, doc 12)
**Prepared:** 2026-10-09 (research cut-off). Facts were checked against primary sources (Microsoft Learn, AWS documentation, Unicode specifications, project repositories) where a URL is cited. Anything not verified is labelled **[UNVERIFIED]** or **[ESTIMATE]**.
**Scope:**
1. A portal screen where users search their own 1:1 chats (by person), group chats (by name), email correspondents (by address), email threads and meetings, and mark them **"do not use at all"**. This works at onboarding, before content is ingested, and later through retroactive purge.
2. A per-user **"never-send words"** list: terms that are never sent to any AI model or stored, and optionally never appear in outgoing drafts.

**Builds on:**
- doc 01: Graph endpoints, throttling, subscriptions;
- doc 10: pipeline stages S0-S13, L0/L1/L2 levels, Tier C dictionaries, vault;
- doc 05 §6.5: lineage deletion cascade;
- doc 04 §2.3: S3 Vectors layout.

Facts verified there are cited, not re-researched.
**Founder decisions applied:** M365 mid-market/enterprise; US + India; 3-6 engineers, ~3-month MVP; work-only recorder; Phase-1 redaction for US + India.
**Naming:** "doc NN" means `docs/research/NN-*.md`. Top-level architecture documents are named in full (e.g. `02-solution-architecture.md`).

**Confidence legend:** **(High)** = read in a current primary source this session; **(Med)** = primary but ambiguous, or strong secondary; **(Low)** = inference or secondary; "test" = needs a test-tenant check.

---

## Executive summary

**Verified facts that shape the design**
- **Metadata-only review is possible.**
  - `GET /me/chats` (`Chat.ReadBasic`) lists 1:1, group and meeting chats without content, **including hidden ones**. It returns up to 25 members per `$expand` and supports recency ordering.
  - Sent Items headers come from the existing delta stream with a body-less `$select`.
  - Meetings come from `calendarView` (`Calendars.ReadBasic`, admin consent).
- **The portal searches our own cached list.** Graph has **no `$search` on chats**, and `topic` is null for 1:1 and unnamed group chats.
- **There is no "list my correspondents" API.**
  - KQL `$search` returns at most **1,000 results**.
  - The People API is in **maintenance mode**.
  - Search API people results are relevance-ranked (25 by default).
  - We build our own index from Sent Items headers.
- **Notifications differ by workload.**
  - Teams notifications expose `chats('{chatId}')/messages('{id}')` in clear text, so excluded chats are dropped **before decryption**.
  - Outlook notifications expose only the message ID. Mail needs a header-only payload or a header GET before any body fetch.
- **AWS managed filters can't hold per-user lists.**
  - Bedrock Guardrails word filters take ≤ 10,000 words (fixed) and ≤ 3-word phrases, match whole words without plurals, and can only **BLOCK or NONE**. Each account-Region gets **100 guardrails, and that is not adjustable**.
  - Transcribe vocabulary filters accept **single words only**, with **100 filters per account**.
  - Never-send matching must therefore be **our own in-memory matcher that runs before any model**.
- **S3 Vectors has no delete-by-filter.** `DeleteVectors` takes ≤ 500 keys, `ListVectors` can't filter, and query filters cap at **100 constraints**. Purge must follow lineage, and the app must post-filter results.
- **Unicode traps (reproduced locally).**
  - Python `re` word boundaries split "हिंदी किताब" into 5 fragments.
  - NFKC keeps zero-width characters and doesn't fold Devanagari digits or Cyrillic look-alikes.
  - We need explicit stripping, ICU segmentation (UAX #29) and UTS #39 skeletons.
- **Precedent.**
  - Microsoft separates "stop using" from "delete" in Copilot Memory.
  - Microsoft publishes propagation times: DLP ≤ 4 h; Restricted Content Discovery > 1 week for large sites.
  - No per-person or per-chat user exclusion was found in Copilot, Gmail or Superhuman. Fyxer has address and domain rules.

**Recommended design (§9)**
1. **Onboarding.** `REVIEW_PENDING` → header pass (chats, mail headers, calendar) → per-user Sources index → user review (Finish or explicit Skip) → **backfill of allowed sources only**.
2. **Rules.**
   - Types: person (OID/address), domain, 1:1/group/meeting chat, email thread, meeting occurrence or series, and channel (later).
   - Tenant and user rules combine, and deny always wins.
   - "Do not use" removes style learning, memory, retrieval and drafting context, and leaves no stub.
3. **Enforcement, in pipeline order:**
   - drop at intake;
   - two-phase fetch;
   - quoted-history scan;
   - a new **S2.5 never-send gate** before any NER, embedding or LLM;
   - S9 re-check;
   - retrieval pre-filter and post-filter;
   - output gate;
   - lineage purge (logical ≤ 1 min, physical ≤ 24 h; legal hold defers only the physical purge);
   - no identifiers in logs.
4. **Never-send words.**
   - The list is encrypted in the vault, and matches become `⟦NS_id⟧` tokens.
   - Users confirm variants: inflections, Hinglish folds, local Roman↔Devanagari, confusables.
   - `allow_in_drafts` is off by default, and a client-side check scans the output.
   - Adding a term triggers a retroactive scrub.
   - Audio is the stated exception: speech-to-text hears spoken terms.
5. **Effort.** ≈ 12.5 engineer-weeks for the MVP cut and ≈ 19 for the full design (±30%).

---

## Contents
1. Teams chats and channels
2. Change notifications: drop before decryption?
3. Outlook mail: correspondent and thread list
4. Meetings and transcripts
5. Never-send building blocks (Guardrails, Transcribe, Purview)
6. Matching engine (normalisation, Unicode, Devanagari, transliteration)
7. S3 Vectors: query-time exclusion and purge
8. Precedents
9. Recommended design
10. Effort estimate
11. Open questions / could not verify
12. Sources

---

## 1. Teams chats and channels

### 1.1 Listing the user's chats (metadata only)

| Item | Verified fact | Conf. |
|---|---|---|
| Call and permission | `GET /me/chats`. Least privileged: **`Chat.ReadBasic`** ("read the members and descriptions of one-to-one and group chat threads"). It does not require admin consent by definition and is not on Microsoft's managed block list (doc 01 D2). `Chat.Read`/`ReadWrite` also work | High |
| Query options | `$expand` = `members` or `lastMessagePreview`; `$top` ≤ **50**; `$orderby` **only** `lastMessagePreview/createdDateTime desc`; `$filter` (properties not listed). "The other OData query parameters are not currently supported", so there is **no `$search`** | High |
| Members | `$expand=members` returns **≤ 25 members per chat**. Use `GET /chats/{id}/members` for larger chats | High |
| Filters | Documented: `installedApps/any(...)` (v1.0) and, in beta only, `members/any(o: o/displayname eq 'Peter Parker')` (exact display name). Filters on `chatType`/`topic` are not documented **[UNVERIFIED]** | High / Low |
| Hidden chats | **Returned**, with `viewpoint.isHidden: true`. The `viewpoint` property appears only in delegated calls and only on List chats | High |
| `topic` | "**Only available for group chats**". It is null for 1:1 and unnamed group chats (Teams labels those with participant names). Meeting chats show the meeting subject | High / Med (client label) |
| Types, links | `chatType` = `oneOnOne` / `group` / `meeting`. `onlineMeetingInfo` = `calendarEventId`, `joinWebUrl`, `organizer`. `lastUpdatedDateTime` changes on rename or membership change. IDs are opaque | High |
| Throttling | 5 requests/s per user for list/get chats (doc 01 B5): seconds for 1,000 chats | High |

**Consequence:** the portal searches a **cached metadata list**: chat ID, type, topic or computed label, members, recency and `isHidden`. Never request `lastMessagePreview`, because it contains message text.

### 1.2 Channels (future)

| Call | Permission | Behaviour | Conf. |
|---|---|---|---|
| `GET /me/joinedTeams` | `Team.ReadBasic.All` | No OData options. Only id, displayName, description, isArchived and tenantId are populated. Host teams of shared channels are not returned | High |
| `GET /teams/{id}/channels` | `Channel.ReadBasic.All` | Supports `$filter` on `membershipType`. Private and shared channels appear only to their members | High |

Reading channel posts needs `ChannelMessage.Read.All` (admin consent), which is not in the MVP. Channel rules are therefore a data-model placeholder for now.

---

## 2. Change notifications: drop before decryption?

| Source | Clear text | Encrypted | Conf. |
|---|---|---|---|
| Teams chat message | `resource` = `chats('{chatId}')/messages('{id}')`, `resourceData.@odata.id`, `changeType`, `subscriptionId`, `tenantId`, `clientState` | The whole `chatMessage` (`$select` is not supported) | High |
| Teams channel message | `teams('{id}')/channels('{id}')/messages('{id}')[/replies('{id}')]` | The whole message | High |
| Outlook message | `Users('{id}')/messages('{id}')` and `resourceData` (id, etag) **only** | Only properties in the subscription `$select`. `Body`/`UniqueBody`, `$top`, `$skip` and `$orderby` are not allowed | High |

- **Teams: yes.** The intake Lambda drops notifications for excluded chats **without decrypting them**.
- **Mail: no.** Use one of two options; either gives a **two-phase fetch** at runtime (headers → decision → body).
  1. A header-only rich subscription: `me/mailFolders('SentItems')/messages?$select=conversationId,toRecipients,ccRecipients,bccRecipients,from,sender,sentDateTime,internetMessageId`. The well-known folder-name form is documented for `Drafts`; **test** `SentItems` (Med).
  2. Basic notifications, followed by a header `GET` before any body fetch.
- **Don't filter at subscription level.** Per-chat subscriptions consume the **10,000-per-organisation** Teams quota (doc 01 B3). Use the user-level `/users/{id}/chats/getAllMessages` subscription (`Chat.Read`) and drop at intake. Encoding exclusions in an Outlook `$filter` is brittle.
- Notifications and delta/backfill call the **same** exclusion check.

---

## 3. Outlook mail: correspondent and thread list

There is **no Graph API that lists everyone a user has corresponded with**; none was found.

| Option | Call | Facts | Fit |
|---|---|---|---|
| **A. Sent Items header index (recommended)** | `GET /me/mailFolders('sentitems')/messages/delta?$select=toRecipients,ccRecipients,bccRecipients,conversationId,sentDateTime,from,sender,internetMessageId` with `Prefer: IdType="ImmutableId"` and `odata.maxpagesize` (or a list call with `$top` ≤ 1,000) | No bodies, only `Mail.ReadBasic`-level fields. Mail limits are per mailbox: 10,000 requests/10 min, 4 concurrent. `$batch` takes ≤ 20 sub-requests, each throttled individually **(High)** | Complete. Aggregates by address, domain and `conversationId`. 50k items ≈ 50-100 pages = **minutes [ESTIMATE]** |
| B. Inbox headers (optional) | Same call on Inbox, last N months | Adds people who write but never get a reply | Optional |
| C. KQL `$search` | `$search="recipients:ana@client.com"` (also `to:`, `cc:`, `bcc:`, `from:`, `participants:`, `subject:`) | **≤ 1,000 results**, sorted by sent date **(High)**. Recipient lambda `$filter`s are not documented **[UNVERIFIED]** | Impact previews only; never the purge source |
| D. People API | `GET /me/people?$search=` | **Maintenance mode**; fuzzy matching; `People.Read` needs admin consent **(High)** | Type-ahead only |
| E. Search API (people) | `POST /search/query`, `entityTypes:["person"]` | Mailbox provenance includes people you emailed, received mail from, met and chatted with. Returns 25 results by default **(High)**. The `People.Read` scope is not restated on the page **(Med)** | Type-ahead only |

**Threads and passes:**
- Thread rules use `conversationId`. Purge looks the ID up in **our lineage**, not in Graph. `$filter=conversationId eq` was not re-verified **[UNVERIFIED]**.
- The existing delta (doc 01 A1) runs first as a fast **header pass**.
- The **body pass** starts only once the review is finished or explicitly skipped (§9.2).
- No new mail scopes are needed.

---

## 4. Meetings and transcripts

| Need | Call | Permission | Facts | Conf. |
|---|---|---|---|---|
| List meetings | `GET /me/calendarView?startDateTime=…&endDateTime=…&$select=subject,organizer,attendees,start,end,isOnlineMeeting,onlineMeeting,seriesMasterId,type,iCalUId,sensitivity` | `Calendars.ReadBasic` (no body or attachments) | Returns occurrences, exceptions and single instances. `type` is singleInstance, occurrence, exception or seriesMaster. Also returns `seriesMasterId`, a per-occurrence `iCalUId`, `onlineMeeting.joinUrl` and `sensitivity` | High |
| Event → meeting chat | `GET /me/onlineMeetings?$filter=JoinWebUrl eq '{url}'` | `OnlineMeetings.Read` | Accepts "both the organizer's and the invited attendee's user token". `chatInfo.threadId` is the meeting chat ID | High |
| Chat → event | `chat.onlineMeetingInfo.calendarEventId` | `Chat.ReadBasic` | The reverse mapping | High |
| One meeting's transcripts | `GET /me/onlineMeetings/{id}/transcripts` | Delegated `OnlineMeetingTranscript.Read.All` (admin consent) | Fails for API-created meetings without a calendar event and after the meeting expires. The tenant must enable transcript API access | High |
| All transcripts for an organiser | `getAllTranscripts(meetingOrganizerUserId=…)` (+ delta) | **Application only** | Only scheduled meetings **organised by that user**; **no channel meetings** | High |

**How meeting rules apply:**
- A meeting rule is keyed on the event or series identity, so it applies whichever capture path produces the content.
- It covers the meeting chat, the transcript and any recorder session that the calendar-bounded assembler links to the event (`02-solution-architecture.md` §6.2-6.3).
- Events marked `sensitivity` = private stay excluded by default, following the recorder rule in doc 06.

---

## 5. Never-send building blocks

### 5.1 Amazon Bedrock Guardrails word filters (all High)
- **Limits:** ≤ **10,000** custom words or phrases (quota "Words per word policy", not adjustable); each ≤ 3 words and ≤ 100 characters.
- **Matching:** "**case-insensitive whole-word and whole-phrase matching**". "`competitor` does not match `competitors`", so there is no stemming or plural handling.
- **Actions:** **`BLOCK` or `NONE`**, set separately for input and output. **Words cannot be masked**; masking exists only for PII entities and regexes.
- **Standalone use:** `ApplyGuardrail` evaluates text "without invoking the foundation models". Its response echoes the matched word in `customWords[].match`.
- **Quotas:** **100 guardrails per account per Region, not adjustable.** ApplyGuardrail allows 100 requests/s in us-east-1 and ap-south-1.

**Verdict:** Guardrails cannot be the never-send mechanism.
- It blocks the whole request rather than stripping the term.
- It can't scale to per-user lists (100 guardrails per account-Region).
- It only sees text that has already reached Bedrock.
- It keeps a second plaintext copy of the list.

At most, use it in enterprise cells to detect a tenant-level Tier C list (≤ 10,000 terms) in model output.

### 5.2 Amazon Transcribe vocabulary filters
- **Modes:** `mask` (`***`), `remove` or `tag`; works in batch and streaming.
- **Matching:** case-insensitive, "only exact word matches", and never inside longer words. **(High)**
- **Limits:** "**Each entry can only contain one word (no spaces)**". **100 filters per account**, ≤ 50 KB each, one language per filter. **(High)**
- **Indian languages:** en-IN and hi-IN transcribe in batch and streaming. PII redaction works for en-IN but not hi-IN **(High)**. Vocabulary-filter support for hi-IN is not stated: **test (Med)**.

**Verdict:** these filters can't serve per-user lists or phrases, and any spoken term has already reached the STT model. The honest promise for audio is "redacted in memory before anything is stored or sent onward". A meeting-level exclusion is stronger: the assembler deletes that meeting's audio **before** transcription.

### 5.3 Purview keyword dictionaries (precedent)
- **Size:** ≤ **1 MB post-compression per tenant** across all dictionaries (≈ 1M characters).
- **Languages:** any; string match is recommended for CJK. **(High)**
- **Scope:** these are tenant-wide admin artefacts; no per-user concept was found.

---

## 6. Matching engine

### 6.1 Engines
- **Aho-Corasick (`pyahocorasick`)**: BSD-3, Unicode-aware, picklable automaton, runtime linear in input length. Used for **per-user lists**. **(High)**
- **Vectorscan**: BSD-3 fork of Hyperscan (Intel releases after 5.4 are closed-source); supports ARM/Graviton. Used for **tenant Tier C dictionaries** of 10k+ terms. **(High)**

Both match literals on a **normalised shadow copy with an offset map**, so spans are masked in the original text.

### 6.2 Normalisation (identical for terms and text)
1. **Strip invisible characters.** Remove Default_Ignorable code points (U+200B-D, U+2060, U+00AD, U+FEFF, variation selectors, tags U+E0000-E007F) and bidi controls (U+202A-E, U+2066-9, U+200E/F, U+061C). **NFKC keeps U+200B/U+200D** (verified locally).
2. **NFKC.** Full-width forms and ligatures fold. Precomposed nukta U+0958 becomes identical to क + ़ (verified).
3. **Full case folding** ("Straße" → "strasse").
4. **Digits.** Map Devanagari digits to ASCII; NFKC leaves १२३ unchanged (verified).
5. **Whitespace.** Collapse runs of whitespace. Codenames also match a "squashed" form (`project-falcon` = `projectfalcon`).
6. **Confusables.** Use the UTS #39 v18.0.0 `skeleton`: NFD → remove Default_Ignorable → confusables map → NFD. Strings are "confusable if and only if skeleton(X) = skeleton(Y)"; skeletons are for internal comparison only. NFKC does **not** unify Cyrillic а with Latin a (verified). Apply to terms of ≥ 4 characters.
7. **Optional Devanagari folds:**
   - nukta folding for क़ ख़ ग़ ज़ फ़ only (ड़ and ढ़ are distinct letters, so don't fold them);
   - chandrabindu → anusvara.

### 6.3 Word boundaries
- **Python's `re` `\b` is wrong for Devanagari.** Locally (Python 3.14.7, Unicode 16.0), `re.findall(r"\b\w+\b", "हिंदी किताब")` returns 5 fragments. Matras and anusvara (categories Mc/Mn) are not word characters to `re`. **(High - reproduced)**
- **Use ICU / UAX #29 segmentation.** Rule WB4 ignores Extend/Format characters, and Extend includes `Grapheme_Extend` and Spacing_Mark, so matras stay attached. UAX #29 lists Devanagari among scripts where default boundaries are "usually adequate". **(High for the rules / Med for the Devanagari reading)**
- **Boundary rules for hits:**
  - Exact and variant hits must start and end on a word boundary.
  - Substring mode, meant for distinctive codenames, skips the check.
  - Name terms allow glued honorifics and possessives (`ji`, `jee`, `sahab`, `bhai`, `'s`).

### 6.4 Local Roman ↔ Devanagari variants (terms never reach an LLM)
- **`indic_transliteration`**: MIT; deterministic schemes (ITRANS, HK, IAST, Velthuis, OPTITRANS). `to_lay_indian` turns "kRShNa" into "krishna". It handles casual spellings poorly, and some maintenance signals are dated. **(High)**
- **AI4Bharat IndicXlit**: MIT ("code (and models)"); ~11M-parameter transformer; Roman ↔ native script, including Hindi; trained on Aksharantar (26M pairs); package `ai4bharat-transliteration`. CPU/offline inference is not documented. **(High / test)**
- **Our Hinglish folds**: aa→a, ee/ii→i, oo/uu→u, w→v, ph→f, and doubled consonants collapsed. These extend doc 10 §6.7 (aa/a, ee/i, v/w, sh/s); keep sh/s optional.

**Policy decision for the founders.** IndicXlit is itself a small ML model.
- Running it offline inside the vault boundary keeps terms away from LLMs and third parties.
- Whether that satisfies "never sent to any AI model" is a policy call. The fallback is rules only.
- Either way, the **user confirms** each variant before it is saved.

### 6.5 Transcripts
- **Fuzzy matching:** transcript mode adds bounded fuzziness for terms of ≥ 6 characters, to catch ASR drift such as "falkon". It allows edit distance ≤ 1 on the folded form and uses English phonetic keys.
- **Audio muting:** word timestamps let us mute matched spans if audio snippets are retained (`02-solution-architecture.md` §8.4).
- **Speaker names:** names in Teams transcripts are matched too.

---

## 7. S3 Vectors: query-time exclusion and purge (High unless noted)

| Capability | Fact |
|---|---|
| Operators | `$eq` (on an array value: true if any element matches), `$ne`, `$gt/$gte/$lt/$lte`, `$startsWith`, `$in`, `$nin`, `$exists`, `$and`, `$or` |
| Pre-filter | ENHANCED indexes apply the filter **before** ANN search. They are the default for buckets created on or after **30 Sep 2026** |
| Filter size | ≤ **100 constraints** per query; each `$in` value counts as one |
| Delete | `DeleteVectors` works **by key only**, 1-500 keys per call; there is **no delete-by-filter** |
| Enumerate | `ListVectors` has **no filter**; ≤ 1,000 vectors per page; ≤ 16 parallel segments |
| Writes | 1,000 requests/s and 2,500 vectors/s per index (doc 04) |

**Consequences:**
1. Query filters are only a **purge-window backstop**: 100 constraints is too few, and `$nin` behaviour on array values is **[UNVERIFIED]**.
2. Purge follows **lineage**, using deterministic keys (`{kind}:{hmac(sourceItemId)}:{chunk}`).
3. The app **post-filters every hit** against the active exclusion set before the prompt is assembled.

---

## 8. Precedents

| Product | Control | Lesson | Conf. |
|---|---|---|---|
| M365 Copilot - Restricted Content Discovery | Admin, site-level. Hides a SharePoint site from org-wide search and Copilot without changing permissions. Sites with > 500,000 items can take **more than a week** to update | Exclusion ≠ access removal; propagation time is published | High |
| Purview DLP for Copilot | Excludes labelled files and emails (emails sent after 1 Jan 2025; invites not covered). Blocks prompts containing SITs. Excludes **external email using sender-domain metadata only** (preview). Policy changes take up to **4 h** | Metadata-only exclusion; a stated SLA | High |
| Copilot Memory | Users can delete saved memories, but deleting a chat or turning memory off **doesn't delete** derived memories. Chat-history details purge 7 days after all source chats are deleted, or 30 days after chat history is turned off. Purview retention doesn't apply; there are no audit events | "Stop using" ≠ "delete": **we must do both**. There is no per-person or per-chat control, which is a gap we can fill | High |
| Gmail Smart Compose | A single personalisation on/off switch | No per-contact exclusion found | High / not found |
| Fyxer | Per-address and per-domain "No label" rules keep mail out of categorisation and drafts. Enterprise admins get **AI Processing Exclusions** by domain, including subdomains | Closest product precedent | Med/Low (search index; page returned 404) |
| Superhuman | Learns your voice from sent mail and from prior threads with each recipient | No per-contact exclusion found | Med |
| Grammarly, Outlook suggested replies | - | Not checked | - |

---

## 9. Recommended design

### 9.1 Principles
1. **Hard boundary.** Excluded sources are never body-fetched, persisted, embedded, retrieved, learned from or quoted. Derivatives created earlier are purged.
2. **Decide on identifiers, never on content.**
3. **Two-phase fetch everywhere:** headers → decision → body.
4. **Deny overrides.**
   - Tenant and user rules apply together.
   - Users can add rules but cannot lift tenant rules.
   - In tenant allow-list mode (`02-solution-architecture.md` §6.1), new sources stay excluded until approved.
5. **Never-send terms are removed before any model sees text,** including our own NER (S5) and embeddings. A new stage **S2.5** does this, with re-checks at S9 and at prompt assembly.
6. **Honest scope.**
   - Source rules remove conversations, not mentions; the never-send list covers mentions.
   - Speech-to-text hears spoken words.

### 9.2 Onboarding: metadata-first enumeration → user review → content backfill

| Step | What happens | Exact calls (delegated) | Time [ESTIMATE] |
|---|---|---|---|
| 0 | Sync state is `REVIEW_PENDING`; the scheduler refuses body fetches | - | - |
| 1a Teams | List chats by recency, without content | `GET /me/chats?$expand=members&$orderby=lastMessagePreview/createdDateTime desc&$top=50` (never expand `lastMessagePreview`). If 25 members come back, also call `GET /chats/{id}/members` | Seconds to minutes |
| 1b Mail | Sent Items headers (optionally Inbox, last 12 months) | `GET /me/mailFolders('sentitems')/messages/delta?$select=toRecipients,ccRecipients,bccRecipients,from,sender,conversationId,sentDateTime,internetMessageId` with immutable IDs; keep the `deltaLink` | 1-5 min per 50k |
| 1c Calendar | Events from 12 months back to 3 months ahead | `GET /me/calendarView?…&$select=subject,organizer,attendees,start,end,isOnlineMeeting,onlineMeeting,seriesMasterId,type,iCalUId,sensitivity` | < 1 min |
| 1d Link | Resolve meeting ↔ chat lazily | `GET /me/onlineMeetings?$filter=JoinWebUrl eq '{url}'` → `chatInfo.threadId` | Per meeting |
| 2 | Build the **Sources index** (details below) | - | Seconds |
| 3 | **Human review**: the "What PersonaAgent may learn from" screen (details below) | Portal API | User-paced |
| 4 | **Backfill allowed sources only**, newest first. Teams: `GET /chats/{id}/messages` for allowed chats. Mail: bodies per allowed ID with `GET /me/messages/{id}?$select=uniqueBody,body,…`, batched ≤ 20 per `$batch` | Graph | ~50-90 min per 50k mails (doc 01) |
| 5 | Steady state: subscription → intake check → body fetch. A weekly "new since your last review" card lists new sources | Graph | - |

**Step 2, Sources index:**
- **Entries:** people (internal people merged by OID), domains, 1:1 and group chats (topic, or a label such as "Rahul, Priya, Ana +2"), threads, and meetings/series.
- **Stats:** mail counts and last activity; for chats, last-active only.
- **Pre-flagged for review:** hidden chats, consumer-mail domains, private events, and tenant-excluded domains.
- **Storage:** names, emails and topics are kept as vault tokens and re-hydrated only for display. Subjects pass through S2.5.

**Step 3, human review:**
- The user searches the list client-side and chooses a scope for each rule.
- An impact preview shows what each rule removes, e.g. "214 emails in 37 threads, 1 chat, 3 meetings".
- The user then selects **Finish** or **Skip**. Reminders go out at 24 and 48 h.
- Nothing is backfilled before Finish or Skip. New items that arrive meanwhile are queued as IDs only.

A faster tenant opt-in pages bodies through the delta and drops excluded items in memory. It is not the default, because excluded bodies still pass through our process.

### 9.3 Rule model

| Rule | Key | Matches when | Default scope |
|---|---|---|---|
| Person (internal) | AAD OID + known SMTP/UPN | They appear as `from`, `sender`, To/Cc/Bcc, a chat member, or a meeting organiser/attendee | **Everywhere they participate**, with per-channel tick-boxes and impact counts |
| Person (external) / address | Lower-cased SMTP; guest/federated identity | Same | Same |
| Domain | Domain + subdomains | Any participant is in the domain | Everywhere |
| 1:1 / group / meeting chat | `chatId` | Every message, regardless of membership changes | That chat (a meeting chat offers to include the meeting) |
| Email thread | `conversationId` + `In-Reply-To`/`References` inheritance | The message is in the conversation or replies into it | Thread |
| Meeting occurrence / series | Event id + `iCalUId` → onlineMeeting/`joinWebUrl`; `seriesMasterId` | Transcript, meeting chat, recorder session, invite | One occurrence / all, including future ones |
| Channel (future) | teamId + channelId | Posts and replies | Channel |

**What "do not use at all" removes:**
- style learning: exemplars, style cards and rule evidence;
- memory: episodes, atoms, commitments and relationship facts;
- retrieval: vectors and full-text search;
- drafting context;
- eval sets and caches.

**No metadata stub is kept.** This differs from doc 10's S3 stub for label-excluded items: only the rule and its HMAC key remain.

**Data model:**
- `exclusion_rule(rule_id, tenant_id, user_id|NULL, kind, key_hmac, key_token, scope_flags, status[active|purging|purged|held|revoked], epoch, created_by, created_at)`.
- A blind-key cache for the hot path: `HMAC(tenant beacon key, key)` → rules, as in the doc 10 vault.
- Lineage gains `container_keys[]` and `participant_keys[]`.
- Vectors gain filterable `src` (a 16-character HMAC) and `pk` (participant HMACs, when there are ≤ 20 participants).
- A per-user `epoch`, re-checked at S3 and S10, so that a rule added mid-flight wins.

### 9.4 Enforcement points

| # | Point | Exclusion rules | Never-send terms |
|---|---|---|---|
| E1 | Intake (S0) | Teams: `resource` → chatId → **drop before decrypt** (still return `202`). Mail: header payload or header GET | - |
| E2 | Fetch (S1) | Fetch bodies only for allowed IDs. Transcripts and recorder audio of excluded meetings are **never fetched or transcribed** | - |
| E3 | Parse (S2) | A quoted-history scanner drops quoted blocks that name an excluded participant, or the whole item if nothing user-authored remains | - |
| E4 | **S2.5 gate** | - | Normalise → segment → match → replace with `⟦NS_id⟧` in L0, in memory. Applies to bodies **and** metadata: subjects, topics, event fields, display names, cards, quote previews, transcript speakers |
| E5 | S3 / S10 | Re-check rules and epoch; write `src`/`pk` and lineage | - |
| E6 | Verify (S9) | - | Re-run on L1; any hit **blocks the item** |
| E7 | Retrieval and prompt assembly | Pre-filter `src $nin` on pending purges (≤ 90 values), then **post-filter every hit by lineage**. Exemplar and style-card selection skip excluded sources | Match text that doesn't come from L1: add-in instructions, portal search queries (**before embedding**), memory edits |
| E8 | Live drafting (S12) | An excluded thread is refused. User rules may allow a one-off ephemeral draft; tenant rules never do | The live thread passes through S2.5 |
| E9 | Output and re-hydration | Check the draft cites no excluded item | Re-hydrate `⟦NS_id⟧` only if `allow_in_drafts`; otherwise show `[removed]`. A client-side matcher flags and blocks terms the model produced by itself |
| E10 | Purge | §9.5 | Scrub, §9.6 |
| E11 | Logs | Rule IDs, counts and HMACs only. Bedrock invocation logging and Guardrails traces stay off (doc 10) | The matcher never logs its input |
| E12 | Caches, exports, backups | Invalidate the persona-pack cache; prompt caches expire by TTL; exports and backups expire or are purged | Same |

### 9.5 Retroactive purge
1. Resolve the affected items via **lineage**, not `$search`.
2. Set status `purging`. The post-filter excludes the items immediately (**logical exclusion ≤ 1 min**).
3. A Step Functions job then:
   - deletes L1 chunks and full-text rows;
   - runs `DeleteVectors` in batches of 500;
   - deletes or **re-derives** memory atoms;
   - decrements rule evidence;
   - **regenerates style cards**;
   - clears exemplar caches, eval sets and the 90-day drafts.
4. A nightly orphan scan marks the rule `purged`, and the user gets a receipt. **Physical purge ≤ 24 h**, matching the delete cascade in `02-solution-architecture.md` §6.1.
5. **Legal hold** defers physical deletion (status `held`). Logical exclusion still applies, and the user is told.

### 9.6 Never-send words
- **Promise:** "Never stored by PersonaAgent and never sent to any AI model (LLM, embedding or NER), except speech-to-text for audio you record." Microsoft's own processing inside M365, such as Teams transcription, is outside this promise.
- **List storage:** the vault account, under the user's branch key. Workers decrypt it only in memory, as a compiled automaton cached for 5-15 min.
- **Term record:**
  - the text;
  - type: word/phrase, person name or codename;
  - matching level: exact → variants → substring → transcript-fuzzy;
  - confirmed variants;
  - `allow_in_drafts`, **off** by default.
  - Cap: ~500 terms / 5,000 patterns per user [ESTIMATE].
- **Token:** `⟦NS_<random id>⟧`, stable per user and not derived from the term. Deleting a term crypto-shreds its mapping.
- **Terms inside names or addresses** (e.g. a family surname): the vault marks that Tier P token `ns=true` and doesn't store the value. Re-hydration uses the client's live compose context.
- **Variants at entry** (the user confirms each):
  - inflections and separator forms;
  - Hinglish folds;
  - local Devanagari ↔ Roman candidates (§6.4);
  - automatic confusable skeletons.
- **Preview before saving:** "appears in N stored items", with a warning for common words such as Asha or Apple.
- **Examples:**
  - "Falcon" (substring) → `falcon`, `fal con`, `फाल्कन`, plus a skeleton that catches Cyrillic "Fаlcon".
  - "Sharma" → `sharma`, `sharmaa`, `शर्मा`, `sharmaji`.
- **Adding a term** (≤ 24 h):
  - re-redact the user's L1 in place;
  - re-embed affected vectors;
  - rewrite memory atoms;
  - regenerate style cards and rules that quote the term;
  - scrub the 30-day transcripts and 90-day drafts.
  - Until the scrub finishes, prompt assembly re-matches retrieved L1.
- **Deleting a term:** matching stops and old tokens stay unresolvable. An optional re-ingest from M365 restores the original text.

### 9.7 Edge cases

| Case | Behaviour |
|---|---|
| Person in many group chats | The preview lists every chat. Strict by default; the user can untick big team chats. Membership changes (`lastUpdatedDateTime`) re-evaluate: if the person is added later, the chat becomes excluded and its history is purged |
| Person mentioned elsewhere | Offer "also add 'Rahul Mehta' to never-send words" |
| Delegate / send-on-behalf | Check `from`, `sender` and all recipients. Delegate-authored mail is already kept out of the persona (doc 05) |
| Forwards | The quoted-header scanner applies. A forward may start a new `conversationId` (Med). Forward-as-attachment is not ingested in the MVP |
| Unnamed group chats | Label = up to 3 member names + "+N"; searchable by any member |
| Hidden chats | Shown with a "hidden in Teams" badge and suggested for exclusion |
| Aliases, distribution lists | Internal people are merged by OID; external addresses stay separate unless the user groups them. A DL address can be excluded, but its membership is not expanded |
| Un-exclude | The rule is revoked. Content is not restored automatically; re-ingest is optional |
| Legal hold | Logical exclusion applies now; purge and scrub wait for release (`02-solution-architecture.md` §8.5) |
| Spoken terms | STT hears them. The transcript is redacted before persistence, and meeting rules delete audio before STT runs |
| Excluding a manager or key client | Warn that this audience will have fewer style examples |

### 9.8 Assurance
- **Daily canaries** in a test tenant:
  - excluded sources: a chat, a thread, a meeting and a person;
  - terms in Latin and Devanagari, plus homoglyph, zero-width-split and Hinglish spellings.
  - The canaries must show zero hits in L1, vectors, memory, logs and captured test-cell prompts.
- **Recall:** extend doc 10's adversarial Unicode set and apply its ≥ 99.9% dictionary-term recall gate.
- **Receipts:** users get exclusion receipts with published propagation times.

---

## 10. Effort estimate (engineer-weeks) [ESTIMATE, ±30%]

Incremental to the existing plan. It reuses the doc 05 §6.5 lineage cascade, the doc 10 §6.7 vault and blind indexes, and stages S0-S13.

| Work item | MVP | Full |
|---|---|---|
| Header pass (chats + members, mail header delta, calendarView, meeting link); Sources index with labels and suggestions | 1.5 | 2.0 |
| Portal review screen and API (tabs, client-side search, scopes, impact preview, onboarding gate, reminders, "new since last review") | 2.0 | 3.0 |
| Rule engine, blind-key cache, Teams drop-before-decrypt, two-phase fetch, epoch checks | 1.5 | 2.0 |
| Quoted-history scanner for forwards | 0.5 | 1.0 |
| Retrieval pre/post-filter; purge orchestration (DeleteVectors, atom re-derivation, style-card regeneration, verification, receipts) | 1.5 | 2.5 |
| Never-send core: vault-side list, normalisation, ICU segmentation, Aho-Corasick with offset-mapped masking, S2.5/S9/prompt/query hooks | 2.0 | 2.0 |
| Variant generation: rule-based in MVP; IndicXlit offline + confusable skeletons in Full | 0.5 | 1.5 |
| Add-in: re-hydration policy and client-side output matcher | 0.5 | 1.0 |
| Retroactive scrub on term add; term delete | 1.0 | 1.0 |
| Transcripts: pre-STT drop and exact matching in MVP; fuzzy mode and timestamp muting in Full | 0.5 | 1.5 |
| Test corpora (Hinglish/Devanagari/adversarial Unicode), canaries, CI gates, security-pack text | 1.0 | 1.5 |
| **Total** | **≈ 12.5** | **≈ 19** |

**MVP cut:**
- **Deferred:**
  - channels;
  - message-level exclusion inside large group chats;
  - transcript fuzzy matching;
  - IndicXlit (ship rule-based variants and user-typed Devanagari instead);
  - automatic re-ingest;
  - the tenant Guardrails Tier C detector.
- **Size:** ≈ 2 engineers for ~6 weeks, roughly 20-35% of a 3-6-engineer, 3-month MVP.
- **Plan:** `03-mvp-plan-and-roadmap.md` should be updated; this report does not change it.

---

## 11. Open questions / could not verify
1. Do `chatType`/`topic` filters work on `GET /me/chats`? They are undocumented. **(Test)**
2. Does `$orderby=lastMessagePreview/createdDateTime desc` work without `$expand=lastMessagePreview`? The documented example does this; test it at scale. **(Med)**
3. Does a header-only rich mail subscription work on `mailFolders('SentItems')`? Only `Drafts` is documented. **(Med - test)**
4. Do `$filter=conversationId eq` and recipient lambda filters work on messages? Neither is documented. **(Med/Low)**
5. Does a forward or a subject change start a new `conversationId`? Test in classic Outlook, new Outlook and OWA. **(Med/Low)**
6. Does the Search API person search need `People.Read`? The page doesn't restate the permission. **(Med)**
7. Can non-organisers read transcripts through the delegated `GET /me/onlineMeetings/{id}/transcripts`? Not stated. **(Test)**
8. Do Transcribe vocabulary filters work for hi-IN? **(Test)**
9. Can IndicXlit run on CPU, offline, and with which dependencies? Not stated; the README says code and models are MIT. **(Test)**
10. How does S3 Vectors `$nin` behave on array metadata? Only `$eq` on arrays is documented. **(Test)**
11. Fyxer's domain-exclusion article returned 404, so it is cited from the search index. Grammarly and Outlook suggested replies were not checked.
12. **Founder policy calls:**
    - Is a self-hosted transliteration model acceptable under "never sent to any AI model"?
    - Should users get a one-off ephemeral draft in a thread they excluded themselves?
    - Should a person rule default to "everywhere", or to 1:1 chats and direct mail only?
13. **Legal track:** does a tenant legal hold require us to preserve *derived* copies of user-excluded sources, given that M365 is the system of record?

---

## 12. Sources

**Microsoft Graph / Microsoft 365**
- List chats (v1.0): https://learn.microsoft.com/en-us/graph/api/chat-list?view=graph-rest-1.0
- List chats (beta, `members/any` filter example): https://learn.microsoft.com/en-us/graph/api/chat-list?view=graph-rest-beta
- chat resource: https://learn.microsoft.com/en-us/graph/api/resources/chat?view=graph-rest-1.0
- chatViewpoint: https://learn.microsoft.com/en-us/graph/api/resources/chatviewpoint?view=graph-rest-1.0
- teamworkOnlineMeetingInfo: https://learn.microsoft.com/en-us/graph/api/resources/teamworkonlinemeetinginfo?view=graph-rest-1.0
- List joinedTeams: https://learn.microsoft.com/en-us/graph/api/user-list-joinedteams?view=graph-rest-1.0
- List channels: https://learn.microsoft.com/en-us/graph/api/channel-list?view=graph-rest-1.0
- Permissions reference: https://learn.microsoft.com/en-us/graph/permissions-reference
- Teams chat-message change notifications: https://learn.microsoft.com/en-us/graph/teams-changenotifications-chatmessage
- Change notifications with resource data: https://learn.microsoft.com/en-us/graph/change-notifications-with-resource-data
- changeNotification resource: https://learn.microsoft.com/en-us/graph/api/resources/changenotification?view=graph-rest-1.0
- Outlook change notifications: https://learn.microsoft.com/en-us/graph/outlook-change-notifications-overview
- `$search` query parameter (messages, people): https://learn.microsoft.com/en-us/graph/search-query-parameter
- `$filter` query parameter: https://learn.microsoft.com/en-us/graph/filter-query-parameter
- List messages: https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0
- JSON batching: https://learn.microsoft.com/en-us/graph/json-batching
- List people (maintenance mode): https://learn.microsoft.com/en-us/graph/api/user-list-people?view=graph-rest-1.0
- Search API, people: https://learn.microsoft.com/en-us/graph/search-concept-person
- event resource: https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0
- List calendarView: https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0
- Get onlineMeeting (JoinWebUrl filter): https://learn.microsoft.com/en-us/graph/api/onlinemeeting-get?view=graph-rest-1.0
- List transcripts: https://learn.microsoft.com/en-us/graph/api/onlinemeeting-list-transcripts?view=graph-rest-1.0
- getAllTranscripts: https://learn.microsoft.com/en-us/graph/api/onlinemeeting-getalltranscripts?view=graph-rest-1.0
- Start a chat in Teams (group chat naming): https://support.microsoft.com/office/start-a-chat-in-teams-0c71b32b-c050-4930-a887-5afbe742b3d8
- Purview keyword dictionaries: https://learn.microsoft.com/en-us/purview/sit-create-a-keyword-dictionary
- Restricted Content Discovery: https://learn.microsoft.com/en-us/sharepoint/restricted-content-discovery
- Purview DLP for Microsoft 365 Copilot: https://learn.microsoft.com/en-us/purview/dlp-microsoft365-copilot-location-learn-about
- Copilot personalization and memory: https://learn.microsoft.com/en-us/microsoft-365/copilot/copilot-personalization-memory

**AWS**
- Bedrock Guardrails word filters: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-word-filters.html
- ApplyGuardrail: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html
- Bedrock service quotas (Guardrails): https://docs.aws.amazon.com/general/latest/gr/bedrock.html
- Transcribe vocabulary filtering: https://docs.aws.amazon.com/transcribe/latest/dg/vocabulary-filtering.html
- Transcribe creating a vocabulary filter (limits): https://docs.aws.amazon.com/transcribe/latest/dg/vocabulary-filter-create.html
- Transcribe supported languages: https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html
- S3 Vectors metadata filtering: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-metadata-filtering.html
- S3 Vectors DeleteVectors: https://docs.aws.amazon.com/AmazonS3/latest/API/API_S3VectorBuckets_DeleteVectors.html
- S3 Vectors ListVectors: https://docs.aws.amazon.com/AmazonS3/latest/API/API_S3VectorBuckets_ListVectors.html

**Unicode and libraries**
- UTS #39 Unicode Security Mechanisms (v18.0.0): https://www.unicode.org/reports/tr39/
- UAX #29 Unicode Text Segmentation (Unicode 18.0.0): https://www.unicode.org/reports/tr29/
- pyahocorasick: https://github.com/WojciechMula/pyahocorasick
- Vectorscan: https://github.com/VectorCamp/vectorscan
- indic_transliteration: https://github.com/indic-transliteration/indic_transliteration_py
- AI4Bharat IndicXlit: https://github.com/AI4Bharat/IndicXlit
- Local reproduction: Python 3.14.7 / Unicode 16.0 script (word boundaries, NFKC, nukta, zero-width, digits, Cyrillic), run 2026-10-09

**Precedents (secondary)**
- Gmail Smart Compose personalization: https://support.google.com/mail/answer/9116836
- Fyxer custom rules: https://support.fyxer.com/article/setting-up-custom-rules-in-fyxer · domain exclusions (404 at fetch time): https://support.fyxer.com/en/articles/12578707-control-which-domains-fyxer-can-process
- Superhuman Write with AI / Personalization: https://help.superhuman.com/hc/en-us/articles/38456855116307
