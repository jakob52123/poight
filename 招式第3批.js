/* R3-only raster playback and native-body poses. Other move paths stay in the base class. */
window.PoightRevision3 = {
  pose(p) {
    const a = p.attack;
    if (!a?.move?.r3) return { angle: 0, lift: 0, squash: 1, alpha: 1 };
    const active = a.emitted,
      time = active ? a.age - a.hitTime : a.age / Math.max(0.001, a.hitTime),
      progress = active ? Math.min(1, time / (a.move.range / (a.move.rushSpeed || 210))) : time,
      side = Math.cos(a.aim) >= 0 ? 1 : -1;
    if (["flamewheel", "rollout"].includes(a.id))
      return { angle: active ? time * 14 * side : -progress * 0.35 * side,
        lift: 0, squash: 1, alpha: 1 };
    if (a.id === "bodyslam")
      return { angle: (active ? Math.sin(progress * Math.PI) : -progress * 0.22) * side,
        lift: active ? Math.sin(progress * Math.PI) * 26 : Math.sin(progress * Math.PI / 2) * 12,
        squash: active ? 1 - 0.1 * Math.sin(progress * Math.PI) : 1, alpha: 1 };
    if (a.id === "waterfall")
      return { angle: 0, lift: active ? Math.sin(progress * Math.PI) * 13 : progress * 3,
        squash: 1, alpha: 1 };
    if (a.id === "shadowsneak")
      return { angle: 0, lift: 0, squash: active ? 0.72 : 1 - progress * 0.28,
        alpha: active ? 0.65 : 1 };
    if (["tackle", "doubleedge", "zenheadbutt", "machpunch"].includes(a.id))
      return { angle: (active ? 0.14 : -progress * (a.id === "doubleedge" ? 0.22 : 0.12)) * side,
        lift: 0, squash: 1, alpha: 1 };
    return { angle: 0, lift: 0, squash: 1, alpha: 1 };
  },
  transform(point, p) {
    const pose = this.pose(p),
      cx = p.x,
      cy = p.y - p.char.body.nominalSize * 0.38,
      dx = point.x - cx,
      dy = point.y - cy;
    return { ...point,
      x: cx + dx * Math.cos(pose.angle) - dy * pose.squash * Math.sin(pose.angle),
      y: cy + dx * Math.sin(pose.angle) + dy * pose.squash * Math.cos(pose.angle) - pose.lift };
  },
};

