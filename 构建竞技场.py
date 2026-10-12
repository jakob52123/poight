"""只打包目录选中的竞技场；未选变体不进入发布清单/HTTP 白名单。"""

import hashlib
import json
import math

from PIL import Image


def build(root, output):
    folder = root / "素材/竞技场"
    catalog = json.loads((folder / "竞技场目录.json").read_text())
    world = catalog["world"]
    assert world == {"width": 2100, "height": 1400}
    folder = folder / catalog["assetFolder"]
    width, height = world["width"], world["height"]

    def rect(value):
        assert value["type"] == "rect", "未支持的几何类型，不能静默丢失障碍"
        return {
            **value,
            "x": value["x"] * width,
            "y": value["y"] * height,
            "width": value["width"] * width,
            "height": value["height"] * height,
        }

    scenes = []
    for entry in catalog["scenes"]:
        if not entry["enabled"]:
            continue
        assert entry["variant"] in "ABC" and len(entry["variant"]) == 1
        stem = entry["name"] + "-" + entry["variant"]
        annotation = json.loads((folder / (stem + ".json")).read_text())
        assert annotation["world"] == world
        assert annotation["artPixelWorldSize"] == 2
        image = folder / (stem + ".png")
        with Image.open(image) as im:
            assert im.size == (width // 2, height // 2)
            im.verify()
        png = image.read_bytes()
        digest = hashlib.sha256(png).hexdigest()
        src = output("arena-" + digest[:12] + ".png", png)
        area = rect(annotation["battleArea"])
        spawns = annotation["spawns"]
        assert len(spawns) == 2
        points = [{"x": s["x"] * width, "y": s["y"] * height} for s in spawns]
        angle = math.atan2(points[1]["y"] - points[0]["y"], points[1]["x"] - points[0]["x"])
        scenes.append({
            **entry,
            "type": "arena",
            "world": world,
            "logoDiameter": annotation.get("logoDiameter"),
            "artPixelWorldSize": annotation["artPixelWorldSize"],
            "description": "跟随镜头 · " + ("白线正规场" if entry["id"] == "arena-formal" else "岩石掩体与高草"),
            "groundSrc": src,
            "objectsSrc": src,
            "previewSrc": src,
            "battleArea": area,
            "bounds": {"left": area["x"], "top": area["y"],
                       "right": area["x"] + area["width"], "bottom": area["y"] + area["height"]},
            "collisionContract": [
                {**r, "w": r["width"], "h": r["height"]}
                for r in map(rect, annotation["obstacles"])
            ],
            "grassRegions": list(map(rect, annotation.get("grassRegions", []))),
            "spawns": {"player": {**points[0], "a": angle},
                       "enemy": {**points[1], "a": angle + math.pi}},
            "sprites": [],
        })
    return scenes, catalog["default"]
