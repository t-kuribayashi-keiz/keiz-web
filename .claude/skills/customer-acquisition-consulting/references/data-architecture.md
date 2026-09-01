# Data architecture — detail

## Originating client's existing artifact (before this engagement)

Client: T&D Group, a chain of 整骨院/接骨院 (orthopedic manipulation clinics), 8 stores — 3 in Tokyo, 5 in Chiba. Site: `td-group.jp`. Existing spreadsheet: "T&D WEB集客状況ヒアリング" — a monthly-duplicated sheet with three sections:

1. **集客数 (acquisition count)** — grid of store × channel, channels being SEO / MEO / Google PPC / META広告 / HPB (HotPepper Beauty) / EPARK, plus an "HP合計" (site-total) column and a grand total. Filled in by the client by hand every month; no connection to any tracking system.
2. **対策チェックリスト** — per channel (SEO/MEO/PPC/META/HPB/EPARK), a ○/△/✕ mark for whether a given measure was executed that month. Purely qualitative, and each month's sheet is a fresh copy — no time-series view of a channel's checklist over months exists unless someone builds one.
3. **その他** — free-text notes on what any external vendor did that month.

**Diagnosis**: outcome (集客数) and leading indicators (rank, traffic, reviews) live in completely disconnected places, so there is no way to see which specific action moved the needle, or how long it took to show up in bookings.

## Store list and URL-path mapping (single-property case)

If a client's stores share one domain with clean per-store URL directories, GA4/GSC can be segmented by store using a `pagePath`/`page` prefix filter on a single property, with no per-store property setup needed. As enumerated for the originating client:

| Store | URL path |
|---|---|
| 秋山駅前整骨院 | `/akiyama-ekimae/` |
| 北千住駅前整骨院 | `/kitasenju/` |
| 三河島鍼灸整骨院 | `/mikawashima/` |
| 逆井駅前整骨院 | `/sakasai/` |
| 金町南口整骨院 | `/kanamachi/` |
| 榎戸接骨院 | `/enokido/` |
| 臼井接骨院 | `/usui/` |
| 薬園台駅東口接骨院 | `/yakuendai/` |

Pages outside any store's path (top page, shared 症例一覧 etc.) are treated as "all-stores-common" and reported separately rather than force-attributed to one store.

**Important caveat actually hit in this engagement**: the client initially described "1 GA4 property for all 8 stores" (which is what motivated the path-mapping table above), but partway through setup the client corrected this — each store actually has its **own** GA4 property, named after the store. When that's the case, don't ask the client to hand-type 8 property IDs; use the GA4 Admin API (`accounts.properties.list` under the relevant account, once the service account has account-level viewer access — see the setup reference) to auto-enumerate every property under the account and match by store name in the property's display name. This generalizes: always confirm 1-property-vs-per-store-property before building the segmentation logic, since the two need different code paths (path-filter vs. property-enumeration-and-match).

## Full source/metric table

| Source | Metric(s) | Acquisition method |
|---|---|---|
| Manual hearing sheet (existing) | Acquisition count, by store × channel | Unchanged — client fills in monthly; this is the one number no API can currently produce, since the client has no call/booking tracking system |
| GA4 | Sessions; channel-level inflow; per-store-page pageviews; conversions (booking-button click / phone tap / LINE transition) | GA4 Data API via service account |
| GSC | Impressions / clicks / CTR / average position, by query and by page | Search Console API via service account |
| GRC (SEO rank tool) | Keyword × store rank history | Desktop-only tool, no API — client/vendor exports CSV monthly to a shared Drive folder; Claude ingests from there |
| MEOチェキ (MEO rank tool) | Store-level map-pack rank, review count/rating trend | Same CSV-to-Drive pattern as GRC, contingent on its export format |
| Checklist tab | Per-channel measure-executed status, as a time series | Continue manual hearing, but retain history across months instead of overwriting, so ✕→○ transitions become visible over time |

## The long-format integrated log

Normalize everything above into one table: `年月 (year-month), 店舗 (store), チャネル (channel), 指標 (metric), 値 (value)`. This is what makes cross-source joins and per-store correlation analysis (leading indicator movement → lagged acquisition-count movement) possible without a bespoke join for every pair of sources. Drive folders for the CSV-drop sources were created alongside the client's existing hearing spreadsheet, with a requested naming convention of `YYYYMM_店舗名.csv` (e.g. `202608_北千住駅前整骨院.csv`) to make monthly ingestion straightforward; a single combined-all-stores CSV per month is also fine if the source tool doesn't split by store.

**Status at end of engagement**: this integrated-log tab and the actual ingestion/join logic were designed but not yet built — the session stalled at the GA4 service-account permission step (see `background.md`) before reaching this part.
