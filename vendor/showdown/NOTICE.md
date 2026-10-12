# Pokémon Showdown 来源与版权说明

本目录来自 **smogon/pokemon-showdown-client**，固定提交：
`cc6f5c24adaaf0a5eb89effbb580516bbf3e7286`。

- 上游仓库：https://github.com/smogon/pokemon-showdown-client
- 下载地址为该提交的 `raw.githubusercontent.com`，不是浮动 master。
- `来源.json` 列出 156 个文件的 URL、SHA256、字节数：151 张 fx 图片、两份动画源码、两份 Dex 类型/工具参考及 LICENSE。
- `tree.json` 为下载时 GitHub 仓库树，用于核对该提交 `fx/` 全部图片；不下载天气视频、不下载外部 sprites 服务。
- `src/battle-animations-moves.ts`、`src/battle-animations.ts` 与全部下载文件保持上游字节；`特效元数据.json` 是转换器提取的派生产物。

## 许可不是一概而论

上游根 LICENSE 是 **GNU Affero General Public License v3.0**，本目录 `LICENSE` 保存原文。
上游源码自身同时声明：客户端整体 AGPLv3，独立 battle 引擎 MIT；
`battle-animations.ts`、`battle-dex.ts`、`battle-dex-data.ts` 标注 `@license MIT`，
`battle-animations-moves.ts` 标注 `@license CC0-1.0`。原作者声明完整保留在源文件头部。
主要署名：Guangcong Luo，以及 Pokémon Showdown 贡献者；图像作者注释保留在 `BattleEffects`。

V1p 新增引擎、页面及转换工具以 **AGPL-3.0-or-later** 提供；不把 AGPL 声称为对任天堂/宝可梦图像和商标的授权。fx 中也有第三方图像或官方图像，具体权利应按上游说明另行核查。

## 移植范围

V1p 抽取动画表执行，记录 showEffect/backgroundEffect/actor.anim 的时间线；
不编译或运行完整 Showdown 客户端，不引入 jQuery、声音、对战协议、tooltip、DOM 场景。
Dex 文件仅作 SpriteData 等类型及工具定义参考；实际运行时依赖为零。
坐标、局部背景、时间压缩、物理弹体接口与具体改动见 `../../坐标映射.md`。

唯一上游纠错在转换器内显式实施：fastattack 的第二段 `y: defender.x` 改成 `y: defender.y`；不修改 vendored 文件。
