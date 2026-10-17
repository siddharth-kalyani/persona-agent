# Vanimo: application code

The build plan is `docs/03-mvp-plan-and-roadmap.md` §0 (solo track M0–M6). This folder holds the code (D11):

| Folder | What | Stack |
|---|---|---|
| `backend/` | API, Graph access, model router, migrations, eval harness, canaries | Python 3.14, FastAPI, SQLAlchemy + psycopg, Alembic, MSAL, Anthropic SDK (Bedrock) |
| `frontend/` | Web control center + Outlook add-in task pane | React 19, Vite, TypeScript, Fluent UI 9, MSAL |
| `infra/` | One regional cell on AWS | AWS CDK (Python): VPC, Aurora PostgreSQL 18 (Serverless v2), ECS Fargate, internal ALB, CloudFront, S3, KMS, Secrets Manager |
| `infra/entra/` | How to register the Entra app | — |
| `surfaces/outlook-addin/` | Outlook add-in manifest (XML); the task pane itself is in `frontend/src/addin/` | — |
| `surfaces/teams-app/` | Teams app manifest + package builder (M5); the dialog and tabs (Commitments, M6's Meetings) are in `frontend/src/teams/` | — |
| `docker-compose.yml` | Local Postgres 18 (port 5433) | Docker |

## Sample data: works without Microsoft 365

Entra and Graph access may come late, so every feature also runs on a **sample workspace**: Kestrel Analytics, a fictional IT-services firm (`backend/vanimo/sources/sample.py`). It includes:
- clients Acme Retail, Bluefin Bank and Orion Health;
- a 62-person group chat, a hidden chat and an unnamed chat;
- forwards, Hinglish subjects, personal email, a private event and recurring meetings.

**Who sees it:**
- Password sign-ins always use the sample workspace.
- Microsoft sign-ins use their real data (Graph), unless `VANIMO_SAMPLE_DATA=always`.
- Both go through the same interface (`vanimo/sources/base.py`), so screens don't change when real data arrives.

**Local sign-in (local/dev only):**
- `VANIMO_ENABLE_PASSWORD_AUTH=true`.
- Accounts are made with `uv run python -m vanimo.ops.local_user --email … --role user|admin|superadmin`, which prints a one-time password the person must replace at first sign-in. `--reset` issues a new one.
- Production refuses this setting.

## M1: Choose what Vanimo learns from

**What it does** (architecture §6.5):
- **Header pass.** Lists people, domains, threads, chats and meetings from headers only.
- **Review screen.** Shows the impact before you confirm: "7 emails in 5 threads, 4 chats, 1 meeting".
- **Person exclusions.** Cover every chat the person is in; you can untick big group chats (D5).
- **Never-send words.** Matched by a deterministic matcher, never by an AI model:
  - it catches case, full-width and zero-width tricks, Cyrillic look-alikes, separators, plurals, Hinglish spellings, honorifics, and spellings you type yourself (e.g. Devanagari);
  - words are replaced before storage and shown as `[removed]`.
- **Finish/Skip gate.** No message content is read before you choose.
- **My data controls.** Change anything later; every change gets a receipt.
- **Admin client scoping (D9).** Exclude client accounts by domain, or allow approved clients only. Users see these rules as locked.

**How it's built:**

| Piece | Where |
|---|---|
| One exclusion engine for user and organisation rules | `vanimo/controls/engine.py` |
| Matcher | `vanimo/controls/neversend.py` |
| Header pass | `vanimo/controls/scan.py` |
| Field encryption + rule-key HMACs | `vanimo/vault.py` |
| Purge and scrub jobs | `vanimo/controls/jobs.py` |
| APIs | `vanimo/api/controls.py`, `vanimo/api/admin_scoping.py` |

**At rest:**
- Names, addresses, subjects and chat names are encrypted per user.
- Rules store only keyed hashes of identifiers.
- Never-send words are encrypted per user and never logged.
- Organisation rules can only be written in a transaction the API marked as admin, after its role check. The database refuses them in any other transaction.
  - This is a backstop against bugs, not a second security boundary: code that can run arbitrary SQL as the API role could set the flag itself.
  - All queries are parameterised.

### Carried into M2 (from the M1 reviews), done in M2

- Every content read calls `require_review_done(engine, ref, source.kind)` (the learning backfill does).
- The fetch path builds the engine with `load_engine(..., self_email=...)` (`vanimo/learning/backfill.py`).
- Every derived store (L1 text, vectors, tokens, style cards) has its purge in `vanimo/controls/jobs.py`.

## M2: Learn safely

Works the same on the sample workspace and on Microsoft 365. Tabs: **Sample workspace**, **Learning**, **Persona**.

1. **Sample workspace** (sample only): Inbox, Sent, Chats and Meetings as Outlook and Teams would show them.
   Each item shows what Vanimo did with it (learned, excluded and why, not learned yet, received). For a
   learned item, **See what Vanimo stored** shows the stored text next to your view of it.
2. **Learning:** *Start learning* runs the backfill (`vanimo/learning/backfill.py`):
   - Gate first: nothing is read until the review is done for this source.
   - Only your own sent emails and chat messages from allowed sources are read; the engine decides from metadata
     before any text is fetched. The message you replied to is kept as context only if its sender is allowed too.
   - Redaction L0 → L1 in memory (`vanimo/redaction/`): hidden HTML and Unicode tag characters dropped,
     never-send words → `⟦NS_…⟧`, Tier R (Aadhaar/VID, PAN, GSTIN, IFSC + account, UPI, voter ID, passport,
     cards, SSN/ITIN, EIN, ABA, secrets and passwords) → `[slot]` (checksum-validated, irreversible), people
     from the header/directory gazetteer → `⟦PERSON_…⟧`, emails and phones → tokens, your own name → `⟦ME⟧`.
     A verify pass blocks any item with residue (fail-closed).
   - Labels: relationship (manager/report/peer/external/personal), intent, channel, language (English,
     Hinglish, Hindi). Stored vault-encrypted with HMAC lineage. A rule or word added mid-run restarts it.
   - *Delete what Vanimo learned* deletes everything learned and leaves a receipt.
3. **Persona:** the Persona Snapshot (style cards: greetings, sign-offs, length, formality, phrases,
   Indian-English keep-list, per audience, with back-off) and the basic studio (formality, length, warmth,
   emoji, polish, phrases to use or avoid). Also shows the offline evaluation baseline.

Two-phase fetch: thread headers are read first; text is fetched only for allowed messages and the one each replied to (and only if everyone on that message is allowed). Meeting chats are tied to their meeting by the join link, so a meeting or series rule covers them; a chat whose roster can't be read in full is never read.

Purges: adding an exclusion deletes learned items whose lineage it now excludes. Adding a never-send word
re-masks stored text, tokens and studio phrases. An admin client-scoping change queues a purge for every user
in the tenant, which the sweeper runs. Style cards are rebuilt after each purge.

## M3: Draft in Outlook

Works the same on the sample workspace and on Microsoft 365. New: the **Draft** tab in the web app and the drafting
task pane in Outlook (`frontend/src/addin/`). Both use one drafting service (`backend/vanimo/drafting/`). **Vanimo
never sends:** you insert, copy or open a reply, read it, and send it yourself.

**What it does:**
- **Reply or new email in your voice.** In Outlook the task pane reads the open email's conversation and recipients;
  on the web you pick a conversation from your inbox or start a new email. An instruction is optional for a reply
  ("tell her I'll send the plan by Wednesday") and required for a new email.
- **Audience chip.** "Writing to: your manager / a colleague / someone outside your organisation", from the same
  rules the learner uses (directory manager and reports, your organisation's domains).
- **Insert at the cursor** in a compose window (never replacing the quoted thread). From a message you're reading:
  **Reply with this** opens Outlook's reply form with the draft in it.
- **Pre-send checks** on every draft, and on your own text with **Check before sending** / **Check my edits**:

  | Check | Severity |
  |---|---|
  | Dates, times, amounts and promises not in the email or your instruction (generated drafts only) | warn |
  | Look-alike domain in a recipient or the sender (`c1oudnest.example` vs `cloudnest.example`) | **block** |
  | Payment-detail change or urgent payment request (BEC) | **block** |
  | First email to a domain, a personal address, an outsider added to an internal thread | warn |
  | Greeting names someone not on To; a client account named in an email to a different client | warn |
  | Regulated IDs or secrets in your text; never-send words in your text | warn |
  | Fill-ins left for you (`[date]`, `[PAN]`), links or made-up contacts removed, hidden text in the email | info |

  A **block** turns insert (and copy) off until you tick "I've checked this another way".
- **Model router.** Claude Haiku 5.5 by default; Sonnet 5.5 for a new email to a client or your manager, a long reply,
  or when you ask for higher quality, within a daily quota (`VANIMO_PREMIUM_DRAFTS_PER_DAY`, default 20). Rate limit
  per user: `VANIMO_DRAFTS_PER_MINUTE` / `VANIMO_DRAFTS_PER_DAY`.
- **Offline stand-in** (`VANIMO_DRAFTER=offline`, the local default) until the AWS account exists. No model: it turns
  your instruction into first-person sentences in your register (for example "Kindly …" if you write that way to
  clients), adds your greeting and sign-off, or writes a short acknowledgement with a fill-in when there is no
  instruction. It is labelled everywhere it appears. A deployed cell always uses Bedrock, and prod refuses `offline`.

**How a draft is made** (`vanimo/drafting/service.py`, architecture §7.2 S12):
1. Rate limit, then the onboarding gate (no review, no draft).
2. Thread **headers** only → the exclusion engine decides on the whole conversation: its thread rule, everyone in it,
   everyone you're writing to. Excluded by you: refused, or a **one-off draft** made in memory and never stored.
   Excluded by your organisation: always refused.
3. Only then the last 4 messages' own words are fetched and redacted to L1 in memory, with your instruction and the
   subject (never-send words → placeholders, Tier R → slots, people → tokens, verify, fail-closed).
4. Persona pack: the style card for this audience (greeting, sign-off and length from your *emails*, since chats have
   none), your studio settings, and up to 3 of your past messages. Every one is re-checked against the live rules,
   and every stored phrase against your never-send words as they are now (a rule or word added a moment ago wins
   before the purge or scrub job runs). A past message goes in word for word only if it's from the same thread or
   everyone this email goes to already received it; anything else only as its shape, so facts never move between
   audiences.
5. The prompt (`vanimo/drafting/prompt.py`): rules → persona (marked for prompt caching) → audience → examples →
   the thread as untrusted, spotlighted data → your instruction. The model writes only the body.
6. Output gate (`vanimo/drafting/gate.py`): plain text; the model's own greeting and sign-off dropped; tokens not in
   this prompt never revealed; links not in the email or instruction removed; a Tier R value blocks the draft; made-up
   addresses and phones become fill-ins; never-send words masked.
7. Your greeting + body + sign-off, re-hydrated for your screen: names back, never-send words as `[removed]` (or the
   word itself if you allowed it in drafts).
8. Pre-send checks (`vanimo/drafting/checks.py`), then the draft is stored as L1 (encrypted, with lineage) for the M4
   edit loop, under the same lock as purges: if your controls changed while it was being written, it isn't stored
   (§6.5 X4). Logs carry codes, counts, model and timings only. The Sonnet quota is counted from the audit log, so
   one-off drafts count and deleting drafts doesn't reset it.

**Purges reach drafts too:** a new exclusion deletes drafts whose lineage it covers, a new never-send word re-masks
them, "Delete what Vanimo learned" deletes them, and an organisation scoping change queues users with drafts.

### Try the Outlook add-in locally

Outlook loads add-in pages over HTTPS only, and needs a manifest. With the Docker stack (or Option B) running:

1. Create and trust a localhost certificate. One way (needs Node): `npx office-addin-dev-certs install`. It writes
   `localhost.crt` and `localhost.key` to `%USERPROFILE%\.office-addin-dev-certs`.
2. Start Vite with it (Option B frontend): set `VANIMO_DEV_HTTPS_CERT` and `VANIMO_DEV_HTTPS_KEY` to those two files,
   then `npm run dev`. The app is now on `https://localhost:5173`.
3. Render a manifest for that host: `py app/surfaces/outlook-addin/render_manifest.py https://localhost:5173 > manifest.xml`.
4. In Outlook on the web: **Get Add-ins → My add-ins → Add a custom add-in → Add from file** → `manifest.xml`.
   Your organisation may need to allow custom add-ins.
5. Open an email (or a reply) and press **Vanimo**. Until the Entra app exists the pane offers local password sign-in;
   a password account uses the **sample workspace**, so pick a sample conversation to reply to. The draft is inserted
   into the real compose window.

## M4: Drafts folder + edit loop

New: the **Queue** tab, "Put in my Drafts folder" on the Draft page, **Learned from your edits** on the Persona tab,
and the organisation's **Drafts in mailboxes** switch on the Client scoping tab. Vanimo still never sends.

**Drafts queue** (`vanimo/drafting/queue.py`):
- **What's waiting.** Recent conversations whose latest message is from someone else, that you haven't answered
  since. This is worked out from headers only (your inbox and Sent Items). Conversations you marked "No reply
  needed" are left out.
- **Triage.** Automated senders and mail you're only copied on rank low. An excluded conversation is listed as
  excluded and its text is never read. Then, after your review and for at most 12 allowed conversations, the latest
  message's own words are read in memory to see whether it asks something (question, request, scheduling).
- **Prepare.** "Prepare draft" (or "Prepare drafts for all", up to 5) runs the M3 drafting service on the
  conversation.

**Drafts in your Outlook Drafts folder:**
- **Opt-in per person**, allowed by the organisation (`tenant_policies.server_drafts`, default on). D8: the one
  internal app holds `Mail.ReadWrite` until the Read/Compose split.
- **How it's created.** Graph `createReply` with the text as `comment`, so the quoted thread stays, with immutable
  IDs. It shows in every Outlook client, including mobile.
- **What goes in.** "Prepare" puts the draft as written. "Put in my Drafts folder" on the Draft page puts in the
  text on your screen, including your edits; it isn't stored by Vanimo.
- **Who it's addressed to.** Exactly the recipients Vanimo checked, set on the draft after it's created, never the
  message's Reply-To. An email whose Reply-To points elsewhere gets a warning, and a look-alike Reply-To blocks.
- **One per conversation.** Placing a new draft removes the earlier unused one in the same conversation. A double
  click can't create two.
- **Warnings.** A draft with a blocking warning (payment change, look-alike domain) only goes in after you tick the
  confirmation.
- **Tidying.** Each time you open the queue, placed drafts older than your setting (3 days by default) are deleted
  only if they are still unsent and untouched since Vanimo wrote them. If you replied in the conversation yourself,
  the unused draft is removed. Anything you edited or sent is never touched; delete only ever applies to unsent
  drafts.

**Edit loop** (`vanimo/edits/`, architecture §9.2, research R05 §2.3 and §7.7):
1. **Match.** When you open the Queue or Persona tab, pending drafts are matched to your recent Sent Items:
   - a reply matches the first message you sent in the same conversation after it; if you drafted several times,
     the latest draft before the send is matched and the older ones are marked superseded (one send is one
     observation);
   - a new email matches a sent message to the same people that shares enough text;
   - within 72 hours, otherwise the draft is marked unmatched.
   - drafts whose candidates weren't all read (at most 10 bodies per sync) stay pending for the next sync.

   Headers first: an excluded sent message ends the tracking and is never read. The people on the real reply join
   the draft's lineage, so excluding someone you cc'd there purges what was learned too. Everything is stored under
   the controls lock, and only if your controls didn't change during the sync. In the sample workspace, **Mark as
   sent** on the Draft page uses your edited text instead.
2. **Compare in L1** (the same tokens on both sides, so names are never edits). The outcome is one of:
   - sent as is (≤ 5% of characters changed, and no number, negation or word changed meaning);
   - light edit (≤ 25%);
   - heavy edit;
   - rewritten.
3. **Style edits become rule observations** for that audience: greeting, sign-off, shorter or longer, exclamation
   marks dropped, a filler phrase deleted ("hope you are having a great week"), one word swapped for another form of
   the same thing ("please" → "pls", "reply" → "revert"; a fixed list). Anything else (accept → decline, a date, a
   number, a name, a slot, a longer passage) is content: counted, never a rule.
4. **Verify (PROSE-style, rules in the MVP).** A rule becomes **active** only after all of these:
   - 3 observations from different drafts;
   - more than twice as many supporting as contradicting, and the latest one supports it;
   - your own sent mail to that audience agrees, where there are enough messages to judge.
5. **Confirm.** On the Persona tab: **Keep** (confirmed) or **Not me** (rejected, never used or proposed again,
   even after a purge removes its evidence: the decision is kept without the text). Keeping a new greeting, sign-off
   or length rule retires the old one for that audience. Unconfirmed rules stop being used 90 days after they were
   last seen.
6. **Use.** Active and confirmed rules go into the prompt and set the greeting, sign-off and target length. Only
   rules you kept change the text in code: word swaps, no exclamation marks, and a short sentence holding a phrase
   you always delete is dropped. These run before the output gate and never touch names, placeholders, `[slots]`,
   links or numbers. Your own "never use" phrases (Persona studio) still only ask the model to revise.
7. **Measure.** The send-without-edit rate (the north star, `docs/03` §5) and the light-edit rate show on the
   Persona tab.

**What is stored:** the outcome, the share of characters changed, the kinds of edit and the rules (their values
vault-encrypted). The sent text is never stored.
**Purges:**
- an exclusion deletes the drafts its lineage covers, with their edit events and rule evidence, then re-counts the
  rules; a rule with no evidence left is deleted;
- a never-send word deletes any rule holding it;
- "Delete what Vanimo learned" deletes everything above, but keeps your drafting settings;
- a purge that deletes the record of a draft already in your Outlook keeps its mailbox ID (encrypted) until the next
  tidy removes the draft, if it's still unsent and untouched.

## M5: Commitments + Teams

Works the same on the sample workspace and on Microsoft 365. New:
- the **Commitments** tab;
- **Teams chats** on the Draft page;
- **Notifications** in the header;
- the **Teams** switches on the Client scoping tab;
- the Teams app (`surfaces/teams-app/`, entry `frontend/teams.html`).

Vanimo still never sends.

**Commitments ledger** (`vanimo/commitments/`, research R05 §5.3–5.4):
1. **Where promises come from.** Only your own sent emails and Teams chat messages, from allowed sources, already
   redacted to L1. They are found in two places:
   - after every learning run, in what it learned (the last 60 days, work mail only). It looks at most 200 messages
     per run, newest first; a message that already has promises isn't looked at again. With Bedrock each is a
     model call, so the run keeps its heartbeat, and a failed call skips that message only;
   - each time you open the Commitments tab, in what you sent since the last look. This reads headers and rosters
     first; an excluded message is never read. At most 60 messages per look, oldest first, cut only between two
     different send times; the rest wait for the next one. With no learning run yet, it looks at the last week.
   - **Teams chats:** Graph's chat list doesn't say when the last message was posted (its "last updated" is a
     rename or a roster change, and the last-message preview carries text). So every allowed chat is asked for
     messages since the last look, filtered by Graph, up to 200 chats per look.
2. **What counts as a promise.** A first-person future with something to deliver: "I'll revert with the final
   runbook tomorrow", "we will add Lisa to the bridge", chat's "will share the metrics by Friday evening", "sharing
   mine in 10 mins". Never a question, a condition, a negation, a request to someone else or someone else's promise
   ("…, and Vikram will confirm" is cut off).
   - Offline stand-in: rules, labelled.
   - With Bedrock: Claude Haiku, held to the same output. Every sentence it returns must be in the message, every
     date phrase in the sentence, and it can't add a name marker; anything else is dropped, and a malformed answer
     falls back to the rules.
3. **Due dates are worked out in code**, never by the model, in the cell's time zone (India: IST). Examples: "by
   Thursday EOD" (18:00), "tomorrow evening", "this week" (Friday), "next week", "12 November", "by the 31st", "in
   10 mins", "by EOD Friday". A weekday that is today means next week's. "Next Friday" is the Friday of next calendar
   week. "This week" said at the weekend means its Sunday, and "the weekend" means Saturday.
4. **The list.** Grouped as overdue, due in the next day, later and no date given, with the sentence as you wrote
   it and who it was to.
   - "Looks done" when a later message of yours in the same thread or chat delivers it ("PFA the final cutover
     runbook"); you confirm.
   - Actions: **Done**, **Not a promise**, **Remind me tomorrow**, **Reopen**. Finding a promise again never
     reopens or duplicates it. A promise's key is an HMAC of its message and its sentence, not its position in an
     extractor's answer.
   - The page shows how many of the promises you decided on were real (the ≥ 80 % precision target, `docs/03` §5).
5. **Follow-up in your voice.** **Draft a follow-up** → "It's done", "Running late" (with a new date) or "Still on
   it". It is drafted where the promise was made: an email reply in the same conversation (copy it or put it in
   your Drafts folder) or a message in the same Teams chat. This goes through the drafting service, so the
   conversation is checked against your rules again first.
6. **Stored:** the promise and its short form (L1, vault-encrypted, never-send words masked, also in what a model
   wrote), the due date, the status and lineage, and the conversation or chat ID (encrypted). The message text isn't
   stored. The list masks never-send words as they are now, before the scrub job reaches the stored text.
   - Exclusions purge promises by lineage, and the list hides them at once.
   - Never-send words re-mask them.
   - "Delete what Vanimo learned" deletes them.

**Teams** (research R02 §B):
- **"Draft reply"** on any chat message (… → More actions → Vanimo) and **"Draft with Vanimo"** under the message
  box open a Vanimo dialog. It drafts in your voice through the same drafting service, the chat way:
  - the roster decides before any message is read;
  - a meeting chat must be tied to its meeting (by the header pass) or it's refused;
  - the last 8 messages up to the one you're answering are the context, and a sender who left the chat is left out;
  - no greeting or sign-off is added, and your chat style card is used.
- **Teams can't type into the message box**, so the dialog offers **Copy**. **Open the chat with this text** appears
  only when your admin turns it on, after spike 1 shows the prefill works in existing chats (Microsoft documents it
  for new chats only), and only for 1:1 chats. For a group, Teams would open or create a chat with exactly those
  people, which may not be the one you're answering. Channels aren't supported yet.
- **Check my edits** works on Teams drafts and follow-ups too: your own words (regulated IDs, another client's
  name, never-send words) and, in an allowed chat, a payment-change request in the last messages. Recipient rules
  are for email only.
- **The bot endpoint** (`/api/teams/messages`) answers only Teams' `fetchTask` and checks every request's Bot
  Framework token: issuer, audience, the key's channel endorsement and `serviceUrl`. A token from our own Entra
  tenant counts only from a caller app ID listed in `VANIMO_TEAMS_BOT_CALLERS`, which is off by default: any app in
  the tenant could get a token for the bot's ID. Turn it on with the Bot Connector's ID if Microsoft moves Teams to
  Entra-issued tokens; check a real request first.
  - Teams puts the message's text in that request. It's never read, logged or stored.
  - The dialog gets the chat and message IDs in an encrypted 10-minute handle, valid only for the person it was
    made for, so no ID appears in a URL.
- **The Vanimo tab** in Teams is the Commitments list, and it's where activity notifications link.
- **The Draft page** lists your recent Teams chats too, the same way, for the web and the sample workspace.
- **Teams edit loop.** A chat draft matches a message you posted in that chat after it (72 h) that shares enough
  text with it, so "one sec" is never taken for the draft. A discarded draft isn't tracked (email too). Chat edits
  teach only phrases, word swaps and exclamation marks; greeting, sign-off and length rules come from email only.
  In the sample workspace, **Mark as sent** works for chat drafts too.

**Notifications** (the channel M1 and M4 were waiting for, `vanimo/notify.py`):
- **What you're told.** Promises due within a day or overdue (once a day), the weekly digest of learned rules to
  confirm, and the review reminder 24 h and 48 h after sign-up.
- **Counts only, never content:** "3 promises due soon or overdue".
- **Where.** In the web app (Notifications in the header), and in your Teams activity feed when your organisation
  allows it and the Teams app is installed. This uses the app-only permission `TeamsActivity.Send`, because a
  person can't notify themselves (`infra/entra/README.md`).
- **When.** The sweeper makes and delivers them every 5 minutes, people notified longest ago first. Opening the app
  brings yours up to date.
  - One already read in the app isn't pushed to Teams.
  - A failed Teams delivery is retried up to 3 times.
  - Only rules still in use count as "to confirm".

**Try it on the sample workspace:**
1. Run Learning, then open **Commitments**: "Share the UAT access list" (to Karan, due Friday EOD), "Send you the
   onboarding checklist" (to Ana), and chat promises.
2. **Draft a follow-up** → Running late → "Monday".
3. On **Draft**, pick the "Rahul Verma" chat.

### Try the Teams app

Teams needs the Entra app, a deployed cell (or an HTTPS tunnel to your machine) and a bot registration; the steps are
in `infra/entra/README.md` §6b. Until then the Teams dialog can be opened in a browser for testing:
`http://localhost:5173/teams.html` (chat picker), `http://localhost:5173/teams.html?tab=commitments` and
`http://localhost:5173/teams.html?tab=meetings` (the tabs).
With password sign-in it uses the sample workspace.

## M6: Meeting memory

Works the same on the sample workspace and on Microsoft 365. New:
- the **Meetings** tab (also a **Meetings** tab in the Teams app);
- promises you made in meetings, in **Commitments**;
- the **Meeting memory** card on the Client scoping tab (a switch and transcript health checks).

Only internal Teams meetings with transcription on: Microsoft's own transcripts (everyone in the meeting sees the
transcription banner), read through Graph. Vanimo never records anything, and never receives audio.

**Reading transcripts** (`vanimo/memory/ingest.py`, architecture §6.2, research R02 §D.1). Graph facts checked against
Microsoft Learn on 2026-10-16:
- **As each person, not as an app.** The organiser *and invited attendees* can read a meeting's transcripts with the
  delegated `OnlineMeetingTranscript.Read.All`, so **no Teams application access policy is needed** (that's only for
  application permissions). The path is calendar → the meeting's join link → `me/onlineMeetings?$filter=JoinWebUrl
  eq '…'` → `…/transcripts` → `…/transcripts/{id}/content`.
- **The Teams admin gate.** Graph access to transcripts and speaker attribution are two tenant settings, both off by
  default since the end of July 2026 (Teams admin center → Meetings → Meeting settings, or
  `Set-CsTeamsMeetingConfiguration`). With access off, every call answers `403` with the inner code
  `GraphAccessToTranscriptsDisabled`: Vanimo records it, stops asking for 6 hours and says so on the Meetings tab.
  With attribution off, the `text/vtt` content answers `SpeakerAttributionNotAllowed`: Vanimo asks again for the
  unattributed format (`Accept: application/vnd.microsoft.graph.transcript+text`) and stores the meeting without
  names.
- **When.** There is still no background Graph token, so meetings are read when you open the Meetings tab (like M4's
  matching and M5's scan): meetings of the last 30 days that ended at least 5 minutes ago, newest first, at most 4
  per look (the rest on the next). An ended meeting with no transcript yet is looked at again every 15 minutes
  for 2 days. Each meeting is read once; one whose transcript is too large, expired or gone isn't downloaded again.
- **Which meetings.** Teams meetings in your calendar, organised inside your organisation (Graph holds no transcript
  of another company's meeting), not marked private, and allowed by your rules and the organisation's: the
  occurrence, its series, every invitee and their domains, client scoping. **An excluded meeting's transcripts are
  never listed or fetched.**
- **Series.** All occurrences of a recurring meeting share one online meeting and one transcript list, so an
  occurrence takes only the transcripts that started in its own time (from 30 minutes before it to 3 hours after,
  and before the next occurrence). Excluding one occurrence never exposes another.

**Who said it** (speaker attribution is the trust signal, R05 §5.3):
- Teams attributes speech to display names. Vanimo matches them to the invite ("John Miller (Guest)" is John
  Miller); a name two invitees share matches nobody.
- **Someone not on the invite:** if they're someone you know (your Sources index) and you haven't excluded them,
  their words are kept. If you excluded them, **the whole meeting is left out**, as a person rule covers every
  meeting they're in. If nobody can tell who they are (or two people you know share the name), their words are
  left out, because nobody can check them against your rules. The Meetings tab says how many parts were left out. Their name
  is still redacted wherever someone else mentions them.
- A wrong name can be fixed: **Wrong speaker?** moves a speaker's words and notes to another person in the
  meeting, or to "I don't know who". Promises follow: words moved to you add your promises to Commitments, and
  words moved away remove the open ones.

**Stored** (Mode A, architecture §8.4):
- Each turn redacted to L1 in memory first, with the same gazetteer as the learner, plus everyone invited:
  - names become person tokens, and regulated IDs become slots ("the signatory's PAN is [PAN]");
  - never-send words become placeholders;
  - a turn that can't be made safe is left out.
- **The transcript, as L1 speaker turns, for 30 days** (`transcript_retention_days`), for citations. Then only the
  notes stay.
- **Notes (memory atoms), for 12 months** (`memory_retention_days`). Each note has:
  - a kind: decision, requirement, action item, promise, open question, risk or idea;
  - the sentence as said;
  - who said it, and their side (you, a colleague, someone outside);
  - who it's for (action items);
  - when it was said, and when it was stored (bi-temporal);
  - the turn it came from;
  - a due date (resolved in code);
  - confidence, and trust ("high" with speaker names, "medium" without).
- The meeting's title (L1), time, lineage (occurrence and series hashes, invitees as person and domain hashes) and
  the governance fields of R05 §5.1: capture source, consent state (the Teams banner), retention class, audio
  retained (always no).
- A content-free record of what became of each meeting (stored, no transcript yet, unavailable, left out, deleted),
  so it's read once. The sweeper deletes expired turns and notes (`vanimo_private.expire_meeting_memory()`).
- Your rules reach all of it:
  - an exclusion added later hides the meeting at once, and the purge deletes it with its turns, notes and
    promises (receipt: `meetings_deleted`);
  - a never-send word added later is re-masked in titles, turns and notes;
  - "Delete what Vanimo learned" deletes every meeting and marks the ones already read as never to be read again.
  - **Forget this meeting** does the same for one.

**Notes** (`vanimo/memory/atoms.py`):
- Offline stand-in (labelled): cue phrases, at most one note per sentence, precision first.
  - "We decided…", "let's go with…", "Decision then:" are decisions.
  - "We need…", "must", "has to" (not questions, not "I need a minute") are requirements.
  - "Rahul, can you send…", "please prepare…" are action items. In a two-person meeting, "please…" is for the
    other one.
  - The commitments finder's first-person promises are promises.
  - Questions about plans and options are open questions; "risk", "concern", "tight" are risks; "what if",
    "we could" are ideas.
- **With Bedrock:** Claude Haiku as a quarantined, tool-less reader (architecture §9.4).
  - It reads windows of 40 turns.
  - Every quote must be in the turn it names, a short form may use only that turn's name markers, and an owner
    must be a person in the meeting; anything else is dropped.
  - Who promised is who said it, never the model's say; due dates are worked out in code.
  - A malformed answer falls back to the rules for that window.
- **Your own promises** in a meeting go to the Commitments ledger as "Meeting". There's no conversation to follow up
  in, so there's no follow-up draft. They need speaker attribution.

**Ask** (`vanimo/memory/ask.py`, `vanimo/memory/when.py`, research R05 §5.4):
1. **The question is read in code.**
   - When: "yesterday", "Tuesday's", "last Wednesday", "this morning", "last week", "14 Oct", "3 days ago", "at 4",
     "4 pm", "16:30". A bare 1–7 is the afternoon. Short weekdays count only capitalised ("Sat", not "we sat").
     All in the cell's time zone.
   - Which kinds: "requirements", "decided", "action items", "promised"…
   - Whose: "the client" means people outside the organisation; a name means someone in your meetings; "I promised"
     means you. A first name alone counts only capitalised ("Will", not "what will we do").
   - Which meeting: words of its title.
2. **"The 4 pm meeting"** is the one starting nearest 16:00 (within 45 minutes) that day. If two match, it asks
   which, with buttons; with no day, it takes the most recent and offers the others.
3. **Notes first, then what was said.** Your notes are filtered and scored. Only if no note fits does it search
   the transcript turns (while they're kept).
   - A topic word that isn't in the meeting's title must be in the note, so "what did we decide about Mars?"
     finds nothing rather than every decision.
4. **The answer has numbered citations:** meeting, time span ("Acme weekly sync, Tue 13 Oct · 10:01:30–10:01:51"),
   speaker and the sentence. **Show in meeting** opens the transcript at that turn.
   - Offline: the notes themselves, grouped by meeting.
   - With Bedrock: Claude answers from the numbered notes only, and the question goes as L1 too. The answer must
     cite at least one note, every citation must exist, it may hold only name markers from the notes and no links;
     otherwise the extractive answer is shown.
   - **No evidence, no answer:** "I couldn't find that in your meeting notes", with the closest meetings to ask
     about instead.
5. Everything is re-checked against your rules as they are now before it's shown. Questions aren't stored, and the
   audit log records that you asked, not what. At most 10 questions a minute.

**Admin** (Client scoping → Meeting memory):
- **Remember Teams meetings** (on by default). Off: no meeting is read, and remembered ones aren't shown or
  searched.
- **Check transcript access:**
  - live, with your own sign-in: transcript *metadata* of your recent internal meetings, never content;
  - speaker attribution, from what reading transcripts ran into across the organisation in the last 14 days
    (counts only, `vanimo_private.meeting_ingest_health()`);
  - the application access policy (not needed);
  - what to change in Teams if something is off.

**Try it on the sample workspace:** finish the review, then open **Meetings**.
1. Five meetings are remembered:
   - the last two **Acme weekly syncs** (client requirements, a weekend go-live, your runbook promise, an
     uninvited guest left out, a PAN masked);
   - the **1:1 with Meera**;
   - the **Orion discovery workshop**;
   - **Kestrel all hands**, with speaker attribution off.
2. Not the Falcon steering committee (organised by the client), nor the private doctor's appointment.
3. Ask: "What did the client ask for in the Acme weekly sync?", "What did I promise in meetings?", "What did Lisa
   say about the rollback?", "What did Meera decide?", or a meeting by its day and time ("…in the 4 pm meeting on
   Thursday?").

## Guarantees built in from M0

- **Tenant and user isolation in the database.**
  - The API connects as `vanimo_app`, which is not the owner and can't bypass row-level security.
  - Every request runs in a transaction pinned to one tenant and one user, so rows of other users are invisible.
  - A request with no identity sees nothing.
  - Tests: `tests/test_rls.py`.
- **Content-free logs.**
  - Allow-listed keys and identifier-like values only.
  - Library log messages are dropped.
  - The access log records the route template, not the path.
  - Tests: `tests/test_logging.py` and the canary check in `tests/test_api.py`.
- **Metadata-only Graph reads before the review step.**
  - `vanimo/graph/metadata.py` refuses body fields.
  - Tests pin the `$select` lists.
- **Single-tenant Entra.**
  - The API only accepts v2 tokens for this tenant that carry the `access_as_user` scope and a Vanimo app role.
  - Graph calls are made as the user (On-Behalf-Of).
- **Models only from the cell's allow-list** (Claude on Bedrock: Haiku 5.5 by default, Sonnet 5.5 for premium drafts).
- **Canaries and evals from day one** (`vanimo/canary.py`, `vanimo/evals/`).

## Local development (Windows, PowerShell or Git Bash)

### Option A: everything in Docker (one command)

Prerequisite: Docker Desktop. Run from the repo root:

```bash
docker compose -f app/docker-compose.yml --profile app up -d --build
# http://127.0.0.1:5173 (web)  ·  http://127.0.0.1:8000/api/docs (API)
```

- **What starts:** `postgres` → `migrate` (creates roles and schema, runs `alembic upgrade head`, then exits) → `api` → `web`.
- **Live reload:** both API and web reload on save. The source folders are mounted into the containers, and the containers poll for changes because Windows mounts send no file events.
- **Settings:** compose sets the local database, `VANIMO_ENV=local` and password sign-in. Anything else (e.g. Entra IDs) still comes from `backend/.env` if you have one.
- **First account:** `docker compose -f app/docker-compose.yml run --rm migrate python -m vanimo.ops.local_user --email you@example.com --role superadmin`
- **Logs / stop:** `docker compose -f app/docker-compose.yml logs -f api` · `docker compose -f app/docker-compose.yml --profile app down` (the database volume is kept).
- **After a dependency change** (`pyproject.toml`, `uv.lock`, `package*.json`): `docker compose -f app/docker-compose.yml --profile app up -d --build -V`.
- **Don't mix with Option B on the same ports:** stop one before starting the other (8000 and 5173).
- These dev images (`Dockerfile.dev`) are never deployed; AWS builds `backend/Dockerfile` (see below).

### Option B: run the API and web app directly

Faster for debugging and running single tests. Prerequisites: Docker Desktop, Python 3.14, uv, Node 24.

```bash
# 1. Database (Postgres 18 in Docker, port 5433)
docker compose -f app/docker-compose.yml up -d

# 2. Backend: install, create roles + schema
cd app/backend
uv sync
#    If uv can't create .venv on this machine, run `py -m venv .venv` first.
export VANIMO_DB_ADMIN_URL=postgresql://postgres:postgres_local@127.0.0.1:5433/postgres
export VANIMO_DB_OWNER_PASSWORD=vanimo_owner_local VANIMO_DB_APP_PASSWORD=vanimo_app_local
uv run python -m vanimo.ops.bootstrap_db
VANIMO_DB_OWNER_URL=postgresql+psycopg://vanimo_owner:vanimo_owner_local@127.0.0.1:5433/vanimo uv run alembic upgrade head

# 3. Backend settings: copy .env.example to .env and fill in the Entra IDs + secret (infra/entra/README.md)
uv run python -m vanimo.dev          # http://127.0.0.1:8000 (API docs at /api/docs)

# 4. Frontend: copy .env.example to .env.local and fill in tenant + client IDs
cd ../frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api to the backend)
```

Bedrock calls from your laptop need AWS credentials and `AWS_REGION=ap-south-1`. Everything else works without AWS.

## Tests

```bash
cd app/backend  && uv run pytest -q && uv run ruff check .   # needs the Postgres container
cd app/frontend && npm run typecheck && npm test && npm run build
cd app/infra    && uv run pytest -q                           # synthesises the stacks; no AWS needed
cd app/backend  && uv run python -m vanimo.evals --dataset evals/datasets/synthetic_v0.jsonl --drafter reference
```

CI runs the same steps (`.github/workflows/ci.yml`) against Postgres 18 and 17.

## Deploy the India cell (once AWS access is in place)

1. **AWS credentials.**
   - `aws configure sso` (or keys) for the target account.
   - In the Bedrock console (ap-south-1), check that **Claude Haiku 5.5** and **Claude Sonnet 5.5** are enabled.
2. **Bootstrap CDK once:** `cdk bootstrap aws://<account>/ap-south-1`.
3. **Build the frontend:** `cd app/frontend && npm run build`.
4. **Deploy:**

   ```
   cd app/infra
   cdk deploy --all -c cell=in -c entra_tenant_id=<tid> -c entra_client_id=<client-id>
   ```

