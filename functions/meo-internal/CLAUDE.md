# MEOチェキ内製化(ブランド横断の社内機能・keiz-web MEOプロジェクト)

このファイルは、外部SaaS「MEOチェキ」相当の機能(マップ順位チェック・口コミ数/評価の
推移・レポーティング)を自社内製システムとして構築する「keiz-web MEOプロジェクト」の
個別コンテキストです。ルートの [CLAUDE.md](../../CLAUDE.md) に定義された全社共通ルール
を前提とし、矛盾する場合は常にルートCLAUDE.mdを優先する。

`functions/`配下に置いているのは、これが特定の1ブランドに閉じたものではなく、
**全ブランド(直営・サンズミライ・グッド・スマイル・リラックス・LUNA等)を横断して
使う社内の共通基盤**になる想定のため([functions/ad-spend-tracking/CLAUDE.md](../ad-spend-tracking/CLAUDE.md)
と同じ位置づけ)。

## 背景・目的(2026-09-17 栗林さん発言)

「keiz-webのMEOプロジェクトとして、MEOチェキを内製化したい。MEOと同じ機能を持った
内部システムを構築して、かつ自分たちが使いやすい機能や仕様を実装していく」という依頼。
現状、複数ブランド(リラックス等)でMEOチェキ・GRC等の順位計測ツールを契約して使っている
([brands/relax/CLAUDE.md](../../brands/relax/CLAUDE.md)参照。APIが無くCSVをDriveに
手動で置く運用)。これを内製化することで、①サブスク費用の削減、②自社の他KPI基盤
(GA4/GSC/CRM等)とのシームレスな統合、③自社独自の機能追加、を狙う。

## 現状の技術的前提(2026-09-17時点で確定した内容)

### GBP公式APIとの関係

