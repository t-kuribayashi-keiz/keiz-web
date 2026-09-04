---
name: hpb-ribbon-kpi
description: Use this skill for the monthly job of turning HotPepper Beauty "ribbon" data (リボンデータ — the per-store, password-protected multi-page HPB analytics PDFs, delivered as password-protected ZIPs) into (a) rows on the 「HPB_145店舗_KPI一括集計結果」 spreadsheet's Master tab and (b) the monthly 集客ボトルネック診断レポート (single-file HTML artifact). Trigger on: "リボンデータ", "リボンのPDF", requests to decrypt/一括解除 the HPB store PDFs, extract PV/CVR/ACR/エリア平均/新規予約/女性率/年代 per store for a month号, reflect (反映) that month into the HPB KPI Master, run the hpb-ribbon-kpi GitHub Actions workflow, or (re)generate/update the monthly HPB診断レポート(集客ボトルネック診断・KPI時系列・相関分析). Do NOT trigger for the 集客数シート monthly aggregation into 「年間計画・目標」 (that is functions/kpi-aggregation), for the CRM×来院 reconciliation GAS (hpb-crm-reconciliation), or for SalonBoard admin edits (hpb-salonboard-update).
---

# HPBリボンデータ → 店舗別KPI Master ＋ 診断レポート

毎月の定例作業。HPBの店舗別PDF(リボンデータ)から月号ごとのKPIを抜き、**2つを出す**：
1. **Master転記**：「HPB_145店舗_KPI一括集計結果」のMasterタブへ1行/店舗（基本A〜S＋拡張T列以降）。
2. **診断レポート**：集客ボトルネックの単一HTMLアーティファクト（KPI時系列→ボトルネック→原因→打ち手→インパクト試算）。

設計・列定義・シートIDは [functions/hpb-ribbon-kpi/CLAUDE.md](../../../functions/hpb-ribbon-kpi/CLAUDE.md) が正。
このスキルは"手順"と"人が判断する例外"、そして**分析の固定ルール**に絞る。

**リボンの取得は毎月「人(栗林さん)がHPBからDL→パスワード共有」が不可避**（HPB側にAPIが無く、
エージェントは認証情報を入力してログインしない）。ここが毎月の起点。

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

### 5. 診断レポート生成(ローカルのClaude Codeセッション)
抽出データ＋集客数＋「HPB予約枠確認」シートから、単一HTMLの診断レポートを再生成し
Artifactへ公開(同一URLを更新)。構成と固定ルールは下記。**Master 140店(直営＋サンズミライ)のみ**で
分析し、レポートは既存URLに上書き更新する。数値は前月から必ず引き直す(前年比・相関・閾値)。

## 人が判断する例外(エージェントはここだけ考える)

| 事象 | writer/extractの印 | 既定の扱い | 判断 |
|---|---|---|---|
| 新規店舗(Master/名寄せに無い) | 抽出CSVに載るがMaster側に行が無い | 反映しない(既存・名寄せ済みのみ) | 登録するかは栗林さん |
| 集客数 未マッチ | `[未マッチ]` | 集客数を空欄 | 別名をaliasesに追記 |
| 鍼灸併設の二重計上 | `[併設按分]` | 本体に値、併設は空欄 | 按分先が妥当か確認 |
| 空データ店(開店直後) | 「空データ(開店直後の可能性)」 | 空行のまま | そのまま |
| 異常値(前月比/エリア乖離が極端) | — | — | measurerへ連携候補 |

## 分析の固定ルール(2026-09確定・レポートとMaster分析で厳守)

1. **対象は Master 140店(直営＋サンズミライ)のみ**。リラックス/グッドフォーチュン/スマイルストーリー/
   心身堂は全て除外(過去データ・深掘り分析との整合)。相関はこの140店のピアソンで判断。
2. **比較サロン平均は使わない**(マッサージ等の他ジャンル混在で歪む)。基準は「エリア平均(同ジャンル・
   同エリア・同プラン)」と「前年比の推移」。PV÷競合が0.5前後は"そもそもの平均"で問題ではない。
