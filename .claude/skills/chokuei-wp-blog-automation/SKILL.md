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

### ローカルセッションへの依頼文(コピー用)

栗林さんがローカルのClaude Codeでこのリポジトリを開いた際に、以下をそのまま貼り付ければ
着手できる:

> 直営WordPressブログ自動化の調査をお願いします。まず
> `.claude/skills/chokuei-wp-blog-automation/SKILL.md` と
> `data/proposals/2026-09-18_chokuei-wp-blog-automation.md` を読んでください。
> その上で、claude-in-chrome(実Chrome)を使って以下2点を確認してください。
>
> 1. 「ブログ更新仕様書」スプレッドシート
>    (https://docs.google.com/spreadsheets/d/1VjA5jwLLHES1U1RPtO_WhwS0BJJ3sXXSoLx4ah4Ac6k)
>    に記載のWordPress共通ログインで、いずれか1店舗の管理画面にログインし、
>    「ユーザー→プロフィール」にApplication Passwords(アプリケーションパスワード)の
>    発行欄があるか確認してください。あれば実際に1つ発行して、
>    `/wp-json/wp/v2/posts`へのPOSTが通るか(下書き投稿で可)を試してください。
> 2. スタッフ紹介トピックのブログ記事が実際に公開されている店舗ページを1つ開き、
>    ページソース(投稿本文のHTML構造)を確認してください。可能なら同じ仕様書スプレッド内の
>    ひな形セクションも探してください。`curacion系`テーマの店舗があれば、同様に症状記事の
>    ひな形も確認できると理想です。
>
> **WordPressのユーザー名・パスワード・発行したApplication Passwordは、このリポジトリの
> どのファイルにも書き込まないでください**(CLAUDE.mdの認証情報ルール)。確認できた
> HTML構造(ひな形そのもの、プレースホルダーの位置)や「REST APIが使えた/使えなかった」
> という結果だけを、SKILL.mdの「未確認」リストとdata/proposals/の該当ブロッカー欄に
> 反映してください。テンプレートHTML自体は
> `.claude/skills/chokuei-wp-blog-automation/templates/`配下に保存してよい
> (これは仕様書自体に含まれる情報で、ログイン情報ではないため)。

## 関連ドキュメント

- [data/proposals/2026-09-18_chokuei-wp-blog-automation.md](../../../data/proposals/2026-09-18_chokuei-wp-blog-automation.md) — 全体調査・アーキテクチャ・段階導入計画
- [brands/chokuei/CLAUDE.md](../../../brands/chokuei/CLAUDE.md) — 直営ブランドの法人体系・ドメイン系統・未確認事項
- [docs/backlog.md](../../../docs/backlog.md) — 「リラックス WordPress環境の実態調査」(別ブランドだが同種のWP調査の先行事例)
