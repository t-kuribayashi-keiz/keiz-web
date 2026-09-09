#!/usr/bin/env python3
"""Gemini グラウンディング調査ランナー。

店舗ごとに 10プロンプト × REPS回 施行し、
 - 対象店舗が言及されたか(表示率)
 - 引用された検索クエリ・引用元ドメイン
を収集して results/<店舗名>.json に書き出す。

使い方:
  export GEMINI_API_KEY=...          # AI StudioでWorkspaceアカウント発行のキー。課金設定必須(グラウンディング利用のため)
  python3 run_survey.py --stores ../config/stores.pilot.json --out results/

料金:
  実測 約¥1.05/回(理論値¥0.49の約2.1倍、原因未特定)。
  詳細は ../references/cost-notes.md 参照。事前にAI Studioの月次利用上限を必ず設定すること
  (上限¥0は全リクエストが失敗する)。
"""
import argparse
import json
import os
import sys
import time
import urllib.request

MODEL = "gemini-3.6-flash"
REPS_DEFAULT = 3
SLEEP_DEFAULT = 2.0


def call_gemini(prompt, api_key):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }).encode()
    req = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def run_store(store_name, cfg, prompts_cfg, api_key, reps, sleep, out_dir, existing=None):
    tpl = prompts_cfg["station"] if cfg["kind"] == "station" else prompts_cfg["roadside"]
    field = "station" if cfg["kind"] == "station" else "area"
    have = {(r["prompt_no"], r["rep"]) for r in (existing or []) if "error" not in r}
    rows = [r for r in (existing or []) if "error" not in r]

    tok_in = tok_out = 0
    for pi, t in enumerate(tpl, 1):
        prompt = t.format(**{field: cfg["place"]})
        for rep in range(1, reps + 1):
            if (pi, rep) in have:
                continue
            try:
                d = call_gemini(prompt, api_key)
            except Exception as e:
                print(f"  [{pi}-{rep}] ERROR {e}", flush=True)
                time.sleep(sleep)
                continue

            cand = d.get("candidates", [{}])[0]
            text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
            gm = cand.get("groundingMetadata", {})
            usage = d.get("usageMetadata", {})
            tok_in += usage.get("promptTokenCount", 0)
            tok_out += usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)

            domains = []
            for ch in gm.get("groundingChunks", []):
                title = ch.get("web", {}).get("title", "")
                if title and title not in domains:
                    domains.append(title)

            rows.append(dict(
                store=store_name, prompt_no=pi, prompt=prompt, rep=rep,
                text=text,
                search_queries=gm.get("webSearchQueries", []),
                cited_domains=domains,
                # rank/mentioned/listed はここでは未確定。parse_ranks.py で後付けする
            ))
            print(f"  [{pi}-{rep}] クエリ={gm.get('webSearchQueries', [])}", flush=True)
            time.sleep(sleep)

    rows.sort(key=lambda r: (r["prompt_no"], r["rep"]))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{store_name}.json"), "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    cost_usd = tok_in / 1e6 * 0.25 + tok_out / 1e6 * 1.50
    print(f"{store_name}: 追加{len([r for r in rows if (r['prompt_no'], r['rep']) not in have])}件 "
          f"/ 累計{len(rows)}件 / 今回トークン概算 ${cost_usd:.4f}(理論値。実測は約2.1倍と想定)", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", required=True, help="config/stores.*.json へのパス")
    ap.add_argument("--prompts", default=os.path.join(os.path.dirname(__file__), "..", "config", "prompts.json"))
    ap.add_argument("--out", default="results")
    ap.add_argument("--reps", type=int, default=REPS_DEFAULT)
    ap.add_argument("--sleep", type=float, default=SLEEP_DEFAULT)
    ap.add_argument("--only", nargs="*", help="この店舗名だけ実行(未指定なら全店)")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY が設定されていません。AI Studioで発行したキーを環境変数に設定してください。")

    stores_cfg = json.load(open(args.stores))["stores"]
    prompts_cfg = json.load(open(args.prompts))
    targets = args.only if args.only else list(stores_cfg.keys())

    for name in targets:
        if name not in stores_cfg:
            print(f"skip: {name} は {args.stores} に見つかりません", file=sys.stderr)
            continue
        out_path = os.path.join(args.out, f"{name}.json")
        existing = json.load(open(out_path)) if os.path.exists(out_path) else []
        print(f"=== {name} ===", flush=True)
        run_store(name, stores_cfg[name], prompts_cfg, api_key, args.reps, args.sleep, args.out, existing)


if __name__ == "__main__":
    main()