window.PoightR3GeneratedMoves = class extends window.PoightGeneratedMoves {
  emit(p, a, target, api) {
    if (!a.move?.r3 || this.data[a.id]) return super.emit(p, a, target, api);
    this.emitted++;
    this.states.push({ id: a.id, owner: p, m: a.move, group: a.group,
      a: a.aim, age: 0, life: a.move.range / a.move.rushSpeed,
      mode: "r3body", x: p.x, y: p.y });
    api.tone("dash");
    return true;
  }
  waveFront(p, m, aim, api) {
    const d = this.data[m.id], root = api.anchor(p, m, aim),
      reach = 24 + d.width * p.char.body.effectScale * 0.45;
    return { x: root.x + Math.cos(aim) * reach, y: root.y + Math.sin(aim) * reach };
  }
  waveReached(p, target, m, aim, api) {
    const front = this.waveFront(p, m, aim, api), ux = Math.cos(aim), uy = Math.sin(aim);
    return (target.x - front.x) * ux + (target.y - front.y) * uy
      <= api.bodies.reach(target, ux, uy);
  }
  returnFlow(p, target, m, api) {
    if (!m.r3 || !["absorb", "gigadrain"].includes(m.id)) return;
    const anchor = api.anchor(p, m, p.attack?.aim ?? p.a);
    this.states.push({ id: m.id, owner: p, m, age: 0, life: 0.48,
      mode: "r3return", x: target.x, y: target.y - 16 - api.lift(target),
      ex: anchor?.x ?? p.x, ey: anchor?.y ?? p.y - 25 });
  }
  bullet(ctx, b, lift, api) {
    if (!b.m.r3 || api.animations.uses(b.m.id)) return super.bullet(ctx, b, lift, api);
    const d = this.data[b.m.id], im = this.images.get(b.m.id);
    if (!d || !im) return false;
    this.drawn.add(b.m.id);
    const angle = Math.atan2(b.uy, b.ux),
      root = (b.owner.attack?.id === b.m.id ? api.anchor(b.owner, b.m, angle) : null)
        ?? b.originAnchor ?? { x: b.sx ?? b.x, y: (b.sy ?? b.y) - 16 - lift },
      travel = Math.hypot(b.x - b.sx, b.y - b.sy),
      fade = Math.max(0, 1 - travel / b.airDistance),
      fx = b.x + (b.visualOffsetX || 0) * fade,
      fy = b.y - 16 - lift + (b.visualOffset || 0) * fade,
      dx = fx - root.x, dy = fy - root.y,
      length = Math.min(b.m.range, Math.max(1, Math.hypot(dx, dy))),
      frame = Math.floor(b.age * 10) % d.frames;
    b.drawAnchor = root;
    b.visualFront = { x: fx, y: fy };
    ctx.save();
    ctx.translate(root.x, root.y);
    ctx.rotate(Math.atan2(dy, dx));
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(im, d.ax, frame * d.fh, Math.max(1, d.fw - d.ax), d.fh,
      0, -d.height * d.ay / d.fh, length, d.height);
    ctx.restore();
    return true;
  }
  charge(ctx, p, m, lift, api) {
    if (api.animations.melee.has(m.id)) {
      api.animations.melee.charge(ctx, p, m, api);
      return;
    }
    if (!m.r3) return super.charge(ctx, p, m, lift, api);
    if (!p.attack || p.attack.emitted || !this.data[m.id]) return;
    const d = this.data[m.id], anchor = api.anchor(p, m, p.attack.aim),
      t = p.attack.age / Math.max(0.001, p.attack.hitTime);
    if (m.kind === "beam" && !["solarbeam", "hyperbeam"].includes(m.id)) return;
    this.stamp(ctx, m.id, anchor.x, anchor.y, Math.min(d.width, 20) * t,
      Math.min(d.height, 16) * t, p.attack.age, p.attack.aim, 0.2 + t * 0.4);
  }
  stats() {
    const result = super.stats();
    result.states.forEach((e, index) => {
      if (this.states[index].visibleFront) e.visibleFront = this.states[index].visibleFront;
    });
    return result;
  }
  draw(ctx, layer, lift, api) {
    const all = this.states;
    this.states = all.filter((e) => !e.m.r3);
    super.draw(ctx, layer, lift, api);
    this.states = all;
    for (const e of all) {
      if (api.animations.melee.has(e.id)) {
        this.drawn.add(e.id);
        continue;
      }
      if (!e.m.r3) continue;
      const d = this.data[e.id], p = e.owner,
        anchor = api.anchor(p, e.m, e.a ?? p.a);
      e.drawAnchor = anchor;
      if (!d) continue; // Animation-only rush: the actual native sprite is the effect.
      if (e.mode === "r3return") {
        if (layer !== "above") continue;
        const t = Math.min(1, e.age / e.life);
        this.stamp(ctx, e.id, e.x + (e.ex - e.x) * t, e.y + (e.ey - e.y) * t,
          24, 10, e.age, Math.atan2(e.ey - e.y, e.ex - e.x), 1 - 0.4 * t);
      } else if (e.mode === "melee") {
        // Absorb shows only real contact return, never a generic fake melee arc.
        this.drawn.add(e.id);
      } else if (["rush", "ride"].includes(e.mode)) {
        const below = ["surf", "shadowsneak"].includes(e.id);
        if ((layer === "below") !== below) continue;
        if (e.id === "surf") e.visibleFront = this.waveFront(p, e.m, e.a, api);
        const scale = p.char.body.effectScale,
          alpha = e.id === "bravebird" ? 0.42 : e.id === "aquajet" ? 0.62 : 0.68;
        if (e.id === "shadowsneak") {
          const length = Math.min(e.m.range, e.age * e.m.rushSpeed + 22);
          this.stamp(ctx, e.id, e.ox + Math.cos(e.a) * length / 2,
            e.oy + Math.sin(e.a) * length / 2, length, 15, e.age, e.a, 0.7);
        } else this.stamp(ctx, e.id,
          anchor.x + (e.id === "surf" ? Math.cos(e.a) * 24 : 0),
          anchor.y + (e.id === "surf" ? Math.sin(e.a) * 24 : 0),
          d.width * scale, d.height * scale, e.age,
          e.id === "waterfall" ? -Math.PI / 2 : e.a, alpha,
          e.id === "surf" ? "bottom" : "center");
      }
    }
  }
};
