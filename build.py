#!/usr/bin/env python3
"""問題データを検証し、選択肢を生成して shell.html に埋め込み、index.html を出力する。

使い方:  python3 build.py
入力:    shell.html, questions.json, questions2.json（複数ファイルは順に結合）
出力:    index.html
"""
import hashlib
import itertools
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
SHELL = ROOT / "shell.html"
SOURCES = ["questions.json", "questions2.json", "questions3.json", "questions4.json", "questions5.json"]
OUT = ROOT / "index.html"
PLACEHOLDER = "/*__DATA__*/"


def load():
    data = None
    for name in SOURCES:
        p = ROOT / name
        if not p.exists():
            continue
        part = json.loads(p.read_text(encoding="utf-8"))
        if data is None:
            data = part
        else:
            data["questions"] += part.get("questions", [])
            if "cases" in part:
                data.setdefault("cases", {}).update(part["cases"])
    return data


# 三冷の法令論点番号 → 二冷の法令論点番号（令和7年度の出題順に基づく）
LAW_SLOT_3_TO_2 = {1:1, 2:2, 3:3, 4:7, 5:5, 6:6, 7:8, 8:4, 9:11, 10:16, 11:16, 12:9, 13:10,
                   14:(12, 15), 15:13, 16:14, 17:17, 18:18, 19:19, 20:20}


def assign_slot2(data):
    """三冷・二冷共用の法令問題に、二冷での論点番号 slot2 を付ける。"""
    alt = {}
    for q in data["questions"]:
        if q["subject"] == "law" and "3" in q["levels"] and "2" in q["levels"]:
            m = LAW_SLOT_3_TO_2[q["slot"]]
            if isinstance(m, tuple):
                i = alt.get(q["slot"], 0); alt[q["slot"]] = i + 1
                m = m[i % len(m)]
            q["slot2"] = m


def validate_and_fill(data):
    errors = []
    assign_slot2(data)
    ids = Counter(q["id"] for q in data["questions"])
    for qid, n in ids.items():
        if n > 1:
            errors.append(f"重複ID: {qid}")
    for q in data["questions"]:
        st = q.get("statements", [])
        if len(st) not in (3, 4):
            errors.append(f"{q['id']}: 記述は3つ又は4つ")
            continue
        for s in st:
            if not isinstance(s.get("ok"), bool):
                errors.append(f"{q['id']}: ok は true/false")
            if not s.get("t") or not s.get("why"):
                errors.append(f"{q['id']}: t と why は必須")
        correct = [i for i, s in enumerate(st) if s.get("ok")]
        if not correct:
            errors.append(f"{q['id']}: 正しい記述が1つもない")
            continue
        n = len(st)
        combos = [list(c) for r in range(1, n + 1) for c in itertools.combinations(range(n), r)]
        rng = random.Random(int(hashlib.md5(q["id"].encode()).hexdigest(), 16))  # IDごとに固定
        pool = [c for c in combos if c != correct]
        if n == 4:
            pool = [c for c in pool if 2 <= len(c) <= 3]
        rng.shuffle(pool)
        opts = [correct] + pool[:4]
        opts.sort(key=lambda a: (len(a), a))
        q["opts"] = opts
        q["ans"] = opts.index(correct)
    return errors


def report(data):
    by = Counter((q["subject"], "/".join(q["levels"])) for q in data["questions"])
    print(f"問題数: {len(data['questions'])}")
    for k, v in sorted(by.items()):
        print(f"  {k[0]:<10} levels={k[1]:<5} {v}問")
    print("正答番号の分布:", dict(sorted(Counter(q["ans"] + 1 for q in data["questions"]).items())))
    for level, subjects in data["topics"].items():
        for subject, topics in subjects.items():
            have = {(q.get("slot2") if level == "2" and q.get("slot2") else q["slot"]) for q in data["questions"] if q["subject"] == subject and level in q["levels"]}
            have |= {t["no"] for t in topics if t.get("gen")}
            missing = [t["no"] for t in topics if t["no"] not in have]
            if missing:
                print(f"  注意: level {level} {subject} に問題のない論点: {missing}")


def main():
    data = load()
    errors = validate_and_fill(data)
    if errors:
        print("エラー:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        sys.exit(1)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if "</script" in payload:
        sys.exit("データに </script が含まれています")
    shell = SHELL.read_text(encoding="utf-8")
    if shell.count(PLACEHOLDER) != 1:
        sys.exit("shell.html にプレースホルダがありません")
    OUT.write_text(shell.replace(PLACEHOLDER, payload), encoding="utf-8")
    report(data)
    print(f"出力: {OUT.name} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
