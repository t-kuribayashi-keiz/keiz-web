#!/usr/bin/env python3
"""応答本文から店舗の表示・順位を抽出する(v2ロジック)。

2026年9月のパイロット調査で2回のバグ修正を経て安定した版:
  v1の失敗: 見出しに店舗名が直接入る形式(「### 6. 本八幡駅前整骨院」)を
            見出し直後の太字と誤認していた
  v2aの修正: 番号付き見出しと通常見出しを両方拾うようにしたところ、
            「やわら接骨院 本八幡」と「1. やわら接骨院 本八幡」が別物として
            重複カウントされた → 先頭の番号を落としてから重複判定するよう修正
  v2bの修正: 「整骨院」「接骨院」等の一般名詞や、「本八幡駅周辺で保険診療に
            対応している整骨院・接骨院」のような文章片が店舗名として誤検出
            された → NOISE語リストを追加、鉤括弧を含む文を除外、長さを30字に制限

実測(291応答): 店舗名抽出232件のうち約11件(5%)で順位が未特定
                (表示の有無は誤りなし。並び順の特定にのみ影響)。

使い方:
  python3 parse_ranks.py results/<店舗名>.json 本八幡南口 [他の表記ゆれ...]
  → 同ファイルに rank / listed_count / mentioned / listed を書き足す
"""
import json
import re
import sys

BIZ = r'(?:接骨院|整骨院|整体院|整体|カイロプラクティック|カイロ|鍼灸院|鍼灸|治療院|サロン|クリニック|整形外科|マッサージ|ストレッチ|リラクゼーション)'

NOISE = re.compile(
    r'(選び方|選ぶ|ポイント|注意|まとめ|比較表|チェック|条件|とは|違い|'
    r'おすすめの選|受診|保険が|適用|流れ|目安|費用|料金相場|'
    r'こんな方|どんな方|方におすすめ|したい方|希望する|重視|場合|'
    r'周辺|対応している|対応可|診療に|一覧|以下の|次の|上記|'
    r'整骨院・接骨院|接骨院・整骨院|整体・整骨)'
)

LEAD_NUM = re.compile(r'^\s*\d+\s*[.．、)）]\s*')
DECO = re.compile(r'^[【\[(（]?[^\w一-龥ぁ-んァ-ヶa-zA-Z]*')


def candidates(text):
    """店舗名候補を出現順(文字位置順)に返す。"""
    hits = []

    for m in re.finditer(r'^#{1,4}\s*\**\s*\d+[.．]\s*(.+?)\**\s*$', text, re.M):
        hits.append((m.start(), m.group(1).strip()))
    for m in re.finditer(r'^#{1,4}\s*\**\s*([^\d\n].*?)\**\s*$', text, re.M):
        hits.append((m.start(), m.group(1).strip()))
    for m in re.finditer(r'\*\*(.+?)\*\*', text):
        hits.append((m.start(), m.group(1).strip()))
    for m in re.finditer(r'^\s*\d+[.．]\s*([^\n*]{2,40})$', text, re.M):
        hits.append((m.start(), m.group(1).strip()))

    hits.sort(key=lambda x: x[0])

    out, seen = [], set()
    for pos, raw in hits:
        name = raw.strip(' 　:：|-–—*#')
        name = re.sub(r'^【.*?】\s*', '', name)
        name = LEAD_NUM.sub('', name)
        name = DECO.sub('', name)
        name = LEAD_NUM.sub('', name)
        name = name.strip(' 　:：|-–—*#')
        if not (3 <= len(name) <= 30):
            continue
        if not re.search(BIZ, name):
            continue
        if NOISE.search(name):
            continue
        if re.search(r'[。？?！!「」『』]', name):
            continue
        key = re.sub(r'[\s　（）()／/・,、。\-–—]', '', name)
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def analyze(text, keys):
    listed = candidates(text)
    rank = None
    for i, name in enumerate(listed, 1):
        if any(k in name for k in keys):
            rank = i
            break
    return rank, len(listed), any(k in text for k in keys), listed


def parse_file(path, keys):
    rows = json.load(open(path))
    n_ok = n_mention = n_rank = 0
    for r in rows:
        if 'text' not in r:
            continue
        rank, cnt, mentioned, listed = analyze(r['text'], keys)
        r['rank'], r['listed_count'], r['mentioned'], r['listed'] = rank, cnt, mentioned, listed
        n_ok += 1
        n_mention += bool(mentioned)
        n_rank += bool(rank)
    json.dump(rows, open(path, 'w'), ensure_ascii=False, indent=2)
    print(f'{path}: 有効{n_ok}件 / 表示{n_mention}件 / 順位特定{n_rank}件 '
          f'(未特定 {n_mention - n_rank}件)')


if __name__ == '__main__':
    parse_file(sys.argv[1], sys.argv[2:] or ['本八幡南口'])
