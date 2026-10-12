"""Compile behavior policies without modifying original collision/elevation/graphics."""
import json
from pathlib import Path

RULES = json.loads((Path(__file__).parent / "自由探索通行表.json").read_text())
BEHAVIORS = {int(k, 16): v for k, v in RULES["behaviors"].items()}


def masks(collision, behavior):
    walk, water = bytearray(len(collision)), bytearray(len(collision))
    for i, (c, b) in enumerate(zip(collision, behavior)):
        rule = BEHAVIORS.get(b, {})
        mode = rule.get("mode")
        if mode == "water":
            water[i] = int(c == 0 or rule.get("overrideCollision", False))
        elif mode in ("land", "bridge", "ledge"):
            walk[i] = int(c == 0 or rule.get("overrideCollision", False))
        else:
            walk[i] = int(c == 0 and not (0x30 <= b <= 0x3f or 0x70 <= b <= 0x7f or 0xd0 <= b <= 0xd7)
                          and b not in (0x18, 0x19, 0x1a, 0x2a, 0x2b))
    return walk, water


def legal(a, b, columns, behavior, elevation, water, bidirectional=()):
    dx, dy = b % columns - a % columns, b // columns - a // columns
    for at in (a, b):
        r = BEHAVIORS.get(behavior[at], {})
        if r.get("mode") == "ledge" and at not in bidirectional:
            vx, vy = r["direction"]
            if dx * vx + dy * vy <= 0:
                return False
    return (elevation[a] == elevation[b] or elevation[a] in (0, 15) or elevation[b] in (0, 15)
            or any(BEHAVIORS.get(behavior[i], {}).get("elevationLink") for i in (a, b))
            or ((water[a] or water[b]) and {elevation[a], elevation[b]} <= {1, 3}))


def attach(terrain):
    import base64
    collision, behavior = [base64.b64decode(terrain[k + "B64"]) for k in ("collision", "behavior")]
    walk, water = masks(collision, behavior)
    terrain["walkB64"] = base64.b64encode(walk).decode()
    terrain["waterB64"] = base64.b64encode(water).decode()
    terrain["traversalRules"] = {str(k): v for k, v in BEHAVIORS.items()}
    terrain["bidirectionalLedges"] = []
