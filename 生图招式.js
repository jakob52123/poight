/* Raster-only move artwork. Combat state is driven by the real simulation, never RAF time. */
window.PoightGeneratedMoves = class {
  constructor(data) {
    this.data = data;
    this.images = new Map();
    this.loading = null;
    this.reset();
  }
  has(id) {
    return !!this.data[id];
  }
  async load(loader, ids = Object.keys(this.data)) {
    this.pending ||= new Map();
    const entries = [...new Set(ids)].filter(id => this.data[id]);
    const impact = entries.map(id => this.data[id]).find(d => d.fangImpact)?.fangImpact;
    if (impact && !this.fangImpact) {
      this.impactLoading ||= loader(impact).then(image => { this.fangImpact = image; })
        .finally(() => { this.impactLoading = null; });
      await this.impactLoading;
    }
    await Promise.all(entries.map(id => {
      if (this.images.has(id)) return;
      if (!this.pending.has(id)) this.pending.set(id, loader(this.data[id].src)
        .then(image => { this.images.set(id, image); })
        .finally(() => this.pending.delete(id)));
      return this.pending.get(id);
    }));
  }
  reset() {
    this.animations?.reset();
    this.states = [];
    this.emitted = 0;
    this.drawn = new Set();
    this.releases = [];
    this.fangPause = 0;
  }
  shown(p, id) {
    return this.states.some((e) => e.owner === p && e.id === id);
  }
  emit(p, a, target, api) {
    const d = this.data[a.id];
    if (!d) return false;
    const m = a.move || api.moves[a.id],
      ux = Math.cos(a.aim),
      uy = Math.sin(a.aim);
    this.emitted++;
    const anchor = api.anchor(p, m, a.aim);
    if (m.hero || m.limb || m.batch2) {
      this.releases.push({
        id: a.id,
        anchor,
        x: p.x,
        y: p.y,
        range: m.range,
        aim: a.aim,
        elapsed: api.elapsed(),
      });
      if (this.releases.length > 32) this.releases.shift();
    }
    const common = {
      id: a.id,
      owner: p,
      m,
      group: a.group,
      a: a.aim,
      age: 0,
      life: 0.48,
      x: p.x,
      y: p.y,
      ox: p.x,
      oy: p.y,
      lift: api.lift(p),
    };
    if (["shot", "fan", "beam"].includes(m.kind)) {
      const count = m.kind === "fan" ? m.count || 3 : 1;
      for (let i = 0; i < count; i++) {
        const angle = a.aim + (i - (count - 1) / 2) * (m.batch2 ? m.fanSpread || 0.16 : 0.16),
          dx = Math.cos(angle),
          dy = Math.sin(angle),
          origin = api.origin(p, m, m.batch2 ? a.aim : angle);
        if (!api.clearLine(p.x, p.y, origin.x, origin.y, Math.min(m.radius, 7))) {
          api.animations.hero.blockedOrigin(p, m, origin, api);
          continue;
        }
        api.projectile(api.animations.prepare({
          x: origin.x,
          y: origin.y,
          sx: origin.x,
          sy: origin.y,
          ux: dx,
          uy: dy,
          speed: m.speed,
          range: m.range,
          age: 0,
          owner: p,
          m,
          group: a.group,
          airFrom: api.lift(p),
          airTo: api.projectileLift(target, m),
          airDistance: Math.max(1, Math.hypot(target.x - p.x, target.y - p.y)),
          generated: true,
          variant: m.batch2 && a.id === "triattack" ? i : 0,
          visualOffset: origin.visualOffset,
          visualOffsetX: origin.visualOffsetX || 0,
          originAnchor: origin.anchor,
        }, api));
      }
      p.shots++;
      api.tone("shot");
      return true;
    }
    if (m.fangs) {
      p.punches++;
      window.PoightFangs.emit(this, common, target, api);
      api.tone("hit");
      return true;
    }
    if (m.limb) {
      p.punches++;
      this.states.push({ ...common, mode: "limb", life: m.recovery, front: 0, contacted: false });
      api.tone("hit");
      return true;
    }
    if (m.kind === "melee" || m.kind === "spin") {
      p.punches++;
      this.states.push({ ...common, mode: "melee", life: m.hero ? m.recovery : 0.34 });
      const dx = target.x - p.x,
        dy = target.y - p.y,
        dist = Math.hypot(dx, dy),
        dot = dist ? (dx * ux + dy * uy) / dist : 1;
      if (
        dist <= api.bodies.meleeRange(target, m.range, dx, dy, p) &&
        (m.kind === "spin" || dot > 0.42) &&
        api.clearLine(p.x, p.y, target.x, target.y, 2)
      )
        api.damage(target, p, m, ux, uy, a.group);
      api.tone("hit");
    } else if (m.kind === "rush") {
      this.states.push({
        ...common,
        mode: d.mode === "ride" ? "ride" : "rush",
        life: m.range / (m.rushSpeed || 630),
      });
      api.tone("dash");
    } else if (m.kind === "guard") {
      p.shield = m.damage;
      p.shieldUntil = api.elapsed() + m.duration;
      this.states.push({ ...common, mode: "support", life: m.duration });
      api.tone("guard");
    } else if (m.kind === "heal") {
      api.heal(p, m.damage, true);
      this.states.push({ ...common, mode: "support", life: 0.7 });
    } else if (m.kind === "buff") {
      p.buffs[m.boost] = m.duration;
      this.states.push({
        ...common,
        mode: a.id === "agility" ? "agility" : "support",
        life: a.id === "agility" ? 0.12 : 0.65,
        distance: 0,
      });
      api.tone("dash");
    } else if (m.kind === "nova") {
      if (api.animations.uses(a.id)) {
        this.states.push(api.animations.nova(common, target, api));
        api.tone("shot");
        return true;
      }
      this.states.push({ ...common, mode: "ground", life: 0.6 });
      const dx = target.x - p.x,
        dy = target.y - p.y,
        dist = Math.hypot(dx, dy) || 1;
      if (
        (a.id === "earthquake"
          ? api.bodies.rect(target, p.x - 72, p.y - 72, 144, 144)
          : api.bodies.circle(target, p.x, p.y, m.range)) &&
        api.clearLine(p.x, p.y, target.x, target.y, 3)
      )
        api.damage(target, p, m, dx / dist, dy / dist, a.group);
      api.tone("shot");
    } else if (m.kind === "zone") {
      const distance = Math.min(m.range, Math.hypot(target.x - p.x, target.y - p.y)),
        end = a.id === "thunder" ? a.targetPoint : api.landing(p, m, a.aim, target);
      if (a.id === "thunder" && !api.clearLine(p.x, p.y, end.x, end.y, 5)) return true;
      const mode = ["iciclecrash", "rockslide", "dracometeor"].includes(a.id)
        ? "lob"
        : a.id === "earthpower"
          ? "propagate"
          : "target";
      this.states.push({
        ...common,
        mode,
        ex: end.x,
        ey: end.y,
        life:
          a.id === "thunder"
            ? m.delay
            : mode === "propagate"
              ? Math.max(0.4, distance / 170)
              : Math.max(0.65, m.delay || 0.75),
        radius: Math.min(m.radius || 50, 65),
        landed: false,
      });
      p.shots++;
      api.tone("shot");
    }
    if (this.states.length > 100) this.states.splice(0, this.states.length - 100);
    return true;
  }
  step(dt, api) {
    for (const e of this.states) {
      if (e.fresh) e.fresh = false;
      else e.age += dt;
      const t = Math.min(1, e.age / e.life),
        target = e.owner === api.player ? api.enemy : api.player;
      if (e.mode === "fangs") window.PoightFangs.step(this, e, target, api);
      if (e.mode === "core-nova") api.animations.stepNova(e, target, api);
      if (e.mode === "limb") {
        const p = e.owner,
          ux = Math.cos(e.a),
          uy = Math.sin(e.a),
          end = api.rayEnd(p.x, p.y, e.a, e.m.range, 2);
        e.front = e.m.contactDelay > 0
          ? e.m.range * Math.min(1, e.age / e.m.contactDelay)
          : e.m.range;
        if (
          p.attack?.group !== e.group ||
          Math.hypot(end.x - p.x, end.y - p.y) + 0.1 < e.m.range
        ) {
          e.life = 0;
          continue;
        }
        if (e.age >= e.m.contactDelay && e.age <= e.m.contactDelay + e.m.contactWindow) {
          const dx = target.x - p.x,
            dy = target.y - p.y,
            distance = Math.hypot(dx, dy),
            dot = distance ? (dx * ux + dy * uy) / distance : 1;
          if (
            distance <= api.bodies.meleeRange(target, e.front, dx, dy, p) &&
            (e.m.kind === "spin" || dot > 0.42) &&
            api.clearLine(p.x, p.y, target.x, target.y, 2)
          ) {
            api.damage(target, p, e.m, ux, uy, e.group);
            e.contacted = true;
          }
        }
      }
      if (e.mode === "agility" && e.owner.hp > 0) {
        const delta = Math.min(e.m.range - e.distance, (e.m.range / 0.12) * dt);
        api.move(e.owner, Math.cos(e.a) * delta, Math.sin(e.a) * delta);
        e.distance += delta;
      }
      if (["lob", "propagate", "target"].includes(e.mode) && !e.landed) {
        if (e.mode === "propagate") {
          e.x = e.ox + (e.ex - e.ox) * t;
          e.y = e.oy + (e.ey - e.oy) * t;
        }
        if (e.age >= e.life) {
          e.landed = true;
          e.x = e.ex;
          e.y = e.ey;
          e.life += 0.35;
          const dx = target.x - e.x,
            dy = target.y - e.y,
            dist = Math.hypot(dx, dy) || 1;
          if (
            api.bodies.circle(target, e.x, e.y, e.radius) &&
            api.clearLine(e.ox, e.oy, e.x, e.y, 3) &&
            api.clearLine(e.x, e.y, target.x, target.y, 3)
          )
            api.damage(target, e.owner, e.m, dx / dist, dy / dist, e.group);
        }
      }
    }
    this.states = this.states.filter((e) => e.age < e.life && e.owner.hp > 0);
  }
  stamp(
    ctx, id, x, y, width, height, age,
    angle = 0, alpha = 1, anchor = "center", frame = null, variant = 0,
  ) {
    const d = this.data[id],
      im = this.images.get(id);
    if (!d) return;
    if (!im) throw new Error("招式图集尚未预载：" + id);
    this.drawn.add(id);
    const f = frame ?? Math.floor(Math.max(0, age) * 10) % d.frames;
    ctx.save();
    ctx.translate(Math.round(x), Math.round(y));
    ctx.rotate(angle);
    ctx.globalAlpha = alpha;
    ctx.imageSmoothingEnabled = false;
    const point = d.frameAnchors?.[f] || [d.ax, d.ay],
      ax = anchor === "source" ? point[0] / d.fw : 0.5,
      ay = anchor === "bottom" ? d.ay / d.fh : anchor === "source" ? point[1] / d.fh : 0.5;
    ctx.drawImage(im, variant * d.fw, f * d.fh, d.fw, d.fh, -width * ax, -height * ay, width, height);
    ctx.restore();
  }
  bullet(ctx, b, lift, api) {
    if (api.animations.bullet(ctx, b, lift, api)) {
      this.drawn.add(b.m.id);
      return true;
    }
    const d = this.data[b.m.id];
    if (!d) return false;
    const angle = Math.atan2(b.uy, b.ux),
      fade =
        (b.m.hero || b.m.batch2) && d.mode !== "stream"
          ? Math.max(
              0,
              1 - (b.m.returning ? Math.hypot(b.x - b.sx, b.y - b.sy) : b.age * b.speed) /
                b.airDistance,
            )
          : 1,
      x = b.x + (b.visualOffsetX || 0) * fade,
      y = b.y - 16 - lift + (b.visualOffset || 0) * fade;
    if (d.mode === "stream") {
      const len = Math.max(
        1,
        Math.min(b.m.range, Math.hypot(b.x - (b.sx ?? b.x), b.y - (b.sy ?? b.y))),
      );
      const im = this.images.get(b.m.id);
      if (im) {
        this.drawn.add(b.m.id);
        ctx.save();
        // A stream stays at the emitting mouth/cheek while its front advances.
        // Standalone projectiles below keep their frozen trajectory.
        const live =
          b.m.hero && b.owner.attack?.id === b.m.id ? api.anchor(b.owner, b.m, angle) : null;
        ctx.translate(live?.x ?? x - b.ux * len, live?.y ?? y - b.uy * len);
        ctx.rotate(angle);
        ctx.imageSmoothingEnabled = false;
        const f = Math.floor(b.age * 10) % 4;
        ctx.drawImage(
          im,
          d.ax,
          f * d.fh,
          Math.max(1, d.fw - d.ax),
          d.fh,
          0,
          (-d.height * d.ay) / d.fh,
          len,
          d.height,
        );
        ctx.restore();
      }
    } else
      this.stamp(
        ctx,
        b.m.id,
        x,
        y,
        d.width,
        d.height,
        b.age,
        b.m.id === "fireblast" ? 0 : angle + (b.m.id === "razorleaf" ? b.age * 8 : 0),
        1,
        "center",
        null,
        b.variant || 0,
      );
    return true;
  }
  limbStamp(ctx, p, m, age, api, charging = false, contacted = false) {
    const d = this.data[m.id],
      part =
        m.id === "closecombat" && !charging
          ? age >= 0.24
            ? "r1-foot"
            : age >= 0.12
              ? "r1-hand2"
              : m.anchor
          : m.anchor,
      anchor = api.anchor(p, { ...m, anchor: part }, p.attack?.aim ?? p.a);
    if (!anchor) return null;
    anchor.part = part;
    const body = p.char.body.nominalSize,
      scale = p.char.body.effectScale,
      progress = charging
        ? Math.min(1, p.attack.age / p.attack.hitTime)
        : Math.min(1, age / m.contactDelay),
      width = Math.min(d.width * scale, body * (m.id === "rapidspin" ? 1.3 : 0.7)),
      height = Math.min(d.height * scale, body * 0.65),
      // R1 is a finite sequence, not a looping stamp. Return light is hit-only.
      frame = charging ? 0 : Math.min(contacted || !m.leech ? 3 : 1, Math.floor(age / 0.10)),
      angle = p.attack?.aim ?? p.a;
    this.stamp(
      ctx,
      m.id,
      anchor.x,
      anchor.y,
      width * (charging && m.id === "bonerush" ? 0.7 + 0.3 * progress : 0.65 + 0.35 * progress),
      height,
      age,
      angle,
      charging ? 0.3 + 0.7 * progress : Math.min(1, (m.recovery - age) / 0.08),
      d.attachSource ? "source" : "center",
      frame,
    );
    // These short effects follow real alternate hands/feet, never extra drawn limbs.
    if (m.id === "crosschop") {
      const secondary = api.anchor(p, { ...m, anchor: "r1-hand2" }, angle);
      if (secondary)
        this.stamp(
          ctx,
          m.id,
          secondary.x,
          secondary.y,
          width * 0.7,
          height * 0.7,
          age,
          angle - 0.6,
          0.7,
          "center",
          frame,
        );
    }
    return anchor;
  }
  charge(ctx, p, m, lift, api) {
    if (api.animations.melee.has(m.id)) {
      api.animations.melee.charge(ctx, p, m, api);
      return;
    }
    if (!p.attack || p.attack.emitted || !this.has(m.id)) return;
    if (m.fangs) return;
    if (api.animations.lick(ctx, p, p.attack.move || m, p.attack.age, api, true)) return;
    if (api.animations.hero.charge(ctx, p, m, api)) return;
    if (m.limb) {
      this.limbStamp(ctx, p, m, p.attack.age, api, true);
      return;
    }
    if (m.batch2) {
      m = p.attack.move;
      const d = this.data[m.id],
        anchor = api.anchor(p, m, p.attack.aim),
        t = Math.min(1, p.attack.age / p.attack.hitTime);
      if (anchor) {
        // Raster gathering/holding follows the actual current sprite pose.
        const size = m.id === "rockthrow" ? 0.65 + 0.20 * t : 0.25 + 0.50 * t;
        this.stamp(
          ctx, m.id, anchor.x, anchor.y, d.width * size, d.height * size,
          p.attack.age, p.attack.aim, 0.4 + 0.6 * t,
        );
      }
      return;
    }
    if (m.id === "thunder") {
      const d = this.data[m.id],
        point = p.attack.targetPoint;
      this.stamp(ctx, m.id, point.x, point.y, d.width, d.height, 0, 0, 1, "bottom", 0);
      return;
    }
    if (!["solarbeam", "hyperbeam", "bonerush", "rockslide", "iciclecrash"].includes(m.id)) return;
    const d = this.data[m.id],
      t = Math.min(1, p.attack.age / p.attack.hitTime),
      a = p.attack.aim,
      dist = m.id === "bonerush" ? 22 : 0;
    this.stamp(
      ctx,
      m.id,
      p.x + Math.cos(a) * dist,
      p.y - 30 - lift - (m.id === "iciclecrash" ? 25 : 0),
      Math.min(d.width, 45) * (0.35 + 0.45 * t),
      Math.min(d.height, 45) * (0.35 + 0.45 * t),
      p.attack.age,
      m.id === "bonerush" ? a : 0,
      0.35 + 0.5 * t,
    );
  }
  draw(ctx, layer, lift, api) {
    for (const e of this.states) {
      ctx.save();
      // The physics-owned hit set identifies this cast, not an unrelated recent hit.
      if (e.contacted || e.group.hit.size) {
        const target = e.owner === api.player ? api.enemy : api.player;
        api.animations.clipContactCenters(ctx, e.contacted ? [target] : e.group.hit);
      }
      try {
      if (api.animations.hero.state(ctx, e, layer, api) || api.animations.melee.has(e.id)) {
        this.drawn.add(e.id);
        continue;
      }
      if (e.id === "lick" && layer === "above") {
        const mouth = api.animations.lick(ctx, e.owner, e.m, e.age, api);
        if (mouth) {
          e.drawAnchor = mouth; // The actual tongue root, preserving the original r1-mouth audit.
          this.drawn.add(e.id);
          continue;
        }
      }
      if (e.mode === "core-nova") {
        if (layer === "below") {
          this.drawn.add(e.id);
          api.animations.drawNova(ctx, e);
        }
        continue;
      }
      if (e.mode === "fangs") {
        window.PoightFangs.draw(this, ctx, e, layer);
        continue;
      }
      const d = this.data[e.id],
        below = ["ride", "ground", "propagate"].includes(e.mode) ||
          (e.mode === "limb" && api?.anchor(e.owner, e.m, e.a)?.hidden);
      if ((layer === "below") !== below) continue;
      const p = e.owner,
        bodyScale = p.char.body?.effectScale ?? 1,
        t = Math.min(1, e.age / (e.landed ? e.life - 0.35 : e.life)),
        alpha = e.landed ? Math.max(0, (e.life - e.age) / 0.35) : 1;
      const anchor = (e.m.hero || e.m.limb) && api ? api.anchor(p, e.m, e.a) : null;
      if (e.mode === "limb") {
        e.drawAnchor = this.limbStamp(ctx, p, e.m, e.age, api, false, e.contacted);
      } else if (anchor && e.mode === "melee") {
        e.drawAnchor = anchor;
        const paint = (g) =>
          this.stamp(
            g,
            e.id,
            anchor.x,
            anchor.y,
            d.width * bodyScale,
            d.height * bodyScale,
            e.age,
            e.a,
            alpha,
          );
        if (e.id === "irontail") {
          this.drawn.add(e.id);
          api.tailMask(ctx, p, anchor, paint);
        } else paint(ctx);
      } else if (e.mode === "melee") {
        const swing = Math.sin(t * Math.PI),
          a = e.a + (0.5 - t) * 0.9,
          dist = (e.id === "irontail" ? -12 : 20 + 8 * swing) * bodyScale;
        this.stamp(
          ctx,
          e.id,
          p.x + Math.cos(e.a) * dist,
          p.y - 18 - lift(p) + Math.sin(e.a) * dist,
          Math.min(d.width, 65) * bodyScale,
          Math.min(d.height, 54) * bodyScale,
          e.age,
          a,
          alpha,
        );
      } else if (["support", "agility", "rush", "ride"].includes(e.mode)) {
        const ride = e.mode === "ride";
        this.stamp(
          ctx,
          e.id,
          anchor?.x ?? p.x,
          anchor?.y ?? p.y - (ride ? -7 : 18) - lift(p),
          d.width * bodyScale,
          d.height * bodyScale,
          e.age,
          ride ? 0 : e.mode === "support" ? 0 : e.a,
          alpha,
          e.id === "quickattack" ? "source" : "center",
        );
      } else if (e.mode === "lob") {
        const x = e.landed ? e.ex : e.ox + (e.ex - e.ox) * t,
          y = e.landed
            ? e.ey
            : e.oy + (e.ey - e.oy) * t - 35 * (1 - t) - Math.sin(t * Math.PI) * 65;
        this.stamp(ctx, e.id, x, y, d.width, d.height, e.age, 0, alpha, "bottom");
      } else if (e.mode === "target" && e.id === "thunder") {
        const since = e.age - (e.life - 0.35),
          frame = !e.landed ? 0 : since < 0.1 ? 1 : since < 0.22 ? 2 : 3;
        this.stamp(ctx, e.id, e.ex, e.ey, d.width, d.height, e.age, 0, 1, "bottom", frame);
      } else if (e.mode === "target") {
        this.stamp(
          ctx,
          e.id,
          e.ex,
          e.ey - 10,
          d.width,
          d.height,
          e.age,
          0,
          e.landed ? alpha : 0.4 + 0.5 * t,
          "bottom",
        );
      } else this.stamp(ctx, e.id, e.x, e.y, d.width, d.height, e.age, 0, alpha, "bottom");
      } finally {
        ctx.restore();
      }
    }
  }
  stats() {
    return {
      bundled: Object.keys(this.data).length,
      loaded: this.images.size,
      active: this.states.length,
      emitted: this.emitted,
      drawn: [...this.drawn],
      releases: this.releases,
      fangPause: this.fangPause,
      states: this.states.map((e) => ({
        id: e.id,
        mode: e.mode,
        x: e.x,
        y: e.y,
        age: e.age,
        life: e.life,
        ex: e.ex,
        ey: e.ey,
        landed: e.landed,
        radius: e.radius,
        contactRadius: e.contactRadius,
        targetDistance: e.targetDistance,
        drawAnchor: e.drawAnchor,
        front: e.front,
        contacted: e.contacted,
        targeted: e.targeted,
        width: e.width,
        bodyWidth: e.bodyWidth,
        dimAge: e.dimAge,
        closures: e.closures,
        contacts: e.contacts,
        jaws: e.mode === "fangs" ? window.PoightFangs.jaws(e) : undefined,
      })),
    };
  }
};
