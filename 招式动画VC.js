// SPDX-License-Identifier: AGPL-3.0-or-later
// VC opt-in visual adapter. Existing combat numbers/shapes and zone landing clocks remain authoritative.
(() => {
  const config = {
    surf: { symbol: "wave", color: "#60ffff" },
    dazzlinggleam: { symbol: "flash", color: "#940044" },
    boomburst: { symbol: "sound", color: "#420074" },
    explosion: { symbol: "blast", color: "#801700" },
    waterspout: { symbol: "rain", color: "#60ffff" },
    heatwave: { symbol: "heat", color: "#920e00" },
    discharge: { symbol: "electric", color: "#ffff16" },
    bulldoze: { symbol: "quake", color: "#462400" },
    blizzard: { symbol: "snow", color: "#42faff" },
    rockslide: { symbol: "rocks", color: "#522600" },
    hex: { symbol: "curse", color: "#53006c" },
    psychic: { symbol: "warp", color: "#720056" },
    inferno: { symbol: "fire", color: "#9a1800" },
    iciclecrash: { symbol: "icicle", color: "#42faff" },
    earthpower: { symbol: "vent", color: "#542400" },
    poisongas: { symbol: "gas", color: "#650083" },
    dracometeor: { symbol: "meteors", color: "#791e02" },
    synthesis: { symbol: "sun", color: "#103100" },
    recover: { symbol: "restore", color: "#062783" },
    rest: { symbol: "sleep", color: "#651083" },
    aquaring: { symbol: "aqua", color: "#60ffff" },
    agility: { symbol: "ghosts", color: "#53006c" },
    focusenergy: { symbol: "energy", color: "#551800" },
    protect: { symbol: "shield", color: "#002712" },
  };
  window.PoightVC = { config };
  const A = window.PoightMoveAnimations.prototype;
  const uses = A.uses, nova = A.nova, stepNova = A.stepNova, drawNova = A.drawNova;
  const path = A.path, frost = A.drawFrost;
  A.uses = function (id) {
    return uses.call(this, id) || (this.enabled && !!config[id]);
  };
  A.nova = function (common, target, api) {
    if (!config[common.id]) return nova.call(this, common, target, api);
    const shapes = target.char.body.hurtByDirection;
    return { ...common, vc: true, mode: "core-nova", life: .6, radius: 0,
      maxRadius: common.m.range + Math.max(...shapes.map((s) => Math.hypot(...s))),
      previousGap: Infinity, contactRadius: null, targetDistance: null };
  };
  A.stepNova = function (e, target, api) {
    if (!e.vc) return stepNova.call(this, e, target, api);
    const dx = target.x - e.x, dy = target.y - e.y, distance = Math.hypot(dx, dy);
    e.radius = e.maxRadius * Math.min(1, e.age / .45);
    if (e.radius >= distance && e.previousGap > 0 &&
      api.bodies.circle(target, e.x, e.y, e.m.range) &&
      api.clearLine(e.x, e.y, target.x, target.y, 3)) {
      e.contactRadius = e.radius;
      e.targetDistance = distance;
      e.contacted = !!api.damage(target, e.owner, e.m, dx / (distance || 1),
        dy / (distance || 1), e.group, { x: target.x, y: target.y });
    }
    e.previousGap = distance - e.radius;
  };
  A.vcStroke = function (ctx, color, width, points) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    points.forEach((p, i) => i ? ctx.lineTo(...p) : ctx.moveTo(...p));
    ctx.stroke();
  };
  A.vcRing = function (ctx, x, y, r, color, width = 5, ellipse = false) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.ellipse(x, y, Math.max(0, r), Math.max(0, r * (ellipse ? .4 : 1)), 0, 0, 2 * Math.PI);
    ctx.stroke();
  };
  A.vcStar = function (ctx, x, y, r, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    for (let i = 0; i < 8; i++) {
      const a = i * Math.PI / 4, radius = i % 2 ? r * .22 : r;
      const point = [x + Math.cos(a) * radius, y + Math.sin(a) * radius];
      if (i) ctx.lineTo(...point); else ctx.moveTo(...point);
    }
    ctx.closePath();
    ctx.fill();
  };
  A.vcSprite = function (ctx, key, x, y, size, angle = 0) {
    this.sprite(ctx, "vc-" + key, x, y, size, 1, angle);
  };
  A.drawNova = function (ctx, e) {
    if (!e.vc) return drawNova.call(this, ctx, e);
    const c = config[e.id], r = e.radius, h = e.owner.char.body.visibleSize[1];
    ctx.save();
    ctx.globalAlpha = Math.min(1, (.6 - e.age) / .1);
    // This circular edge is the same radius used by stepNova, including diagonal hits.
    this.vcRing(ctx, e.x, e.y, r, c.color, 7);
    const n = c.symbol === "blast" ? 14 : 18;
    for (let i = 0; i < n; i++) {
      const a = i * Math.PI * 2 / n, ux = Math.cos(a), uy = Math.sin(a),
        x = e.x + ux * r, y = e.y + uy * r, size = Math.max(18, h * .38);
      if (c.symbol === "flash") {
        this.vcStar(ctx, x, y, size * .65, c.color);
        this.vcStroke(ctx, "#fff5ff", 2, [[x, y], [x - ux * 14, y - uy * 14]]);
      } else if (c.symbol === "sound") {
        if (i === 0) {
          this.vcRing(ctx, e.x, e.y, r * .7, c.color, 4);
          this.vcRing(ctx, e.x, e.y, r * .4, c.color, 3);
        }
      } else if (c.symbol === "blast") {
        this.vcSprite(ctx, "blast", x, y, size * 1.5, a);
        this.vcStar(ctx, x, y, size * .27, "#fff7dc");
      } else if (c.symbol === "rain") {
        // Water balls rise at the caster, then rain exactly at the advancing ground edge.
        const up = Math.max(0, 1 - e.age / .18);
        this.sprite(ctx, "core-water", e.x + ux * 12, e.y - 30 - (1 - up) * 35,
          size, up);
        const rainY = y - Math.max(0, .22 - e.age) * 80;
        this.vcStroke(ctx, "#dfffff", 4, [[x - 4, rainY - 25], [x, rainY - 3]]);
        this.sprite(ctx, "core-water", x, rainY, size);
        if (e.age >= .22) this.sprite(ctx, "core-splash", x, y, size * 1.25);
      } else if (c.symbol === "electric") {
        this.vcStroke(ctx, c.color, 6, [[x - ux * 18, y - uy * 18],
          [x - ux * 9 - uy * 6, y - uy * 9 + ux * 6], [x, y],
          [x + ux * 8 + uy * 5, y + uy * 8 - ux * 5]]);
        this.vcSprite(ctx, "spark", x, y, 14, a);
      } else if (c.symbol === "heat") {
        this.vcStroke(ctx, c.color, 6, [[x - ux * 23, y - uy * 23],
          [x - ux * 12 - uy * 7, y - uy * 12 + ux * 7], [x, y]]);
        this.vcSprite(ctx, "flame", x, y, size, a);
      } else if (c.symbol === "quake") {
        this.vcStroke(ctx, c.color, 5, [[x * 0 + e.x + ux * r * .55, e.y + uy * r * .55],
          [x - ux * 14 - uy * 6, y - uy * 14 + ux * 6], [x, y]]);
        this.sprite(ctx, "core-dust", x, y, size);
      }
    }
    ctx.restore();
  };
  A.path = function (ctx, id, root, front, age, alpha = 1, height = 48) {
    if (!["blizzard", "poisongas"].includes(id))
      return path.call(this, ctx, id, root, front, age, alpha, height);
    const dx = front.x - root.x, dy = front.y - root.y, angle = Math.atan2(dy, dx),
      size = Math.max(22, height * .42), n = id === "blizzard" ? 9 : 5;
    ctx.save();
    ctx.globalAlpha = alpha;
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1), arc = Math.sin(t * Math.PI) * Math.sin(age * 13 + i) * 11,
        x = root.x + dx * t - Math.sin(angle) * arc,
        y = root.y + dy * t + Math.cos(angle) * arc;
      if (id === "blizzard") {
        this.sprite(ctx, "core-ice", x, y, size, 1, angle + age * 4 + i);
        if (i % 2) this.sprite(ctx, "core-shard", x - Math.sin(angle) * 14,
          y + Math.cos(angle) * 14, size, 1, angle);
      } else this.vcSprite(ctx, "cloud", x, y, size * 1.3);
    }
    ctx.restore();
  };
  A.vcZone = function (ctx, e) {
    const c = config[e.id], h = e.owner.char.body.visibleSize[1],
      size = Math.max(24, h * .5), land = e.vcLanding,
      t = Math.min(1, e.age / land), x = e.ex, y = e.ey,
      fall = (1 - t) * 90;
    ctx.save();
    ctx.globalAlpha = e.landed ? Math.max(0, (e.life - e.age) / .35) : 1;
    // Local warning only: no background recolor, no screen-wide flash.
    if (!e.landed) {
      ctx.save();
      ctx.globalAlpha *= .55;
      ctx.setLineDash([7, 5]);
      this.vcRing(ctx, x, y, e.radius, "#d6af62", 2);
      ctx.restore();
    }
    if (["rocks", "meteors", "icicle"].includes(c.symbol)) {
      const n = c.symbol === "icicle" ? 3 : 7;
      for (let i = 0; i < n; i++) {
        const a = i * Math.PI * 2 / n, r = i ? e.radius * .55 : 0,
          px = x + Math.cos(a) * r, py = y + Math.sin(a) * r - fall,
          key = c.symbol === "rocks" ? "rock" : c.symbol === "meteors" ? "meteor" : "spike";
        if (c.symbol === "meteors") {
          this.vcStroke(ctx, "#731482", 9, [[px - fall * .35, py - 35], [px, py]]);
          this.vcStroke(ctx, "#fff7d8", 2, [[px - fall * .35, py - 30], [px, py]]);
        }
        // Icicle bottom/stone center reaches the landing point on the original landing tick.
        const width = c.symbol === "icicle" ? size * .7 : size * (i ? .85 : 1.3),
          sprite = this.engine.mapping.effects["vc-" + key],
          halfHeight = width * sprite.height / sprite.width / 2;
        this.vcSprite(ctx, key, px, py - (c.symbol === "icicle" ? halfHeight : 0), width);
      }
    } else if (c.symbol === "fire") {
      const radius = e.landed ? e.radius * .65 : Math.max(5, size * (1 - t));
      for (let i = 0; i < 7; i++) {
        const a = i * Math.PI * 2 / 7;
        this.vcSprite(ctx, "flame", x + Math.cos(a) * radius,
          y + Math.sin(a) * radius - fall, size * 1.15);
      }
      if (e.landed) this.vcSprite(ctx, "flame", x, y, size * 1.4);
    } else if (c.symbol === "vent") {
      // Manual Earth Power: propagated fissure then a target-foot eruption, not a lobbed rock.
      const px = e.ox + (x - e.ox) * t, py = e.oy + (y - e.oy) * t;
      this.vcStroke(ctx, c.color, 7, [[e.ox, e.oy], [px - 8, py + 5], [px, py]]);
      this.vcRing(ctx, px, py, size * .65, c.color, 6, true);
      if (e.landed) for (let i = 0; i < 7; i++) {
        const a = i * Math.PI * 2 / 7;
        this.vcSprite(ctx, "meteor", x + Math.cos(a) * 25,
          y + Math.sin(a) * 12 - 18, size * .85);
      }
    } else {
      // Psychic warp/Hex curse is local and becomes an opaque contact pulse only at landing.
      const r = e.landed ? e.radius * .8 : size + (1 - t) * 20;
      if (!e.landed) ctx.globalAlpha *= .16; // Warning ghost, NOT a visible attack contact.
      for (let i = 0; i < 3; i++) {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(e.age * 4 + i * Math.PI / 3);
        this.vcRing(ctx, 0, 0, r * (1 - i * .18), c.color, 6, true);
        ctx.restore();
      }
      if (c.symbol === "curse") {
        // Four hooked dark glyphs distinguish Hex from the smooth Psychic warp.
        for (let i = 0; i < 4; i++) {
          const a = i * Math.PI / 2 + e.age;
          ctx.save();
          ctx.translate(x + Math.cos(a) * r, y + Math.sin(a) * r);
          ctx.rotate(a);
          this.vcStroke(ctx, c.color, 6, [[-8, -12], [4, -12], [4, 8], [-5, 8]]);
          ctx.restore();
        }
      }
    }
    e.drawAnchor = { x, y };
    ctx.restore();
  };
  A.vcSupport = function (ctx, e, lift) {
    const p = e.owner, h = p.char.body.visibleSize[1], size = Math.max(18, h * .4),
      x = p.x, y = p.y + 14 - h / 2 - lift(p), c = config[e.id];
    ctx.save();
    ctx.globalAlpha = Math.min(1, (e.life - e.age) / .04);
    e.drawAnchor = { x, y };
    if (c.symbol === "sleep") {
      for (let i = 0; i < 3; i++) this.vcSprite(ctx, "z", x + h * .4 + i * 9,
        y - h * .2 - ((e.age * 24 + i * 13) % 35), size * (1 - i * .15));
    } else if (c.symbol === "shield") {
      // Engine drawEffect sets opacity explicitly, so pass it through the sprite argument.
      this.sprite(ctx, "vc-shield", x, y, h * 1.45, ctx.globalAlpha * .42);
      this.vcRing(ctx, x, y, h * .7, c.color, 5);
    } else if (c.symbol === "energy") {
      for (let i = 0; i < 5; i++) this.vcSprite(ctx, "energy",
        x + (i - 2) * size * .65, y + 10 - ((e.age * 60 + i * 9) % 35), size * .8);
    } else if (c.symbol === "aqua") {
      for (let i = 0; i < 3; i++) this.vcRing(ctx, x, y + (i - 1) * 13, h * .7,
        c.color, 5, true);
      for (let i = 0; i < 5; i++) {
        const a = e.age * 5 + i * Math.PI * 2 / 5;
        this.vcSprite(ctx, "water", x + Math.cos(a) * h * .7,
          y + Math.sin(a) * h * .3, size);
      }
    } else if (c.symbol === "ghosts") {
      for (let i = 0; i < 4; i++) this.vcStroke(ctx, c.color, 4,
        [[x - Math.cos(e.a) * (30 + i * 9), y - 15 + i * 10],
          [x - Math.cos(e.a) * 10, y - 15 + i * 10]]);
    } else {
      for (let i = 0; i < 7; i++) {
        const a = i * Math.PI * 2 / 7, r = c.symbol === "restore"
          ? h * .85 * (1 - Math.min(1, e.age / .5)) + 12 : h * .65;
        this.vcSprite(ctx, c.symbol === "restore" ? "orb" : "shine",
          x + Math.cos(a) * r, y + Math.sin(a) * r, size);
        if (i % 2 === 0) this.vcSprite(ctx, "star", x + Math.cos(a) * h * .45,
          y + Math.sin(a) * h * .45 - e.age * 15, size);
      }
      if (c.symbol === "sun") {
        this.vcStar(ctx, x, y - h * .9, size, "#543400");
        this.vcStar(ctx, x, y - h * .9, size * .13, "#ffffee");
      }
    }
    ctx.restore();
  };
  A.vcSurf = function (ctx, e, front) {
    const h = e.owner.char.body.visibleSize[1], angle = e.a;
    ctx.save();
    ctx.translate(front.x, front.y);
    ctx.rotate(angle);
    // Leading lip sits on the real body-segment radius; the existing R3 gate is untouched.
    ctx.fillStyle = config.surf.color;
    ctx.beginPath();
    ctx.moveTo(0, -h * .85);
    ctx.bezierCurveTo(-h * .7, -h, -h * .6, -h * .3, -h * .8, 0);
    ctx.bezierCurveTo(-h * .65, h * .3, -h * .7, h, 0, h * .85);
    ctx.lineTo(0, -h * .85);
    ctx.fill();
    this.vcStroke(ctx, "#f0ffff", 3, [[0, -h * .8], [-h * .25, -h * .5],
      [-h * .16, 0], [-h * .25, h * .5], [0, h * .8]]);
    for (let i = 0; i < 5; i++) {
      const y = (i - 2) * h * .3;
      this.vcStroke(ctx, "#f0ffff", 5, [[-h * .55, y + 8], [-h * .35, y], [-h * .2, y + 4]]);
    }
    ctx.restore();
  };
  A.drawFrost = function (ctx, p, ...args) {
    const e = this.vcGenerated?.states.find((s) => s.vc && s.id === "agility" && s.owner === p);
    if (e) {
      const [im, sx, sy, sw, sh, x, y, w, h] = args;
      ctx.save();
      for (let i = 3; i > 0; i--) {
        ctx.globalAlpha = .15 + (3 - i) * .1;
        ctx.drawImage(im, sx, sy, sw, sh, x - Math.cos(e.a) * i * 16,
          y - Math.sin(e.a) * i * 16, w, h);
      }
      ctx.restore();
    }
    return frost.call(this, ctx, p, ...args);
  };
  const G = window.PoightR3GeneratedMoves.prototype;
  const emit = G.emit, draw = G.draw, charge = G.charge, step = G.step;
  G.step = function (dt, api) {
    step.call(this, dt, api);
    for (const e of this.states) {
      if (e.mode !== "vc-zone" || e.landed || e.age < e.vcLanding) continue;
      e.landed = true;
      const target = e.owner === api.player ? api.enemy : api.player,
        dx = target.x - e.ex, dy = target.y - e.ey, distance = Math.hypot(dx, dy) || 1;
      // Non-raster Inferno retains its original circle and target-to-zone wall gate.
      if (api.bodies.circle(target, e.ex, e.ey, e.radius) &&
        api.clearLine(e.ex, e.ey, target.x, target.y, 3))
        api.damage(target, e.owner, e.m, dx / distance, dy / distance, e.group);
    }
  };
  G.emit = function (p, a, target, api) {
    const start = this.states.length;
    let result;
    if (api.animations.enabled && config[a.id] && !this.data[a.id]) {
      const m = a.move || api.moves[a.id], common = { id: a.id, owner: p, m, group: a.group,
        a: a.aim, age: 0, x: p.x, y: p.y, ox: p.x, oy: p.y, lift: api.lift(p) };
      this.emitted++;
      if (m.kind === "nova") this.states.push(api.animations.nova(common, target, api));
      else if (m.kind === "zone") {
        const end = api.landing(p, m, a.aim, target);
        this.states.push({ ...common, mode: "vc-zone", ex: end.x, ey: end.y,
          life: m.delay + .35, vcLanding: m.delay, radius: m.radius, landed: false });
      } else {
        if (m.kind === "heal") api.heal(p, m.damage, true);
        if (m.kind === "buff") p.buffs[m.boost] = m.duration;
        this.states.push({ ...common, mode: "support", life: .7 });
      }
      api.tone(m.kind === "nova" || m.kind === "zone" ? "shot" : "heal");
      result = true;
    } else result = emit.call(this, p, a, target, api);
    if (api.animations.enabled && config[a.id]) {
      api.animations.vcGenerated = this;
      for (const e of this.states.slice(start)) {
        e.vc = true;
        e.vcLanding ??= e.life;
      }
    }
    return result;
  };
  G.charge = function (ctx, p, m, lift, api) {
    if (!api.animations.enabled || !config[m.id]) return charge.call(this, ctx, p, m, lift, api);
    // Existing dashed warning owns telegraph; do not display a premature landed attack sprite.
  };
  G.draw = function (ctx, layer, lift, api) {
    const all = this.states;
    this.states = all.filter((e) => !e.vc);
    try { draw.call(this, ctx, layer, lift, api); } finally { this.states = all; }
    for (const e of all) {
      if (!e.vc) continue;
      const below = e.mode === "core-nova" || e.id === "surf" || e.id === "earthpower";
      if ((layer === "below") !== below) continue;
      this.drawn.add(e.id);
      ctx.save();
      if (e.contacted || e.group.hit.size) api.animations.clipContactCenters(ctx);
      if (e.mode === "core-nova") api.animations.drawNova(ctx, e);
      else if (e.id === "surf") {
        const ux = Math.cos(e.a), uy = Math.sin(e.a),
          pad = api.bodies.reach(e.owner, -uy, ux) + 4,
          target = e.owner === api.player ? api.enemy : api.player,
          shape = api.bodies.shape(target),
          expanded = 1 / Math.hypot(ux / (shape.rx + pad), uy / (shape.ry + pad)),
          reach = expanded - api.bodies.reach(target, ux, uy);
        // The physical segment expands BOTH ellipse axes by pad. At diagonals that
        // boundary is not original directional reach + pad; render the exact difference.
        e.visibleFront = { x: e.owner.x + ux * reach, y: e.owner.y + uy * reach };
        e.drawAnchor = api.anchor(e.owner, e.m, e.a);
        api.animations.vcSurf(ctx, e, e.visibleFront);
      } else if (["lob", "propagate", "target", "vc-zone"].includes(e.mode))
        api.animations.vcZone(ctx, e);
      else api.animations.vcSupport(ctx, e, lift);
      ctx.restore();
    }
  };
  // Only this batch's zone warning changes to the earthquake-style dashed landing circle.
  const telegraph = window.PoightTelegraph, shape = telegraph.shape;
  telegraph.shape = function (p, m, angle, target, api) {
    const s = shape.call(this, p, m, angle, target, api);
    if (api.animationEnabled !== false && config[m.id] && m.kind === "zone")
      return { ...s, shape: "ground-ring" };
    return s;
  };
})();
