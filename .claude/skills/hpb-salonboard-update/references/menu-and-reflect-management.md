# メニュー掲載情報 (`CNK/draft/menuEdit`) と 掲載管理TOP (`CNK/reflect/reflectTop`)

Learned 2026-09-10 while re-registering menu listings (unchanged content) for 5 あはき柔整 salons after adding エステ to their ジャンル, and reading 掲載管理TOP to decide which sections needed 反映申請.

## メニュー掲載情報の編集 (`menuEdit`)

Unlike `salonEdit`, this page shows the existing menu already in an editable state (no separate "edit" click needed) — every field is already a live textbox. To "re-register with no changes" (needed after some ジャンル/カテゴリ changes force a re-submit), just scroll to the bottom (`key End`) and click 登録 without touching any field.

`get_page_text` returns every menu row including empty/unused ones (~10 blank rows), which is long enough that a vague `find` query like "登録ボタン" can blow past the 200k-token limit (`prompt is too long`). If you already know roughly where the button is, go straight to `key End` → screenshot rather than `find`.

After 登録, a red "登録した情報に確認していただきたい内容があります。内容を見るボタンから内容を確認してください。" message with a "内容を見る" button sometimes appears (1/5 salons, 2026-09-10). Clicking that button — by ref or coordinate — produces no visible change and no new tab in `tabs_context_mcp`; it looks like a blocked popup, unconfirmed. No downstream effect (reflect-blocking etc.) was observed from leaving it unclicked; treat the top confirmation banner plus a reload-and-recheck of the saved fields as sufficient, don't chase this button.

## 掲載管理TOP (`reflectTop`) — how the 反映申請 buttons are actually grouped

The page lists one row per section (サロン掲載情報, スタッフ掲載情報一覧, フォトギャラリー掲載情報, メニュー掲載情報, こだわり掲載情報一覧, 特集, クーポン, …), but **the 反映申請 button only appears on the サロン掲載情報 row** — サロン/スタッフ/フォト/メニュー/こだわり all get bundled into that single button (confirmed 2026-09-10). You cannot 反映 just the menu, or just こだわり, on its own; 特集 and クーポン each keep their own independent 反映申請 button outside this bundle.

**Whether that bundled button is actually clickable is not decidable from the チェック column's OK/NG/要確認 value alone:**

- Any **NG** in the bundle → button is visibly greyed out and inert. Unambiguous.
- **要確認** is ambiguous — read the 詳細 column's actual text, not just the label:
  - A generic "変更内容がHOT PEPPER Beautyに反映されていません。反映申請を行ってください。" → button is still enabled (blue).
  - A **specific unresolved instruction** — e.g. "『設定』＞『スタッフ設定』画面で更新された情報が登録されていません。スタッフ掲載情報で登録を行ってください。" — means something else needs finishing first, and the button stays greyed out (confirmed: 八幡宿駅西口鍼灸接骨院 H000822247).

**`read_page`'s `disabled` attribute does not distinguish these states** — both the clickable and greyed-out 反映申請 buttons came back as plain `button "反映申請" [ref] type="button"` with no `disabled` attribute either way. The only reliable signal is the **on-screen color** (blue = enabled, grey = inert) — confirm by screenshot/`zoom`, not by reading the DOM.
