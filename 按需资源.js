/* R200: lossless per-character metadata. An opaque RGB PNG byte envelope keeps
 * connect-src 'none' on HTTP. file:// uses only build-generated local literals
 * because both fetch and canvas reads are blocked for file origins.
 * Four big-endian length bytes + UTF-8 JSON + zero padding, no alpha rounding.
 */
window.PoightCharacterMetadata = function (refs, art, byID, loadImage) {
  const pending = new Map();
  window.PoightOfflineArt = Object.create(null);
  return async function load(id) {
    if (art[id]) return art[id];
    if (!pending.has(id)) pending.set(id, (async () => {
      if (location.protocol === "file:") {
        await new Promise((resolve, reject) => {
          const script = document.createElement("script");
          script.charset = "utf-8";
          script.src = refs[id].offline;
          script.onload = () => { script.remove(); resolve(); };
          script.onerror = () => { script.remove(); reject(new Error("离线角色元数据加载失败：" + id)); };
          document.head.append(script);
        });
        const value = window.PoightOfflineArt[id];
        delete window.PoightOfflineArt[id];
        if (!value?.art?.idle || !value?.art?.dash) throw new Error("离线角色元数据缺失：" + id);
        byID.get(id).moveAnchors = value.moveAnchors;
        return art[id] = value.art;
      }
      const image = await loadImage(refs[id].png);
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(image, 0, 0);
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      const bytes = new Uint8Array(pixels.length / 4 * 3);
      for (let i = 0, j = 0; i < pixels.length; i += 4) {
        bytes[j++] = pixels[i]; bytes[j++] = pixels[i + 1]; bytes[j++] = pixels[i + 2];
      }
      const size = new DataView(bytes.buffer).getUint32(0);
      if (size < 2 || size > bytes.length - 4) throw new Error("角色元数据长度错误：" + id);
      const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(4, 4 + size)));
      if (["idle", "walk", "shoot", "melee", "hurt", "dash"].some(k => !value.art?.[k]?.src))
        throw new Error("角色元数据动作缺失：" + id);
      byID.get(id).moveAnchors = value.moveAnchors;
      art[id] = value.art;
      return value.art;
    })().catch(error => { pending.delete(id); throw error; }));
    return pending.get(id);
  };
};

/* Match-scoped artwork dependencies. No gameplay or drawing changes. */
window.PoightMatchAssets = function (animations, generated, moves) {
  const hero = {
    thunderbolt: ["hero-spark0", "hero-spark1", "hero-orb"],
    quickattack: ["core-impact--1"],
    irontail: [],
    thunder: ["core-impact--1", "hero-orb", "hero-spark0", "hero-spark1"],
    flamethrower: ["hero-flame-rim", "hero-flame0", "hero-flame1"],
    fireblast: ["hero-flame-rim", "hero-flame0", "hero-flame1"],
    dragonclaw: ["hero-claw-strike"],
    airslash: ["hero-wind"],
  };
  const core = {
    watergun: ["core-water", "core-splash", "core-drop"],
    icebeam: ["core-ice", "core-shard"],
    earthquake: ["core-dust"],
  };
  const va2Extra = {
    signalbeam: ["green"], dragonbreath: ["dragon-flare"], gigadrain: ["heal"],
    icywind: ["spikes"], freezedry: ["spikes"], triattack: ["flame", "electric", "ice"],
    poisonsting: ["poison"],
  };
  const vb2 = {
    aquajet: ["drop", "splash"], flamecharge: ["flame"], tackle: [], machpunch: ["fist"],
    bodyslam: [], doubleedge: [], waterfall: ["splash"], flamewheel: ["flame"],
    spark: [], wildcharge: [], rollout: ["rock", "dust"], zenheadbutt: [],
    shadowsneak: [], phantomforce: [], bravebird: [], closecombat: ["fist"],
    rapidspin: [], aquatail: ["splash"], bonerush: ["bone"],
  };
  const vc = {
    surf: [], dazzlinggleam: [], boomburst: [], explosion: ["vc-blast"],
    waterspout: ["core-water", "core-splash"], heatwave: ["vc-flame"],
    discharge: ["vc-spark"], bulldoze: ["core-dust"],
    blizzard: ["core-ice", "core-shard"], rockslide: ["vc-rock"], hex: [], psychic: [],
    inferno: ["vc-flame"], iciclecrash: ["vc-spike"], earthpower: ["vc-meteor"],
    poisongas: ["vc-cloud"], dracometeor: ["vc-meteor"],
    synthesis: ["vc-shine", "vc-star"], recover: ["vc-orb", "vc-star"],
    rest: ["vc-z"], aquaring: ["vc-water"], agility: [], focusenergy: ["vc-energy"],
    protect: ["vc-shield"],
  };
  function plan(profile) {
    const ids = new Set([...profile.playerMoves, ...profile.enemyMoves]);
    const raster = new Set(), effects = new Set(["core-impact--1"]);
    for (const side of ["player", "enemy"]) {
      for (const id of profile[side + "Moves"]) {
        // Native opt-in renderers fully replace their legacy large rasters.
        // Hero replacements are species-specific; ?anim=old retains every fallback.
        const replaced = animations.hero.uses(id, { id: profile[side] }) ||
          animations.melee.has(id) || (animations.enabled && (core[id] ||
            window.PoightVA2Moves[id] || window.PoightVA1Shots[id] || vb2[id] || vc[id]));
        if (!replaced) raster.add(id);
      }
    }
    for (const id of ids) {
      effects.add("core-impact-" + moves[id].type);
      for (const key of core[id] || []) effects.add(key);
      for (const key of hero[id] || []) effects.add(key);
      const va1 = window.PoightVA1Shots[id];
      if (va1) {
        effects.add("va1-" + id);
        if (["water", "steam"].includes(va1.debris)) effects.add("core-splash");
        if (va1.debris === "water") effects.add("core-drop");
        if (va1.debris === "steam") effects.add("va1-steam");
      }
      for (const key of vb2[id] || []) effects.add("vb2-" + key);
      for (const key of vc[id] || []) effects.add(key);
      const va2 = window.PoightVA2Moves[id];
      if (va2) {
        for (const key of [va2.symbol, ...(va2Extra[id] || [])]) effects.add("va2-" + key);
        if (["bubble", "hydropump"].includes(id)) effects.add("core-splash");
      }
      const melee = window.PoightMeleeVB1.moves[id];
      if (melee) {
        const { shape, color, accent, drain } = melee;
        const add = (s, c = color) => effects.add(`vb1-${s}-${c}`);
        if (["combo", "scratch"].includes(shape)) add("scratch");
        else if (shape === "claw") add("claw");
        else if (shape === "palms") { add("cross", "gold"); add("palm", "gold"); }
        else if (["tip", "star"].includes(shape)) add("star", "gold");
        else add(shape);
        if (shape === "combo") add("star", "gold");
        if (accent === "ice") effects.add("core-shard");
        else if (accent === "poison") add("orb");
        else if (accent === "blueorb") add("blueorb", "blue");
        else if (accent === "wall") add("shard", "green");
        else if (accent === "trace") add("fist", "ghost");
        else if (accent) add(accent);
        if (drain) add("orb", "green");
        if (id === "drainingkiss") add("heart", "pink");
      }
    }
    return { ids: [...ids], raster: [...raster], effects: [...effects] };
  }
  return { plan, async load(profile, loader) {
    const required = plan(profile);
    await Promise.all([
      generated.load(loader, required.raster),
      animations.load(required.ids, required.effects),
    ]);
    return required;
  } };
};
