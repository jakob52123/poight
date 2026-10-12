# VB1 · 21 招近身接入

## 范围

仅 `招式动画近身VB1.js:PoightMeleeVB1.moves` 列出的 21 招启用。`?anim=old` 完整绕过本批新表现。不将这 21 招加入三样板的 projectile/nova 白名单，避免误走嘴炮或地震路径。

## 安全边界与合并点

- 独立 `PoightMeleeVB1` 类，实例属于 `PoightMoveAnimations.melee`；reset/step/draw/impact 的接入是增量的，核心引擎原文件不改。
- `对战.js:spriteDraw` 只在 Canvas save/restore 内 translate。取 Showdown 本招 attacker 动作；无 attacker 事件时用已转换的 `contactattack`。舞台纵深折算为实时攻击朝向，叠加点头/弹跳后再次限幅至半身高；impact 后 120ms 归零。实例无 onImpact 判伤回调，采样绝不修改身体坐标。
- 接触时刻仍由原生图近身或 limb contactDelay/contactWindow 决定；rangeBodies、朝向、墙体、空中、免疫、闪避、取消、体力和 CD 均保留。成功 damage 同一调用栈写入原通用爆点和本批符号。不命中没有符号或吸取回流。
- `生图招式.js` 与 `招式第3批.js` 仅对本批白名单跳过 M4 旧充能/附体图；原 state 和推进/取消门禁原样运行。R3 吸取的旧 return state 仍保留其生命周期，但绘制由 VB1 绿色回流接管；gigadrain 不变。
- 标志符号紧裁 alpha 后，最长实际轮廓约目标高度的 .98；爆点在本批加 1.1 绘制补偿，避免透明边使 .8H 下限落空。它不改变通用爆点的伤害缩放记录或其他招式。
- 吸取/吸取拳/吸取之吻：仅成功命中后，六个绿色原版 orb 沿弧线飞回施放者。实际主体取 max(15,.32H)，给像素量化留安全余量，不用透明光晕凑尺寸。短路径弧高受距离限制；吸取之吻另带粉红心，不替代绿球。
- 起死回生在施放者周围先出现六球能量环；命中处拳与能量球呼应。舌舔保留原版 Lick strip 纹理，加圆舌尖和粉色中缝，避免只像矩形色块；啄用原版尖命中星加细长尖锋，没有冒称取得独立鸟喙原图。

## 原版素材与色板

`VB1原版/来源.json` 保存 ref-moves 还原贴图副本 SHA。原始副本不重着色；`VB1素材.py` 在构建内存中裁切帧、收紧 alpha、重映射饱和色阶，原版轮廓作为符号主体。Lick/Peck 的即时化修饰在运行时单独列明。

拳=hands_and_feet 第 0 帧，掌=第 3 帧；鞭=slam_hit 第 1 帧；抓=scratch 第 3 帧重复并列；爪=claw_slash 末帧交错；双翼=gust 双旋风；叶刃=leaf+cross_impact；拳属性附加 small_ember/lightning/ice_crystals；吸取=orbs；吻=magenta_heart；起死回生=gray_orb 的 BLUE_ORB 色板。

吸取拳、毒击、吸取之吻是 ref-moves 已标注的替代/改编，不冒充绿宝石有同名第 3 代动画。为满足双场地亮度门槛，草用亮黄绿、拳/普通命中用亮金黄、钢用青银、舌/吻用深洋红、幽灵拳用黑紫轮廓。可读性优先，但没有声称完全照搬原色板或大集结 3D 效果。

构建 `招式动画/打包.py` 增量引入 VB1 素材打包，runtime 将本批类置于接入类之前；无 `构建完整版.py` 拼接列表改动。便携清单包含哈希派生图、原始副本、对应源码、来源记录和既有 NOTICE/许可证。

