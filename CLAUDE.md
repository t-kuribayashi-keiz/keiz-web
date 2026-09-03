# 全社共通ルール(AI組織 憲章)

このリポジトリは、複数のClaude Codeインスタンス・サブエージェント・Skillsを組み合わせた
「AI組織」の本体です。どのPCでもこのリポジトリをclone(またはcloud実行環境に接続)すれば、
同じ組織構成・同じルールで作業できることを目的とします。

## 組織構成

役割は `.claude/agents/` に定義されたサブエージェントとして実装します。

| 役割 | 定義ファイル | 責務 |
|---|---|---|
| 分析・施策担当 | [analyst.md](.claude/agents/analyst.md) | KPI・音声データ等を分析し、施策案を `/data/proposals/` に出力 |
| 実装担当 | [implementer.md](.claude/agents/implementer.md) | 施策案を受け取り、コード・自動化スクリプト(GAS等)として実装 |
| 効果計測担当 | [measurer.md](.claude/agents/measurer.md) | 実装後のKPI変化を `/data/kpi-history/` に記録し、分析担当へフィードバック |
| SalonBoard操作担当 | [salonboard-operator.md](.claude/agents/salonboard-operator.md) | HotPepper Beauty SalonBoard(salonboard.com)の定型更新・反映作業(ブランド非依存、要ローカル実行環境) |
| スマイル マーケティング参謀 | [smile-marketing-strategist.md](.claude/agents/smile-marketing-strategist.md) | スマイルブランド専属のWEB集客データ分析・戦略立案・執筆指示書作成(ブランド固有。他ブランドで同様の役割が必要になれば同じ型で追加する) |
| コンテンツライター | [content-writer.md](.claude/agents/content-writer.md) | 承認済みの執筆指示書を、ブログ・広告文・口コミ返信等の完成コンテンツに仕上げる(ブランド非依存) |
| 横断オーケストレーター | [cross-functional.md](.claude/agents/cross-functional.md) | 複数業務・複数院にまたがる重複/共通パターンを検出し、棚卸しを行う |

実務そのもの(SalonBoard更新、CRM突合、シフト自動化など)は `.claude/skills/` 配下の
Skillとして実装します。1業務=1Skillを原則とし、疎結合に保つことで追加・入れ替え・統合を
容易にします。既存Skillの一覧と役割マッピングは [skills/README.md](skills/README.md) を参照。

コンテキストの置き場所は、店舗ブランド(整骨院チェーン等)は `brands/<ブランド名>/CLAUDE.md`、
採用・レセプト代行のようなブランド横断の社内機能は `functions/<機能名>/CLAUDE.md` として
区別します(例: [functions/recruiting/CLAUDE.md](functions/recruiting/CLAUDE.md)、
[functions/receipt-agency/CLAUDE.md](functions/receipt-agency/CLAUDE.md))。

複数ブランドで共通の外部サービス(Chatwork、広告費スプレッドシート等)を扱う場合は、
**APIの読み書き手順そのものはブランド非依存のSkillとして1つにまとめ、ブランド固有の情報
(どのルーム/シートがどのブランドか)は`data/`配下の設定ファイルに切り出す**。こうすると
ブランドの追加が設定1行で済み、コードの分岐が増えません(例:
[functions/chatwork-integration/CLAUDE.md](functions/chatwork-integration/CLAUDE.md) と
[data/chatwork-rooms.json](data/chatwork-rooms.json))。

## 業務フロー(横串の刺し方)

1. **analyst** が施策案をMarkdownで `/data/proposals/YYYY-MM-DD_<件名>.md` に出力
2. **implementer** がそれを受け取り実装し、`/data/proposals/` の同ファイルに実装ログを追記
3. **measurer** が実装後のKPI推移を `/data/kpi-history/<院ID or ブランド>.md` に記録し、
   analystにフィードバック(次の施策案の材料にする)
4. **cross-functional** は上記のサイクルを横断的に見て、以下を定期的に判断する:
   - 複数院・複数ブランドで再利用できる施策/Skillはないか
   - 重複作業や、まだ手作業のまま残っている業務はないか
   - 判断結果は [docs/org-review-log.md](docs/org-review-log.md) に記録する(=組織図の変更履歴)

## KPI定義・命名規則