5. **Set the Entra client secret** in Secrets Manager (`infra/entra/README.md` step 7). Then run `aws ecs update-service --force-new-deployment` on the API service.
6. **Create roles and run migrations.** Use the outputs `ClusterName`, `MigrateTaskDef`, `TaskSubnets` and `TaskSecurityGroup`:

   ```
   aws ecs run-task --region ap-south-1 --launch-type FARGATE --cluster <ClusterName> --task-definition <MigrateTaskDef> \
     --network-configuration "awsvpcConfiguration={subnets=[<subnet1>,<subnet2>],securityGroups=[<sg>],assignPublicIp=DISABLED}"
   ```

   Re-run it after every deploy that adds a migration.
7. **Register the URLs with Entra:**
   - add the `RedirectUri` output (`https://<cloudfront-domain>/redirect.html`) as a SPA redirect URI;
   - add `brk-multihub://<cloudfront-domain>` for the add-in.

## Known deviations from the target architecture (M0)

These are deliberate for 2–3 internal users and are listed again in the pre-external-customer checklist (`docs/03` §0, "Deferred"):

| Area | Target (`docs/02`) | M0 | Before external customers |
|---|---|---|---|
| API runtime | API Gateway + Lambda BFF, separate drafting service (§4.2) | One FastAPI service on ECS Fargate behind an internal ALB, reached only through CloudFront (VPC origin). ~~Revisit in M3~~ (M3): drafting runs inside this service; it is already warm | Split drafting into its own service when load or latency needs it (measure p95 in the pilot) |
| Egress | No internet egress from the data plane; Graph/Bedrock allow-list (Network Firewall / DNS Firewall) (§4.2) | API tasks reach the internet through one NAT gateway | Add the egress allow-list and WAF |
| Bedrock IAM | Scoped to allowed models | `bedrock-mantle:CreateInference` on `*`, limited to the cell region. The model allow-list is enforced in code | Scope to model ARNs once the ARN format is published |
| Keys | Per-tenant CMKs, per-user data keys (§8.2) | One cell CMK | Per-tenant keys arrive with external tenants |
| Entra | Read app + Compose app; certificate in KMS, no client secret (§5.1–5.2) | One app with a client secret in Secrets Manager (D8) | Split the apps; switch to a certificate |
| Add-in CSP | Enforced | Report-only until the add-in spike confirms Outlook's hosts. Still report-only after M3: the spike needs the Entra app and a deployed cell, which don't exist yet | Enforce right after the add-in spike |
| Stores | S3 Vectors, DynamoDB, Valkey | Aurora only | Added when M2/M4 need them |
| Vault | Separate vault account; KMS per-tenant CMK with per-user data keys, so deleting a user's key crypto-shreds their data (§7.2 S8, §8.2) | AES-256-GCM keys derived (HKDF) from one master key in Secrets Manager | Move to KMS data keys before external customers |
| Purge | Step Functions job across all stores (§6.5 X7) | In-process job. ~~M1 has no derived content yet~~ (superseded in M2): purges the L1 items, tokens, vectors and style cards by lineage, re-masks the Sources index, L1 text and studio phrases, and writes receipts | Move to Step Functions with the queue |
| Redaction (M2 vs §7.2) | NER ensemble (Presidio/spaCy, GLiNER, IndicNER), contextual Tier C/S classifier, Guardrails, Macie backstops, vault service in a separate account | Deterministic detectors + checksum validators + the M365 header/directory gazetteer. Names that never appear in a header or the directory stay in L1. No Tier C/S classification (client sensitive words are stored but not yet applied). Token map in Aurora, vault-encrypted | Add NER + the contextual classifier (needs AWS, D7) before external customers |
| Embeddings and drafting (M2) | Bedrock embeddings + S3 Vectors; Claude Haiku 5.5 drafter | Local hashing-trick vectors (`vanimo/learning/embed.py`) in Aurora; an offline drafter (`vanimo/llm/offline.py`), clearly labelled, used only for the evaluation baseline. (M3: live drafting uses Claude through `vanimo/drafting/generate.py` when `VANIMO_DRAFTER=bedrock`, always in a deployed cell; locally a separate offline stand-in) | Swap in Bedrock embeddings behind the same functions once the AWS account exists |
| Drafting (M3 vs §9.1–9.2, §9.4) | One streaming call, p95 first token ≤ 2.5 s; persona prefix padded to ≥ 4,096 tokens for caching; post-generation leakage judge; LLM revise on failed style checks | The output gate needs the whole text before anyone sees it, so the draft is returned whole: measure p95 *total* time instead. The persona block is marked for caching but not padded. No leakage judge yet (needs a model): cross-audience leakage is limited by sending other audiences' messages only as shapes. Revise runs once, only on failed checks. Pre-send checks are rules, not a model. No separate "audience card"
 (history with this person beyond the examples), and greeting and sign-off use your most common form rather than a
 sample from your distribution | Measure latency and caching on Bedrock in ap-south-1; add the leakage judge to the release gate before external customers |
