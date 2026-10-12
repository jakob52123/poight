"""Offline body calibration, preserving native sprite shapes and animations.
Pokédex dimensions are source facts; rendering, hurt shapes and speed are
explicit project adaptations, not real-world physics or main-series formulas.
"""

from pathlib import Path
from statistics import median
import hashlib, json, math
from PIL import Image

LONG_BODY = {95, 130, 147, 148, 208}  # serpentine length, NOT upright standing height
clamp = lambda x, a, b: max(a, min(b, x))


def apply(metadata, rows, root, lib):
    directory = root / "数值资料/体型校准"
    source = json.loads((directory / "来源.json").read_text())
    assert not source["errors"] and source["count"] == 50
    facts = {s["id"]: s for s in source["species"]}
    assert set(facts) == {c["id"] for c in rows}
    lookup = {c["id"]: c for c in rows}
    records = []
    for c in metadata:
        n = c["id"]
        f = facts[n]
        raw = directory / f["raw"]
        payload = raw.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == f["sha256"]
        data = json.loads(payload)
        assert data["id"] == n and data["is_default"]
        h, w = data["height"] / 10, data["weight"] / 10
        speed = next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "speed")
        assert (
            h > 0
            and w > 0
            and (data["height"], data["weight"], speed)
            == (f["heightDm"], f["weightHg"], f["baseSpeed"])
        )
        a = lookup[n]["art"]["idle"]
        path = lib / a["file"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == lookup[n]["audit"][a["sourceAnimation"]]["sha256"]
        )
        im = Image.open(path).convert("RGBA")
        by_row = []
        tops = []
        for row in range(a["rows"]):
            widths = []
            heights = []
            for frame in range(a["frames"]):
                x, y = frame * a["frameWidth"], row * a["frameHeight"]
                bb = im.crop((x, y, x + a["frameWidth"], y + a["frameHeight"])).getbbox()
                assert bb
                widths.append(bb[2] - bb[0])
                heights.append(bb[3] - bb[1])
                off = a.get("bodyOffsets", [[[0, 0]] * a["frames"]] * a["rows"])[row][frame]
                tops.append(a["anchorY"] + off[1] - bb[1])
            by_row.append([median(widths), median(heights)])
        mh = median(v[1] for v in by_row)
        mw = median(v[0] for v in by_row)
        long = n in LONG_BODY
        if long:
            # A coiled sprite cannot be scaled as an upright 9.2 m tower.
            # Target its visible longest extent, not a claimed true standing height.
            mass_factor = clamp((w / (18 * h)) ** 0.05, 0.88, 1.14)
            nominal = clamp(54 * math.sqrt(h / 1.8) * mass_factor, 40, 128)
            reference = median(max(v) for v in by_row)
        else:
            # Compressed height ratio with a bounded mass/volume adjustment.
            # Never stretch width alone, and weight alone cannot shrink gaseous species to zero.
            mass_factor = clamp((w / (20 * h**3)) ** 0.08, 0.86, 1.15)
            nominal = clamp(48 * h**0.55 * mass_factor, 26, 86)
            reference = mh
        scale = round(nominal / reference, 4)
        radius = clamp(nominal * 0.32, 10, 30)
        shapes = []
        for aw, ah in by_row:
            rx = (
                clamp(aw * scale * 0.42, 12, 48)
                if long
                else clamp(aw * scale * 0.36, radius * 0.72, radius * 1.18)
            )
            ry = clamp(ah * scale * 0.32, 10, 26) if long else radius * 0.82
            shapes.append([round(rx, 2), round(ry, 2)])
        if len(shapes) == 1:
            shapes *= 8
        assert len(shapes) == 8
        # Size dominates locomotion; species speed supplies a modest individual difference.
        # Dash/rush/attack speeds, immunity, resource costs and damage are NOT changed here.
        walk_speed = round(clamp(210 - 0.78 * (nominal - 48) + 0.12 * (speed - 70), 160, 230))
        body = {
            "heightMeters": h,
            "weightKg": w,
            "baseSpeed": speed,
            "dimensionMode": "coiled-length" if long else "height",
            "nominalSize": round(nominal, 2),
            "massFactor": round(mass_factor, 4),
            "referencePixels": [mw, mh],
            "visibleSize": [round(mw * scale, 2), round(mh * scale, 2)],
            "hurtByDirection": shapes,
            "moveRadius": round(clamp(radius * 0.78, 10, 20), 2),
            "top": round(max(tops) * scale - 14, 2),
            "effectScale": round(clamp(scale / c["scale"], 0.72, 1.35), 3),
            "sourceSHA256": f["sha256"],
            "mapping": "compressed-size-v1; ellipse core, not pixel-perfect anatomy",
        }
        records.append(
            {
                "id": n,
                "name": c["name"],
                "oldScale": c["scale"],
                "oldSpeed": c["speed"],
                "scale": scale,
                "speed": walk_speed,
                "body": body,
            }
        )
        c.update(scale=scale, speed=walk_speed, body=body)
    receipt = {
        "policy": "Candidate balance adaptation, not approved final balance. Native artwork/aspect ratios and six role animations preserved.",
        "count": len(records),
        "sourceReceiptSHA256": hashlib.sha256((directory / "来源.json").read_bytes()).hexdigest(),
        "mapping": {
            "normal": "clamp(48 * height_m^.55 * clamp((weight_kg/(20*height_m^3))^.08,.86,1.15),26,86)",
            "serpentine": "longest visible extent = clamp(54*sqrt(length_m/1.8)*clamp((weight_kg/(18*length_m))^.05,.88,1.14),40,128)",
            "walk": "clamp(round(210-.78*(nominalSize-48)+.12*(baseSpeed-70)),160,230)",
            "hurt": "8-direction core ellipses; circular ground footprint capped at20px for48px map cells",
        },
        "unchanged": [
            "roster50",
            "moves120",
            "HP",
            "move damage/cost/CD",
            "dash speed/duration/protection/cost",
            "art source pixels",
            "no evolution",
        ],
        "notProven": [
            "win-rate balance",
            "pixel-perfect anatomical hurtboxes",
            "jump/height collision",
            "all large-species sprite redesign as new art",
        ],
        "species": records,
    }
    (directory / "映射记录.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    return receipt
