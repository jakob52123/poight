# Poight 招式动画接入 · 第三方声明

V1 的动画引擎移植自 Pokémon Showdown 动画 API 语义，固定来源见 `vendor/showdown/来源.json`，逐项署名和上游许可见 `vendor/showdown/NOTICE.md`。V1p 起点：4634ea4；本次新增/移植的动画程序以 **AGPL-3.0-or-later** 提供，全文 `LICENSE-AGPL-3.0`。运行时不请求远程资源。

- `招式动画引擎.js`、`招式动画/招式动画.json`、`招式动画/特效映射.json`：V1p 的 Showdown Canvas 移植及转换结果。构建仅把 ESM 导出包装成独立闭包，不修改源语义。
- `招式动画接入.js`：Poight 物理驱动的三类适配和通用命中星；Showdown 整段攻击方位移不直接用于战斗。
- `主角招式外观.js`：VH 八招物理驱动视觉适配，AGPL-3.0-or-later。新增原版副本与 SHA 见 `招式动画/原版/VH来源.json`；火苗、电花、电球、落雷、爪痕与风刃由原版轮廓裁切/属性调色，实时电束、五点「大」字和银尾弧为改编。空气斩借用第三代旋风刀的月牙，不冒充第三代同名原版动画。
- `vendor/showdown/fx/`：上游特效，版权及文件许可不统一等同于 AGPL，见上游 NOTICE。
- `招式动画/原版/`：从本地 ref-moves/还原贴图复制的 pret/pokeemerald 原版像素派生；调色板映射见 `招式动画/色板映射.tsv`。保留索引 0 透明，通用 impact 按属性重新着色。水枪小水珠/水花、冰晶、尘土均保留原版轮廓与颜色。地震原作只摇屏，本适配的局部裂纹/尘土波为实时玩法改编，不声称原版已有该波。
- 原作图像、宝可梦角色/商标属于相应权利人。代码许可不授予原版美术商业或再分发许可；个人非商业研究，无 ROM、无模拟器。

候选发布清单同时包含本声明、AGPL 全文、上游 NOTICE/LICENSE 和动画可编辑源码。正式网络发布前必须提供整个组合程序的完整对应源码（AGPL 第 13 条），不能只提供这些动画文件。本仓库为公开源码快照，完整素材重建与可复现构建链仍在补齐；具体缺件见 README 与素材清单。

## 战斗音乐（AUD）

以下音乐做了截段、循环接缝处理、-16 LUFS 响度归一化与 MP3 转码；许可不因处理改变。CC0 作者也一并致谢。

|编号|曲名|作者|许可|来源页面|
|---|---|---|---|---|
|01|16-bit - Battle Theme I|HydroGene|CC0|https://opengameart.org/content/16-bit-battle-theme-i|
|02|Chiptune Battle Music|pmiller|CC0|https://opengameart.org/content/chiptune-battle-music|
|03|Rin's Theme (Loopable chiptune, adventure/battle BGM)|request|CC0|https://opengameart.org/content/rins-theme-loopable-chiptune-adventurebattle-bgm|
|04|Underclocked (underunderclocked mix)|Eric Skiff|CC-BY 4.0|https://ericskiff.com/music/|
|05|Arpanauts|Eric Skiff|CC-BY 4.0|https://ericskiff.com/music/|
|06|Digital Native|Eric Skiff|CC-BY 4.0|https://ericskiff.com/music/|
|09|Looping Japanese fight track|Pepsidog|CC0|https://opengameart.org/content/looping-japanese-fight-track|
|15|fated encounter|PPEAK / Preston Peak|CC-BY 4.0|https://opengameart.org/content/free-action-chiptune-music-pack|
|orig|跃步电光 / 暗棱警报（BGM3 C/B/R3）|Poight 项目原创合成谱面|项目代码许可 AGPL-3.0-or-later|本仓库 `战斗音乐.js`|

- Eric Skiff 指定署名：Music: Eric Skiff - Underclocked (underunderclocked mix) / Arpanauts / Digital Native - Resistor Anthems - Available at http://EricSkiff.com/music 。
- PPEAK 指定署名：PPEAK / Preston Peak。
- CC-BY 4.0 许可：https://creativecommons.org/licenses/by/4.0/ 。CC0：https://creativecommons.org/publicdomain/zero/1.0/ 。
- 原署名全文及下载来源见 `素材/音乐/源/来源.tsv`，打包后校验和及循环点见 `素材/音乐/外部BGM.json`。为满足体积预算，音频文件不随本仓库分发；获取方式见 `docs/music.md`。游戏现有「素材作者与说明」鸣谢入口包含同样内容。
- 大型源码 JSON 以 `.json.gz` 无损保留，原始字节 SHA256 与还原脚本见 `tools/source-data.json`、`tools/restore_source_data.py`。vendor 源码保持上游原文，不压缩、不改版权头。
