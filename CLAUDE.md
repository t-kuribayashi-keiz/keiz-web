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
| 横断オーケストレーター | [cross-functional.md](.claude/agents/cross-functional.md) | 複数業務・複数院にまたがる重複/共通パターンを検出し、棚卸しを行う |

実務そのもの(SalonBoard更新、CRM突合、シフト自動化など)は `.claude/skills/` 配下の
Skillとして実装します。1業務=1Skillを原則とし、疎結合に保つことで追加・入れ替え・統合を
容易にします。既存Skillの一覧と役割マッピングは [skills/README.md](skills/README.md) を参照。

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
