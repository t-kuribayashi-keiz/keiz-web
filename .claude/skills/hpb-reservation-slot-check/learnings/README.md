# learnings/

並行して動いているセッションが、気づいたことを**新規ファイルとして**置く場所。

`SKILL.md`・`references/known-bugs.md`・`references/colab-editing-gotchas.md` を直接編集すると、
同時に走っている別セッション(例: 週次M/N確認と、別の人によるK/Lデバッグが重なる場合)の
編集と競合して**片方の学習が黙って消える**。ファイルを分ければ衝突しようがない。

- 書き方・命名・統合手順: [../../hpb-salonboard-update/references/concurrent-sessions.md](../../hpb-salonboard-update/references/concurrent-sessions.md)
  (詳細手順はここが唯一の参照先。このSkillは対象ファイルが`known-bugs.md`/
  `colab-editing-gotchas.md`である点だけが違う)
- **タスクを始める前にこのフォルダを読むこと。** 未統合でも、ここにある内容は既に有効な知見。

統合(ここの内容を`SKILL.md`/`references/`へ畳む作業)は、並行実行が終わったあとに
**1セッションだけ**が行う。
