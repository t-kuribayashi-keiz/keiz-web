---
name: chokuei-wp-blog-automation
description: Use this skill for automating the monthly WordPress blog post workflow for 直営(135院、8法人)— turning raw material staff enter monthly in the "ホームページ用原稿資料" spreadsheet into a polished blog article (applying the 景品表示法対応 correction rules) and publishing it to the store's own WordPress site. Trigger on "直営のブログ更新を自動化して", "今月のブログ投稿を回して", "ブログ更新仕様書の通りに投稿して", or requests to extend this pipeline to a new blog topic (トピック) or new store. STATUS (2026-09-18): design-only, no working code yet — see data/proposals/2026-09-18_chokuei-wp-blog-automation.md for the full investigation and phased rollout plan. Do NOT assume a working publisher exists; only the スタッフ紹介トピックの原稿スキーマと校閲ルールが確認済み. Do NOT use this for SalonBoard/HotPepper Beauty blog work (that's hpb-salonboard-update / hpb-ahaki-blog-rotation) or for リラックスブランドのWordPress調査(別ブランド・別インフラ、docs/backlog.mdの該当項目を参照) — this skill is chiryouin.biz/chiryou-in/curacion系ドメインを使う直営専用.
---

# 直営 WordPressブログ月次更新 自動化

**現在地(2026-09-18時点)**: 設計フェーズ0が完了しただけで、動くコードはまだ無い。
全体像・確認済み事実・未確認ブロッカーは
[data/proposals/2026-09-18_chokuei-wp-blog-automation.md](../../../data/proposals/2026-09-18_chokuei-wp-blog-automation.md)
を必ず先に読むこと。このSKILL.mdはそこからの要点と、次にやることだけをまとめる。

## なぜ完成していないか(先に断る)

`hpb-ahaki-blog-rotation`のように「実データを精査してから作る」方針をここでも踏襲している。
対象の「ホームページ用原稿資料」スプレッドシートは112MBあり、このセッションのGoogle Drive
ツールでは全体を読めなかった(タイムアウト・セッション切断)。全文検索のプレビューで
断片的に確認できた範囲だけがこのSkillの根拠であり、以下は**まだ未確認**:

- トピック(院長挨拶・腰痛・肩こり…80種以上)ごとの原稿材料タブの列構成
  (確認できたのはスタッフ紹介トピックの1タブのみ)
- スタッフ紹介トピック用・`curacion`系テーマ用のHTMLひな形
- 各店舗のWordPress REST API / Application Passwordの利用可否
- 「アップ状況一覧」の店舗別ログインURL列を集約した、店舗→テーマ系統の対応表

**このSkillを使う人は、上記が埋まっていないトピック・店舗に対して見切り発車で投稿しないこと。**
1店舗・1トピックで人が最終確認しながら通しで動かし、確定してから対象を広げる
(提案書「5. 段階導入計画」参照)。

### クラウド環境から直接は進められないことを確認済み(2026-09-19)

このクラウドセッションから、ログイン抜きで進められる部分(公開ブログページのHTML取得・
`/wp-json/`のREST API疎通確認)だけでも自力で済ませようとしたが、`curl`で
`https://motoyawata.chiryouin.biz/`(直営の実店舗サイト)に直接アクセスしたところ、
ログインとは無関係に**403 Forbidden**(レスポンス本文は`Copyright XSERVER Inc.`の
汎用エラーページ)が返ってきた。これはXserver側のホスティングレベルのアクセス制限で、
このクラウド実行環境のIPアドレスそのものがブロックされているためと判断できる
(ID・パスワードの正誤とは無関係)。**したがって公開ページの閲覧・REST API疎通確認・
ログインのいずれも、実オフィス/自宅回線のIPからでないと進められない**。ローカルPCの
claude-in-chrome(実Chromeの実際の回線)が必要な理由はこれで確定した。

### 「サイトIDパスワード表」について(2026-09-19確認)

栗林さんの指摘通り、ルートCLAUDE.mdに記載の「サイト情報一覧」ことスプレッドシート
(ID: `1n06i3R6QYuQ4SUCid3RsT5rnNcmtc9jxOaqZPKNGnnc`、実際のファイル名は
「サイトIDパスワード表」)が各店舗のWordPressログインURL・ID・パスワードの一次情報として
存在することを確認した。**このセッションでは中身を読み込んでいない**: 実行環境の安全機構が
このファイルの内容をファイルへ書き出す操作を「Credential Materialization」として自動的に
拒否したため、それ以上の抽出を試みていない。140以上の実パスワードをこのセッションの会話
コンテキストに持ち込むこと自体、たとえ技術的に回避できたとしても避けるべき操作と判断した。

