# 実務Skill一覧・役割マッピング

以下10件の実務Skillは、[t-kuribayashi-keiz/skill-kanri](https://github.com/t-kuribayashi-keiz/skill-kanri)
リポジトリから移設し、`.claude/skills/` 配下にコミット済み(2026-09-01)。全て指示書
(SKILL.md + references/*.md)のみで構成されており、スクリプトや鍵ファイルは含まれず、
ハードコードされた認証情報も確認されなかった。今後Skillを追加・更新する場合も、まず
skill-kanriリポジトリ側で育ててから、同じ手順でこのリポジトリに反映する運用とする。

## 役割マッピング

| Skill | 主担当業務 | 対応する役割(agent) |
|---|---|---|
| `hpb-salonboard-update` | SalonBoardのクーポン・掲載情報更新 | salonboard-operator(要ローカル実行環境。ブラウザ操作ツールを持たないimplementerからは分離) |
| `hpb-crm-reconciliation` | CRM×HotPepper Beauty来店データの突合ロジック(GAS) | implementer / analyst(判定ロジック改善時) |
| `karte-demographics-chart` | カルテデータから男女比・年代構成グラフを作成 | analyst(分析・可視化) |
| `shift-schedule-gas-automation` | スタッフのシフト/公休入力の自動化(GAS) | implementer |
| `dji-mic-auto-upload` | DJI Micの録音データをGoogle Driveへ自動アップロード | implementer(業務基盤) |
| `gdrive-store-staff-folders` | Google Driveの店舗・スタッフフォルダ管理(GAS) | implementer(業務基盤) |
| `org-structure-artifact` | 組織図・役割分担ドキュメントの作成/更新 | cross-functional(組織設計そのもの) |
| `org-structure-table` | 組織体制表(役割×法人のマトリクス表)の作成/更新 | cross-functional |
| `customer-acquisition-consulting` | 集客のデータパイプライン・分析自動化 | analyst |
| `session-to-skill` | 今の会話の作業手順をSkill化する | cross-functional(型化・再利用の判断) |
| `hpb-reservation-slot-check` | 予約枠チェック(公開カレンダーのスクレイピング・○✕判定)。**2026-09-03にColabから`scripts/hpb_slot_check.py`+GitHub Actions(毎日13:07 JST)へ移行済みで、Colabノートブックは日常運用では使わない**。Skillはその保守と、結果の読み方の playbook | daily-ops-monitor(日次の結果確認・異常の振り分け=主担当) / implementer(スクレイパー・ワークフロー修正) / salonboard-operator(✕の原因をSalonBoardで確認) |
| `hpb-ribbon-kpi` | HPBリボンデータ(店舗別PDF)の復号・KPI抽出 → HPB_145店舗KPI Masterへ反映 | implementer(抽出・転記) / measurer(月次KPI更新)。設計は `functions/hpb-ribbon-kpi/` |
| `chatwork-integration` | Chatwork APIの読み書き(依頼検知の共通基盤、ブランド非依存) | 全役割の入口。検知後の実作業はsalonboard-operator / implementer等に引き渡す |
| `llmo-gemini-survey` | Gemini API調査(LLMO/AI検索露出計測)とダッシュボードへの反映 | analyst(定点観測) / implementer(パイプライン・自動化)。2026-09-09にこのリポジトリ内で新規構築(skill-kanri由来ではない) |
| `kpi-aggregation`(実体は`functions/kpi-aggregation/`) | 直営+サンズミライの月次集客KPI集計(Sheets API + GitHub Actions、Python) | implementer(自動化の保守) |
| `hpb-review-blog-check` | 「HPB口コミ・ブログチェック」の月次集計(各院のHPB公開ページから口コミ投稿総数・★5口コミ数・口コミ返信数・ブログ数を自動集計し専用スプレッドシートのB〜F列に反映。手動集計との照合はもう行わない、完全AI入力)。2026-09-09にGitHub Actions化(毎月1日 10:00 JST、`--mode apply`)+Chatwork(マイチャット)への実行結果通知まで実装済み、2026-09-11に書き込み先を専用の新シート・B〜F列に切り替え。要: スプレッドシートを書き込み用サービスアカウントに編集者共有(未実施の場合は書き込み失敗) | implementer(スクリプト・院マスタ・ワークフロー保守) |
| `good-smile-monthly-report` | 「グッド・スマイル 集客レポート」(単一HTML Artifact)の月次更新。CRM集客数・チャネル別推移・HPBリボン(スマイルのみ)・SEO/MEO・スマイルの広告実績(Google PPC/META)・ボトルネック診断を1レポートに統合。ジェネレータは`scripts/good_smile_report_gen.py`+`data/good-smile-report-data.json`(2026-09-09新設。同種の`relax-monthly-report`とは別パイプライン・別Artifact) | smile-marketing-strategist / good-marketing-strategist(分析・示唆出し) |
| `genai-search-visibility` | Search Consoleの「生成AI機能(ベータ版)」レポート(AI Overviews表示回数)を直営・サンズミライ全店舗分収集・集計する。HPB(HotPepper Beauty)ではなく自社サイトのSearch Consoleが対象で、`hpb-`系Skillとは無関係(命名は当初誤って`hpb-genai-visibility`としてしまい、2026-09-15に訂正)。この指標はSearch Console APIに未対応(2026-09-15確認)でブラウザ操作必須のため、フェーズA(手順・店舗↔プロパティ対応表確定、通常モデル)→フェーズB(全店舗の反復巡回、ローカルセッションをHaikuに切り替えて実行)の2段構成にした点が他Skillと異なる。2026-09-15新設、対応表(`data/genai-search-visibility-properties.json`)・手順(`references/procedure.md`)ともに未確定(draft) | implementer(手順確定・対応表保守・Haikuフェーズの実行) |
| `shinkyu-staff-check` | あはき柔整プラン5院に女性の鍼灸有資格者が在籍しているかの月次確認。HPB「雰囲気・メニューなど」の「女性鍼灸師在籍」バナーの出し下げ判断に使う。名簿が写真込みの巨大xlsxでテキスト抽出が旧版を返すため、**ブラウザで開いて顔写真ごと目視**する方式(要ローカルPC) | salonboard-operator(確認とバナー取り下げ) |
| `hpb-ahaki-blog-rotation` | ライトプラン・あはき柔整プラン並行運用5院の、あはき柔整側ブログ投稿ローテーション。郡山若葉町鍼灸接骨院の投稿から精査した鍼灸専用テンプレート8種を店舗別に自動で差し替え、`hpb-salonboard-update`経由で投稿する(2026-09-12新設、ブログ投稿UIの実クリック手順は未検証)。 | salonboard-operator(投稿の実行、要ローカルのログイン済みChrome) |
| `relax-monthly-report` | リラックス(25店舗)の集客レポート(単一HTML Artifact)の月次更新。HPBリボン(PV/CVR/ACR)・GA4(新規ユーザー数・コンバージョンユーザー数)・Search Console・「リラックス新規客経路集計」シートの集客数を店舗別・時系列で統合。`good-smile-monthly-report`とは別パイプライン・別Artifact(Skillフォルダは`.claude/skills/relax-monthly-report/`に実在していたが、2026-09-19までこの表に単独行が無かった) | implementer(自動化の保守) / relax-marketing-strategist(分析・示唆出し、2026-09-19新設) |
| `analytics-sync`(Skillフォルダなし、実体は`.github/workflows/brand-analytics.yml`・`relax-analytics.yml`・`smile-good-analytics-monthly.yml`+`scripts/analytics_discover.py`・`analytics_pull.py`・`analytics_sync_sheet.py`・`ga4_metrics_probe.py`) | ブランド横断のGA4/GSC自動取得と、長形式ログとしてのSheets反映。スマイル・グッドは`smile-good-analytics-monthly.yml`で毎月5日05:00 JSTに自動実行(2026-09本番稼働開始)。リラックスは稼働実績のある`relax-analytics.yml`を維持しつつ、ブランド非依存の`brand-analytics.yml`と同じスクリプトを共有した状態で並存中(統合要否は未決、`docs/backlog.md`参照)。`customer-acquisition-consulting`スキルが設計した権限・長形式ログ方式を正しく継承した実装だが、`kpi-aggregation`のような専用`functions/`CLAUDE.mdはまだ無く(2026-09-19時点)、この表への登録のみで整合を取っている暫定状態 | implementer(自動化の保守) |
| `GRC順位データ自動エクスポート`(Skillフォルダなし、実体は`scripts/GRC_export_v2.ahk`+GRC計測PCのタスクスケジューラ) | SEO順位計測ツールGRCのCSVエクスポートを、GRC本体にCSV自動保存機能が無いため(現契約はエキスパートライセンス)Windowsタスクスケジューラ+AutoHotkey(v2)のUI自動操作で代替。GRC計測PC上で毎日07:00に自動実行しGoogle Drive for Desktop同期フォルダへ保存(2026-09-18動作確認済み、出力はYahoo順位のみ)。ケイズグループ全体で使う順位計測ツールでリラックス専用ではないが、現状`brands/relax/CLAUDE.md`に暫定記載のまま(実装者自身が「本来`functions/`配下の横断ドキュメントに置くべき」と自己申告済み。移設は別タスク) | implementer(タスクスケジューラ・スクリプト保守) |
| `meo-internal`(Skillフォルダなし、実体は`functions/meo-internal/CLAUDE.md`) | 外部SaaS「MEOチェキ」相当機能(マップ順位チェック・口コミ数/評価の推移・レポーティング)の内製化プロジェクト。ブランド横断の社内機能(2026-09-17着手、Google Business Profile API申請中) | implementer(基盤構築) |
| `epark-review-sheets`(Skillフォルダなし、実体は`functions/epark-review-sheets/CLAUDE.md`) | 各院のEPARK口コミ投稿シートのGoogle Drive提出状況、および本社からEPARK担当への送付状況を自動集計。ブランド横断の社内機能(2026-09-12新設) | implementer(自動化の保守) |

`kpi-aggregation`は`.claude/skills/`配下にSkillフォルダを新設せず、既存の
`functions/kpi-aggregation/CLAUDE.md`(実装は`scripts/kpi_aggregate.py`・
`scripts/store_matcher.py`・`.github/workflows/kpi-aggregate.yml`・`tests/`)をそのまま
実体として扱う例外。本番自動化として稼働しコード資産が`functions/`側に育っている機能は、
`.claude/skills/`への二重管理を避けてこの表への登録のみで整合を取る運用とし、
`meo-internal`・`epark-review-sheets`も同じ型で登録している。一方、まだ本番自動化に
育っていないブランド横断の社内機能(`functions/receipt-agency/`、`functions/recruiting/`、
`functions/ad-spend-tracking/`)はCLAUDE.mdのみでこの表には未登録のままにしている
(自動化が動き出した時点でこの表に追加すること — **2026-09-19の棚卸しで、この「動き出したら
登録する」運用が徹底されておらず後追いになっていたことが判明した。`docs/org-review-log.md`
の同日の記載を参照**)。

## 移設手順(skill-kanriリポジトリの更新をこちらに反映する場合)

1. [skill-kanri](https://github.com/t-kuribayashi-keiz/skill-kanri) から対象フォルダを
   `.claude/skills/<skill-name>/` にコピー(上書き)する
2. フォルダ内のスクリプト(`.gs`、`.ps1`など)にAPIキー・トークン・個人情報がハードコードされて
   いないか確認する。あれば環境変数 or 実行環境のプロパティストア(GASなら
   `PropertiesService`)に切り出す
3. `git add .claude/skills/<skill-name>` して差分を確認してからコミットする
4. 新しいPC/クラウド実行環境では、この移設済みSkillが自動的にプロジェクトスコープの
   Skillとして認識される

## 新しいSkillを追加するとき

- 1業務=1Skillを原則にする(既存Skillへの機能追加ではなく、明確に別業務なら新規Skillにする)
- 追加したら必ずこの表に1行追加する
- どの役割(agent)が主に使うかも明記する(横断エージェントが棚卸しする際の材料になる)
