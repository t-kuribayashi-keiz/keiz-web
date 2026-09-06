# learnings/

並行して動いているセッションが、気づいたことを**新規ファイルとして**置く場所。

`SKILL.md` や `references/*.md`(特に `reconciliation-logic.md`)を直接編集すると、
同時に走っている別セッションの編集と競合して**片方の学習が黙って消える**。
ファイルを分ければ衝突しようがない。

- 書き方・命名・統合手順: [../../hpb-salonboard-update/references/concurrent-sessions.md](../../hpb-salonboard-update/references/concurrent-sessions.md)
  (詳細手順はここが唯一の参照先。このSkill固有の差分はSKILL.mdのLogging節を参照)
- 作業ログの一時置き場は `hpb_crm_work_log.d/`(`hpb_work_log.d/` ではない。
  兄弟Skill `hpb-salonboard-update` の列構成と違うため、別名で分けている)
- **タスクを始める前にこのフォルダを読むこと。** 未統合でも、ここにある内容は既に有効な知見。

統合(ここの内容を`SKILL.md`/`references/`へ畳む作業)は、並行実行が終わったあとに
**1セッションだけ**が行う。
