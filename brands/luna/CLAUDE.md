# LUNA(LUNA Pilates Studio)ブランドコンテキスト

このファイルはブランド「LUNA」専用の個別コンテキストです。ルートの
[CLAUDE.md](../../CLAUDE.md) に定義された全社共通ルール(組織構成・業務フロー・認証情報の
扱いなど)を前提とし、**このファイルの記述とルートCLAUDE.mdの記述が矛盾する場合は、常に
ルートCLAUDE.mdを優先する**。

LUNAは整骨院グループの中で最初の着手対象として選定されたパイロットブランドであり、他の
整骨院ブランド(直営/サンズミライ統合、グッド、スマイル、心身堂、アイワ、リクスム、
チョコザップ、リラックス等)とは業態が異なる(整骨院ではなくピラティススタジオ)。今後
他ブランドを `brands/<ブランド名>/CLAUDE.md` として追加する際のテンプレートケースとして
扱う想定。

## 店舗・ブランド概要

- ブランド名: LUNA(LUNA Pilates Studio)
- 現在稼働中の店舗: 戸越銀座店(とごしぎんざ、東京都品川区)。`data/clinics.json` 上のid
  は `luna-togoshiginza`
- 業態: ピラティススタジオ(整骨院ではない)
- 集客チャネル: ホームページのみ(SEO/MEO・メタ広告・Google PPC)。オフラインではチラシ
  配布のQRコード遷移もあり

## ドメイン・システム構成

- コーポレート/LPドメイン: `luna-pilates.com`
- 会員・予約系サブドメイン: `mypage.luna-pilates.com`(GA4上はこの2ドメインをクロス
  ドメイン統合計測)
- GitHubリポジトリ: [Tsukasa0105/luna-pilates-togoshi](https://github.com/Tsukasa0105/luna-pilates-togoshi)
  (private、デフォルトブランチ `main`)
- 予約・会員管理: 外部SaaS「hacomono」を利用
  - 予約フロー: ①LP → ②予約枠選択 → ③レッスン内容確認 → ④情報入力 → ⑤最終確認 → 完了
  - 予約完了イベント名: `reserve_completed_thankspage`

## 運用中のClaude Codeセッション

LUNAサイトの日常運用(分析・実装)は、本リポジトリ側の `analyst` / `implementer` /
`measurer` エージェントではなく、既存の運用専用Claude Codeセッションで行われている。

- session id: `session_01KuA5rbdBVGsh4mZYtnqUGy`
- environment id: `env_014Wg7aVXEn5DVaZcYKadVr4`

このリポジトリ側でLUNAの分析・実装・効果測定サイクルを回す場合は、上記運用セッション側の
最新状況(特にGA4プロパティID、GSCプロパティURLなどの一次情報)を都度確認すること。本
ドキュメントは2026年7月20日〜8月22日時点の実績と、その時点でclaude.ai上のArtifactとして
公開されていた集客パフォーマンス分析レポート2本を土台にした棚卸し内容であり、一次情報の
写しではない。

## 分析基盤の連携状況

- **GA4**: `luna-pilates.com` と `mypage.luna-pilates.com` をクロスドメイン統合計測済み。
  **正確なプロパティIDは本リポジトリには未記載。要確認(運用セッション側で確認が必要)**
- **Google Search Console**: 連携済み。**正確な確認済みプロパティURLは本リポジトリには
  未記載。要確認**。対象ドメインは `luna-pilates.com`
- **Microsoft Clarity**: 行動シグナル(デッドクリック・クイックバック等)の分析に利用。
  API仕様上、直近1〜3日分のデータしか取得できない制約がある
- **既知の技術的負債**: GA4カスタムディメンション `reserve_source` /
  `reserve_trigger_text` はLP側で送信されているが、GA4のカスタム定義に未登録のため
  データが破棄されている状態。登録すれば予約経路・トリガーの詳細分析が可能になる

## チャネル構成サマリー(2026-07-20〜2026-08-22実績ベース)

詳細は `brands/luna/channels/website/` 配下の各ドキュメントを参照。

- **Direct**: CVR平均3.7%で全チャネル最高。チラシ配布のQRコード遷移が主因と推定される
  が、QR遷移先が共通トップページのためUTM未計測で厳密な特定はできていない
- **Paid Social(Meta広告)**: Instagram/Facebook配置はCVR 0.93%程度で唯一週次で
  踏みとどまっているチャネル。一方でThreads/Audience Network配置は深刻な課題
  (詳細は `meta-ads.md`)
- **Organic Search(SEO)**: 指名検索は高CTR・上位表示で好調。一般語は順位悪化傾向
  (詳細は `seo-meo.md`)
- **Paid Search(Google広告)**: 新規出現、37セッション程度の小規模配信
  (詳細は `google-ppc.md`)
- **Organic Social、Referral**: データはあるが本棚卸し時点では優先課題なし

## 既知の重要課題(未対応)

- **Meta広告 Threads/Audience Network配置の即時停止提案が未対応**: 同一キャンペーンID
  (`120251395983210131`)の一部配置面で、累計421セッション・予約完了0件が継続。
  運用担当に2回「即時停止」を提案しているが、本棚卸し時点(2026-09-01)で未対応のまま
- **予約フロー中盤の離脱**: ③レッスン内容確認→④情報入力の離脱が全チャネル共通で大きい。
  特にhacomonoの予約枠選択画面(`/reserve/schedule/1/2`)にデッドクリック・クイック
  バックが集中しており、LP側ではなくhacomono側UI起因の可能性がある
- **広告費データ未連携**: Meta Ads Managerの消化金額が未連携のため、CPA/ROASは算出
  できず、セッション数・CVRのみで判断している状態
- **スマホCVRの見かけ上の低さはシンプソンのパラドックス**: Meta広告(99%がスマホ・
  CVRほぼ0)の構成比が原因であり、Meta以外のチャネルではスマホ平均CVRはPCを上回る。
  「スマホ導線が悪い」という短絡的な解釈をしないよう注意
- **チラシQRコードのUTM未計測**: 次回増刷時にUTMパラメータ付与で対応予定(未実施)
