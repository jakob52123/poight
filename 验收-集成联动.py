"""M1 + M2: actual UI/Canvas, global HP multiplier, hitstop, dive, safe warps and compact skills."""

import base64
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from 游戏数据 import HP_MULTIPLIER

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/集成联动"
SHOTS = OUT / "截图"
SHOTS.mkdir(parents=True, exist_ok=True)
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8840/").rstrip("/")
checks, errors, screenshots = [], [], []


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    assert ok, (name, detail)


def poll(page, expression, timeout=10):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if page.evaluate(expression):
            return True
        page.wait_for_timeout(15)
    return False


def snap(page):
    return page.evaluate("window.__waterTest.snapshot()")


def arrange(page, **value):
    page.evaluate("v => window.__waterTest.arrange(v)", value)


def step(page, seconds):
    page.evaluate("v => window.__waterTest.step(v)", seconds)


def shot(page, name):
    path = SHOTS / name
    page.screenshot(path=str(path))
    screenshots.append(str(path))


def intersects(a, b):
    return (a["x"] < b["x"] + b["width"] and a["x"] + a["width"] > b["x"]
            and a["y"] < b["y"] + b["height"] and a["y"] + a["height"] > b["y"])


def probe(page):
    # Observe real draw calls, including screen-space HP backgrounds/fills and tag text.
    # A hidden HUD must have no commands, not merely be overpainted or given alpha=0.
    return page.evaluate("""() => {
      const c = document.querySelector('#game'), ctx = c.getContext('2d');
      const rect = ctx.fillRect, text = ctx.fillText, rects = [], labels = [];
      ctx.fillRect = function(x,y,w,h) {
        const m = this.getTransform(), r = c.getBoundingClientRect();
        rects.push({x:(m.a*x+m.e)*r.width/c.width, y:(m.d*y+m.f)*r.height/c.height,
          width:m.a*w*r.width/c.width, height:m.d*h*r.height/c.height,
          color:this.fillStyle, alpha:this.globalAlpha});
        return rect.call(this,x,y,w,h);
      };
      ctx.fillText = function(s,...args) {labels.push(s); return text.call(this,s,...args);};
      try {window.__waterTest.render();}
      finally {ctx.fillRect = rect; ctx.fillText = text;}
      return {rects, labels};
    }""")


def hp_calls(state, calls, side):
    h = next(h for h in state["hud"]["actors"] if h["side"] == side)
    b = h["box"]
    return [r for r in calls["rects"]
            if r["color"] == h["color"] and all(
                abs(r[k] - b[k] * (h["ratio"] if k == "width" else 1)) < 0.1
                for k in ["x", "y", "width", "height"])]


def pixel(page, box):
    return page.evaluate("""b => {
      const c=document.querySelector('#game'), r=c.getBoundingClientRect();
      return [...c.getContext('2d').getImageData(
        Math.floor((b.x+3)*c.width/r.width),Math.floor((b.y+3)*c.height/r.height),1,1
      ).data].slice(0,3);
    }""", box)


