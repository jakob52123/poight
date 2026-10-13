"""Render the complete captured CDP request lists into the handoff document."""
import gzip
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '验收记录/首开加载'
reports = {label: json.loads((OUT / label / 'network.json').read_text())
           for label in ['before', 'after']}
selections = {label: json.loads((OUT / label / 'selection-network.json').read_text())
              for label in reports}


def category(url):
    name = urlsplit(url).path.rsplit('/', 1)[-1]
    if not name:
        return 'HTML / 内嵌代码和数据'
    if name.startswith('move-fx-'):
        return '旧招式动画图集'
    if name.startswith('animation-'):
        return 'Showdown / 原版像素 fx'
    if name.startswith('portrait-'):
        return '当前选择立绘'
    if name.startswith('icons-'):
        return '50 头像合图'
    if name.startswith(('arena-', 'ground-', 'objects-', 'emerald-')):
        return '当前场地'
    if name.startswith('status-'):
        return '异常状态共用小图'
    if name.startswith('fang-'):
        return '咬类共用命中小图'
    if name.startswith('favicon-'):
        return 'favicon'
    if name[:4].isdigit():
        return '双方角色精灵动作'
    return '其他'


def initiator(row):
    i = row.get('initiator') or {}
    frames = i.get('stack', {}).get('callFrames', [])
    if frames:
        f = frames[0]
        return f"{i['type']} · {f.get('functionName') or '(anonymous)'} · L{f['lineNumber'] + 1}:{f['columnNumber'] + 1}"
    if 'lineNumber' in i:
        return f"{i['type']} · parser L{i['lineNumber'] + 1}:{i.get('columnNumber', 0) + 1}"
    return i.get('type', 'unknown')


lines = ['# PERF · 首开请求清单与交付依据', '',
         '## 测量口径', '',
         '- 基线：冻结 `2ba2ee4` 的候选。改后：本分支候选；浏览器均在 Jade，端口 8961。',
         '- Chromium headless、新 context、空 localStorage、禁用 HTTP 缓存；CDP 全局下载 300,000 B/s、延迟 50 ms。',
         '- 字节为 CDP `Network.loadingFinished.encodedDataLength`（含传输头），不是 PNG 解码尺寸；MB=1,000,000 B。',
         '- 选人就绪：50 个可选按钮、确定可点、双方立绘已有帧，已发起请求全部完成。',
         '- 开打就绪：点击确定开始计时；改后直接核对 `phase=playing`，基线观察选人关闭且 VS 结束（其 `finishVersus` 同步进入 playing）。包含原有 1.6 秒 VS，不提前跳过。',
         '- 冻结代码实际初始阵容为 **7 vs 4**，并非任务文字的 25 vs 6。为不改默认行为，测完首开后通过真实选人按钮选择 **25 vs 6**；新增两张立绘也计入总量。',
         '- 原始逐请求 JSON 保留完整 CDP initiator；下表为全部 URL、字节、顶层发起者和模块，不用估算文件大小代替线传字节。',
         '', '## 改前 / 改后', '',
         '|阶段|改前字节|改前秒|改后字节|改后秒|门槛|', '|---|---:|---:|---:|---:|---|']
for phase, name, budget in [('selection', '首次打开→选人可点', '≤800,000 B / ≤6 s'),
                             ('battle', '确定 25 vs 6→可操作（追加）', '≤1,000,000 B / ≤6 s')]:
    b, a = reports['before'][phase], reports['after'][phase]
    lines.append(f"|{name}|{b['bytes']:,}|{b['seconds']:.3f}|{a['bytes']:,}|{a['seconds']:.3f}|{budget}|")
lines += ['', f"改后含切换至 25/6 的立绘总传输：**{reports['after']['totalWithPicks']:,} B**（≤1,500,000 B）。",
          '改前开打追加较少，是因为全部招式已在首开阶段付清，不能误读为其整体更快。', '',
          '## 根因与实现', '',
          '1. 原启动入口先 `applyProfile` 再 `openSetup`，把 104 招旧图集、全部动画贴图和战场塞入选人前的阻塞链；旧图集本身占约 20.66 MB 线传。',
          '2. 现在普通/observe 首开直接进入选人阶段；只取页面、头像合图、当前两张立绘。点击角色才取其立绘，保留原动画和布局。首次 X/Esc 仍取消草稿返回默认待开打，只在此显式操作后准备默认对局。',
          '3. `按需资源.js` 按双方配招生成依赖；`applyProfile` 等待双方动作、当前场地、本场图集/fx、状态小图全部完成才提交角色并放行 VS。',
          '4. 按招式 id 加载旧图集；Showdown 按本场 timeline effect / override 及真实渲染器的附加依赖加载，图片按 URL 去重、共享 pending，失败清除 pending 可重试。',
          '5. VH 主角八招（限定原指定物种）、VA2、VB1、核心三招已有完整轻量替代。只跳过从不使用的旧大图；其他物种及 `anim=old` 保留原图回退，未改渲染算法。',
          '6. 缺少应预取图集时明确报错，不再让 `stamp` 静默绘空白；八招逐招与 121 招懒加载实战冒烟覆盖此路径。',
          '7. 原测试 `?test=1` 是可同步任意 equip/cast/直接像素探针的特权夹具，显式保留全库预热；**不作为性能证据**。新增测试先测普通 observe 页面，再以 `?test=1&lazy=1` 验证真实懒加载预取；保存 25/6 后重载清空 JS 图片表，确认旧图集 loaded=0 再逐招，防止前一对局掩盖缺依赖。demo 也走本场资源。',
          '8. 音效由 WebAudio 合成，无音频下载；首开场地/精灵动作/招式图集请求均为零。', '',
          '## HTML 内嵌数据审计与保留理由', '',
          '- 没有 `data:image` / 内嵌 base64 图片，也没有外部 JS 请求。大头是丰缘地形拓扑和角色动作锚点，不是全量大 PNG。',
          '- 现有约束明确要求 `file://` 双击离线可玩，且页面 CSP 为 `connect-src none`；直接拆 JSON 再 fetch 会破坏两者。当前同步 catalog/地形接口也依赖这些表。',
          '- 因而本次确认保留这些内嵌表有必要：保留静态离线包、同步数据 API 和 CSP，不为首开性能放宽安全或删除离线能力；已经满足首开预算，无需引入外部脚本或另造离线加载器。',
          '- 各表独立 JSON 的未压缩 / gzip 尺寸（gzip 分别压缩不等于 HTML 总和）：', '',
          '|数据项|未压缩 B|gzip B|', '|---|---:|---:|']