**この表そのものは自動化の直接の入力にしない設計を推奨する。** ローカルセッションが
この表を見て1店舗ずつ手でログインし、WordPress標準機能(ユーザー→プロフィール→
Application Passwords)でサイトごとに**発行し直した**アプリケーションパスワードだけを
自動化に使う。理由: アプリケーションパスワードは失効・再発行が自由で、万一漏れても本体の
ログインパスワードには影響しない。マスターのID・パスワード表自体をリポジトリやGAS
Script Propertiesにコピーする必要は無く、そうすべきでもない。

## 確認済み事実(そのまま使ってよい)

### 校閲ルール(ChatGPTに代わってClaude自身が適用する)

原文は提案書2章に全文転記済み。要点:
- 「治療」→「施術」、「改善」→「軽減/軽減が期待」、「効果的」→「効果が期待できる」、
  「自院」→「当院」、「問診」→「カウンセリング」
- 断定的表現は柔らかい言い回しに、全体を丁寧な「です・ます」調に統一
- **景品表示法遵守が唯一の絶対条件**。生成後、「治療」「改善」等の禁止語や断定表現が
  残っていないか機械チェックしてから初めて投稿候補として扱う(`banned_word_check`相当。
  `hpb-ahaki-blog-rotation/scripts/build_ahaki_blog_post.py`の禁止語チェックの考え方を流用可)

### 既知の例外店舗

- **稲毛海岸中央整骨院**: サイトが「静的」ページのため、このパイプラインの対象外
  (毎月スキップする)

### スタッフ紹介トピックの原稿材料スキーマ(唯一確認済みのトピック)

「ホームページ用原稿資料」内、姓の50音別タブ(例:「【あ行】原稿」)に、店舗をまたいだ
全スタッフが1行1人の形式で入っている:

```
氏名（漢字）,氏名（ふりがな）,顔写真,画像URL,①出身地,②趣味,③血液型,
④持っている資格,⑤当院のキャッチコピー,⑥施術家になるまでの自分,
⑦新人・修業時代の自分,⑧地域の皆さまへの熱いメッセージ
```

このトピックのHTMLひな形はまだ未取得(次のアクション参照)。

### WordPress共通ログイン

全店共通の1組のユーザー名・パスワードが手順書に直書きされている。**このSkillのどのファイルにも
転記しない。** 実行環境では環境変数(例: `CHOKUEI_WP_USERNAME` / `CHOKUEI_WP_APP_PASSWORD`)
またはGAS Script Propertiesから読むこと。

## 次のアクション(フェーズ1)

**この2点はローカル実行必須(claude-in-chrome + 実Chrome)。** クラウド実行環境には
ブラウザ操作手段が無く、WordPressへのログインもできないため、このフェーズ1調査は
`salonboard-operator`と同様にユーザーのローカルPC上のセッションに依頼する必要がある。

1. スタッフ紹介トピック用のHTMLひな形を「ブログ更新仕様書」内の該当セクション、または
   実際に公開済みのスタッフ紹介記事のページソースから確認する
2. 1店舗で実際にWordPressにログインし、ユーザープロフィールからApplication Passwordが
   発行できるか(REST APIが有効か)を確認する
3. 上記2点が揃った時点で、はじめて「対象店舗特定→原稿取得→生成→禁止語チェック→
   投稿→院ブログ更新表への記録」を1店舗分、人の最終確認付きで通しで実装・実行する
4. 実行基盤はGoogle Apps Script推奨(理由: 対象スプレッドシートが112MBありこのセッションの
   Driveツールでは扱えないが、GASなら`SpreadsheetApp`で対象タブ・行だけ直接読み書きできる)

### ローカルセッションでの着手方法(貼り付け不要)

このSKILL.md自体に手順・確認事項・禁止事項(認証情報を書き込まない等)を全て書いてあるので、
長い指示文を毎回貼り付ける必要はない。ローカルPCでこのリポジトリのClaude Codeを開き、
`git pull`した上で「直営ブログ自動化のフェーズ1を進めて」のような一言を伝えるだけでよい
(このSkillのdescriptionがそのトリガーを拾い、このSKILL.mdが読み込まれる)。あとは
claude-in-chromeで「サイトIDパスワード表」を見ながら1店舗ログインし、上記2点
(Application Password発行可否、スタッフ紹介記事のHTML構造)を確認して、結果を
このSKILL.mdとdata/proposals/の該当ブロッカー欄に反映するだけ。

## 関連ドキュメント

- [data/proposals/2026-09-18_chokuei-wp-blog-automation.md](../../../data/proposals/2026-09-18_chokuei-wp-blog-automation.md) — 全体調査・アーキテクチャ・段階導入計画
- [brands/chokuei/CLAUDE.md](../../../brands/chokuei/CLAUDE.md) — 直営ブランドの法人体系・ドメイン系統・未確認事項
- [docs/backlog.md](../../../docs/backlog.md) — 「リラックス WordPress環境の実態調査」(別ブランドだが同種のWP調査の先行事例)
