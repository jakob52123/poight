/* Local Showdown BW atlases. Canvas CSS pixels equal backing pixels: no fractional scaling. */
window.PoightPortraits = function (catalog, loadImage) {
  const assets = new Map(), states = new Map();
  function preload(id) {
    if (!assets.has(id)) assets.set(id, loadImage(catalog[id].src));
    return assets.get(id);
  }
  function set(el, id, side) {
    if (el.dataset.id === String(id) && el.dataset.side === side) return;
    el.dataset.id = id;
    el.dataset.side = side;
    delete el.dataset.frame;
    states.delete(el);
    const d = catalog[id];
    preload(id).then((image) => {
      if (el.dataset.id === String(id) && el.dataset.side === side) {
        states.set(el, { d, image, side, frame: -1, scale: 0 });
      }
    });
  }
  function animate(now) {
    for (const [el, state] of states) {
      if (!el.checkVisibility()) continue;
      const { d, image, side } = state;
      const stage = el.parentElement.getBoundingClientRect();
      const gba = document.documentElement.dataset.gba,
        fit = Math.min(gba && el.closest(".winner-art, #vsScreen") ? 12 : 3,
          Math.floor(Math.min(stage.width / d.width, stage.height / d.height))),
        scale = gba ? Math.max(1, fit) : fit;
      if (scale < (gba ? 1 : 2)) continue;
      let age = now % d.durations.reduce((a, b) => a + b, 0), frame = 0;
      while (frame < d.frames - 1 && age >= d.durations[frame]) age -= d.durations[frame++];
      if (state.frame === frame && state.scale === scale) continue;
      state.frame = frame;
      state.scale = scale;
      el.width = d.width * scale;
      el.height = d.height * scale;
      el.style.width = `${el.width}px`;
      el.style.height = `${el.height}px`;
      el.dataset.frame = frame;
      el.dataset.scale = scale;
      el.dataset.facing = side === "player" ? "right" : "left";
      const g = el.getContext("2d");
      g.imageSmoothingEnabled = false;
      if (side === "player") {
        g.translate(el.width, 0);
        g.scale(-1, 1);
      }
      g.drawImage(
        image,
        (frame % d.columns) * d.width,
        Math.floor(frame / d.columns) * d.height,
        d.width,
        d.height,
        0,
        0,
        el.width,
        el.height,
      );
    }
    requestAnimationFrame(animate);
  }
  return { set, animate, preload };
};
