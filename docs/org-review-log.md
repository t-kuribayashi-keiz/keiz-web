# 組織レビューログ(棚卸し記録)

cross-functionalエージェントによる棚卸し結果、および組織構成(CLAUDE.md / .claude/agents/ /
.claude/skills/)への変更を時系列で記録する。Gitのコミットログと合わせて「いつ・なぜ組織を
変えたか」を追える状態にする。

---

## 2026-09-01 初期構築

- 全社共通の組織スキャフォールドを作成: `CLAUDE.md`、`.claude/agents/`(analyst / implementer /
  measurer / cross-functional)、`data/`(proposals, kpi-history, clinics.json)、
  `skills/README.md`
- このPC上の `.claude/skills/` に以下10件の実務Skillが既に存在することを確認。今後リポジトリへ
  の移設(認証情報の分離を含む)が必要:
  `hpb-salonboard-update`, `hpb-crm-reconciliation`, `karte-demographics-chart`,
  `shift-schedule-gas-automation`, `dji-mic-auto-upload`, `gdrive-store-staff-folders`,
  `org-structure-artifact`, `org-structure-table`, `customer-acquisition-consulting`,
  `session-to-skill`
- 対応状況: 未対応(スキャフォールド構築のみ。Skill移設・KPI定義の記入・リモートリポジトリ
  への接続は未実施)

---

## 2026-09-01 パイロットブランド「LUNA」の組み込み

- 見つかった事実:
  - claude.ai上での事前検討(引き継ぎ書)により、複数ブランド(直営/サンズミライ統合、
    グッド、スマイル、心身堂、アイワ、リクスム、ピラティス、チョコザップ、リラックス、
    LUNA)のうち、LUNA(LUNA Pilates Studio・戸越銀座店)を最初の着手対象(パイロット
    ブランド)とする方針が既に決まっていた
  - LUNAサイトを実際に運用中の既存Claude Codeセッション(session_01KuA5rbdBVGsh4mZYtnqUGy、
    environment env_014Wg7aVXEn5DVaZcYKadVr4)を特定した。GitHubリポジトリは
    [Tsukasa0105/luna-pilates-togoshi](https://github.com/Tsukasa0105/luna-pilates-togoshi)
    (private、デフォルトブランチ `main`)
  - 当該運用セッションでは、GA4(luna-pilates.com と mypage.luna-pilates.com のクロス
    ドメイン統合計測)・Google Search Console・Microsoft Clarityの分析連携が既に稼働して
    おり、2026-07-20〜08-22の実績をまとめた集客パフォーマンス分析レポート(Artifact)が
    2本公開されていた。これを土台に `brands/luna/` 配下のドキュメントを新設できる状態
    だった
  - 一方で、本リポジトリ側にはGA4の正確なプロパティID・Google Search Consoleの確認済み
    プロパティURLが未記載であり、これらは運用セッション側で確認する必要がある(推測で
    埋めていない)
  - 本リポジトリには、LUNAのような「業態がそもそも整骨院と異なり(ピラティススタジオ)、
    集客チャネルがホームページのみ(SEO/MEO・メタ広告・Google PPC)」というブランドの
    コンテキストを置く場所がまだ存在しなかった(`data/clinics.json` はテンプレートの
    ままで、ブランド別ドキュメントの置き場所も未定義)
- 提案・対応内容:
  - `data/clinics.json` のテンプレートエントリ(`example-001`)をLUNA戸越銀座店の実データ
    (id: `luna-togoshiginza`)に置き換えた
  - 新規に `brands/luna/CLAUDE.md` を作成し、店舗・ドメイン・GitHubリポジトリ・予約
    システム(hacomono)・分析連携状況・チャネル構成サマリー・既知の重要課題をまとめた。
    ルートCLAUDE.mdを前提とし、矛盾時はルート優先である旨を明記
  - `brands/luna/channels/website/` 配下に `seo-meo.md`・`meta-ads.md`・`google-ppc.md`
    の3ファイルを作成。いずれも実行可能なSkillではなく、運用ノウハウ・実績・注意点を
    まとめたドキュメント(自動化する段階にはまだ至っていないため)
  - ルートCLAUDE.mdの「KPI定義・命名規則」セクションに、ブランドごとに業態・集客チャネル
    が大きく異なる場合は `brands/<ブランド名>/CLAUDE.md` に個別コンテキストを持たせる
    方針を追記(全社共通KPI定義そのものはまだ埋めていない)
  - 今後の課題として残したこと: GA4プロパティID・GSCプロパティURLの正確な値の確認、
    Meta広告Threads/Audience Network配置(キャンペーンID
    `120251395983210131`、累計421セッション・予約完了0件)の即時停止対応(運用担当への
    2回の提案が未対応のまま)、チラシQRコードへのUTM付与
- 対応状況: 対応済み(ドキュメント新設)。変更したファイル:
  `data/clinics.json`、`brands/luna/CLAUDE.md`、
  `brands/luna/channels/website/seo-meo.md`、
  `brands/luna/channels/website/meta-ads.md`、
  `brands/luna/channels/website/google-ppc.md`、`CLAUDE.md`
  未対応として残っている論点: GA4プロパティID/GSCプロパティURLの正確な値の確認
  (運用セッション側での確認が必要)、Meta広告Threads/Audience Network配置の停止判断の
  エスカレーション

---

## 2026-09-01 実務Skill10件の移設

- 見つかった事実:
  - 初期構築ログで「未対応」として残っていた実務Skill10件は、このセッション(クラウド
    実行環境)からは直接アクセスできないユーザーのローカルPC上にしかなかった
  - ユーザーに確認したところ、実際には別リポジトリ
    [t-kuribayashi-keiz/skill-kanri](https://github.com/t-kuribayashi-keiz/skill-kanri)
    に10件全てが整理済みの状態(SKILL.md + references/*.md)で存在しており、アクセス権限も
    付与された
  - skill-kanri配下の全ファイルを確認した結果、スクリプト(.gs/.ps1等)や鍵ファイルは
    一切含まれておらず、APIキー・トークン・パスワード等のハードコードも見つからなかった
    (`shift-schedule-gas-automation`と`hpb-crm-reconciliation`のbackground.mdには
    「認証情報は一切含まれていない」旨が明記済みだった)
- 対応内容:
  - skill-kanriの10フォルダ全てを `.claude/skills/` 配下にコピーし、コミットした
  - `skills/README.md` を更新: 移設元をskill-kanriリポジトリと明記し、今後の更新も
    skill-kanri側で育ててからこちらに反映する運用にした
  - `README.md` の現状セクションを更新
- 対応状況: 対応済み。変更したファイル: `.claude/skills/*`(10フォルダ)、
  `skills/README.md`、`README.md`
  今後の課題: skill-kanri側で今後Skillが追加・更新された場合の反映を定期棚卸しの
  チェック項目に加える(現状は手動での気づき依存)
