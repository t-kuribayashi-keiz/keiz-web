---
name: hpb-review-blog-check
description: Use this skill for the monthly「HPB口コミ・ブログチェック」作業 — 各院のHotPepper Beauty公開ページから対象月の口コミ投稿総数・★5口コミ数・口コミ返信数・ブログ数(写真ありのみ)を自動集計し、専用スプレッドシートのB〜F列に書き込む(完全自動入力、手動集計との照合は行わない)。Trigger on "口コミブログチェック表", "HPB口コミ・ブログチェック", "口コミとブログの集計", "前月分の口コミ・ブログを集計して", or requests to run/update the monthly review-and-blog count for HPB listings. Do NOT trigger for SalonBoard content edits (hpb-salonboard-update) or the public reservation-calendar ○✕チェック (hpb-reservation-slot-check) — this skill is specifically about counting 口コミ/ブログ activity, a different HPB public page section.
---

# 口コミ・ブログ集計チェック(hpb-review-blog-check)

「HPB口コミ・ブログチェック」(スプレッドシートID: `12gx_guSdsVToNn3fjA5fzujqrk7E4crs9UE6V9rJ71Y`)は、
各院のHotPepper Beauty上での月次の口コミ投稿総数・★5口コミ数・口コミ返信数・ブログ投稿数
(写真ありのみ)を自動集計するための専用シート。2026-09-07〜09にまず旧シート「口コミブログ
チェック表」(スプレッドシートID: `1cmYMBJb5do2MsdO43-RS2uD22vEbNJHoPYMZ3hvqEvA`、人手で
B〜D列に手動集計、G〜I列に自動集計を書き込んで突き合わせる方式)で構築・検証・自動化し、
2026-09-11に栗林さんが本Skill専用の新シート(旧シートのコピー)を用意して書き込み先を
切り替えた。**新シートはB〜F列の全てがAI入力という位置づけで、旧シートのような手動集計値
との照合運用ではない**(旧シートはそのまま残っているが、このSkillはもう触らない)。

## シートの列構成(対象月のタブ、例:「2609月分」の場合)

| 列 | 内容 |
|---|---|
| A | 院名 |
| B | 対象月(9月)のブログ数(写真ありのみ) |
| C | 対象月(9月)の口コミ投稿総数 |
| D | 対象月(9月)の★5口コミ数 |
| E | 前月(8月)の口コミ投稿総数 |
| F | 前月(8月)の口コミ返信数 |

E列は基本的に前月タブ(例:「2608月分」)自身のC列の値をそのままコピーする(前月分を
二重にスクレイピングしない)。前月タブや該当行が無い場合のみ、フォールバックとして
このスクリプトが直接スクレイピングした値を使う。**F列(口コミ返信数)はどの月のタブにも
「その月の返信数」を記録する列が存在せず前月タブからコピーできる元データが無いため、
毎月その場でHPBから直接スクレイピングする**(2026-09-11、栗林さんと合意)。

## 実体

- `scripts/hpb_review_blog_check.py` — Playwrightで各院のHPB公開ページ(口コミ一覧・
  月別ブログアーカイブ)を巡回し、対象月・前月の口コミ総数・★5数・返信数、対象月の
  写真ありブログ数を集計する。`--mode report`(既定、CSV出力のみ)と`--mode apply`
  (スプレッドシートのB〜F列に書き込み、`GCP_KPI_WRITER_KEY`環境変数が必要)がある。
  口コミ返信の有無は、口コミ本文に「〇〇からの返信コメント」ブロック(クラス名
  `.mT20.mH10.pV5.pH9.bdGray`)が挿入されているかどうかで判定する(2026-09-11、
  わかば整骨院の実データで確認済み)。
- `data/hpb-review-blog-ids.json` — 院名 → HotPepper Beauty店舗ID(storeId)の対応表。
  スクリプトはこれを読んで各院のURLを組み立てる。
- `scripts/notify_hpb_review_blog_check.py` — 実行結果をChatworkの送信キュー
  (`data/chatwork-outbox/`)に積む。実際の送信は`scripts/chatwork_send.py`が行う。
