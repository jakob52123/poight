"use strict";
// Apply exactly once, after generic, hero, generated and R3 runtime overrides.
window.PoightFeelTiming = (moves) => {
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const cooldownFactor = 0.4;
  for (const m of Object.values(moves)) {
    m.windup = m.windup === 0 ? 0 : clamp(m.windup * 0.5, 0.05, 0.35);
    // M6b 导演裁决：仅 B1 咬类至少 100ms 前摇，牙齿张开放在前摇；
    // contactDelay 仍为零，释放 tick 第一口，crunch +120ms 第二口。
    if (m.fangs) m.windup = Math.max(m.windup, 0.10);
    m.recovery *= 0.6;
    if (!["heal", "buff", "splash"].includes(m.kind))
      m.cd = clamp(m.cd * cooldownFactor, 0.45, 3);
    if (m.limb) m.contactDelay = 0;
  }
};
