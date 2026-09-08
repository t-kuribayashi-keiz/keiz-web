# グラフ・レポート作成の共通ルール

複数ブランド・複数店舗のレポート(HTML集客レポート、KPIダッシュボード等)を作る際に
共通で守るルール。2026-09-07に栗林さんの指示で確定した([リラックス8月度レポート]
(brands/relax/CLAUDE.md)の作成時)。**新しくグラフやレポートを作るときはここを読む。**

## 1. 指標は「1店舗あたり」で表示・議論する

対象店舗数は月によって変わる(新規開店、閉店)。合計値(例:「新患数532名」)は店舗数が
変われば見かけ上増減するため、**合計ではなく1店舗あたりの平均で表示・議論する**。

- KPIタイル・チャート・本文中の言及は「1店舗あたり◯◯」を主にし、合計値は補足情報として
  添える程度に留める(例:「21.3名/店(全店合計532名 / 25店舗)」)
- 店舗ランキングなど、個別店舗の実数を扱うグラフ(=もともと1店舗単位)はこの限りではない
- 店舗数自体が月によって変わる場合は、その旨と実際の店舗数を明記する(推測で埋めない)

## 2. 時系列グラフは暦月(1〜12月)を横軸にし、年度を重ねて表示する

複数年にまたがる時系列データは、横軸を **1月〜12月の暦月に固定**し、**年度ごとに1本の
折れ線として重ねて**表示する(月を単純に連結した1本の時系列にしない)。季節性の比較を
可能にするため。

- **最新年は実線・強調**(通常の太さ・不透明度)
- **それ以前の年は点線・控えめ**(細め・低不透明度、`stroke-dasharray`)
- データが揃っていない月(まだ両年分が無い等)はそのまま欠落させる。無い月を補間・推測
  しない
- 凡例は「系列(自社/エリア平均など)の色」と「年度(実線/点線)の線種」を分けて示す
  (系列 × 年度の組み合わせを1つずつ凡例に並べると数が爆発するため)

## 実装例

以下は「2026年08月号」のような年月号ラベルの配列から、暦月(1〜12月)を横軸に年度ごとの
折れ線を重ねて描く実装の骨子(SVGを直接組み立てるHTML Artifact向け)。実際の初出は
2026年09月のリラックス8月度レポート(HTML Artifact、リポジトリ外)。

```js
// trend: [{month: "2026年08月号", pv_self: 1234, pv_area: 1500, ...}, ...]
const byYearMonth = {};
trend.forEach(d => {
  const m = /^(\d{4})年(\d{1,2})月号$/.exec(d.month);
  if (!m) return;
  const year = +m[1], month = +m[2];
  (byYearMonth[year] = byYearMonth[year] || {})[month] = d;
});
const years = Object.keys(byYearMonth).map(Number).sort((a, b) => a - b);
const latestYear = years[years.length - 1];
const months = Array.from({ length: 12 }, (_, i) => i + 1);

// 系列(例: 自社/エリア平均)ごとに、年ごとの折れ線を描く。
// 最新年 = 実線・太め・不透明、それ以前 = 点線・細め・低不透明度。
// データが無い月はパスを途切れさせる(補間しない)。
series.forEach(s => {
  years.forEach(yr => {
    const isLatest = yr === latestYear;
    const pts = months.map(mo => {
      const d = byYearMonth[yr] && byYearMonth[yr][mo];
      return (d && d[s.key] != null) ? [mo, d[s.key]] : null;
    });
    let path = '', drawing = false;
    pts.forEach(p => {
      if (!p) { drawing = false; return; }
      path += (drawing ? 'L' : 'M') + x(p[0]) + ',' + y(p[1]) + ' ';
      drawing = true;
    });
    const style = isLatest
      ? `stroke:${s.color};stroke-width:2.2;stroke-opacity:1`
      : `stroke:${s.color};stroke-width:1.4;stroke-opacity:0.5;stroke-dasharray:4 3`;
    // <path d="${path}" style="${style}"/> をSVGに追加
  });
});
```
