#!/usr/bin/env python3
"""グッド・スマイル 集客レポート(単一HTML Artifact)のジェネレータ。

使い方:
    python3 scripts/good_smile_report_gen.py [--data data/good-smile-report-data.json] [--out /tmp/.../good-smile-report.html]

このスクリプト自体は「型」(HTML構造・CSS・チャート描画JS)の置き場所。当月の実データは
コミットしない(--dataで渡すJSONを都度更新する。既定値はdata/good-smile-report-data.json
だが、月次更新時は新しいdictをこのスクリプトの外で組み立てて渡すか、そのファイルを直接
書き換えてから実行する)。データの取得元・スキーマ・毎月の作業手順は
.claude/skills/good-smile-monthly-report/SKILL.md を参照。

このスクリプトが埋め込むJS(renderMultiEntityChart・renderYearChart・layoutLabels等)は
docs/chart-conventions.md の共通方針(1店舗あたり表示・暦月×年度重ね・前月/前年同月ラベル)
を満たす実装のリファレンスでもある。他ブランドのレポートで同種のグラフが必要になったら、
ここのJSをコピーして使ってよい。
"""
import argparse
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=os.path.join(REPO_ROOT, "data", "good-smile-report-data.json"),
                 help="レポートに埋め込むデータJSON(既定: data/good-smile-report-data.json)")
ap.add_argument("--out", default="/tmp/good-smile-report.html",
                 help="出力先HTMLパス(既定: /tmp/good-smile-report.html。Artifact公開前提のため"
                      "実際にはセッションのscratchpad配下を指定することが多い)")
args = ap.parse_args()

with open(args.data, encoding="utf-8") as f:
    DATA_JSON = json.dumps(json.load(f), ensure_ascii=False, separators=(",", ":"))

