#!/usr/bin/env python3
"""あはき柔整プラン5院向けブログ投稿を組み立てるヘルパー。

店舗の自己紹介文・営業時間・住所・TEL・HP等の"末尾の定型文"をテンプレートの
プレースホルダーに機械的に流し込むことで、人が手で書き換えて店舗名や住所を
間違える事故を防ぐ。ローテーション(どの店にどのテンプレートを次に出すか)も
ここで決め、rotation-state.jsonに記録する。

このスクリプトは文章を組み立てるだけで、SalonBoardへの実際の投稿はしない。
投稿はclaude-in-chrome経由のブラウザ操作(hpb-salonboard-updateスキルの
非交渉ルール: パスワードは絶対に打たない/公開前に毎回人の確認を取る)が別途行う。

Usage:
  python build_ahaki_blog_post.py list-stores
  python build_ahaki_blog_post.py list-templates
  python build_ahaki_blog_post.py next <store_name>              # ドライラン。stateは変更しない
  python build_ahaki_blog_post.py mark-posted <store_name> <template_id> [--date YYYY-MM-DD] [--url URL]
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = SKILL_ROOT / "data"
TEMPLATES_PATH = DATA_DIR / "blog-templates.json"
STORES_PATH = DATA_DIR / "store-info.json"
STATE_PATH = DATA_DIR / "rotation-state.json"
IMAGE_DIR_REL = "data/proposals/2026-09-12_koriyama-blog-images"

BANNED_WORDS_FALLBACK = ["整体", "骨盤矯正", "マッサージ", "柔整", "矯正", "もみほぐし"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def get_store(stores_data, store_name):
    for s in stores_data["stores"]:
        if s["store_name"] == store_name:
            return s
    raise SystemExit(f"未知の店舗名です: {store_name!r}. list-stores で確認してください。")


def get_template(templates_data, template_id):
    for t in templates_data["templates"]:
        if t["id"] == template_id:
            return t
    raise SystemExit(f"未知のtemplate_idです: {template_id!r}. list-templates で確認してください。")


def build_signature(store):
    lines = [store["store_name"], f"営業時間：{store['hours_text']}"]
    if store.get("closed_day"):
        lines.append(f"定休日：{store['closed_day']}曜")
    lines.append(f"住所：{store['address']}")
    lines.append(f"TEL：{store['phone']}")
    if store.get("instagram"):
        lines.append(f"Instagram：{store['instagram']}")
    lines.append(f"HP：{store['hp_url']}")
    return "\n".join(lines)


def build_hashtags(templates_data, store):
    pool = templates_data.get("hashtag_pool", [])
    tags = [f"#{w}" for w in pool]
    if store.get("area_keyword"):
        tags.append(f"#{store['area_keyword']}鍼灸")
        tags.append(f"#{store['area_keyword']}美容鍼")
    return "".join(tags)


def fill_placeholders(text, store):
    return (
        text.replace("{{STORE_NAME}}", store["store_name"])
        .replace("{{FACILITY}}", store["facility_word"])
    )


def check_banned_words(text, templates_data):
    banned = templates_data.get("banned_words", BANNED_WORDS_FALLBACK)
    hits = [w for w in banned if w in text]
    return hits


def pick_template(templates_data, state, store_name):
    """次に使うテンプレートを選ぶ。

    優先順位: (1) その店舗がまだ使っていないもの優先 (2) 全店舗を通じて最も
    長く使われていない(≒他店でも最近使われていない)もの優先 (3) 店舗名込みの
    安定ハッシュでタイブレーク。

    (3)が無いと、複数店舗分をまとめて(mark-postedを挟まずに)`next`だけ
    連続で呼んだ場合、状態が更新されないため全店舗が同じ計算結果=同じ
    テンプレートを選んでしまう(2026-09-14に実際に発生)。ハッシュタイブレークは
    店舗ごとに異なる順序を作るため、この「まとめて先読み」のケースでも
    ある程度分散する。本来の使い方(1店舗ごとにmark-postedしてから次のstoreの
    nextを呼ぶ)であれば、状態更新そのものによって自然に分散する。
    """
    templates = templates_data["templates"]
    store_hist = state["stores"].setdefault(store_name, {"history": []})["history"]
    store_used_ids = {h["template_id"] for h in store_hist}

    global_last_used = {}
    for s_data in state["stores"].values():
        for h in s_data.get("history", []):
            tid = h["template_id"]
            d = h["posted_at"]
            if tid not in global_last_used or d > global_last_used[tid]:
                global_last_used[tid] = d

    def sort_key(t):
        tid = t["id"]
        used_by_this_store = tid in store_used_ids
        global_date = global_last_used.get(tid, "")  # "" (未使用) が最優先になるよう空文字を最小値にする
        tiebreak = hashlib.md5(f"{store_name}:{tid}".encode("utf-8")).hexdigest()
        return (used_by_this_store, global_date, tiebreak)

    return sorted(templates, key=sort_key)[0]


def cmd_list_stores(stores_data):
    for s in stores_data["stores"]:
        print(f"{s['store_name']}\t{s['hpb_store_id']}\t{s['facility_word']}")


def cmd_list_templates(templates_data):
    for t in templates_data["templates"]:
        print(f"{t['id']}\t{t['category']}\t{t['title']}")


def cmd_next(templates_data, stores_data, state, store_name):
    store = get_store(stores_data, store_name)
    template = pick_template(templates_data, state, store_name)

    title = fill_placeholders(template["title"], store)
    body_main = fill_placeholders(template["body"], store)
    signature = build_signature(store)
    full_body = f"{body_main}\n\n{signature}"
    hashtags = build_hashtags(templates_data, store)

    hits = check_banned_words(body_main, templates_data)

    result = {
        "store_name": store["store_name"],
        "hpb_store_id": store["hpb_store_id"],
        "template_id": template["id"],
        "source_bid": template["source_bid"],
        "category": template["category"],
        "title": title,
        "body": full_body,
        "hashtags": hashtags,
        "image_path": f"{IMAGE_DIR_REL}/{template['image_bid']}.jpg",
        "banned_word_check": "OK - 検出なし" if not hits else f"要確認: {hits} を含む",
        "note": "投稿前に必ず人の目でこの本文・店舗情報を確認すること。承認後、実際の投稿はclaude-in-chrome経由のSalonBoard操作で行う(このスクリプトは投稿しない)。成功を確認できたら mark-posted で記録すること。",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_mark_posted(state, store_name, template_id, post_date, url):
    store_hist = state["stores"].setdefault(store_name, {"history": []})
    entry = {"template_id": template_id, "posted_at": post_date}
    if url:
        entry["hpb_blog_url"] = url
    store_hist["history"].append(entry)
    save_json(STATE_PATH, state)
    print(f"記録しました: {store_name} <- {template_id} ({post_date})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-stores")
    sub.add_parser("list-templates")

    p_next = sub.add_parser("next")
    p_next.add_argument("store_name")

    p_mark = sub.add_parser("mark-posted")
    p_mark.add_argument("store_name")
    p_mark.add_argument("template_id")
    p_mark.add_argument("--date", default=date.today().isoformat())
    p_mark.add_argument("--url", default=None)

    args = parser.parse_args()

    templates_data = load_json(TEMPLATES_PATH)
    stores_data = load_json(STORES_PATH)

    if args.command == "list-stores":
        cmd_list_stores(stores_data)
    elif args.command == "list-templates":
        cmd_list_templates(templates_data)
    elif args.command == "next":
        state = load_json(STATE_PATH)
        cmd_next(templates_data, stores_data, state, args.store_name)
    elif args.command == "mark-posted":
        state = load_json(STATE_PATH)
        get_store(stores_data, args.store_name)  # 存在確認
        get_template(templates_data, args.template_id)  # 存在確認
        cmd_mark_posted(state, args.store_name, args.template_id, args.date, args.url)


if __name__ == "__main__":
    sys.exit(main())
