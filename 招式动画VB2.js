// SPDX-License-Identifier: AGPL-3.0-or-later
// VB2 is a visual-only opt-in. Native R1/R3 simulation remains the sole hit authority.
(() => {
  const styles = {
    aquajet: { symbol: "jet", color: "#20ffff" },
    flamecharge: { symbol: "charge", color: "#ffff25" },
    tackle: { symbol: "ram", color: "#ffe72b" },
    machpunch: { symbol: "fist", color: "#ffe72b" },
    bodyslam: { symbol: "press", color: "#ffe72b" },
    doubleedge: { symbol: "double", color: "#ffe72b" },
    waterfall: { symbol: "rise", color: "#20ffff" },
    flamewheel: { symbol: "wheel", color: "#ffff25" },
    spark: { symbol: "spark", color: "#fff500" },
    wildcharge: { symbol: "volt", color: "#fff500" },
    rollout: { symbol: "roll", color: "#ffe72b" },
    zenheadbutt: { symbol: "forehead", color: "#ff50ff" },
    shadowsneak: { symbol: "shadow", color: "#ff50ff" },
    phantomforce: { symbol: "phase", color: "#ff50ff" },
    bravebird: { symbol: "bird", color: "#20ffff" },
    closecombat: { symbol: "fists", color: "#ffe72b" },
    rapidspin: { symbol: "spin", color: "#ffe72b" },
    aquatail: { symbol: "tail", color: "#20ffff" },
    bonerush: { symbol: "bone", color: "#ffe72b" },
  };
  const on = (api, id) => api.animations.enabled && !!styles[id];
  const root = (p, m, a, api, stateAge = null) => {
    const age = stateAge ?? (p.attack?.emitted ? p.attack.age - p.attack.hitTime : 0);
    const part = m.id === "closecombat" && p.attack?.emitted
      ? age >= .24 ? "r1-foot" : age >= .12 ? "r1-hand2" : m.anchor : m.anchor;
    return api.anchor(p, { ...m, anchor: part }, a) ||
      { x: p.x, y: p.y + 14 - p.char.body.visibleSize[1] / 2 - api.lift(p) };
  };
  const line = (ctx, points, width, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    // White-hot border provides positive contrast, not a dark silhouette.
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = width + (["#ff50ff", "#ff59ff"].includes(color) ? width >= 5 ? 12 : 10 : 4);
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  };
  const arc = (ctx, x, y, r, a, span, width, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.arc(x, y, r, a, a + span);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = width + (["#ff50ff", "#ff59ff"].includes(color) ? width >= 5 ? 12 : 10 : 4);
    ctx.stroke();
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  };
  window.PoightVB2 = {
    styles, root,
    icon(ctx, api, key, x, y, size, angle = 0) {
      api.animations.sprite(ctx, "vb2-" + key, x, y, size, 1, angle);
    },
    glint(ctx, x, y, radius) {
      // Small cyan-white facets brighten the rim without washing out its magenta ink.
      for (const [r, color] of [[radius, '#ffffff'], [radius * .5, '#40ffff']]) {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(x, y - r); ctx.lineTo(x + r, y);
        ctx.lineTo(x, y + r); ctx.lineTo(x - r, y);
        ctx.closePath(); ctx.fill();
      }
    },
    // This exact production method is mirrored by the acceptance raster probe.
    emblem(ctx, e, point, api, charging = false) {
      const { symbol, color } = styles[e.id], h = e.owner.char.body.visibleSize[1],
        size = Math.max(22, h * .65), thick = Math.max(10, h * .25),
        a = e.a ?? e.owner.a, time = e.age, spin = time * 22;
      ctx.save();
      ctx.translate(point.x, point.y);
      // World-up waterfalls and ground shadows are intentionally not aim-rotated.
      ctx.rotate(["rise", "shadow", "phase", "spin"].includes(symbol) ? 0 : a);
      ctx.imageSmoothingEnabled = false;
      if (["jet", "charge", "ram", "double", "press", "volt"].includes(symbol)) {
        // Open-backed attribute shell, not a painted rectangle over the actor.
        if (["jet", "volt"].includes(symbol))
          arc(ctx, size * .25, 0, size * .82, -1.35, 2.70, 4, color);
        if (symbol === "jet") {
          for (let i = -1; i <= 1; i++) {
            line(ctx, [[-size * .9, i * size * .32], [-size * .45, i * size * .25]],
              3, "#20ffff");
          }
          api.animations.sprite(ctx, "vb2-drop", size * .72, 0, Math.max(16, h * .36));
        } else if (symbol === "charge") {
          for (let i = -1; i <= 1; i++)
            this.icon(ctx, api, "flame", -size * .55, i * size * .85,
              size * .65, -.5 + i * .35);
          line(ctx, [[-size * .8, -size * .30], [-size * .35, -size * .20]], 4, color);
          line(ctx, [[-size * .8, size * .30], [-size * .35, size * .20]], 4, color);
        } else if (symbol === "volt") {
          for (let i = -1; i <= 1; i++)
            line(ctx, [[-size * 1.6, i * size * .7], [-size * 1.2, i * size * .7 - 7],
              [-size * 1.3, i * size * .7 + 5], [-size * .8, i * size * .7]], 2, color);
        } else if (symbol === "press") {
          for (let i = -1; i <= 1; i++)
            line(ctx, [[i * size * .4, -size * .9], [i * size * .4, -size * .45]], 4, color);
        } else {
          for (let i = -1; i <= 1; i++)
            line(ctx, [[-size, i * size * .35], [-size * .5, i * size * .35]],
              symbol === "double" ? 5 : 3, color);
        }
      } else if (symbol === "rise") {
        // Manual WATERFALL adaptation: consecutive splashes moving bottom -> top.
        for (let i = 0; i < 3; i++) {
          const y = size * .5 - ((time * 65 + i * size * .5) % (size * 1.5));
          api.animations.sprite(ctx, "vb2-splash", size * 1.25, y, size * .65, 1, 0);
        }
        line(ctx, [[size * .85, size * .6], [size * .85, -size * .4]], 2, color);
        line(ctx, [[size * 1.3, size * .6], [size * 1.3, -size * .4]], 2, color);
      } else if (["wheel", "roll", "spin"].includes(symbol)) {
        // Hollow rolling halo: flames stay outside the visible body.
        const radius = h * .70;
        for (let i = 0; i < 6; i++) {
          const angle = spin + i * Math.PI / 3;
          arc(ctx, 0, 0, radius, angle, .92, symbol === "wheel" ? 5 : 3, color);
          if (symbol === "wheel") {
            // Orange inner edge must not acquire another white border over the yellow ring.
            ctx.strokeStyle = "#ffb225";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(0, 0, radius - 2, angle, angle + .92);
            ctx.stroke();
            this.icon(ctx, api, "flame", Math.cos(angle) * (radius + 4),
              Math.sin(angle) * (radius + 4), h * .50, angle);
          }
        }
        if (symbol === "spin") {
          arc(ctx, 0, -size * .1, h * .80, -spin, 4.5, 3, color);
          arc(ctx, 0, size * .1, h * .85, spin, 4.5, 3, color);
        }
        if (symbol === "roll")
          for (let i = 0; i < 4; i++)
            this.icon(ctx, api, i % 2 ? "dust" : "rock", -size * (.7 + i * .25),
              size * (.4 + i % 2 * .3), 16 + i * 2, spin + i);
      } else if (symbol === "spark") {
        for (let i = 0; i < 5; i++) {
          const angle = spin * .6 + i * Math.PI * 2 / 5, r = h * .80;
          ctx.save();
          ctx.rotate(angle);
          line(ctx, [[r - 4, -12], [r + 6, -5], [r - 3, 2], [r + 6, 12]], 3, color);
          ctx.restore();
        }
      } else if (["fist", "fists"].includes(symbol)) {
        const n = symbol === "fists" && !charging && e.contacted ? 3 : 1;
        for (let i = 0; i < n; i++) {
          const x = (i % 2) * size * .4, y = (i - (n - 1) / 2) * size * .48;
          this.icon(ctx, api, "fist", x, y, size * 1.35, -.2 + i * .2);
          line(ctx, [[x - size, y - 6], [x - size * .65, y - 6]], 4, "#224bdd");
        }
      } else if (symbol === "forehead") {
        arc(ctx, size * .20, 0, size * .60, -1.7, 3.4, 4, color);
        line(ctx, [[size * .45, -4], [size * .45, 4]], 3, "#ffffff");
        for (const side of [-1, 1])
          this.glint(ctx, size * .7, side * size * .9, h * .12);
      } else if (["shadow", "phase"].includes(symbol)) {
        // Shadow stays on the foot plane; phase portals stay local to the caster.
        if (symbol === "shadow") {
          ctx.translate(0, 6);
          line(ctx, [[-size, 0], [size * .7, 0]], 5, color);
          line(ctx, [[size * .2, -size * .28], [size * .7, 0],
            [size * .2, size * .28]], 5, color);
        } else {
          arc(ctx, 0, 0, h * .70, spin, 4.8, 5, color);
          arc(ctx, 0, 0, h * .82, -spin, 2, 5, color);
          for (let i = 0; i < 4; i++) {
            const a = spin * .25 + i * Math.PI / 2;
            this.glint(ctx, Math.cos(a) * h * .86, Math.sin(a) * h * .86, h * .15);
          }
        }
      } else if (symbol === "bird") {
        // Two blue-white flame wings, with an open center for the real actor.
        for (const side of [-1, 1]) {
          const wing = [[-size * .55, side * size * .65],
            [-size * .25, side * size * 1.15], [size * .55, side * size * .70]];
          line(ctx, wing, 5, color);
          for (let i = 0; i < 3; i++)
            line(ctx, [[-size * (.9 + i * .18), side * size * (1.12 - i * .17)],
              [-size * .15, side * size * (.90 - i * .12)]], 2, color);
        }
        for (let i = -1; i <= 1; i++)
          line(ctx, [[-size * 1.45, i * size * .22], [-size * .8, i * size * .3]],
            2, color);
      } else if (symbol === "tail") {
        // A thick water arc around the real tail anchor, not a free-flying water ball.
        arc(ctx, 0, 0, size * .65, -2 + spin * .6, 3.2, 4, color);
        api.animations.sprite(ctx, "vb2-splash", Math.cos(-2 + spin * .6) * size * .65,
          Math.sin(-2 + spin * .6) * size * .65, size, 1, 0);
      } else if (symbol === "bone") {
        line(ctx, [[0, 0], [size * .8, 0]], 1, color);
        ctx.translate(size * .8, 0);
        arc(ctx, 0, 0, size * .6, spin, 3.2, 2, color);
        this.icon(ctx, api, "bone", 0, 0, size * 1.35, spin);
        // Ivory highlight follows the original bone contour.
        line(ctx, [[-size * .35 * Math.cos(spin - .5), -size * .35 * Math.sin(spin - .5)],
          [size * .35 * Math.cos(spin - .5), size * .35 * Math.sin(spin - .5)]], 1, "#fff0cf");
      }
      ctx.restore();
    },
    paint(ctx, e, api, charging = false) {
      const point = root(e.owner, e.m, e.a, api, e.age);
      e.drawAnchor = point;
      if (e.id === "shadowsneak" && !charging && e.vb2Start)
        line(ctx, [[e.vb2Start.x, e.vb2Start.y + 6], [point.x, point.y + 6]],
          5, styles[e.id].color);
      this.emblem(ctx, e, point, api, charging);
      if (charging || e.m.kind !== "rush") return;
      const h = e.owner.char.body.visibleSize[1], color = styles[e.id].color;
      for (const t of e.vb2Trail || []) {
        const age = api.animations.time - t.time;
        if (age <= 0 || age > .14) continue;
        ctx.save();
        ctx.globalAlpha = (1 - age / .14) * .65;
        const side = h * .48;
        for (const sign of [-1, 1]) {
          const x = t.x - Math.sin(e.a) * side * sign,
            y = t.y + Math.cos(e.a) * side * sign;
          line(ctx, [[x - Math.cos(e.a) * 9, y - Math.sin(e.a) * 9], [x, y]], 1, color);
        }
        ctx.restore();
      }
    },
    contact(ctx, b, api) {
      const color = styles[b.id].color, t = b.age / .26;
      ctx.save();
      ctx.globalAlpha = 1 - t;
      // Only near-contact swings need a final bridge. Rush motion is already native contact.
      if (b.vb2Move.limb)
        line(ctx, [[b.vb2Root.x, b.vb2Root.y], [b.x, b.y]], 3, color);
      const fake = { id: b.id, owner: b.vb2Owner, m: b.vb2Move,
        a: b.vb2Aim, age: b.age, contacted: true };
      if (["machpunch", "closecombat", "bonerush", "aquatail", "waterfall"].includes(b.id))
        this.emblem(ctx, fake, { x: b.x, y: b.y }, api);
      else for (let i = 0; i < 7; i++) {
        const a = i * Math.PI * 2 / 7, r = b.size * (.35 + t * .7);
        if (["flamecharge", "flamewheel"].includes(b.id))
          this.icon(ctx, api, "flame", b.x + Math.cos(a) * r, b.y + Math.sin(a) * r,
            b.size * .5, a);
        else line(ctx, [[b.x + Math.cos(a) * r, b.y + Math.sin(a) * r],
          [b.x + Math.cos(a) * (r + 8), b.y + Math.sin(a) * (r + 8)]], 3, color);
      }
      if (b.id === "waterfall") {
        for (let i = 0; i < 3; i++)
          api.animations.sprite(ctx, "vb2-splash", b.x, b.y + 15 - i * 15 - t * 28,
            b.size * .8, 1 - t);
      }
      if (["aquajet", "aquatail"].includes(b.id))
        api.animations.sprite(ctx, "vb2-splash", b.x, b.y, b.size * 1.2, 1 - t);
      if (b.id === "doubleedge") {
        // Emerald white flash adapted to a bounded three-body region, not global scene flicker.
        ctx.globalAlpha = Math.max(0, 1 - b.age / .07) * .7;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.size * 1.5, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    },
  };
  const Base = window.PoightR3GeneratedMoves;
  window.PoightR3GeneratedMoves = class extends Base {
    emit(p, a, target, api) {
      const result = super.emit(p, a, target, api);
      if (on(api, a.id)) {
        const e = this.states.findLast(e => e.group === a.group);
        const point = root(p, a.move, a.aim, api);
        if (e) { e.vb2Trail = []; e.vb2Start = { ...point }; }
        api.animations.releases.push({ id: a.id, ...point, anchor: { ...point },
          time: api.animations.time, vb2: true });
        api.animations.releases = api.animations.releases.slice(-32);
      }
      return result;
    }
    step(dt, api) {
      super.step(dt, api);
      for (const e of this.states) {
        if (!on(api, e.id) || e.m.kind !== "rush") continue;
        const trail = (e.vb2Trail ||= []), point = root(e.owner, e.m, e.a, api);
        if (!trail.length || api.animations.time - trail.at(-1).time >= .025)
          trail.push({ ...point, time: api.animations.time });
        e.vb2Trail = trail.filter(t => api.animations.time - t.time < .14);
      }
    }
    charge(ctx, p, m, lift, api) {
      if (!on(api, m.id)) return super.charge(ctx, p, m, lift, api);
      if (!p.attack || p.attack.emitted) return;
      window.PoightVB2.paint(ctx, { id: m.id, owner: p, m, a: p.attack.aim,
        age: p.attack.age }, api, true);
    }
    draw(ctx, layer, lift, api) {
      const all = this.states;
      this.states = all.filter(e => !on(api, e.id));
      try { super.draw(ctx, layer, lift, api); } finally { this.states = all; }
      for (const e of all) {
        if (!on(api, e.id)) continue;
        const below = ["shadowsneak", "phantomforce"].includes(e.id) ||
          api.anchor(e.owner, e.m, e.a)?.hidden;
        if ((layer === "below") !== !!below) continue;
        this.drawn.add(e.id);
        ctx.save();
        if (e.contacted || e.group.hit.size) api.animations.clipContactCenters(ctx);
        window.PoightVB2.paint(ctx, e, api);
        ctx.restore();
      }
    }
  };
  const Animations = window.PoightMoveAnimations;
  window.PoightMoveAnimations = class extends Animations {
    impact(target, source, m, ...args) {
      super.impact(target, source, m, ...args);
      if (!this.enabled || !styles[m.id]) return;
      const api = args.at(-1), b = this.bursts.at(-1), aim = source.attack?.aim ?? source.a;
      // Keep object references private: snapshot serializes only the pre-existing audit fields.
      Object.defineProperties(b, {
        vb2Root: { value: root(source, m, aim, api) },
        vb2Owner: { value: source }, vb2Move: { value: m }, vb2Aim: { value: aim },
        vb2Height: { value: source.char.body.visibleSize[1] }, vb2API: { value: api },
      });
      source.vb2Contact = { group: source.attack?.group, time: this.time };
    }
    draw(ctx) {
      ctx.save();
      this.clipContactCenters(ctx);
      for (const b of this.bursts)
        if (b.vb2Root) window.PoightVB2.contact(ctx, b, b.vb2API);
      ctx.restore();
      // Render-only copies: no metadata/physics mutation, no key/coordinate alias with other moves.
      // Emerald's contour plus subpixel snapping otherwise falls below the 0.8H raster floor.
      const all = this.bursts;
      this.bursts = all.map(b => b.vb2Root
        ? Object.defineProperty({ ...b, size: b.size * 1.12 }, 'ringTarget', { value: b.ringTarget })
        : b);
      try { super.draw(ctx); } finally { this.bursts = all; }
    }
  };
  const pose = window.PoightRevision3.pose.bind(window.PoightRevision3);
  window.PoightRevision3.pose = p => {
    const base = pose(p), a = p.attack;
    if (!a || a.id !== "phantomforce" ||
      new URLSearchParams(location.search).get("anim") === "old") return base;
    const revealed = p.vb2Contact?.group === a.group;
    return { ...base, alpha: revealed ? 1 : a.emitted ? .08 :
      Math.max(.08, 1 - a.age / Math.max(.001, a.hitTime)) };
  };
})();
