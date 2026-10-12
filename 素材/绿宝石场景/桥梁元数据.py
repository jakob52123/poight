"""Original Route110 bridge cells, with separate deck and underpass masks.
Elevation 15 retains actor height upstream. Elevation 0 door aprons are the
only deck/land transitions here (gatehouse interiors are deliberately omitted).
"""
import base64


def add_bridges(terrain, maps):
    decode = lambda key: base64.b64decode(terrain[key + "B64"])
    behavior, collision, elevation = map(decode, ["behavior", "collision", "elevation"])
    n = len(behavior)
    deck, land, water, gateway = (bytearray(n) for _ in range(4))
    cols = terrain["columns"]
    cycling = bytearray(n)
    rules = terrain.get("traversalRules", {})
    # The W2 table remains the surface authority. Layers are derived for every
    # source area, not just the old 13-map component; source bytes stay intact.
    for i, b in enumerate(behavior):
        rule = rules.get(str(b), {})
        if b == 0x2b and collision[i] == 0 and elevation[i] == 3:
            land[i] = 1  # F1 wooden reflection deck, not swimming water.
        if rule.get("mode") != "bridge":
            continue
        if collision[i] and not rule.get("overrideCollision"):
            continue
        z = elevation[i]
        deck[i] = z in {4, 15}
        if z == 15:
            land[i] = b == 0x78  # Fortree's road under the treetop bridge.
            water[i] = b != 0x78
        elif z == 1:
            water[i] = 1
    route = next((a for a in terrain["areas"] if a["sourceName"] == "Route110"), None)
    for y in range(route["rows"] if route else 0):
        # Original multi-level crossing height comes from the row's adjacent
        # non-bridge walkable cells: land=3, ocean=1. Do not invent artwork.
        heights = set()
        for x in range(route["columns"]):
            i = (route["gridY"] + y) * cols + route["gridX"] + x
            if collision[i] == 0 and elevation[i] == 15 and behavior[i] == 0x70:
                for j in [i - 1, i + 1]:
                    if collision[j] == 0 and elevation[j] in {1, 3}:
                        heights.add(elevation[j])
        below = 3 if 3 in heights else 1
        for x in range(route["columns"]):
            i = (route["gridY"] + y) * cols + route["gridX"] + x
            cycling[i] = 1
            if collision[i] != 0 or behavior[i] not in {0x70, 0x7f}:
                continue
            z = elevation[i]
            deck[i] = z in {0, 4, 15}
            gateway[i] = z == 0
            land[i] = z == 15 and below == 3
            water[i] = z == 1 or (z == 15 and below == 1)
    terrain["bridges"] = {key + "B64": base64.b64encode(mask).decode()
                          for key, mask in [("deck", deck), ("land", land),
                                            ("water", water), ("gateway", gateway),
                                            ("cycling", cycling)]}
    if route is None:
        terrain["bridges"]["gates"] = []
        return
    # Gatehouse interiors are out of scope. Pair their two ORIGINAL outdoor
    # animated-door events, using the walkable approach immediately south.
    # Never open the collision=1 door/building tiles or invent a new map.
    events = maps[route["id"]]["warp_events"]
    gates = []
    for number, event in enumerate(events):
        if "SEASIDE_CYCLING_ROAD" not in event["dest_map"]:
            continue
        other_number, other = next((j, v) for j, v in enumerate(events)
                                   if j != number and v["dest_map"] == event["dest_map"])
        def approach(v):
            return (route["gridY"] + v["y"] + 1) * cols + route["gridX"] + v["x"]
        assert collision[approach(event)] == collision[approach(other)] == 0
        gates.append({"from": approach(event), "to": approach(other),
                      "gateMap": event["dest_map"],
                      "sourceEvent": number, "targetEvent": other_number})
    assert len(gates) == 4
    terrain["bridges"]["gates"] = gates
    terrain["bridges"]["policy"] = (
        "Route110 original heights; height-0 aprons join deck to land; "
        "omitted gatehouse interiors replaced by paired exterior-door approach shortcuts"
    )
