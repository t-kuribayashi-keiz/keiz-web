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

---

## 2026-09-02 院マスタの構造確認とブランド「サンズミライ」18院の追加

- 見つかった事実:
  - 院マスタ本体はGoogleスプレッドシート「診療時間」
    (ID: `1Pd2S6P9sAVMTk8FBqPJHKwihhggPgmvQk6pEFkgwHl8`)であり、タブ(シート)ごとに
    1ブランドの院リストが入っている構造だと判明した。`data/clinics.json` はこれまで
    LUNA1院分のテンプレートのままだったが、今後複数ブランドを追加していく上でこの
    「1タブ=1ブランド」の構造を前提にするとよい
  - ユーザーから「サンズミライは『ミライ・サンズ』シートである」と明示的な確認を受け、
    当該シートの内容(法人「ミライ」9院・法人「サンズ」9院、計18院。大阪・滋賀・
    和歌山・京都エリア、いずれも `chiryou-in.biz` ドメイン系のサイトを利用)を
    このセッションで実際に読み取った
  - gid=0の最初のタブは「直営院」で134院(法人名クラシオン/エフアール/ケイズ等)を
    確認した。過去のclaude.ai上の引き継ぎ書には「直営とサンズミライはほぼ同一のため
    統合可(`chokusei-sunsmirai`)」という提案があったが、実際の院マスタでは
    直営(134院)とサンズミライ(18院、法人ミライ/サンズ)は別タブ・別法人体系
    (直営はクラシオン/エフアール/ケイズ等、サンズミライはミライ/サンズ)で管理
    されており、エリアも直営は全国広域なのに対しサンズミライは大阪・滋賀・和歌山・
    京都の関西圏に限定されている。ドメイン構成も直営とサンズミライで別系統である
    ことを確認した
  - ついでに「スマイル」ブランドと思われるタブも見つかった(法人名「スマイル
    ストーリー」、大阪堺市エリア、11院: 山本接骨院なかもず院、やまもと鍼灸接骨院
    おおとり院・さかいし院、すまいる鍼灸接骨院ながよし院・泉が丘院、すまいる針灸
    接骨院六甲道院・甲南山手院・春木院・きたのだ院、岸和田まるまる針灸接骨院、
    金剛まるまる針灸整骨院)。ただしこれはブランド名・帰属について未確認のため
    今回は`clinics.json`には追加せず、候補として記録するに留める
- 提案・対応内容:
  - `data/clinics.json` にブランド「サンズミライ」の18院を追加した(id はケバブケース、
    例: `sunsmirai-kawachinagano-310`)。法人区分は `corporation` フィールドに
    「ミライ」/「サンズ」として残した。既存のLUNAエントリ(`luna-togoshiginza`)は
    変更していない。集客チャネル(`acquisition_channels`)はまだ未確認のため空配列
    とし、notesに出典(院マスタのシート名)を明記した
  - 引き継ぎ書にあった「直営とサンズミライの統合」は、上記の事実(別タブ・別法人体系・
    エリアが異なる)により見送り、別ブランドとして扱うこととした。統合の再検討は
    直営134院を`clinics.json`に取り込むタイミングで、法人体系・エリア・ドメイン構成の
    重複度合いを改めて確認した上で判断する
  - スマイルらしきタブ(法人「スマイルストーリー」、11院)は、ブランド名・実在ブランド
    としての位置づけがユーザー未確認のため、`clinics.json`には追加せず、本ログに
    候補として記録するのみとした。次回ユーザーに確認の上、追加するかどうかを判断する
- 対応状況: 対応済み(サンズミライ18院の追加)。変更したファイル: `data/clinics.json`、
  `docs/org-review-log.md`
  未対応として残っている論点: 直営院134院の`clinics.json`への取り込み(その際に
  直営とサンズミライの統合可否を再検討)、「スマイルストーリー」タブ11院がブランド
  「スマイル」に該当するかのユーザー確認、サンズミライの集客チャネル・KPI連携状況の
  確認(`acquisition_channels`が現状空)

---

## 2026-09-02 「アイワ」「リクスム」はブランドではなく社内機能と判明、functions/へ再配置

- 見つかった事実:
  - 過去のclaude.ai上の引き継ぎ書では「アイワ」「リクスム」を他の整骨院ブランド
    (直営/サンズミライ統合、グッド、スマイル、心身堂、チョコザップ、リラックス等)と
    並べて1ブランドとして扱う想定になっており、`brands/luna/CLAUDE.md` 冒頭の
    ブランド一覧にもその名残として両者が列挙されていた
  - ユーザーに確認したところ、両者とも実店舗を持つ整骨院チェーン(ブランド)では
    なかった:
    - **アイワ**(https://www.aiwairyo.com/): 実体は「アイワ接骨師会」という、
      柔道整復師・あん摩マッサージ指圧師・鍼灸師向けにレセプト(保険請求)チェック・
      代行、開業サポートを行う業界団体(2007年12月設立、千葉県市川市)。整骨院
      グループが自ら運営する店舗ブランドではなく、直営整骨院がレセプト業務等で
      利用しうる外部/業界団体的な機能
    - **リクスム**(https://rikusumu.com/): 実体は「リクスムサポート」という、
      柔道整復師・鍼灸師・あん摩マッサージ指圧師向け(20〜30代対象)の求人・
      転職支援サイト。店舗ブランドではなく採用チャネルとしての機能
  - 引き継ぎ書には元々「採用はブランドではなく社内機能」として `/functions/recruiting/`
    に切り出す想定が書かれており、レセプト代行機能についても同様の整理(ブランド
    横断の社内機能)が妥当と判断した
- 提案・対応内容:
  - `functions/receipt-agency/CLAUDE.md` を新設し、アイワ接骨師会の概要(設立・所在地・
    提供内容・費用・サイト)を記録。直営整骨院グループがこの機能(または類似の業界
    団体)をレセプト業務でどう使っているかは未確認である旨を明記した
  - `functions/recruiting/CLAUDE.md` を新設し、リクスムサポートの概要(対象職種・
    特徴・サイト・Xアカウント)を記録。直営・サンズミライなど社内のどの範囲の採用で
    実際に使われているかは未確認である旨を明記した
  - ルートCLAUDE.mdの「組織構成」セクションに、店舗ブランドは `brands/<ブランド名>/
    CLAUDE.md`、ブランド横断の社内機能(採用・レセプト代行など)は
    `functions/<機能名>/CLAUDE.md` に区別して置く方針を追記した
  - `data/clinics.json` にはアイワ・リクスムいずれも追加していない(実店舗を持つ
    クリニックチェーンではないため)
- 対応状況: 対応済み。変更したファイル: `functions/receipt-agency/CLAUDE.md`(新規)、
  `functions/recruiting/CLAUDE.md`(新規)、`CLAUDE.md`、`brands/luna/CLAUDE.md`
  (冒頭のブランド一覧からアイワ・リクスムを削除し、直営/サンズミライ非統合の経緯への
  参照を追記)、`docs/org-review-log.md`
  未対応として残っている論点: 直営整骨院グループが実際にアイワ接骨師会(または類似の
  業界団体)をレセプト業務で利用しているかの確認、リクスムが社内のどの範囲の採用で
  使われているかの確認
