---
name: customer-acquisition-consulting
description: Use this skill when the user takes on (or is already running) marketing/customer-acquisition (集客) consulting for a multi-location client business, and wants to build a data-driven reporting system that merges self-reported KPIs with automated pulls from GA4, Google Search Console, SEO rank tools (e.g. GRC), and MEO rank tools (e.g. MEOチェキ). Also trigger when the user wants to set up a Google Cloud service account so Claude can hit the GA4 Data/Admin API, Search Console API, or Sheets API directly (without a Python/Node runtime, using curl+openssl), for any client — not just the one this was first built for. Do NOT assume this describes a proven, fully-running monthly report engine: the session this skill was extracted from designed the architecture and got partway through the Google Cloud/service-account plumbing, then stalled waiting on a client permission grant. Treat this as a framework + technical playbook to restart or replicate, not a finished recurring job.
---

# Customer-Acquisition Consulting: Data Pipeline & Analytics Automation

Framework for consulting a client (typically a multi-location service business — the originating case was a chain of 整骨院/接骨院, orthopedic manipulation clinics) on customer acquisition (集客), where the goal is to replace a purely self-reported, disconnected set of monthly numbers with one data backbone that lets Claude operate as autonomously as possible: pulling leading-indicator data itself via API, and reserving manual client input for only what genuinely can't be automated (the actual acquisition/booking counts, when the client has no tracking system for them).

This is **not yet a proven, running recurring pipeline** — see `references/background.md` for exactly how far the originating engagement (T&D Group, 8-store 整骨院 chain, `td-group.jp`) got before it stalled on a client-side permission grant. What generalizes across clients is the data architecture and the technical setup pattern below.

## Non-negotiable rules

