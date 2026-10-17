# Entra app registration: Vanimo (single tenant, D8)

One app registration in the organisation's own tenant. It is the web app, the Outlook add-in and the API at the same time. Before any external customer it is split into a **Read** app and an opt-in **Compose** app (`02-solution-architecture.md` §5.1).

Someone with **Application Administrator** (or Cloud Application Administrator) in Entra can do steps 1–7. Step 8 needs a **Privileged Role Administrator** or **Global Administrator**, because it grants admin consent.

## 1. Register

Entra admin centre → **App registrations** → **New registration**:

- Name: `Vanimo`
- Supported account types: **Accounts in this organizational directory only** (single tenant)
- Redirect URI: platform **Single-page application (SPA)**, `http://localhost:5173/redirect.html`

Copy the **Application (client) ID** and **Directory (tenant) ID**.

## 2. Redirect URIs (Authentication → Single-page application)

| URI | Why |
|---|---|
| `http://localhost:5173/redirect.html` | Local development |
| `https://<cloudfront-domain>/redirect.html` | The deployed web app (CDK output `RedirectUri`) |
| `brk-multihub://<cloudfront-domain>` | Outlook add-in sign-in through nested app authentication (host only, no `https://`, no trailing slash) |

MSAL v5 sends every sign-in through the `/redirect.html` bridge page: full-page redirects, popups, and the hidden iframe used for silent renewal. Register exactly these URIs. The step 1 registration used `http://localhost:5173/`; replace it.

Leave **implicit grant** off. Leave **Allow public client flows** set to **No**.

## 3. Expose an API

- **Application ID URI**: `api://<client-id>` (accept the default).
- **Add a scope**:
  - name `access_as_user`;
  - who can consent: **Admins only**. Users never consent to it themselves. The API also accepts only tokens issued to Vanimo's own client (`azp` must equal the client ID), so no other app in the tenant can use Vanimo's Graph permissions.
  - admin consent display name "Use Vanimo as you".

## 4. Access token version (Manifest)

In **Manifest**, set `"requestedAccessTokenVersion": 2` (under `api`). The API accepts only v2 tokens.

## 5. App roles

Create two roles. For each: allowed member types **Users/Groups**, enabled.

| Display name | Value | Who |
|---|---|---|
| Vanimo user | `Vanimo.User` | Everyone who may use Vanimo |
| Vanimo admin | `Vanimo.Admin` | The founder; later IT admins. Opens diagnostics, client scoping (M1) |

The API rejects any token without one of these roles, even if Entra let the person sign in.

## 6. API permissions (Microsoft Graph, Delegated)

| Permission | Used for | Milestone |
|---|---|---|
| `openid`, `profile`, `offline_access`, `User.Read` | Sign-in; background sync later | M0 |
| `User.Read.All` | Manager chain, job titles (relationship labels) | M0 |
| `Mail.Read` | Sent Items headers, then bodies of allowed sources only | M0/M2 |
| `Mail.ReadWrite` | Drafts in the Drafts folder (M0 test, M4) | M0/M4 |
| `Chat.Read` | Chat list and members, then allowed chats | M1/M2 |
| `Calendars.Read` | Meetings for exclusions and meeting memory | M1/M6 |
| `OnlineMeetings.Read` | Look up a meeting from its join link | M0 test/M6 |
| `OnlineMeetingTranscript.Read.All` | Meeting transcripts (delegated: the organiser and invited attendees can read them) | M0 test/M6 |

> `OnlineMeetings.Read` is not in the access list in `docs/03` §0. It's needed to find a meeting's ID from the calendar event, before its transcripts can be listed.

**Application permission (M5), also on this app:**

| Permission | Used for | Milestone |
|---|---|---|
| `TeamsActivity.Send` (Application) | Reminders in people's own Teams activity feed (promises due, rules to confirm, the review). A person can't send a notification to themselves with a delegated token, so this one is app-only. Notifications carry counts only, never content | M5 |