- `.github/workflows/hpb-review-blog-check.yml` — 毎月1日 10:00 JSTに自動実行する
  GitHub Actionsワークフロー(下記「自動化」参照)。

## 自動化(2026-09-09、GitHub Actionsで実装済み)

`.github/workflows/hpb-review-blog-check.yml` が毎月1日 10:00 JSTに自動実行し、前月分を
`--mode apply`で集計・書き込みしたうえで、成功・失敗いずれの場合もマイチャット(Chatwork)に
実行結果を通知する。これは「本当に毎月動いているか栗林さんが確認できるようにしたい」という
2026-09-09の要望に対応したもの。通知が来ない月があれば、cron自体が発火していない可能性を
真っ先に疑うこと(`.github/workflows/hpb-reservation-slot-check.yml`でも一度、毎時ちょうど
指定が原因で初回発火しなかった前例がある)。

**前提条件(未実施の場合は書き込みが失敗する):** 「HPB口コミ・ブログチェック」スプレッドシートを、
書き込み用サービスアカウント(`chokuei-sunsumirai-kpi-writer@keizgroup-automation.iam.gserviceaccount.com`、
`functions/kpi-aggregation`・`hpb-reservation-slot-check`と共用、新規の鍵作成は不要)に
**編集者として共有**しておく必要がある。共有手順: スプレッドシート右上の「共有」→上記の
メールアドレスを追加→権限「編集者」→送信。

**対象月のタブ(例: 「2609月分」)は基本的に栗林さんが手動で用意する運用。** 無い場合は
`ensure_tab_exists()`(`scripts/hpb_review_blog_check.py`)が**前月のタブを複製して自動作成**
するフォールバックが2026-09-09に入っている。複製後、B〜F列は全データ行(行3-36・40-170、
`DATA_ROW_RANGES`定数)で空にするが、**ヘッダー行の月表記(「8月」「7月」等の文言)は
前月のまま残る**ため、このフォールバックが発火した月はヘッダーの手動修正が必要になる
場合がある。前月のタブ自体が無い場合はこのフォールバックも使えず、通常通り失敗として
扱われる(手動でどちらかのタブを用意する必要がある)。`--tab`でタブ名を明示指定した場合
(テスト実行時など)はこのフォールバックは働かない(テスト用タブは呼び出し側が用意している
前提のため)。

手動で任意の月を再実行・確認したい場合は、GitHub Actionsの「HPB review/blog check (monthly)」
ワークフローを`workflow_dispatch`で手動実行できる(対象月・mode(apply/report)を指定可能)。
ローカルで直接実行する場合は以下(Chatwork通知は行われない):

```
python scripts/hpb_review_blog_check.py --month 202609 --mode report --out hpb_review_blog_202609.csv
```

出力CSVには対象月の口コミ総数・★5数・写真ありブログ数に加え、前月分の口コミ総数
(`prev_review_total_scraped`、通常は使われずE列は前月タブのC列から転記される)と
前月の返信数(`prev_review_reply`、F列に書き込まれる値)も含まれる。ローカルから直接
`--mode apply`で書き込む場合(サービスアカウントの鍵が使えない環境など)は
[references/sheet-write-back.md](references/sheet-write-back.md)のブラウザ経由の手順を
使うこと(旧シートでの手動照合運用を前提に書かれた部分があるため、新シート(B〜F列)に
適用する際は読み替えが必要)。

Chatworkの通知の仕組み自体(`kind: "status_report"`という新しい種別)の詳細は
[functions/chatwork-integration/CLAUDE.md](../../../functions/chatwork-integration/CLAUDE.md)
の「例外: 定期実行automationの『動いたかどうか』の事実報告」を参照。

## 院マスタ(data/hpb-review-blog-ids.json)の維持

