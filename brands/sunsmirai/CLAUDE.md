# サンズミライ ブランドコンテキスト

このファイルはブランド「サンズミライ」専用の個別コンテキストです。ルートの
[CLAUDE.md](../../CLAUDE.md) に定義された全社共通ルールを前提とし、**このファイルの記述と
ルートCLAUDE.mdの記述が矛盾する場合は、常にルートCLAUDE.mdを優先する**。

内容は [docs/org-review-log.md](../../docs/org-review-log.md)(特に2026-09-02「院マスタの
構造確認とブランド『サンズミライ』18院の追加」)・`docs/backlog.md`・
`data/clinics.json`の該当エントリから実際に確認できた事実のみをまとめている。

## ブランド概要

- ブランド名: サンズミライ
- 院数: **18院**(法人「ミライ」9院・法人「サンズ」9院)。`data/clinics.json`の
  `brand: "サンズミライ"` と一致確認済み
- 業態: 整骨院・鍼灸接骨院(`type: "seikotsuin"`)
- エリア: **大阪府・滋賀県・和歌山県・京都府**(関西圏に限定)。同じ関西圏を含む
  「直営」ブランドとは法人体系・院マスタ上のタブが別で、統合は見送られている
  (`brands/chokuei/CLAUDE.md`参照)

## 法人体系

- **ミライ**(9院): 店名は「弁慶はりきゅう整骨院」が中心。エリアは大阪府河内長野市・
  堺市美原区・富田林市、滋賀県大津市、和歌山県和歌山市など
- **サンズ**(9院): 店名は「たいよう鍼灸整骨院」「あやめ鍼灸整骨院」「おかだ鍼灸整骨院」
  「河内いわふね駅前整骨院」「忍ヶ丘駅前整骨院」など。エリアは大阪府枚方市・交野市・
  高槻市・茨木市・四條畷市・大阪市城東区、京都府京田辺市など

## ドメイン・システム構成

- ウェブサイトはいずれも`chiryou-in.biz`系ドメイン(直営の一部院と同じ基盤)を利用
  (例: `https://chiryou-in.biz/kawachinagano/`)。一部の院は独自サブドメイン
  (`hiramatsu.chiryouin.biz`、`wakayama.chiryouin.biz`)を持つ

## 紐づく実務Skill・自動化

### 月次KPI集計自動化(直営と共有)

サンズミライは**直営と合算した約149〜150店舗分**の月次WEB集客KPI集計の対象。詳細・
サービスアカウント・工程進捗は[brands/chokuei/CLAUDE.md](../chokuei/CLAUDE.md)の
「3. 月次KPI集計自動化」および[functions/kpi-aggregation/CLAUDE.md](../../functions/kpi-aggregation/CLAUDE.md)
を参照(重複記載を避けるためここでは繰り返さない)。サービスアカウントは
`chokuei-sunsumirai-kpi-writer@keizgroup-automation.iam.gserviceaccount.com`。

### EPARK法人名マッピング

`data/epark-corporations.json`に、EPARK掲載店舗リストのB列(契約法人名)から
KPIシートの区分(直営/サンズ/ミライ)への対応表が切り出されている。サンズミライの
2社は以下の実際の契約法人名で登録されている(2026-09-03確定、KPIシートの手入力値と
完全一致):

| KPIシート上の区分 | EPARK契約法人名 |
|---|---|
| サンズ | 株式会社太洋メディカル(たいよう鍼灸整骨院 等)、株式会社サンズ |
| ミライ | 株式会社光井JAPAN(弁慶はりきゅう整骨院 等)、株式会社ミライ |

法人名は`data/clinics.json`の`corporation`(ミライ/サンズ)とは別の実際の登記法人名で
入っているため、部分一致による対応表が必要だった経緯がある。

### SalonBoard・HPB

`salonboard-operator`エージェント(ブランド非依存)がHPB対応する前提だが、サンズミライの
院が実際にSalonBoard/HPBの対象に含まれるかは、直営同様`data/clinics.json`側では未確定
(`brands/chokuei/CLAUDE.md`の「未確認事項」と同じ論点)。ただしKPIシートの「Epark店舗数
(ミライ/サンズ)」列は2026年8月時点でミライ8・サンズ8の実績が確認されている。

## 集客チャネル・データ連携の状況

- `data/clinics.json`のサンズミライ18院はいずれも`acquisition_channels`が空配列のまま
  (2026-09-03時点で未確認)
- Chatwork連携(`data/chatwork-rooms.json`)にサンズミライ専用のルームは登録されていない

## 既知の課題(未対応)

- `acquisition_channels`が全院で空
- サンズミライ専用のChatworkルーム未登録
- HPB利用院の確定リストが未作成(直営と同じ論点)

## 未確認事項

- GA4・Google Search Console等の分析ツール連携状況(現時点で連携の記録なし)
- サンズミライ単体(直営との合算ではなく)の集客数・UU数を直接読む経路は現状無い
  (KPIシート側が直営+サンズミライの合算値のみを扱う設計のため)
