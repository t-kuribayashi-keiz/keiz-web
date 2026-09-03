# HPBリボンデータ → 店舗別KPI Master(月次)

直営+サンズミライ+リラックス系の各店舗について、HotPepper Beautyが出す店舗別PDFレポート
(社内で「リボンデータ」と呼ぶ)から月号ごとのKPIを抜き、「HPB_145店舗_KPI一括集計結果」
シートのMasterタブへ1行/店舗で転記する。ルートの [CLAUDE.md](../../CLAUDE.md) を前提とし、
矛盾する場合は常にルートを優先する。

集客数シート側の月次集計(「年間計画・目標」への転記)は別物で、
[functions/kpi-aggregation/CLAUDE.md](../kpi-aggregation/CLAUDE.md) が担当する。本functionは
その集客数シートを**読む**(『◯月HPB(速報値)』の店舗別当月値)が、書くのはHPB_145のMasterだけ。

## 対象スプレッドシート

| 役割 | シート | ID | 所有者 |
|---|---|---|---|
| 書き込み先 | HPB_145店舗_KPI一括集計結果(Masterタブ) | `1ciiSxy_RFUMgTBZznD_fetcPPuldOslub1Natvgh1Jw` | `t-kuribayashi@keizgroup.jp` |
| 集客数の参照元 | 【2026年_月次報告】集客数(『◯月HPB(速報値)』タブ) | `1Ali0uUUTnoWVv00GBYcp88-JfiPFP01Ttu5gqJ9D_Bg` | `mar-yoshida@keizgroup.jp` |

Masterは**月号ごとに全店舗を縦積み**する長い表。1行目タイトル/2行目ヘッダー/3行目からデータ。
列は [data/hpb-ribbon-config.json](../../data/hpb-ribbon-config.json) の `master_sheet.columns`。

## リボンデータとは / 何を抜くか

店舗単位の23ページ超のPDF。パスワード付きZIPで配布され(バッチID `SL…` 単位)、中の各PDFにも
共通パスワードが掛かっている。1枚に14か月分の予約数・売上・PV/CVR/ACR(自社/エリア平均/比較)・
性別/年代が入っている。Masterへ入れるのは対象月号の以下:

| Master列 | 取得元(PDF内) |
|---|---|
| 自社PV / エリア平均PV | サマリページ「自サロンTOP PV」の 自社 / 同エリア・同プラン・同ジャンル平均 |
| 自社CVR / エリア平均CVR / 自社ACR / エリア平均ACR | サマリページ 同上 |
| 新規予約数実績 | サマリ「新規予約」 |
| 女性率 / 20代未満〜50代以上比率 | P1時系列の**完了月の列** |
| 集客数 | **PDFではなく**集客数シート『◯月HPB(速報値)』の店舗別当月値 |
| No. | 各月ブロックの位置番号(1,15,29…)。集計に使われない飾り |
| 予約枠〇 | 手入力運用。書き込まない(空欄) |

### 完了月の決め方(重要)

DL時点で当月号はまだ進行中。**サマリページ**(自サロンTOP PV等)は"最新の完了月"の
スナップショットで、ここのPV/CVR/ACRがその月号の値。時系列ページ(予約/性別/年代)は末尾2列が
『当月号(進行中)』『翌月号』なので、完了月は**末尾から2列目**(config `series_completed_month_index = -2`)。
両者は実データで一致する(2026年8月号で確認)。開店直後の店舗は早い月が『- %』で入るため、
`- %` を欠損列として"数える"ことで列ずれを防ぐ。

## 実行の分担: ローカル抽出 + Actions書き込み

リボンPDFは数百MB・メール受領のためGitHub Actionsに持ち込めない。処理を2段に分ける。

### ① ローカル(PDFがある環境)で抽出

パスワードは環境変数 `HPB_RIBBON_PASSWORDS`(JSON: バッチID部分文字列→パスワード、または
そのJSONファイルのパス)で渡す。**Secretsには入れない**(Actionsは復号しないため不要)。

```
export HPB_RIBBON_PASSWORDS='{"SL761993086":"…","SL714414472":"…"}'
python3 scripts/hpb_ribbon_extract.py \
  --src "<ZIP展開済みルート>" --month "2026年08月号" \
  --out data/hpb-ribbon/2026-08.csv
```

`--skip-decrypt` で復号を飛ばして既存の `解除済み/` を使える。出力CSVは数十KB。
**リポジトリが公開のあいだは実データCSVをコミットしない**(店舗別KPIは社内情報)。

### ② Actionsで書き込み(サービスアカウント)

`.github/workflows/hpb-ribbon-kpi.yml` を `workflow_dispatch` で実行。
`inspect → calibrate → dry-run → apply` の順で確かめる。鍵は `GCP_KPI_WRITER_KEY`。

