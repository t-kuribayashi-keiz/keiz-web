# クーポン (Coupon) tab — click path and gotchas

Learned while updating coupon text for 都賀駅前整骨院 (H000523612) on 2026-09-01, extended by a read-only re-walk of the same salon on 2026-09-02, and by creating a new coupon from scratch at 姿勢堂 段原鍼灸接骨院 (H000657363) later the same day.

## Getting to the list

Fastest path: from anywhere inside the salon, `navigate` straight to `https://salonboard.com/CNK/draft/couponList/`. The salon context lives in the session, so no clicking through the nav is needed.

The long way, for reference: from a salon's SalonBoard TOP page click 掲載管理 in the top nav (a dropdown, `javascript:void(0)` href) → 掲載管理TOP → the クーポン tab in the sub-nav → `CNK/draft/couponList`.

Getting *into* the salon from `CNC/groupTop/` is the awkward part: those salon-name links are `javascript:void(0);`, and clicking them by element ref *or* screenshot coordinate can both silently fail partway through a multi-salon task (see SKILL.md's "Before any browser action" for the confirmed fix: `javascript_tool` calling `element.click()` on the matched `<a>` directly). Confirm the URL changed afterwards either way.

Once inside a salon, **don't `navigate` straight to `couponList`/`couponEdit`** the very first time you enter — that transition alone has produced `ユーザエラー: サロンが選択されていません` a few times even right after a correct salon-TOP landing (confirmed 2026-09-10, 3/5 direct-navigates failed this way, 0/3 UI-click-throughs did). Click 掲載管理→クーポン through the on-screen nav for that first hop into the section; direct `navigate` is fine for subsequent hops once you're already inside `CNK/draft/*`.

The **反映** ("クーポン掲載情報を反映する") button that actually publishes staged changes lives on 掲載管理TOP (`CNK/reflect/reflectTop`), not on the coupon list or edit pages. After any 登録 (save), a yellow banner on the list page reminds you it's not live yet.

Confirm the salon before editing: the page footer shows `都賀駅前整骨院様 / H000523612 / 即時予約 / …` on every page.

## Finding matches

`couponList` can hold 30+ rows (都賀駅前整骨院 had 38 on 2026-09-02: 17 live + 21 unpublished), including a second block of unpublished/archived coupons. A live row has (1) a number in the 順番 column, (2) a white background, and (3) a "非掲載にする" button; an unpublished row has (1) an empty 順番, (2) a grey background, and (3) a "掲載にする" button. There is **no heading or separator between the two blocks — they run continuously in the same table.** Ask the user whether the unpublished ones are in scope before touching them; usually the live block is what "the coupons" refers to.

Pull the whole page's text in one call rather than scrolling+screenshotting — much faster for spotting every row containing the target string, across both クーポン名 and クーポン内容.

**But page text alone cannot tell live from unpublished.** The 順番 numbers and the 非掲載にする / 掲載にする buttons are images, so extracted text shows all 38 rows as one flat list. Use text for matching, then a screenshot scroll-pass to establish the split. `read_page` doesn't fill the gap either: with `filter=interactive` on a 38-row list it returned only 6 of the 順番 textboxes and none of the 詳細 / 非掲載にする / 削除する buttons — it is not a reliable way to enumerate rows.

There is also a **チェック column** with values `OK` and `要確認` (the latter a link). On 2026-09-02, 9 of the 21 unpublished coupons were 要確認 and all 17 live ones were OK. It appears tied to HPB's listing-compliance checks (cf. the ビビビ祭 coupon-wording notice), so after a 登録, check whether that row flipped to 要確認 before treating the edit as done.

## Do not touch these controls

Each row's 非掲載にする / 掲載にする button has a **削除する button roughly 20px directly below it.** A coordinate click that drifts a few pixels lands on delete. Treat that whole column as off-limits: never coordinate-click it, and never change a coupon's published state unless the user asked for exactly that.

**Clicking 非掲載にする can freeze the tab for 30–45s and, on repeat, time out the whole session** (confirmed 2026-09-11, 3 occurrences on the same coupon across separate attempts. 1st: another session was confirmed active on the same account/salon at the same time, doing フォトギャラリー非公開化 on the same salon — root-caused as session collision after the fact. 2nd: no other session's recent activity was visible in `hpb_work_log.d/` at the time, so it isn't purely a concurrency artifact — it may also be specific to this particular photo-less "要確認"-flagged new coupon, or to the button itself. 3rd: not yet re-attempted after the coupon stayed untouched). If a click on this button hangs: don't retry/screenshot repeatedly — `wait` ~60s, then check `tabs_context_mcp`; if still unresponsive, close and reopen the tab at the same `couponList` URL and check the row's state (順番/background/button) before deciding whether the click had any effect (in all observed cases, it hadn't — no state change, nothing deleted). If it recurs on retry, stop and hand the specific row back to the user as a manual step rather than continuing to fight it. **There is no bulk/一括 unpublish toggle** — 非掲載にする is per-row only, so this risk is paid once per coupon, not once per batch.

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

**登録 can fail with a session error that discards nothing.** `couponEdit/doRegister` can come back as a ユーザエラー: 「ユーザまたは、お店が切り替わっているため、操作を続けることができません。最初から操作しなおしてください。」(confirmed 2026-09-02, cause not isolated — it happened after navigating away from the edit form and back mid-task before submitting). Nothing was created when this happened; the fix is simply to start over from `CNC/groupTop/`, re-enter the salon, reopen the form, and fill it in one continuous run without navigating elsewhere in between. Always verify by reloading the coupon list afterward rather than trusting the click alone.

## Creating a new coupon

Via クーポン新規追加 (a button both above and below the list) rather than 詳細, the form has one extra required step and some differences from editing an existing coupon:

- **ビビビ祭用クーポン設定** appears at the top and must be answered before the rest of the form is usable — pick **設定しない** for an ordinary coupon. Only pick "ビビビ祭用に設定する" if the task is explicitly about that campaign (see the news-feed notice about ビビビ祭 wording/compliance).
- **写真 has no "reuse another salon's image" option** — 画像ID is a read-only label assigned after upload, not something you can type in to pull an existing image by ID. The only input is a local file (drag-and-drop or ファイルを選択, via the `file_upload` MCP tool with a ref to the `input[type=file]` — note the visible "ファイルを選択" element found by `find` is often the wrapping `<label>`, not the input itself; search more specifically (e.g. "input type file") to get the actual file input ref). If you're replicating a coupon that already exists at another salon and don't have the image as a local file, ask the user to send it rather than trying to fetch it from SalonBoard yourself.
  - **The `input[type=file]` doesn't exist in the DOM until you click "画像をアップロードする" first** — `find`/`read_page` return zero matches before that click, and only find it after (confirmed 2026-09-10). Click the upload button, *then* `find` for the file input.
  - **`file_upload` only accepts files under this session's own read-allowed paths** — a file in the OS scratchpad temp dir (`%TEMP%\claude\...\scratchpad\`) is rejected ("only files this session is allowed to read can be uploaded") even though Bash/Read can read it fine, both with the short and long path form. Copy the file into the repo working tree first, upload from there, then delete it afterward (check `git status` before committing so it doesn't get added).
  - After upload, a preview modal appears with its own "登録する" button — **that has to be clicked too** (it's what actually assigns the 画像ID and updates the thumbnail); the form's outer 登録 button alone may not persist the image if this modal step gets skipped.
- **アイコン用カテゴリ選択は別モーダルで、チェックボックスはDOM順が画面の見た目と一致しない.** `read_page` returns them as opaque `MC01`, `MC02`, … values with no adjacent label text, so you can't map a category name to a ref reliably. Take a screenshot of the open modal and click by coordinate instead, then re-screenshot to confirm the right boxes ended up checked before clicking the modal's own 登録.
- All other fields (種別, クーポン名, クーポン内容, 提示条件, 利用条件, 有効期限, 検索用カテゴリ, 価格, 所要目安時間) behave the same as in the edit form described above.

To replicate a coupon that already exists elsewhere: open that coupon's 詳細 on a salon that has it, screenshot the filled-in form to read every field's actual value (`get_page_text` shows character-count labels like `34/36` but not the field contents — you need a screenshot), then reproduce those values on the new salon's 新規追加 form.

## 感謝祭クーポン: existing template wording (found 2026-09-10)

When asked to add a "感謝祭" (thanksgiving-fair) coupon to a new salon, check whether it's
just cloning an existing chain-wide template before writing new copy — 都賀駅前整骨院
(H000523612) and 南柏駅前整骨院 (H000499467, same corporate group as 南流山駅前) both carry
byte-identical クーポン内容:

> `＼期間限定★無料体験会／●内容：指圧+骨格矯正●時間：計30分(カウンセリング込み)●価格：今だけ￥0！「肩こり・腰痛・疲れ」をプロの技でスッキリ♪この機会にご体感ください◎`

クーポン名 follows one of two date patterns (the content field itself carries no date):
- Single day: `【4/28(火)限定】★感謝祭★本格骨格矯正＋指圧etc(計30分)無料体験￥0` (day + weekday in
  parens, no leading zero, no slash before the weekday)
- Multi-day: `5/18・5/19限定★感謝祭★本格骨格矯正+指圧etc(計30分)無料体験¥0` (中黒 `・` between
  dates, no weekday)

提示条件: 予約時 / 利用条件: ご新規様限定 / 検索用カテゴリ: リラクゼーション：整体 / 価格: ¥0 /
所要目安時間: 30分. 有効期限 is set to the last day the coupon runs. Only 2 salons were
checked (both matched exactly), so treat this as "confirmed template within at least this
corporate group," not "confirmed chain-wide."

**The banner image is not reusable across salons** — each salon's version has its own
画像ID with that salon's name/dates baked in (per SKILL.md's "no reuse another salon's
image" constraint above), so a new salon needs its own banner even when the text is a
straight clone.

## Publishing (反映)

反映申請 lives on 掲載管理TOP (`CNK/reflect/reflectTop`), one row per section (サロン, スタッフ, フォトギャラリー, メニュー, こだわり, 特集, クーポン, …) — each with its own independent 反映申請 button. Click only the button in the row for the section you actually changed; sections already 反映済み show a greyed-out 反映申請 button in the same column, which is easy to mistake for the live one at a glance. **Re-screenshot immediately before clicking** — the row's vertical position shifts depending on how much content is above it (which salon, how many prior sections have data), so a coordinate reused from an earlier screenshot or a different salon will land on the wrong row. After a successful click the row's status changes from 未申請 to 反映待ち with a timestamp; the change usually goes live within ~15 minutes (SalonBoard's own estimate, can take longer during maintenance).