| Drafts in the Drafts folder (M4 vs §3.2, §9.1) | Proactive: a webhook on new mail → "needs reply" triage model → `createReply` in the background (Step Functions); stale-draft cleanup on a schedule | Made when you open the Queue or press Prepare, and tidied when you open it. A background job has no Microsoft 365 token (we keep no refresh tokens, and webhooks need a public endpoint), so nothing happens while you're away. Triage is rules (automated sender, To vs Cc, question/request/scheduling), not a model | After deploy: change notifications + a background token strategy (or the Compose app with application permissions), then proactive drafts for reply-likely mail |
| Edit loop (M4 vs R05 §2.3, §7.7) | Haiku edit classifier, nightly LLM verification of rule candidates against held-out mail, Teams edits, add-in send-time capture, confidentiality deletions as negative ACL evidence | Rule-based edit taxonomy and deterministic verification against your sent mail; matching runs when you open the Queue or Persona tab; email only (Teams in M5); no send-time capture; content edits are counted only (there is no memory store to correct until M6). Rules to confirm are shown on the Persona tab, not sent as a weekly digest (no
 notification channel until M5). Matching waits 72 h rather than R05's 24 h, because it only runs when you open the
 app. "No reply needed" choices are thread HMACs and stay after an exclusion (like the exclusion rule itself).
 **M5:** Teams edits and the weekly digest are done (the digest is a count in the web app and the Teams activity
 feed); chat edits teach only channel-neutral rules | Add the classifier and LLM verification with Bedrock |
