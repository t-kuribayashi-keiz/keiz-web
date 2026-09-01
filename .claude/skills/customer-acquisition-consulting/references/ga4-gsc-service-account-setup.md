# GA4 / GSC / Sheets service-account setup — detail

Use this when a session has no ready-made GA4/GSC connector and the client wants automated monthly pulls rather than a fragile "log into the dashboard and screen-scrape" approach. This is a general technique, reusable across clients — not specific to any one engagement.

## Why a service account, and not the browser

Two options exist once you've confirmed GA4/GSC have no MCP connector in this session:

- **(a) A free Sheets add-on** (e.g. "Search Analytics for Sheets" for GSC, or GA4's own Sheets add-on) that the client sets up themselves to auto-export into a Google Sheet Claude can then just read via Drive. Fully automatable on Claude's side, but depends on the client installing and configuring the add-on correctly, and on it continuing to run.
- **(b) A Google Cloud service account** hitting the GA4 Data API / Search Console API / Sheets API directly. This is the one that made it into the actual build, because it puts full control in Claude's hands (no add-on to babysit) once initial permissions are granted, and doesn't depend on repeated browser logins or UI stability.

Screen-scraping the GA4/GSC dashboards via browser automation every month was explicitly rejected as an approach — it's brittle against login-state changes and UI redesigns, and doesn't scale to a recurring job.

## No Python/Node on this machine — use curl + openssl instead

This machine was confirmed (via `Bash`/`PowerShell`) to have no working Python or Node.js runtime (a `python` shim resolves to a non-functional Windows Store stub). It does have `curl` and `openssl`, which is sufficient for the full service-account OAuth2 flow:

1. Build a JWT claim set (`iss` = service account email, `scope` = space-separated list of required scopes, `aud` = `https://oauth2.googleapis.com/token`, `iat`/`exp`).
2. Base64url-encode header + claims, sign the resulting string with the service account's RSA private key (from the downloaded JSON key file) using `openssl dgst -sha256 -sign`.
3. Exchange the signed JWT for an access token via `curl -X POST https://oauth2.googleapis.com/token -d "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=<signed_jwt>"`.
4. Use the returned bearer token with `curl -H "Authorization: Bearer <token>"` against the actual API (Sheets API `spreadsheets.values.get`/`update`, GA4 Data API `runReport`, GA4 Admin API `properties.list`, Search Console API `sites.list`/`searchanalytics.query`).

This was verified working end-to-end for a Sheets API read/write round-trip in the originating engagement — a good smoke test to run immediately after any new service account is wired up, before building anything more elaborate on top of it. Necessary scopes to request in the JWT depend on which APIs are needed, e.g. `https://www.googleapis.com/auth/analytics.readonly`, `https://www.googleapis.com/auth/webmasters.readonly` (or `.readonly`→full as needed), `https://www.googleapis.com/auth/spreadsheets`.

## Google Cloud Console click-path

1. **New project**: console.cloud.google.com → project switcher → "New project" → any name (e.g. `<client>-consulting`).
2. **Enable APIs** ("APIs & Services" → "Library", search + enable each):
   - Google Analytics Data API (for report queries)
   - Google Analytics Admin API (only needed if you must auto-enumerate GA4 properties — see below)
   - Google Search Console API
   - Google Sheets API
3. **Service account**: "APIs & Services" → "Credentials" → "Create credentials" → "Service account" → name it (e.g. `<client>-reporter`) → skip role assignment → done. Note the generated email, `<name>@<project-id>.iam.gserviceaccount.com`.
4. **Key**: open the service account → "Keys" tab → "Add key" → "Create new key" → JSON → download.
5. **Grant access** (see the account-vs-property distinction below for GA4).
6. **Save the key file** to a local path the client tells you, and read it only from there — never have its contents pasted into chat.

## GA4: grant at the account level, not per property

For a client with multiple GA4 properties (e.g. one per store) under a single GA4 account, grant the service account **account-level** access rather than repeating the process per property:

> GA4 admin UI → left-hand "アカウント" (Account) column → "アカウントのアクセス管理" (Account Access Management) → "+" → add the service-account email → role "閲覧者" (Viewer)

This one grant covers every property under that account. Granting only at the property level (the more obvious-looking option) requires repeating the grant once per store and was the wrong first guess in the originating engagement — an empty `{}` response from the GA4 Admin API's property-list call was the symptom that revealed only property-level (or no) access had been granted, not account-level.

## GSC: per-property only, no bulk option

Search Console has no equivalent account-level bulk grant — each property/site needs "ユーザーを追加" (Add user) done individually, with "フル" (Full) permission for the service account. The upside: once granted, `sites.list` via the Search Console API can auto-enumerate every site the service account can see, so the client never needs to hand-type site URLs (`sc-domain:...` vs `https://.../` format) — just confirm each grant went through.

## Credential-handling failure mode actually hit, and the fix

Downloading the JSON key through a **sandboxed automation browser** (as opposed to the user's own real, already-logged-in browser) put the file in that browser's isolated container filesystem, which was not reachable from Claude's normal file tools — confirmed by checking network requests and the local filesystem directly. Two things follow from this:

- **Don't try to work around it by extracting the key's contents via injected JavaScript** reading it out of browser memory/the download event before it lands on disk — this was attempted once and correctly refused by a safety guardrail as equivalent to credential exfiltration. Accept the refusal; don't retry with a different injection technique.
- **The actual fix**: delete the orphaned, content-unrecoverable key from the Cloud Console (Keys tab → trash icon → confirm), then ask the user to do the download themselves in their own real, logged-in browser, move the resulting JSON file to a local folder, and hand you the path. Only ever read the key from that local path afterward.

## Smoke test after wiring up auth

Before building any report logic, confirm the whole chain works with a minimal Sheets API call (e.g. read a known cell range from the target spreadsheet using the fresh access token). A successful read/write here is strong evidence that: the JWT signing is correct, the token exchange succeeded, and the "editor" grant on the spreadsheet reached the right service account email. Do this before spending more time on GA4/GSC-specific query building.
