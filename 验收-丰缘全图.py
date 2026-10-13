"""Full component/geometry + real keyboard seams, cities, streaming and sea traversal."""
import base64
import hashlib
import json
import math
import os
import sys
from collections import deque
from itertools import pairwise
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
ENV = ROOT / "素材/绿宝石场景"
OUT = ROOT / "验收记录/丰缘全图"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8865/").rstrip("/")
sys.path.insert(0, str(ENV))
from 丰缘连接 import OUTDOOR
from 自由探索 import legal

checks, errors = [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def wait(page, expr):
    for _ in range(1200):
        if page.evaluate(expr):
            return
        page.wait_for_timeout(30)
    raise AssertionError(expr)


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def call(page, method, value=None):
    return page.evaluate("v=>window.__waterTest[v.method](v.value)", {"method": method, "value": value})


def move(page, key, seconds):
    page.keyboard.down(key)
    call(page, "step", seconds)
    page.keyboard.up(key)


def cell(point, size=48):
    return {"x": (point[0] + .5) * size, "y": (point[1] + .5) * size}


try:
    catalog = json.loads((ENV / "场景目录.json").read_text())
    index = json.loads((ENV / "地图索引.json").read_text())
    t = catalog["terrains"][0]
    cols, rows, size = t["columns"], t["rows"], t["cellSize"]
    walk, water, elevation = [base64.b64decode(t[k + "B64"]) for k in ("walk", "water", "elevation")]
    maps = {m["id"]: m for m in index["maps"] if m["map_type"] in OUTDOOR}
    component, queue = {"MAP_LITTLEROOT_TOWN"}, deque(["MAP_LITTLEROOT_TOWN"])
    while queue:
        for edge in maps[queue.popleft()].get("connections") or []:
            target = edge["map"]
            if target in maps and target not in component and edge["direction"] in ("left", "right", "up", "down"):
                component.add(target)
                queue.append(target)
    names = [a["sourceName"] for a in t["areas"]]
    print("户外连通分量", len(names), json.dumps(names, ensure_ascii=False), flush=True)
    check("Exact outdoor component", {a["id"] for a in t["areas"]} == component and len(component) == 49, names)
    check("Independent Sootopolis; no Frontier or Safari", catalog["terrains"][-1]["areas"][0]["id"] == "MAP_SOOTOPOLIS_CITY"
          and not any("FRONTIER" in k or "SAFARI" in k for k in component))
    areas = {a["id"]: a for a in t["areas"]}
    for a in t["areas"]:
        for b in t["areas"]:
            if a["id"] >= b["id"]:
                continue
            check("No overlap " + a["sourceName"] + "/" + b["sourceName"],
                  min(a["x"] + a["w"], b["x"] + b["w"]) <= max(a["x"], b["x"])
                  or min(a["y"] + a["h"], b["y"] + b["h"]) <= max(a["y"], b["y"]))
    receipt = json.loads((ENV / "接缝表.json").read_text())
    check("Corrections at most two cells", all(max(map(abs, c["delta"])) <= 2 for c in receipt["corrections"]))
    registered = {(e["from"], e["to"]): e for e in receipt["seams"]}
    for edge in t["seams"]:
        a, b = areas[edge["from"]], areas[edge["to"]]
        x, y, o = a["gridX"], a["gridY"], edge["offset"]
        want = {"left": (x - b["columns"], y + o), "right": (x + a["columns"], y + o),
                "up": (x + o, y - b["rows"]), "down": (x + o, y + a["rows"])}[edge["direction"]]
        delta = [b["gridX"] - want[0], b["gridY"] - want[1]]
        check("Geometry original or registered " + edge["from"] + "/" + edge["to"],
              not any(delta) or registered[(edge["from"], edge["to"])]["shift"] == delta)
    check("Bridge elevation/collision metadata retained", all(len(base64.b64decode(t[k + "B64"])) == cols * rows
          for k in ("walk", "water", "collision", "behavior", "elevation")))
    policy = json.loads((ENV / '自由探索通行表.json').read_text())
    object_cells = []
    for a in t['areas']:
        for obj in maps[a['id']].get('object_events', []):
            if obj['graphics_id'] in policy['objectEvents']:
                at = (a['gridY'] + obj['y']) * cols + a['gridX'] + obj['x']
                object_cells.append((a['sourceName'], obj['graphics_id'], obj['x'], obj['y'], bool(walk[at] or water[at])))
    check('HM object tiles use traversable underlying ground', all(v[-1] for v in object_cells), object_cells)
    legacy = json.loads((OUT / 'M-fd1eb0f/素材/绿宝石场景/场景目录.json').read_text())
    for old in legacy['scenes']:
        if old.get('entranceOnly'):
            continue
        new = next(s for s in catalog['scenes'] if s['id'] == old['id'])
        a = next(a for a in legacy['terrains'][0]['areas'] if a['id'] == old['areaID'])
        b = areas[new['areaID']]
        check('Legacy local spawn preserved ' + old['id'], all(
            old['spawns'][side][axis] - a[axis] == new['spawns'][side][axis] - b[axis]
            for side in ('player', 'enemy') for axis in ('x', 'y')))
    # Every raw map cell remains byte-identical; behavior policies are separate masks.
    layouts = {v['id']: v for v in index['layouts']}
    for a in t['areas']:
        source = json.loads((ENV / '解码' / (layouts[maps[a['id']]['layout']]['name'] + '.json')).read_text())
        for key in ('collision', 'elevation', 'behavior'):
            values = base64.b64decode(t[key + 'B64'])
            check('Raw metadata ' + a['sourceName'] + '/' + key, all(
                values[(a['gridY'] + y) * cols + a['gridX'] + x] == source[key][y * a['columns'] + x]
                for y in range(a['rows']) for x in range(a['columns'])))

    # Reachability includes the already-contracted forest/tunnel walks, not fictional shortcuts.
    warp_links = {}
    for entry in t['warps']:
        scene = next(s for s in catalog['scenes'] if s['id'] == entry['destScene'])
        inner = next(v for v in catalog['terrains'] if v['id'] == scene['terrainID'])
        iw, iz = [base64.b64decode(inner[k + 'B64']) for k in ('walk', 'elevation')]
        ni = inner['columns']
        first = int(entry['y'] // size) * ni + int(entry['x'] // size)
        reached, todo = {first}, deque([first])
        while todo:
            a = todo.popleft()
            for b in (a - 1, a + 1, a - ni, a + ni):
                if 0 <= b < len(iw) and iw[b] and b not in reached and (
                        iz[a] == iz[b] or iz[a] in (0, 15) or iz[b] in (0, 15)):
                    reached.add(b)
                    todo.append(b)
        warp_links[entry['row'] * cols + entry['col']] = [
            int(w['y'] // size) * cols + int(w['x'] // size) for w in inner['warps']
            if w['row'] * ni + w['col'] in reached]

    behavior = base64.b64decode(t['behaviorB64'])
    seam_links = {}
    for edge in t['seams']:
        if any(edge['shift']):
            for x, y, xx, yy in edge['pairs']:
                seam_links.setdefault(y * cols + x, []).append(yy * cols + xx)
    def adjacent(at, wet_only=False):
        if not wet_only:
            yield from warp_links.get(at, [])
        yield from (v for v in seam_links.get(at, []) if not wet_only or water[v])
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x, y = at % cols + dx, at // cols + dy
            if not (0 <= x < cols and 0 <= y < rows):
                continue
            n = y * cols + x
            if not (water[n] if wet_only else walk[n] or water[n]):
                continue
            if legal(at, n, cols, behavior, elevation, water, t.get('bidirectionalLedges', [])):
                yield n

    def route(start, goal, wet_only=False):
        parents, q = {start: None}, deque([start])
        while q:
            at = q.popleft()
            if goal(at):
                path = []
                while at is not None:
                    path.append(at)
                    at = parents[at]
                return path[::-1]
            for n in adjacent(at, wet_only):
                if n not in parents:
                    parents[n] = at
                    q.append(n)
        return []

    def inside(at, map_id):
        a = areas[map_id]
        return a["gridX"] <= at % cols < a["gridX"] + a["columns"] and a["gridY"] <= at // cols < a["gridY"] + a["rows"]

    start = catalog["scenes"][0]["spawns"]["player"]
    start_at = int(start["y"] // size) * cols + int(start["x"] // size)
    graph = {i: list(adjacent(i)) for i in range(len(walk)) if walk[i] or water[i]}
    reverse = {i: [] for i in graph}
    for a, ns in graph.items():
        for b in ns:
            reverse.setdefault(b, []).append(a)
    def flood(edges):
        seen, q = {start_at}, deque([start_at])
        while q:
            for b in edges.get(q.popleft(), []):
                if b not in seen:
                    seen.add(b)
                    q.append(b)
        return seen
    forward, backward = flood(graph), flood(reverse)
    unreachable = [k for k in areas if not any(inside(a, k) for a in forward)]
    no_return = [k for k in areas if not any(inside(a, k) for a in forward & backward)]
    print('不可达地图', unreachable, '不能返回未白镇', no_return, flush=True)
    check('49 maps reachable from Littleroot', not unreachable, unreachable)
    check('49 maps can return to Littleroot', not no_return, no_return)
    long_path = route(start_at, lambda at: inside(at, "MAP_LILYCOVE_CITY"))
    check("Littleroot to Lilycove via original land/water and contracted forest/tunnel", bool(long_path), len(long_path))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL + "/?test=1")
        wait(page, "window.__waterTest?.snapshot().artReady")
        runtime_checks = page.evaluate((ROOT / '验收-自由探索.js').read_text())
        for item in runtime_checks:
            check(item['name'], item['ok'], item.get('detail'))
        base = snap(page)["profile"]
        check("Arena remains default", base["map"] == "arena-formal")
        base = {**base, "map": "emerald-littleroottown"}
        check("Initial main-world entry", call(page, "select", base))
        call(page, "reset", True)
        call(page, "arrange", {"ai": False})
        wait(page, "window.__waterTest.snapshot().environment.terrain.loading === 0")
        initial = snap(page)["environment"]["terrain"]
        check("Lazy initial textures < 1/4 of full chunks", initial["textures"] < len(t["chunks"]) / 4, initial)
        check("Initial visible chunks complete", initial["visibleMissing"] == 0)
        for name in ("mauvillecity", "fortreecity", "lilycovecity", "mossdeepcity", "evergrandecity", "sootopoliscity"):
            check("City entry " + name, call(page, "select", {**base, "map": "emerald-" + name}))
            call(page, "reset", True)
            call(page, "arrange", {"ai": False})
            state = snap(page)
            check("City loaded " + name, state["environment"]["terrain"]["visibleMissing"] == 0, state["environment"]["terrain"])
            if name == "mauvillecity":
                page.screenshot(path=str(SHOTS / "紫堇市-1440x900.png"))
            if name == "lilycovecity":
                later = state["environment"]["terrain"]
                check("Far textures actually evicted", later["evicted"] > 0 and not
                      (set(initial["residentSources"]) - {r for r in initial["residentSources"] if "grass" in r})
                      & set(later["residentSources"]), {"before": initial["textures"], "after": later["textures"], "evicted": later["evicted"]})
        call(page, "select", base)

        # All six directed misaligned seams; adjacent original cells walked with real keys.
        regular = [e for e in t["seams"] if not any(e["shift"]) and e["pairs"] and e["from"] < e["to"]][:10]
        for edge in [*receipt["seams"], *regular]:
            pair = edge["pairs"][len(edge["pairs"]) // 2]
            a, b = cell(pair[:2]), cell(pair[2:])
            call(page, "reset", True)
            call(page, "arrange", {"ai": False, "player": {**a, "hp": 57}, "enemy": start})
            check("Seam source " + edge["from"], snap(page)["environment"]["area"] == edge["from"])
            path = page.evaluate("v=>window.__waterTest.findPath(v.a.x,v.a.y,v.b.x,v.b.y)", {"a": a, "b": b})
            check("A* treats seam as neighbor " + edge["from"], 1 <= len(path) <= 2, path)
            key = {"left": "a", "right": "d", "up": "w", "down": "s"}[edge["direction"]]
            previous = snap(page)["player"]["seamVisualPosition"]
            largest = 0
            page.keyboard.down(key)
            for _ in range(22):
                call(page, "step", .02)
                p = snap(page)["player"]["seamVisualPosition"]
                largest = max(largest, math.hypot(p["x"] - previous["x"], p["y"] - previous["y"]))
                previous = p
            page.keyboard.up(key)
            state = snap(page)
            check("Real walk seam " + edge["from"] + " -> " + edge["to"], state["environment"]["area"] == edge["to"], state["environment"])
            check("Seam continuous visual/HP/time", largest < 16 and state["player"]["hp"] == 57 and abs(state["elapsed"] - .44) < 1e-6, largest)
            if any(edge["shift"]):
                call(page, "step", .3)
                wait(page, "window.__waterTest.snapshot().environment.terrain.loading === 0")
                page.screenshot(path=str(SHOTS / '错位接缝-1440x900.png'))
        page.screenshot(path=str(SHOTS / "跨图交界-1440x900.png"))

        # Water-only continuous route through 124 -> 126 -> 127 -> 128, no teleports after start.
        edge = next(e for e in t["seams"] if e["from"] == "MAP_ROUTE124" and e["to"] == "MAP_ROUTE126")
        pair = next(p for p in edge["pairs"] if water[p[1] * cols + p[0]] and water[p[3] * cols + p[2]]
                    and route(p[1] * cols + p[0], lambda at: inside(at, 'MAP_ROUTE128'), True))
        current = pair[1] * cols + pair[0]
        sea_path = [current]
        for target in ("MAP_ROUTE126", "MAP_ROUTE127", "MAP_ROUTE128"):
            path = route(current, lambda at, target=target: inside(at, target), True)
            check("Water-only path into " + target, bool(path), len(path))
            sea_path.extend(path[1:])
            current = path[-1]
        call(page, "reset", True)
        call(page, "arrange", {"ai": False, "player": cell((sea_path[0] % cols, sea_path[0] // cols)), "enemy": start})
        # arrange() is a test-only teleport; settle camera at the start before measuring continuous travel.
        call(page, 'step', 2)
        wait(page, "window.__waterTest.snapshot().environment.terrain.loading === 0 && window.__waterTest.snapshot().environment.terrain.visibleMissing === 0")
        visited = {snap(page)["environment"]["area"]}
        missing = []
        for a, b in pairwise(sea_path):
            state = snap(page)
            key = "d" if b == a + 1 else "a" if b == a - 1 else "s" if b > a else "w"
            move(page, key, size / (state["player"]["speed"] * .75))
            state = snap(page)
            visited.add(state["environment"]["area"])
            check("Continuous sea step " + str(b), state["player"]["swimming"] and
                  math.hypot(state["player"]["x"] - (b % cols + .5) * size,
                             state["player"]["y"] - (b // cols + .5) * size) < .1)
            # Test stepping is faster than wall-clock downloads; allow async prefetch to resolve.
            page.wait_for_timeout(10)
            missing.append(snap(page)["environment"]["terrain"]["visibleMissing"])
        check("Swam across four original sea routes", {"MAP_ROUTE124", "MAP_ROUTE126", "MAP_ROUTE127", "MAP_ROUTE128"} <= visited, sorted(visited))
        check("Cross-chunk prefetch no blank ground", not any(missing), max(missing))
        wet = pair
        call(page, "arrange", {"player": cell(wet[:2])})
        call(page, "step", 1)
        wait(page, "window.__waterTest.snapshot().environment.terrain.loading === 0")
        page.screenshot(path=str(SHOTS / "水静市附近海面-1440x900.png"))

        def portal(warp):
            target = cell((warp['col'], warp['row']))
            for dx, dy, key in ((0, 1, 'w'), (0, -1, 's'), (-1, 0, 'd'), (1, 0, 'a')):
                point = {'x': target['x'] + dx * size, 'y': target['y'] + dy * size}
                if page.evaluate('p=>window.__waterTest.freeAt(p.x,p.y,20)', point):
                    break
            else:
                raise AssertionError(('no entrance approach', warp))
            call(page, 'arrange', {'ai': False, 'player': {**point, 'hp': 57}})
            call(page, 'step', .01)
            move(page, key, .16 * 216 / snap(page)['player']['speed'])
            wait(page, '!window.__waterTest.snapshot().environment.warpPending')
            state = snap(page)
            check('Full-world real warp ' + warp['id'], state['environment']['id'] == warp['destScene'])
            check('Warp preserves HP ' + warp['id'], state['player']['hp'] == 57)
            call(page, 'step', 1.1)
            state = snap(page)
            check('Warp AI safe follow >=120 ' + warp['id'], not state['enemy']['worldAbsent'] and
                  math.hypot(state['enemy']['x'] - state['player']['x'], state['enemy']['y'] - state['player']['y']) >= 120)
        for dest in ('MAP_PETALBURG_WOODS', 'MAP_RUSTURF_TUNNEL'):
            call(page, 'select', base)
            call(page, 'reset', True)
            entry = next(w for w in t['warps'] if w['destMap'] == dest)
            portal(entry)
            inner = next(v for v in catalog['terrains'] if any(a['id'] == dest for a in v['areas']))
            portal(next(w for w in inner['warps'] if w['sourceWarp'] == entry['destWarp']))
        call(page, 'select', base)
        call(page, 'reset', True)
        call(page, 'arrange', {'ai': False})
        # Native grass in newly-added Route119, not manually defined grassRegions.
        behavior = base64.b64decode(t["behaviorB64"])
        at = next(i for i, b in enumerate(behavior) if b in (2, 3) and walk[i] and inside(i, "MAP_ROUTE119"))
        call(page, "arrange", {"player": cell((at % cols, at // cols)), "enemy": start})
        call(page, "step", 1.2)
        state = snap(page)
        check("New-world native grass hides player", state["player"]["stealth"]["hidden"], state["player"]["stealth"])
        for width, height in ((390, 844), (844, 390)):
            page.set_viewport_size({"width": width, "height": height})
            call(page, "select", {**base, "map": "emerald-mauvillecity"})
            call(page, "reset", True)
            page.screenshot(path=str(SHOTS / f"城市-{width}x{height}.png"))
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("#battleMenuButton").click()
        page.locator("#sceneButton").click()
        check("All sixteen Chinese city starts in menu", page.locator("#hoennStart option").count() == 16)
        page.locator("#hoennStart").select_option("emerald-sootopoliscity")
        page.locator("#applyScene").click()
        wait(page, "window.__waterTest.snapshot().environment.id === 'emerald-sootopoliscity'")
        check("Real menu independent Sootopolis", snap(page)["environment"]["id"] == "emerald-sootopoliscity")
        # Old save schema/map ID remains valid and lazily reloads correct origin.
        page.evaluate("p=>localStorage.setItem('pocket-arena-loadout-v1',JSON.stringify(p))", base)
        page.reload()
        wait(page, "window.__waterTest?.snapshot().artReady")
        check("Old saved map ID restores", snap(page)["environment"]["id"] == base["map"])
        check("Reloaded world complete", snap(page)["environment"]["terrain"]["visibleMissing"] == 0)
        check("No streaming errors", not snap(page)["environment"]["terrain"]["streamErrors"])
        check("No JS errors", not errors, errors)
        browser.close()
    # Exact full-world thumbnail, also used by the in-game minimap.
    from PIL import Image
    Image.open(ENV / t["preview"]["path"]).save(SHOTS / "全图缩略.png")
    performance = json.loads((OUT / "性能对比.json").read_text())
    print("性能原样", json.dumps(performance, ensure_ascii=False), flush=True)
    check('Performance belongs to current candidate', performance['runs'][1]['candidateSHA256'] ==
          hashlib.sha256((ROOT / '候选试玩.html').read_bytes()).hexdigest())
    check("60 seconds same-machine frame <=1.2x", performance["frameRatio"] <= 1.2)
    check("First-entry download <=1.5x", performance["firstBytesRatio"] <= 1.5)
except Exception as exc:
    failure = repr(exc)
    raise
finally:
    report = {"candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
              "passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks),
              "jsErrors": len(errors), "errors": errors, "failure": globals().get("failure"), "checks": checks}
    (OUT / "验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False, indent=2))