| Language (D6 vs M2) | English-only drafting in the MVP; Hindi/Hinglish wait for their own quality gate | M2 *labels* each message English, Hinglish or Hindi and keeps their style slices apart, so Hinglish chats don't skew the English cards. Nothing is drafted in Hinglish | Unchanged: Hinglish drafting needs its own quality gate (v1.5) |
| Never-send matching (M1 review) | Research 12: invisible characters removed | Zero-width spaces are still removed, not treated as spaces, so splitting a word with them ("Fal​con") can't dodge the filter. The cost: two words glued by a zero-width space ("the​falcon") don't match a *word* (they do match a codename) | Revisit with ICU word segmentation |
| Data controls (M1 vs §6.5 / research 12) | One table of rules for admins and users; rule states active → purging → purged / held; admins can also exclude specific chats; Aho–Corasick + ICU word segmentation; internal people merged by Entra object ID; review reminders at 24 h and 48 h | Organisation rules live in their own tables (client accounts with domains and approved/excluded mode) and go through the same engine. Rules are active or revoked; purging happens in receipts. No admin chat exclusion (admins can't see users' chats). The matcher uses plain string search with Unicode-category word boundaries (letters, marks and digits are word characters, so Devanagari matras stay attached). People are keyed by email address. No reminders yet (no notification channel until M5; **done in M5**: the review reminder at 24 h and 48 h, as
a count in the web app and the Teams activity feed). Words inside email addresses are masked on screen, but the address itself is kept encrypted, because it identifies the person | Before external customers: Aho–Corasick for large lists, OID merge, admin chat rules. Reminders come with Teams in M5 |
| Commitments (M5 vs R05 §5.3–5.4, R09) | Typed memory atoms across email, chat and meetings, extracted by Haiku and consolidated by Sonnet; cross-channel linking; promises others made to you; nudges | The user's own promises only, from sent email and Teams chats (~~meetings arrive with M6~~ **M6:** and Teams meetings, with speaker attribution; no follow-up draft for those). Rules offline, Haiku on Bedrock, both checked against the text in code. Due dates resolved in code in the cell's time zone, not the user's own (no `MailboxSettings.Read` yet). "Looks done" is a word-overlap hint, never automatic. Found after learning and when you open the tab (no background token), within 60 days | Measure precision on Bedrock against the ≥ 80 % target; add others' promises to you, the user's own time zone, and meeting commitments (M6) |
| Teams (M5 vs R02 §B, architecture §5) | Personal agent (Agents SDK) + message action + compose extension; RSC for chat context; dialog with Copy / prefill / Send as me | Message action + compose action only (the personal agent is v1.5). Copy always; open-the-chat prefill behind an admin switch until spike 1. Chats only, not channels. Context comes from Graph with the user's token after the exclusion engine decides, never from the invoke. The Teams page's CSP is report-only (like the add-in) until the hosts are confirmed | Run spike 1 and the Teams CSP check on desktop, web and mobile; then the personal agent (v1.5) |
| Meeting memory (M6 vs R05 §5, architecture §6.2, §9.3–9.4, R02 §D) | Transcript subscriptions created at enrolment (they must exist before transcription starts), change notifications, auto-transcribe for enrolled organisers; episodes from calendar + silence + speaker/topic shifts; Haiku per-chunk extraction then Sonnet per-episode consolidation and cross-episode linking; hybrid retrieval (S3 Vectors + full text); a Haiku query parser; answers by Sonnet/Haiku on AgentCore with audio snippets; recall Q&A in a Teams personal agent | Pulled when the user opens the Meetings tab (no background token or webhooks yet), so a meeting is remembered the next time they look, not minutes after it ends. One episode per calendar occurrence with a transcript (no unscheduled sessions: no recorder until Phase 2). Rule-based notes offline, Haiku on Bedrock with every quote checked; no consolidation step or cross-meeting linking (a repeated action item is two notes). Retrieval is SQL + keyword scoring over decrypted notes, no vectors. The question is parsed in code, not by a model. Answers in the web app and the Teams tab (the personal agent is v1.5); no audio (Teams audio is never fetched). Only the user's own promises go to the ledger. Speech by people not on the invite whom the user doesn't know is left out. Meetings of other companies and channel meetings aren't covered (Graph has no transcripts of the first; the second weren't tested) | Spike 4 on real meetings (attendee access, attribution off, latency); then subscriptions + a background token, Bedrock embeddings, the consolidation step, and measure note precision/recall and citation precision (R05 §5.6 targets) on dogfood questions |
| Notifications (M5) | Teams bot proactive messages and email digests | Content-free counts in the web app and the Teams activity feed (Graph `sendActivityNotification`, app-only `TeamsActivity.Send`). No email digest. Delivery needs the Teams app installed; without it, notifications are in the web app only | Add the permission and install the app after deploy |
| Background work | Step Functions / durable queues | In-process tasks, plus a sweeper every 5 minutes that resumes interrupted purge jobs and fails scans cut off by a restart (`vanimo/controls/sweeper.py`) | Move to a queue when there is more than one API task |
| Housekeeping functions | Separate sweeper role | `vanimo_private.fail_stale_scans` / `claim_purge_jobs` / `notification_candidates` (M5) / `expire_meeting_memory` (M6) are SECURITY DEFINER functions the API role can call. They act across tenants and return only IDs. `record_org_domains` accepts domains from Microsoft 365 scans, plus the sample domain in the local tenant only | Give the sweeper its own database role; add an admin view of recorded organisation domains |
| Sources index | One index per data source | One index per user. After switching between the sample workspace and Microsoft 365, the old index is hidden until the new scan finishes. Reviews are remembered per source | Split the index by source if both are used side by side |
| Sign-in | Entra only | Also email + password, local/dev only, for testing while the Entra app is pending | Removed or kept off in prod (the settings refuse it) |

