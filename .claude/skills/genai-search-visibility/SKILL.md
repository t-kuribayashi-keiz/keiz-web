---
name: genai-search-visibility
description: Use this skill for collecting and aggregating Google Search Console's beta「生成AI機能(AI Overviews)」performance report — "合計表示回数" (impressions inside Google's AI-generated search surfaces) — across all 直営・サンズミライ store properties. Trigger on "生成AI表示回数を集計して", "AI Overviewsの表示回数まとめて", "生成AI機能のレポートを店舗分集めて", or requests to roll up the GSC "生成AI機能(ベータ版)" report across many stores. Do NOT trigger for ordinary GA4/GSC (web検索) automation, which is a separate API-based pipeline once one exists for this brand group — this skill exists specifically because the AI-features metric has no API and must be read from the browser.
---

# 生成AI機能(AI Overviews)表示回数の集計 — 直営・サンズミライ全店舗

## 背景

2026-09-15、栗林さんから「生成AI表示数を直営、サンズ、ミライ全店舗でまとめたい」という依頼があり、
その場でSearch Console API (`searchanalytics.query`)を調査した。**結論: この指標はAPIから取得
できない。** `type`フィールドは`web/image/video/news/discover/googleNews`のみで、AI Overviews/AI
Mode用の値が無く、`searchAppearance`ディメンションにも該当値が無く、専用エンドポイントも無い。
2026年6月にSearch Console UIへ追加された「生成AI機能(ベータ版)」レポートは現時点(2026-09)で
UI専用のベータ機能で、Discover/Newsレポートの時と同じ「UI先行→数か月後にAPI追随」のパターンを
辿っている可能性が高いが、時期は不明。

つまり**このSkillが存在する唯一の理由は、GoogleがまだAPIを提供していないこと**。ブラウザ操作
(`claude-in-chrome`)以外に取得手段が無い。将来APIが追加されたら、このSkillのフェーズB(下記)は
不要になり、`hpb-ribbon-kpi`や`functions/kpi-aggregation`と同じ通常のAPIベースの集計に切り替える
べき — 定期的にSearch Console APIのドキュメントを再確認すること。

## Non-negotiable rules

0. **このSkillは、`claude-in-chrome`でユーザーの実ブラウザ(admin@keizgroup.jpでログイン済み)に
   アクセスできるローカルのClaude Codeセッションでのみ動く。** クラウド実行環境にはブラウザが無く、
   GSC UIに触れない。`mcp__claude-in-chrome__*`ツールが無い環境でこのトリガーが来たら、
   ブラウザ操作を試みたりAPIで代替しようとしたりせず、**その場で止まってローカルPCでの実行を
   依頼する**こと。
1. **2フェーズで進める。フェーズを飛ばさない。**
   - **フェーズA(パイロット・都度確認)**: `references/procedure.md`の「確定手順」と
     `data/genai-search-visibility-properties.json`の店舗↔プロパティ対応表が**両方とも確定済み
     (`status: confirmed`)**でない限り、まずこのセッション自身(モデルは通常どおりでよい。
     Haikuに切り替える前)が実際に1つ以上のプロパティで画面を操作し、以下を確認・記録する:
     - 正確なクリック手順(検索パフォーマンス→生成AI機能タブへの到達経路、期間指定UIの操作)
     - admin@keizgroup.jpが実際に対象プロパティへアクセスできるか(想定と違えば栗林さんに確認)
     - 店舗名 ↔ GSCプロパティURLの対応(推測しない。1件ずつ実在確認したものだけ`confirmed`にする)
     ここを飛ばしてフェーズBに進まないこと。Haikuは「決まった手順の反復」には強いが、
     手順自体をその場で発見・修正する作業には向かない — 手順が未確定のままHaikuに投げると、
     画面遷移でつまずいた時に自己流の代替手順を編み出して誤読・誤記録するリスクがある。
   - **フェーズB(一括収集)**: フェーズAで手順・対応表が確定している回のみ、全店舗分の反復巡回は
     **ローカルの同じセッションをHaikuモデルへ切り替えて(例: `/model haiku`)実行する**。
     2026-09-15の会話で、この作業(決まった手順で画面の数字を読んで書き写すだけの反復・複雑な
     判断を要しない)にはHaikuで十分と判断した。ただし`references/procedure.md`に無い分岐
     (生成AI機能タブが無い、0件、アクセス権エラー、想定外のUI)に当たったら、Haikuは推測で
     埋めず、その店舗を「要確認」として空欄のまま報告する(rule 3)。
2. **全プロパティで同一の期間・フィルタ(デバイス/国)を揃える。** 実行のたびに「今回使った期間」を
   結果に明記する(期間がバラバラだと店舗間比較が無意味になる)。
