# Chatwork送信キュー(outbox)

Claudeが送りたいChatworkメッセージを、1件1ファイル(`*.json`)としてここに置く。
`.github/workflows/chatwork-send.yml`が拾って投稿し、投稿済みファイルを削除する。

Claude自身はChatworkに投稿できない(トークンはGitHub Secretsにあり、GitHub Actions実行時に
しか渡らない)。この仕組みはその「送信側の橋渡し」であり、トークンがClaudeのコンテキストに
入らないという設計を保ったまま返信を可能にするためのもの。

## ファイル形式

ファイル名は `<ISO日時>-<内容がわかる短い英字>.json`(例: `2026-09-03T0930-relax-coupon.json`)。
送信順はファイル名順なので、日時を先頭に置く。

```json
{
  "room_name": "【WEBマーケ】ケイズ×リラックス",
  "kind": "hearing",
  "body": "着手にあたって3点確認させてください。\n1. 対象店舗はどちらでしょうか\n2. ...",
  "in_reply_to_message_id": "2147013845519302656",
  "issue": 12
}
```

| フィールド | 必須 | 内容 |
|---|---|---|
| `room_name` | ○ | `data/chatwork-rooms.json`にある名前と完全一致。かつそのルームに`allow_auto_hearing: true`が必要 |
| `kind` | ○ | 現在は`hearing`(不足情報のヒアリング)のみ送信可。それ以外はスクリプトが拒否する |
| `body` | ○ | 質問本文。1,500文字以内。「Claudeによる自動確認」というヘッダは送信時に自動で付くので本文に書かない |
| `in_reply_to_message_id` | | 元依頼メッセージのID(記録用) |
| `issue` | | 対応するGitHub Issue番号(記録用) |

## 送信できるもの・できないもの

**自動送信してよいのは「着手に必要な情報を集める質問」だけ**(2026-09-02に栗林さんと合意)。
対応の約束、完了報告、料金・方針などの経営判断、実作業そのものは含まれない。詳細と理由は
[.claude/skills/chatwork-integration/SKILL.md](../../.claude/skills/chatwork-integration/SKILL.md)
の非交渉ルールを参照。

質問は**1通にまとめる**。細切れに何通も送ると、依頼者のChatworkが自動メッセージで埋まる。
