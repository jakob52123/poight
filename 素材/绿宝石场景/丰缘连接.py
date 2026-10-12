"""Original outdoor component, deterministic spanning tree, explicit seam receipts."""
from collections import deque

from 自由探索 import legal as traversal_legal

OUTDOOR = {"MAP_TYPE_" + t for t in ("TOWN", "CITY", "ROUTE", "OCEAN_ROUTE")}
NAMES = {
    "LittlerootTown": "未白镇", "OldaleTown": "古辰镇", "PetalburgCity": "橙华市",
    "RustboroCity": "卡那兹市", "SlateportCity": "凯那市", "MauvilleCity": "紫堇市",
    "DewfordTown": "武斗镇", "VerdanturfTown": "绿荫镇", "FallarborTown": "秋叶镇",
    "LavaridgeTown": "釜炎镇", "FortreeCity": "茵郁市", "LilycoveCity": "水静市",
    "MossdeepCity": "绿岭市", "EverGrandeCity": "彩幽市", "PacifidlogTown": "暮水镇",
    "SootopolisCity": "琉璃市",
}


def connected(index, rows):
    outdoor = {m["id"]: m for m in index["maps"] if m["map_type"] in OUTDOOR}
    positions = {"MAP_LITTLEROOT_TOWN": (0, 0)}
    queue = deque(positions)

    def expected(k, c):
        x, y = positions[k]
        w, h = rows[k]["width"], rows[k]["height"]
        other = rows[c["map"]]
        o = c["offset"]
        return {"up": (x + o, y - other["height"]), "down": (x + o, y + h),
                "left": (x - other["width"], y + o), "right": (x + w, y + o)}[c["direction"]]

    while queue:
        k = queue.popleft()
        for c in outdoor[k].get("connections") or []:
            n = c["map"]
            if n not in outdoor or c["direction"] not in ("up", "down", "left", "right"):
                continue
            if n not in positions:
                positions[n] = expected(k, c)
                queue.append(n)
    original = dict(positions)
    # Route116 overlaps Verdanturf by two rows in the original connection graph.
    # Move only Verdanturf south, keeping every rectangle disjoint and every delta <=2.
    x, y = positions["MAP_VERDANTURF_TOWN"]
    positions["MAP_VERDANTURF_TOWN"] = (x, y + 2)
    corrections = [{"map": k, "tree": list(original[k]), "corrected": list(v),
                    "delta": [v[0] - original[k][0], v[1] - original[k][1]]}
                   for k, v in positions.items() if v != original[k]]
    edges = []
    for k in positions:
        for c in outdoor[k].get("connections") or []:
            if c["map"] not in positions or c["direction"] not in ("up", "down", "left", "right"):
                continue
            want, actual = expected(k, c), positions[c["map"]]
            shift = [actual[0] - want[0], actual[1] - want[1]]
            assert max(map(abs, shift)) <= 2, (k, c, shift)
            edges.append({"from": k, "to": c["map"], **c, "shift": shift})
    return ({k: outdoor[k] for k in positions}, positions, edges,
            {"units": "48px metatile; positions relative to Littleroot before padding",
             "corrections": corrections,
             "excluded": [k for k in outdoor if k not in positions]})


def seam_pairs(seams, positions, rows, width, walk, water, elevation, behavior):
    def legal(a, b):
        return ((walk[a] or water[a]) and (walk[b] or water[b]) and
                traversal_legal(a, b, width, behavior, elevation, water))

    for edge in seams:
        k, n = edge["from"], edge["to"]
        x, y = positions[k]
        xx, yy = positions[n]
        w, h = rows[k]["width"], rows[k]["height"]
        nw, nh = rows[n]["width"], rows[n]["height"]
        dx, dy = edge["shift"]
        pairs, land = [], []
        direction = edge["direction"]
        for i in range(h if direction in ("left", "right") else w):
            if direction == "left":
                a, b = (x, y + i), (x - 1 + dx, y + i + dy)
            elif direction == "right":
                a, b = (x + w - 1, y + i), (x + w + dx, y + i + dy)
            elif direction == "up":
                a, b = (x + i, y), (x + i + dx, y - 1 + dy)
            else:
                a, b = (x + i, y + h - 1), (x + i + dx, y + h + dy)
            if not (xx <= b[0] < xx + nw and yy <= b[1] < yy + nh):
                continue
            ai, bi = a[1] * width + a[0], b[1] * width + b[0]
            if legal(ai, bi):
                pairs.append([*a, *b])
                if walk[ai] and walk[bi]:
                    land.append([*a, *b])
        edge["pairs"] = pairs
        # Legacy regression suite walks cardinal unshifted land edges.
        edge["walkablePairs"] = land if not any(edge["shift"]) else []
        if any(edge["shift"]):
            assert pairs, ("unwalkable registered seam", edge)
