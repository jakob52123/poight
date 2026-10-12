"use strict";
// Instantiated by ?test=1 or ?demo=1. Uses the live engine, never a second combat model.
window.PoightBalanceTest = class {
  constructor(api) {
    this.api = api;
    this.playerTier = null;
    this.playerBrain = null;
    this.tracking = false;
    this.ledger = [];
  }
  reset() {
    this.playerTier = null;
    this.playerBrain = null;
    this.tracking = false;
    this.ledger = [];
  }
  control(tier) {
    if (tier !== null && !this.api.tiers.some((t) => t.id === tier))
      throw new Error("unknown player AI tier");
    this.playerTier = tier;
    this.playerBrain = tier === null ? null : this.api.newBrain();
    return this.state();
  }
  state() {
    return {
      playerTier: this.playerTier,
      playerDecisions: this.playerBrain?.decisions || 0,
      hpMultiplier: this.api.multiplier,
    };
  }
  record(source, target, move, kind, amount, multiplier = null) {
    if (!this.tracking || amount <= 0) return;
    const side = (p) => (p.isPlayer ? "a" : "b");
    const key = [side(source), side(target), move, kind, multiplier].join(":");
    let entry = this.ledger.find((e) => e.key === key);
    if (!entry) {
      entry = {
        key,
        source: side(source),
        target: side(target),
        move,
        kind,
        multiplier,
        amount: 0,
        hits: 0,
        first: this.api.elapsed(),
        last: 0,
      };
      this.ledger.push(entry);
    }
    entry.amount += amount;
    entry.hits++;
    entry.last = this.api.elapsed();
  }
  run(options = {}) {
    const {
      seed = 1,
      tier = "poke",
      playerTier = tier,
      maxSeconds = 600,
      hpMultiplier = this.api.multiplier,
    } = options;
    if (
      !Number.isInteger(seed) ||
      seed < 0 ||
      seed > 0xffffffff ||
      !Number.isFinite(maxSeconds) ||
      maxSeconds <= 0 ||
      maxSeconds > 3600 ||
      !Number.isFinite(hpMultiplier) ||
      hpMultiplier <= 0 ||
      hpMultiplier > 100 ||
      !this.api.tiers.some((t) => t.id === tier) ||
      !this.api.tiers.some((t) => t.id === playerTier)
    )
      throw new Error("invalid simulation options");
    this.api.reset();
    this.control(playerTier);
    this.api.prepare(seed, tier, hpMultiplier);
    this.tracking = true;
    // Integer tick count: exactly the normal engine's 120 Hz, no coarse-step tunnelling.
    const ticks = Math.ceil(maxSeconds * 120);
    let tick = 0;
    for (; tick < ticks && this.api.playing(); tick++) this.api.update(1 / 120);
    const [a, b] = this.api.actors();
    const result = {
      a: a.id,
      b: b.id,
      seed,
      tier,
      playerTier,
      hpMultiplier,
      map: this.api.map(),
      ticks: tick,
      seconds: tick / 120,
      combatSeconds: this.api.elapsed(),
      frozenSeconds: this.api.matchSeconds() - this.api.elapsed(),
      winner: a.hp <= 0 && b.hp <= 0 ? "draw" : a.hp <= 0 ? "b" : b.hp <= 0 ? "a" : "timeout",
      hp: { a: a.hp, b: b.hp },
      maxHP: { a: a.maxHP, b: b.maxHP },
      damageDealt: { a: a.damageDealt, b: b.damageDealt },
      damageTaken: { a: a.damageTaken, b: b.damageTaken },
      composition: this.ledger.map(({ key, ...entry }) => ({ ...entry })),
    };
    this.tracking = false;
    return result;
  }
};
