# 実務Skill一覧・役割マッピング

現時点で実際に稼働している実務Skillは、このPC上ではユーザーレベル
(`C:\Users\81904\.claude\skills\`)に置かれている。**このリポジトリをclaudeし他のPCで使うには、
下記のSkillフォルダをこのリポジトリの `.claude/skills/` にコピーし、認証情報を環境変数化して
からコミットする必要がある(詳細は下部「移設手順」参照)。**

## 役割マッピング

| Skill | 主担当業務 | 対応する役割(agent) |
|---|---|---|
| `hpb-salonboard-update` | SalonBoardのクーポン・掲載情報更新 | implementer(定型実装・更新作業) |
| `hpb-crm-reconciliation` | CRM×HotPepper Beauty来店データの突合ロジック(GAS) | implementer / analyst(判定ロジック改善時) |
| `karte-demographics-chart` | カルテデータから男女比・年代構成グラフを作成 | analyst(分析・可視化) |
| `shift-schedule-gas-automation` | スタッフのシフト/公休入力の自動化(GAS) | implementer |
| `dji-mic-auto-upload` | DJI Micの録音データをGoogle Driveへ自動アップロード | implementer(業務基盤) |
| `gdrive-store-staff-folders` | Google Driveの店舗・スタッフフォルダ管理(GAS) | implementer(業務基盤) |
| `org-structure-artifact` | 組織図・役割分担ドキュメントの作成/更新 | cross-functional(組織設計そのもの) |
| `org-structure-table` | 組織体制表(役割×法人のマトリクス表)の作成/更新 | cross-functional |
| `customer-acquisition-consulting` | 集客のデータパイプライン・分析自動化 | analyst |
| `session-to-skill` | 今の会話の作業手順をSkill化する | cross-functional(型化・再利用の判断) |

## 移設手順(このPC上のSkillをリポジトリに取り込む場合)

1. 対象フォルダを `.claude/skills/<skill-name>/` にコピーする
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