- **inspect**: 集客数タブの解決と結合結果(未マッチ/併設按分)を出すだけ
- **calibrate**: 既にMasterに入っている過去の月号で、抽出だけで再現できるか照合
- **dry-run**: 書き込む行列を表示(書かない)
- **apply**: Masterの最終データ行の次に追記し、**読み返して一致を確認**

## 集客数の結合と、鍼灸併設の按分(重要)

集客数は『◯月HPB(速報値)』タブの 院名(各行)×当月列。合計行は店舗数で動くので毎回探す
(「合計/店舗数…」ラベルで打ち切る)。結合キーは [store_matcher](../../scripts/store_matcher.py) の
正規化(冠文字除去・針灸→鍼灸・院種別語を潰す)。

**鍼灸併設リスティング**: 同一店舗がHPB上で『◯◯接骨院』と『◯◯鍼灸接骨院』の2リスティングを
持つことがある。集客数シートには本体側に1つだけ計上される。正規化すると両者は同じキーに
なるため、素の名前が集客数側に近い方(本体)にだけ値を入れ、もう一方は**空欄**にする
(二重計上を防ぐ)。writerが自動でこの按分を行い、`[併設按分]` としてログに出す。2026年8月号では
6件(八幡宿駅西口/新静岡駅前/本八幡南口/新潟関屋/ライフガーデン茂原/豊四季北口)。

## 検証(答え合わせ)

書き込み前に、既にMasterに入っている過去の完了月号で `--mode calibrate` を回し、抽出だけで
PV/CVR/ACR/エリア平均がその月号の行と一致するか確かめる。書き込み後は必ず読み返して一致を確認し、
外れたら止める。行番号・タブ名・合計行はコードに直書きしない(店舗増減でずれ、エラーも出ない)。

## セットアップ(未完了)

| # | 対象 | 権限 | 誰が | 状態 |
|---|---|---|---|---|
| 1 | HPB_145店舗_KPI一括集計結果 を書き込み用SA `chokuei-sunsumirai-kpi-writer@keizgroup-automation.iam.gserviceaccount.com` に共有 | **編集者** | 栗林さん(=所有者) | 未 |
| 2 | 【2026年_月次報告】集客数 を同SAへ共有(集客数の読み取り) | 閲覧者以上 | 既に共有済み(kpi-aggregationで実施) | ✅ |
| 3 | PDFパスワード2種を `HPB_RIBBON_PASSWORDS` としてローカルに設定 | — | 栗林さん(ローカル) | 未 |

`GCP_KPI_WRITER_KEY` は kpi-aggregation で登録済みのものをそのまま使う。

## エージェント層に委ねる判断(定例運用)

決定論の抽出・結合・書き込みはスクリプトが行う。人(またはエージェント)が見るべきは例外だけ:

- **新規店舗**: Masterにも名寄せにも無い店舗(2026年8月号ではリラックス系等33店)。登録するかは
  栗林さん判断。既定は「既存・名寄せ済みのみ反映」
- **未マッチ / 併設按分**: writerが `[未マッチ]` `[併設按分]` で出す。院名の対応が疑わしいものは
  [data/store-name-aliases.json](../../data/store-name-aliases.json) に追記して吸収する
- **空データ店**: 開店直後で全「-」の店舗(抽出時に「空データ(開店直後の可能性)」と印字)。空行のまま
- **異常値**: 前月比・エリア乖離が極端な店舗。分析(measurer)への連携候補

詳細な運用手順は [.claude/skills/hpb-ribbon-kpi/SKILL.md](../../.claude/skills/hpb-ribbon-kpi/SKILL.md)。

## 後工程(現状は現行GASのまま)

Master更新後、シート内蔵のGAS(`★分析ツール`メニュー: ダッシュボード更新 / 店舗状況生成 /
予約枠ACR集計)を人が実行する。kpi-aggregationと同じくサービスアカウント方式へ寄せるかは
2026-09-03時点で保留(栗林さん「後で考える」)。移す場合は集計もAPI側で再実装し読み返し検証する。

## ファイル

| ファイル | 用途 |
|---|---|
| [scripts/hpb_ribbon_extract.py](../../scripts/hpb_ribbon_extract.py) | 復号 + PDFからKPI抽出(ローカル。ネットワーク不要) |
| [scripts/hpb_master_writer.py](../../scripts/hpb_master_writer.py) | 集客数結合 + Masterへ転記 + 読み返し検証 |
| [scripts/store_matcher.py](../../scripts/store_matcher.py) | 院名の正規化・名寄せ(既存を再利用) |
| [data/hpb-ribbon-config.json](../../data/hpb-ribbon-config.json) | シートID・タブキーワード・Master列・完了月の定義 |
| [tests/test_hpb_ribbon_extract.py](../../tests/test_hpb_ribbon_extract.py) | 抽出・結合の純粋ロジックの回帰 |
