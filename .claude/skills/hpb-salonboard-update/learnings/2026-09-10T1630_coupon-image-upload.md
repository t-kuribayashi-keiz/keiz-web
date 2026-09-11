# クーポン画像アップロード時のfile_upload制約と手順(2026-09-10)

南流山駅前整骨院(H000485906)・下総中山駅前整骨院(H000498853)への感謝祭クーポン新規作成で確認。

## file_uploadに渡すパスは「このセッションが読み取り許可されたディレクトリ」限定

`mcp__claude-in-chrome__file_upload` はBash/Readツールとは別に、独自のファイルアクセス許可を持つ。
セッションのOS一時スクラッチパッド(`%TEMP%\claude\...\scratchpad\`)配下のファイルは、Bash/Readからは
普通に読み書きできるが、`file_upload`には**常に拒否される**(エラー文: 「only files this session is
allowed to read can be uploaded」)。8.3短縮パス(`KEIZGR~1`)でもロングパス(`Keizgroup500`)でも同様に拒否された。

**回避策**: アップロードしたいファイルをプロジェクトの作業ディレクトリ(このリポジトリの
ワーキングツリー内、例: リポジトリ直下)に一時的にコピーしてから`file_upload`に渡すと成功する。
作業が終わったら忘れずに削除すること(gitの管理対象に残さない。`git status`で確認してから
コミット対象に含めないよう注意)。

## 「画像をアップロードする」ボタンはクリックするまでinput[type=file]が存在しない

クーポン編集フォームの`写真`欄にある「画像をアップロードする」ボタンをクリックする**前**は、
`read_page`/`find`で`input[type=file]`を検索しても一件もヒットしない。クリックした**後**に
初めてDOMに挿入される(モーダルではなく、同一タブ内に配置される)。`find`で「file input」を
検索すればref付きのボタン要素として見つかる。`file_upload`ツール自身の説明文には「クリックする
とネイティブのファイル選択ダイアログが開いて操作できなくなる」という警告があるが、実際には
ネイティブダイアログではなく上記のinput要素が出現するだけだった(SalonBoard側の実装によるものと
見られる)。クリック後に`find`で再探索してから`file_upload`を呼ぶ、という順序を踏めば問題ない。

アップロード後は画像プレビューのモーダルが出て「登録する」ボタンを押す必要がある
(押すと画像IDが払い出され、フォーム上部の写真枠にサムネイルが反映される)。このモーダルの
「登録する」を押し忘れると、フォーム全体の「登録」ボタンを押しても画像が保存されない可能性が
あるため注意(今回は都度確認して押した)。

## salonboard-operatorサブエージェントにはfile_uploadツールの権限が無い

`.claude/agents/salonboard-operator.md`の許可ツール一覧に`mcp__claude-in-chrome__file_upload`が
含まれていない(browser_batch, computer, find, form_input, get_page_text, navigate,
read_page, tabs_context_mcp, tabs_create_mcp, tabs_close_mcp, list_connected_browsers,
select_browser はあるが file_upload だけが抜けている)。画像アップロードを伴うクーポン新規作成
タスクをこのサブエージェントに投げると、`ToolSearch`で`file_upload`を探しても見つからず、
その場で行き詰まる。**画像アップロードが絡むタスクは、当面メインセッション側で直接ブラウザ操作
するか、エージェント定義に`mcp__claude-in-chrome__file_upload`を追加してから委譲すること。**
