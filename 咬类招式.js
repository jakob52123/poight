/* Emerald BITE/CRUNCH geometry, independent of the caster's eight headings. */
window.PoightFangs = class {
  static center(p, api) {
    const [width, height] = p.char.body.visibleSize;
    return { x: p.x, y: p.y + 14 - height / 2 - api.bodyLift(p), width, height };
  }
  static eligible(e, target, api) {
    const p = e.owner,
      dx = target.x - p.x,
      dy = target.y - p.y,
      distance = Math.hypot(dx, dy),
      dot = distance ? (dx * Math.cos(e.a) + dy * Math.sin(e.a)) / distance : 1;
    return (
      distance <= api.bodies.meleeRange(target, e.m.range, dx, dy, p) &&
      dot > 0.42 &&
      api.clearLine(p.x, p.y, target.x, target.y, 2)
    );
  }
  static locate(e, target, api) {
    const eligible = this.eligible(e, target, api),
      hit = e.contacted || eligible,
      body = this.center(hit ? target : e.owner, api);
    e.x = hit ? body.x : e.owner.x + Math.cos(e.a) * e.m.range;
    e.y = hit ? body.y : body.y + Math.sin(e.a) * e.m.range;
    e.targeted = eligible;
    e.bodyWidth = body.width;
    e.width = body.width * 1.15;
    e.radius = body.height * 3;
    e.drawAnchor = { x: e.x, y: e.y, part: "target-body" };
  }
  static windup(engine, p, a, target, api) {
    const e = {
      id: a.id, owner: p, m: a.move, group: a.group, a: a.aim,
      age: -a.hitTime, life: a.move.recovery, mode: "fangs", preview: true,
      closures: [], contacts: [], dimAge: 0, front: 0, contacted: false,
    };
    this.locate(e, target, api);
    engine.states.push(e);
  }
  static emit(engine, common, target, api) {
    const preview = engine.states.find((e) => e.mode === "fangs" && e.group === common.group);
    if (preview) {
      Object.assign(preview, { age: 0, preview: false, fresh: true, front: common.m.range });
      this.step(engine, preview, target, api);
      return;
    }
    const e = {
      ...common,
      mode: "fangs",
      life: common.m.recovery,
      closures: [],
      contacts: [],
      dimAge: 0,
      front: 0,
      contacted: false,
    };
    this.locate(e, target, api);
    engine.states.push(e);
  }
  static step(engine, e, target, api) {
    const p = e.owner,
      end = api.rayEnd(p.x, p.y, e.a, e.m.range, 2);
    if (p.attack?.group !== e.group || Math.hypot(end.x - p.x, end.y - p.y) + 0.1 < e.m.range) {
      e.life = 0;
      return;
    }
    this.locate(e, target, api);
    if (e.preview) {
      e.age = Math.min(0, p.attack.age - p.attack.hitTime);
      return;
    }
    e.front = e.m.range;
    const count = e.id === "crunch" ? 2 : 1;
    for (let bite = e.closures.length; bite < count; bite++) {
      const close = bite * .12;
      if (e.age + 1e-9 < close) break;
      e.closures.push({ bite, age: e.age, x: e.x, y: e.y });
      if (!e.targeted) continue;
      const dx = Math.cos(e.a),
        dy = Math.sin(e.a),
        // Calculate normal rounded damage first, then split it. No double rounding.
        move = {
          ...e.m,
          hitFraction: 1 / count,
          knockScale: bite < count - 1 ? 0 : 1,
        },
        group = { ...e.group, hit: new Set(), fangSequence: e.group, fangBite: bite };
      if (api.damage(target, p, move, dx, dy, group)) {
        e.contacted = true;
        e.contacts.push({ bite, age: e.age });
        engine.fangPause = Math.max(engine.fangPause, 2 / 60);
      }
    }
  }
  static presentationStep(engine, dt) {
    for (const e of engine.states)
      if (e.mode === "fangs") e.dimAge += dt;
  }
  static jaws(e) {
    const bite = e.id === "crunch" && e.age > 0 ? 1 : 0,
      age = e.age - bite * .12,
      // Opening belongs to the actual H1 windup; closure is damage-authoritative.
      gap = e.preview ? Math.min(1, -e.age / e.m.windup)
        : bite && e.age < .12 ? Math.sin(Math.PI * e.age / .12)
          : Math.min(1, Math.max(0, age) / .10),
      offset = 32 * (e.width / 64) * gap,
      diagonal = e.id === "crunch",
      x = diagonal ? (bite === 0 ? -offset : offset) : 0,
      angle = diagonal ? (bite === 0 ? -Math.PI / 4 : Math.PI / 4) : 0;
    return [
      { x: e.x + x, y: e.y - offset, angle },
      { x: e.x - x, y: e.y + offset, angle: angle + Math.PI },
    ];
  }
  static pulse(e) {
    const last = e.contacts.at(-1);
    if (!last) return 0;
    return Math.max(0, 1 - (e.age - last.age) / .14);
  }
  static shake(engine, p = null) {
    let value = 0;
    for (const e of engine.states) {
      if (e.mode !== "fangs" || (p && p === e.owner)) continue;
      const pulse = this.pulse(e),
        strength = e.contacts.at(-1)?.bite === 1 ? 4 : 2;
      value += Math.round(
        Math.cos((e.age - (e.contacts.at(-1)?.age || 0)) * 100) * pulse * strength,
      );
    }
    return value;
  }
  static draw(engine, ctx, e, layer) {
    if (layer === "below") {
      if (e.id !== "crunch") return;
      const age = e.dimAge ?? e.age,
        alpha = .46 * Math.min(1, age / .04, Math.max(0, (.6 - age) / .16)),
        gradient = ctx.createRadialGradient(e.x, e.y, 0, e.x, e.y, e.radius);
      gradient.addColorStop(0, `rgba(18,12,30,${alpha})`);
      gradient.addColorStop(.65, `rgba(18,12,30,${alpha * .6})`);
      gradient.addColorStop(1, "rgba(18,12,30,0)");
      ctx.fillStyle = gradient;
      ctx.fillRect(e.x - e.radius, e.y - e.radius, e.radius * 2, e.radius * 2);
      return;
    }
    const jaws = this.jaws(e),
      alpha = e.preview ? 1 : Math.min(1, Math.max(0, (e.life - e.age) / .045));
    for (const jaw of jaws)
      engine.stamp(ctx, e.id, jaw.x, jaw.y, e.width, e.width, 0, jaw.angle, alpha, "center", 0);
    const closure = e.closures.at(-1),
      pulse = closure ? Math.max(0, 1 - (e.age - closure.age) / .12) : 0,
      image = engine.fangImpact;
    if (pulse && image) {
      const size = e.width * .65;
      ctx.save();
      ctx.globalAlpha = pulse;
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(image, e.x - size / 2, e.y - size / 2, size, size);
      if (e.id === "firefang") {
        ctx.fillStyle = "#ffd46b";
        for (let i = 0; i < 6; i++) {
          const angle = (i * Math.PI) / 3,
            radius = size * (.4 + .6 * (1 - pulse));
          ctx.fillRect(
            Math.round(e.x + Math.cos(angle) * radius),
            Math.round(e.y + Math.sin(angle) * radius),
            2,
            2,
          );
        }
      }
      ctx.restore();
    }
  }
};
