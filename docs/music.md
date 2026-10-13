# 音乐获取与署名

在线版的「每局随机 · 9 首」= 8 首外部曲目 + 项目原创 BGM3（`战斗音乐.js` 中的浏览器合成谱面，无需下载）。外部曲目只采用 CC0 / CC-BY 4.0；完整曲名、作者、指定署名、来源与许可链接见 [CREDITS](../CREDITS.md)、[NOTICE](../NOTICE.md)。Pokémon 官方音乐不在此列表内。

源码与原创美术已接近 25 MB 预算，加入外部 MP3 会超限，因此 MP3 / OGG / WAV 均不随本仓库分发。

## 本地获取（由你自行执行；本次导出未联网下载）

1. 查看 `素材/音乐/源/来源.tsv`，从作者页面或该表的下载直链获取 01、02、03、04、05、06、09、15。保留原署名与许可。
2. 按下表将原始音频放入 `素材/音乐/源/`；01 使用 ZIP 内 intro 与 loop 两份，15 使用 ZIP 内的 fated encounter。

|编号|本地源文件名|
|---|---|
|01|`01. Battle Theme I (intro).ogg` 和 `01. Battle Theme I (loop).ogg`|
|02|`02-pmiller-ChiptuneBattle.ogg`|
|03|`03-request-RinsTheme.ogg`|
|04|`04-Skiff-Underclocked.mp3`|
|05|`05-Skiff-Arpanauts.mp3`|
|06|`06-Skiff-DigitalNative.mp3`|
|09|`09-Pepsidog-JapaneseFight.wav`|
|15|`15-ppeak-FatedEncounter.mp3`|

3. 安装 FFmpeg（含 libmp3lame）与 Python NumPy 后，在仓库根目录执行：

```sh
python3 -m pip install numpy
mkdir -p assets
python3 工具-外部BGM包装.py
```

脚本按已提交的截段、40 ms 循环接缝、响度归一化配方生成 MP3 与曲目清单。当前清单的 SHA256、字节数和循环点位于 `素材/音乐/外部BGM.json`；不同 FFmpeg 版本的编码字节可能不同，不能未经核验宣称逐字节复现。源码快照的其他缺件仍见 README，这一步不意味着整个游戏已可构建。

下载源音频与 `assets/` 下生成产物已加入 `.gitignore`，不要提交。