3. **集客 = PV × CVR × ACR**(PV=露出/CVR=興味喚起/ACR=予約到達)。
4. **拡張列は Master の T列以降へ右追記のみ**。A〜S列とGASを壊さない(GASはA〜Sを固定indexで読む)。
5. **予約枠**：「HPB予約枠確認」シートは**左の〇✕が判定・右列は備考**(備考に✕があっても左が〇ならOK)。
   開放率は全店平均96.7%で健全、深刻な開放不足は開放率<70%の少数店(8月時点7店)のみ。
   **開放率×ACRは閾値型(≈70%で崖)**：全体r≈+0.12だが、開放率<100の店に絞るとr≈+0.33、境目は70%。
6. **口コミ**：口コミ数×PV +0.49／月次新規口コミ×ACR +0.42／口コミ数×集客 +0.36。
   **口コミ数×集客は閾値・飽和型**(≈45〜60件で効き始め・90件超で頭打ち、<45件は無相関)。
   **口コミ評点×集客は無相関(≈−0.15)**(皆が高評価4.4〜5.0で差がつかない=閾値でも無関係)。
7. **CVR改善は"見かけ"の可能性が高い**：CVRとACRは時系列で強い逆相関(全16か月r≈−0.87・直近5か月
   r≈−0.99)だが**店舗横断では無相関(+0.03)**。2026年5月に全店一斉の段差=HPBの指標定義変更等の
   系統的要因のサイン。**CVR単体で喜ばない/PV減の穴埋めに当てにしない**、CVRとACRはセットで見る。
8. **打ち手の主語は本社WEB課**(現場任せにしない)。因果を断定しない指標(口コミ→順位等)は
   「施策後に動くか実測で検証」の姿勢。グラフの縦軸下限は0。

## 診断レポートの構成(単一HTML・SVG自作チャート・Zen Kaku Gothic New/Noto Sans JP・0起点)

- **01 KPI推移(2025 vs 2026)**：集客/PV/CVR/ACRを横軸1〜12月で年次比較(実線=2026・点線薄=2025)。
  データは2025年5月号〜。→ 2025は5〜12月/2026は1〜8月のみ(重なる5〜8月で前年差)。
- **02 ボトルネック**：集客の前年差をPV効果/転換率効果に分解(ウォーターフォール)＋ファネル(PV−28%/
  CVR+45%/ACR−37%)＋**「なぜCVRは改善したか」ボックス**(上記ルール7・CVR/ACR/積の指数重ね線)。
- **03 なぜPV**：口コミ数×PV散布図・その直下に口コミ→ACR散布図(両輪)・評点×集客(無相関)・
  口コミ帯×集客(閾値バー)。
- **04 なぜACR**：予約枠70%閾値バー・ワースト店(<70%)・開放率×ACR散布図・原因ランキング
  (①市場系統低下 ②口コミ ③予約枠は少数店の個別対応)。
- **05 要対策(本社WEB課)**：①口コミ獲得の仕組み化(閾値60件へ) ②開放不足の少数店を是正
  ③掲載最適化 ④出稿。補=クーポンは検証課題。
- **06 インパクト試算**：レバー別の集客寄与を幅(保守〜意欲的)で。相関ベース・実測更新前提。

## 参考
- [references/pipeline.md](references/pipeline.md) — 抽出ロジックの内部(完了月の決め方・PDF内の位置)
- 過去の実測: 2026年8月号=173店抽出/既存140店に反映/集客数135店入力・5店空欄(鍼灸併設・本体に計上済み)。除外30(閉院・譲渡・9月号開始・HPB離脱)を差し引くと集客数タブ合計2607と一致
- 診断レポート(2026年8月号)は既存Artifact URLを更新する運用。レポートは Master 140店のみで再計算し、
  上記「分析の固定ルール」を毎月適用する。新月号では前年比・相関・閾値・CVR逆相関の数値を必ず引き直す。
