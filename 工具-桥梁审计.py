"""Read-only audit of all outdoor raw block words/metatile attributes and traversal masks."""
import base64
import json
from collections import Counter
from pathlib import Path

from 素材.绿宝石场景.解码地图 import PIN, SRC, metatile, words

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/桥梁通行"


def main():
    catalog = json.loads((ROOT / "素材/绿宝石场景/场景目录.json").read_text())
    terrain = catalog["terrains"][0]
    layouts = {v["id"]: v for v in json.loads((SRC / "data/layouts/layouts.json").read_text())["layouts"]}
    masks = {key: base64.b64decode(terrain[key + "B64"])
             for key in ["collision", "elevation", "behavior", "walk", "water"]}
    bridge = {key: base64.b64decode(terrain["bridges"][key + "B64"])
              for key in ["deck", "land", "water", "gateway"]}
    rows, examples = [], []
    count = 0
    for area in terrain["areas"]:
        layout = layouts[area["sourceLayout"]]
        blocks = words(layout["blockdata_filepath"])
        special = Counter()
        transition = []
        for local, value in enumerate(blocks[:area["columns"] * area["rows"]]):
            x, y = local % area["columns"], local // area["columns"]
            i = (area["gridY"] + y) * terrain["columns"] + area["gridX"] + x
            _, _, attr = metatile(layout["primary_tileset"], layout["secondary_tileset"], value & 1023)
            c, z, b = (value >> 10) & 3, value >> 12, attr & 255
            assert (c, z, b) == tuple(masks[key][i] for key in ["collision", "elevation", "behavior"])
            count += 1
            if b == 0x2b or 0x70 <= b <= 0x7f or b in {0x1b, 0x61, 0x6a, 0x6b}:
                special[f"behavior=0x{b:02x}, collision={c}, elevation={z}"] += 1
                if c == 0 and b == 0x2b and z == 3:
                    assert (masks["walk"][i] or bridge["land"][i]) and masks["water"][i] == 0
                # One concrete raw word for each behavior/height/collision combination.
                key = (area["sourceName"], b, c, z)
                if not any(tuple(e["key"]) == key for e in examples):
                    examples.append({"key": key, "local": [x, y], "rawWord": f"0x{value:04x}",
                                     "metatile": f"0x{value & 1023:03x}",
                                     "attribute": f"0x{attr:04x}",
                                     "walk": masks["walk"][i], "swim": masks["water"][i],
                                     "layers": {k: bridge[k][i] for k in bridge}})
            if c == 0 and b == 0 and z == 0:
                transition.append([x, y])
        rows.append({"map": area["sourceName"], "cells": area["columns"] * area["rows"],
                     "bridgeAndStairBehaviors": dict(special),
                     "normalHeight0Transitions": transition})
    report = {"sourceCommit": PIN, "outdoorMaps": len(rows), "rawCellsVerified": count,
              "rawMismatch": 0, "deck": sum(bridge["deck"]), "underLand": sum(bridge["land"]),
              "underWater": sum(bridge["water"]), "gateways": sum(bridge["gateway"]),
              "maps": rows, "rawExamples": examples}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{len(rows)}图原始桥梁审计.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"maps", "rawExamples"}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
