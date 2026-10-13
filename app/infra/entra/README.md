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
| `OnlineMeetingTranscript.Read.All` | Meeting transcripts | M0 test/M6 |

> `OnlineMeetings.Read` is not in the access list in `docs/03` §0. It's needed to find a meeting's ID from the calendar event, before its transcripts can be listed.

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