具体的なKPI定義(来院数、CPA、リピート率など)とブランド・院の命名規則は、
このファイルに追記していく。**このセクションが空のまま各Skillで独自定義しない** こと。
定義したら [data/clinics.json](data/clinics.json) のスキーマと矛盾がないか確認する。

ブランドごとに業態・集客チャネル・分析基盤の連携状況が大きく異なる場合は、共通KPI定義を
このセクションに書く前に、まず `brands/<ブランド名>/CLAUDE.md` にブランド個別のコンテキ
ストを持たせる(パイロットブランドとして [brands/luna/CLAUDE.md](brands/luna/CLAUDE.md)
を参照)。ブランド個別ファイルとこのファイルが矛盾する場合は常にこのファイルを優先する。

## 複数セッションの同時実行と、学習の蓄積(重要)

栗林さんは同じSkillを使うセッションを日常的に**並行して**回す。このとき、各セッションが
学んだことを取りこぼさずに溜めるための共通ルール。

**共有ファイルを同時に書かせない。1ファイル1ライターにする。**
ファイルの編集は「読む→直す→書く」なので、読んでから書くまでの間に別セッションが書くと、
こちらの変更は消えた状態で上書きされる。**エラーは出ず、ファイルは正常に見える。**
失われた学習は、数週間後に誰かが同じことを再発見して初めて気づく。

したがって、他のセッションと並行している可能性がある間は:

1. **`SKILL.md`や`references/*.md`を直接編集しない。** 学習は、そのSkillの`learnings/`配下に
   **新規ファイル**として置く(`<日時>_<セッションIDの先頭8桁>.md`)。パスが違えば衝突しない
2. **同じCSV/ログに追記しない。** 1行1ファイルで`<ログ名>.d/`に置き、あとでまとめる
3. **gitコマンドを実行しない。** 同じクローンで動くセッションはindexと作業ツリーを共有する。
   `git add -A`は別セッションの作りかけの変更を巻き込み、ブランチ切り替えは全セッションの
   足元を崩す。ファイルを作るだけにして、コミットは統合時に1回でまとめる
4. **タスク開始時に`learnings/`を読む。** 未統合でもそこにある内容は既に有効な知見であり、
   統合待ちの置き場ではない

**統合は1セッションだけが行う。** `learnings/`を読んで`SKILL.md`/`references/`へ畳み、
ログをまとめ、消費したファイルを削除して1コミットにする。並行実行が終わってからでよい。

統合を人手(または単一セッション)に寄せるのは、衝突回避のためだけではない。並行セッションは
**互いに矛盾する学習**をすることがある(同じ画面に2通りの操作手順が見つかる等。A/Bテストや
アカウント差が原因のことが多い)。両方をそのまま`SKILL.md`に足すとSkillはむしろ劣化するので、
突き合わせて判断する工程が要る。ロックを増やしても解決しない種類の問題。

なお、既に開いているセッションは**Skillファイルを更新してもその場では読み直さない**
(Skillの可視性はセッション開始時に決まる。`session-to-skill/SKILL.md`の"Known bug"参照)。
つまり学習を即座に`SKILL.md`へ書き込んでも、いま走っているセッションには何の得も無い。
まとめて統合しても失うものは無い。

実例と具体的な手順:
[`.claude/skills/hpb-salonboard-update/references/concurrent-sessions.md`](.claude/skills/hpb-salonboard-update/references/concurrent-sessions.md)

## 認証情報の扱い(重要)

- APIキー・トークンの類は**絶対にこのリポジトリにコミットしない**
- 環境変数、またはクラウド実行環境のシークレット管理機能を使う
- Skillを `.claude/skills/` に移設する際は、ハードコードされた認証情報がないか必ず確認してから
  コミットする

## 組織の見直し

組織構成の変更(役割の追加/廃止、Skillの統合)は、このファイルおよび `.claude/agents/` への
変更としてGitコミットする。コミットログがそのまま組織変更の履歴になる。
月次、または気づいたタイミングで cross-functional エージェントに棚卸しを依頼し、
結果を [docs/org-review-log.md](docs/org-review-log.md) に追記する運用とする。

## どのPCでも使うために

1. このリポジトリをclone
2. `.claude/skills/` 配下のSkillをこのPCのClaude Codeに認識させる(プロジェクトスコープの
   Skillとして自動的に読み込まれる)
3. 認証情報だけは各PC/実行環境ごとに環境変数で設定する