> `TeamsActivity.Send` is not in the access list in `docs/03` §0. Without it Vanimo still works: notifications show in the web app only.

## 6a. Teams meeting transcripts (M6)

Vanimo reads transcripts **as each signed-in person** (delegated `OnlineMeetingTranscript.Read.All`), which works for
the organiser and for anyone in the meeting's calendar invite. So **no Teams application access policy is needed**
(that's only for application permissions). A Teams admin still has to:

1. **Allow Graph access to transcripts:** Teams admin center → Meetings → Meeting settings → *Transcript API access*
   (or `Set-CsTeamsMeetingConfiguration`). Off by default since the end of July 2026; while it's off, every
   transcript call answers `403 GraphAccessToTranscriptsDisabled` and Vanimo remembers no meetings.
2. **Allow speaker attribution** (the setting next to it). Without it Vanimo reads the unattributed format: notes have
   no names, "what did the client ask for?" can't tell the client from your colleagues, and your promises in meetings
   can't be found.
3. **Allow transcription** in the meeting policy for the people using Vanimo (people still start it, or organisers
   turn on automatic transcription for their meetings).

Then check it: Client scoping → **Meeting memory** → *Check transcript access*.

## 6b. Teams app and bot (M5)

1. **Bot.** Teams message actions ("Draft reply") need a bot registration. In the Teams Developer Portal: **Tools → Bot management → New bot** (single tenant, no Azure subscription needed). Set its **endpoint** to `https://<cloudfront-domain>/api/teams/messages`. Note the bot ID. Vanimo answers only Teams' `composeExtension/fetchTask` requests on it and checks every request's Bot Framework token; no client secret is needed because it never posts as the bot.
2. **Package.** `py app/surfaces/teams-app/render_manifest.py https://<cloudfront-domain> <bot-id> <this app's client ID> vanimo-teams.zip` builds the Teams app (manifest + icons). The manifest's `webApplicationInfo.id` is this Entra app, which is what lets it send activity notifications.
3. **Settings.** Deploy with `-c teams_app_id=6eb7a34e-98f7-47fd-a00a-58b5f900f9be -c teams_bot_id=<bot-id>` (or `VANIMO_TEAMS_APP_ID` / `VANIMO_TEAMS_BOT_ID` locally).
4. **Install.** The package has two personal tabs, Commitments and (M6) Meetings. A Teams admin uploads the zip (Teams admin center → Manage apps → Upload) or allows custom app upload; people add it from Apps. Activity notifications only reach people who have the app installed.
5. **Sign-in inside Teams** uses nested app authentication: the `brk-multihub://<cloudfront-domain>` redirect URI in step 2 covers Teams too.

## 7. Client secret (Certificates & secrets)

Create a client secret (6–12 months). **Never put it in code or Git.**

- **Local:** put it in `app/backend/.env` as `VANIMO_ENTRA_CLIENT_SECRET=...` (the file is git-ignored).
- **AWS:** after the first deploy:

  ```
  aws secretsmanager put-secret-value --region ap-south-1 --secret-id <EntraClientSecret ARN from the data stack> --secret-string '<value>'
  ```

  Then restart the API service.

A certificate in KMS replaces the secret before external customers (`02` §5.2).

## 8. Admin consent and assignment

- **API permissions** → **Grant admin consent for <organisation>**.
- **Enterprise applications** → Vanimo → **Properties** → **Assignment required? = Yes**.
- **Users and groups** → add a group (for example `Vanimo pilot`) with role `Vanimo.User`, and the founder with `Vanimo.Admin`.

## Checks

- Sign in at the web app. Home shows your name, your manager and your last 5 sent subjects (the M0 demo).
- Someone outside the group gets "not assigned" at sign-in (Entra), or `not_assigned` from the API if their token has no role.
- If Home shows *"Vanimo needs admin consent"*, step 8 is missing.
