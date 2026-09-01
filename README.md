# AI組織リポジトリ

K's Group(整骨院グループ、約149院)向けの「どのPCでも使えるAI組織」の本体リポジトリ。
Claude Codeのサブエージェント(役割)とSkill(定型業務)を組み合わせて、分析→実装→効果計測→
横断レビューのサイクルを回す。設計思想・運用ルールは [CLAUDE.md](CLAUDE.md) を参照。

## 構成

```
CLAUDE.md              全社共通ルール(組織憲章)
.claude/agents/         役割定義(analyst / implementer / measurer / cross-functional)
skills/README.md        実務Skill一覧・役割マッピング・移設手順
data/proposals/         施策案(analyst出力 → implementer実装ログ)
data/kpi-history/       KPI推移(measurer出力)
data/clinics.json       院マスタ
docs/org-review-log.md  組織レビュー・変更履歴
```

## 新しいPCでのセットアップ

1. このリポジトリをclone
2. `.claude/skills/` 配下のSkillが未移設の場合は [skills/README.md](skills/README.md) の
   手順に従って移設する
3. 必要な認証情報を環境変数として設定する(リポジトリにはコミットしない)

## 現状(2026-09-01時点)

初期スキャフォールドに加え、パイロットブランド「LUNA」の個別コンテキスト(`brands/luna/`)と、
実務Skill10件([skill-kanri](https://github.com/t-kuribayashi-keiz/skill-kanri)から移設、
`.claude/skills/`)を構築済み。全社共通のKPI定義はまだ空。
詳細は [docs/org-review-log.md](docs/org-review-log.md) を参照。
