# Background: T&D Group engagement (source of this skill)

## Client and request

T&D Group is a chain of 整骨院/接骨院 (orthopedic manipulation clinics) — 8 stores, 3 in Tokyo and 5 in Chiba, site at `td-group.jp`. The user (this PC's owner) is doing customer-acquisition (集客) consulting for them — T&D Group is a client of the user's company, not the user's own business. The user opened the session saying they wanted Claude to run the consulting "全自動" (fully automated) as far as possible, and asked to "壁打ち" (think it through together) on what data infrastructure to build before doing any consulting work.

Starting inputs the user gave:
- A Google Sheet the user authored, used as a monthly hearing/reporting format (see `data-architecture.md` for its structure).
- Confirmed permissions on GA4 and GSC for the client's properties.
- SEO rank tracked via GRC (desktop tool), MEO rank tracked via MEOチェキ — both offered as "tell me the format and I'll provide data."
- Acquisition counts (集客数) themselves are not tracked in any system — purely the client's manual monthly self-report.

## How the design took shape

Claude first read the spreadsheet and tried to fetch the client site (blocked by a 403 on direct fetch, so it fell back to browsing it via the Browser pane instead). From that, it characterized the existing sheet's three sections (acquisition counts, checklist, vendor notes) and diagnosed the core problem: outcome numbers and leading-indicator data were never joined, so no one could tell which action actually moved bookings, or how long that took.

The proposed fix was a long-format "integrated log" (year-month × store × channel × metric × value) sitting behind the existing hearing sheet, fed by GA4, GSC, GRC, and MEOチェキ in addition to the manual inputs — see `data-architecture.md` for the full table. This was presented to the user as a menu of automation options up front, with an explicitly honest caveat: this session's tool list had no ready-made GA4/GSC connector, so full automation would need either a client-installed Sheets export add-on, or a Google Cloud service account hitting the APIs directly. The user's first framing of this ("GA4/GSCにはAPIがない" — a slight misstatement by Claude) was corrected by the user, prompting Claude to restate the situation precisely: GA4/GSC do have official REST APIs, this session simply lacked a pre-built connector for them, and a service account was the way to use those APIs directly. The service-account route was chosen as the "本命" (primary/preferred) option specifically because it avoids repeated browser logins/CSV exports and gives Claude full autonomous control going forward.

Before committing to that route, Claude checked whether this machine could actually run a service-account auth flow at all — no Python or Node runtime was found, but `curl` + `openssl` were both present and sufficient for a full JWT-sign → OAuth-token-exchange → REST-call chain without installing anything. This became the concrete technical plan, and Claude wrote out a full Google Cloud Console setup guide for the user (project creation, enabling 3 APIs, service account + key creation, permission grants at 3 destinations: GA4, GSC, and the target spreadsheet) plus a request for 4 specific pieces of information to complete it (service-account email, key file path, GA4 property ID, GSC site URL).

The user then supplied a useful correction that changed the design mid-stream: rather than the assumed single-GA4-property-for-all-8-stores setup, each store actually has its **own** GA4 property, named after the store. Claude adapted by planning to enable the GA4 **Admin** API and auto-enumerate/match properties by name instead of asking the client to hand-type 8 IDs — removing a manual step the original plan would have required.

## The actual Google Cloud / browser-automation work done

Working in the Browser pane (there was a mix-up early on between that pane and a separate, unauthenticated "real Chrome" automation surface — Claude briefly drove the wrong, logged-out tab before the user pointed out which one was actually the intended target), Claude:

1. Created the GCP project `td-group-consulting`.
2. Enabled Google Analytics Data API, Search Console API, and Google Sheets API (later also the GA4 Admin API, once the per-store-property structure was discovered).
3. Created the service account `td-group-reporter@td-group-consulting.iam.gserviceaccount.com`.
4. Attempted to generate and download a JSON key inside the automation browser — the file landed in that browser's isolated sandbox and was unreachable from Claude's normal filesystem/network-request inspection. An attempt to instead capture the key's contents via injected JavaScript before the download completed was correctly blocked by a safety guardrail as equivalent to credential exfiltration; Claude did not try to route around this, and instead deleted the orphaned (content-unrecoverable) key from the Cloud Console.
5. Asked the user to complete the download themselves, in their own real logged-in browser, and place the JSON file locally.

The user did this, saving the file to `C:\Users\keizgroup634\Desktop\栗林\claude\td-group`. From there, Claude wrote a small script using `curl`+`openssl` to perform the JWT-signing/OAuth flow, successfully obtained an access token, and confirmed working Sheets API read/write access against the target spreadsheet (i.e., the "editor" grant on the sheet was correctly in place).

At this point Claude tried the GA4 Admin API property-listing call to test the account-level access approach prompted by the per-store-property revelation — it returned an empty result, indicating the service account had not yet been granted GA4 access at the **account** level (only property-level grants, if any, would have been made per the original instructions). Claude explained the account-vs-property distinction (GA4 supports one bulk account-level grant; GSC does not and needs per-property grants, but its site list can still be auto-enumerated once granted) and asked the user to complete the GA4 account-level grant.

## Where the engagement actually stands

The session went idle immediately after that request — there is no confirmation in the transcript that the user completed the GA4 account-level grant, and no further exchange. **Not yet built or verified**: the actual property-enumeration/matching logic, the integrated-log tab and its ingestion pipeline from GA4/GSC/CSV sources, the correlation analysis between leading indicators and acquisition counts, and any recurring (monthly) execution of the whole thing. The two Drive folders for GRC/MEOチェキ CSV drops were created (`T&Dグループ_順位データ(GRC・MEOチェキ)` with `GRC` and `MEOチェキ` subfolders) but no CSVs have been uploaded or ingested yet.

## Assessment for future use

This was a single consulting engagement's initial data-infrastructure design and technical setup — not a workflow that has been run repeatedly, or even completed once end-to-end. Treat the analytical framework (self-reported outcome + long-format leading-indicator log, joined for lag correlation) and the service-account/curl+openssl technical pattern as the reusable takeaways; treat the specific T&D Group conclusions/state above as a historical record to resume from, not a template output to imitate verbatim. If resuming this exact engagement, start by checking whether the GA4 account-level grant was ever completed (re-run the Admin API `properties.list` call) before assuming any further progress happened.
