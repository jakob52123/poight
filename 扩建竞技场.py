"""Recompose six arenas at 1050×700 art pixels / 2100×1400 world pixels.

Original PNG/annotations remain immutable. All crops are from the approved originals;
no character assets, API generation, interpolation or full-image stretching is used.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
SOURCE = ROOT / "素材/竞技场"
OUTPUT = SOURCE / "扩建"
WORLD = (2100, 1400)


def box(kind, x, y, w, h, ident):
    return {"id": ident, "kind": kind, "type": "rect", "x": x / 2100,
            "y": y / 1400, "width": w / 2100, "height": h / 1400}


def tile(canvas, patch, region):
    x, y, right, bottom = region
    for yy in range(y, bottom, patch.height):
        for xx in range(x, right, patch.width):
            canvas.paste(patch.crop((0, 0, min(patch.width, right - xx),
                                    min(patch.height, bottom - yy))), (xx, yy))


def build(names=("正规场", "自然场")):
    OUTPUT.mkdir(exist_ok=True)
    for name in names:
        for variant in "ABC":
            stem = f"{name}-{variant}"
            source = Image.open(SOURCE / (stem + ".png")).convert("RGB")
            old = json.loads((SOURCE / (stem + ".json")).read_text())
            canvas = Image.new("RGB", (1050, 700))
            # Plain ground crop deliberately excludes painted lines/grass/rocks.
            crop = (300, 350, 420, 470) if name == "正规场" else (210, 400, 330, 520)
            patch = source.crop(crop).resize((60, 60), Image.Resampling.NEAREST)
            tile(canvas, patch, (0, 0, 1050, 700))
            obstacles, grasses = [], []
            draw = ImageDraw.Draw(canvas)
            if name == "正规场":
                # Original stands and corner flags; bare ground continues to the stands.
                approved = Image.open(SOURCE / "正规场-A.png").convert("RGB")
                stand = approved.crop((245, 0, 425, 60)).resize((90, 30), Image.Resampling.NEAREST)
                tile(canvas, stand, (0, 0, 1050, 30))
                tile(canvas, stand, (0, 670, 1050, 700))
                tile(canvas, stand.rotate(90, expand=True), (0, 30, 30, 670))
                tile(canvas, stand.rotate(90, expand=True), (1020, 30, 1050, 670))
                flag = approved.crop((77, 59, 137, 139)).resize((30, 40), Image.Resampling.NEAREST)
                for x in (30, 990):
                    for y in (28, 630):
                        canvas.paste(flag, (x, y))
                white = "#f3e7c8"
                draw.rectangle((95, 90, 955, 610), outline=white, width=3)
                draw.line((525, 90, 525, 610), fill=white, width=3)
                for x in (75, 955):
                    draw.rectangle((x, 320, x + 20, 380), outline=white, width=3)
                # 480 world-pixel diameter. Draw directly on the art grid, not scaled old logo.
                draw.ellipse((405, 230, 645, 470), fill=white)
                draw.pieslice((409, 234, 641, 466), 180, 360, fill="#d45e52")
                draw.pieslice((409, 234, 641, 466), 0, 180, fill="#ded8c6")
                draw.rectangle((409, 346, 641, 354), fill="#515867")
                draw.ellipse((485, 310, 565, 390), fill="#515867")
                draw.ellipse((496, 321, 554, 379), fill=white)
                # The visible stands themselves are the boundary (zero invisible margin).
                for i, (kind, x, y, w, h) in enumerate([
                    ("stands", 0, 0, 2100, 60), ("stands", 0, 1340, 2100, 60),
                    ("stands", 0, 60, 60, 1280), ("stands", 2040, 60, 60, 1280),
                ]):
                    obstacles.append({**box(kind, x, y, w, h, f"{stem}-border-{i}"),
                                      "perimeter": True})
                for i, (x, y) in enumerate([(60, 56), (1980, 56), (60, 1260), (1980, 1260)]):
                    obstacles.append({**box("flag", x, y, 60, 80, f"{stem}-flag-{i}"),
                                      "perimeter": True})
                area = box("battle", 60, 60, 1980, 1280, "battle")
            else:
                # Border strips retain trees/rock walls without doubling their scale.
                for crop_box, dest, size in [
                    ((0, 0, 1536, 96), (0, 0), (768, 48)),
                    ((0, 928, 1536, 1024), (0, 652), (768, 48)),
                ]:
                    strip = source.crop(crop_box).resize(size, Image.Resampling.NEAREST)
                    tile(canvas, strip, (dest[0], dest[1], 1050, dest[1] + size[1]))
                strip = source.crop((0, 100, 90, 900)).resize((45, 400), Image.Resampling.NEAREST)
                tile(canvas, strip, (0, 48, 45, 652))
                strip = source.crop((1446, 100, 1536, 900)).resize((45, 400), Image.Resampling.NEAREST)
                tile(canvas, strip, (1005, 48, 1050, 652))
                rocks = [o for o in old["obstacles"] if o["kind"] == "rock"]
                count = len(rocks) * 4
                cols = math.ceil(count / 4)
                for i in range(count):
                    o = rocks[i % len(rocks)]
                    x = 290 + (i % cols) * (1510 / max(1, cols - 1))
                    x = round((x + [-24, 18, -8, 26, 0][i % 5]) / 2) * 2
                    y = [276, 496, 876, 1106][i // cols] + [-12, 16, 0, 8][i % 4]
                    w, h = round(o["width"] * 1536), round(o["height"] * 1024)
                    sx, sy = round(o["x"] * 1536), round(o["y"] * 1024)
                    # Include original shadow in the art but only annotated solid in collision.
                    part = source.crop((sx - 4, sy - 4, sx + w + 20, sy + h + 10))
                    canvas.paste(part.resize((part.width // 2, part.height // 2),
                                            Image.Resampling.NEAREST), (round(x / 2) - 2, round(y / 2) - 2))
                    obstacles.append(box("rock", round(x), y, w, h, f"{stem}-rock-{i+1:02}"))
                for i in range(len(old["grassRegions"]) * 4):
                    g = old["grassRegions"][i % len(old["grassRegions"])]
                    cols = len(old["grassRegions"])
                    x, y = 495 + (i % cols) * 510, [220, 455, 845, 1080][i // cols]
                    sx, sy = round(g["x"] * 1536), round(g["y"] * 1024)
                    w, h = round(g["width"] * 1536), round(g["height"] * 1024)
                    # Place whole walkable grass boxes clear of every rock and each other.
                    candidates = [(x + dx, y + dy) for dy in [0, -90, 100, -160, 160, 200, 400, 600]
                                  for dx in [0, -160, 160, -260, 260, -360, 360]]
                    candidates += [(xx, yy) for yy in range(130, 1260, 20)
                                   for xx in range(150, 1940, 40)]
                    for xx, yy in candidates:
                        if xx < 150 or xx + w > 1940 or yy < 130 or yy + h > 1270:
                            continue
                        if all(xx + w + 24 <= o["x"] * 2100 or
                               xx - 24 >= (o["x"] + o["width"]) * 2100 or
                               yy + h + 24 <= o["y"] * 1400 or
                               yy - 24 >= (o["y"] + o["height"]) * 1400
                               for o in obstacles + grasses):
                            x, y = xx, yy
                            break
                    else:
                        raise ValueError((stem, i, "grass placement"))
                    x, y = x // 2 * 2, y // 2 * 2
                    part = source.crop((sx, sy, sx + w, sy + h))
                    canvas.paste(part.resize((w // 2, h // 2), Image.Resampling.NEAREST), (x // 2, y // 2))
                    grasses.append({**box("tall_grass", x, y, w, h, f"{stem}-grass-{i+1:02}"),
                                    "walkable": True, "conceals": True})
                for i, (x, y, w, h) in enumerate([(0, 0, 2100, 96), (0, 1304, 2100, 96),
                                                  (0, 96, 90, 1208), (2010, 96, 90, 1208)]):
                    obstacles.append({**box("rock_wall" if variant == "C" else "trees_and_bushes",
                                            x, y, w, h, f"{stem}-border-{i}"), "perimeter": True})
                area = box("battle", 110, 110, 1880, 1180, "battle")
            annotation = {"schemaVersion": 2, "image": stem + ".png",
                          "world": {"width": 2100, "height": 1400},
                          "artPixelWorldSize": 2, "logoDiameter": 480 if name == "正规场" else None,
                          "annotationMethod": "扩建竞技场.py: exact composited pixel coordinates",
                          "battleArea": area, "obstacles": obstacles, "grassRegions": grasses,
                          "spawns": [{"side": "left", "x": .275, "y": .5},
                                     {"side": "right", "x": .725, "y": .5}]}
            canvas.save(OUTPUT / (stem + ".png"))
            (OUTPUT / (stem + ".json")).write_text(json.dumps(annotation, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-only", action="store_true",
                        help="Regenerate only formal A/B/C; never write natural assets")
    args = parser.parse_args()
    build(("正规场",) if args.formal_only else ("正规场", "自然场"))
