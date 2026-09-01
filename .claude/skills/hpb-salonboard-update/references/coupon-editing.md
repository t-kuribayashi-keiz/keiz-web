# クーポン (Coupon) tab — click path and gotchas

Learned while updating coupon text for 都賀駅前整骨院 (H000523612) on 2026-09-01.

## Getting to the list

From a salon's SalonBoard TOP page: click 掲載管理 in the top nav (it's a dropdown, `javascript:void(0)` href) → this lands on 掲載管理TOP → click the クーポン tab in the sub-nav → lands on `CNK/draft/couponList`.

The **反映** ("クーポン掲載情報を反映する") button that actually publishes staged changes lives on the 掲載管理TOP page, not on the coupon list or edit pages. After any 登録 (save), a yellow banner on the list page reminds you it's not live yet.

## Finding matches

`couponList` can hold 30+ rows, including a second block of unpublished/archived coupons (their row shows a "掲載にする" button instead of "非掲載にする" — meaning they're currently NOT live). Ask the user whether those should be in scope before touching them; usually the live ones (top block, showing "非掲載にする") are what "the coupons" refers to.

Pull the whole page's text in one call rather than scrolling+screenshotting — much faster for spotting every row containing the target string, across both クーポン名 and クーポン内容.

## Opening a specific coupon

Each row has a 詳細 link, rendered as an *unlabeled image* (searching for "詳細" text returns them in row order — first match is row 1, etc.). **Element references go stale on every navigation and even after scrolling in some cases** — re-search/re-read the page fresh each time you return to the list rather than reusing refs from before. Coordinates from a screenshot can also shift by a few pixels between an action and the next screenshot (page chrome reflow) — if a coordinate click misses, re-screenshot and retry rather than assuming the click landed.

Clicking 詳細 opens `CNK/draft/couponEdit`, a form with (at least):

| Field | Notes |
|---|---|
| クーポン名 | Title. ~36 character limit. Most-common place to find date-limited wording like "◯月末まで限定". |
| クーポン内容 | Longer description. ~90 character limit. Can *also* contain date wording — always check both fields, not just the title. |
| 提示条件 / 利用条件 | Rarely touched for text rollovers, but read them if the task is broader than a simple find/replace. |

To edit a field: search for its textbox, then set its full corrected value in one shot (don't try to select/retype partial substrings — just compose the full new string with the target text swapped and set the whole field). Then click 登録.

## After 登録

Clicking 登録 shows a confirmation page ("登録が完了しました") with the same "not yet reflected" warning and a button back to the list — OR it may go straight back to the list page directly (both were observed; don't assume which happens, just check the resulting page). Either way, **the edit is only a draft until 反映 is pressed on 掲載管理TOP** — see the non-negotiable rule in SKILL.md.
