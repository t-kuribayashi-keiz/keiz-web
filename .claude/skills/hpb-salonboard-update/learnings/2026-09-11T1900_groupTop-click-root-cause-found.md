# 2026-09-11 19:00頃 CNC/groupTop/クリック不能問題の根本原因が判明(前2件の続き)

- 前提: `2026-09-11T1653_mn-check-groupTop-click-instability.md` と
  `2026-09-11T1745_mn-check-groupTop-click-total-failure.md` の直接の続き。
  両ファイルの「未検証の仮説」を、栗林さんの実PC・実Chromeセッションで直接検証できたので記録する。
- 反映先候補: `hpb-salonboard-update/SKILL.md`(サロン切替の実装方法として)、
  `hpb-reservation-slot-check/references/github-actions-ops.md`(スケジュール画面の高速取得法として)。

## 根本原因: 座標/ref経由の合成クリックは、サロン一覧リンクのハンドラを発火させないことがある

`CNC/groupTop/`のサロン名リンクは`href="javascript:void(0);"`で、クリックハンドラは
(おそらくイベント委譲で)JS側にのみ存在する。**`computer`ツールの座標クリック・`ref`クリック・
`double_click`は、CDP経由の合成マウスイベントとして送られる。これが「効くときと効かないときが
ある」不安定な挙動の正体**で、前2件が疑っていた「セッション劣化」や「並行セッション競合」ではない
(今回、他セッションが存在しない状態でも新しいナビゲーションの一発目から再現した)。

**確認方法**: `javascript_tool`で以下を実行し、リンクに対して`element.click()`を直接呼ぶと
確実に遷移する。

```js
const link = Array.from(document.querySelectorAll('a'))
  .find(a => a.textContent.trim() === '柏南口整骨院'); // 完全一致で探す
link.click();
```

これは`computer`ツールの座標/refクリックとは異なり、**DOM要素に対する本物の`click`イベントを
発火させる**ため、イベント委譲されたハンドラが確実に呼ばれる。実際に試したところ、
座標クリックでは0/2〜3回成功、`element.click()`では検証した全店舗で100%成功した。

## 対策(次回からの標準手順)

1. **`CNC/groupTop/`のサロン切り替えは、`computer`の座標/refクリックを使わず、
   `javascript_tool`で`element.click()`を呼ぶ。** テキスト完全一致(`textContent.trim() === 店舗名`)
   で探すこと(部分一致だと同名を含む別店舗に誤ヒットする可能性がある)。
2. **サロン選択後の画面遷移は`navigate`でURLを直接叩ける。** サロンに一度入れば
   (`KLP/top/`が返る)、以降は`https://salonboard.com/KLP/schedule/salonSchedule/?date=YYYYMMDD`
   に直接`navigate`すればよく、UI上でスケジュールタブ等をクリックする必要はない。
   日付を変えて複数日確認する場合も、`navigate`を繰り返すだけでよい(サロン選択の
   コンテキストはセッション/Cookie側で保持される)。
3. **スケジュール画面はAjaxで遅延描画されるため、`navigate`直後に即座に読み取らない。**
   `wait`を1.5秒程度挟んでから`get_page_text`または DOM 読み取りを行う
   (`2026-09-11T1745`の既存知見と同じ)。

## 重要な制約: `salonboard-operator`エージェントは`javascript_tool`を持っていない

この回避策は`javascript_tool`が使えることが前提。現在の`salonboard-operator`エージェント
定義(`.claude/agents/salonboard-operator.md`)のツールリストには`javascript_tool`が
**含まれていない**ため、このエージェント自身では今回の回避策を実行できない。
`.claude/agents/salonboard-operator.md`のツールリストに`mcp__claude-in-chrome__javascript_tool`
を追加することを強く推奨する(次回統合時に反映すべき変更)。

## 副次的な発見: ✕/○ の全角記号は`computer`の`type`アクションで欠落する

これはGoogle Sheets側の作業(M/N列書き込み)で判明した話だが、SalonBoard・Sheets問わず
今後のブラウザ自動化全般に関わるため記録する。

- `computer`ツールの`type`アクションで`✕`(U+2715)や`○`を含む文字列を打つと、**その文字自体が
  無音で欠落する**(前後の文字は正常に入る)。試したケースでは一貫して再現した。
- **回避策は「実クリップボード経由のコピー&ペースト」のみ**。`navigator.clipboard.writeText()`で
  クリップボードにセットし、`await navigator.clipboard.readText()`で直後に読み戻して
  中身を確認してから、`ctrl+v`で貼り付ける。
- 合成`ClipboardEvent('paste', {clipboardData: ...})`をJSから`dispatchEvent`する方法も試したが、
  **これも同じ文字欠落が起きた**(OSクリップボードを経由しない限り、この文字欠落は解消しない)。
- 長い日本語文字列を`type`する場合も、セルに移動した直後(`Return`直後)に即`type`すると
  **文字列の先頭側が欠落することがある**(✕/○と無関係の通常の日本語文字列でも発生)。
  `F2`(明示的に編集モードに入る)→`wait 1秒`→`type`の順にすると安定する。
- **クリップボードは他の作業(栗林さんが実PCで別のコピー操作をした場合)と共有されており、
  頻繁に競合して上書きされる。** `navigator.clipboard.writeText()`の直後に
  `navigator.clipboard.readText()`で読み戻して意図した内容と一致することを確認してから
  `ctrl+v`する、貼り付け後も対象セルの内容を必ず読み返して検証する、という「毎回検証」を
  怠らないこと。1回の書き込みで確定させようとすると、無関係な文字列(実例:
  URLやメールドメインらしき文字列)がセルに紛れ込むことがある。
