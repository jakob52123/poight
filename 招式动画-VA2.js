// SPDX-License-Identifier: AGPL-3.0-or-later
// VA2 additive visuals. No damage, range, velocity, collision or actor pose writes.
(() => {
  const moves = {
    bubble: { symbol: "bubble", anchor: "mouth" },
    ember: { symbol: "flame", anchor: "mouth" },
    razorleaf: { symbol: "razor", anchor: "plant" },
    icywind: { symbol: "ice", anchor: "mouth" },
    gust: { symbol: "gust", anchor: "wing" },
    poisonsting: { symbol: "needle", anchor: "mouth" },
    swift: { symbol: "star", anchor: "mouth" },
    triattack: { symbol: "triangle", anchor: "mouth" },
    leafstorm: { symbol: "leaf", anchor: "plant" },
    psychocut: { symbol: "crescent", anchor: "head" },
    hydropump: { beam: true, symbol: "water", color: "#69ffff", ratio: .40, anchor: "mouth" },
    solarbeam: { beam: true, symbol: "orb", color: "#ffef35", ratio: .40, anchor: "flower" },
    psybeam: { beam: true, symbol: "ring", color: "#fff520", anchor: "head" },
    dragonbreath: { beam: true, symbol: "breath", color: "#ffd95a", anchor: "mouth" },
    hyperbeam: { beam: true, symbol: "orb", color: "#ffe129", ratio: .40, anchor: "mouth" },
    signalbeam: { beam: true, symbol: "red", color: "#6dff35", anchor: "head" },
    gigadrain: { beam: true, symbol: "sap", color: "#72ff36", anchor: "flower" },
    freezedry: { beam: true, symbol: "ice", color: "#45ffff", anchor: "mouth" },
    flashcannon: { beam: true, symbol: "silver", color: "#36e9ff", anchor: "cannon" },
  };
  window.PoightVA2Moves = moves;
  const p = window.PoightMoveAnimations.prototype;
  const old = Object.fromEntries([
    "uses", "reset", "prepare", "path", "bullet", "projectileContact", "impact", "draw",
  ].map((name) => [name, p[name]]));
  p.reset = function () {
    old.reset.call(this);
    this.va2Roots = new Map();
  };
  p.uses = function (id) {
    return this.enabled && (!!moves[id] || old.uses.call(this, id));
  };
  p.va2Anchor = function (actor, move, angle, api) {
    // Already-reviewed batch2 landmark wins. R3 visual deformation is not applied twice.
    if (move.batch2) {
      const point = api.anchor(actor, move, angle);
      if (point) return point;
    }
    const entries = actor.char.moveAnchors || {}, part = moves[move.id].anchor;
    const key = ["r3-" + part, part, "r3-mouth", "mouth"].find((key) => entries[key]);
    return api.anchor(actor, { ...move, batch2: true, r3: false, anchor: key }, angle);
  };
  p.prepare = function (b, api) {
    if (!this.enabled || !moves[b.m.id]) return old.prepare.call(this, b, api);
    const angle = b.owner.attack?.aim ?? Math.atan2(b.uy, b.ux);
    const root = this.va2Anchor(b.owner, b.m, angle, api);
    if (!root) throw new Error("VA2 landmark missing: " + b.owner.id + "/" + b.m.id);
    b.originAnchor = { ...root };
    b.coreRoot = { ...root };
    b.visualOffsetX = root.x - b.x;
    b.visualOffset = root.y - (b.y - 16 - b.airFrom);
    // Solar Beam's upstream weather conversion failed; only reuse the inert shot tracker.
    // Its local gold charge/strip below is explicitly authored, not the weather timeline.
    b.coreShot = this.engine.createShot(this.engine.data.moves[b.m.id] ? b.m.id : "hyperbeam",
      { ...root, height: b.owner.char.body.visibleSize[1] },
      { x: b.x, y: b.y, height: 48 }, { fx: "va2-" + moves[b.m.id].symbol });
    b.coreShot.moveId = b.m.id;
    this.va2Roots.set(b.owner, { id: b.m.id, root: { ...root } });
    this.releases.push({ id: b.m.id, x: root.x, y: root.y, anchor: { ...root },
      landmark: root, physical: { x: b.x, y: b.y }, time: this.time });
    this.releases = this.releases.slice(-32);
    return b;
  };
  p.va2Symbol = function (ctx, key, x, y, diameter, alpha = 1, angle = 0) {
    const spec = this.engine.mapping.effects["va2-" + key];
    // Tight alpha crops: minimum dimension is the actual contour, not transparent canvas.
    this.sprite(ctx, "va2-" + key, x, y,
      diameter * spec.width / Math.min(spec.width, spec.height), alpha, angle);
  };
  p.path = function (ctx, id, root, front, age, alpha = 1, height = 48) {
    const cfg = this.enabled && moves[id];
    if (!cfg) return old.path.call(this, ctx, id, root, front, age, alpha, height);
    const dx = front.x - root.x, dy = front.y - root.y,
      length = Math.hypot(dx, dy), a = Math.atan2(dy, dx),
      size = Math.max(14, height * .30) * 1.3;
    ctx.save();
    ctx.globalAlpha = alpha;
    // The physical front is a hard leading plane: round caps, glow and texture tiles
    // must not visually reach through the opponent before the collision tick.
    const back = length + height * 12 + 300, side = height * 12 + 300,
      ux = Math.cos(a), uy = Math.sin(a), nx = -uy, ny = ux;
    ctx.beginPath();
    ctx.moveTo(front.x + nx * side, front.y + ny * side);
    ctx.lineTo(front.x - nx * side, front.y - ny * side);
    ctx.lineTo(front.x - ux * back - nx * side, front.y - uy * back - ny * side);
    ctx.lineTo(front.x - ux * back + nx * side, front.y - uy * back + ny * side);
    ctx.closePath();
    ctx.clip();
    if (!cfg.beam) {
      // Each existing fan projectile has its OWN physical front; never add hit-bearing shots.
      const rotation = ["razorleaf", "leafstorm", "psychocut"].includes(id) ? a
        : id === "poisonsting" ? a + Math.PI / 2 : 0;
      if (id === "bubble") {
        for (let i = 1; i <= 2; i++) {
          const back = Math.min(length, i * size * 1.15);
          this.va2Symbol(ctx, "bubble", front.x - Math.cos(a) * back,
            front.y - Math.sin(a) * back, size * .78, alpha);
        }
      }
      if (id === "leafstorm" || id === "icywind") {
        for (let i = 0; i < 4; i++) {
          const back = Math.min(length, size * (1.1 + i * .6)),
            offset = Math.sin(age * 14 + i * 2) * size * .65;
          this.va2Symbol(ctx, cfg.symbol, front.x - Math.cos(a) * back - Math.sin(a) * offset,
            front.y - Math.sin(a) * back + Math.cos(a) * offset, size * .7, alpha,
            id === "leafstorm" ? a + age * 9 + i : age * 4 + i);
        }
      }
      const spec = this.engine.mapping.effects["va2-" + cfg.symbol],
        scale = size / Math.min(spec.width, spec.height), relative = rotation - a,
        half = (Math.abs(Math.cos(relative)) * spec.width +
          Math.abs(Math.sin(relative)) * spec.height) * scale / 2;
      this.va2Symbol(ctx, cfg.symbol, front.x - ux * half, front.y - uy * half,
        size, alpha, rotation);
      ctx.restore();
      return;
    }
    const width = Math.max(10, height * (cfg.ratio || .25));
    const stroke = (w, color, offset = 0) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = w;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(root.x - Math.sin(a) * offset, root.y + Math.cos(a) * offset);
      ctx.lineTo(front.x - Math.sin(a) * offset, front.y + Math.cos(a) * offset);
      ctx.stroke();
    };
    // Continuous opaque attribute strip, broad luminous center, translucent outer halo.
    stroke(width * 1.9 + 8, cfg.color + "50");
    stroke(width * 1.6 + 4, cfg.color);
    stroke(width, "#f8ffff");
    const count = Math.max(1, Math.floor(length / 22));
    for (let i = 0; i <= count; i++) {
      const t = i / count, x = root.x + dx * t, y = root.y + dy * t;
      if (id === "hydropump") {
        for (const side of [-1, 1])
          this.va2Symbol(ctx, "water", x - Math.sin(a) * width * .42 * side,
            y + Math.cos(a) * width * .42 * side, width * .55, alpha, a);
      } else if (id === "signalbeam") {
        const offset = Math.sin(t * 14 - age * 24) * width * .55;
        for (const side of [-1, 1])
          this.va2Symbol(ctx, side < 0 ? "red" : "green", x - Math.sin(a) * offset * side,
            y + Math.cos(a) * offset * side, width * .85, alpha);
      } else if (id !== "gigadrain") {
        this.va2Symbol(ctx, cfg.symbol, x, y, width * (id === "psybeam" ? 1.7 : 1.2),
          alpha, id === "dragonbreath" ? a - Math.PI / 2 : a);
      }
    }
    // Restroke uninterrupted 230+ core; serial gold rings stay above it for Psybeam.
    stroke(width * (id === "signalbeam" ? 1.10 : id === "hydropump" ? .85 : .70), "#f8ffff");
    if (id === "psybeam") {
      for (let i = 0; i <= count; i++) {
        const t = i / count;
        this.va2Symbol(ctx, "ring", root.x + dx * t, root.y + dy * t, width * 1.3, alpha, a);
      }
      stroke(width * .22, "#ffffff");
    }
    if (id === "hydropump") {
      stroke(width * .12, "#60f5ff", -width * .22);
      stroke(width * .12, "#60f5ff", width * .22);
    }
    if (id === "dragonbreath" || id === "signalbeam") {
      // Iconic particles must survive the luminous restroke, not disappear behind it.
      for (let i = 0; i <= count; i++) {
        const t = i / count, side = i % 2 ? -1 : 1,
          offset = width * .65 * side,
          key = id === "dragonbreath" ? "dragon-flare" : side < 0 ? "red" : "green";
        this.va2Symbol(ctx, key, root.x + dx * t - Math.sin(a) * offset,
          root.y + dy * t + Math.cos(a) * offset, width * .40, alpha,
          id === "dragonbreath" ? a - Math.PI / 2 : 0);
      }
    }
    if (id === "flashcannon") {
      stroke(width * .20, "#ffffff");
    }
    ctx.restore();
  };
  p.bullet = function (ctx, b, lift, api) {
    if (!this.enabled || !moves[b.m.id] || !b.coreShot)
      return old.bullet.call(this, ctx, b, lift, api);
    const front = this.front(b, lift), root = moves[b.m.id].beam && b.owner.attack?.id === b.m.id
      ? this.va2Anchor(b.owner, b.m, b.owner.attack.aim, api) : b.coreRoot;
    b.coreShot.update(front, this.time * 1000);
    this.path(ctx, b.m.id, root, front, b.age, 1, b.owner.char.body.visibleSize[1]);
    return true;
  };
  p.projectileContact = function (b, point, lift, api) {
    if (!this.enabled || !moves[b.m.id] || !b.coreShot)
      return old.projectileContact.call(this, b, point, lift, api);
    const front = { x: point.x, y: point.y - 16 - lift },
      root = moves[b.m.id].beam && b.owner.attack?.id === b.m.id
        ? this.va2Anchor(b.owner, b.m, b.owner.attack.aim, api) : b.coreRoot;
    b.coreShot.hit(front, this.time * 1000);
    this.ribbons.push({ id: b.m.id, root: { ...root }, front, age: 0, shotAge: b.age,
      height: b.owner.char.body.visibleSize[1] });
    this.ribbons = this.ribbons.slice(-32);
    this.va2Roots.set(b.owner, { id: b.m.id, root: { ...root } });
  };
  p.impact = function (target, source, m, ...args) {
    old.impact.call(this, target, source, m, ...args);
    if (!this.enabled || !moves[m.id]) return;
    const burst = this.bursts.at(-1);
    const origin = this.va2Roots.get(source);
    if (burst && origin?.id === m.id) burst.va2Root = { ...origin.root };
    if (m.id === "freezedry") this.frost.set(target, .3);
  };
  p.draw = function (ctx) {
    old.draw.call(this, ctx);
    for (const b of this.bursts) {
      if (!moves[b.id]) continue;
      const t = b.age / .26, alpha = 1 - t;
      if (b.id === "gigadrain" && b.va2Root) {
        // Visible return is conditional on SUCCESSFUL direct damage, not on the cast.
        for (let i = 0; i < 12; i++) {
          const u = Math.min(1, t * 1.8 + i / 18),
            x = b.x + (b.va2Root.x - b.x) * u,
            y = b.y + (b.va2Root.y - b.y) * u + Math.sin(u * Math.PI) * (i % 2 ? 16 : -16);
          this.va2Symbol(ctx, "sap", x, y, 12, alpha);
        }
        this.va2Symbol(ctx, "heal", b.va2Root.x, b.va2Root.y, b.size * .5, alpha);
      } else if (b.id === "icywind" || b.id === "freezedry") {
        for (let i = -2; i <= 2; i++)
          this.va2Symbol(ctx, "spikes", b.x + i * 13, b.y + 12 - t * 6,
            b.size * .28, alpha);
      } else if (b.id === "triattack") {
        for (let i = 0; i < 3; i++) {
          const a = i * Math.PI * 2 / 3 - Math.PI / 2;
          this.va2Symbol(ctx, ["flame", "electric", "ice"][i],
            b.x + Math.cos(a) * b.size * .55, b.y + Math.sin(a) * b.size * .55,
            b.size * .35, alpha);
        }
      } else if (b.id === "hydropump" || b.id === "bubble") {
        this.sprite(ctx, "core-splash", b.x, b.y, b.size * (1 + t), alpha);
      } else {
        // Outward debris, not six huge copies piled into a generic solid doughnut.
        // The common impact star remains visible in the center for every successful hit.
        for (let i = 0; i < 5; i++) {
          const a = i * Math.PI * 2 / 5, radius = b.size * (.6 + t * .7),
            symbol = b.id === "poisonsting" ? "poison" : moves[b.id].symbol,
            angle = ["razorleaf", "leafstorm", "psychocut"].includes(b.id) ? a : 0;
          this.va2Symbol(ctx, symbol,
            b.x + Math.cos(a) * radius, b.y + Math.sin(a) * radius,
            Math.min(12, b.size * .15), alpha, angle);
        }
      }
    }
  };
  const generated = window.PoightR3GeneratedMoves.prototype,
    charge = generated.charge, returnFlow = generated.returnFlow;
  generated.returnFlow = function (actor, target, m, api) {
    if (api.animations.enabled && m.id === "gigadrain") return;
    return returnFlow.call(this, actor, target, m, api);
  };
  generated.charge = function (ctx, actor, m, lift, api) {
    if (!api.animations.enabled || !moves[m.id]) return charge.call(this, ctx, actor, m, lift, api);
    if (!actor.attack || actor.attack.emitted) return;
    const animator = api.animations,
      root = animator.va2Anchor(actor, actor.attack.move || m, actor.attack.aim, api),
      t = Math.min(1, actor.attack.age / actor.attack.hitTime);
    if (!root) return;
    if (m.id === "solarbeam") {
      ctx.save();
      ctx.globalAlpha = .18 + t * .28;
      ctx.fillStyle = "#ffe429";
      ctx.fillRect(root.x - 8 - 8 * t, root.y - 40 * t, 16 + 16 * t, 48 * t);
      ctx.restore();
      for (let i = 0; i < 6; i++) {
        const a = i * Math.PI / 3 + actor.attack.age * 3, r = (1 - t) * 28;
        animator.va2Symbol(ctx, "orb", root.x + Math.cos(a) * r,
          root.y + Math.sin(a) * r, 8 + t * 10, .5 + t * .5);
      }
    } else if (moves[m.id].beam) {
      animator.va2Symbol(ctx, moves[m.id].symbol, root.x, root.y, 8 + t * 12, .4 + .6 * t);
    }
  };
})();
