#!/usr/bin/env python3
"""results/*.json + ranks.json(任意) → ダッシュボードDBに投入する形のJSONを生成する。

出力は3つのドキュメントに対応:
  config/master  … 店舗マスタ(SEO/MEO順位・立地区分など)
  summary/latest … ヘッダーの要約統計
  rounds/<round> … 今回ラウンドの店舗×プロンプト集計

ダッシュボードのDBスキーマは ../references/dashboard-schema.md 参照。
生成したJSONをArtifactツールのwrite_db(batch)でダッシュボードURLに書き込むのは
Claudeセッション側の役目(このスクリプト自身はDBに書き込めない — dbはArtifactツール
経由でのみ書き込める仕様のため)。

使い方:
  python3 aggregate_for_dashboard.py \
    --stores ../config/stores.pilot.json \
    --results results/ \
    --round 2026-10 \
    --ranks ranks.json \
    --out dashboard_payload.json
"""
import argparse
import glob
import json
import os
import statistics
from collections import Counter

PROMPTS = json.load(open(os.path.join(os.path.dirname(__file__), "..", "config", "prompts.json")))
PROMPT_LABELS = ['おすすめ', '口コミ評価', '骨盤矯正', '肩甲骨はがし', '胸郭出口症候群',
                 '女性向け', '保険適用', '日曜営業', '骨盤矯正(相談形)', '肩甲骨(相談形)']

OWN_DOMAINS_DEFAULT = ('chiryou-in.biz', 'chiryouin.biz')


def cite_class(domain, own_domains):
    if 'hotpepper.jp' in domain:
        return 'hpb'
    if 'ekiten.jp' in domain:
        return 'ekiten'
    if any(o in domain for o in own_domains):
        return 'own'
    return 'other'


def avg_rank(vals):
    nums = []
    for v in vals or []:
        v = str(v).strip()
        if v in ('-', '', '圏外', '計測不可'):
            continue
        try:
            nums.append(float(v))
        except ValueError:
            continue
    return round(statistics.mean(nums), 2) if nums else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", required=True)
    ap.add_argument("--results", default="results")
    ap.add_argument("--round", required=True, help="YYYY-MM 形式")
    ap.add_argument("--ranks", help="SEO/MEO順位のJSON({店舗名: {seo:[...], meo:[...]}} )。省略可")
    ap.add_argument("--own-domains", nargs="*", default=list(OWN_DOMAINS_DEFAULT))
    ap.add_argument("--out", default="dashboard_payload.json")
    args = ap.parse_args()

    stores_cfg = json.load(open(args.stores))["stores"]
    ranks = json.load(open(args.ranks)) if args.ranks else {}

    config_stores = {}
    round_stores = {}

    for name, cfg in stores_cfg.items():
        path = os.path.join(args.results, f"{name}.json")
        if not os.path.exists(path):
            print(f"skip: {path} が見つかりません")
            continue
        rows = [r for r in json.load(open(path)) if 'error' not in r and 'mentioned' in r]
        if not rows:
            print(f"skip: {name} は有効な応答がありません(parse_all.py実行済みか確認)")
            continue

        r = ranks.get(name, {})
        loc_label = '駅近' if cfg['kind'] == 'station' else 'ロードサイド'
        config_stores[name] = {
            'name': name,
            'brand': cfg.get('brand', '直営'),
            'location': loc_label,
            'area': cfg['place'],
            'seoRanks': r.get('seo', []),
            'meoRanks': r.get('meo', []),
            'seoAvgRank': avg_rank(r.get('seo')),
            'meoAvgRank': avg_rank(r.get('meo')),
        }

        prompt_results = []
        for pi in range(1, 11):
            prs = [x for x in rows if x['prompt_no'] == pi]
            if not prs:
                continue
            mentioned = sum(1 for x in prs if x['mentioned'])
            ranks_list = [x['rank'] for x in prs if x['rank']]
            prompt_results.append({
                'no': pi, 'label': PROMPT_LABELS[pi - 1],
                'total': len(prs), 'mentioned': mentioned,
                'avgRank': round(sum(ranks_list) / len(ranks_list), 2) if ranks_list else None,
            })

        cite_counter = Counter()
        total_cites = 0
        for x in rows:
            for d in x.get('cited_domains', []):
                total_cites += 1
                cite_counter[cite_class(d, args.own_domains)] += 1

        total_mentioned = sum(1 for x in rows if x['mentioned'])
        round_stores[name] = {
            'totalResponses': len(rows),
            'totalMentioned': total_mentioned,
            'displayRate': round(total_mentioned / len(rows) * 100, 1),
            'promptResults': prompt_results,
            'citeShare': {k: round(v / total_cites * 100, 1) for k, v in cite_counter.items()} if total_cites else {},
            'totalCites': total_cites,
            'noQueryCount': sum(1 for x in rows if not x.get('search_queries')),
        }

    payload = {
        'config': {'stores': config_stores, 'prompts': [{'no': i + 1, 'label': p} for i, p in enumerate(PROMPT_LABELS)]},
        'round': {'round': args.round, 'stores': round_stores},
        'summary': {
            'storeCount': len(round_stores),
            'totalResponses': sum(v['totalResponses'] for v in round_stores.values()),
        },
    }
    json.dump(payload, open(args.out, 'w'), ensure_ascii=False, indent=1)
    print(f"{args.out} 生成完了: {len(round_stores)}店舗 / "
          f"{payload['summary']['totalResponses']}応答")
    print("次の手順: Claudeセッションで Artifact write_db(batch) を使い、")
    print("  config['config'] → config/master (set)")
    print("  round データ → rounds/<round> (set)")
    print("  summary → summary/latest (update; lastUpdated/roundsCountも足す)")
    print("を書き込む。詳細は ../references/dashboard-schema.md 参照。")


if __name__ == "__main__":
    main()
