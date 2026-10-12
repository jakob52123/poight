"""Hoenn-only traversal metadata and two original interiors. No source artwork edits."""
import base64
import hashlib
import json
from pathlib import Path

from PIL import Image
from 全图可达 import relax_traps
from 桥梁元数据 import add_bridges
from 自由探索 import attach

CAPABILITIES = {"swim": True, "dive": True, "warps": True}
INTERIORS = {"PetalburgWoods": "橙华森林", "RusturfTunnel": "卡绿隧道"}


def encoded(values):
    return base64.b64encode(bytes(values)).decode()


def extend_catalog(root, catalog, index, blocked):
    root = Path(root)
    out = root / "通行场景"
    out.mkdir(exist_ok=True)
    maps = {m["id"]: m for m in index["maps"]}
    layouts = {v["id"]: v for v in index["layouts"]}
    main = catalog["terrains"][0]
    size = main["cellSize"]

    def emit(name, image):
        path = out / name
        image.save(path, optimize=True)
        data = path.read_bytes()
        return {"path": str(path.relative_to(root)),
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

    for m in maps.values():
        if m["name"] not in {*INTERIORS, "SootopolisCity"}:
            continue
        independent = m["name"] == "SootopolisCity"
        row = json.loads((root / "解码" / (layouts[m["layout"]]["name"] + ".json")).read_text())
        width, height = row["width"], row["height"]
        tid = "hoenn-" + m["name"].lower()
        ground, over = [Image.open(root / row["layers"][k]["path"]).convert("RGBA")
                        for k in ["ground", "over"]]
        chunks = []
        for y in range(0, height, 32):
            for x in range(0, width, 32):
                w, h = min(32, width - x), min(32, height - y)
                chunk = {"x": x * size, "y": y * size, "w": w * size, "h": h * size}
                for key, image in [("ground", ground), ("over", over)]:
                    crop = image.crop((x * 16, y * 16, (x + w) * 16, (y + h) * 16))
                    if crop.getbbox():
                        chunk[key] = emit(f"{m['name']}-{x}-{y}-{key}.png", crop)
                chunks.append(chunk)
        preview = ground.copy()
        preview.alpha_composite(over)
        preview.thumbnail((400, 250), Image.Resampling.NEAREST)
        ref = emit(m["name"] + "-preview.png", preview)
        blank = emit("blank.png", Image.new("RGBA", (1, 1)))
        walk = bytearray(c == 0 and b not in blocked
                         for c, b in zip(row["collision"], row["behavior"]))
        world = {"width": width * size, "height": height * size}
        area = {"id": m["id"], "sourceName": m["name"], "name": "琉璃市" if independent else INTERIORS[m["name"]],
                "x": 0, "y": 0, "w": world["width"], "h": world["height"],
                "gridX": 0, "gridY": 0, "columns": width, "rows": height,
                "sourceLayout": row["id"]}
        terrain = {"id": tid, "cellSize": size, "columns": width, "rows": height,
                   "walkB64": encoded(walk), "chunks": chunks, "areas": [area],
                   "world": world, "fieldEffects": main["fieldEffects"], "seams": []}
        for key in ["collision", "behavior", "elevation"]:
            terrain[key + "B64"] = encoded(row[key])
        catalog["terrains"].append(terrain)
        spawn = m["warp_events"][0]
        point = {"x": (spawn["x"] + .5) * size, "y": (spawn["y"] + .5) * size, "a": 0}
        enemy = {**point, "y": point["y"] - size}
        if independent:
            candidates = [(x, y) for y in range(2, height - 2) for x in range(2, width - 7)
                          if all(walk[(y + dy) * width + x + dx]
                                 for dy in (0,) for dx in range(6))]
            x, y = min(candidates, key=lambda p: (p[0] - width/2)**2 + (p[1] - height*.6)**2)
            point = {"x": (x + .5) * size, "y": (y + .5) * size, "a": 0}
            enemy = {**point, "x": point["x"] + 5 * size, "a": 3.141592653589793}
        terrain["streaming"] = True
        scene = {"id": "emerald-" + m["name"].lower(), "terrainID": tid,
                 "name": area["name"], "description": "独立城市起点（本轮不做水下入口）" if independent else "由原版入口进入，保留当前对局",
                 "entranceOnly": not independent, "darkness": .19 if m["name"] == "RusturfTunnel" else 0,
                 "world": world, "bounds": {"left": 18, "top": 18,
                                             "right": world["width"] - 18,
                                             "bottom": world["height"] - 18},
                 "spawns": {"player": point, "enemy": enemy},
                 "sprites": [], "collisionContract": [], "areaID": m["id"],
                 "sourceCommit": index["sourceCommit"]}
        for key, asset in [("ground", ref), ("preview", ref), ("objects", blank)]:
            scene[key] = asset["path"]
            scene[key + "SHA256"] = asset["sha256"]
        catalog["scenes"].append(scene)

    owners = {}
    for terrain in catalog["terrains"]:
        terrain["capabilities"] = dict(CAPABILITIES)
        attach(terrain)
        add_bridges(terrain, maps)
        terrain["warps"] = []
        for area in terrain["areas"]:
            owners[area["id"]] = (terrain, area)
    for scene in catalog["scenes"]:
        scene["capabilities"] = dict(CAPABILITIES)
    scene_for = {t["id"]: next(s["id"] for s in catalog["scenes"] if s["terrainID"] == t["id"])
                 for t in catalog["terrains"]}
    for mid, (terrain, area) in owners.items():
        for number, warp in enumerate(maps[mid].get("warp_events", [])):
            dest = warp["dest_map"]
            if dest not in owners or not ({maps[mid]["name"], maps[dest]["name"]} & INTERIORS.keys()):
                continue
            other, target_area = owners[dest]
            target_id = int(warp["dest_warp_id"])
            target = maps[dest]["warp_events"][target_id]
            terrain["warps"].append({
                "id": f"{mid}:{number}", "sourceMap": mid, "sourceWarp": number,
                "col": area["gridX"] + warp["x"], "row": area["gridY"] + warp["y"],
                "destScene": scene_for[other["id"]], "destMap": dest, "destWarp": target_id,
                "x": (target_area["gridX"] + target["x"] + .5) * size,
                "y": (target_area["gridY"] + target["y"] + .5) * size,
            })
    ledges = relax_traps(catalog)
    (root / '双向台阶登记.json').write_text(json.dumps(ledges, ensure_ascii=False, indent=2) + '\n')
    catalog["limitations"] = [
        "49 connected outdoor maps, independent Sootopolis, PetalburgWoods and RusturfTunnel",
        "No NPC/story/items/underwater maps; Frontier and Safari not in component",
        "Free exploration behavior table with height-preserving bridge layers across all maps",
        "Cycling gatehouse interiors omitted: paired original exterior-door approaches connect directly",
        "Route110 elevation-0 aprons join deck to land; building collision stays original",
        "16 town menu presets restart matches; original entrance warps preserve resources",
    ]
    return catalog
