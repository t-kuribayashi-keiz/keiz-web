---
name: relax-monthly-report
description: Use this skill for the monthly job of building リラックス(25店舗)の集客レポート — a single-file HTML artifact combining HPBリボンデータ(PV/CVR/ACR)・GA4(新規ユーザー数・コンバージョンユーザー数)・Search Console・「リラックス新規客経路集計」シートの集客数(新患数)を店舗別・時系列で示す。Trigger on "リラックスの月次レポート", "リラックスの集客レポートを更新して", requests to reflect a new 年月号 into the リラックス report, or the monthly recurring Routine firing for this brand. Do NOT trigger for 直営・サンズミライのHPB Master/診断レポート(that's hpb-ribbon-kpi — completely separate pipeline, different brands, do not mix data or Artifacts) or for the 集客数シート集計 into 「年間計画・目標」(functions/kpi-aggregation).
---

# リラックス 月次集客レポート

毎月の定例作業。リラックス25店舗の集客状況を単一HTMLアーティファクトにまとめ、
既存のArtifact URLを更新する。**直営・サンズミライのMaster/診断レポート
(hpb-ribbon-kpiスキル)とは完全に別のパイプライン・別のArtifact。数字もURLも混同しないこと。**

設計の前提は [brands/relax/CLAUDE.md](../../../brands/relax/CLAUDE.md) が正。
このスキルは"手順"と"レポートの固定ルール"に絞る。

**HPBリボンデータの取得は毎月「人(栗林さん)からのCSV共有」が不可避**(直営と違い、
リラックスはHPBリボンPDFの自動抽出パイプラインが無い。`data/hpb-ribbon-config.json`に
`relax`プロファイルは存在しない)。セッションが起動したら、まず対象月のHPBリボンCSVが
共有されているか確認し、無ければ栗林さんに依頼すること。**推測やダミー値で埋めない。**

## Non-negotiable rules

1. **全指標は「1店舗あたり」で表示・議論する**(店舗数が月によって変わるため)。
   合計値は補足情報として添える程度に留める。
   → [docs/chart-conventions.md](../../../docs/chart-conventions.md)(全ブランド共通)
2. **時系列グラフは横軸を暦月(1〜12月)に固定し、年度を重ねて表示する**
   (最新年=実線・強調、前年=点線・控えめ)。同上ドキュメント参照。
3. **GA4指標の定義**(2026-09-07にgetMetadataで確認済み。憶測で別の指標名を使わない):
   - 新規ユーザー数 = `newUsers`(公式apiName)
   - コンバージョンユーザー数 = GA4に単一の該当指標が無いため、`isKeyEvent=="true"`で
     絞り込んだ`activeUsers`(店舗ごとの個別キーイベント名を知らなくても、全キーイベント
     横断のユニークユーザー数が取れる)。取得コードは
     [scripts/analytics_pull.py](../../../scripts/analytics_pull.py)の`pull_ga4()`。
     指標名の確認には[scripts/ga4_metrics_probe.py](../../../scripts/ga4_metrics_probe.py)
     が使える(getMetadataに実際に問い合わせる。記憶や検索結果で決めない)。
4. **推測で埋めない。** Search Consoleが0件で返る店舗、高円寺店(新規開店で一部指標が
   サンプル不足)など、確認できない値は空欄・注記のまま出す。
5. **複数月をまとめて取る場合はワークフローのArtifact経由で受け取る**
   (`relax-analytics.yml`の`months`カンマ区切り入力。ログ出力には長さの上限があり、
   複数月・全店舗だと`get_job_logs`で途中が切れることがある。1ヶ月・全店舗程度なら
   ログでも読める)。

## 月次の流れ

### 0. HPBリボンCSVの受領(人)
栗林さんから対象月のHPBリボンCSV(院名・Hコード・年月号・自社PV/CVR/ACR・エリア平均・
比較サロン平均・女性率・年代構成の列)を受け取る。無ければ依頼する。

### 1. 集客数(新患数)の取得
```
mode=pull(相当) で relax-shukyaku-pull.yml を実行し、「リラックス新規客経路集計」
シートのタブ「集客数(新ルール6月〜)」から対象月のHPB経由新患数・新患合計を取得する。
```
実装は [scripts/relax_shukyaku_pull.py](../../../scripts/relax_shukyaku_pull.py)。
全体行(`全体`)と閉店店舗は取り込み対象外(正常)。

### 2. GA4・Search Consoleの取得
`relax-analytics.yml`を`mode=pull`で実行。単月のみなら`month`、複数月なら`months`
(カンマ区切り)。`scope=ga4`だけでも良い(GSCは新規ユーザー数と独立に、必要な月だけ
`scope=gsc`または`scope=both`で追加取得できる)。

### 3. レポートの再構築・公開
上記データとHPBリボンCSVを突き合わせ、下記「レポートの構成」に従って単一HTMLを
再生成し、既存のArtifact URLに上書き公開する(新しいURLを作らない):

**Artifact URL: https://claude.ai/code/artifact/4dfbe10f-fc8f-40ca-8a84-6221b4eb4096**
(タイトル「リラックス 8月度レポート」。月が変わっても同じURLを更新し、タイトル・
「対象月」表記だけ差し替える)

公開前に artifact-design / dataviz スキルの手順(色パレットのvalidate_palette.js確認、
スクリーンショットでの一度だけの見た目確認)を通すこと。

## レポートの構成(単一HTML・SVG自作チャート・Zen Maru Gothic+Zen Kaku Gothic New・0起点)

- **ヘッダー**: 対象月・作成日・店舗数(25、直営リラックスブランド)
- **KPIタイル(4枚、すべて1店舗あたり)**: HPB経由新患数・全チャネル集客数・
  GA4新規ユーザー数(サブにコンバージョンユーザー数)・Search Console取得率
- **データギャップの注記(callout)**: Search Console未取得店舗を店舗名で列挙、
  新規開店店舗のサンプル不足項目、今回含まれないデータ(新規予約数実績・SEO/MEO順位等)
  を推測で埋めずそのまま明記
- **集客数ランキング + GA4流入チャネル構成**: 店舗別HPB新患数の横棒ランキング、
  GA4チャネル別新規ユーザー数の構成比(積み上げバー)
- **全店舗トレンド(年度比較、4チャート)**: 自社PV・自社CVR・自社ACR・GA4新規ユーザー数/
  コンバージョンユーザー数を、横軸1〜12月・年度重ね(直近年実線・前年点線)で表示。
  Y軸は必ず0起点。データが無い月・年はそのまま欠落させる(補間しない)
- **店舗別サマリー表(12列)**: 店舗名・自社PV(エリア平均比含む)・自社CVR(エリア平均比
  含む)・HPB新患・集客数合計・GA4新規ユーザー・GA4コンバージョンユーザー・GSC・女性率・
  主要年代
- **フッター**: データソース一覧・用語集(GA4指標の定義を含む)

## 実行環境

- ワークフロー: [.github/workflows/relax-analytics.yml](../../../.github/workflows/relax-analytics.yml)
  (`mode`: discover/pull/probe-metrics)、
  [.github/workflows/relax-shukyaku-pull.yml](../../../.github/workflows/relax-shukyaku-pull.yml)
- 鍵はリポジトリシークレット`GCP_RELAX_KEY`のみ。**読み取り専用**(GA4・Search Console・
  シートいずれにも書き込まない)。ワークフローの成果物(Artifact、7日で自動削除)には
  実データのTSVが乗るが、リポジトリにはコミットしない

## 参考
- 初回実行: 2026年08月号(2026-09-07作成)。GA4は当月分を`sessions`/`conversions`で
  取得後、栗林さんの指示で`newUsers`/`isKeyEvent`絞り込みの`activeUsers`に差し替え、
  2025年08月号〜2026年08月号の13ヶ月分をバックフィルした
- 高円寺店: HPBリボンデータでは開店(2026年07月号)以降、GA4では2026年06月号以降のみ
  算出対象(1ヶ月ずれる。サイト計測開始が店舗掲載より先行したとみられる、原因未確認)
