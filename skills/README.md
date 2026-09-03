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
| `chatwork-integration` | Chatwork APIの読み書き(依頼検知の共通基盤、ブランド非依存) | 全役割の入口。検知後の実作業はsalonboard-operator / implementer等に引き渡す |
| `kpi-aggregation`(実体は`functions/kpi-aggregation/`) | 直営+サンズミライの月次集客KPI集計(Sheets API + GitHub Actions、Python) | implementer(自動化の保守) |

`kpi-aggregation`は`.claude/skills/`配下にSkillフォルダを新設せず、既存の
`functions/kpi-aggregation/CLAUDE.md`(実装は`scripts/kpi_aggregate.py`・
`scripts/store_matcher.py`・`.github/workflows/kpi-aggregate.yml`・`tests/`)をそのまま
実体として扱う例外。他のブランド横断の社内機能(`functions/receipt-agency/`、
`functions/recruiting/`、`functions/ad-spend-tracking/`)がCLAUDE.mdのみでSkill化されて
いないのと異なり、この機能は既に本番自動化として稼働しコード資産が`functions/`側に
育っているため、`.claude/skills/`への二重管理を避けてこの表への登録のみで整合を取る。

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
