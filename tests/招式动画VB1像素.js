// Read-only real Canvas probe. Same draw calls, same transforms; no replacement colors/geometry.
() => {
  window.vb1Probe = { enabled: false, suppress: false, records: [], pose: [], flows: [] };
  const proto = window.PoightMeleeVB1.prototype, symbol = proto.symbol, pose = proto.pose,
    core = window.PoightMoveAnimations.prototype, burst = core.drawBurst, lick = core.lick;
  proto.pose = function (p) {
    const result = pose.call(this, p);
    window.vb1Probe.poseInstances = this.activePoses.length;
    if (this.has(p.attack?.id) || p.attack?.id === 'lick') window.vb1Probe.pose.push({
      id: p.attack.id, age: p.attack.age,
      impact: p.attack.hitTime + (p.attack.move.contactDelay || 0),
      height: p.char.body.visibleSize[1], ...result,
    });
    window.vb1Probe.pose = window.vb1Probe.pose.slice(-500);
    return result;
  };
  function layer(ctx) {
    const canvas = document.createElement("canvas");
    canvas.width = ctx.canvas.width;
    canvas.height = ctx.canvas.height;
    const c = canvas.getContext("2d");
    c.setTransform(ctx.getTransform());
    c.imageSmoothingEnabled = false;
    return [canvas, c];
  }
  const flow = proto.draw, stamp = proto.stamp;
  proto.draw = function (ctx) {
    const probe = window.vb1Probe;
    probe.flowLayers = [];
    probe.inFlow = true;
    try { return flow.call(this, ctx); } finally { probe.inFlow = false; }
  };
  proto.stamp = function (ctx, shape, color, x, y, size, ...rest) {
    const probe = window.vb1Probe;
    if (probe.inFlow && shape === "orb" && color === "green") {
      probe.flows.push({ x, y, size, time: this.adapter.time });
      probe.flows = probe.flows.slice(-100);
      if (probe.enabled) {
        const [canvas, c] = layer(ctx);
        stamp.call(this, c, shape, color, x, y, size, ...rest);
        probe.flowLayers.push({ canvas, matrix: ctx.getTransform() });
      }
    }
    return stamp.call(this, ctx, shape, color, x, y, size, ...rest);
  };
  window.measureVB1Flow = () => {
    const layers = window.vb1Probe.flowLayers;
    return layers.map(({ canvas, matrix }) => {
      const inverse = matrix.inverse(), d = canvas.getContext("2d")
        .getImageData(0, 0, canvas.width, canvas.height).data;
      let count = 0, green = 0, minX = Infinity, maxX = -Infinity,
        minY = Infinity, maxY = -Infinity;
      for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
        const i = (y * canvas.width + x) * 4;
        if (d[i + 3] < 250) continue;
        const p = new DOMPoint(x + .5, y + .5).matrixTransform(inverse);
        minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
        count++; if (d[i + 1] > d[i] && d[i + 1] > d[i + 2]) green++;
      }
      return { count, greenFraction: green / Math.max(1, count),
        diameter: Math.max(maxX - minX, maxY - minY) + 1 / matrix.a };
    });
  };
  proto.symbol = function (ctx, b) {
    const probe = window.vb1Probe;
    if (!b.vb1) return symbol.call(this, ctx, b);
    probe.records.push({ id: b.id, x: b.x, y: b.y, age: b.age, time: this.adapter.time });
    probe.records = probe.records.slice(-500);
    if (!probe.enabled) return symbol.call(this, ctx, b);
    const [canvas, c] = layer(ctx);
    this.adapter.clipContactCenters(c);
    symbol.call(this, c, b);
    probe.last = { canvas, matrix: ctx.getTransform(), b };
    if (!probe.suppress) symbol.call(this, ctx, b);
  };
  core.lick = function (ctx, p, m, ...rest) {
    const probe = window.vb1Probe;
    if (m.id !== 'lick' || !probe.enabled) return lick.call(this, ctx, p, m, ...rest);
    const [canvas, c] = layer(ctx);
    this.clipContactCenters(c);
    const root = lick.call(this, c, p, m, ...rest);
    probe.tongue = { canvas, matrix: ctx.getTransform() };
    if (!probe.suppress) lick.call(this, ctx, p, m, ...rest);
    return root;
  };
  core.drawBurst = function (ctx, b, ...rest) {
    const probe = window.vb1Probe;
    if (b.id === 'lick') {
      probe.records.push({id:b.id,x:b.x,y:b.y,age:b.age,time:this.time});
      if (probe.tongue) probe.last = {...probe.tongue,b};
    }
    if (probe.enabled) {
      const [canvas, c] = layer(ctx);
      this.clipContactCenters(c);
      burst.call(this, c, b, ...rest);
      probe.star = { canvas, matrix: ctx.getTransform(), size:b.size };
      if (probe.suppress) return;
    }
    return burst.call(this, ctx, b, ...rest);
  };
  window.measureVB1Pixels = () => {
    const probe = window.vb1Probe, entry = probe.last, star = probe.star,
      api = window.__waterTest, game = document.querySelector("#game"),
      composite = game.toDataURL();
    probe.suppress = true;
    api.step(0);
    const background = game.toDataURL(), bg = game.getContext("2d")
      .getImageData(0, 0, game.width, game.height).data;
    probe.suppress = false;
    api.step(0);
    const lum = (r, g, b) => .2126 * r + .7152 * g + .0722 * b;
    function measure(layer, color = true) {
      const { canvas, matrix } = layer, inverse = matrix.inverse(),
        data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
      let count = 0, colored = 0, sat = 0, fg = 0, back = 0,
        minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
        const i = (y * canvas.width + x) * 4;
        if (data[i + 3] < 250) continue;
        const p = new DOMPoint(x + .5, y + .5).matrixTransform(inverse),
          r = data[i], g = data[i + 1], b = data[i + 2], maximum = Math.max(r, g, b),
          s = maximum ? (maximum - Math.min(r, g, b)) / maximum : 0;
        minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
        minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
        if (s > .12) { colored++; sat += s; }
        fg += lum(r, g, b);
        back += lum(bg[i], bg[i + 1], bg[i + 2]);
        count++;
      }
      return { count, diameter: Math.max(maxX - minX, maxY - minY) + 1 / matrix.a,
        saturation: color ? sat / Math.max(1, colored) : null,
        colorFraction: colored / Math.max(1, count),
        contrast: Math.abs(fg - back) / Math.max(1, count),
        foreground: fg / Math.max(1, count), background: back / Math.max(1, count) };
    }
    return { ...measure(entry), star: measure(star, false),
      height: entry.b.height, id: entry.b.id,
      composite, background, mask: entry.canvas.toDataURL(), starMask: star.canvas.toDataURL() };
  };
}
