# クーポン (Coupon) tab — click path and gotchas

Learned while updating coupon text for 都賀駅前整骨院 (H000523612) on 2026-09-01, extended by a read-only re-walk of the same salon on 2026-09-02.

## Getting to the list

Fastest path: from anywhere inside the salon, `navigate` straight to `https://salonboard.com/CNK/draft/couponList/`. The salon context lives in the session, so no clicking through the nav is needed.

The long way, for reference: from a salon's SalonBoard TOP page click 掲載管理 in the top nav (a dropdown, `javascript:void(0)` href) → 掲載管理TOP → the クーポン tab in the sub-nav → `CNK/draft/couponList`.

Getting *into* the salon from `CNC/groupTop/` is the awkward part: those salon-name links are also `javascript:void(0);`, and **clicking them by element ref silently fails** — the tool reports `Clicked on element ref_N` but the page never leaves `CNC/groupTop/`. Click by screenshot coordinate, and confirm the URL changed afterwards.

The **反映** ("クーポン掲載情報を反映する") button that actually publishes staged changes lives on 掲載管理TOP (`CNK/reflect/reflectTop`), not on the coupon list or edit pages. After any 登録 (save), a yellow banner on the list page reminds you it's not live yet.

Confirm the salon before editing: the page footer shows `都賀駅前整骨院様 / H000523612 / 即時予約 / …` on every page.

## Finding matches

`couponList` can hold 30+ rows (都賀駅前整骨院 had 38 on 2026-09-02: 17 live + 21 unpublished), including a second block of unpublished/archived coupons. A live row has (1) a number in the 順番 column, (2) a white background, and (3) a "非掲載にする" button; an unpublished row has (1) an empty 順番, (2) a grey background, and (3) a "掲載にする" button. There is **no heading or separator between the two blocks — they run continuously in the same table.** Ask the user whether the unpublished ones are in scope before touching them; usually the live block is what "the coupons" refers to.

Pull the whole page's text in one call rather than scrolling+screenshotting — much faster for spotting every row containing the target string, across both クーポン名 and クーポン内容.

**But page text alone cannot tell live from unpublished.** The 順番 numbers and the 非掲載にする / 掲載にする buttons are images, so extracted text shows all 38 rows as one flat list. Use text for matching, then a screenshot scroll-pass to establish the split. `read_page` doesn't fill the gap either: with `filter=interactive` on a 38-row list it returned only 6 of the 順番 textboxes and none of the 詳細 / 非掲載にする / 削除する buttons — it is not a reliable way to enumerate rows.

There is also a **チェック column** with values `OK` and `要確認` (the latter a link). On 2026-09-02, 9 of the 21 unpublished coupons were 要確認 and all 17 live ones were OK. It appears tied to HPB's listing-compliance checks (cf. the ビビビ祭 coupon-wording notice), so after a 登録, check whether that row flipped to 要確認 before treating the edit as done.

## Do not touch these controls

Each row's 非掲載にする / 掲載にする button has a **削除する button roughly 20px directly below it.** A coordinate click that drifts a few pixels lands on delete. Treat that whole column as off-limits: never coordinate-click it, and never change a coupon's published state unless the user asked for exactly that.

## Opening a specific coupon

Each row has a 詳細 link — on screen it's a blue button reading 詳細, but it's an image, so tools see it as unlabeled (searching for "詳細" text returns them in row order — first match is row 1, etc.); note that `read_page` may not list them at all, see above.

**Element references go stale on every navigation and even after scrolling in some cases** — re-search/re-read the page fresh each time you return to the list rather than reusing refs from before. Worse, a stale or `javascript:void(0)` ref click can **report success while doing nothing**, so after any click that should navigate, verify the URL actually changed (`tabs_context_mcp` or a screenshot) before continuing. Coordinates from a screenshot can also shift by a few pixels between an action and the next screenshot (page chrome reflow) — if a coordinate click misses, re-screenshot and retry rather than assuming the click landed.

Clicking 詳細 opens `CNK/draft/couponEdit`, a form with (at least):

| Field | Notes |
|---|---|
| クーポン名 | Title. ~36 character limit. Most-common place to find date-limited wording like "◯月末まで限定". |
| クーポン内容 | Longer description. ~90 character limit. Can *also* contain date wording — always check both fields, not just the title. |
| 提示条件 / 利用条件 | Rarely touched for text rollovers, but read them if the task is broader than a simple find/replace. |

To edit a field: search for its textbox, then set its full corrected value in one shot (don't try to select/retype partial substrings — just compose the full new string with the target text swapped and set the whole field). Then click 登録.

## After 登録

Clicking 登録 shows a confirmation page ("登録が完了しました") with the same "not yet reflected" warning and a button back to the list — OR it may go straight back to the list page directly (both were observed; don't assume which happens, just check the resulting page). Either way, **the edit is only a draft until 反映 is pressed on 掲載管理TOP** — see the non-negotiable rule in SKILL.md.
