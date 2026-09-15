# ダッシュボードのDBスキーマ

ダッシュボードArtifact: https://claude.ai/code/artifact/79c438e1-8131-4220-9ec4-0733933a336d
(db capability宣言済み。読み書きはArtifactツールの `read_db`/`write_db` から)

## ドキュメント構成

| コレクション | doc_id | 内容 |
|---|---|---|
| `config` | `master` | 店舗マスタ。`{stores: {店舗名: {name, brand, location, area, seoRanks, meoRanks, seoAvgRank, meoAvgRank}}, prompts: [{no, label}, ...]}` |
| `summary` | `latest` | ヘッダー要約。`{lastUpdated, roundsCount, storeCount, totalResponses}` |
| `rounds` | `<YYYY-MM>` | 1ラウンド分の集計。`{round, stores: {店舗名: {totalResponses, totalMentioned, displayRate, promptResults, citeShare, totalCites, noQueryCount}}}` |

ダッシュボードのJSは `rounds` コレクションを `orderBy('round','desc').limit(1)` で読むため、
新しいラウンドを追加するだけで自動的に最新表示に切り替わる(過去ラウンドのdocは消さずに残してよい —
5,000ドキュメント上限に対して年12ラウンド×店舗数分は十分な余裕がある)。

## 月次更新の手順(Claudeセッションが行う)

1. `scripts/run_survey.py` で調査を実行(要 `GEMINI_API_KEY`)
2. `scripts/parse_all.py` で順位・表示を抽出
3. `scripts/aggregate_for_dashboard.py --round <YYYY-MM>` でペイロード生成
4. 生成された `dashboard_payload.json` を3つに分けてArtifact `write_db`(`db_op: batch`)で書き込む:
   - `payload['config']` → `set` `config`/`master`
   - `payload['round']`(`stores`キーの中身をルート直下に展開: `{round: "...", stores: {...}}`)→ `set` `rounds`/`<round>`
   - `summary`は `update`(`update`は既存必須なので、初回は`set`)。`lastUpdated`(今日の日付)・`roundsCount`(累積ラウンド数、手動でインクリメント)・`storeCount`・`totalResponses` を含める
5. `read_db` で1件読み戻して反映を確認

## 制約・注意

- `db` の書き込みはArtifactツール(=Claudeセッション)経由でのみ可能。GAS/cronから直接書き込むことはできない
  → 月次実行は「Claude Code Remoteのトリガーがこのセッションを起こし、上記手順を実行する」形が現実的な自動化経路
- 1ドキュメント256KiB上限。全店舗(最大204店舗)×10プロンプトでも1ラウンド分は約60KB程度(実測4,370+12,277+89byte@10店舗から線形換算)で十分収まる
- ダッシュボードはDB読み込みに失敗した場合、公開時に埋め込んだ2026年9月の10店舗データにフォールバックする(`__SEED_JSON__` として埋め込み済み)。DBが空でも壊れて見えることはない
