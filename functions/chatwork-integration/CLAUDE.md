# Chatwork連携(ブランド横断の社内機能)

このファイルは、Chatwork経由で届く業務依頼(SalonBoard更新・HP修正など)を検知して対応に
つなげる仕組みについての個別コンテキストです。ルートの [CLAUDE.md](../../CLAUDE.md) に定義
された全社共通ルールを前提とし、矛盾する場合は常にルートCLAUDE.mdを優先する。

`functions/`配下に置いているのは、Chatworkが**特定の1ブランドに閉じたものではなく、複数
ブランドのやり取りに使われている共通の連絡基盤**であるため([functions/ad-spend-tracking/CLAUDE.md](../ad-spend-tracking/CLAUDE.md)
と同じ位置づけ)。ブランド固有の情報(どのルームがどのブランドか)は
[data/chatwork-rooms.json](../../data/chatwork-rooms.json)に切り出してある。

## 構成要素

| ファイル | 役割 |
|---|---|
| [.claude/skills/chatwork-integration/SKILL.md](../../.claude/skills/chatwork-integration/SKILL.md) | Chatwork APIの読み書き手順・非交渉ルール(ブランド非依存の共通レイヤー) |
| [.claude/skills/chatwork-integration/references/api-reference.md](../../.claude/skills/chatwork-integration/references/api-reference.md) | 使用エンドポイントの詳細、レート制限、Chatwork独自マークアップ |
| [data/chatwork-rooms.json](../../data/chatwork-rooms.json) | 監視対象ルームの設定(ルーム名・ブランド・検知キーワード) |
| [scripts/chatwork_watcher.py](../../scripts/chatwork_watcher.py) | ポーリング・粗い事前フィルタ・レポート生成 |
| [.github/workflows/chatwork-watcher.yml](../../.github/workflows/chatwork-watcher.yml) | 30分間隔のcron実行、検知時にGitHub Issueを起票 |
| `data/chatwork-watcher-state.json` | 各ルームの最終確認位置(ワークフローが自動更新・自動コミット。手で触らない) |

## 認証情報の置き場所

- **GitHub Secrets の `CHATWORK_API_TOKEN`**(リポジトリ`t-kuribayashi-keiz/keiz-web`)。
  2026-09-02に栗林さんが登録。
- トークンは栗林さん個人のChatworkアカウントのもの。よって**このトークンで投稿すると
  栗林さん本人の発言として表示される**。返信を送る場合は必ず本人の明示的な承認を取る
  (SKILL.mdの非交渉ルール4)。
- **クラウドClaudeセッションからはこのトークンを参照できない**(GitHub Secretsは
  GitHub Actionsの実行時にのみ環境変数として渡される)。これは制約ではなく設計意図で、
  トークンがClaudeのコンテキストに一切入らないことを保証している。そのため
  「セッションから直接Chatworkを読む」ことはできず、必ずワークフロー経由になる。
- 過去に一度、初期のトークンがチャット上に平文で貼られたため無効化・再発行済み
  (2026-09-02)。同じことが起きた場合も同様に即無効化する。

## 処理フロー

```
GitHub Actions (30分ごと)
  └─ scripts/chatwork_watcher.py
       ├─ data/chatwork-rooms.json の各ルームを名前でID解決
       ├─ 最新100件を取得し、前回位置より新しいものだけ対象に
       ├─ watch_keywords による粗い事前フィルタ
       └─ 該当ありならレポートを出力
  └─ GitHub Issue を起票(ラベル: chatwork-request)
       └─ Claudeがそれを読んで「本当に依頼か」を判断
            └─ PushNotification で栗林さんに実行可否を確認
                 └─ 承認後: SalonBoard案件はローカル環境の salonboard-operator、
                            HP/コード修正は implementer が着手
```

**キーワード判定とAI判断を分けているのが要点**。ワークフロー側は「依頼かもしれない」までしか
判断せず(LLMを使わないのでAPIキーもコストも不要)、実際の意図判断はブランド文脈を持つ
Claude側が行う。取りこぼしを防ぐためキーワードは広めに設定してあり、空振りのIssueが立つのは
許容コストとして扱う。

## 監視対象ルーム

現在の設定は[data/chatwork-rooms.json](../../data/chatwork-rooms.json)が正。2026-09-02時点では
**「【WEBマーケ】ケイズ×リラックス」(リラックスブランド)の1件のみ**。

他ブランドのルームを追加する場合は、同ファイルに1エントリ足すだけでよい(スクリプト・
ワークフローの変更は不要)。追加時は、トークンのアカウントがそのルームのメンバーであることを
必ず確認する — メンバーでないルームは`GET /rooms`に現れず、「ルームが見つかりません」として
Issueに報告される。

## 未確認・今後の検討事項

- 実際にIssueが起票されたときのClaude側の起動方法(GitHubイベント起点のRoutineを設定するか、
  栗林さんがIssueを見てセッションを開くか)は未確定。まずはIssue起票までを動かして、
  検知精度を見てから決める
- GitHub Actionsの実行時間(privateリポジトリでは消費対象)。30分間隔で月480分程度の見込み。
  プラン上限が厳しい場合は間隔を延ばす(ただし1回の取得上限が100件なので、日次まで延ばすと
  取りこぼしのリスクがある)
- Chatworkへの返信を自動化するかは未決。現状は「Claudeから栗林さんへ通知」までが設計範囲で、
  Chatworkへの返信投稿は都度承認を前提とする