HTML = """<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1"><style>:root{color-scheme:light}body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#faf9f5;color:#141413}img{max-width:100%}</style></head><body>
<title>グッド・スマイル 集客レポート</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700;900&family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#faf8f3; --surface:#ffffff; --surface-2:#f2ede3; --ink:#242019; --muted:#7c7566;
  --line:#e7e0d2; --smile:#2a78d6; --smile-soft:#e1ecf9; --good:#eb6834; --good-soft:#fbe6db;
  --chokuei:#1baf7a; --chokuei-soft:#dcf3ea;
  --meta-ad:#8a5cd6; --meta-ad-soft:#ece3fa;
  --gray-fill:#c8c0ac; --gray-fill-soft:#efeadf;
  --pos:#1baf7a; --pos-soft:#dcf3ea; --neg:#e34948; --neg-soft:#fbe1e0;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#171410; --surface:#221e17; --surface-2:#2a251c; --ink:#f2ede2; --muted:#a89e8a;
    --line:#3a3327; --smile:#5b9ce8; --smile-soft:#20344f; --good:#f08659; --good-soft:#3f2a1c;
    --chokuei:#4fbf7f; --chokuei-soft:#1c3226;
    --meta-ad:#b494e3; --meta-ad-soft:#332a44;
    --gray-fill:#5c5240; --gray-fill-soft:#2c281f;
    --pos:#4fbf7f; --pos-soft:#1c3226; --neg:#e97a7a; --neg-soft:#3a201f;
  }
}
:root[data-theme="dark"]{
  --bg:#171410; --surface:#221e17; --surface-2:#2a251c; --ink:#f2ede2; --muted:#a89e8a;
  --line:#3a3327; --smile:#5b9ce8; --smile-soft:#20344f; --good:#f08659; --good-soft:#3f2a1c;
  --chokuei:#4fbf7f; --chokuei-soft:#1c3226;
  --meta-ad:#b494e3; --meta-ad-soft:#332a44;
  --gray-fill:#5c5240; --gray-fill-soft:#2c281f;
  --pos:#4fbf7f; --pos-soft:#1c3226; --neg:#e97a7a; --neg-soft:#3a201f;
}
:root[data-theme="light"]{
  --bg:#faf8f3; --surface:#ffffff; --surface-2:#f2ede3; --ink:#242019; --muted:#7c7566;
  --line:#e7e0d2; --smile:#2a78d6; --smile-soft:#e1ecf9; --good:#eb6834; --good-soft:#fbe6db;
  --chokuei:#1baf7a; --chokuei-soft:#dcf3ea;
  --meta-ad:#8a5cd6; --meta-ad-soft:#ece3fa;
  --gray-fill:#c8c0ac; --gray-fill-soft:#efeadf;
  --pos:#1baf7a; --pos-soft:#dcf3ea; --neg:#e34948; --neg-soft:#fbe1e0;
}
*,*::before,*::after{box-sizing:border-box;}
body{margin:0; background:var(--bg); color:var(--ink); font-family:'Noto Sans JP',sans-serif; line-height:1.75; font-feature-settings:"palt" 1;}
h1,h2,h3{font-family:'Zen Kaku Gothic New',sans-serif; font-weight:700; text-wrap:balance; margin:0;}
.num{font-variant-numeric:tabular-nums;}
.wrap{max-width:1040px; margin:0 auto; padding:44px 24px 96px;}

.report-head{border-bottom:1px solid var(--line); padding-bottom:26px; margin-bottom:32px;}
.eyebrow{font-size:.76rem; letter-spacing:.2em; color:var(--muted); text-transform:uppercase; margin:0 0 10px;}
.report-head h1{font-size:clamp(1.5rem,3.2vw,2rem); margin:0 0 12px;}
.meta-row{display:flex; flex-wrap:wrap; gap:6px 22px; font-size:.85rem; color:var(--muted);}
.meta-row b{color:var(--ink); font-weight:600;}
.brand-tag{display:inline-flex; align-items:center; gap:5px; font-size:.72rem; padding:2px 8px 2px 6px; border-radius:999px; font-weight:600; white-space:nowrap;}
.brand-tag i{width:7px; height:7px; border-radius:50%; display:inline-block;}
.brand-tag.smile{background:var(--smile-soft); color:var(--smile);} .brand-tag.smile i{background:var(--smile);}
.brand-tag.good{background:var(--good-soft); color:var(--good);} .brand-tag.good i{background:var(--good);}

section.block{margin-bottom:42px;}
section.block.is-hidden{display:none;}
.sec-label{display:flex; align-items:baseline; gap:10px; margin-bottom:14px;}
.sec-label h2{font-size:1.12rem;}
.sec-label .sec-note{color:var(--muted); font-size:.8rem;}

.kpi-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px;}
.kpi{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:15px 17px;}
.kpi .label{font-size:.74rem; color:var(--muted); margin-bottom:7px;}
.kpi .value{font-family:ui-monospace,'SF Mono',Menlo,monospace; font-size:1.42rem; font-weight:600;}
.kpi .sub{font-size:.74rem; color:var(--muted); margin-top:3px;}

.callout{background:var(--surface-2); border:1px solid var(--line); border-radius:10px; padding:16px 19px; font-size:.85rem; color:var(--muted);}
.callout h3{font-size:.86rem; color:var(--ink); margin:0 0 8px; font-family:'Zen Kaku Gothic New',sans-serif; font-weight:700;}
.callout ul{margin:0; padding-left:1.15em;} .callout li{margin-bottom:5px;}
.callout b{color:var(--ink);}

.tbl-scroll{overflow-x:auto; border:1px solid var(--line); border-radius:10px;}
table{width:100%; border-collapse:collapse; background:var(--surface); font-size:.83rem; min-width:600px;}
th,td{padding:8px 12px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap;}
th:first-child,td:first-child{text-align:left; position:sticky; left:0; background:var(--surface);}
thead th{background:var(--surface-2); font-weight:600; color:var(--muted); font-size:.72rem; letter-spacing:.02em;}
tbody tr:last-child td{border-bottom:none;}
td.rank1{font-weight:700;} td.rank-bad{color:var(--muted);}

.trend-tbl table{min-width:420px;}
.trend-tbl td.trend-total,.trend-tbl th.trend-total{font-weight:700;}
.trend-tbl tr.total-row td{background:var(--surface-2);}
.mom{display:inline-block; padding:1px 7px; border-radius:999px; font-size:.76rem; font-weight:600; font-variant-numeric:tabular-nums;}
.mom.down{background:var(--pos-soft); color:var(--pos);}
.mom.up{background:var(--neg-soft); color:var(--neg);}
.mom.flat{background:var(--surface-2); color:var(--muted);}
.trend-na{font-size:.8rem; color:var(--muted); margin:0 0 8px;}
.trend-caption{font-size:.76rem; color:var(--muted); padding:8px 12px 0;}

.bars{display:flex; flex-direction:column; gap:9px;}
.bar-row{display:grid; grid-template-columns:26px 190px 1fr 100px; align-items:center; gap:8px; font-size:.8rem;}
.bar-row .name{color:var(--ink); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.brand-dot{width:9px; height:9px; border-radius:50%; justify-self:center;}
.brand-dot.smile{background:var(--smile);} .brand-dot.good{background:var(--good);}
.bar-track{height:22px; background:var(--surface-2); border-radius:5px; overflow:hidden; display:flex; border:1px solid var(--line);}
.bar-seg{height:100%;}
.bar-val{font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums; text-align:right; color:var(--muted); font-size:.78rem;}
.bar-legend{display:flex; flex-wrap:wrap; gap:16px; font-size:.76rem; color:var(--muted); margin:2px 0 12px;}
.bar-legend .item{display:flex; align-items:center; gap:6px;}
.bar-legend .sw{width:10px; height:10px; border-radius:3px;}
.bar-legend .sw.dot{border-radius:50%;}

.chart-block{margin-bottom:26px;}
.chart-title{font-size:.92rem; font-weight:600; margin:0 0 2px;}
.chart-sub{font-size:.78rem; color:var(--muted); margin:0 0 10px;}
.chart-wrap{position:relative; background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:12px 10px 4px;}
.chart-svg{display:block; width:100%; height:auto; overflow:visible;}
.chart-svg .grid-line{stroke:var(--line); stroke-width:1;}
.chart-svg .axis-label{fill:var(--muted); font-size:10px; font-family:ui-monospace,monospace;}
.chart-svg .end-label{font-size:10.5px; font-weight:600; font-family:ui-monospace,monospace;}
.chart-svg .end-label.compare{font-size:9.5px; font-weight:500; opacity:.82;}
.chart-svg .series-line{fill:none; stroke-width:2.3px; stroke-linecap:round; stroke-linejoin:round;}
.chart-svg .series-line.y2025{stroke-dasharray:4 4; opacity:.62;}
.chart-svg .series-dot{stroke:var(--surface); stroke-width:1.4px;}
.chart-legend{display:flex; flex-wrap:wrap; gap:8px 16px; padding:0 4px 10px; font-size:.76rem; color:var(--muted);}
.chart-legend .item{display:flex; align-items:center; gap:6px;}
.legend-line{width:16px; height:2px;}

.idx-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px;}
.idx-card{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:13px 15px;}
.idx-card .store{font-size:.82rem; font-weight:600; margin-bottom:6px;}
.idx-card .idx-head{font-size:.72rem; color:var(--muted); margin-bottom:6px;}
.idx-row{display:flex; justify-content:space-between; gap:8px; font-size:.78rem; padding:3px 0; white-space:nowrap;}
.idx-row .idxval{font-family:ui-monospace,monospace; font-weight:600; flex:none;}
.idx-row .idxval.low{color:var(--neg);} .idx-row .idxval.ok{color:var(--pos);}

.month-brief{margin-top:14px; display:flex; flex-direction:column; gap:9px;}
.brief-row{font-size:.85rem; display:flex; gap:10px; align-items:baseline; color:var(--ink);}
.brief-row .tag{flex:none; font-size:.7rem; font-weight:700; padding:2px 9px; border-radius:999px; white-space:nowrap;}
.brief-row.good .tag{background:var(--pos-soft); color:var(--pos);}
.brief-row.bad .tag{background:var(--neg-soft); color:var(--neg);}
.brief-row.next .tag{background:var(--surface-2); color:var(--muted);}

.insight{background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:20px 22px; font-size:.87rem;}
.insight h4{font-size:.92rem; margin:0 0 8px; font-family:'Zen Kaku Gothic New',sans-serif; font-weight:700;}
.insight h4.top{color:var(--neg);}
.insight h4:not(:first-child){margin-top:20px;}
.insight p{margin:0 0 10px; color:var(--ink);}
.insight ul,.insight ol{margin:0 0 10px; padding-left:1.3em; color:var(--ink);}
.insight li{margin-bottom:5px;}
.insight .data-gap{background:var(--surface-2); border-radius:8px; padding:12px 16px; font-size:.82rem; color:var(--muted); margin-top:12px;}
.insight .data-gap b{color:var(--ink);}
.insight b{color:var(--ink);}

footer{border-top:1px solid var(--line); padding-top:20px; font-size:.77rem; color:var(--muted); text-align:center;}
@media (max-width:640px){ .wrap{padding:30px 16px 72px;} .bar-row{grid-template-columns:18px 112px 1fr 70px;} }
</style>

<div class="wrap">
  <div class="report-head">
    <p class="eyebrow">Monthly Acquisition Report</p>
    <h1>グッド・スマイル 集客レポート</h1>
    <div class="meta-row">
      <span>対象: <b>2026年1〜8月</b>(9月は進行中のため信憑性の観点で対象外)</span>
      <span>作成日: <b>2026年09月08日</b></span>
      <span><span class="brand-tag smile"><i></i>スマイル 11院</span></span>
      <span><span class="brand-tag good"><i></i>グッド 7院</span></span>
    </div>
  </div>

  <section class="block">
    <div class="sec-label"><h2>2026年8月サマリー</h2></div>
    <p class="chart-title" style="margin-top:2px;"><span class="brand-tag good"><i></i>グッド</span></p>
    <div class="kpi-grid" id="kpi-grid-good"></div>
    <div class="month-brief">
      <div class="brief-row good"><span class="tag">好調</span><span>HPB経由 1院あたり10.9→13.7件(前年同月比<b>+25.7%</b>)</span></div>
      <div class="brief-row bad"><span class="tag">課題</span><span>MEO(3位外KWの店舗数)が7月10院→8月17院へ急悪化。特に府中整体院はGoogleビジネスプロフィールのエリア表記が「天神川」のまま残っており、この表記のKW4/5が圏外</span></div>
      <div class="brief-row next"><span class="tag">9月の対策</span><span>府中整体院のエリア表記修正・NAP整合性確認を最優先。悪化が府中固有かエリア全体かの切り分けも9月中に行う</span></div>
    </div>
    <p class="chart-title" style="margin-top:18px;"><span class="brand-tag smile"><i></i>スマイル</span></p>
    <div class="kpi-grid" id="kpi-grid-smile"></div>
    <div class="month-brief">
      <div class="brief-row good"><span class="tag">好調</span><span>HPBリボンのCVR(興味喚起率)49.82%→66.16%(前年同月比<b>+32.8%</b>)。Google PPC広告もCV/院が前年同月2.3→8月4.1に改善</span></div>
      <div class="brief-row bad"><span class="tag">課題</span><span>HPBリボンのACR(予約到達率)4.42%→1.88%(前年同月比<b>-57.5%</b>)。見てもらえて興味も持たれているのに予約に至らない構造。MEO(3位外KWの店舗数)も7月24院→8月33院へ急悪化</span></div>
      <div class="brief-row next"><span class="tag">9月の対策</span><span>HPB掲載5院の予約枠(K/L)稼働状況を最優先で確認(ACR急落の一次仮説検証)。MEO悪化が9月以降も続くか追跡</span></div>
    </div>
  </section>

  <section class="block is-hidden">
    <div class="sec-label"><h2>集客数(新患数)の推移</h2><span class="sec-note">1〜8月・1院あたり・ブランド別</span></div>
    <p class="chart-sub">グッド・スマイルそれぞれの1院あたり平均と、直営(関西7院)平均を並べて表示(合算はしていない)。</p>
    <div class="chart-legend">
      <span class="item"><span class="legend-line" style="background:var(--good)"></span>グッド(1院あたり)</span>
      <span class="item"><span class="legend-line" style="background:var(--smile)"></span>スマイル(1院あたり)</span>
      <span class="item"><span class="legend-line" style="background:var(--chokuei)"></span>直営 関西7院平均(1院あたり)</span>
    </div>
    <div class="chart-wrap"><div id="chart-acquisition" class="chart-svg-host"></div></div>
  </section>

  <section class="block">
    <div class="sec-label"><h2>チャネル別集客数・自然検索の推移</h2><span class="sec-note">グッド・スマイル・直営(関西参考)・1院あたり・実線=2026年・点線=2025年</span></div>
    <p class="chart-sub">「グッド・スマイル月次報告」シート「集計用 （栗林）」タブより。集客数(新患数)チャネル別の月次値で、上のCRM基準の集客数時系列とはソースが異なる(一致しない場合がある)。自然検索UU・CVRは2025年5月分・直営は自然検索CVRのみ2026年6月分までしか値が無く、無理に埋めていない。</p>
    <div class="chart-legend">
      <span class="item"><span class="legend-line" style="background:var(--good)"></span>グッド</span>
      <span class="item"><span class="legend-line" style="background:var(--smile)"></span>スマイル</span>
      <span class="item"><span class="legend-line" style="background:var(--chokuei)"></span>直営(関西参考)</span>
      <span class="item"><span class="legend-line" style="background:var(--muted);opacity:.6;border-top:2px dashed var(--muted)"></span>点線=2025年・実線=2026年</span>
    </div>
    <div class="chart-block">
      <p class="chart-title">HP経由</p>
      <div class="chart-wrap"><div id="chart-ch-hp" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">HPB経由</p>
      <div class="chart-wrap"><div id="chart-ch-hpb" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">オフライン経由</p>
      <div class="chart-wrap"><div id="chart-ch-offline" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">自然検索UU</p>
      <div class="chart-wrap"><div id="chart-ch-uu" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">HP CVR</p>
      <div class="chart-wrap"><div id="chart-ch-cvr" class="chart-svg-host"></div></div>
    </div>
  </section>

  <section class="block">
    <div class="sec-label"><h2>店舗別 新患数(CRM基準・HP/HPB内訳)</h2><span class="sec-note">8月・HP+HPB合算で降順・ブランド別</span></div>
    <div class="bar-legend">
      <span class="item"><span class="sw" style="background:var(--gray-fill)"></span>HP経由</span>
      <span class="item"><span class="sw" style="background:var(--good)"></span>HPB経由(バー色はブランド色と同一系統)</span>
    </div>
    <p class="chart-title"><span class="brand-tag good"><i></i>グッド</span></p>
    <div class="bars" id="bars-good"></div>
    <p class="chart-title" style="margin-top:16px;"><span class="brand-tag smile"><i></i>スマイル</span></p>
    <div class="bars" id="bars-smile"></div>
  </section>

  <section class="block">
    <div class="sec-label"><h2>スマイル: 広告実績(Google/META)の推移</h2><span class="sec-note">1院あたり・横軸1〜12月・実線=2026年・点線=2025年(Googleのみ)・広告代理店(株式会社五箱)運用スプレッドシートより</span></div>
    <p class="chart-sub">上の「店舗別 新患数」のHP経由には、この広告経由の流入(および自然検索・直接流入等)が合算されている。広告単体の実績は下記のとおり(HP経由新患数と単純に対応づけられる数値ではない)。実施院数はシート「担当院数」行の実測値で月ごとに割っている(Google: 13院[2025年6月〜2026年4月]→11院[2026年5月〜、閉院済みのうりわり院・はつしば院を除いた実質稼働数]。META: 2院[2026年6月]→5院[2026年7月〜]。2025年4-5月は担当院数が未記録のためグラフから除外・補間していない)。</p>
    <div class="chart-legend">
      <span class="item"><span class="legend-line" style="background:var(--smile)"></span>Google PPC</span>
      <span class="item"><span class="legend-line" style="background:var(--meta-ad)"></span>META(2026年6月〜)</span>
      <span class="item"><span class="legend-line" style="background:var(--muted);opacity:.6;border-top:2px dashed var(--muted)"></span>点線=2025年・実線=2026年(Googleのみ)</span>
    </div>
    <div class="chart-block">
      <p class="chart-title">広告費(1院あたり)</p>
      <div class="chart-wrap"><div id="chart-ad-spend" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">CV(1院あたり)</p>
      <div class="chart-wrap"><div id="chart-ad-cv" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">CPA(広告費÷CV)</p>
      <div class="chart-wrap"><div id="chart-ad-cpa" class="chart-svg-host"></div></div>
    </div>

    <div class="callout">
      <h3>仮説: Pmax(P-MAX)広告の学習効果とCV増加の関係(2026-09-10・要検証)</h3>
      <ul>
        <li><b>栗林さんの仮説</b>: 2026年からCVが伸びているのはP-max広告の開始によるもので、機械学習の最適化に半年ほどかかるため、開始から半年後の8月頃から成果が伸びてきたのではないか。直営もP-maxを2025年から導入済みで、現在CPAが¥4.1万前後で安定推移しており、スマイルもその水準に「追いついてきた」段階では、という見立て</li>
        <li><b>裏付け(このシートには検索広告・Pmax広告の内訳タブが別途あり、今回初めて分離して確認した)</b>: Pmax広告費は2025年12月に小規模開始(¥116,523)、2026年2〜3月に本格スケール(月¥30〜47万)、以降8月まで月¥37〜45万で推移。<b>PmaxのCPAは開始月の¥38,841から段階的に下がり、2026年8月に¥11,041(観測期間中の最良値)</b>。学習が進むほど効率化するという仮説の形とよく一致する</li>
        <li><b>留保点</b>: 同時期、Pmaxではない検索広告単体のCPAも、ほぼ同じタイミング(2026年4月前後)で¥25,642→¥9,162へ急改善しており、Pmax固有の効果だけでは説明しきれない可能性がある。Pmaxの蓄積データが同一アカウント内の検索広告の自動入札にも波及した可能性(Google広告の仕組み上あり得る)と、Pmaxとは別に4月前後にアカウント側で何か変更があった可能性の両方が考えられ、切り分けはできていない</li>
        <li><b>今後の検証方法</b>: 9月以降もPmax・検索広告双方のCPAが同水準で高止まりするかを継続確認する。2026年4月前後にアカウント設定(入札戦略・コンバージョン計測方法等)に変更が無かったかを広告代理店(株式会社五箱)に確認できると、Pmax固有の効果かアカウント全体の変化かを切り分けられる</li>
      </ul>
    </div>
  </section>

  <section class="block">
    <div class="sec-label"><h2>HPBリボン: PV・CVR・ACRの推移</h2><span class="sec-note">スマイル HPB掲載5院平均・横軸1〜12月・実線=2026年・点線=2025年(8月まで)</span></div>
    <div class="chart-legend">
      <span class="item"><span class="legend-line" style="background:var(--smile)"></span>自社</span>
      <span class="item"><span class="legend-line" style="background:var(--gray-fill)"></span>エリア平均</span>
      <span class="item"><span class="legend-line" style="background:var(--muted);opacity:.6;border-top:2px dashed var(--muted)"></span>点線=2025年・実線=2026年</span>
    </div>
    <div class="chart-block">
      <p class="chart-title">PV(露出)</p>
      <div class="chart-wrap"><div id="chart-pv" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">CVR(興味喚起率)</p>
      <div class="chart-wrap"><div id="chart-cvr" class="chart-svg-host"></div></div>
    </div>
    <div class="chart-block">
      <p class="chart-title">ACR(予約到達率)</p>
      <div class="chart-wrap"><div id="chart-acr" class="chart-svg-host"></div></div>
    </div>
  </section>

  <section class="block">
    <div class="sec-label"><h2>HPB掲載5院 比較(2026年08月・対エリア平均指数)</h2></div>
    <div class="idx-grid" id="idx-cards"></div>
  </section>

  <section class="block">
    <div class="sec-label"><h2>SEO順位</h2><span class="sec-note">取得時点スナップショット。3位以内は太字。ブランド別</span></div>
    <p class="chart-title"><span class="brand-tag good"><i></i>グッド</span></p>
    <p class="trend-na" id="seo-trend-good-note"></p>
    <div class="tbl-scroll trend-tbl" id="seo-trend-good"></div>
    <div class="tbl-scroll" style="margin-top:10px;" id="seo-table-good"></div>
    <p class="chart-title" style="margin-top:16px;"><span class="brand-tag smile"><i></i>スマイル</span></p>
    <p class="trend-na" id="seo-trend-smile-note"></p>
    <div class="tbl-scroll trend-tbl" id="seo-trend-smile"></div>
    <div class="tbl-scroll" style="margin-top:10px;" id="seo-table-smile"></div>
  </section>
  <section class="block">
    <div class="sec-label"><h2>MEO順位</h2><span class="sec-note">取得時点スナップショット。ブランド別</span></div>
    <p class="chart-title"><span class="brand-tag good"><i></i>グッド</span></p>
    <p class="trend-na" id="meo-trend-good-note"></p>
    <div class="tbl-scroll trend-tbl" id="meo-trend-good"></div>
    <div class="tbl-scroll" style="margin-top:10px;" id="meo-table-good"></div>
    <p class="chart-title" style="margin-top:16px;"><span class="brand-tag smile"><i></i>スマイル</span></p>
    <p class="trend-na" id="meo-trend-smile-note"></p>
    <div class="tbl-scroll trend-tbl" id="meo-trend-smile"></div>
    <div class="tbl-scroll" style="margin-top:10px;" id="meo-table-smile"></div>
  </section>

  <section class="block">
    <div class="sec-label"><h2>ボトルネック診断・示唆出し</h2><span class="sec-note">2026年8月号・前年同月比評価・グッド/スマイル マーケティング参謀エージェント作成</span></div>
    <p class="chart-title"><span class="brand-tag good"><i></i>グッド</span></p>
    <div class="insight">
      <h4 class="top">最大のボトルネック: MEOの急激な悪化(8月に+7店舗、全キーワードで一律悪化)</h4>
      <p>4〜7月は横ばいだったMEO(3位外店舗数)が8月だけ急変(10→17)しており、単月での急変は評価アルゴリズムやプロフィール設定側の変化を疑う根拠になる。特に<b>府中整体院</b>はGoogleビジネスプロフィール上のエリアラベルが「天神川」のままになっており、この「天神川」表記の5KW中4つが圏外という個別要因が判明している。府中1店舗の異常が全体の悪化(+7店舗)のうちどの程度を占めるか切り分けが必要。SEOは横ばいのためMEOと分離して評価すべき(検索エンジンのオーガニック順位ではなく、マップ表示側だけが悪化している=ローカル要因の可能性が高い)。</p>
      <h4>次点: HP経由のわずかな減少(-9.3%)</h4>
      <p>HP経由新患数は1院あたり4.3→3.9件(-9.3%)。HPB経由は+25.7%と好調なため合計への影響は限定的だが、自社WEBサイト経由の集客が伸びていない点は継続監視したい。</p>
      <h4>仮説と検証方法(いずれも仮説・要検証)</h4>
      <ul>
        <li>MEO悪化: 府中/天神川のNAP不整合(店舗名・エリア表記の不一致)が主因の可能性。Googleビジネスプロフィールの管理画面で直近の編集履歴・口コミ増減・カテゴリ設定を確認すれば検証できる</li>
        <li>HP経由減少: サイトの自然検索UUはほぼ横ばい(-0.2%)のため、流入自体より着地後のCVR側に課題がある可能性。自然検索CVRの8月分データで検証したい</li>
      </ul>
      <h4>次のアクション(優先順位順)</h4>
      <ol>
        <li>府中整体院のGoogleビジネスプロフィールのエリア表記を「天神川」から「府中」に修正し、NAP(店舗名・住所・電話番号)の整合性を確認する</li>
        <li>広告費スプレッドシート(Google PPC・META)へのアクセス権を栗林さんに共有依頼し、広告出稿有無・実額とHP経由の連動を確認する</li>
        <li>HPBリボンデータ(PV/CVR/ACR、口コミ数・評点、予約枠)の取得経路を確立する。現状HPB経由が唯一の増加チャネルであり伸び代の特定に必須だが、グッドは未着のまま</li>
        <li>自然検索CVRの8月分を取得し、UU横ばい(-0.2%)の裏でCVRが動いていないか確認する</li>
      </ol>
      <div class="data-gap"><b>まだ手元にないデータ(確認済み・未取得。今回は数値を作っていない)</b>: HPBリボン(PV/CVR/ACR)・口コミ数・評点・予約枠(K/L)指標はグッド未着。Google PPC・META広告の実績はサービスアカウントが該当シートへのアクセス権を持たず未取得。自然検索CVRの2026年8月分は欠損。GA4上のSEO/MEO流入とCVRの相関データは未取得。府中/天神川のMEO圏外化の根本原因は未特定。<br><b>対象外</b>: オフライン経由は自社コントロール外のチャネルのため、季節傾向把握の参考値として扱い、ボトルネック診断の対象外としている(参考: 前年同月比-38.8%)。</div>
    </div>

    <p class="chart-title" style="margin-top:22px;"><span class="brand-tag smile"><i></i>スマイル</span></p>
    <div class="insight">
      <h4 class="top">最大のボトルネック: HPBリボンのACR(予約到達率)急落</h4>
      <p>前年同月比で最も深刻なのは<b>ACR(予約到達率)</b>。4.42%→1.88%(<b>-57.5%</b>)。エリア平均も9.52%→7.66%(-19.5%)と下がっているが、自社の下落幅はその約3倍で、市場要因では説明できない自社固有の問題と判定できる。特に見過ごせないのは、同じ指標群のCVR(興味喚起率)が49.82%→66.16%(+32.8%、エリア平均+5.6%を大きく上回る伸び)と好調な点。<b>見てもらえて興味も持たれているのに、予約に至らない</b>という、ファネルの一番出口側で機会損失している構造がうかがえる。露出(PV)やMEO順位をいくら改善しても、この出口が壊れたままでは新患数に反映されない。HPB経由新患数(9.0→5.8、-35.6%)の下落幅もPV減(-12.4%)だけでは説明しきれず、ACR急落との重なりが実態に近いと見る。</p>
      <h4>次点: MEO(3位外店舗数)の急悪化</h4>
      <p>4→7月は20→9と改善傾向だったが、8月に33へ急悪化(整骨院・整体・肩こりの3KWが揃って悪化)。8月単月の変動である可能性も残るため、9月以降の継続性を要確認とする。HP経由の急伸(+132.7%)は、広告出稿がHP経由に合算されている可能性が高い。下記「広告実績」セクションで内訳を確認したところ、2026年に入ってGoogle広告(特にPmax)のCV・CPAが大きく改善しており、この広告効果がHP経由急伸の主因である可能性が高いと見ている(ただし内訳データ・CRM上のHP経由新患数を単純対応づけできる関係ではないため、引き続き参考情報の域を出ない)。</p>
      <h4>原因仮説(推測・要検証)</h4>
      <ul>
        <li>ACR急落: (a)予約枠(K/L)の空き不足・時間帯閉塞で興味を持ったユーザーが離脱、(b)HPB予約導線の表示崩れ、(c)口コミ評点・件数の悪化によるページ内離脱。(a)は予約枠稼働状況、(c)は口コミ推移データが無いと検証できない</li>
        <li>MEO急悪化: (a)Googleビジネスプロフィールの投稿頻度低下、(b)競合の強化、(c)口コミ件数・評点の伸び悩み。GA4のMEO流入UU/CVRとの相関確認が必要</li>
        <li>HP経由急伸: 広告実績(下記セクション参照)を確認した結果、Pmax広告のCPAが開始月(2025年12月・¥38,841)から2026年8月(¥11,041)まで一貫して改善しており、広告効果によるものと見て矛盾しない。ただし同時期、Pmaxではない検索広告のCPAも同様に改善しており、Pmax固有の学習効果かアカウント全体の変化かは切り分けられていない(仮説の詳細は下記「広告実績」セクションの記載を参照)</li>
      </ul>
      <h4>次のアクション(優先順位順)</h4>
      <ol>
        <li>HPB掲載5院の予約枠(K/L)稼働状況を今月中に確認(ACR急落の一次仮説検証)</li>
        <li>HPB口コミ数・評点の推移データ取得の運用立ち上げ</li>
        <li>Pmax広告のCPA改善が9月以降も続くか、検索広告のCPAと合わせて継続確認する(下記「広告実績」セクションのPmax仮説の検証)</li>
        <li>MEO順位悪化(整骨院・整体・肩こり)が9月以降も継続するか追跡</li>
        <li>自然検索CVRの8月分取得、GA4でSEO/MEO流入の実UU/CVRと順位変動の相関を確認</li>
      </ol>
      <div class="data-gap"><b>まだ手元にないデータ(確認済みの事実)</b>: HPB口コミ数・評点の推移、予約枠(K/L)稼働状況、自然検索CVR(8月分)、GA4のSEO/MEO流入UU/CVRはいずれも今回未取得。推測値では埋めていない。Google PPC(検索/Pmax内訳)・META広告の実績は今回取得済み(下記「広告実績」セクション参照)。</div>
    </div>
  </section>

  <div class="callout" style="margin-bottom:36px;">
    <h3>このレポートで扱っているデータと、扱っていないデータ</h3>
    <ul>
      <li><b>ブランドは合算しない</b>: グッドとスマイルは別ブランドでサービス内容・ブランディングが異なるため、KPI・時系列・店舗一覧・チャネル表・SEO/MEO表のすべてをブランドごとに分けて表示する(2026-09-09栗林さん指示、<a href="https://github.com/t-kuribayashi-keiz/keiz-web/blob/main/docs/chart-conventions.md">docs/chart-conventions.md</a>に今後の共通方針として記録済み)。1つのレポートに両ブランドを並べて比較することはあるが、数値を合成した「グッド+スマイル合計/平均」は作らない</li>
      <li><b>新患数(CRM基準)</b>: 「集患媒体集計」CRMの月次・チャネル別新患数(集計値のみ、個人情報は含まない)</li>
      <li><b>HPBリボン(PV/CVR/ACR)</b>: HPB掲載店のリボンデータ。<b>スマイル11院中5院分のみ</b>(なかもず・さかいし・ながよし・六甲道・甲南山手)。残り6院はHPB非掲載のため存在しない(異常ではない)。<b>グッドのリボンデータは未着</b></li>
      <li><b>直営(関西)</b>: 「HPB_145店舗_KPI一括集計結果」Masterから、関西圏(大阪・兵庫・京都・奈良・滋賀・和歌山)の直営7院(北山駅前接骨院はMaster未収載のため対象外)の集客数を比較用に参照。<b>整骨院という業態は同じだが、ブランド・立地・運用年数が異なるため単純比較はできない</b>参考値</li>
      <li><b>9月データは除外</b>: 月の途中で信憑性が低いため、集客数の時系列・HPBリボンとも2026年8月号までとした</li>
      <li><b>含まれていないもの</b>: 「グッド・スマイル月次報告」シート側のHPB速報値(8月タブのHPBブロック2つ問題で栗林さんの目視確認待ち)。上記CRM基準の新患数は別ソースであり数値が一致しない場合がある</li>
      <li>SEO/MEO順位は直近の取得時点スナップショット(月次推移ではない)</li>
    </ul>
  </div>

  <footer>
    データソース: 「集患媒体集計」CRM(集計値)・HPBリボンデータ(スマイル5院)・SEO/MEO順位シート・
    「HPB_145店舗_KPI一括集計結果」Master(直営関西7院の参考値)・院マスタ(data/clinics.json)<br>
    グッド・スマイル マーケティング参謀エージェント(smile-marketing-strategist / good-marketing-strategist)
  </footer>
</div>

<script id="report-data" type="application/json">__DATA_JSON__</script>
<script>
(function(){
  var DATA = JSON.parse(document.getElementById('report-data').textContent);
  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs){ var e = document.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function cssVar(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  // ---- shared end-label layout: creates the <text> elements, measures their REAL
  // rendered width via getBBox() (a guessed char-width was found to be unreliable -
  // ui-monospaceが無い環境ではフォールバックフォントの実測幅が想定と違うため、必ず実測する),
  // then resolves overlaps by actual bounding-box collision (x重なり かつ y近接、の両方を見る。
  // 別の月=別のx位置のラベルはy座標が近くても重ならないため)。
  function layoutLabels(svg, endLabels){
    var boxes = endLabels.map(function(lb){
      var t = el('text',{x:lb.x,y:lb.y+3.5,class:'end-label'+(lb.compare?' compare':''),fill:lb.color,'text-anchor':lb.anchor||'start'});
      t.textContent = lb.text;
      svg.appendChild(t);
      var b = t.getBBox();
      return {el:t, y: lb.y, x0: b.x - 2, x1: b.x + b.width + 2};
    });
    boxes.sort(function(a,b){ return a.y - b.y; });
    var placed = [];
    boxes.forEach(function(box){
      var moved = true;
      while (moved){
        moved = false;
        for (var i=0;i<placed.length;i++){
          var p = placed[i];
          var xOverlap = box.x0 < p.x1 && box.x1 > p.x0;
          var yOverlap = Math.abs(box.y - p.y) < 13;
          if (xOverlap && yOverlap){ box.y = p.y + 13; moved = true; }
        }
      }
      placed.push(box);
    });
    boxes.forEach(function(box){ box.el.setAttribute('y', box.y + 3.5); });
  }

  // ---- KPI tiles (per brand) ----
  function renderKpi(hostId, c){
    var host = document.getElementById(hostId);
    host.innerHTML =
      '<div class="kpi"><div class="label">新患数合計(CRM基準・'+c.n_stores+'院)</div><div class="value num">'+c.aug_total+'</div><div class="sub">1院あたり '+c.per_store_total+'件</div></div>' +
      '<div class="kpi"><div class="label">うちHPB経由(CRM基準)</div><div class="value num">'+c.aug_hpb+'</div><div class="sub">1院あたり '+c.per_store_hpb+'件・構成比'+Math.round(c.aug_hpb/c.aug_total*1000)/10+'%</div></div>';
  }
  renderKpi('kpi-grid-good', DATA.good);
  renderKpi('kpi-grid-smile', DATA.smile);

  // ---- store bars (per brand, HP+HPB only) ----
  function renderBars(hostId, bars, accentVar){
    var host = document.getElementById(hostId);
    var accent = cssVar(accentVar);
    var gray = cssVar('--gray-fill');
    var max = Math.max.apply(null, bars.map(function(b){ return b.hp + b.hpb; })) || 1;
    host.innerHTML = '';
    bars.forEach(function(b){
      var total = b.hp + b.hpb;
      var row = document.createElement('div'); row.className = 'bar-row';
      var dot = document.createElement('span'); dot.className = 'brand-dot'; dot.style.background = accent;
      var name = document.createElement('div'); name.className = 'name'; name.textContent = b.name; name.title = b.name;
      var track = document.createElement('div'); track.className = 'bar-track';
      var segHp = document.createElement('div'); segHp.className = 'bar-seg'; segHp.style.width = (b.hp/max*100) + '%'; segHp.style.background = gray;
      var segHpb = document.createElement('div'); segHpb.className = 'bar-seg'; segHpb.style.width = (b.hpb/max*100) + '%'; segHpb.style.background = accent;
      track.appendChild(segHp); track.appendChild(segHpb);
      var val = document.createElement('div'); val.className = 'bar-val'; val.textContent = 'HP '+b.hp+' / HPB '+b.hpb;
      row.appendChild(dot); row.appendChild(name); row.appendChild(track); row.appendChild(val);
      host.appendChild(row);
    });
  }
  renderBars('bars-good', DATA.good.bars, '--good');
  renderBars('bars-smile', DATA.smile.bars, '--smile');


  // ---- calendar-month / year-overlay line chart (ribbon) ----
  function monthNum(label){ var m = label.match(/(\\d{1,2})月/); return m ? parseInt(m[1],10) : null; }
  function yearOf(label){ var m = label.match(/(\\d{4})年/); return m ? parseInt(m[1],10) : null; }

  function renderYearChart(hostId, seriesData, fields, opts){
    var host = document.getElementById(hostId);
    if (!host) return;
    var byField = {};
    fields.forEach(function(f){
      var byYear = {};
      seriesData.forEach(function(pt){
        if (!pt) return;
        var y = yearOf(pt.month), m = monthNum(pt.month);
        if (!y || !m) return;
        (byYear[y] = byYear[y] || {})[m] = pt[f.field];
      });
      byField[f.field] = byYear;
    });
    var years = [];
    fields.forEach(function(f){ Object.keys(byField[f.field]).forEach(function(y){ y=Number(y); if (years.indexOf(y)===-1) years.push(y); }); });
    years.sort();
    var W = 640, H = 190, marginL = 40, marginR = 54, marginT = 14, marginB = 24;
    var innerW = W - marginL - marginR, innerH = H - marginT - marginB;
    var allVals = [];
    fields.forEach(function(f){ years.forEach(function(y){ for (var m=1;m<=12;m++){ var v=(byField[f.field][y]||{})[m]; if (v!=null) allVals.push(v); } }); });
    var maxV = Math.max.apply(null, allVals) * 1.15;
    var minV = opts.yMin != null ? opts.yMin : 0;
    function xAt(m){ return marginL + innerW * (m-1) / 11; }
    function yAt(v){ var t = (v-minV)/(maxV-minV); return marginT + innerH - t*innerH; }
    var svg = el('svg', {viewBox:'0 0 '+W+' '+H, class:'chart-svg'});
    host.innerHTML = ''; host.appendChild(svg);
    var gridCount = 4;
    for (var g=0; g<=gridCount; g++){
      var gv = minV + (maxV-minV)*g/gridCount;
      var gy = yAt(gv);
      svg.appendChild(el('line',{x1:marginL,x2:marginL+innerW,y1:gy,y2:gy,class:'grid-line'}));
      var lbl = el('text',{x:marginL-6,y:gy+3,class:'axis-label','text-anchor':'end'});
      lbl.textContent = opts.yFormat ? opts.yFormat(gv) : Math.round(gv);
      svg.appendChild(lbl);
    }
    for (var m=1;m<=12;m+=1){
      var lbl2 = el('text',{x:xAt(m),y:H-6,class:'axis-label','text-anchor':'middle'});
      lbl2.textContent = m+'月';
      svg.appendChild(lbl2);
    }
    var latestYear = years[years.length-1];
    var endLabels = [];
    fields.forEach(function(f){
      var byYear = byField[f.field];
      // 前月・前年同月に数字ラベルを付けるため、当月(latestYearの最終月)を先に特定しておく
      var latestMonths = [];
      for (var lm=1;lm<=12;lm++){ if ((byYear[latestYear]||{})[lm]!=null) latestMonths.push(lm); }
      var lastMonth = latestMonths.length ? latestMonths[latestMonths.length-1] : null;
      var prevMonth = lastMonth ? lastMonth - 1 : null;
      years.forEach(function(y){
        var pts = [];
        for (var m=1;m<=12;m++){ if ((byYear[y]||{})[m]!=null) pts.push([m, byYear[y][m]]); }
        if (pts.length === 0) return;
        var isLatest = (y === latestYear);
        if (pts.length < 2) { pts.forEach(function(p){ svg.appendChild(el('circle',{cx:xAt(p[0]),cy:yAt(p[1]),r:3.6,class:'series-dot',fill:f.color})); }); return; }
        var d = pts.map(function(p,i){ return (i===0?'M':'L')+xAt(p[0]).toFixed(1)+' '+yAt(p[1]).toFixed(1); }).join(' ');
        var path = el('path',{d:d, class:'series-line'+(isLatest?'':' y2025'), stroke: f.color});
        svg.appendChild(path);
        pts.forEach(function(p){ svg.appendChild(el('circle',{cx:xAt(p[0]),cy:yAt(p[1]),r:isLatest?3.4:2.6,class:'series-dot',fill:f.color})); });
        function fmt(v){ return opts.yFormat ? opts.yFormat(v) : v; }
        if (isLatest){
          // 当月(最新値)
          var lastPt = pts[pts.length-1];
          endLabels.push({x:xAt(lastPt[0])+7, y:yAt(lastPt[1]), color:f.color, text:fmt(lastPt[1])});
          // 前月比較用: 直前月の値
          if (prevMonth){
            var pmPt = pts.filter(function(p){ return p[0] === prevMonth; })[0];
            if (pmPt) endLabels.push({x:xAt(pmPt[0]), y:yAt(pmPt[1])-9, color:f.color, text:fmt(pmPt[1]), anchor:'middle', compare:true});
          }
        } else if (y === latestYear - 1 && lastMonth){
          // 前年同月比較用: 前年の同じ月の値
          var pyPt = pts.filter(function(p){ return p[0] === lastMonth; })[0];
          if (pyPt) endLabels.push({x:xAt(pyPt[0]), y:yAt(pyPt[1])-9, color:f.color, text:fmt(pyPt[1]), anchor:'middle', compare:true});
        }
      });
    });
    layoutLabels(svg, endLabels);
  }

  // ---- multi-entity (good/smile/chokuei) year-overlay chart: fixed calendar-month x-axis,
  // each entity may have y2025/y2026 point arrays of [month, value] with different month ranges ----
  function renderMultiEntityChart(hostId, entities, opts){
    var host = document.getElementById(hostId);
    if (!host) return;
    var W = 640, H = 200, marginL = 42, marginR = 46, marginT = 14, marginB = 24;
    var innerW = W - marginL - marginR, innerH = H - marginT - marginB;
    var allVals = [];
    entities.forEach(function(e){
      (e.y2025||[]).concat(e.y2026||[]).forEach(function(p){ allVals.push(p[1]); });
    });
    var maxV = Math.max.apply(null, allVals) * 1.18;
    var minV = 0;
    function xAt(m){ return marginL + innerW * (m-1) / 11; }
    function yAt(v){ var t = (v-minV)/(maxV-minV); return marginT + innerH - t*innerH; }
    var svg = el('svg', {viewBox:'0 0 '+W+' '+H, class:'chart-svg'});
    var gridCount = 4;
    host.innerHTML = ''; host.appendChild(svg);
    for (var g=0; g<=gridCount; g++){
      var gv = minV + (maxV-minV)*g/gridCount;
      var gy = yAt(gv);
      svg.appendChild(el('line',{x1:marginL,x2:marginL+innerW,y1:gy,y2:gy,class:'grid-line'}));
      var lbl = el('text',{x:marginL-6,y:gy+3,class:'axis-label','text-anchor':'end'});
      lbl.textContent = opts.yFormat ? opts.yFormat(gv) : Math.round(gv);
      svg.appendChild(lbl);
    }
    for (var m=1;m<=12;m++){
      var lbl2 = el('text',{x:xAt(m),y:H-6,class:'axis-label','text-anchor':'middle'});
      lbl2.textContent = m+'月';
      svg.appendChild(lbl2);
    }
    var maxLatestMonth = Math.max.apply(null, entities.map(function(e){
      var pts = e.y2026 || []; return pts.length ? pts[pts.length-1][0] : 0;
    }));
    var endLabels = [];
    function drawOne(pts, color, isLatest){
      if (!pts || pts.length === 0) return;
      var d = pts.map(function(p,i){ return (i===0?'M':'L')+xAt(p[0]).toFixed(1)+' '+yAt(p[1]).toFixed(1); }).join(' ');
      svg.appendChild(el('path', {d:d, class:'series-line'+(isLatest?'':' y2025'), stroke:color}));
      pts.forEach(function(p){ svg.appendChild(el('circle', {cx:xAt(p[0]), cy:yAt(p[1]), r:isLatest?3.2:2.4, class:'series-dot', fill:color})); });
      if (isLatest){
        var last = pts[pts.length-1];
        // a series ending before the others would otherwise label right on top of their
        // still-continuing lines; label it above its point instead of beside it.
        var endsEarly = last[0] < maxLatestMonth;
        endLabels.push({
          x: xAt(last[0]) + (endsEarly ? -4 : 7),
          y: yAt(last[1]) + (endsEarly ? -11 : 0),
          color:color, text:opts.yFormat?opts.yFormat(last[1]):last[1]
        });
      }
    }
    entities.forEach(function(e){
      var color = cssVar(e.color);
      drawOne(e.y2025, color, false);
      drawOne(e.y2026, color, true);
      // 前月・前年同月に数字ラベルを付ける(前年比・前月比が主な見方のため)
      var y2026 = e.y2026 || [], y2025 = e.y2025 || [];
      var lastMonth = y2026.length ? y2026[y2026.length-1][0] : null;
      if (lastMonth){
        var pm = y2026.filter(function(p){ return p[0] === lastMonth - 1; })[0];
        if (pm) endLabels.push({x:xAt(pm[0]), y:yAt(pm[1])-9, color:color, text:opts.yFormat?opts.yFormat(pm[1]):pm[1], anchor:'middle', compare:true});
        var py = y2025.filter(function(p){ return p[0] === lastMonth; })[0];
        if (py) endLabels.push({x:xAt(py[0]), y:yAt(py[1])-9, color:color, text:opts.yFormat?opts.yFormat(py[1]):py[1], anchor:'middle', compare:true});
      }
    });
    layoutLabels(svg, endLabels);
  }

  (function(){
    var ENTITIES = [
      {key:'good', color:'--good'},
      {key:'smile', color:'--smile'},
      {key:'chokuei', color:'--chokuei'}
    ];
    function build(metric){
      return ENTITIES.map(function(e){
        var d = DATA.channels[metric][e.key] || {};
        return {color:e.color, y2025:d.y2025||[], y2026:d.y2026||[]};
      });
    }
    var intFmt = function(v){ return Math.round(v*10)/10; };
    var pctFmt = function(v){ return (Math.round(v*10)/10)+'%'; };
    renderMultiEntityChart('chart-ch-hp', build('hp'), {yFormat:intFmt});
    renderMultiEntityChart('chart-ch-hpb', build('hpb'), {yFormat:intFmt});
    renderMultiEntityChart('chart-ch-offline', build('offline'), {yFormat:intFmt});
    renderMultiEntityChart('chart-ch-uu', build('organic_uu'), {yFormat:intFmt});
    renderMultiEntityChart('chart-ch-cvr', build('organic_cvr'), {yFormat:pctFmt});
  })();

  // ---- スマイル: Google PPC / META広告 実績の推移(11院合計。METAは2026年のみ) ----
  (function(){
    var ad = DATA.smile.ad || {};
    var yenFmt = function(v){ return '¥'+Math.round(v).toLocaleString('ja-JP'); };
    var cvFmt = function(v){ return Math.round(v*10)/10; };
    function entity(color, series){ var d = series || {}; return {color:color, y2025:d.y2025||[], y2026:d.y2026||[]}; }
    // CPA(広告獲得単価) = 広告費 ÷ CV。月ごとに広告費とCVの両方が揃っている点だけ計算する
    // (店舗数で割った1店舗あたりの値でも比率は変わらないため、合計値同士の比でよい)。
    function cpaSeries(spend, cv){
      var s = spend || {}, c = cv || {};
      function ratioYear(sPts, cPts){
        var cByMonth = {}; (cPts||[]).forEach(function(p){ cByMonth[p[0]] = p[1]; });
        return (sPts||[]).map(function(p){
          var cv = cByMonth[p[0]];
          return (cv != null && cv > 0) ? [p[0], p[1]/cv] : null;
        }).filter(function(p){ return p; });
      }
      return { y2025: ratioYear(s.y2025, c.y2025), y2026: ratioYear(s.y2026, c.y2026) };
    }
    renderMultiEntityChart('chart-ad-spend', [
      entity('--smile', ad.google_spend),
      entity('--meta-ad', ad.meta_spend)
    ], {yFormat:yenFmt});
    renderMultiEntityChart('chart-ad-cv', [
      entity('--smile', ad.google_cv),
      entity('--meta-ad', ad.meta_cv)
    ], {yFormat:cvFmt});
    renderMultiEntityChart('chart-ad-cpa', [
      entity('--smile', cpaSeries(ad.google_spend, ad.google_cv)),
      entity('--meta-ad', cpaSeries(ad.meta_spend, ad.meta_cv))
    ], {yFormat:yenFmt});
  })();

  var smileColor = cssVar('--smile');
  var areaColor = cssVar('--gray-fill');
  var selfAreaFields = function(selfField, areaField){
    return [{field:selfField, color:smileColor}, {field:areaField, color:areaColor}];
  };
  renderYearChart('chart-pv', DATA.smile.ribbon_avg_series, selfAreaFields('pv_self','pv_area'), {yFormat:function(v){return Math.round(v);}});
  renderYearChart('chart-cvr', DATA.smile.ribbon_avg_series, selfAreaFields('cvr_self','cvr_area'), {yFormat:function(v){return Math.round(v)+'%';}});
  renderYearChart('chart-acr', DATA.smile.ribbon_avg_series, selfAreaFields('acr_self','acr_area'), {yFormat:function(v){return v.toFixed(1)+'%';}});

  // ---- acquisition-count time series (3 lines: good, smile, chokuei-kansai; months 1-8, single year) ----
  (function(){
    var host = document.getElementById('chart-acquisition');
    var W = 640, H = 220, marginL = 44, marginR = 46, marginT = 16, marginB = 26;
    var innerW = W - marginL - marginR, innerH = H - marginT - marginB;
    var months = DATA.crm_months; // [1..8]
    var series = [
      {data: DATA.good.month_series, color: cssVar('--good')},
      {data: DATA.smile.month_series, color: cssVar('--smile')},
      {data: DATA.chokuei_kansai.month_series, color: cssVar('--chokuei')}
    ];
    var allVals = [];
    series.forEach(function(s){ s.data.forEach(function(p){ if (p) allVals.push(p.per_store); }); });
    var maxV = Math.max.apply(null, allVals) * 1.2;
    var minV = 0;
    function xAt(i){ return marginL + innerW * i / (months.length - 1); }
    function yAt(v){ var t = (v - minV) / (maxV - minV); return marginT + innerH - t * innerH; }
    var svg = el('svg', {viewBox:'0 0 '+W+' '+H, class:'chart-svg'});
    var gridCount = 4;
    for (var g = 0; g <= gridCount; g++){
    host.innerHTML = ''; host.appendChild(svg);
      var gv = minV + (maxV - minV) * g / gridCount;
      var gy = yAt(gv);
      svg.appendChild(el('line', {x1:marginL, x2:marginL+innerW, y1:gy, y2:gy, class:'grid-line'}));
      var lbl = el('text', {x:marginL-6, y:gy+3, class:'axis-label', 'text-anchor':'end'});
      lbl.textContent = gv.toFixed(1);
      svg.appendChild(lbl);
    }
    months.forEach(function(m, i){
      var lbl = el('text', {x:xAt(i), y:H-6, class:'axis-label', 'text-anchor':'middle'});
      lbl.textContent = m + '月';
      svg.appendChild(lbl);
    });
    var endLabels = [];
    series.forEach(function(s){
      var pts = [];
      s.data.forEach(function(p, i){ if (p) pts.push([i, p.per_store]); });
      if (pts.length === 0) return;
      var d = pts.map(function(p,i){ return (i===0?'M':'L')+xAt(p[0]).toFixed(1)+' '+yAt(p[1]).toFixed(1); }).join(' ');
      svg.appendChild(el('path', {d:d, class:'series-line', stroke:s.color}));
      pts.forEach(function(p){ svg.appendChild(el('circle', {cx:xAt(p[0]), cy:yAt(p[1]), r:3.6, class:'series-dot', fill:s.color})); });
      var last = pts[pts.length-1];
      endLabels.push({x:xAt(last[0])+7, y:yAt(last[1]), color:s.color, text:last[1].toFixed(1)});
      // 前月比較用: 直前月の値(このチャートは単年のみのため前年同月は付けられない)
      var prevMonthIdx = last[0] - 1;
      var pm = pts.filter(function(p){ return p[0] === prevMonthIdx; })[0];
      if (pm) endLabels.push({x:xAt(pm[0]), y:yAt(pm[1])-9, color:s.color, text:pm[1].toFixed(1), anchor:'middle', compare:true});
    });
    layoutLabels(svg, endLabels);
  })();

  // ---- ribbon index cards ----
  (function(){
    var host = document.getElementById('idx-cards');
    function cls(v){ return v < 50 ? 'low' : (v >= 90 ? 'ok' : ''); }
    host.innerHTML = DATA.smile.ribbon_aug_index.map(function(r){
      return '<div class="idx-card"><div class="store">'+r.name+'</div>' +
        '<div class="idx-head">対エリア平均・100%が同等</div>' +
        '<div class="idx-row"><span>PV指数</span><span class="idxval '+cls(r.pv_idx)+'">'+r.pv_idx+'%</span></div>' +
        '<div class="idx-row"><span>CVR指数</span><span class="idxval '+cls(r.cvr_idx)+'">'+r.cvr_idx+'%</span></div>' +
        '<div class="idx-row"><span>ACR指数</span><span class="idxval '+cls(r.acr_idx)+'">'+r.acr_idx+'%</span></div>' +
        '</div>';
    }).join('');
  })();

  // ---- SEO/MEO rank tables (per brand) ----
  var KWS = ['整骨院','整体','腰痛','肩こり','骨盤矯正'];
  function renderRankTable(hostId, rows, kind){
    var host = document.getElementById(hostId);
    var html = '<table><thead><tr><th>店舗</th>' + KWS.map(function(k){ return '<th>'+k+'</th>'; }).join('') + '</tr></thead><tbody>';
    rows.forEach(function(r){
      var vals = r[kind];
      html += '<tr><td>'+r.name+'</td>' + KWS.map(function(k){
        var v = vals[k];
        if (v == null) return '<td class="rank-bad">—</td>';
        var cls = v <= 3 ? 'rank1' : '';
        return '<td class="'+cls+'">'+v+'</td>';
      }).join('') + '</tr>';
    });
    html += '</tbody></table>';
    host.innerHTML = html;
  }
  renderRankTable('seo-table-good', DATA.good.seo_meo, 'seo');
  renderRankTable('seo-table-smile', DATA.smile.seo_meo, 'seo');
  renderRankTable('meo-table-good', DATA.good.seo_meo, 'meo');
  renderRankTable('meo-table-smile', DATA.smile.seo_meo, 'meo');

  // ---- SEO/MEO 全体傾向(6位外/3位外KW数の月次推移。店舗別表の前に表示) ----
  function momBadge(mom){
    var cls = mom < 0 ? 'down' : (mom > 0 ? 'up' : 'flat');
    var sign = mom > 0 ? '+' : '';
    return '<span class="mom '+cls+'">'+sign+mom+'</span>';
  }
  function renderTrendTable(hostId, months, block){
    var host = document.getElementById(hostId);
    if (!host) return;
    var html = '<div class="trend-caption">'+block.label+'</div><table><thead><tr><th>キーワード</th>' +
      months.map(function(m){ return '<th>'+m+'</th>'; }).join('') +
      '<th>前月比</th></tr></thead><tbody>';
    block.rows.forEach(function(r){
      html += '<tr><td>'+r.kw+'</td>' +
        r.values.map(function(v){ return '<td>'+v+'</td>'; }).join('') +
        '<td>'+momBadge(r.mom)+'</td></tr>';
    });
    html += '<tr class="total-row"><td class="trend-total">合計</td>' +
      block.total.values.map(function(v){ return '<td class="trend-total">'+v+'</td>'; }).join('') +
      '<td>'+momBadge(block.total.mom)+'</td></tr>';
    html += '</tbody></table>';
    host.innerHTML = html;
  }
  if (DATA.smile.seo_trend){
    var st = DATA.smile.seo_trend;
    renderTrendTable('seo-trend-smile', st.months, st.seo);
    renderTrendTable('meo-trend-smile', st.months, st.meo);
    if (st.computed_from_8gatsu){
      var noteMsg2 = '8月分のみこのセッションが店舗別SEO/MEO順位の生データから算出(4〜7月は「報告用」タブの既存手入力値をそのまま使用。集計ルールは同一のつもりだが、値の出所が月によって異なる点に注意)';
      document.getElementById('seo-trend-smile-note').textContent = noteMsg2;
      document.getElementById('meo-trend-smile-note').textContent = noteMsg2;
    }
  }
  if (DATA.good.seo_trend){
    var gt = DATA.good.seo_trend;
    renderTrendTable('seo-trend-good', gt.months, gt.seo);
    renderTrendTable('meo-trend-good', gt.months, gt.meo);
    if (gt.computed){
      var noteMsg = 'このセッションが各月の店舗別SEO/MEO順位データから算出(スマイル側は「報告用」タブの既存値をそのまま使用。集計ルールは同一だが、値の出所が異なる点に注意)';
      document.getElementById('seo-trend-good-note').textContent = noteMsg;
      document.getElementById('meo-trend-good-note').textContent = noteMsg;
    }
  }
})();
</script>
</body></html>"""

html = HTML.replace("__DATA_JSON__", DATA_JSON)

with open(args.out, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", len(html), "bytes ->", args.out)
