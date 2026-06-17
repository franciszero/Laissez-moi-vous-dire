#!/usr/bin/env python3
"""给现有 ../L*/vocab.json 回填 fem/fem_raw（从每条的 raw 重算）。跑一次即可。"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import vocab  # noqa: E402

BASE = pathlib.Path(__file__).resolve().parent.parent.parent  # 本地录屏课/


def main() -> None:
    for vj in sorted(BASE.glob("L*/vocab.json")):
        data = json.loads(vj.read_text("utf-8"))
        n = 0
        for e in data:
            masc, marker = vocab.split_gender(e.get("raw") or e.get("lemma") or "")
            fem = vocab.feminine_form(masc, marker)
            e["fem"] = fem
            e["fem_raw"] = marker
            if fem:
                n += 1
        vj.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        print(f"{vj.parent.name}: {len(data)} 词，回填阴性 {n} 个")


if __name__ == "__main__":
    main()
