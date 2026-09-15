---
name: llmo-gemini-survey
description: Use this skill whenever the user asks to run, extend, or automate the in-house Gemini API survey that measures how often each 整骨院/接骨院 store appears in Gemini's AI-search answers (LLMO/AI検索対策の一環) — e.g. "Gemini調査をまた回して", "ダッシュボードを更新して", "全店舗展開のシステムを直して", or requests to add stores to the survey. Also trigger when the user wants to push new survey results into the LLMO dashboard Artifact. Brand-agnostic mechanism (any 整骨院/接骨院 store can be added to config/stores.*.json), currently piloted on 10 直営 stores. Do NOT use this for x3d社のChatGPT調査そのもの(外部委託分。参照のみ)や、SEO/MEO順位取得(GRC・MEOチェキは別契約・別ツール)。
---

# LLMO Gemini調査 & ダッシュボード

Gemini API(検索グラウンディング)を使って「AIが各店舗をどれだけ検索結果に出すか」を
月次で計測し、[ダッシュボードArtifact](https://claude.ai/code/artifact/79c438e1-8131-4220-9ec4-0733933a336d)に反映する仕組み。
2026年9月にx3d社のChatGPT調査を自社で再現する形でパイロット構築し、直営10店舗・291応答で検証済み。

背景・全社ルールは `CLAUDE.md` の「業務フロー」「複数セッションの同時実行」を参照。
この調査自体はanalyst相当の定点観測作業に近いが、専用Skillとして独立させている
(Gemini API呼び出し・パース・ダッシュボード反映という技術的に固有な工程が多いため)。

## 現在の状態(2026年9月9日時点)

対策対象10店舗については、ユーザーの指示で「一旦この10店舗でシステムを完成させる」方針に確定。
全店舗(153店舗)への展開は、この10店舗の運用が安定してから改めて着手する(下記「全店舗展開する場合の前提作業」参照)。

- **10店舗の調査パイプライン・ダッシュボード連携は動作確認済み**(`config/stores.pilot.json`)
- **月次トリガーは設定済み**(`trig_019qPkAeJFi26a7X9QVSB3XY`、毎月1日06:00 UTC=15:00 JST、このセッションを起こす形)。
  `db` への書き込みはArtifactツール(=Claudeセッション)経由でしかできない仕様のため、GAS/cronで完結する
  自動化はできず、この「トリガーがセッションを起こしてSkillの手順を実行する」形が現実的な自動化経路
- **唯一の残タスク: `GEMINI_API_KEY` をこの実行環境のシークレットとして登録すること。**
  未設定の間、月次トリガーは「キーが無い」と報告して調査をスキップするだけで、エラーにはならない。
  ユーザーがAI Studioで発行したキーを環境のシークレット設定に登録すれば、次回の月次実行から
  自動で回り始める(環境変数の設定方法は https://code.claude.com/docs/en/claude-code-on-the-web 参照)
- **AI Studioの月次利用上限を¥500以上に。** 10店舗の月次実行は300回・実測概算¥315。
  以前¥350に設定した記録があるが、バッファを見て¥500程度に上げておくことを推奨(429で一部店舗が
  未取得になるのを避けるため)

## 費用

実測 **約¥1.05/回**(理論値の2.1倍。原因未特定)。詳細・無料枠・前払い方式の注意点は
`references/cost-notes.md` を必ず読むこと。**月次利用上限を¥0にすると全リクエストが失敗する**
(検証済みの既知の罠)。

## 標準ワークフロー

1. **店舗設定を確認。** `config/stores.pilot.json`(10店舗)を使うか、新しい店舗を追加する場合は
   同じ形式(`kind`/`place`/`match`)で新規configファイルを作る。`match` は応答文中の自店舗検出用の
   部分一致キーワード(表記ゆれ対応で複数指定可)
2. **`GEMINI_API_KEY` を確認。** セッションの環境変数にあるか、無ければユーザーに聞く。
   AI Studioの月次利用上限が非ゼロに設定されているか、想定コスト(店舗数×30回×¥1.05)が
   その上限に収まるかを事前に伝える
3. **調査実行**: `python3 scripts/run_survey.py --stores config/stores.pilot.json --out results/`
   (既存の `results/<店舗>.json` があれば未取得分だけ追加取得する。429で打ち切られても再実行で続きから取れる)
4. **順位パース**: `python3 scripts/parse_all.py --stores config/stores.pilot.json --results results/`
5. **ダッシュボード用ペイロード生成**: `python3 scripts/aggregate_for_dashboard.py --stores config/stores.pilot.json --results results/ --round YYYY-MM --ranks <SEO/MEO順位JSON> --out dashboard_payload.json`
   (`--ranks` は省略可。SEO/MEO順位はGRC/MEOチェキから別途取得したものをJSON化して渡す)
6. **ダッシュボードへ反映**: `references/dashboard-schema.md` の手順どおり、Artifactツールの
   `write_db`(`db_op: batch`)で `config/master`・`rounds/<round>`・`summary/latest` を書き込む
7. **反映確認**: `read_db` で1件読み戻し、ダッシュボードURLを開いて表示を確認

## 全店舗展開する場合の前提作業(10店舗の運用が安定してから着手)

1. `data/clinics.json` の対象店舗(直営135＋サンズミライ18)に「検索地域名」「駅近/ロードサイド区分」を
   追記する、または別途マッピングファイルを作る(これが無いとプロンプトが組み立てられない)
2. AI Studioの月次利用上限を、対象店舗数に応じて引き上げる(153店舗・毎月なら¥8,000程度を推奨。
   統合レポートの「全店舗展開のAPI費用」セクション参照)
3. 1回あたりの実行時間を実測し、GASの6分制限に当たるかを確認(`references/cost-notes.md` 参照)
4. 既存の月次トリガー(`trig_019qPkAeJFi26a7X9QVSB3XY`)を `update_trigger` で153店舗用configを
   使うプロンプトに差し替える、または新規トリガーを追加する

## 関連ドキュメント

- 統合レポート(分析結果の全体像): https://claude.ai/code/artifact/c2c85a2b-2a5c-4897-8178-086a02d1dd0b
- ダッシュボード: https://claude.ai/code/artifact/79c438e1-8131-4220-9ec4-0733933a336d
- `references/dashboard-schema.md` — DBスキーマと反映手順
- `references/cost-notes.md` — 単価・無料枠・前払い方式の注意点
