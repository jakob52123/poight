"use strict";
(() => {
  const TAU = Math.PI * 2;
  const tracks = {
    A: {
      name: "赤焰交锋", mood: "热血 · 正面对决", bpm: 168, root: 62,
      mode: "D Dorian", scale: [0, 2, 3, 5, 7, 9, 10], duty: 0.25,
      chords: [0, 3, 1, 4, 5, 2, 3, 0],
      motifs: [
        [0, 4, 1, 6, 3, 5], [2, 6, 4, 1, 5, 3],
        [1, 5, 2, 7, 4, 6], [4, 1, 6, 2, 5, 0],
        [5, 2, 7, 3, 6, 4], [2, 5, 1, 4, 0, 3],
        [3, 7, 4, 1, 6, 2], [0, 5, 3, 6, 1, 4],
      ],
      rhythm: [0.5, 0.25, 0.75, 0.5, 0.75, 0.25],
    },
    B: {
      name: "暗棱警报", mood: "紧张 · 压迫追逐", bpm: 174, root: 59,
      mode: "B Phrygian", scale: [0, 1, 3, 5, 7, 8, 10], duty: 0.5,
      chords: [0, 1, 5, 3, 1, 4, 2, 0],
      motifs: [
        [7, 1, 5, 2, 6, 0], [1, 7, 3, 6, 2, 5],
        [5, 0, 4, 1, 6, 2], [3, 6, 0, 5, 1, 4],
        [1, 5, 0, 6, 2, 7], [4, 0, 6, 1, 5, 2],
        [2, 7, 1, 4, 0, 5], [7, 2, 6, 1, 5, 0],
      ],
      rhythm: [0.25, 0.75, 0.5, 0.25, 0.75, 0.5],
    },
    C: {
      name: "跃步电光", mood: "轻快 · 跳跃切磋", bpm: 162, root: 65,
      mode: "F Lydian", scale: [0, 2, 4, 6, 7, 9, 11], duty: 0.5,
      chords: [0, 2, 1, 5, 3, 0, 4, 0],
      motifs: [
        [0, 3, 6, 2, 5, 1], [2, 5, 1, 4, 7, 3],
        [1, 4, 0, 6, 2, 5], [5, 1, 4, 7, 3, 6],
        [3, 0, 5, 2, 6, 1], [0, 6, 3, 7, 2, 4],
        [4, 1, 7, 3, 6, 2], [0, 4, 7, 2, 6, 3],
      ],
      rhythm: [0.75, 0.25, 0.5, 0.75, 0.25, 0.5],
    },
  };
  function degree(track, n) {
    return track.root + track.scale[((n % 7) + 7) % 7] + 12 * Math.floor(n / 7);
  }
  function score(id) {
    const track = tracks[id];
    if (!track) throw new Error("Unknown music track");
    const beat = 60 / track.bpm, bar = beat * 3, introBars = 2, loopBars = 48;
    const intro = [], loop = [];
    function add(events, offset, voice, note, length, gain) {
      events.push({ time: offset * beat, voice, note, duration: length * beat, gain });
    }
    function makeBar(events, b, motif, chord, section = 0, introOnly = false) {
      const base = b * 3;
      let at = 0;
      motif.forEach((n, i) => {
        const length = track.rhythm[i];
        if (!introOnly || i % 2 === 0) {
          add(events, base + at, "lead", degree(track, n + 7), length, 0.105);
        }
        at += length;
      });
      for (let i = 0; i < 6; i++) {
        add(events, base + i * 0.5, "bass", degree(track, chord - 14 + (i === 3 ? 4 : 0)),
          0.5, 0.105);
        if (!introOnly) {
          const arp = [0, 4, 2, 4, 0, 2][(i + section) % 6];
          add(events, base + i * 0.5, "arp", degree(track, chord + arp), 0.25, 0.028);
        }
        add(events, base + i * 0.5, "hat", 0, 0.12, 0.025);
      }
      add(events, base, "kick", 0, 0.32, 0.115);
      add(events, base + 1.5, "snare", 0, 0.22, 0.060);
      if (section % 2) add(events, base + 2.5, "kick", 0, 0.25, 0.070);
    }
    for (let b = 0; b < introBars; b++) makeBar(intro, b, track.motifs[b], 0, 0, true);
    for (let b = 0; b < loopBars; b++) {
      const section = Math.floor(b / 8), index = b % 8;
      let motif = [...track.motifs[index]];
      if (section === 1) motif = motif.map((n, i) => n + (i % 2 ? 0 : 2));
      if (section === 2) motif = motif.map((n) => n + 7);
      if (section === 3) motif = motif.map((n) => 7 - n);
      if (section === 4) motif = motif.map((n, i) => n + (i === 4 ? 1 : 0));
      if (b === loopBars - 1) {
        makeBar(loop, b, track.motifs[0], track.chords[0], 0);
      } else makeBar(loop, b, motif, track.chords[index], section);
    }
    const sort = (events) => events.sort((a, b) => a.time - b.time);
    return { id, ...track, beat, bar, introBars, loopBars,
      introDuration: introBars * bar, loopDuration: loopBars * bar,
      intro: sort(intro), loop: sort(loop) };
  }
  const caches = new WeakMap();
  function resources(ctx) {
    if (caches.has(ctx)) return caches.get(ctx);
    const waves = {};
    for (const duty of [0.125, 0.25, 0.5]) {
      const real = new Float32Array(33), imag = new Float32Array(33);
      for (let n = 1; n < real.length; n++) {
        real[n] = 2 * Math.sin(TAU * n * duty) / (Math.PI * n);
        imag[n] = 2 * (1 - Math.cos(TAU * n * duty)) / (Math.PI * n);
      }
      waves[duty] = ctx.createPeriodicWave(real, imag);
    }
    const noise = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * 0.25), ctx.sampleRate);
    const data = noise.getChannelData(0);
    let seed = 0x504f4947;
    for (let i = 0; i < data.length; i++) {
      seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5;
      data[i] = (seed >>> 0) / 2147483648 - 1;
    }
    const value = { waves, noise };
    caches.set(ctx, value);
    return value;
  }
  const softMix = { B: 0.9, C: 1.3 };
  function lowpass(ctx, frequency) {
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass"; filter.frequency.value = frequency; filter.Q.value = 0.7;
    return filter;
  }
  function outputBus(ctx, destination, soft) {
    if (!soft) return destination;
    const filter = lowpass(ctx, 6000);
    filter.connect(destination);
    return filter;
  }
  function voice(ctx, destination, event, time, duty, active, soft = false) {
    const r = resources(ctx), g = ctx.createGain(), nodes = [g];
    g.gain.value = 0;
    let source;
    const noise = event.voice === "hat" || event.voice === "snare";
    if (noise) {
      source = ctx.createBufferSource();
      source.buffer = r.noise;
      const filter = ctx.createBiquadFilter();
      filter.type = "highpass";
      filter.frequency.value = event.voice === "hat" ? 6500 : 1500;
      source.connect(filter); nodes.push(filter);
      if (soft && event.voice === "snare") {
        const rolloff = lowpass(ctx, 2500);
        filter.connect(rolloff); rolloff.connect(g); nodes.push(rolloff);
      } else filter.connect(g);
    } else {
      source = ctx.createOscillator();
      if (event.voice === "lead" || event.voice === "arp") {
        source.setPeriodicWave(r.waves[event.voice === "arp" ? 0.5 : duty]);
      } else source.type = event.voice === "bass" ? "triangle" : "sine";
      if (event.voice === "kick") {
        source.frequency.setValueAtTime(150, time);
        source.frequency.exponentialRampToValueAtTime(42, time + event.duration);
      } else {
        // B/C exceed C6 in the written score: transpose the whole lead, keep its intervals.
        const note = event.note - (soft && event.voice === "lead" ? 12 : 0);
        source.frequency.value = 440 * 2 ** ((note - 69) / 12);
      }
      if (soft && (event.voice === "lead" || event.voice === "arp")) {
        const filter = lowpass(ctx, 3200);
        source.connect(filter); filter.connect(g); nodes.push(filter);
      } else source.connect(g);
    }
    const amplitude = event.gain * (soft && event.voice === "lead" ? 10 ** (-3 / 20) :
      soft && event.voice === "hat" ? 10 ** (-6 / 20) : 1);
    const end = time + Math.max(0.015, event.duration);
    g.gain.setValueAtTime(0, time);
    g.gain.linearRampToValueAtTime(amplitude, time + (soft ? 0.005 : 0.004));
    if (noise || event.voice === "kick") {
      g.gain.exponentialRampToValueAtTime(0.00001, end - 0.003);
    } else g.gain.setValueAtTime(amplitude, end - 0.009);
    g.gain.linearRampToValueAtTime(0, end);
    g.connect(destination);
    const handle = { source, nodes, time, end };
    if (active) active.add(handle);
    source.onended = () => {
      source.disconnect(); nodes.forEach((n) => n.disconnect()); active?.delete(handle);
    };
    source.start(time); source.stop(end);
    return handle;
  }
  function offline(seconds, volume, soft) {
    const ctx = new OfflineAudioContext(2, Math.ceil(seconds * 44100), 44100);
    const master = ctx.createGain();
    master.gain.value = volume * 0.65;
    master.connect(outputBus(ctx, ctx.destination, soft));
    master.gain.setValueAtTime(volume * 0.65, seconds - 0.3);
    master.gain.linearRampToValueAtTime(0, seconds);
    return { ctx, master };
  }
  async function render(id, seconds = 60, volume = 0.4) {
    const { ctx, master } = offline(seconds, volume, !!softMix[id]), start = 0.05;
    const l = layer(ctx, master, id, false, start);
    l.pump(seconds);
    return { buffer: await ctx.startRendering(),
      seam: start + l.s.introDuration + l.s.loopDuration, score: l.s };
  }
  const DYNAMIC_BAR = 180 / 162, CROSSFADE = 0.6;
  // Gain-only normalization of BGM3, measured at 100% slider (C -20.1 / B -23.8 LUFS).
  const originalTrim = { C: 10 ** (4.1 / 20), B: 10 ** (7.8 / 20) };
  function transportScore(id, dynamic) {
    const s = score(id);
    if (!dynamic) return s;
    const factor = s.bpm / 162;
    return { ...s, bpm: 162, beat: 60 / 162, bar: DYNAMIC_BAR,
      introDuration: s.introDuration * factor, loopDuration: s.loopDuration * factor,
      intro: s.intro.map((e) => ({ ...e, time: e.time * factor, duration: e.duration * factor })),
      loop: s.loop.map((e) => ({ ...e, time: e.time * factor, duration: e.duration * factor })) };
  }
  function layer(ctx, master, id, dynamic, start, active, intro = true, barIndex = 0, normalize = false) {
    const s = transportScore(id, dynamic), gain = ctx.createGain();
    const melody = ctx.createGain(), rhythm = ctx.createGain();
    const compensation = ctx.createGain();
    compensation.gain.value = (softMix[id] || 1) * (normalize ? originalTrim[id] || 1 : 1);
    gain.connect(compensation); compensation.connect(master);
    melody.connect(gain); rhythm.connect(gain);
    const value = { s, gain, melody, rhythm, index: 0, intro, offset: start, end: Infinity };
    value.disconnect = () => {
      melody.disconnect(); rhythm.disconnect(); gain.disconnect(); compensation.disconnect();
    };
    if (!intro) {
      const position = ((barIndex % s.loopBars) + s.loopBars) % s.loopBars * s.bar;
      value.index = s.loop.findIndex((e) => e.time >= position - 1e-7);
      value.offset -= position;
    }
    value.pump = (until) => {
      for (;;) {
        const list = value.intro ? s.intro : s.loop, e = list[value.index];
        const time = value.offset + e.time;
        if (time > until || time >= value.end) break;
        if (time >= ctx.currentTime) voice(ctx,
          e.voice === "lead" || e.voice === "arp" ? melody : rhythm,
          e, time, s.duty, active, !!softMix[id]);
        value.index++;
        if (value.index === list.length) {
          value.offset += value.intro ? s.introDuration : s.loopDuration;
          value.intro = false; value.index = 0;
        }
      }
    };
    return value;
  }
  function fadeLayers(old, next, boundary, duration = CROSSFADE) {
    old.gain.gain.cancelScheduledValues(boundary);
    old.gain.gain.setValueAtTime(old.mixGain ?? 1, boundary);
    old.gain.gain.linearRampToValueAtTime(0, boundary + duration);
    old.end = boundary + duration;
    next.gain.gain.setValueAtTime(0, boundary);
    next.gain.gain.linearRampToValueAtTime(1, boundary + duration);
    next.mixGain = 1;
  }
  function redMix(l, mode, boundary, incoming = false) {
    for (const [node, key, value] of [[l.gain, "mixGain", mode === "r1" ? 0 : 1],
      [l.melody, "mixMelody", mode === "r3" ? 0 : 1]]) {
      node.gain.cancelScheduledValues(boundary);
      node.gain.setValueAtTime(incoming && key === "mixGain" ? 0 : l[key] ?? 1, boundary);
      node.gain.linearRampToValueAtTime(value, boundary + (mode === "r1" ? 0.8 : CROSSFADE));
      l[key] = value;
    }
  }
  const alarmLimit = (mode) => mode === "r2" ? 4 : mode === "r3" ? 0 : Infinity;
  const alarmStep = (mode, index) => index % 2 ? (mode === "r1" ? 0.89 :
    mode === "r2" ? 0.69 : 0.53) : 0.31;
  function alarmVoice(ctx, master, time, index, active, mode = null) {
    const handle = voice(ctx, master, { voice: "lead", note: index % 2 ? 75 : 81,
      duration: index % 2 ? 0.14 : 0.11, gain: 0.105 * (mode === "r1" ? 0.5 : 0.6) },
      time, 0.25, active);
    handle.alarm = true;
    return handle;
  }
  async function renderDynamic(seconds = 45, volume = 1, redMode = null) {
    const { ctx, master } = offline(seconds, volume, true), alarm = ctx.createGain();
    alarm.connect(master);
    const start = 0.05;
    const stage = redMode ? 10 : 15;
    const yellow = start + Math.ceil((stage - start) / DYNAMIC_BAR) * DYNAMIC_BAR;
    const red = start + Math.ceil((stage * 2 - start) / DYNAMIC_BAR) * DYNAMIC_BAR;
    const c = layer(ctx, master, "C", true, start);
    const b = layer(ctx, master, "B", true, yellow, null, false,
      Math.round((yellow - start) / DYNAMIC_BAR) - 2);
    fadeLayers(c, b, yellow);
    if (redMode) redMix(b, redMode, red);
    c.pump(seconds); b.pump(seconds);
    const events = [];
    for (let t = red, i = 0; t < seconds && i < alarmLimit(redMode); i++) {
      alarmVoice(ctx, alarm, t, i, null, redMode); events.push(t);
      t += alarmStep(redMode, i);
    }
    return { buffer: await ctx.startRendering(), yellow, red, crossfade: CROSSFADE,
      redMode, alarmEvents: events };
  }
  const LAST_TRACK = "poight.music.last.v1";
  function pickTrack(pool, random = Math.random, storage) {
    let previous;
    try { storage = storage || localStorage; previous = storage.getItem(LAST_TRACK); } catch (_) {}
    const eligible = pool.filter((id) => id !== previous);
    const selected = eligible[Math.min(eligible.length - 1, Math.floor(random() * eligible.length))];
    try { storage.setItem(LAST_TRACK, selected); } catch (_) {}
    return selected;
  }
  // Same-origin streaming only: no fetch/XHR, whole-track buffers, EQ or pitch effects.
  class StreamMusic {
    constructor(track, onFailure, onReady) {
      this.track = track; this.onFailure = onFailure; this.running = false;
      this.active = 0; this.sources = []; this.gains = []; this.seams = [];
      this.elements = Array.from({ length: track.intro ? 2 : 1 }, (_, index) => {
        const a = document.createElement("audio");
        a.preload = "auto"; a.src = index === 0 && track.intro ? track.intro : track.src;
        a.loop = !track.intro || index === 1;
        a.addEventListener("error", () => onFailure());
        a.addEventListener("canplay", () => onReady?.());
        if (index) a.addEventListener("loadedmetadata", () => { a.currentTime = track.loopStart; }, {once:true});
        a.load(); return a;
      });
    }
    get ready() { return this.elements.every((a) => a.readyState >= 3); }
    connect(ctx, volume) {
      if (this.ctx) return;
      this.ctx = ctx;
      this.elements.forEach((a, i) => {
        const source = ctx.createMediaElementSource(a), gain = ctx.createGain();
        source.connect(gain); gain.connect(ctx.destination);
        gain.gain.value = i === this.active ? volume : 0;
        this.sources.push(source); this.gains.push(gain);
      });
    }
    setVolume(volume) {
      this.volume = volume;
      this.gains.forEach((g, i) => {
        g.gain.cancelScheduledValues(this.ctx.currentTime);
        g.gain.setTargetAtTime(i === this.active ? volume : 0, this.ctx.currentTime, .015);
      });
    }
    async play(ctx, volume) {
      if (this.running || this.starting) return;
      this.connect(ctx, volume); this.setVolume(volume); this.starting = true;
      const a = this.elements[this.active];
      try {
        await a.play(); this.starting = false;
        if (this.cancelled) { a.pause(); return; }
        this.running = true;
        if (this.elements.length > 1) {
          this.timer = setInterval(() => this.pump(), 8);
          this.warmAlternate();
        }
      } catch (error) {
        this.starting = false;
        if (error.name !== "NotAllowedError" && error.name !== "AbortError") this.onFailure();
      }
    }
    async warmAlternate() {
      if (this.warmed || this.warming) return;
      this.warming = true;
      const next = this.elements[1 - this.active];
      try {
        await next.play();
        await new Promise((resolve) => setTimeout(resolve, 250));
        next.pause(); next.currentTime = this.track.loopStart; this.warmed = true;
      } catch (_) {} finally { this.warming = false; }
    }
    async pump() {
      if (!this.running || this.switching || this.warming || this.active === 1) return;
      const oldIndex = this.active, old = this.elements[oldIndex];
      if (old.duration - old.currentTime > .08) return;
      this.switching = true;
      const nextIndex = 1 - oldIndex, next = this.elements[nextIndex];
      if (Math.abs(next.currentTime - this.track.loopStart) > .02) next.currentTime = this.track.loopStart;
      try {
        await next.play();
        if (!this.running) { next.pause(); return; }
        const now = this.ctx.currentTime, duration = .06;
        this.gains[oldIndex].gain.cancelScheduledValues(now);
        this.gains[oldIndex].gain.setValueAtTime(this.volume, now);
        this.gains[oldIndex].gain.linearRampToValueAtTime(0, now + duration);
        this.gains[nextIndex].gain.cancelScheduledValues(now);
        this.gains[nextIndex].gain.setValueAtTime(0, now);
        this.gains[nextIndex].gain.linearRampToValueAtTime(this.volume, now + duration);
        this.active = nextIndex;
        // The authored standalone loop now repeats natively; intro is never restarted.
        clearInterval(this.timer);
        this.seams.push({ time: now, gapMS: Math.max(0, -1000 * (old.duration - old.currentTime)) });
        this.fadeTimer = setTimeout(() => {
          old.pause(); old.currentTime = this.track.loopStart; this.switching = false;
        }, duration * 1000);
      } catch (_) { this.onFailure(); }
    }
    pause() {
      this.cancelled = true; this.running = false;
      clearInterval(this.timer); clearTimeout(this.fadeTimer); this.switching = false;
      this.elements.forEach((a) => a.pause());
    }
    resume(ctx, volume) { this.cancelled = false; return this.play(ctx, volume); }
    dispose() {
      this.pause();
      this.elements.forEach((a) => { a.removeAttribute("src"); a.load(); });
      this.sources.forEach((s) => s.disconnect()); this.gains.forEach((g) => g.disconnect());
    }
  }
  class BattleMusic {
    constructor(getContext, args, catalog = []) {
      this.catalog = catalog; this.pool = [...catalog.map((t) => t.id), "orig"];
      this.bgm = "orig"; this.prepared = false; this.args = args;
      Object.assign(this, { getContext, playing: false, unlocked: false, session: null,
        volume: 0.4, track: "random", enabled: true, redMode: "r3", level: "green", health: 1,
        transitions: 0, redEntry: 0, r2Entry: -1 });
      try {
        const saved = JSON.parse(localStorage.getItem("poight.music.v1"));
        if (saved) {
          this.enabled = saved.enabled === true;
          if (saved.track === "random") this.track = saved.track;
          if (["r1", "r2", "r3"].includes(saved.redMode)) this.redMode = saved.redMode;
          if (Number.isFinite(saved.volume)) this.volume = Math.max(0, Math.min(1, saved.volume));
        }
      } catch (_) {}
      const query = args.get("music");
      if (args.get("demo") === "1") this.enabled = false;
      if (query === "off") this.enabled = false;
      else if (tracks[query] || query === "dynamic" || /^r[123]$/.test(query || "")) {
        this.track = /^r[123]$/.test(query) ? "dynamic" : query; this.enabled = true;
        if (/^r[123]$/.test(query)) this.redMode = query;
      }
      if (catalog.some((t) => t.id === query) || query === "orig") {
        this.forced = query; this.track = "random"; this.enabled = true;
      }
      if (query === "random") { this.track = "random"; this.enabled = true; }
      this.quiet = ["demo", "observe", "test"].some((k) => args.get(k) === "1") &&
        !(query && query !== "off");
      if (this.quiet) this.enabled = false;
      this.mount();
      const unlock = (event) => {
        if (!event.isTrusted || !this.enabled) return;
        this.awake();
      };
      document.addEventListener("pointerdown", unlock, true);
      document.addEventListener("keydown", unlock, true);
    }
    awake() {
      this.unlocked = true;
      try { this.getContext()?.resume().then(() => this.reconcile()).catch(() => {}); }
      catch (_) {}
    }
    mount() {
      const menu = document.querySelector("#battleMenu .buttons") ||
        document.querySelector(".buttons");
      this.button = document.createElement("button");
      this.button.id = "musicToggle";
      this.button.onclick = (event) => {
        event.stopPropagation();
        this.enabled = !this.enabled;
        if (this.enabled) this.awake();
        this.changed();
      };
      const picker = (id, label, values, selected, changed) => {
        const select = document.createElement("select");
        select.id = id; select.setAttribute("aria-label", label);
        for (const [value, text] of values) {
          const option = document.createElement("option");
          option.value = value; option.textContent = text; select.append(option);
        }
        select.value = selected;
        select.onclick = (event) => event.stopPropagation();
        select.onchange = () => { changed(select.value); this.changed(); };
        return select;
      };
      const select = picker("musicTrack", "战斗曲目", [["random", "每局随机 · 9 首"], ["dynamic", "原创 · 随血量 C / B"],
        ...Object.entries(tracks).map(([id, t]) => [id, id + " · " + t.name])], this.track,
      (value) => {
        this.stop(); this.stream?.dispose(); this.stream = null;
        this.track = value; this.forced = null; this.bgm = "orig"; this.prepared = false;
      });
      this.redSelect = picker("musicRedMode", "低血提示",
        [["r1", "报警"], ["r2", "简短"], ["r3", "无"]].map(([id, text]) =>
          [id, "低血提示：" + text]), this.redMode,
        (value) => { this.redMode = value; this.requestTransition(); });
      const label = document.createElement("label");
      label.htmlFor = "musicVolume";
      label.onclick = (event) => event.stopPropagation();
      this.range = document.createElement("input");
      this.range.id = "musicVolume"; this.range.type = "range";
      this.range.min = "0"; this.range.max = "100"; this.range.value = this.volume * 100;
      this.output = document.createElement("span");
      label.append(this.output, this.range);
      this.range.oninput = () => {
        this.volume = Number(this.range.value) / 100;
        this.stream?.setVolume(this.volume);
        if (this.session) this.session.master.gain.setTargetAtTime(
          this.volume * 0.65, this.session.ctx.currentTime, 0.015);
        this.changed();
      };
      // Legacy synthesis strategies are audition/debug controls, not extra production pool entries.
      select.hidden = this.redSelect.hidden = !this.args.has("music");
      menu.append(this.button, select, this.redSelect, label);
      this.updateUI();
    }
    updateUI() {
      this.button.textContent = "音乐：" + (this.enabled ? "开" : "关");
      this.button.setAttribute("aria-pressed", String(this.enabled));
      this.output.textContent = "音乐音量 " + Math.round(this.volume * 100) + "% ";
    }
    changed() {
      this.updateUI();
      try { localStorage.setItem("poight.music.v1", JSON.stringify({
        enabled: this.enabled, volume: this.volume, track: this.track, redMode: this.redMode,
      })); } catch (_) {}
      this.reconcile();
    }
    prepareRound() {
      this.stop(); this.stream?.dispose(); this.stream = null;
      clearTimeout(this.fallbackTimer); this.fallbackTimer = null; this.prepared = true; this.decided = false;
      if (this.track === "random") this.redMode = "r3";
      this.bgm = this.forced || (this.track === "random" ? pickTrack(this.pool) : "orig");
      const selected = this.catalog.find((t) => t.id === this.bgm);
      if (selected && this.enabled && !this.quiet) {
        const stream = new StreamMusic(selected, () => {
          if (this.stream === stream && !this.decided) this.fallback();
        }, () => this.reconcile());
        this.stream = stream;
      }
    }
    fallback() {
      if (this.decided) return;
      this.stream?.dispose(); this.stream = null;
      this.bgm = "orig"; this.decided = true; clearTimeout(this.fallbackTimer);
      try { localStorage.setItem(LAST_TRACK, "orig"); } catch (_) {}
      this.onDecision?.("orig");
      this.reconcile();
    }
    duckAlarm() {
      const s = this.session;
      if (!s) return;
      const t = s.ctx.currentTime, gain = s.alarmDuck.gain;
      gain.cancelAndHoldAtTime(t);
      gain.linearRampToValueAtTime(0.2, t + 0.006);
      gain.setValueAtTime(0.2, t + 0.18);
      gain.linearRampToValueAtTime(1, t + 0.22);
    }
    setHealth(ratio) {
      if (!Number.isFinite(ratio)) return;
      this.health = Math.max(0, Math.min(1, ratio));
      const old = this.level;
      if (ratio <= 0.2) this.level = "red";
      else if (old === "red" && ratio <= 0.23) this.level = "red";
      else if (ratio > (old === "green" ? 0.5 : 0.53)) this.level = "green";
      else this.level = "yellow";
      if (old !== this.level) {
        if (this.level === "red") this.redEntry++;
        this.requestTransition();
      }
    }
    target() {
      return { id: ["dynamic", "random"].includes(this.track) ? (this.level === "green" ? "C" : "B") : this.track,
        alarm: ["dynamic", "random"].includes(this.track) && this.level === "red" && this.redMode !== "r3",
        redMode: ["dynamic", "random"].includes(this.track) && this.level === "red" ? this.redMode : null };
    }
    requestTransition() {
      const s = this.session;
      if (!s || !["dynamic", "random"].includes(this.track) || this.stream) return;
      const target = this.target();
      if (s.pending || (target.id === s.current.s.id &&
          target.alarm === s.alarmOn && target.redMode === s.redMode)) return;
      const { ctx, start, bar } = s;
      const boundary = start + Math.ceil((ctx.currentTime + 0.02 - start) / bar) * bar;
      const next = target.id === s.current.s.id ? null : layer(ctx, s.master,
        target.id, true, boundary, s.active, false,
        Math.round((boundary - start) / bar) - 2, this.track === "random");
      if (next) {
        fadeLayers(s.current, next, boundary, target.redMode === "r1" ? 0.8 : CROSSFADE);
        s.layers.push(next);
      }
      if (!next || target.redMode) redMix(next || s.current, target.redMode, boundary, !!next);
      s.alarm.gain.cancelAndHoldAtTime(ctx.currentTime);
      s.alarm.gain.setValueAtTime(s.alarmOn ? 1 : 0, boundary);
      s.alarm.gain.linearRampToValueAtTime(target.alarm ? 1 : 0, boundary + 0.03);
      if (target.alarm) {
        s.alarmTime = boundary;
        s.alarmIndex = target.redMode === "r2" && this.r2Entry === this.redEntry ? 4 : 0;
        s.alarmEvents = []; s.alarmMode = target.redMode;
      }
      s.pending = { ...target, boundary,
        end: boundary + (target.redMode === "r1" ? 0.8 : CROSSFADE), next };
      this.transitions++;
    }
    setPlaying(value) {
      if (value === this.playing) return;
      this.playing = value;
      if (value && !this.prepared) this.prepareRound();
      if (value && !this.decided && !this.fallbackTimer) {
        this.deadline = performance.now() + 3000;
        this.fallbackTimer = setTimeout(() => this.fallback(), 3000);
      }
      this.reconcile();
    }
    reconcile() {
      if (!this.enabled || !this.playing || this.quiet) { this.stop(); return; }
      if (!this.unlocked) return;
      if (this.stream) {
        if (!this.decided && performance.now() >= this.deadline) { this.fallback(); return; }
        if (!this.stream.ready) return;
        const ctx = this.getContext();
        if (ctx?.state !== "running") return;
        const stream = this.stream;
        stream.resume(ctx, this.volume).then(() => {
          if (this.stream === stream && stream.running && !this.decided) {
            this.decided = true; clearTimeout(this.fallbackTimer); this.onDecision?.(this.bgm);
          }
        });
        return;
      }
      this.bgm = "orig";
      if (!this.decided) {
        this.decided = true; clearTimeout(this.fallbackTimer); this.onDecision?.("orig");
      }
      if (this.session) return;
      try {
        const ctx = this.getContext();
        if (!ctx || ctx.state !== "running") return;
        const master = ctx.createGain(), active = new Set(), alarm = ctx.createGain();
        const alarmDuck = ctx.createGain();
        master.gain.setValueAtTime(0, ctx.currentTime);
        master.gain.linearRampToValueAtTime(this.volume * 0.65, ctx.currentTime + 0.03);
        const bus = outputBus(ctx, ctx.destination, this.track !== "A");
        master.connect(bus); alarm.connect(alarmDuck); alarmDuck.connect(master);
        const target = this.target(), start = ctx.currentTime + 0.05;
        const current = layer(ctx, master, target.id, ["dynamic", "random"].includes(this.track), start, active,
          true, 0, this.track === "random");
        alarm.gain.value = target.alarm ? 1 : 0;
        redMix(current, target.redMode, start);
        const s = { ctx, master, bus, active, alarm, alarmDuck, current, layers: [current], start,
          bar: current.s.bar, alarmOn: target.alarm, alarmTime: start, alarmIndex: 0,
          redMode: target.redMode, alarmMode: target.redMode, alarmEvents: [],
          pending: null, timer: null };
        if (target.redMode === "r2" && this.r2Entry === this.redEntry) s.alarmIndex = 4;
        this.session = s;
        const pump = () => {
          if (this.session !== s) return;
          const now = ctx.currentTime, until = now + 0.16, pending = s.pending;
          s.layers.forEach((l) => l.pump(until));
          if (s.alarmOn || pending?.alarm) {
            const cutoff = pending && !pending.alarm ? pending.boundary : Infinity;
            while (s.alarmTime < Math.min(until, cutoff) &&
                s.alarmIndex < alarmLimit(s.alarmMode)) {
              if (s.alarmTime >= now) {
                alarmVoice(ctx, alarm, s.alarmTime, s.alarmIndex, active, s.alarmMode);
                s.alarmEvents.push(s.alarmTime);
                if (s.alarmMode === "r2") this.r2Entry = this.redEntry;
              }
              s.alarmTime += alarmStep(s.alarmMode, s.alarmIndex++);
            }
          }
          if (pending && now >= pending.end) {
            if (pending.next) s.current = pending.next;
            s.alarmOn = pending.alarm; s.redMode = pending.redMode;
            s.pending = null; this.requestTransition();
          }
          s.layers = s.layers.filter((l) => {
            if (now < l.end + 0.5) return true;
            l.disconnect(); return false;
          });
        };
        pump(); s.timer = setInterval(pump, 25);
      } catch (_) { this.stop(); }
    }
    stop() {
      this.stream?.pause();
      const s = this.session;
      if (!s) return;
      this.session = null; clearInterval(s.timer);
      const t = s.ctx.currentTime, end = t + 0.35;
      s.master.gain.cancelAndHoldAtTime(t);
      s.master.gain.linearRampToValueAtTime(0, end);
      for (const handle of s.active) {
        try { handle.source.stop(Math.min(handle.end, end)); } catch (_) {}
      }
      setTimeout(() => {
        for (const h of s.active) {
          h.source.disconnect(); h.nodes.forEach((n) => n.disconnect());
        }
        s.active.clear(); s.layers.forEach((l) => l.disconnect());
        s.alarm.disconnect(); s.alarmDuck.disconnect(); s.master.disconnect();
        if (s.bus !== s.ctx.destination) s.bus.disconnect();
      }, 400);
    }
    snapshot() {
      const s = this.session, now = s?.ctx.currentTime || 0;
      const pending = s?.pending, switched = pending && now >= pending.boundary;
      return { enabled: this.enabled, volume: this.volume, bgm: this.bgm,
        media: this.stream ? { currentTime: this.stream.elements[this.stream.active].currentTime,
          ready: this.stream.ready, running: this.stream.running, active: this.stream.active,
          gain: this.stream.gains[this.stream.active]?.gain.value ?? 0,
          seams: this.stream.seams, paused: this.stream.elements.every((a) => a.paused) } : null,
        mode: this.track, redMode: this.redMode,
        musicGain: s?.current.gain.gain.value ?? 0,
        melodyGain: s?.current.melody.gain.value ?? 0,
        rhythmGain: s?.current.rhythm.gain.value ?? 0,
        alarmEvents: s?.alarmEvents || [], alarmPairSeconds: this.redMode === "r1" ? 1.2 : 1,
        track: this.stream ? this.bgm : switched ? pending.id : s?.current.s.id || this.target().id,
        alarm: switched ? pending.alarm : s?.alarmOn || false,
        alarmDuck: s?.alarmDuck.gain.value ?? 1,
        alarmAudible: s ? [...s.active].filter((h) => h.alarm && h.time <= now && h.end > now).length : 0,
        health: this.health, level: this.level, transitions: this.transitions,
        bpm: s?.current.s.bpm || 0, barSeconds: s?.bar || 0, audioTime: now,
        pending: pending ? { track: pending.id, alarm: pending.alarm,
          boundary: pending.boundary, end: pending.end } : null,
        unlocked: this.unlocked, playing: this.playing, state: s?.ctx.state || (this.stream?.running ? "running" : "inactive"),
        scheduled: s?.active.size || 0,
        audible: s ? [...s.active].filter((h) => h.time <= now && h.end > now).length : 0 };
    }
  }
  window.PoightMusicRandom = { pickTrack, StreamMusic };
  window.PoightBattleMusic = BattleMusic;
  window.PoightMusicScore = { tracks, score, render, renderDynamic,
    renderOriginal: () => render("C", 60, originalTrim.C) };
})();
