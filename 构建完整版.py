"""构建轻量离线完整版。候选→浏览器验收→人工脚本原子提升，不自动覆盖 index.html。"""

from pathlib import Path
from PIL import Image
import csv, hashlib, json, math, re, subprocess, tempfile, html as html_lib, sys
from 游戏数据 import (
    TYPES, MOVES, DIFFICULTIES, HP_MULTIPLIER, DEFAULT_DIFFICULTY, roster_metadata,
)
from 体型数据 import apply as apply_body_profiles
from 招式特效.打包实战 import build as build_generated_fx
from 构建竞技场 import build as build_arenas
from 空中判定 import apply as apply_airborne
from 异常状态数据 import apply as apply_statuses
from 招式特效.第3批参数 import MOVES as R3_MOVES
from 招式动画.打包 import build as build_animations, runtime as animation_runtime

ROOT = Path(__file__).resolve().parent
LIB = ROOT / "素材/角色库"
ENV = ROOT / "素材/绿宝石场景"
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)
sha = lambda b: hashlib.sha256(b).hexdigest()
all_rows = json.loads((LIB / "角色库.json").read_text())
selection = json.loads((ROOT / "首发50.json").read_text())
ids = selection["ids"]
assert selection["limit"] == 50 and len(ids) == len(set(ids)) == 50, "用户硬上限50；不能自行扩充"
rows = [c for c in all_rows if c["id"] in ids]
assert len(rows) == 50 and {c["id"] for c in rows} == set(ids)
# 已下载的其他角色只作备用；不进入HTML、资产清单、服务白名单或离线包。
flights = json.loads((LIB / "飞行修正/飞行包.json").read_text())
assert {c["id"] for c in rows if 3 in c["types"]} == {int(n) for n in flights}, (
    "每一只上场飞行系都必须核验，不能只修烈雀"
)
for c in rows:
    if str(c["id"]) in flights:
        f = flights[str(c["id"])]
        c["audit"][f["art"]["sourceAnimation"]] = f["audit"]
        for role in f["roles"]:
            c["art"][role] = dict(f["art"])
        for role, offsets in f["bodyOffsets"].items():
            c["art"][role]["bodyOffsets"] = offsets
metadata = roster_metadata(rows)
for c in metadata:
    if str(c["id"]) in flights:
        c["flightHeight"] = flights[str(c["id"])]["flightHeight"]
body_receipt = apply_body_profiles(metadata, rows, ROOT, LIB)
packed = {}
assets = {}
audit = []
cells = 0


