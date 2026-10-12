/* Shared scene contract: grassRegions = [{x,y,w,h}, {points:[{x,y}, ...]}].
 * Actor x/y is the ground-plane footprint centre (not the sprite/label centre).
 * Native grass is derived once from behavior cells, without touching field-effect art.
 */
"use strict";
window.PoightGrassStealth = class PoightGrassStealth {
  static nativeRegions(world) {
    const result = [];
    for (let row = 0; row < world.rows; row++) {
      let start = -1;
      for (let col = 0; col <= world.columns; col++) {
        const grass = col < world.columns && world.grassType(col * world.cell, row * world.cell);
        if (grass && start < 0) start = col;
        if (!grass && start >= 0) {
          result.push({
            x: start * world.cell,
            y: row * world.cell,
            w: (col - start) * world.cell,
            h: world.cell,
          });
          start = -1;
        }
      }
    }
    return result;
  }
  configure(scene, world) {
    // An explicit empty list opts out, even on a native map.
    this.regions = (scene.grassRegions ?? world?.data.grassRegions ?? []).map((region) =>
      this.points(region) ? region : {
        ...region, w: region.w ?? region.width, h: region.h ?? region.height,
      },
    );
    this.reset();
  }
  reset() {
    this.actors = new WeakMap();
    this.lastSeen = null;
    this.searchIndex = 0;
    this.searchGoal = null;
    this.retreat = null;
  }
  state(p) {
    if (!this.actors.has(p))
      this.actors.set(p, { hidden: false, entered: null, cast: 0, hit: -Infinity });
    return this.actors.get(p);
  }
  points(region) {
    return (Array.isArray(region) ? region : region.points)?.map((p) =>
      Array.isArray(p) ? { x: p[0], y: p[1] } : p,
    );
  }
  contains(region, x, y) {
    const points = this.points(region);
    if (!points)
      return x >= region.x && y >= region.y && x < region.x + region.w && y < region.y + region.h;
    let inside = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
      const a = points[i],
        b = points[j];
      // Include polygon boundary, just like a footprint centre on the grass edge.
      const cross = (x - a.x) * (b.y - a.y) - (y - a.y) * (b.x - a.x);
      if (
        Math.abs(cross) < 1e-7 &&
        x >= Math.min(a.x, b.x) &&
        x <= Math.max(a.x, b.x) &&
        y >= Math.min(a.y, b.y) &&
        y <= Math.max(a.y, b.y)
      )
        return true;
      if (a.y > y !== b.y > y && x < ((b.x - a.x) * (y - a.y)) / (b.y - a.y) + a.x)
        inside = !inside;
    }
    return inside;
  }
  inGrass(p) {
    return !p.worldAbsent && !(p.diveLeft > 0) &&
      this.regions.some((r) => this.contains(r, p.x, p.y));
  }
  grounded(p) {
    return p.hp > 0 && !p.char.flightHeight && !p.jump && !(p.jumpHeight > 2);
  }
  hidden(p) {
    return !!p && this.state(p).hidden;
  }
  event(p, kind, now) {
    const state = this.state(p);
    state[kind] = now;
    state.hidden = false;
  }
  update(now, player, enemy) {
    const close = Math.hypot(player.x - enemy.x, player.y - enemy.y) < 70;
    for (const p of [player, enemy]) {
      const s = this.state(p);
      if (!this.grounded(p) || !this.inGrass(p)) {
        s.entered = null;
        s.hidden = false;
        continue;
      }
      if (s.entered === null) s.entered = now;
      s.hidden =
        !close &&
        !p.attack &&
        now - s.entered >= 0.8 - 1e-7 &&
        now - s.cast >= 0.8 - 1e-7 &&
        now - s.hit >= 1.5 - 1e-7;
    }
    if (!this.hidden(player)) {
      this.lastSeen = { x: player.x, y: player.y };
      this.searchGoal = null;
      this.searchIndex = 0;
    }
  }
  nearest(p, radius, reachable) {
    const candidates = [];
    for (const region of this.regions) {
      const points = this.points(region),
        left = points ? Math.min(...points.map((q) => q.x)) : region.x,
        top = points ? Math.min(...points.map((q) => q.y)) : region.y,
        right = points ? Math.max(...points.map((q) => q.x)) : region.x + region.w,
        bottom = points ? Math.max(...points.map((q) => q.y)) : region.y + region.h;
      if (
        right < p.x - radius ||
        left > p.x + radius ||
        bottom < p.y - radius ||
        top > p.y + radius
      )
        continue;
      const add = (x, y) => {
        const d = Math.hypot(x - p.x, y - p.y);
        if (d <= radius && this.contains(region, x, y)) candidates.push({ x, y, d });
      };
      add(
        Math.max(left + 1, Math.min(right - 1, p.x)),
        Math.max(top + 1, Math.min(bottom - 1, p.y)),
      );
      add((left + right) / 2, (top + bottom) / 2);
      for (let y = Math.max(top + 4, p.y - radius); y < Math.min(bottom, p.y + radius); y += 16)
        for (let x = Math.max(left + 4, p.x - radius); x < Math.min(right, p.x + radius); x += 16)
          add(x, y);
    }
    candidates.sort((a, b) => a.d - b.d);
    return candidates.find((q) => reachable(q.x, q.y)) || null;
  }
  think({ player, enemy, brain, tier, navigate, reachable }) {
    if (enemy.dash || enemy.hurt > 0 || enemy.attack) {
      if (this.hidden(player)) brain.mx = brain.my = 0;
      return this.hidden(player);
    }
    // Recovery is a commitment: reach cover and rest, instead of abandoning it
    // as soon as ordinary regeneration crosses the 30% trigger threshold.
    if (tier !== "poke" && this.grounded(enemy)) {
      if (enemy.stamina >= 65) this.retreat = null;
      if (!this.retreat && enemy.stamina < 30) this.retreat = this.nearest(enemy, 200, reachable);
      if (this.retreat) {
        brain.mx = brain.my = 0;
        if (this.inGrass(enemy)) brain.mode = "草丛休息";
        else {
          const v = navigate(this.retreat.x, this.retreat.y);
          brain.mx = v.x;
          brain.my = v.y;
          brain.mode = "进草丛回体力";
        }
        return true;
      }
    } else this.retreat = null;
    if (!this.hidden(player)) return false;
    brain.mx = brain.my = 0;
    // No casts at all against an unseen target. Search coordinates use only
    // remembered information; neither aim nor path receives its live position.
    const known = this.lastSeen || { x: enemy.x, y: enemy.y };
    let goal = known;
    if (this.searchGoal || Math.hypot(enemy.x - known.x, enemy.y - known.y) < 22) {
      if (
        !this.searchGoal ||
        Math.hypot(enemy.x - this.searchGoal.x, enemy.y - this.searchGoal.y) < 18
      ) {
        const a = this.searchIndex++ * 2.399963;
        const next = { x: known.x + Math.cos(a) * 95, y: known.y + Math.sin(a) * 95 };
        this.searchGoal = reachable(next.x, next.y) ? next : { ...known };
      }
      goal = this.searchGoal;
      brain.mode = "附近搜索";
    } else brain.mode = "最后已知位置";
    const v = navigate(goal.x, goal.y);
    brain.mx = v.x;
    brain.my = v.y;
    return true;
  }
  invisible(p) {
    return !p.isPlayer && this.hidden(p);
  }
  alpha(p) {
    return this.hidden(p) ? (p.isPlayer ? 0.4 : 0) : 1;
  }
  hud(p, box) {
    const hidden = this.invisible(p);
    box.style.visibility = hidden ? "hidden" : "";
    box.setAttribute("aria-hidden", String(hidden));
  }
  drawGenerated(generated, ctx, layer, lift, api) {
    // Attached guard/rush artwork must not disclose an invisible actor. Detached
    // projectiles/ground effects remain visible and retain their combat behavior.
    const states = generated.states;
    try {
      generated.states = states.filter(
        (e) => !this.invisible(e.owner) || !["support", "rush", "ride", "agility"].includes(e.mode),
      );
      generated.draw(ctx, layer, lift, api);
    } finally {
      generated.states = states;
    }
  }
  draw(ctx, actors, now) {
    for (const p of actors) {
      if (!this.hidden(p)) continue;
      ctx.save();
      // Player gets a clear leaf ring; enemy gets only a tiny, slow grass stir.
      ctx.globalAlpha = p.isPlayer ? 0.8 : 0.09;
      ctx.fillStyle = "#b5d878";
      const count = p.isPlayer ? 9 : 3;
      for (let i = 0; i < count; i++) {
        const a = (i / count) * Math.PI * 2,
          r = p.isPlayer ? 23 : 9,
          sway = Math.sin(now * 2.5 + i) * (p.isPlayer ? 0.4 : 0.8);
        ctx.beginPath();
        ctx.ellipse(
          p.x + Math.cos(a) * r + sway,
          p.y + 12 + Math.sin(a) * r * 0.4,
          2,
          4,
          a + 0.5,
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }
      ctx.restore();
    }
  }
  snapshot(p) {
    const s = this.state(p);
    return { hidden: s.hidden, inGrass: this.inGrass(p), alpha: this.alpha(p), entered: s.entered };
  }
};
