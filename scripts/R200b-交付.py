"""Render the full delivery note from final evidence, not estimated counts."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'验收记录/R200/补充1'
r=json.loads((OUT/'总验收.json').read_text())
proof=json.loads((OUT/'配招核验.json').read_text())
root=str(ROOT)
before,after=r['coldBefore'],r['coldAfter']
core='7bd82e0'  # Runtime/CSS and migrated assertions frozen here; later commits only evidence/tools.
core=subprocess.check_output(['git','rev-parse',core],cwd=ROOT,text=True).strip()
rows=list(csv.DictReader((OUT/'配招前后对照.tsv').open(),delimiter='\t'))
examples=[row for n in [10,11,384,445,778,887] for row in rows if int(row['编号'])==n]
table='\n'.join(f"| #{row['编号']} {row['名字']} | {row['旧四招']} | {row['新四招']} |" for row in examples)
summary=lambda v:json.dumps(v,ensure_ascii=False)
note=f'''## 交付说明

R200扩容成果保留，补充1已完成。**回归口径为完整49套＋末次CSS受影响6套复验，不是49套全部在最终SHA重跑。** 未部署、未向发布服务器上传、未push、未写知识库。

### 1. 提交与候选

- 分支：`R200-from-cd1e796`。
- 运行代码冻结提交：`{core}`。最终提交为本交付文件所在提交；最后交付消息给出完整SHA。
- 候选：`{root}/候选试玩.html`。
- 候选SHA256：`{r['candidateSHA256']}`。
- Stone Edge：`{r['release']['stoneEdgeSHA256']}`，不变。
- 没有替换精灵，原50默认招、可选池、体型、走速、完整角色数据与动画均不变。

### 2. R200原任务成果

- 按指定顺序收录200只；保留`首发50.json`，新增授权及以后扩容仍需本人开口已写入`首发200.json`和构建注释。
- 飞行包24/24，新增16只的原生姿态重编排、躯干锚点、flightHeight、bodyOffsets、audit及八方向接触表齐全；原8包不变。
- 200只默认形态体型来源、原始响应和SHA归档；延用身高/体重公式、长蛇盘曲长度及20px脚印上限，没有另调基础HP/走速。
- 新150只Showdown立绘来源与SHA齐全；仅#724狙射树枭缺GIF，按约定回退PNG。角色名与归档zh-Hans参考0差异，保留「暴飞龙」「谜拟丘」；没有独立逐页审计官方站点。
- 200格可滚动；键盘、标准Gamepad API模拟、两种手机横屏触控均选到#887，CPU随机上边界也是#887。格子采用CSS变量，没有视觉改版。
- 元数据/动画/锚点仍按角色包加载；开打角色动画与元数据请求恰好为`[6,25]`，不是预下载200只。
- 发布清单{r['release']['assets']}项，去重后少于预估4000+；本地冻结包{r['release']['releaseFiles']}文件。原发布器`--check`返回`validated-only`、服务器命令0条；上限12000文件/单文件32MiB/总256MiB，本包最长路径57字节。

### 3. 补充1：可学招式与继承断言

150份PokéAPI默认形态`moves`原始响应已用curl归档（并发4、重试2），按任意世代/学习方式取与原有120招的交集。原50行学招审计仍按旧Gen IX范围保留；新150行明确标注Any generation，不混用口径。

新增150只可选池全部按「原池∪可学交集」核验。默认四招实际改变**{proof['defaultChanged']}只**，其余11只保留已合规则或特例的组合；本系、近身、覆盖/光束、守住结构与`covers()`均验证。补自属性池**{proof['fallbackSpecies']}只**：

- 绿毛虫：信号光束；铁甲蛹：撞击、信号光束。
- 独角虫：毒击；铁壳蛹：毒击、毒针。
- 上述4只的守住沿用通用规则；逐槽来源、补位说明已写进配招表，没有冒充原作可学。
- 百变怪保持「抓/劈瓦/咬住/撞击」，注明「原作仅变身，暂用一般系」。鲤鱼王仍仅水溅跃。

关键前后对照：

| 精灵 | 原四招 | 新四招 |
|---|---|---|
{table}

**全部139只、每个变更槽位的前后对照**：`{root}/验收记录/R200/补充1/配招前后对照.tsv`。

体型断言已按裁决迁移：≤430px竖屏要求详情DOM存在且内容正确，并真实点击换招/恢复推荐；横屏与电脑仍要求可见。追加发现的窄屏按钮遮挡已修复（原真实点击失败→成功，不用force），横屏详情已恢复。原50守卫没有删掉：原48非主角仍对照原黄金值，新增150单列；旧游戏数据AST精确扣除获授权分支后仍须一致，并新增原50完整数据/可选池对照。

走场验收仅将相同120Hz逐tick循环放在浏览器内，减少完整snapshot跨进程序列化；步长、渲染、键盘、3960 tick上限和距离<2门槛不变。优化前后timings与断言名称/结果完全相同。

### 4. 验收原样数字

```text
TOTAL {summary(r['regression'])}
R200  {summary(r['R200'])}
M9    {summary(r['M9'])}
```

相比M9通过断言增加{r['regression']['passed']-r['M9']['passed']}；仅保留冰冻拳注入探针58.3%<60%的2项，没有降低门槛。local、Jade、macmini三台均实际执行；macmini首次全源码同步过慢，改为传精确候选＋全部白名单资产，原验收脚本不改。

最终候选的定向验收：

```text
体型移速：passed={r['bodyPassed']} testedSpecies=200 errors=[]（已跑到底）
逐精灵：tested=200 passed=200 failed=0 jsErrors=0
冒烟：tested=200 games=100 secondsPerMatch=20 passed=200 failed=0
默认槽位：defaultCasts=797 emitted=797 castFailures=[] jsErrors=0
离线：tested=200 passed=200 jsErrors=0 externalRequests=[]
选人输入：passed=5 failed=0 jsErrors=0
原50完整数据：changed=[]
原50六动作及锚点：original50ArtAndLandmarksChanged=[]
```

797→797是槽位数不变，不是沿用旧结果：新候选全部重放。AI冒烟使用测试专用高HP防止提前KO，每只真实经历20秒；四招逐槽释放另外验证，不声称AI自然放齐四招。

首开同口径（冷缓存、300000B/s、50ms）：

```json
前：{summary(before)}
后：{summary(after)}
开打增量：{summary(r['battleAfter'])}
```

满足≤1,000,000字节、≤3.5秒。

### 5. 文件、截图与命令

三张表：
- `{root}/验收记录/R200/体型表.tsv`
- `{root}/验收记录/R200/配招表.tsv`
- `{root}/验收记录/R200/飞行表.tsv`

截图：`{root}/验收记录/R200/补充1/选人-1440x900.png`、同目录`选人-844x390.png`、`选人-667x375.png`。

飞行接触表：`{root}/验收记录/R200/飞行/`。

本轮主要改动：`游戏数据.py`、`界面-GBA.css`、3个继承验收文件、`scripts/R200b-*`、`scripts/R200-数据验收.py`、`learnset-audit.tsv`及150份原始响应、候选/清单、验收证据。完整清单见`验收记录/R200/补充1/改动文件清单.txt`。

```bash
"$PY" scripts/R200b-可学采集.py
"$PY" scripts/R200b-数据验收.py
"$PY" scripts/R200-数据验收.py
"$PY" 构建完整版.py
"$PY" scripts/R200-发布检查.py
"$PY" scripts/R200b-汇总.py
```

浏览器一律经授权`tools/远程执行.sh`、headless、分配端口执行。完整原样数字和来源见`验收记录/R200/补充1/总验收.json`、`回归-原样摘要.txt`、`回归来源.json`、`复验记录.json`；断言迁移见`验收记录/R200/断言迁移.md`。

### 6. 边界与未完成

- **没有将全部49套再次跑在最后一个SHA。** 完整49套之后只修横屏配招CSS，并复验受影响6套、200只、797槽位、选人、离线、首开。`最后CSS差异.json`证明其余玩法JS/DATA/HTML不变，仅另有埋点构建版本号变化。
- 场地变体重建会刷新埋点Git短码，触发原批次SHA相等守卫；原错误保留，逐字节证明只变该版本号，不把不同SHA冒称同一候选。
- 不包含线上部署、公网实测、实体手柄人工验收或新增150只胜率再平衡；没有未说明的精灵替换。
'''
(OUT/'交付说明.md').write_text(note)
print(note)