def m5_links(browser, page):
    """Real merged runtime: touch/seams, layered bridge rendering and full-world policy."""
    page.goto(URL + '/?test=1')
    check('M5 default desktop ready', poll(page, 'window.__waterTest?.snapshot().artReady', 45))
    catalog = page.evaluate('window.__waterTest.catalog()')
    roster = {c['id']: c for c in catalog['roster']}
    profile = {**snap(page)['profile'], 'player': 25, 'enemy': 6,
               'playerMoves': roster[25]['defaultMoves'], 'enemyMoves': roster[6]['defaultMoves'],
               'map': 'emerald-littleroottown'}
    check('M5 desktop letters remain visible', all(k.is_visible() for k in page.locator('.skill kbd').all()))
    page.evaluate('p=>window.__waterTest.select(p)', profile)
    t = catalog['terrains'][0]
    areas = {a['sourceName']: a for a in t['areas']}
    size = t['cellSize']
    check('M5 bridges attached to all 49 maps and independent terrains', len(areas) == 49
          and all('bridges' in q for q in catalog['terrains']))
    policy = json.loads((ROOT / '素材/绿宝石场景/自由探索通行表.json').read_text())['behaviors']
    check('M5 runtime rules exactly equal W2 policy', t['traversalRules'] ==
          {str(int(k, 16)): v for k, v in policy.items()})

    def point(name, x, y, upper=False):
        a = areas[name]
        return {'x': (a['gridX'] + x + .5) * size,
                'y': (a['gridY'] + y + .5) * size, 'onBridge': upper}

    def reset(q):
        page.evaluate('window.__waterTest.reset(true)')
        arrange(page, ai=False, player=q, enemy=point('Route110', 4, 90))

    # New-world bridges, not only F1's original component; both directions.
    for name, start, end in [('Route119', (15, 33), (21, 33)),
                              ('Route120', (22, 67), (33, 67)),
                              ('FortreeCity', (14, 14), (35, 14)),
                              ('Route104', (24, 8), (24, 15))]:
        for a, b in [(start, end), (end, start)]:
            origin, target = point(name, *a), point(name, *b)
            reset(origin)
            dx, dy = target['x'] - origin['x'], target['y'] - origin['y']
            key = ('d' if dx > 0 else 'a') if dx else ('s' if dy > 0 else 'w')
            page.keyboard.down(key)
            step(page, math.hypot(dx, dy) / snap(page)['player']['speed'])
            page.keyboard.up(key)
            state = snap(page)['player']
            check(f'M5 {name} player {a}->{b} walks at land speed',
                  math.hypot(state['x'] - target['x'], state['y'] - target['y']) < .1
                  and not state['swimming'], state)
            # Execute actual layered A* with the same body movement used by AI.
            result = page.evaluate('''v=>{
              const t=window.__waterTest.catalog().terrains[0], w=new PoightWorld(t);
              w.capabilities={...t.capabilities};
              const p={...v.a,hp:1,char:{}}, path=w.findPath(p.x,p.y,v.b.x,v.b.y,false,false);
              for(const q of path) for(let n=0;n<180 && !w.waypointReached(p,q);n++) {
                const dx=q.x-p.x,dy=q.y-p.y,d=Math.hypot(dx,dy);
                w.move(p,dx/d*Math.min(d,4),dy/d*Math.min(d,4),v.r);
              }
              return {length:path.length,distance:Math.hypot(p.x-v.b.x,p.y-v.b.y)};
            }''', {'a': origin, 'b': target, 'r': state['body']['moveRadius']})
            check(f'M5 {name} A* body {a}->{b}', result['length'] > 0 and result['distance'] < 22, result)
    for name, x, y, end_y, swimming in [('FortreeCity', 30, 13, 15, False),
                                        ('Route119', 18, 32, 35, True),
                                        ('Route120', 15, 14, 17, True)]:
        reset(point(name, x, y))
        page.keyboard.down('s')
        step(page, (end_y-y)*size / snap(page)['player']['speed'] / (.75 if swimming else 1))
        page.keyboard.up('s')
        state = snap(page)['player']
        target = point(name, x, end_y)
        check('M5 new-map underpass retains height '+name, not state['onBridge']
              and state['swimming'] == swimming
              and math.hypot(state['x']-target['x'], state['y']-target['y']) < .1, state)
    # H1 Shift uses the same swept body/bridge and shifted-seam traversal as walking.
    for direction in [-1, 1]:
        reset(point('Route110', 12, 46, True))
        origin = snap(page)['player']
        key = 'w' if direction < 0 else 's'
        page.keyboard.down(key)
        page.keyboard.press('Shift')
        page.keyboard.up(key)
        for _ in range(22):
            step(page, 1/120)
            state = snap(page)['player']
            check('M6a Shift deck never drops to lower layer', state['onBridge']
                  and not state['swimming'] and abs(state['x']-origin['x']) < .1)
        check('M6a Shift deck not stuck', (state['y']-origin['y'])*direction > 80, state)
    for edge in [e for e in t['seams'] if any(e['shift'])]:
        pair = edge['pairs'][len(edge['pairs']) // 2]
        reset({'x': (pair[0]+.5)*size, 'y': (pair[1]+.5)*size})
        before = snap(page)
        key = {'left': 'a', 'right': 'd', 'up': 'w', 'down': 's'}[edge['direction']]
        page.keyboard.down(key)
        page.keyboard.press('Shift')
        page.keyboard.up(key)
        previous = before['player']['seamVisualPosition']
        largest = distance = 0
        for _ in range(22):
            step(page, 1/120)
            current = snap(page)['player']['seamVisualPosition']
            delta = math.hypot(current['x']-previous['x'], current['y']-previous['y'])
            largest = max(largest, delta)
            distance += delta
            previous = current
        state = snap(page)
        check('M6a Shift shifted seam crosses without teleport/sticking '+edge['from'],
              state['environment']['area'] == edge['to'] and largest < 16 and distance > 80
              and state['player']['hp'] == before['player']['hp']
              and state['player']['onBridge'] == before['player']['onBridge'],
              {'area': state['environment']['area'], 'largest': largest, 'distance': distance})
    reset(point('Route110', 12, 40))
    page.keyboard.press('Space')
    page.keyboard.down('s')
    step(page, .23)
    check('M5 jump below bridge remains on lower layer', snap(page)['player']['airborne']
          and not snap(page)['player']['onBridge'])
    step(page, 1)
    page.keyboard.up('s')
    p = snap(page)['player']
    check('M5 jump never crosses exclusive deck boundary', not p['onBridge']
          and p['y'] <= (areas['Route110']['gridY'] + 42) * size - p['body']['moveRadius'] + .1)
    reset(point('Route110', 12, 46, True))
    step(page, 1.2)
    check('M5 blue bridge textures ready', poll(page,
          'window.__waterTest.snapshot().environment.terrain.loading===0 && '
          'window.__waterTest.snapshot().environment.terrain.visibleMissing===0', 30))
    order = page.evaluate('''()=>{
      const api=window.__waterTest, c=document.querySelector('#game').getContext('2d');
      const draw=c.drawImage, events=[], art=api.catalog().art[25];
      const actor=new Set(Object.values(art).map(a=>new URL(a.src,location.href).href));
      const over=PoightWorld.prototype.draw;
      PoightWorld.prototype.draw=function(...args){
        const result=over.apply(this,args); if(args[5]==='over') events.push('over'); return result;
      };
      c.drawImage=function(im,...args){if(actor.has(im.src)) events.push('actor'); return draw.call(this,im,...args)};
      try {api.render()} finally {c.drawImage=draw;PoightWorld.prototype.draw=over}
      return events;
    }''')
    check('M5 actual bridge actor draws after over layer', 'over' in order and 'actor' in order
          and order.index('actor') > order.index('over'), order)
    shot(page, 'M5-110蓝桥中段-1440x900.png')

    context = browser.new_context(viewport={'width': 844, 'height': 390}, has_touch=True, is_mobile=True)
    touch = context.new_page()
    touch.on('pageerror', lambda e: errors.append(str(e)))
    touch.goto(URL + '/?test=1')
    check('M5 phone ready', poll(touch, 'window.__waterTest?.snapshot().artReady', 45))
    check('M5 phone defaults HUD3 and hides J K L I', snap(touch)['hud']['variant'] == '3'
          and len(touch.locator('.skill kbd').all()) == 4
          and all(not k.is_visible() for k in touch.locator('.skill kbd').all()))
    touch.evaluate('p=>window.__waterTest.select(p)', profile)
    cdp = context.new_cdp_session(touch)
    for edge in [e for e in t['seams'] if any(e['shift'])]:
        pair = edge['pairs'][len(edge['pairs']) // 2]
        touch.evaluate('window.__waterTest.reset(true)')
        arrange(touch, ai=False, player={'x': (pair[0]+.5)*size, 'y': (pair[1]+.5)*size, 'hp': 57})
        step(touch, 2)
        before = snap(touch)
        dx, dy = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}[edge['direction']]
        origin = {'x': 170, 'y': 240, 'id': 1}
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [origin]})
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints':
                 [{**origin, 'x': origin['x']+dx*54, 'y': origin['y']+dy*54}]})
        previous = before['player']['seamVisualPosition']
        camera = before['camera']
        largest = camera_step = 0
        for _ in range(22):
            step(touch, .02)
            current = snap(touch)['player']['seamVisualPosition']
            largest = max(largest, math.hypot(current['x']-previous['x'], current['y']-previous['y']))
            previous = current
            current_camera = snap(touch)['camera']
            camera_step = max(camera_step, math.hypot(current_camera['x']-camera['x'],
                                                    current_camera['y']-camera['y']))
            camera = current_camera
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        state = snap(touch)
        check('M5 joystick crosses shifted seam '+edge['from']+'->'+edge['to'],
              state['environment']['area'] == edge['to'] and state['player']['hp'] == 57, state['environment'])
        check('M5 joystick seam no actor/camera jump or reset '+edge['from'], largest < 16
              and camera_step < 16 and abs(state['elapsed']-before['elapsed']-.44) < 1e-6
              and state['mobile']['pointerId'] is None, {'actor': largest, 'camera': camera_step})
    touch.evaluate('window.__waterTest.reset(true)')
    arrange(touch, ai=False, player=point('Route110', 24, 25))
    step(touch, 1.2)
    check('M5 dive visibility follows W2 scene capability', snap(touch)['environment']['capabilities']['dive']
          and touch.locator('#diveButton').is_visible() and not touch.locator('#diveButton').is_disabled())
    check('M5 water textures ready', poll(touch, 'window.__waterTest.snapshot().environment.terrain.loading===0', 30))
    shot(touch, 'M5-手机水边有潜-844x390.png')
    touch.locator('#diveButton').tap()
    check('M5 phone W2 water really dives', snap(touch)['player']['diving'])
    touch.evaluate('p=>window.__waterTest.select(p)', {**profile, 'map': 'arena-formal'})
    check('M5 phone arena capability hides dive', not touch.locator('#diveButton').is_visible())
    context.close()
    page.evaluate('p=>window.__waterTest.select(p)', {**profile, 'map': 'arena-formal'})
    page.evaluate('window.__waterTest.reset(true)')
    arrange(page, ai=True, player={'x': 650, 'y': 450}, enemy={'x': 900, 'y': 450})
    step(page, 10)
    check('M5 Pikachu Charizard ten seconds actual battle', snap(page)['matchSeconds'] >= 9.9
          and snap(page)['player']['id'] == 25 and snap(page)['enemy']['id'] == 6)
    shot(page, 'M5-竞技场开打10秒-1440x900.png')