def output(name, data):
    assert Path(name).name == name and not name.startswith(".")
    f = OUT / name
    if not f.exists() or f.read_bytes() != data:
        tmp = f.with_suffix(f.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(f)
    assets["assets/" + name] = {"bytes": len(data), "sha256": sha(data)}
    return "assets/" + name


icons = Image.new("RGBA", (32 * 48, math.ceil(len(rows) / 32) * 48))
for index, c in enumerate(rows):
    pack = {}
    seen = {}
    for name, a in c["art"].items():
        path = (LIB / a["file"]).resolve()
        assert path.is_relative_to(LIB.resolve())
        data = path.read_bytes()
        assert len(data) < 2000000 and sha(data) == c["audit"][a["sourceAnimation"]]["sha256"]
        assert (
            a["rows"] in (1, 8)
            and 1 <= a["frames"] <= 120
            and a["frameWidth"] <= 256
            and a["frameHeight"] <= 256
        )
        assert (
            all(math.isfinite(d) and d > 0 for d in a["durations"])
            and len(a["durations"]) == a["frames"]
        )
        assert abs(sum(a["durations"]) - a["totalDuration"]) < 1e-8
        if a["hitFrame"] is not None:
            assert (
                0 <= a["hitFrame"] < a["frames"]
                and abs(sum(a["durations"][: a["hitFrame"]]) - a["hitTime"]) < 1e-8
            )
        with Image.open(path) as im:
            im.load()
            assert im.mode == "RGBA" and im.size == (
                a["frameWidth"] * a["frames"],
                a["frameHeight"] * a["rows"],
            )
            if a["sourceAnimation"] not in seen:
                for y in range(a["rows"]):
                    for x in range(a["frames"]):
                        tile = im.crop(
                            (
                                x * a["frameWidth"],
                                y * a["frameHeight"],
                                (x + 1) * a["frameWidth"],
                                (y + 1) * a["frameHeight"],
                            )
                        )
                        bb = tile.getbbox()
                        assert (
                            bb
                            and 0 < bb[0] < bb[2] < a["frameWidth"]
                            and 0 < bb[1] < bb[3] < a["frameHeight"]
                        ), (c["id"], name, x, y)
                        cells += 1
                # PNG lossless palette encoding: preserve exact RGBA pixels while reducing transfer size.
                colors = im.getcolors(257)
                encoded = im
                if colors is not None and len(colors) <= 256:
                    palette = sorted(rgba for count, rgba in colors)
                    lookup = {rgba: i for i, rgba in enumerate(palette)}
                    encoded = Image.new("P", im.size)
                    encoded.putpalette([v for rgba in palette for v in rgba[:3]])
                    encoded.putdata([lookup[rgba] for rgba in im.get_flattened_data()])
                    encoded.info["transparency"] = bytes(rgba[3] for rgba in palette)
                    assert encoded.convert("RGBA").tobytes() == im.tobytes()
                from io import BytesIO

                b = BytesIO()
                encoded.save(b, format="PNG", optimize=True)
                png = b.getvalue()
                file = output(f"{c['id']:04}-{a['sourceAnimation']}-{sha(png)[:12]}.png", png)
                seen[a["sourceAnimation"]] = file
        allowed = [
            "frameWidth",
            "frameHeight",
            "frames",
            "rows",
            "anchorX",
            "anchorY",
            "durations",
            "totalDuration",
            "hitTime",
        ]
        pack[name] = {k: a[k] for k in allowed}
        pack[name]["src"] = seen[a["sourceAnimation"]]
        if "bodyOffsets" in a:
            assert len(a["bodyOffsets"]) == a["rows"] and all(
                len(row) == a["frames"] for row in a["bodyOffsets"]
            )
            pack[name]["bodyOffsets"] = a["bodyOffsets"]
    assert set(pack) == {"idle", "walk", "shoot", "melee", "hurt", "dash"}
    packed[c["id"]] = pack
    icon = Image.open(LIB / c["icon"]).convert("RGBA")
    assert icon.size == (48, 48) and icon.getbbox()
    box = icon.getbbox()
    cut = icon.crop(box)
    factor = min(42 / cut.width, 42 / cut.height)
    cut = cut.resize(
        (max(1, round(cut.width * factor)), max(1, round(cut.height * factor))),
        Image.Resampling.NEAREST,
    )
    cell = Image.new("RGBA", (48, 48))
    cell.paste(cut, ((48 - cut.width) // 2, (48 - cut.height) // 2))
    icons.paste(cell, (index % 32 * 48, index // 32 * 48))
    audit.append(
        {
            "id": c["id"],
            "name": c["name"],
            "actions": 6,
            "uniqueSources": len(seen),
            "nativeWalkPoses": c["audit"][c["art"]["walk"]["sourceAnimation"]]["distinctPoses"],
            "fallbackRoles": [k for k, a in c["art"].items() if a.get("roleFallback")],
            "sourceSHAValidated": True,
            "pngDecoded": True,
            "clipping": 0,
            "nativeFloatOrBob": c.get("nativeFloatOrBob", False),
        }
    )
from io import BytesIO

b = BytesIO()
icons.save(b, format="PNG", optimize=True)
iconPNG = b.getvalue()
iconFile = output("icons-" + sha(iconPNG)[:12] + ".png", iconPNG)
subprocess.run([sys.executable, str(ENV / "构建丰缘.py")], check=True)
scene_catalog = json.loads((ENV / "场景目录.json").read_text())
environments = scene_catalog["scenes"]
assert len({e["id"] for e in environments}) == len(environments) and environments
terrains = scene_catalog.get("terrains", [])
for terrain in terrains:
    for chunk in terrain["chunks"]:
        for key in ["ground", "over"]:
            if key not in chunk:
                continue
            ref = chunk[key]
            path = (ENV / ref["path"]).resolve()
            assert path.is_relative_to(ENV.resolve())
            png = path.read_bytes()
            assert sha(png) == ref["sha256"]
            with Image.open(path) as im:
                assert max(im.size) <= 512
                im.verify()
            chunk[key + "Src"] = output("emerald-" + key + "-" + sha(png)[:12] + ".png", png)
    for effect in terrain.get("fieldEffects", {}).values():
        path = (ENV / effect["path"]).resolve()
        assert path.is_relative_to(ENV.resolve())
        png = path.read_bytes()
        assert sha(png) == effect["sha256"]
        with Image.open(path) as im:
            im.verify()
        effect["src"] = output("emerald-grass-" + sha(png)[:12] + ".png", png)
for scene in environments:
    for key in ["ground", "objects", "preview"]:
        path = (ENV / scene[key]).resolve()
        assert path.is_relative_to(ENV.resolve())
        data = path.read_bytes()
        assert sha(data) == scene[key + "SHA256"]
        with Image.open(path) as im:
            im.verify()
        scene[key + "Src"] = output(key + "-" + sha(data)[:12] + ".png", data)
env = next(e for e in environments if e["id"] == scene_catalog["default"])
for a in metadata:
    assert a["hp"] > 0 and 0 < a["speed"] <= 230 and set(a["types"]).issubset(TYPES)
    assert 1 <= len(a["defaultMoves"]) <= 4
    assert len(set(a["defaultMoves"])) == len(a["defaultMoves"])
    assert set(a["defaultMoves"]).issubset(a["learnset"]) and set(a["learnset"]).issubset(MOVES)
for key, m in MOVES.items():
    assert m["id"] == key and m["kind"] in {
        "shot",
        "fan",
        "melee",
        "rush",
        "spin",
        "beam",
        "zone",
        "nova",
        "guard",
        "heal",
        "buff",
        "splash",
    }
    assert m["cd"] >= m["windup"] + m["recovery"] + (m["range"] / 630 if m["kind"] == "rush" else 0)
    assert 0 < m["cost"] <= 100 and m["type"] in TYPES
matrix = {}
for row in csv.DictReader((LIB / "原始/type_efficacy.csv").open()):
    attack, defense, factor = (
        int(row["damage_type_id"]),
        int(row["target_type_id"]),
        int(row["damage_factor"]) / 100,
    )
    if attack in TYPES and defense in TYPES:
        matrix.setdefault(attack, {})[defense] = factor
assert len(matrix) == 18 and all(len(v) == 18 for v in matrix.values())
assert set().union(*(set(c["learnset"]) for c in metadata)) == set(MOVES), (
    "招式必须确实可以在可玩角色上选择"
)
# Every default loadout must cover every typing, except explicitly flagged harmless loadouts.
def assert_default_damage_coverage(metadata, moves, matrix):
    type_combos = {tuple(c["types"]) for c in metadata}
    for c in metadata:
        if "无伤配招" in c.get("flags", []):
            continue
        for target in type_combos:
            assert any(
                moves[id]["kind"] not in ("guard", "heal", "buff", "splash")
                and moves[id]["damage"] > 0
                and math.prod(matrix[moves[id]["type"]][t] for t in target) > 0
                for id in c["defaultMoves"]
            ), (c["id"], "all default attacks immune vs", target)


assert_default_damage_coverage(metadata, MOVES, matrix)
# Source receipts and every contributing artist remain in the portable delivery, not just in the workspace.
credits = [
    "Poight · 非官方个人非商业练习",
    "角色像素源：PMDCollab/SpriteCollab（各物种逐项署名如下）",
    "https://github.com/PMDCollab/SpriteCollab",
    "场景源：Game Freak / pret/pokeemerald，commit " + env["sourceCommit"],
    "https://github.com/pret/pokeemerald",
    "图鉴名称、类型、基础数据与相克表：PokeAPI/pokeapi",
    "招式池、血量、速度、技能数值与实时战斗机制为本项目改编，不是官方完整规则。",
    "未使用用户提供的GBA ROM；不包含ROM、不运行上游游戏代码。",
    "仓库政策或代码许可证不等于取得宝可梦/官方图像商业传播授权。",
    "包含原作和社区美术，仅供个人非商业研究试玩，请勿冒充官方或转售。",
    "部分源动作采用原生浮动或共享方向，不声称每个动作都具有八套独立姿态。不同招式可复用原生发力动作。",
    "飞行修正：8只飞行系使用原生Hover/振翅/腾空姿态重新编排循环，以躯干锚点移除原地跳跃轨迹。喷火龙、飞天螳螂、快龙使用原生Hop翼姿重编，并非原素材已有完整专用飞行循环；暴鲤龙为无翼空中蜿蜒。不是仅抬高走路贴图。",
    "",
]
for c in rows:
    credits.extend([f"#{c['id']:04} {c['name']}", c["credits"].strip(), ""])
creditBytes = ("\n".join(credits) + "\n").encode()
creditFile = output("鸣谢-" + sha(creditBytes)[:12] + ".txt", creditBytes)
status_assets = apply_statuses(MOVES, ROOT, output)
generatedFx = build_generated_fx(MOVES, output)
apply_airborne(MOVES, generatedFx, TYPES, ROOT / "协作/J1/空中判定表.tsv", R3_MOVES)
arena_scenes, arena_default = build_arenas(ROOT, output)
environments = arena_scenes + environments
env = next(e for e in environments if e["id"] == arena_default)
portraits = json.loads((ROOT / "素材/立绘/图集.json").read_text())
assert set(map(int, portraits)) == set(ids)
for ident, portrait in portraits.items():
    png = (ROOT / "素材/立绘" / portrait["file"]).read_bytes()
    assert sha(png) == portrait["sha256"]
    portrait["src"] = output(f"portrait-{ident}-{sha(png)[:12]}.png", png)
portrait_json = json.dumps(portraits, ensure_ascii=False, separators=(",", ":")).encode()
output("portrait-timing.json", portrait_json)
data = {
    "portraits": portraits,
    "hpMultiplier": HP_MULTIPLIER,
    "defaultDifficulty": DEFAULT_DIFFICULTY,
    "generatedFx": generatedFx,
    "moveAnimations": build_animations(ROOT, output, TYPES),
    "revision3Moves": R3_MOVES,
    "roster": [{k: v for k, v in c.items() if k != "credits"} for c in metadata],
    "moves": MOVES,
    "statusAssets": status_assets,
    "tiers": DIFFICULTIES,
    "types": TYPES,
    "efficacy": matrix,
    "environment": env,
    "environments": environments,
    "terrains": terrains,
    "art": packed,
    "icons": iconFile,
    "iconColumns": 32,
    "iconOrder": [c["id"] for c in rows],
}
script = (
    (ROOT / "桥梁通行.js").read_text()
    + "\n"
    + (ROOT / "丰缘接缝.js").read_text()
    + "\n"
    + (ROOT / "世界地图.js").read_text()
    + "\n"
    + (ROOT / "竞技场.js").read_text()
    + "\n"
    + (ROOT / "草丛藏身.js").read_text()
    + "\n"
    + (ROOT / "大地图通行.js").read_text()
    + "\n"
    + (ROOT / "体型判定.js").read_text()
    + "\n"
    + (ROOT / "咬类招式.js").read_text()
    + "\n"
    + animation_runtime(ROOT)
    + "\n"
    + (ROOT / "生图招式.js").read_text()
    + "\n"
    + (ROOT / "招式第3批.js").read_text()
    + "\n"
    + (ROOT / "招式动画-VA2.js").read_text()
    + "\n"
    + (ROOT / "平衡测试.js").read_text()
    + "\n"
    + (ROOT / "打击感.js").read_text()
    + "\n"
    + (ROOT / "瞄准预警.js").read_text()
    + (ROOT / "手感参数.js").read_text()
    + "\n"
    + (ROOT / "手机操作.js").read_text()
    + "\n"
    + (ROOT / "战斗界面方案.js").read_text()
    + "\n"
    + (ROOT / "跳跃.js").read_text()
    + "\n"
    + (ROOT / "异常状态.js").read_text()
    + "\n"
    + (ROOT / "立绘.js").read_text()
    + "\n"
    + (ROOT / "演示模式.js").read_text()
    + "\n"
    + (ROOT / "对战.js").read_text()
)
assert script.count("__GAME_DATA__") == 1
script = script.replace(
    "__GAME_DATA__",
    json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
)
with tempfile.NamedTemporaryFile(mode="w", suffix=".js") as f:
    f.write(script)
    f.flush()
    subprocess.run(["node", "--check", f.name], check=True)
# 本人指定的抖音头像favicon：本地小PNG进入同一发布白名单，不热链抖音。
faviconPNG = (ROOT / "图标/favicon-32.png").read_bytes()
assert len(faviconPNG) <= 8192
with Image.open(BytesIO(faviconPNG)) as favicon:
    assert favicon.size == (32, 32) and favicon.format == "PNG"
    favicon.verify()
faviconFile = output("favicon-" + sha(faviconPNG)[:12] + ".png", faviconPNG)
page = (ROOT / "页面.html").read_text().replace("assets/鸣谢.txt", creditFile)
assert (
    page.count("__GAME_SCRIPT__")
    == page.count("__GAME_CSS__")
    == page.count("__GAME_FAVICON__")
    == 1
)
result = (
    page.replace(
        "__GAME_CSS__",
        (ROOT / "界面.css").read_text()
        + "\n"
        + (ROOT / "街机界面.css").read_text()
        + "\n"
        + (ROOT / "配招界面.css").read_text()
        + "\n"
        + (ROOT / "场景界面.css").read_text()
        + "\n"
        + (ROOT / "选人界面.css").read_text()
        + "\n"
        + (ROOT / "战斗界面方案.css").read_text()
        + "\n"
        + (ROOT / "手机操作.css").read_text()
        + "\n"
        + (ROOT / "演示模式.css").read_text(),
    )
    .replace("__GAME_SCRIPT__", script)
    .replace("__GAME_FAVICON__", faviconFile)
)
assert "__GAME_" not in result and not re.search(
    r'<(?:script|link|img)[^>]+(?:src|href)=["\']https?://', result
)
(ROOT / "候选试玩.html").write_text(result)
report = {
    "candidate": "候选试玩.html",
    "bytes": len(result.encode()),
    "sha256": sha(result.encode()),
    "roster": len(rows),
    "rosterCap": 50,
    "selectedIDs": ids,
    "sourceLibraryOnly": len(all_rows),
    "moves": len(MOVES),
    "moveKinds": sorted({m["kind"] for m in MOVES.values()}),
    "tiers": [t["name"] for t in DIFFICULTIES],
    "cellsVerified": cells,
    "assets": len(assets),
    "assetsBytes": sum(a["bytes"] for a in assets.values()),
    "bodyProfiles": body_receipt["count"],
    "sourceRuntime": "页面.html + 界面.css + 街机界面.css + 配招界面.css + 场景界面.css + 选人界面.css + 战斗界面方案.css + 手机操作.css + 演示模式.css + 演示模式.js + 战斗界面方案.js + 手机操作.js + 桥梁通行.js + 丰缘接缝.js + 世界地图.js + 竞技场.js + 构建竞技场.py + 对战.js + 平衡测试.js + 打击感.js + 瞄准预警.js + 手感参数.js + 异常状态.js + 异常状态数据.py + 招式状态表.tsv + 大地图通行.js + 草丛藏身.js + 跳跃.js + 空中判定.py + 生图招式.js + 咬类招式.js + 招式动画引擎.js + 招式动画接入.js + 主角招式外观.js + 招式动画/打包.py + 体型判定.js + 体型数据.py + 游戏数据.py + 素材/绿宝石场景/构建丰缘.py + 素材/绿宝石场景/构建通行.py + 素材/绿宝石场景/桥梁元数据.py",
    "scenes": [
        {
            "id": e["id"],
            "name": e["name"],
            "obstacles": len(e["collisionContract"]),
            "terrainID": e.get("terrainID"),
        }
        for e in environments
    ],
    "characterAudit": audit,
    "externalRuntimeRequests": 0,
}
(ROOT / "构建核验-完整版.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
(ROOT / "候选发布清单.json").write_text(
    json.dumps(
        {"candidateSHA256": report["sha256"], "assets": assets}, ensure_ascii=False, indent=2
    )
    + "\n"
)
print(
    json.dumps(
        {k: v for k, v in report.items() if k != "characterAudit"}, ensure_ascii=False, indent=2
    )
)