同日、[Google Business Profile APIへのアクセス申請](https://support.google.com/business/workflow/16726127)を
web.kanri.keizgroup@gmail.com(GBP全店舗管理アカウント)で送信済み。ケースID
**5-6974000042178**、審査に7〜10営業日。これが承認されれば、MEOチェキが持つ機能のうち
以下は公式APIで賄える:

- インサイト(検索表示回数・検索キーワード・顧客アクション数等) — Business Profile Performance API
- 口コミの一覧取得・返信 — Google My Business API(reviewsリソース)

**賄えないのは「マップ順位チェック」(競合との相対順位)。** これがMEOチェキの核心機能であり、
公式Business Profile APIの範囲外(自社アカウントのデータしか取れない)。

### マップ順位チェックの実現方式(2026-09-17、栗林さん確認済み)

技術検証の結果、**公式Places API(Nearby Search等)は消費者が実際にGoogleマップで見る
ローカルパックの並び順と一致しない**ことが分かった(Places APIのランキングロジックは
「関連性・知名度・距離」等の内部基準で、消費者向けMap/ローカルパックのアルゴリズムとは別物。
参考: [Search Engine Land](https://searchengineland.com/guide/google-maps-vs-local-search)、
[Google Developers Nearby Search](https://developers.google.com/maps/documentation/places/web-service/nearby-search)) 。
そのため方式として以下3案を提示し、当初「有料SERP APIを使う」を採用したが、
**2026-09-17、栗林さんから「MVPはできれば無料で構築したい」との要望があり、
MVP/パイロット段階は自前スクレイピングに変更**(下記「MVP方針の変更」参照)。
本番規模(全ブランド・高頻度チェック)に拡張する段階で、有料SERP APIへの
切り替えを再検討する二段構えとする:

| 方式 | 精度 | コスト | リスク |
|---|---|---|---|
| 有料SERP API(本番規模で再検討) | 高(業者が実際のマップ検索を再現) | 従量課金。DataForSEOは$0.60/1,000件〜と非常に安価。SerpApiはサブスク型で$25/月(1,000件)〜 | Googleブロック対策は業者側で吸収済み |
| **自前スクレイピング(MVP採用)** | 高 | 追加費用ゼロ | CAPTCHA・IPブロック対策が要保守、規約グレーゾーン。MVP/パイロット規模なら実用上のリスクは小さいと判断 |
| 公式Places API | 低(消費者向け順位と不一致) | 安い | MEOチェキ代替としては精度不足。不採用 |

### MVP方針の変更: 自前スクレイピングで無料構築(2026-09-17)

このマシンにはPython 3.12 + Playwright(chromiumバイナリ込み)が実際に動作することを
確認済み。[scripts/meo_rank_check.py](../../scripts/meo_rank_check.py) として実装し、
Googleマップの検索結果パネル(`div[role="feed"] a[href*="/maps/place/"]`)を
スクロールしながら読み取ることで、店舗の並び順(=順位)を無料で取得できることを
実地検証済み:

- 「ピラティス 戸越銀座」で検索 → LUNA Pilates Studio 戸越銀座店を7件中1位で正しく検出
- 「整骨院 船橋」で検索 → スクロールで24件まで読み込み、ページネーションが機能することを確認

この方式は緯度経度を使わず、**検索キーワードにエリア名を含める**(例:「整骨院 船橋」)
ことで地点を指定する。そのため、当初想定していた「GBP API承認 → 店舗の緯度経度取得」
という依存関係は**MVP段階では発生しない**(緯度経度による地点指定は、本番規模で
DataForSEO等に切り替える際に再検討)。

**残るリスク・限界**(栗林さんに伝達済みの前提): Google利用規約上のグレーゾーン、
CAPTCHA/IPブロックへの対策が無い(現状は低頻度・少数店舗のパイロット利用を想定)、
将来的に高頻度・全店舗規模で回す場合はブロックされる可能性が高く、その時点で
有料SERP API(DataForSEO推奨)への切り替えが必要になる。

### GCPプロジェクト

新規に作らず、**既存の「MEO Automation」プロジェクト(project ID: `meo-automation-490007`、
2026年3月作成)を土台として再利用してよいと確認済み**(2026-09-17)。以下がすでに
有効化・作成済みだが、その後使われた形跡はない(BigQueryデータセット無し、サービス
アカウント無し、サンドボックスモードのまま=支払い情報未設定):

- 有効化済みAPI: Business Profile Performance API、My Business Account Management API、
  My Business Business Information API、Google Analytics Data API、Google Sheets API、
  BigQuery関連API一式
- OAuth 2.0クライアントID(デスクトップ アプリ、2026/03/12作成、`699523999859-39nr...`)
- オーナー: web.kanri.keizgroup@gmail.com(ケイズグループ、GBP全店舗管理アカウントと同一)

なお、GBPインサイト・口コミAPIの許可リスト申請(上記ケースID 5-6974000042178)は
別プロジェクト `gbp-api-access`(project番号 957906329881)で申請済み。
**用途を分けている**: `gbp-api-access` = 許可リスト申請対象の狭いスコープ、
`meo-automation-490007`(MEO Automation) = 順位チェック・データ蓄積・ダッシュボード等
アプリケーション層の土台。

## 順位チェックAPIの技術仕様(本番規模に切り替える場合の参考、調査済み・未使用)

将来、有料SERP APIに切り替える場合の参考。DataForSEOのエンドポイントは
`POST https://api.dataforseo.com/v3/serp/google/maps/live/advanced`。リクエストは
`location_coordinate`("緯度,経度,ズーム" 形式)と `keyword` を渡す形式で、レスポンスに
`rank_group`/`rank_absolute`(順位)、`place_id`、`title`、`rating`、`reviews_count` 等が
ローカルパックの並び順そのままで返る。参照:
[dataforseo.com/apis/serp-api/google-maps-api](https://dataforseo.com/apis/serp-api/google-maps-api)、
[docs.dataforseo.com/v3/serp-google-maps-overview](https://docs.dataforseo.com/v3/serp-google-maps-overview/)。
この方式に切り替える際は`location_coordinate`(店舗の緯度経度)が必要になるが、
[data/clinics.json](../../data/clinics.json)には現状lat/lngが無いため、GBP公式API
(Business Information API、ケースID 5-6974000042178承認後)のlocationリソースから
取得するのが最も正確(再ジオコーディングより優先)。**MVP(自前スクレイピング)段階では
この依存関係は発生しない**(検索キーワードにエリア名を含めることで地点を指定するため)。

## データモデル: BigQueryに作成済み(2026-09-17)

`meo-automation-490007` プロジェクトに、データセット`meo_internal`と以下3テーブルを
**実際に作成済み**(BigQueryコンソールから直接DDL実行。サンドボックスモードのままで
支払い設定不要だった):

| テーブル | 主なカラム | 備考 |
|---|---|---|
| `rank_checks` | check_date, store_id, brand, keyword, location_coordinate, rank_absolute, found, place_id, matched_name, total_listings_seen, source | [scripts/meo_rank_check.py](../../scripts/meo_rank_check.py)の出力を書き込む想定。まだ投入処理は未実装(スクリプトはJSON出力のみ) |
| `review_snapshots` | snapshot_date, store_id, brand, review_count, average_rating, source | GBP公式API(無料、承認待ち)から取得予定 |
| `keywords_master` | store_id, brand, keyword, active, added_date | どの店舗にどのキーワードを追跡させるかの設定表。MEOチェキの現行設定を移植する形を想定(下記CSVサンプル待ち)。**まだ空。**投入が次の作業 |

`store_id`は[data/clinics.json](../../data/clinics.json)の`id`と一致させる。
`check_date`/`snapshot_date`でパーティション、`store_id`(等)でクラスタリング済み。

## MEOチェキ実機調査(2026-09-17、栗林さんの指示で「内部仕様のチェックは全てローカル
Claude Codeにやらせたい」との方針に基づき、ブラウザで実際にログインして直接調査)

- 実体は「MEO CHEKI byGMO」(運営: 株式会社トライハッチ)。ログイン画面は
  https://ranktoolap.com/users/sign_in 、アプリ本体は https://app.ranktoolap.com 。
  ログイン情報はChromeに保存済み(t-kuribayashi@keizgroup.jp)。reCAPTCHAがあるため
  ログイン操作自体は栗林さんご本人にクリックしてもらう必要があった(Claude Codeは
  CAPTCHA操作不可)
- アカウント: 33534 - t-kuribayashi@keizgroup.jp、契約社名「株式会社ケイズグループ」、
  **登録店舗数199件**(直営・サンズミライ・LUNA・リラックス等が混在)
- 店舗一覧(`/d/businesses`)の主な列: ユーザー名、グループ名、カテゴリ、会社・屋号名、
  店舗・施設名、検索地点(駅名などの地名)、検索時間(基本05:00固定=毎日深夜〜早朝に
  自動チェック)、本日の最高順位、メインカテゴリ。店舗ごとに「順位チャート」「順位
  カレンダー」「インサイト」「クチコミ管理」等のタブがある

### 順位チェックのキーワード構成パターンを実データで確認(重要な発見)

LUNA Pilates Studio 戸越銀座店(`/d/rankings/charts?business_id=122102`)の実データ:

**地点2種 × カテゴリ5種 = 10キーワード**を毎日チェックしている:

| | ピラティス | ピラティススタジオ | マシンピラティス | ジム | フィットネス |
|---|---|---|---|---|---|
| **戸越銀座** | 2位 | 3位 | 3位 | 11位 | 6位 |
| **戸越** | 2位 | 2位 | 4位 | 20位 | 13位 |

キーワードは「駅名(広め/狭め2種)+ カテゴリ語」の組み合わせで、緯度経度は使っていない
(検索キーワード文字列に地名を含めることで地点を指定している)。**これは
[scripts/meo_rank_check.py](../../scripts/meo_rank_check.py)で採用した方式(エリア名を
キーワードに含める)と同じ設計思想**で、無料スクレイピング方式の妥当性を裏付ける実例
になった。参考までに自前スクレイピングで「ピラティス 戸越銀座」(語順が逆)を検索した
結果は1位、MEOチェキの「戸越銀座 ピラティス」は2位——語順・チェック時刻の違いによる
妥当な誤差の範囲。

### インサイト画面はBusiness Profile Performance APIそのもの

`/insights?business_id=122102` の中身は「ビジネスプロフィールで実施されたインタラクション」
「閲覧したユーザー数」「表示につながった検索キーワード」等、**GBP公式APIの
Performance API/reviewsが返すデータとほぼ同一の見た目**。これはGBP API承認後、
同等以上のデータを無料で自前取得できることの裏付けになる

### クチコミ管理画面の機能一覧

`/d/operation?business_id=122102`(「運用」メニュー配下):
主要指標(平均評価・総数・今月の件数・ポジティブ/ネガティブワード件数・返信率)、
個別クチコミへの返信(文字数カウント付き)、**一括返信**(入力内容で一括/共通文章で一括)、
CSV出力、AI文章生成(月間利用回数の上限あり)。これらは口コミ一覧取得・返信という点で
GBP公式API(reviewsリソース)で代替可能。「ポジティブ/ネガティブワード」抽出や
AI返信文生成は、GBP APIには無い付加機能——**Claudeを使えばここが自社独自の
強みにできる**(MEOチェキ以上の機能を無料で提供できる部分)

### 全店舗一括CSVエクスポート → BigQuery投入まで完了(2026-09-17)

`/reports/exports_csv` の「【順位】順位データ全案件ダウンロード」(全店舗×全キーワードの
順位データ、当月分)と「【レビュー】レビューダウンロード」を、送信先
t-kuribayashi@keizgroup.jp を指定して実行。メールは`info-meo@ranktoolap.com`から届く
(件名「順位データ全案件ダウンロード」「レビューダウンロード」、本文中のS3署名付きURLは
**有効期限30分**なので早めに開く。Gmail APIでの本文取得はquoted-printableの`=`が
一部失われる不具合があったため、実URLはGmail Web UI上のリンクをクリックして取得した)。

取得したCSV:
- `MEO_google_2026-09-01_2026-09-30.csv`(3.2MB): 列は`日付,案件名,検索キーワード,
  順位,検索住所,取得時間`。31,454行 = 199店舗 × 1,856ユニーク店舗×キーワードの組み合わせ
  (店舗あたり平均9.3キーワード)× 日次
- `business_review_20260917.csv`(9.5MB): 先頭5行がサマリー(口コミ総数30,141・平均評価4.7・
  今月169件等)、6行目が空行、7行目が実データのヘッダー`店舗名,投稿者,日付,点数,新着,
  未返信,口コミ内容`。全30,141件の口コミ本文・投稿者名を含む(**個人情報のため
  リポジトリにコミットしない。`.gitignore`に`.scratch/`を追加済み**)

[scripts/meo_import_rank_export.py](../../scripts/meo_import_rank_export.py)で順位CSVを
BigQuery投入用NDJSONに変換し、`bq load`で実際に投入済み:
- `meo_internal.keywords_master`: 1,856行
- `meo_internal.rank_checks`: 31,454行(`source='meochecki_csv_import_20260917'`で識別)

口コミCSVは個別レビュー明細(日次スナップショットではない)なので、`review_snapshots`
テーブルへの投入は見送り、GBP API承認後に本来の想定通りAPI経由で取得する方針のまま
(下記次ステップ参照)。**store_idは現状MEOチェキの「案件名」をそのまま使っており、
`data/clinics.json`のidとはまだ突き合わせていない**(次ステップに記載)。

### つまずいた点と解決策(再現用メモ)

1. BigQueryコンソールの「テーブルを作成」ダイアログの「ソース」ドロップダウン
   (`cfc-select`というカスタム部品)は、キーボード操作(Down+Enter)やオプション要素への
   直接クリックだと選択が反映されずパネルごと閉じてしまう不具合があり、ブラウザ経由の
   CSVアップロードは断念した
2. 代わりにサービスアカウント作成・IAM権限付与をブラウザから行おうとしたが、
   Claude Codeの権限フィルタが両方とも自動ブロック(要ユーザー確認のアクション)
3. ローカルの`gcloud`/`bq`を使う方針に切替。栗林さんのPCではPowerShellの
   実行ポリシーで`gcloud.ps1`がブロックされたため、**`gcloud.cmd auth login`
   (.ps1を経由しない)で再ログイン**してもらった
4. 最後にt-kuribayashi@keizgroup.jpへの`meo-automation-490007`プロジェクトの
   IAM付与(BigQuery管理者)だけは栗林さんご自身にブラウザから実施していただいた
   (付与自体はClaude Codeでは実行できない操作のため)
5. これで`bq load`が成功。**今後このプロジェクトに対してはローカルCLIがそのまま使える**
   (t-kuribayashi@keizgroup.jpにBigQuery管理者ロールが付与済み)

## 未解決・次のステップ

1. `keywords_master`/`rank_checks`の`store_id`(現状MEOチェキの「案件名」文字列)を
   [data/clinics.json](../../data/clinics.json)の`id`と突き合わせる(名寄せ処理が必要。
   完全一致しない店舗名がある可能性が高いので推測で決めない)
2. [scripts/meo_rank_check.py](../../scripts/meo_rank_check.py)(無料スクレイパー)の
   出力をBigQuery`rank_checks`テーブルに書き込む処理を実装(現状はJSON出力のみ)。
   実際に投入済みのMEOチェキ実測値と突き合わせて精度検証する
3. パイロット対象店舗・キーワードを数件選び、無料スクレイパーを定期実行してデータを溜める
4. GBP API申請(ケースID 5-6974000042178)の承認を待つ → 承認後、
   `review_snapshots`テーブルへの投入処理をAPI経由で実装
5. ダッシュボード/レポート設計。MEOチェキに無い自社独自機能として、上記の
   ポジティブ/ネガティブワード分析・AI返信文生成をClaude側で実装する案が有力
6. 本番規模(全ブランド・高頻度)に拡張する段階で、自前スクレイピングのブロック
   リスク・保守負荷を評価し、有料SERP API(DataForSEO)への切り替えを再検討する

### 保留中の項目(栗林さんの対応待ち)

- (本番規模移行時のみ)DataForSEO等のアカウント登録・支払い設定 — 私は決済情報を
  扱えないため、その時点でご本人対応が必要

## ストレージ層をBigQueryからGoogle Sheetsに変更(2026-09-17、同日中に方針転換)

上記「データモデル: BigQueryに作成済み」節で構築したBigQuery(`meo_internal`データセット)は、
**投入直後にデータが消失する不具合が発覚し、使用を中止した**。以下は原因・経緯・
代替手段(Google Sheets)への切り替え手順の記録。

### 発覚した問題: BigQueryサンドボックスモードの60日パーティション有効期限

`meo-automation-490007`は支払い情報未設定の**サンドボックスモード**のままBigQueryを
使っていた。サンドボックスモードのテーブルは、パーティション(この場合`check_date`)に
基づいて**60日で自動的にデータが削除される**仕様がある。投入したCSVの日付範囲が
1〜8月分を含んでいたため、投入直後からパーティションの一部(60日より古い日付)が
消え始めており、**このまま使い続けると過去データが恒常的に失われる**ことが判明した。
支払い情報を設定してサンドボックスを解除すれば回避できるが、栗林さんの意向を確認した
うえで、2026-09-17に「Google Sheetsへの保存に切り替える」方針に転換した。

### 検討した代替ストレージと、Google Sheetsを選んだ理由

BigQueryの支払い設定(サンドボックス解除)も選択肢としてはあったが、①決済情報の
入力はClaude Codeでは扱えず都度ご本人対応が必要になる、②現時点のデータ量
(rank_checks 470,117行 + keywords_master 1,856行)ならGoogle Sheetsで十分扱える、
③スプレッドシートなら栗林さんご自身が中身を直接見て手直しできる、という理由から
**Google Sheets(1シート)への切り替え**を採用した。年ごとにファイルを分割する案も
検討したが、現状すべてのデータが2026年に収まるため、当面は単一の
「MEO順位ログ_2026」スプレッドシートとし、年が変わった時点でファイル分割を再検討する
運用にした。

### 試して失敗した投入方法: IMPORTDATA / Google Picker

CSVをそのままGoogle Sheetsに取り込む方法として、まず`IMPORTDATA`関数
(`=IMPORTDATA("https://drive.google.com/uc?export=download&id=<file_id>")`)を試したが、
**繰り返し「読み込み中」のまま止まる、または列が正しく分割されずに壊れた状態になる**
不具合が再現し、複数回試しても改善しなかった。次にGoogleのファイル選択UI(Picker)経由の
取り込みも検討したが、これもブラウザ自動操作との相性が悪く安定しなかった。
栗林さんの指示「代替手段に切り替えてください」を受けて、この2方式は放棄した。

### 最終的に採用した投入方法: Drive変換(CSV→Sheets) + IMPORTRANGE

安定して動作した手順は以下の通り(11ファイル: `rank_checks_part01.csv`〜`part10.csv`、
`keywords_master_combined.csv`。1ファイルが Sheets の行数上限に収まるよう、
31,454行の順位データを10分割してアップロードしていた):

1. **Google Driveの「アプリで開く」機能でCSVをネイティブのGoogle スプレッドシートに
   変換する**(右クリックまたはケバブメニュー→「アプリで開く」→「Google スプレッドシート」)。
   この変換は日本語の文字化けが起きず、`IMPORTDATA`より確実に動いた。
   変換すると新しいSheetsファイル(元CSVとは別ファイル)が生成される。
2. **本体のスプレッドシート(「MEO順位ログ_2026」)側で、変換済みの各チャンクを
   `IMPORTRANGE`で連結する**。各チャンクのデータ行数に合わせて、`rank_checks`タブの
   行オフセットを事前に計算し(50,000行ずつ)、10個の`IMPORTRANGE`式を配置した。
3. `IMPORTRANGE`は参照先スプレッドシートごとに初回のみ「アクセスを許可」の同意が必要。
   この同意バナーはセルクリック直後には出ないことがあり、**ページの再読み込み
   (URLへの再ナビゲート)を挟むと確実に表示される**、という運用上のコツがある。

### つまずいた点(BigQuery移行時とは別の、Sheets移行時の固有の問題)

- **セル数1,000万の上限**: `IMPORTRANGE`の展開先スプレッドシートは、ワークブック内の
  全シート・全タブを合計したセル数(行×列)が1,000万を超えられない。以前の失敗した
  試行(IMPORTDATA等)で作られた**不要な広い列範囲(H〜KN列、293列)が空のまま
  残っていて**、これが原因で新規行の追加時にセル数上限エラーが出た。該当列を削除して
  解消した。**Sheetsで大量データを扱う前は、Ctrl+Endで実際に使われている範囲を確認し、
  不要な広い範囲が残っていないか確認すること。**
- **行の一括追加**: シートの一番下までスクロールすると出る「一番下に[N]行 追加」の
  入力欄で、必要な行数(今回は420,000行)を一度に指定して追加できる。
- **ブラウザ自動操作での数式入力の信頼性**: Name Box(セル参照ボックス)への高速な
  連続入力は、まれに(a)数式が入力されない、または(b)スクロール位置のずれにより
  意図しないセルに入力される、という**サイレントな失敗**を起こすことがあった
  (実際に2箇所で発生・検出・修正)。**Name Boxでセルへ移動した直後は、そのセルの
  数式バーをズームで確認してから次の操作に進む**、という検証を徹底することで
  再発を防いだ。

### 現状(2026-09-17時点)

- 「MEO順位ログ_2026」スプレッドシートの`rank_checks`タブ(470,117行+ヘッダー)・
  `keywords_master`タブ(1,856行+ヘッダー)とも、`IMPORTRANGE`経由で全件投入・
  エラーなしを確認済み
- 元の11個のCSVファイルは、投入作業中だけ一時的に「リンクを知っている全員」に
  共有設定を変更していたが、**投入完了後に「制限付き」(非公開)へ戻し済み**
- [scripts/meo_import_rank_export.py](../../scripts/meo_import_rank_export.py)は
  BigQuery向けNDJSON出力のままで、**この切り替えを反映できていない**(次のステップに追記)
- [scripts/meo_merge_monthly_exports.py](../../scripts/meo_merge_monthly_exports.py)は
  複数月分のMEOチェキCSVを1本に統合してCSVを出す処理で、こちらはストレージ層に依存しない
  ため変更不要。統合後のCSVをDrive変換+IMPORTRANGEの入力として使う想定
- `meo-automation-490007`プロジェクトのBigQueryデータセット(`meo_internal`、
  60日で消えるサンドボックスモードのまま)は**放置すると同じ問題が再発する上、
  もう使わない**ため、削除するかどうかを栗林さんと相談する必要がある(下記「未解決・
  次のステップ」に追記)

## 未解決・次のステップ(更新: 2026-09-17 Sheets移行後)

上記「未解決・次のステップ」節の1〜6に加えて:

7. [scripts/meo_import_rank_export.py](../../scripts/meo_import_rank_export.py)を、
   BigQuery向けNDJSON出力からGoogle Sheets(IMPORTRANGE用の中間CSV、または将来的には
   Sheets APIでの直接書き込み)向けに書き換える
8. `meo-automation-490007`のBigQueryデータセット(`meo_internal`)を削除するか、
   このまま放置(サンドボックスのため課金は発生しない)するか、栗林さんと決める
9. 月次の運用フロー(MEOチェキから新しい月のCSVをダウンロード→
   `meo_merge_monthly_exports.py`で統合→Drive変換→`IMPORTRANGE`の行オフセットを
   延長)を、手作業でもすぐ回せる手順書としてこのファイルに追記するか、
   半自動化スクリプトにするか検討する