2026-09-09時点で165院、全て決着済み。163院は個別のHPB店舗ページで直接計測できる。残り2院
(豊四季北口整骨院・郡山若葉町整体院)は「あはき柔整プラン」への完全切り替えにより独立した
店舗ページが無くなり、それぞれ豊四季北口鍼灸整骨院・郡山若葉町鍼灸接骨院(いずれも収録済み)
に統合されている(`merged_into_ahaki_sibling`参照。この2院の行は今後も空欄のままでよい —
統合先の院で計測済みのため)。新しく院が増えた場合や、未収録院を追加する場合は
未収録院を追加する場合は [references/id-matching-pitfalls.md](references/id-matching-pitfalls.md)
を必ず読むこと — 院名の表記ゆれ(整骨院/接骨院/整体院違い)を安易に突き合わせると、
**同じ拠点にある別の院に間違って同じ店舗IDを割り当ててしまう**(2026-09-07に実際に5院分
発生し、最終検証で発覚したが、2026-09-08にHPBジャンル検索で個別に正しい店舗IDを特定し
解決済み)。名前の一致だけで確信を持たず、必ずスクレイプ結果を手動集計値と突き合わせて
確認すること。

**「掲載エラー」= 恒久的な閉店とは限らない。** 池袋駅前整体院・新松戸クラシオン整体院・
クラシオン整体院MEGAドン・キホーテ長野高田の3院は、当初「掲載エラー」と判定していたが、
実際には**新しい店舗IDで再掲載されていた**(2026-09-08、栗林さんから正しいURLの提供を
受けて判明)。「掲載エラー」と確認した院は、店舗名でHPBジャンル検索(駅名×業種で絞り込み)
をかけて、同じ院名の別store_idが無いか確認する一手間を追加すること。

## スプレッドシートへの書き込み

現状はサービスアカウントを未設定のため、`claude-in-chrome`(利用者の実ブラウザ、ログイン
済み)でスプレッドシートを開き、Name Box(名前ボックス)でセル範囲を選択して値を
クリップボード経由で貼り付ける方法を使っている。**行番号の取得元によっては、実際の
シート行と2行分ズレる罠がある**(Google Sheets自体のバグではなく、`read_file_content`が
返すMarkdown変換に起因する。詳細は
[references/id-matching-pitfalls.md](references/id-matching-pitfalls.md) の1.5、
回避手順は[references/sheet-write-back.md](references/sheet-write-back.md) を必ず
参照すること)。これを見落として直接大きな範囲に貼り付けると、既存データを誤った位置に
上書きしてしまう(2026-09-07に実際に発生し、クリアしてやり直した)。値を流し込む前に
必ず1セルで対象行を目視確認してから本番の範囲貼り付けを行うこと。

## 担当役割

- **implementer**: スクリプト・院マスタ・GitHub Actionsワークフローの保守
- 月次の実行は自動化済み(cron)だが、**結果の確認(Chatwork通知を見る)は依頼ベース/
  栗林さん自身が行う**。異常時(取得エラーが多い、通知が来ない月がある等)の一次対応は
  implementerに引き継ぐ想定(`daily-ops-monitor`が担当する日次の予約枠チェックとは別サイクル
  — CLAUDE.mdの「施策のサイクル/運用のサイクル」の区別と同様、こちらは月次の
  「手動集計の代替」であって日次の異常検知ではない)

## 実績(2026-09-07〜08、初回実行)

163院分の8月(2026年)実績を集計し、手動集計と照合:
- 口コミ投稿総数・★5口コミ数: 手動データがある147院中ほぼ100%一致
  (「サロンPick Up」枠の見落としバグを1件修正後)
- ブログ数(写真ありのみ): 87%完全一致、残りは±1〜数件の小さな差
  (「写真あり」判定の主観的ブレ、または集計後に投稿が削除された等の実データ変化)

## 継続的な学習

このSkillを使う中で新しく分かったこと(院マスタの新しい落とし穴、書き込み時の新しい
不具合など)は、他のセッションと並行している可能性がある間は `SKILL.md` や
`references/*.md` を直接編集せず、`learnings/<日時>_<セッションIDの先頭8桁>.md` に
新規ファイルとして残すこと。手順は `hpb-salonboard-update/references/concurrent-sessions.md`
と同じ。