try:
    from 协作.M4.核对集成 import assets, verify
    additions = verify()
    check('M4 T5 original anchors canonical-byte identical', True)
    for batch, entries in additions.items():
        check(f'M4 {batch} all branch anchor entries retained: {len(entries)}', bool(entries))
    assets()
    check('M4 nine protected atlases match T5 and packed manifest; original pixels unchanged', True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        response = page.goto(URL + "/?test=1")
        check("HTTP serves exact integrated candidate", hashlib.sha256(response.body()).hexdigest()
              == hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest())
        check("Art ready", poll(page, "window.__waterTest?.snapshot().artReady", 45))
        catalog = page.evaluate("window.__waterTest.catalog()")
        roster = {c["id"]: c for c in catalog["roster"]}
        profile = {**snap(page)["profile"], "player": 7, "enemy": 4,
                   "playerMoves": roster[7]["defaultMoves"],
                   "enemyMoves": roster[4]["defaultMoves"], "map": "emerald-rustborocity",
                   "holdAim": False}
        check("Initial loadout loads", page.evaluate("v => window.__waterTest.select(v)", profile))
        terrain = catalog["terrains"][0]
        walk = base64.b64decode(terrain["walkB64"])
        behavior = base64.b64decode(terrain["behaviorB64"])
        cols, cell = terrain["columns"], terrain["cellSize"]
        area = next(a for a in terrain["areas"] if a["sourceName"] == "RustboroCity")
        x, y = next((x, y)
                    for y in range(area["gridY"] + 3, area["gridY"] + area["rows"] - 3)
                    for x in range(area["gridX"] + 4, area["gridX"] + area["columns"] - 4)
                    if all(walk[(y + dy) * cols + x + dx]
                           for dy in range(-2, 3) for dx in range(-4, 5)))
        cx, cy = (x + 0.5) * cell, (y + 0.5) * cell
        page.locator("#battleMenuButton").click()
        page.locator("#setupButton").click()
        # T8 resize actions must also refresh T4's portrait chips, on both sides.
        for side, expected in [("player", roster[7]), ("enemy", roster[4])]:
            page.locator("#pick" + side.title() + "Panel").click()
            page.locator("#toggleLoadout").click()
            for count in [3, 2, 1]:
                page.locator("#removeMoveSlot").click()
                chips = page.locator(f"#{side}PickMoves > span").all_text_contents()
                check(f"{side} portrait follows {count} slots", chips == [
                    catalog["moves"][m]["name"] for m in expected["defaultMoves"][:count]])
            for count in [2, 3, 4]:
                page.locator("#addMoveSlot").click()
                check(f"{side} portrait adds slot {count}",
                      page.locator(f"#{side}PickMoves > span").count() == count)
            page.locator("#closeMoves").click()
        page.locator("#pickPlayerPanel").click()
        page.locator("#search").fill("129")
        page.locator('#roster .mon[data-id="129"]').click()
        page.locator("#search").fill("")
        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            label = f"{width}x{height}"
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(150)
            if not page.locator("#setup").is_visible():
                page.locator("#battleMenuButton").click()
                page.locator("#setupButton").click()
            check(label + " Magikarp portrait lists only Splash",
                  page.locator("#playerPickMoves > span").all_text_contents() == ["水溅跃"])
            check(label + " CPU portrait still lists four moves",
                  page.locator("#enemyPickMoves > span").count() == 4)
            shot(page, f"选人-鲤鱼王-{label}.png")
            page.locator("#startBattle").click()
            check(label + " enters VS", poll(page, "window.__waterTest.snapshot().phase==='versus'"))
            page.wait_for_timeout(780)  # Capture the visible middle, not the initial fade-in.
            shot(page, f"VS-{label}.png")
            check(label + " VS auto-finishes without skip",
                  poll(page, "window.__waterTest.snapshot().phase==='playing'", 2.2))
            arrange(page, ai=False, player={"x": cx - 60, "y": cy},
                    enemy={"x": cx + 65, "y": cy + 65})
            step(page, 1)
            check(label + " only one skill and J binding",
                  page.locator("#skills button").count() == 1
                  and page.locator("#skills kbd").all_text_contents() == ["J"])
            panel = page.locator(".hud").bounding_box()
            button = page.locator("#skills button").bounding_box()
            check(label + " one-move panel hugs button without blank slots",
                  0 <= panel["width"] - button["width"] <= 30, [panel, button])
            shot(page, f"M2-鲤鱼王技能栏-{label}.png")
            check(label + " no obsolete HP/SP/counters after VS", page.locator(
                ".battlehud,#playerHealth,#enemyHealth,#staminaBox,#staminaMeter,#hits,#taken"
            ).count() == 0)
            calls, state = probe(page), snap(page)
            check(label + " actual head HP and 1P/CPU tags after VS",
                  all(hp_calls(state, calls, side) for side in ["player", "enemy"])
                  and "1P" in calls["labels"] and "CPU" in calls["labels"])
            page.keyboard.down("j")
            step(page, 0.1)
            page.keyboard.up("j")
            step(page, 0.475)
            state, calls = snap(page), probe(page)
            floats = state["hud"]["floats"]
            check(label + " Splash uses actual new float renderer",
                  len(floats) == 1 and floats[0]["text"] == "但是什么也没有发生"
                  and floats[0]["side"] == "player"
                  and floats[0]["text"] in calls["labels"])
            for h in state["hud"]["actors"]:
                b = h["box"]
                # Include tag plus outline, not only the green fill.
                full = {"x": b["x"] - 29, "y": b["y"] - 4,
                        "width": b["width"] + 30, "height": b["height"] + 8}
                check(label + " Splash avoids " + h["side"] + " full HP/tag box",
                      all(not intersects(f["box"], full) for f in floats), floats)
                check(label + " " + h["side"] + " HP pixels remain visible",
                      pixel(page, b) == [72, 216, 120])
            check(label + " Splash is harmless", state["enemy"]["hp"] == state["enemy"]["maxHP"]
                  and state["hits"] == state["taken"] == 0)
            check(label + " no horizontal overflow",
                  page.evaluate("document.documentElement.scrollWidth<=innerWidth+1"))
            shot(page, f"水溅跃-头顶HUD-{label}.png")

        # Native grass, visible-before/hidden/revealed-after positive and negative draw probes.
        check("Restore ordinary grounded fighters", page.evaluate(
            "v => window.__waterTest.select(v)", profile))
        area = next(a for a in terrain["areas"] if a["sourceName"] == "Route101")
        x, y = next((x, y)
                    for y in range(area["gridY"], area["gridY"] + area["rows"])
                    for x in range(area["gridX"], area["gridX"] + area["columns"])
                    if behavior[y * cols + x] == 2
                    and all(walk[y * cols + x + dx] for dx in [-3, -2, -1, 0, 1]))
        g = {"x": (x + 0.5) * cell, "y": (y + 0.5) * cell}
        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            label = f"{width}x{height}"
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(150)
            page.evaluate("window.__waterTest.reset(true)")
            arrange(page, ai=False, player={"x": g["x"] - 144, "y": g["y"]}, enemy=g)
            state, calls = snap(page), probe(page)
            check(label + " visible CPU HP/tag positive control",
                  bool(hp_calls(state, calls, "enemy")) and "CPU" in calls["labels"])
            step(page, 0.8)
            state, calls = snap(page), probe(page)
            check(label + " AI is hidden in native grass", state["enemy"]["stealth"]["hidden"])
            check(label + " hidden AI has no HP fill or CPU text commands",
                  not hp_calls(state, calls, "enemy") and "CPU" not in calls["labels"])
            h = next(h for h in state["hud"]["actors"] if h["side"] == "enemy")
            b = h["box"]
            forbidden = {"#182632", "#ffffff", h["color"], "#b83d4c"}
            region = {"x": b["x"] - 29, "y": b["y"] - 4,
                      "width": b["width"] + 30, "height": b["height"] + 8}
            check(label + " no hidden AI HP background/trail/tag rectangles",
                  not any(r["color"] in forbidden and intersects(r, region) for r in calls["rects"]))
            check(label + " player HP/tag unaffected by AI hiding",
                  bool(hp_calls(state, calls, "player")) and "1P" in calls["labels"])
            shot(page, f"AI藏身-无血条无CPU-{label}.png")
            arrange(page, player={"x": g["x"] - 60, "y": g["y"]})
            state, calls = snap(page), probe(page)
            check(label + " proximity restores CPU head HP and tag",
                  not state["enemy"]["stealth"]["hidden"]
                  and bool(hp_calls(state, calls, "enemy")) and "CPU" in calls["labels"])
        # M2-1: real damage, maxHP-relative trail, and the actual float/HP draw path.
        page.set_viewport_size({"width": 1440, "height": 900})
        check("M2 HP profile selected", page.evaluate(
            "v => window.__waterTest.select(v)", {**profile, "shake": False}))
        page.evaluate("window.__waterTest.reset(true)")
        arrange(page, ai=False, player={"x": cx - 60, "y": cy},
                enemy={"x": cx + 65, "y": cy + 65})
        step(page, 1)
        before = snap(page)
        check("M2 both maxHP equal original baseHP times global multiplier", all(
            before[side]["maxHP"] == roster[before[side]["id"]]["baseHP"] * HP_MULTIPLIER
            for side in ["player", "enemy"]))
        page.evaluate("n => window.__waterTest.testDamage('enemy', n, 0, 0)",
                      before["enemy"]["maxHP"] / 4)
        calls, state = probe(page), snap(page)
        amount = before["enemy"]["hp"] - state["enemy"]["hp"]
        h = state["hud"]["actors"][1]
        check("M2 damage/trail use maxHP, not literal 100", amount > 0
              and abs(h["ratio"] - (1 - amount / state["enemy"]["maxHP"])) < 1e-10
              and h["trailRatio"] == 1 and bool(hp_calls(state, calls, "enemy")))
        check("M2 real damage float displays actual amount", any(
            f["text"] == "−" + str(amount) and f["text"] in calls["labels"]
            for f in state["hud"]["floats"]))
        step(page, state["feel"]["remaining"] + 0.9)
        h = snap(page)["hud"]["actors"][1]
        check("M2 maxHP-relative trail collapses to current ratio",
              abs(h["trailRatio"] - h["ratio"]) < 1e-9)

        # M2-2: real engine hitstop, equal seeded no-render and stepped clocks/HP.
        sim_profile = {**profile, "player": 25, "enemy": 6,
                       "playerMoves": roster[25]["defaultMoves"],
                       "enemyMoves": roster[6]["defaultMoves"]}
        check("M2 simulation profile selected", page.evaluate(
            "v => window.__waterTest.select(v)", sim_profile))
        fast = page.evaluate("window.__waterTest.simulate({seed:1357911,tier:'poke',maxSeconds:120})")
        repeated = page.evaluate("window.__waterTest.simulate({seed:1357911,tier:'poke',maxSeconds:120})")
        check("M2 full simulation result repeats exactly", fast == repeated)
        page.evaluate("window.__waterTest.reset(true); window.__waterTest.autopilot('poke')")
        arrange(page, tier="poke")
        step(page, 120)
        state = snap(page)
        check("M2 no-render and stepped engine agree including hitstop",
              fast["hp"] == {"a": state["player"]["hp"], "b": state["enemy"]["hp"]}
              and abs(fast["seconds"] - state["matchSeconds"]) < 1e-8
              and abs(fast["combatSeconds"] - state["elapsed"]) < 1e-8
              and fast["frozenSeconds"] > 0
              and abs(fast["seconds"] - fast["combatSeconds"] - fast["frozenSeconds"]) < 1e-8,
              {k: fast[k] for k in ["seconds", "combatSeconds", "frozenSeconds"]})

        # M2-3/4: native open water, keyboard hold, both visible shadow HUDs and oxygen.
        water = base64.b64decode(terrain["waterB64"])
        shore = next(i for i in range(cols, len(walk) - cols)
                     if water[i] and walk[i - 1] and walk[i - 2]
                     and all(water[i + dx + dy * cols] for dx in range(7) for dy in [-1, 0, 1]))
        wx, wy = (shore % cols + 3.5) * cell, (shore // cols + 0.5) * cell
        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            label = f"{width}x{height}"
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(150)
            check(label + " M2 dive profile selected", page.evaluate(
                "v => window.__waterTest.select(v)", {**profile, "holdAim": True, "shake": False}))
            page.evaluate("window.__waterTest.reset(true)")
            arrange(page, ai=False, player={"x": wx, "y": wy},
                    enemy={"x": wx + 130, "y": wy})
            step(page, 1.2)
            page.mouse.down(button="right")
            page.keyboard.down("j")
            step(page, 0.2)
            check(label + " M2 surface aim positive control", snap(page)["aim"]["active"])
            page.keyboard.press("c")
            page.keyboard.up("j")
            page.mouse.up(button="right")
            check(label + " M2 entering dive cancels held aim", snap(page)["aim"] is None)
            check(label + " M2 CPU enters actual dive", page.evaluate("window.__waterTest.dive('enemy')"))
            page.keyboard.down("j")
            step(page, 0.3)
            state, calls = snap(page), probe(page)
            check(label + " M2 dive cannot hide even after grass timer", all(
                state[s]["diving"] and not state[s]["stealth"]["hidden"]
                and not state[s]["stealth"]["inGrass"] for s in ["player", "enemy"]))
            check(label + " M2 underwater hold has no aim, warning, spend or projectile",
                  state["aim"] is None and not state["warnings"] and not state["bullets"]
                  and state["player"]["spent"] == 0)
            page.keyboard.up("j")
            check(label + " M2 diving CPU still draws head HP and CPU tag",
                  bool(hp_calls(state, calls, "enemy")) and "CPU" in calls["labels"])
            for h in state["hud"]["actors"]:
                o, b = h["oxygen"], h["box"]
                check(label + " M2 " + h["side"] + " oxygen is below same-width HP",
                      o is not None and abs(o["box"]["x"] - b["x"]) < 1e-7
                      and abs(o["box"]["width"] - b["width"]) < 1e-7
                      and abs(o["box"]["y"] - b["y"] - b["height"] - 4) < 1e-7
                      and abs(o["ratio"] - state[h["side"]]["oxygen"] / 3) < 1e-7)
                check(label + " M2 " + h["side"] + " actual oxygen fill matches geometry",
                      any(r["color"] == "#9ff3ff" and all(
                          abs(r[k] - o["box"][k] * (o["ratio"] if k == "width" else 1)) < 0.1
                          for k in ["x", "y", "width", "height"]) for r in calls["rects"]))
            dive_button = page.locator("#diveButton")
            check(label + " M2 no top-right debug countdown",
                  dive_button.inner_text() == "上浮 · C"
                  and dive_button.bounding_box()["y"] > height / 2
                  and not any("氧气 " in str(s) or "浮 · " in str(s) for s in calls["labels"]))
            shot(page, f"M2-潜水氧气条-{label}.png")

            # Strong negative control: explicit grass metadata cannot hide a submerged actor.
            page.evaluate("v => window.__waterTest.grassRegions(v)",
                          [{"x": wx - 100, "y": wy - 100, "w": 400, "h": 200}])
            step(page, 0.85)
            state = snap(page)
            check(label + " M2 even overlapping grass metadata cannot hide divers",
                  all(state[s]["diving"] and not state[s]["stealth"]["hidden"]
                      and not state[s]["stealth"]["inGrass"] for s in ["player", "enemy"]))

            # M2-5: enter actual original forest/tunnel warp by walking and wait for follow.
            for dest in ["woods", "tunnel"]:
                check(label + " M2 restore overworld for " + dest, page.evaluate(
                    "v => window.__waterTest.select(v)", profile))
                page.evaluate("window.__waterTest.reset(true)")
                w = next(w for w in terrain["warps"] if dest in w["destScene"])
                tx, ty = (w["col"] + 0.5) * cell, (w["row"] + 0.5) * cell
                for dx, dy, key in [(0, 1, "w"), (0, -1, "s"), (-1, 0, "d"), (1, 0, "a")]:
                    start = {"x": tx + dx * cell, "y": ty + dy * cell}
                    if page.evaluate("q => window.__waterTest.freeAt(q.x,q.y,20)", start):
                        break
                else:
                    raise AssertionError("No adjacent walkable entrance")
                arrange(page, ai=False, player=start)
                step(page, 0.01)
                page.keyboard.down(key)
                step(page, 0.16)
                page.keyboard.up(key)
                check(label + " M2 walk through " + dest, poll(
                    page, "!window.__waterTest.snapshot().environment.warpPending")
                    and snap(page)["environment"]["id"] == w["destScene"])
                check(label + " M2 AI waits outside " + dest, snap(page)["enemy"]["worldAbsent"])
                step(page, 1.02)
                state = snap(page)
                distance = math.hypot(state["enemy"]["x"] - state["player"]["x"],
                                      state["enemy"]["y"] - state["player"]["y"])
                check(label + " M2 " + dest + " AI follows at least120px on walkable cell",
                      not state["enemy"]["worldAbsent"] and distance >= 120
                      and page.evaluate("p => window.__waterTest.freeAt(p.x,p.y,p.body.moveRadius)",
                                        state["enemy"]), distance)
                shot(page, f"M2-{dest}-AI落点-{label}.png")
        # M3: both arenas keep Hoenn traversal opt-in, plus real natural-scene cover.
        defaults = {
            25: ['thunderbolt', 'quickattack', 'irontail', 'thunder'],
            6: ['flamethrower', 'fireblast', 'dragonclaw', 'airslash'],
        }
        hero_profile = {**snap(page)['profile'], 'player': 25, 'enemy': 6,
                        'playerMoves': defaults[25], 'enemyMoves': defaults[6],
                        'map': 'arena-formal', 'tier': 'great', 'shake': True, 'holdAim': True}
        arenas = [s for s in catalog['scenes'] if s.get('type') == 'arena']
        for scene in arenas:
            check('M3 select ' + scene['id'], page.evaluate(
                'v => window.__waterTest.select(v)', {**hero_profile, 'map': scene['id']}))
            page.evaluate('window.__waterTest.reset(true)')
            arrange(page, ai=False)
            state = snap(page)
            check('M3 ' + scene['id'] + ' no swim/dive/warps',
                  not any(state['environment']['capabilities'].get(k)
                          for k in ['swim', 'dive', 'warps'])
                  and not page.evaluate("window.__waterTest.dive('player')")
                  and not page.locator('#diveButton').is_visible())
            check('M3 ' + scene['id'] + ' world and HP budgets unchanged',
                  state['world'] == {'width': 2100, 'height': 1400}
                  and all(state[s]['maxHP'] == roster[state[s]['id']]['baseHP'] * HP_MULTIPLIER
                          for s in ['player', 'enemy']))

        natural = next(s for s in arenas if s['id'] == 'arena-natural')
        g = natural['grassRegions'][0]
        cover = {'x': g['x'] + g['width'] / 2, 'y': g['y'] + g['height'] / 2}
        # A grounded CPU, deliberately outside an actual annotated grass patch (no fixture).
        check('M3 natural recovery profile', page.evaluate('v => window.__waterTest.select(v)',
              {**hero_profile, 'map': natural['id'], 'enemy': 7,
               'enemyMoves': roster[7]['defaultMoves']}))
        page.evaluate('window.__waterTest.reset(true)')
        recovery = page.evaluate('''g => {
          const api=window.__waterTest, s=api.catalog().scenes.find(s=>s.id==='arena-natural');
          for(const p of [{x:g.x-35,y:g.y+g.height/2},
              {x:g.x+g.width+35,y:g.y+g.height/2},
              {x:g.x+g.width/2,y:g.y-35}, {x:g.x+g.width/2,y:g.y+g.height+35}])
            if(api.freeAt(p.x,p.y,20) && !s.grassRegions.some(r=>
              p.x>=r.x && p.x<r.x+r.width && p.y>=r.y && p.y<r.y+r.height)) return p;
        }''', g)
        check('M3 natural grass has reachable outside recovery site', bool(recovery))
        arrange(page, ai=True, player={'x': 800, 'y': 500},
                enemy={**recovery, 'stamina': 5})
        modes, recovered = [], False
        for _ in range(65):
            step(page, 0.1)
            state = snap(page)
            modes.append(state['ai']['mode'])
            if state['enemy']['stealth']['inGrass'] and state['enemy']['stamina'] >= 65:
                recovered = True
                break
        check('M3 natural AI enters grass and rests to65', recovered
              and '进草丛回体力' in modes and '草丛休息' in modes, modes)

        check('M3 hero arena profile', page.evaluate('v => window.__waterTest.select(v)', hero_profile))
        page.locator('#battleMenuButton').click()
        page.locator('#setupButton').click()
        for side, n in [('player', 25), ('enemy', 6)]:
            check('M3 ' + side + ' portrait has new signature four',
                  page.locator(f'#{side}PickMoves > span').all_text_contents()
                  == [catalog['moves'][m]['name'] for m in defaults[n]])
        page.locator('#closeSetup').click()
        # Check the actual held warning AND cast budget for each of the eight moves.
        # Quick Attack has zero windup, so only its held warning should exist.
        for n, ids in defaults.items():
            check('M3 select caster ' + str(n), page.evaluate('v => window.__waterTest.select(v)',
                  {**hero_profile, 'player': n, 'playerMoves': ids, 'enemy': 7,
                   'enemyMoves': roster[7]['defaultMoves']}))
            for slot, mid in enumerate(ids):
                page.evaluate('window.__waterTest.reset(true)')
                arrange(page, ai=False, player={'x': 450, 'y': 350},
                        enemy={'x': 505, 'y': 350})
                step(page, 1)
                page.locator('#game').focus()
                key = ['j', 'k', 'l', 'i'][slot]
                page.mouse.down(button='right')
                page.keyboard.down(key)
                step(page, .21)
                held = snap(page)
                warning = next(w for w in held['warnings'] if w['aiming'])
                m = catalog['moves'][mid]
                budget = min(m['range'], roster[n]['body']['nominalSize'] * m['rangeBodies'])
                page.keyboard.up(key)
                page.mouse.up(button='right')
                step(page, .01)
                state = snap(page)
                attack = state['player']['attack']
                check('M3 ' + mid + ' warning equals actual min(pixel,body*multiple) +/-2px',
                      attack is not None and abs(attack['range'] - budget) < 1e-8
                      and abs(warning['length'] - attack['range']) <= 2
                      and all(abs(r['length'] - attack['range']) <= 2
                              for r in warning.get('rays', [])),
                      {'warning': warning['length'], 'actual': attack['range'], 'budget': budget})
                if m['windup']:
                    live = next(w for w in state['warnings'] if not w['aiming'])
                    check('M3 ' + mid + ' cast warning also uses budget', abs(live['length'] - budget) <= 2)
                else:
                    check('M3 Quick Attack keeps zero windup', not state['warnings'] and attack['emitted'])

        for width, height in [(1440, 900), (390, 844), (844, 390)]:
            label = f'{width}x{height}'
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(150)
            check(label + ' M3 default-tier heroes', page.evaluate(
                'v => window.__waterTest.select(v)', hero_profile))
            page.evaluate('window.__waterTest.reset(true)')
            arrange(page, ai=False, player={'x': 450, 'y': 370, 'a': 0},
                    enemy={'x': 550, 'y': 370, 'a': math.pi})
            step(page, 1)
            state, calls = snap(page), probe(page)
            check(label + ' M3 head HP stays screen-sized and actually draws',
                  all(hp_calls(state, calls, s) for s in ['player', 'enemy'])
                  and all(40 <= h['box']['width'] <= 90 and 4 <= h['box']['height'] <= 10
                          for h in state['hud']['actors']), state['hud']['actors'])
            hp = state['enemy']['hp']
            check(label + ' M3 Thunderbolt cast', page.evaluate(
                "window.__waterTest.cast('player','thunderbolt')"))
            step(page, .13)  # H1 halves Thunderbolt's windup.
            state = snap(page)
            check(label + ' M3 blue Thunderbolt warning before damage',
                  any(w['id'] == 'thunderbolt' and w['player'] for w in state['warnings'])
                  and state['enemy']['hp'] == hp)
            shot(page, f'M3-正规场-十万伏特预警-{label}.png')
            step(page, .08)
            shot(page, f'M3-正规场-十万伏特发射-{label}.png')
            # Observe a real hit, not an injected feedback callback.
            for _ in range(100):
                step(page, 1 / 120)
                if snap(page)['feel']['remaining'] > 0:
                    break
            state = snap(page)
            check(label + ' M3 actual arena hitstop and shake', state['enemy']['hp'] < hp
                  and state['feel']['remaining'] > 0
                  and any(abs(v) > 0 for v in state['feel']['offset'].values()))
            stopped = state['elapsed']
            step(page, 1 / 120)
            check(label + ' M3 combat clock freezes on hit', snap(page)['elapsed'] == stopped)
            # Intercept the real post-render canvas blit, prove zoomed source arena covers
            # its whole unchanged clip rectangle for every shake phase, with no exposed edge.
            for tick in range(20):
                coverage = page.evaluate('''() => {
                  const c=document.querySelector('#game'), ctx=c.getContext('2d'),
                    old=ctx.drawImage, s=__waterTest.snapshot(), rect=c.getBoundingClientRect();
                  let result=null;
                  ctx.drawImage=function(im,...args) {
                    if(im===c) {
                      const m=this.getTransform(), x=0, y=0,
                        sx=c.width/s.viewport.width, sy=c.height/s.viewport.height;
                      result={zoom:m.a/sx, left:(m.a*x+m.e)/sx, top:(m.d*y+m.f)/sy,
                        right:(m.a*s.viewport.width+m.e)/sx,
                        bottom:(m.d*s.viewport.height+m.f)/sy,
                        x,y, width:s.viewport.width, height:s.viewport.height,
                        screen:[rect.width,rect.height]};
                    }
                    return old.call(this,im,...args);
                  };
                  try {__waterTest.render();} finally {ctx.drawImage=old;}
                  return result;
                }''')
                check(label + f' M3 shake frame{tick} no newly exposed border', coverage is None or (
                    1 < coverage['zoom'] < 1.15 and coverage['left'] <= coverage['x']
                    and coverage['top'] <= coverage['y']
                    and coverage['right'] >= coverage['width']
                    and coverage['bottom'] >= coverage['height']), coverage)
                step(page, 1 / 120)
            page.evaluate('window.__waterTest.reset(true)')
            arrange(page, ai=False, player={'x': 450, 'y': 370},
                    enemy={'x': 550, 'y': 370, 'a': math.pi})
            step(page, 1)
            check(label + ' M3 Fire Blast cast', page.evaluate(
                "window.__waterTest.cast('enemy','fireblast')"))
            step(page, .2)  # H1 halves Fire Blast's windup.
            check(label + ' M3 red Fire Blast warning', any(
                w['id'] == 'fireblast' and not w['player'] for w in snap(page)['warnings']))
            step(page, .11)
            check(label + ' M3 Fire Blast atlas actually drawn', 'fireblast' in snap(page)['generated']['drawn'])
            shot(page, f'M3-正规场-大字爆炎-{label}.png')
            check(label + ' M3 natural scene selected', page.evaluate(
                'v => window.__waterTest.select(v)', {**hero_profile, 'map': natural['id']}))
            page.evaluate('window.__waterTest.reset(true)')
            arrange(page, ai=False, player=cover, enemy={'x': 800, 'y': 500})
            step(page, .81)
            state = snap(page)
            check(label + ' M3 natural player hides in original grassRegions',
                  state['player']['stealth']['hidden'] and state['player']['stealth']['inGrass'])
            shot(page, f'M3-自然场-玩家高草藏身-{label}.png')

        check('M3 arena autopilot defaults', page.evaluate('v => window.__waterTest.select(v)', hero_profile))
        page.evaluate("window.__waterTest.reset(true); window.__waterTest.autopilot('poke')")
        arrange(page, ai=True, tier='poke')
        step(page, 10)
        state = snap(page)
        check('M3 actual autopilot uses both new defaults',
              state['player']['moves'] == defaults[25] and state['enemy']['moves'] == defaults[6]
              and state['ai']['casts'] > 0 and state['balance']['playerDecisions'] > 0)
        candidate = (ROOT / '候选试玩.html').read_text()
        check('M3 build dependency order World -> Arena -> remaining modules',
              candidate.index('window.PoightWorld =') < candidate.index('window.PoightArena =')
              < candidate.index('window.PoightGrassStealth ='))
        for name in ['PoightTraversal', 'PoightBalanceTest', 'PoightFeel', 'PoightAim', 'PoightBodies']:
            check('M3 build retains ' + name, 'window.' + name in candidate)
        # M4: three real moves per batch, non-hero pairings on BOTH arenas.
        # HUD0 preserves the default; HUD1/2/3 additionally exercise U0 + F2.
        cases = [
            ('R1', 'firepunch', 68, 20), ('R1', 'icepunch', 68, 20),
            ('R1', 'thunderpunch', 68, 20),
            ('R2', 'shadowball', 94, 70), ('R2', 'energyball', 3, 70),
            ('R2', 'aurasphere', 448, 70),
            ('R3', 'hyperbeam', 143, 70), ('R3', 'psybeam', 65, 70),
            ('R3', 'watergun', 7, 70),
        ]
        page.set_viewport_size({'width': 1440, 'height': 900})
        for hud in range(4):
            page.goto(URL + f'/?test=1&hud={hud}')
            check(f'M4 HUD{hud} ready', poll(page, 'window.__waterTest?.snapshot().artReady', 45))
            for scene in ['arena-formal', 'arena-natural']:
                for batch, mid, caster, distance in cases:
                    label = f'M4 HUD{hud}/{scene}/{batch}/{mid}'
                    check(label + ' non-hero pairing selected', page.evaluate(
                        'v => window.__waterTest.select(v)',
                        {**profile, 'map': scene, 'player': caster, 'enemy': 7,
                         'playerMoves': roster[caster]['defaultMoves'],
                         'enemyMoves': roster[7]['defaultMoves'], 'holdAim': False}))
                    page.evaluate('window.__waterTest.reset(true)')
                    arrange(page, ai=False, player={'x': 450, 'y': 350, 'a': 0},
                            enemy={'x': 450 + distance, 'y': 350, 'a': math.pi})
                    page.evaluate('mid => window.__waterTest.equip("player", [mid])', mid)
                    step(page, .1)
                    before = snap(page)
                    page.locator('#game').focus()
                    page.keyboard.press('KeyJ')
                    step(page, .02)
                    state = snap(page)
                    check(label + ' keyboard actually casts and spends',
                          state['player']['attack']['id'] == mid
                          and state['player']['spent'] == catalog['moves'][mid]['cost'])
                    button = page.locator('#skills .skill').first
                    cool = float(button.evaluate("b => b.style.getPropertyValue('--cool')"))
                    step(page, .12)
                    check(label + ' cooldown sweep advances before impact', cool > float(
                        button.evaluate("b => b.style.getPropertyValue('--cool')")) > 0
                        and snap(page)['enemy']['hp'] == before['enemy']['hp'])
                    step(page, 2.8)
                    check(label + ' real hit', snap(page)['enemy']['hp'] < before['enemy']['hp'])
                    page.evaluate('window.__waterTest.reset(true)')
                    page.evaluate('mid => window.__waterTest.equip("player", [mid])', mid)
                    arrange(page, ai=False, player={'stamina': 0})
                    check(label + ' insufficient grey', button.evaluate(
                        "b => b.classList.contains('insufficient') && Number(getComputedStyle(b).opacity)<1"))
                    page.locator('#game').focus()
                    page.keyboard.press('KeyJ')
                    # Keep this negative-control fixture insufficient throughout
                    # the buffer; low-cost Water Gun otherwise regenerates in time.
                    for _ in range(6):  # Cover the full 120ms buffer; immediate refusal stays visible.
                        arrange(page, player={'stamina': 0})
                        step(page, .02)
                    state = snap(page)
                    check(label + ' F2 refusal text and shake; no spending',
                          state['player']['spent'] == 0 and not state['player']['attack']
                          and any(f['text'] == '体力不足' for f in state['hud']['floats'])
                          and button.evaluate("b => b.classList.contains('cast-rejected')"))
                    if scene == 'arena-natural' and mid in ['firepunch', 'energyball', 'hyperbeam']:
                        page.evaluate('window.__waterTest.reset(true)')
                        page.evaluate('mid => window.__waterTest.equip("player", [mid])', mid)
                        arrange(page, ai=False, player={'hurt': .09})
                        page.keyboard.press('KeyJ')
                        step(page, .08)
                        check(label + ' F2 queued while busy', not snap(page)['player']['attack']
                              and snap(page)['queued'] is not None)
                        step(page, .03)
                        check(label + ' F2 buffer casts within .12s',
                              snap(page)['player']['attack']['id'] == mid)
                        page.evaluate('window.__waterTest.reset(true)')
                        page.evaluate('mid => window.__waterTest.equip("player", [mid])', mid)
                        arrange(page, ai=False, player={'hurt': .5})
                        page.keyboard.press('KeyJ')
                        step(page, .6)
                        check(label + ' F2 expired buffer never casts',
                              snap(page)['player']['spent'] == 0 and snap(page)['queued'] is None)
            for width, height in [(1440, 900), (390, 844), (844, 390)]:
                page.set_viewport_size({'width': width, 'height': height})
                page.evaluate('window.__waterTest.reset(true)')
                arrange(page, ai=False, player={'x': 450, 'y': 350},
                        enemy={'x': 520, 'y': 350})
                page.evaluate("window.__waterTest.equip('player',['firepunch','energyball','hyperbeam'])")
                page.evaluate("window.__waterTest.cast('player','hyperbeam')")
                step(page, .9)
                shot(page, f'M4-HUD{hud}-R三批-{width}x{height}.png')
            page.set_viewport_size({'width': 1440, 'height': 900})
        m5_links(browser, page)
        check('No JS errors', not errors, errors)
        browser.close()
    # CLI twice, serial after browser close; stdout is retained without normalization.
    command = [sys.executable, '工具-平衡模拟.py', '--a', '25', '--b', '6',
               '--tier', 'poke', '--n', '5', '--seed', '1']
    runs = []
    for i in [1, 2]:
        result = subprocess.run(command, cwd=ROOT, env={**os.environ, 'POIGHT_TEST_URL': URL},
                                capture_output=True, timeout=600, check=True)
        (OUT / f'M3-模拟-{i}.jsonl').write_bytes(result.stdout)
        runs.append(result.stdout)
    check('M3 fixed seed CLI output byte-identical', runs[0] == runs[1])
    for i, line in enumerate(runs[0].splitlines(), 1):
        result = json.loads(line)
        check(f'M3 CLI seed{i} only uses T5 defaults and global HP multiplier', result['seed'] == i
              and result['hpMultiplier'] == HP_MULTIPLIER and bool(result['composition'])
              and all(e['move'] in defaults[25 if e['source'] == 'a' else 6]
                      for e in result['composition']))
finally:
    report = {"candidateSHA256": hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest(),
              "passed": sum(c["ok"] for c in checks), "failed": sum(not c["ok"] for c in checks),
              "jsErrors": len(errors), "errors": errors, "checks": checks, "screenshots": screenshots}
    (OUT / "验收.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["passed", "failed", "jsErrors"]}, ensure_ascii=False))