html = (ROOT / '候选试玩.html').read_text()
start = html.index('const DATA = ') + len('const DATA = ')
data, _ = json.JSONDecoder().raw_decode(html[start:])
for key, value in data.items():
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    lines.append(f'|{key}|{len(raw):,}|{len(gzip.compress(raw)):,}|')
lines += ['', '## 发布与边界', '',
          '- `按需资源.js` 仅构建时内联；线上无新增 JS 类型资源。',
          '- 修正既有 VA2 对应源码附件的 `.js/.py` 后缀为 `.txt`（源码内容仍附带），构建增加发布扩展名白名单断言。没有改发布器或部署方式。',
          '- 数值、AI、身体判定、原角色/地图 PNG、尖石图集不变；静态校验见 `验收记录/首开加载/静态检查.json`。',
          '- 旧断言不删减：仅平衡钩子等待器允许“选人资源就绪”；丰缘性能先真正开打，再取场地资源快照、仍执行完整 60 秒 RAF 与原阈值。详见交付说明。',
          '', '## 按模块汇总', '']
for label in reports:
    for phase in ['selection', 'battle']:
        rows = selections[label]['requests'] if phase == 'selection' else [
            r for r in reports[label]['requests'] if r['phase'] == 'battle']
        sums = defaultdict(lambda: [0, 0])
        for row in rows:
            bucket = sums[category(row['url'])]
            bucket[0] += 1
            bucket[1] += row['bytes']
        lines += [f'### {label} / {phase}', '', '|模块|请求数|线传 B|', '|---|---:|---:|']
        lines += [f'|{key}|{count}|{size:,}|' for key, (count, size) in sums.items()]
        lines.append('')
lines += ['## 全部请求明细', '',
          '初始 inline 脚本同步发出的 Image 请求，Chromium 常归因为 parser；这是原始 CDP 返回，并非丢弃调用栈。对应业务发起点：旧图集 `PoightGeneratedMoves.load`、动画 fx `MoveAnimationEngine.load`、立绘 `PoightPortraits.set`、角色/场地 `applyProfile`。', '']
for label, report in reports.items():
    lines += [f'### {label}', '', '|阶段|模块|URL|线传 B|CDP 发起者（候选 HTML）|', '|---|---|---|---:|---|']
    initial_urls = {r['url'] for r in selections[label]['requests']}
    for row in report['requests']:
        phase = '选人首开' if row['url'] in initial_urls else '选择25/6立绘' if row['phase'] == 'selection' else '确定→开打'
        lines.append(f"|{phase}|{category(row['url'])}|`{row['url']}`|{row['bytes']:,}|{initiator(row)}|")
    lines.append('')
manifest = json.loads((ROOT / '候选发布清单.json').read_text())
size = sum(a['bytes'] for a in manifest['assets'].values())
lines += ['## 产物定位', '',
          f"- 候选 HTML SHA256：`{manifest['candidateSHA256']}`。",
          f"- 清单资产 **{len(manifest['assets'])} 文件 / {size:,} B**；加 HTML 后 **{len(manifest['assets']) + 1} 文件 / {size + len(html.encode()):,} B**（完整离线包，不是首开下载量）。",
          '- 原始网络证据：`验收记录/首开加载/{before,after}/{network,selection-network}.json`。',
          '- 三尺寸已读图：`验收记录/首开加载/after/截图/selection-{1440x900,390x844,844x390}.png`。',
          '- 全量原样摘要：`验收记录/首开加载/PERF-release/原样摘要.txt`。',
          '- 重跑：`python3 scripts/PERF-全量.py PERF-release`（本机协调，浏览器只经授权包装器在 Jade 三路执行）。', '']
(ROOT / 'docs/PERF-首开清单.md').write_text('\n'.join(lines))
print('docs/PERF-首开清单.md:', len(lines), 'lines')
