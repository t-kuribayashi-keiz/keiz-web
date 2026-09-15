#!/usr/bin/env python3
"""config/stores.*.json の match キーを使って results/*.json 全店舗を一括パースする。

使い方:
  python3 parse_all.py --stores ../config/stores.pilot.json --results results/
"""
import argparse
import json
import os

from parse_ranks import parse_file


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", required=True)
    ap.add_argument("--results", default="results")
    args = ap.parse_args()

    stores_cfg = json.load(open(args.stores))["stores"]
    for name, cfg in stores_cfg.items():
        path = os.path.join(args.results, f"{name}.json")
        if not os.path.exists(path):
            print(f"skip: {path} が見つかりません")
            continue
        parse_file(path, cfg["match"])


if __name__ == "__main__":
    main()