## M0 demo and week-1 spikes

**Demo:** open the `WebUrl`, sign in. You should see your name, your manager and the subjects of your last 5 sent emails. Only headers are read; nothing is stored.

**Spikes:** use the Diagnostics and Teams prefill tabs, which need the `Vanimo.Admin` role. Record the results in `docs/05` §5.

| # | Spike | How |
|---|---|---|
| 1 | Teams prefill in existing chats | *Teams prefill test* tab: tests A and B on desktop, web and mobile. **M5:** also from the Teams dialog ("Draft reply" → turn on *Open Teams chats with the draft typed in* on Client scoping → *Open the chat with this text*), since TeamsJS `chat.openChat` from a dialog is undocumented. If it passes everywhere, leave the switch on |
| 2 | Add-in insert/read | Render the manifest and add it in Outlook (*Get add-ins → My add-ins → Add a custom add-in*). Test sign-in and insert in new Outlook, classic, web and Mac:<br>`py surfaces/outlook-addin/render_manifest.py https://<cloudfront-domain> > manifest.xml` |
| 3 | Graph delta details, `MSIP_Labels` | Diagnostics → *Run checks*: `sent_headers` and `sent_delta_headers` rows. **`uniqueBody` in delta moves to M2:** it needs a message body, and no body is read before the user's review step. The quote-stripper fallback is planned anyway |
| 4 | Transcript access as organiser/attendee | Diagnostics → `meeting_transcripts` row. **M6:** Client scoping → *Check transcript access*, then open **Meetings** after a real internal meeting with transcription on, as the organiser and as an attendee. Turn speaker attribution off in a test tenant and check the meeting is stored without names. Note how long after the meeting its transcript appears (no Microsoft SLA) |
| 5 | Drafts on Outlook mobile | Diagnostics → *Create test draft*, check the phone, then *Delete*. **M4:** also check that a Queue draft (Graph `createReply` with `comment`) keeps its line breaks and shows inside the conversation on iOS/Android, and that an edited-then-sent draft keeps its immutable ID (the Queue shows "You sent it") |
| 7 | Latency from Mumbai | Diagnostics → *Measure latency* (Haiku 5.5, Sonnet 5.5) |
| 11 | Data-control Graph checks | Diagnostics:<ul><li>*Run checks*: chat roster, `chatType` and `topic` filters, `conversationId` on forwards, calendar</li><li>*Time the header pass*: how long the M1 metadata review takes to build</li></ul>Header-only subscriptions wait for M1, because they need a public webhook |