1. **Never enter a password, 2FA code, or identity-verification input into an automated/scripted browser.** If a Google (or any) login flow demands this, stop and ask the user to complete that one step themselves in their own logged-in browser (or the visible Browser pane, if that's already authenticated) — then resume. This came up directly: an automation browser hit a re-authentication prompt and correctly stopped rather than trying to push through it.
2. **Never write the contents of a downloaded credential/key file (e.g. a GCP service-account JSON key) into chat, and never attempt to extract it from a browser's memory/sandbox via injected script.** A prior attempt to capture a JSON key's contents via `javascript_tool` before the download dialog completed was correctly blocked by a safety guardrail as functionally equivalent to credential exfiltration — do not try to route around a block like that. If a downloaded file lands in an automation browser's isolated sandbox and is unreachable from the normal filesystem, that's a hard limitation: ask the user to download it in their own real browser and move it to a local path instead, and only ever read it from that local path.
3. **If a generated key's raw content is unrecoverable, revoke/delete it in Google Cloud Console rather than leaving an orphaned valid credential behind.**
4. **Be precise about "no API" vs "no connector."** GA4/GSC/Sheets all have official REST APIs. If this session's MCP tool list has no ready-made connector for them, say so exactly that way — don't tell the user "there's no API," which is factually wrong and was called out as such mid-session. The correct fallback in that situation is direct API access via a Google Cloud service account (see `references/ga4-gsc-service-account-setup.md`), not "check the dashboard manually every month."
5. **Two different "browser" surfaces can both be present in a session — don't confuse them.** A separate real-Chrome-extension automation surface and the sandboxed Browser pane preview are not the same login state; mixing them up (as happened once) wastes turns clicking into the wrong, unauthenticated tab. Confirm with `tabs_context` which surface is actually logged in before driving it.

## The data architecture (the reusable core)

The client's existing artifact is almost always a monthly hand-filled spreadsheet mixing three things that need separating: (a) an outcome number nobody but the client can measure (bookings/inquiries by channel), (b) a checklist of what work was actually done (○/△/✕ per channel), and (c) leading-indicator numbers that live in other systems the client already has access to but has never pulled into one place.

**Design**: keep the client's existing monthly hearing sheet as the human-input surface, but build a second, automatically-populated "integrated log" in **long format** — one row per `(year-month, store, channel, metric, value)` — and load every available source into it:

| Source | What it contributes | How it's obtained |
|---|---|---|
| Client's monthly hearing sheet | Acquisition count, by store × channel (SEO/MEO/Google PPC/Meta ads/HPB/EPARK-style portals, plus totals) | Manual, as-is — this is the one thing genuinely un-automatable without the client adopting call/booking tracking |
| Checklist tab | Which measures were actually executed, per channel, per month | Manual, but log it over time (time series) rather than overwriting — the value is watching ✕→○ transitions |
| GA4 | Sessions, channel-level traffic, per-store-page pageviews, conversions (booking button / phone tap / LINE click) | Automated via GA4 Data API (see technical reference) |
| GSC | Impressions/clicks/CTR/average position, by query and by page | Automated via Search Console API |
| SEO rank tool (e.g. GRC) | Keyword × store rank history | Usually a desktop-only tool with no API — have the client (or their vendor) drop a CSV into a shared Drive folder monthly; Claude ingests from there |
| MEO rank tool (e.g. MEOチェキ) | Map-pack rank, review count/rating trend, per store | Same CSV-to-Drive-folder pattern as above, if it has no API |

Once this log exists, the actual consulting value is the correlation work it enables: for each store, do movements in leading indicators (rank, traffic, CTR) precede movements in the self-reported acquisition number, and by how long? That lag relationship is what turns "we improved SEO ranking" into "and it shows up in bookings ~N months later," which is the evidence a consulting recommendation needs. Don't skip straight to dashboards before this join is possible — the join is the point.

See `references/data-architecture.md` for the full source/metric table as actually specified for the originating client, store-list-to-URL-path mapping technique (useful for single-GA4-property-per-domain clients), and the GA4-property-per-store variant that this specific engagement turned out to need instead.

## Technical setup: Google Cloud service account for GA4/GSC/Sheets

When this session's tools have no ready-made GA4/GSC connector, the direct-API-via-service-account route is the one to propose (over screen-scraping the dashboards, which is fragile and non-automatable long-term). Full step-by-step — the exact Google Cloud Console click-path, the account-level vs property-level permission distinction between GA4 and GSC, and the curl+openssl JWT auth technique for machines without Python/Node — is in `references/ga4-gsc-service-account-setup.md`. Key points worth knowing before opening that file:

- This machine has no Python or Node runtime, but does have `curl` and `openssl`, which is enough to do the full JWT-signing → OAuth-token-exchange → REST-call flow for any Google API a service account can reach. This is a general-purpose technique, not specific to this client — reuse it for future engagements needing GA4/GSC/Sheets/Drive automation on this machine.
- GA4 access can be granted once at the **account** level (covers every property under that account, e.g. one grant per client covering all their stores) — GSC has no equivalent bulk grant and needs one per property/site. Ask which the client's setup needs before telling them how many times to grant access.
- If store pages live under one shared domain with clean per-store URL paths, GA4/GSC can be segmented by store using a `pagePath` prefix filter on a single property — no per-store property needed. If the client instead already has one GA4 property per store (as this engagement turned out to have, revealed only after the user pointed it out), use the GA4 Admin API to auto-enumerate properties and match them by name instead of asking the client to hand-type property IDs.

## Suggested workflow for a new engagement

1. Read whatever spreadsheet/sheet the client already uses for reporting, and fetch the client's site structure (store list, URL paths) — don't design the schema before seeing what already exists.
2. Lay out the source/metric table above for this specific client, and be explicit with them about which parts are fully automatable now vs. need a CSV-drop workaround vs. must stay manual.
3. If GA4/GSC automation is wanted, walk the client through the Google Cloud Console setup in `references/ga4-gsc-service-account-setup.md`, respecting the non-negotiable rules above throughout (never touch their login, never handle the raw key except by reading a path they give you).
4. Once service-account auth is verified (a simple Sheets API read/write round-trip is a good smoke test — see the reference), build the long-format integrated-log ingestion and the store/channel join, then only after that, build the correlation analysis and monthly write-up.
5. Log where the engagement actually got to at the end of each session (this one stalled at "waiting on client to grant GA4 account-level access") so the next session picks up from the true state rather than assuming further-along progress.

## Reference files

- `references/data-architecture.md` — full metric/source table, store list and URL-path mapping as specified for the originating client, and notes on the single-property-vs-per-store-property GA4 branch.
- `references/ga4-gsc-service-account-setup.md` — the Google Cloud Console click-path (project → enable APIs → service account → key), the account-vs-property permission distinction, the curl+openssl JWT/OAuth technique with the actual working command shapes, and the credential-handling failure modes hit along the way.
- `references/background.md` — narrative of the T&D Group engagement this skill was extracted from: the client, the back-and-forth that shaped the design, and exactly how far the technical setup got before the session went idle.