3. **判定できないものを黙って埋めない。** 未マッチ店舗、アクセス権が無いプロパティ、0件、
   レポート自体が表示されない店舗は空欄のまま一覧化し、最終報告で個別に挙げる。
4. **最終の合計・店舗数の検算はHaikuに任せない。** フェーズBが終わったら、通常モデルのセッション
   (Haikuから戻す)が、対応表の店舗数と実際に読み取れた件数が一致するかを確認し、いくつかの値を
   画面で再確認(スポットチェック)してから栗林さんに報告する。
5. **ブランド側CLAUDE.mdの記載を実態に合わせて更新する副産物を忘れない。** `brands/chokuei/CLAUDE.md`
   と`brands/sunsmirai/CLAUDE.md`の未確認事項に「GA4・Google Search Console等の分析ツール連携状況
   (現時点で連携の記録なし)」とあるが、これは2026-09-15時点で未更新のまま。フェーズAで
   admin@keizgroup.jpが実際に対象プロパティへアクセスできることを確認したら、この行を
   「admin@keizgroup.jpのブラウザアクセスでは連携確認済み(API連携は別途未整備)」のように
   実態に合わせて更新する。API連携(サービスアカウント+ドメイン全体委任)は別課題として混同しない。

## 対象範囲

`hpb-ribbon-kpi`と同じ「Master 140店(直営＋サンズミライ)」を暫定の想定スコープとする
(2026-09時点、`hpb-ribbon-kpi/SKILL.md`参照)。ただし対象店舗の確定リストは未確認 —
フェーズAで実際の店舗マスタ・admin@keizgroup.jpのSearch Consoleプロパティ一覧と突き合わせて
確定させること。店舗数が食い違う場合(140店ちょうど揃わない等)は憶測で埋めず栗林さんに確認する。

## 手順

### フェーズA: パイロット(手順・対応表の確定)

1. `references/procedure.md`と`data/genai-search-visibility-properties.json`を読み、既に
   `confirmed`になっている内容があればそこから再開する(全部やり直さない)。
2. admin@keizgroup.jpでログイン済みの実Chromeで、Search Consoleのプロパティ一覧を開き、対象
   140店に該当するプロパティが実際に見えるか確認する。見えないプロパティがあれば、その場で
   一覧化して栗林さんに報告する(憶測で「あるはず」として進めない)。
3. 1店舗で実際に「検索パフォーマンス→生成AI機能(ベータ版)」タブを開き、期間設定→
   「合計表示回数」の読み取りまで一通り操作し、正確な手順を`references/procedure.md`に書く。
4. 店舗名とGSCプロパティURLの対応を、確認できた分から`data/genai-search-visibility-properties.json`
   に追記する(1件ずつ実在確認したものだけ)。

### フェーズB: 一括収集(Haiku)

1. フェーズAの手順・対応表が確定していることを確認してから、ローカルセッションをHaikuモデルへ
   切り替える。
2. `data/genai-search-visibility-properties.json`の対応表を1店舗ずつ辿り、`references/procedure.md`
   の確定手順どおりに「生成AI機能(ベータ版)」タブを開き、指定された期間の「合計表示回数」を
   読み取って記録する。
3. 手順書に無い分岐(タブが無い/0件/エラー)に当たった店舗は、推測で埋めず「要確認」として
   空欄のまま次の店舗へ進む。

### 集計・報告(通常モデルへ戻す)

1. Haikuから通常モデルへ戻し、全店舗分の記録を合計する。対応表の店舗数と実際に読み取れた件数
   (「要確認」を除く)が一致するか確認する。
2. いくつかの値(数件)を画面で再確認し、Haikuの読み取りが正しかったか照合する。
3. 「要確認」店舗の一覧、使用した期間、合計値を添えて栗林さんに報告する。

## 参考ファイル

- `references/procedure.md` — フェーズAで確定させる、生成AI機能レポートへの正確な操作手順
  (期間指定の具体的なUI操作を含む)。**未確定のうちは`status: draft`のままにしておき、
  Haikuフェーズを始めない。**
- `data/genai-search-visibility-properties.json` — 店舗名 ↔ GSCプロパティURLの対応表。

## 並行セッション対策

他のセッションと並行している可能性がある間は、`SKILL.md`や`references/procedure.md`、
`data/genai-search-visibility-properties.json`を直接編集しない。学習・確認済み対応表の追記は
`learnings/<日時>_<セッションIDの先頭8桁>.md`に新規ファイルとして残す。手順・統合方法は
[`../hpb-salonboard-update/references/concurrent-sessions.md`](../hpb-salonboard-update/references/concurrent-sessions.md)
と同じ。
