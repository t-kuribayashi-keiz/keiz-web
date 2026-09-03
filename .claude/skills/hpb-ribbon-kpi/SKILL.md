---
name: hpb-ribbon-kpi
description: Use this skill for the monthly job of turning HotPepper Beauty "ribbon" data (リボンデータ — the per-store, password-protected multi-page HPB analytics PDFs, delivered as password-protected ZIPs) into rows on the 「HPB_145店舗_KPI一括集計結果」 spreadsheet's Master tab. Trigger on: "リボンデータ", "リボンのPDF", requests to decrypt/一括解除 the HPB store PDFs, extract PV/CVR/ACR/エリア平均/新規予約/女性率/年代 per store for a month号, reflect (反映) that month into the HPB KPI Master, or run the hpb-ribbon-kpi GitHub Actions workflow. Do NOT trigger for the 集客数シート monthly aggregation into 「年間計画・目標」 (that is functions/kpi-aggregation), for the CRM×来院 reconciliation GAS (hpb-crm-reconciliation), or for SalonBoard admin edits (hpb-salonboard-update).
---

# HPBリボンデータ → 店舗別KPI Master

毎月の定例作業。HPBの店舗別PDF(リボンデータ)から月号ごとのKPIを抜き、
「HPB_145店舗_KPI一括集計結果」のMasterタブへ1行/店舗で転記する。設計・列定義・シートIDは
[functions/hpb-ribbon-kpi/CLAUDE.md](../../../functions/hpb-ribbon-kpi/CLAUDE.md) が正。
このスキルは"手順"と"人が判断する例外"に絞る。

## Non-negotiable rules

1. **PDFパスワードはローカル専用**。`HPB_RIBBON_PASSWORDS`(環境変数/ローカルファイル)で渡し、
   GitHub Secretsにもリポジトリにもチャットにも書かない。
2. **書き込みは必ず読み返して照合**。`--mode apply` は writer が書き込み後に読み返して一致を
   確認する。外れたら止める。行番号・タブ名・合計行はコードに直書きしない。
3. **本番前に calibrate**。既にMasterに入っている過去の完了月号で `--mode calibrate` を回し、
   抽出だけでその月の行を再現できることを確かめてから apply する。
4. **リポジトリが公開のあいだは実データCSVをコミットしない**(店舗別KPIは社内情報)。
5. **判定できないものを黙って埋めない**。集客数の未マッチ・按分は空欄のまま人に見せる。

## 月次の流れ

### 0. 受領(人)
栗林さんがHPBからリボンZIP(バッチID `SL…`)を受け取り、展開する。各PDFの共通パスワードは
バッチ単位。

### 1. 抽出(ローカルのClaude Codeセッション)
```
export HPB_RIBBON_PASSWORDS='{"SL761993086":"…","SL714414472":"…"}'
python3 scripts/hpb_ribbon_extract.py --src "<展開ルート>" \
  --month "2026年08月号" --out data/hpb-ribbon/2026-08.csv
```
- 出力の要約(店舗数・要確認)を確認する。「空データ(開店直後の可能性)」の店舗は空行で正常。
- 依存: `pip install pikepdf pymupdf`。復号済みは `解除済み/` に残るので `--skip-decrypt` で再利用可。

### 2. 結合の下見(inspect)
`workflow_dispatch` で `mode=inspect`。集客数タブが一意に解決するか、`[未マッチ]`/`[併設按分]`を
確認する。おかしければ [data/store-name-aliases.json](../../../data/store-name-aliases.json) を直す。

### 3. 答え合わせ(calibrate)→ 下書き(dry-run)→ 本番(apply)
過去の完了月号で `mode=calibrate`(不一致0を確認)→ 対象月で `mode=dry-run`(先頭数行を目視)→
`mode=apply`。applyのログで「読み返し一致=True」を必ず確認する。

### 4. 後工程(人)
Master更新後、シートの `★分析ツール` メニュー(ダッシュボード更新/店舗状況生成/予約枠ACR)を
実行。※このGASをAPI側へ移すかは保留(2026-09-03)。

## 人が判断する例外(エージェントはここだけ考える)

| 事象 | writer/extractの印 | 既定の扱い | 判断 |
|---|---|---|---|
| 新規店舗(Master/名寄せに無い) | 抽出CSVに載るがMaster側に行が無い | 反映しない(既存・名寄せ済みのみ) | 登録するかは栗林さん |
| 集客数 未マッチ | `[未マッチ]` | 集客数を空欄 | 別名をaliasesに追記 |
| 鍼灸併設の二重計上 | `[併設按分]` | 本体に値、併設は空欄 | 按分先が妥当か確認 |
| 空データ店(開店直後) | 「空データ(開店直後の可能性)」 | 空行のまま | そのまま |
| 異常値(前月比/エリア乖離が極端) | — | — | measurerへ連携候補 |

## 参考
- [references/pipeline.md](references/pipeline.md) — 抽出ロジックの内部(完了月の決め方・PDF内の位置)
- 過去の実測: 2026年8月号=173店抽出/既存140店に反映/集客数135店入力・5店空欄(鍼灸併設・本体に計上済み)。除外30(閉院・譲渡・9月号開始・HPB離脱)を差し引くと集客数タブ合計2607と一致
