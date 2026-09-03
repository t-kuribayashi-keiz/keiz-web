#!/usr/bin/env python3
"""広告費シートなどの店舗名を、`data/clinics.json` の院マスタに突き合わせる。

なぜ完全一致では駄目か(栗林さんの指摘、2026-09-03):

  HPBに掲載するタイミングで店舗名を整骨院→整体院に変えている店舗や、
  SEO対策として【肩こり・腰痛なら】といった冠文字をつけている店舗もある

つまり同じ店舗が媒体ごとに違う名前で出てくる。完全一致だと取りこぼし、取りこぼした分は
店舗数として数えられず、**エラーも出ないまま集計が少なくなる**。かといって緩くしすぎると
別店舗を同一視する。そこで2段構えにする:

  1. 表記ゆれを正規化してから完全一致を試す(ここでほぼ吸収できる)
  2. それでも当たらなければ類似度で候補を集める。候補が全部同じグループ(直営/サンズ/ミライ)に
     属していれば、どの店舗かまでは特定できなくても**店舗数としては数えられる**ので採用する。
     グループがまたがったら判定不能として停止する

「判定できないときは黙って直営に寄せない」のがこのモジュールの一番大事な性質。
店舗数が1件ずれても数字は自然に見えてしまい、誰も気づかないため。
"""

from __future__ import annotations

import difflib
import json
import os
import re
import unicodedata

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLINICS_PATH = os.path.join(REPO_ROOT, "data", "clinics.json")

# 院の種別を表す語。媒体によって整骨院/整体院/接骨院が入れ替わるため、1つの記号に潰して
# 「〇」として扱う。潰すだけで消さないのは、「わかば」と「わかば整骨院」を同一視しないため。
CLINIC_TYPE_WORDS = (
    "鍼灸整骨院", "鍼灸接骨院", "鍼灸整体院",
    "整骨院", "整体院", "接骨院", "治療院", "鍼灸院",
    "整骨", "接骨", "整体",
)
TYPE_TOKEN = "〇"

# 冠文字(【肩こり・腰痛なら】など)。中身ごと落とす。院マスタ側には括弧付きの名前が
# 1件も無いことを確認済みなので、落として困る名前は今のところ存在しない。
BRACKETED = re.compile(r"[【\[（(〔「『《〈][^】\]）)〕」』》〉]*[】\]）)〕」』》〉]")

# 類似度で拾うときの下限。これを下回る候補は見ない。
SIMILARITY_THRESHOLD = 0.82


def normalize_store_name(name: str) -> str:
    """媒体をまたいでも同じ形になるように店舗名をならす。"""
    text = unicodedata.normalize("NFKC", str(name))
    text = BRACKETED.sub("", text)
    text = re.sub(r"\s+", "", text)
    text = text.replace("針灸", "鍼灸")          # 院マスタ内にも両方の表記がある
    for word in CLINIC_TYPE_WORDS:
        text = text.replace(word, TYPE_TOKEN)
    text = re.sub(f"{TYPE_TOKEN}+", TYPE_TOKEN, text)
    text = re.sub(r"[院店]$", "", text)           # 「枚方公園院」と「枚方公園」を同一視する
    return text


def group_of(clinic: dict) -> str:
    """KPIシートのM/N/O・Q/R/S列の括りに合わせたグループ名を返す。

    直営はこのシート上では法人を分けずに1列(M/Q)にまとまるので、直営配下の法人は
    すべて "直営" に畳む。
    """
    brand = clinic.get("brand")
    if brand == "直営":
        return "直営"
    if brand == "サンズミライ":
        return clinic.get("corporation") or "サンズミライ"
    return brand


class StoreMatcher:
    def __init__(self, clinics_path: str = CLINICS_PATH):
        with open(clinics_path, encoding="utf-8") as handle:
            self.clinics = json.load(handle)["clinics"]
        self.by_normalized: dict[str, list[dict]] = {}
        for clinic in self.clinics:
            self.by_normalized.setdefault(normalize_store_name(clinic["name"]), []).append(clinic)
        self.normalized_names = list(self.by_normalized)

    def match(self, name: str) -> dict:
        """1件の店舗名を判定する。

        返す辞書:
          group      判定できたグループ名(直営 / サンズ / ミライ / スマイル ...)。不明ならNone
          how        "exact"(正規化後の完全一致) / "similar"(類似度) / "unmatched" / "ambiguous"
          clinic     店舗まで特定できた場合のマスタのエントリ
          candidates 類似候補の店舗名(ログ用)
        """
        normalized = normalize_store_name(name)
        if not normalized:
            return {"group": None, "how": "unmatched", "clinic": None, "candidates": []}

        exact = self.by_normalized.get(normalized)
        if exact:
            groups = {group_of(clinic) for clinic in exact}
            if len(groups) == 1:
                return {
                    "group": groups.pop(),
                    "how": "exact",
                    "clinic": exact[0] if len(exact) == 1 else None,
                    "candidates": [clinic["name"] for clinic in exact],
                }
            return {
                "group": None,
                "how": "ambiguous",
                "clinic": None,
                "candidates": [clinic["name"] for clinic in exact],
            }

        scored = [
            (difflib.SequenceMatcher(None, normalized, candidate).ratio(), candidate)
            for candidate in self.normalized_names
        ]
        near = [candidate for ratio, candidate in scored if ratio >= SIMILARITY_THRESHOLD]
        if not near:
            return {"group": None, "how": "unmatched", "clinic": None, "candidates": []}

        clinics = [clinic for candidate in near for clinic in self.by_normalized[candidate]]
        groups = {group_of(clinic) for clinic in clinics}
        names = [clinic["name"] for clinic in clinics]
        if len(groups) > 1:
            # どの店舗かは分からなくても構わないが、グループが割れたら数えようがない。
            return {"group": None, "how": "ambiguous", "clinic": None, "candidates": names}
        return {
            "group": groups.pop(),
            "how": "similar",
            "clinic": clinics[0] if len(clinics) == 1 else None,
            "candidates": names,
        }
