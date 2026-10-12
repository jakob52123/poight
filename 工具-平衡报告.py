"""Recompute TSVs and the balance report from archived live-engine JSONL, no browser needed."""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/平衡"
MULTIPLIERS = [1, 3, 4, 5, 6, 6.5, 7, 8, 9, 10]
MELEE = {"melee", "rush", "spin"}
SUPPORT = {"guard", "heal", "buff"}


def load(name):
    return [json.loads(line) for line in (OUT / name).read_text().splitlines() if line]


def tsv(name, rows):
    with (OUT / name).open("w", newline="") as file:
        csv.writer(file, delimiter="\t").writerows(rows)


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="全量对局-完整.jsonl")
    parser.add_argument("--out-dir", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.out_dir
    catalog = json.loads((OUT / "catalog.json").read_text())
    roster = {c["id"]: c for c in catalog["roster"]}
    moves = catalog["moves"]
    games = load(args.results)
    plan = json.loads((OUT / "全量计划.json").read_text())
    expected = [(j["a"], j["b"], j["seed"] + i) for j in plan for i in range(j["n"])]
    assert [(g["a"], g["b"], g["seed"]) for g in games] == expected
    assert len(games) == 7350
    assert all(g["hpMultiplier"] == 6 and g["tier"] == g["playerTier"] == "great" for g in games)
    for game in games:
        for side in ["a", "b"]:
            net = sum(e["amount"] * (-1 if e["kind"] == "heal" else 1)
                      for e in game["composition"] if e["target"] == side)
            assert net == game["maxHP"][side] - game["hp"][side]
    pair = defaultdict(Counter)
    totals = defaultdict(Counter)
    cross = Counter()
    composition = Counter()
    four = defaultdict(list)
    style = {n: "纯近战" if all(moves[m]["kind"] in MELEE for m in c["defaultMoves"]
                              if moves[m]["kind"] not in SUPPORT) else "带远程混合"
             for n, c in roster.items()}
    for game in games:
        for side, other in [("a", "b"), ("b", "a")]:
            n, opponent = game[side], game[other]
            outcome = ("win" if game["winner"] == side else "loss"
                       if game["winner"] == other else game["winner"])
            pair[n, opponent][outcome] += 1
            totals[n][outcome] += 1
            totals[n]["n"] += 1
            if style[n] == "纯近战" and style[opponent] != style[n]:
                cross[outcome] += 1
        for e in game["composition"]:
            if e["kind"] == "direct":
                composition["近战" if moves[e["move"]]["kind"] in MELEE else "远程/范围"] += e["amount"]
            else:
                composition[e["kind"]] += e["amount"]
        # Incoming fourfold moves in DEFAULT loadouts, not just theoretical type matchups.
        for side, other in [("a", "b"), ("b", "a")]:
            attacker, defender = roster[game[side]], roster[game[other]]
            matching = []
            for mid in attacker["defaultMoves"]:
                move = moves[mid]
                if move["kind"] in SUPPORT:
                    continue
                effectiveness = 1
                for typ in defender["types"]:
                    effectiveness *= (2 if move.get("waterEffective") and typ == 11
                                      else catalog["efficacy"][str(move["type"])][str(typ)])
                if effectiveness == 4:
                    matching.append(mid)
            if matching:
                four[attacker["id"], defender["id"]].append({
                    "game": game, "side": side, "moves": matching,
                    "ko": game["hp"][other] <= 0,
                    "fourDamage": sum(e["amount"] for e in game["composition"]
                                      if e["source"] == side and e["multiplier"] == 4),
                })
    assert all(sum(counts.values()) == 6 for counts in pair.values())
    assert all(counts["n"] == 294 for counts in totals.values())
    winrate = {n: totals[n]["win"] / totals[n]["n"] * 100 for n in roster}
    tsv("胜率矩阵.tsv", [["攻击方编号/名称\\对手"] + [f"{n}-{c['name']}" for n, c in roster.items()]] + [
        [f"{n}-{c['name']}"] + ["NA" if n == o else f"{pair[n, o]['win'] / 6 * 100:.4f}"
                                for o in roster] for n, c in roster.items()
    ])
    tsv("各物种总胜率.tsv", [["id", "name", "style", "games", "wins", "losses", "draws", "timeouts",
                           "win_percent", "score_percent"]] + [
        [n, roster[n]["name"], style[n], totals[n]["n"], totals[n]["win"], totals[n]["loss"],
         totals[n]["draw"], totals[n]["timeout"], f"{winrate[n]:.4f}",
         f"{100 * (totals[n]['win'] + totals[n]['draw'] / 2) / totals[n]['n']:.4f}"]
        for n in sorted(roster, key=lambda k: -winrate[k])
    ])
    summary, durations = [], []
    for multiplier in MULTIPLIERS:
        rows = load(f"时长-{multiplier}.jsonl")
        groups = defaultdict(list)
        for row in rows:
            groups[row["a"], row["b"]].append(row)
        assert len(rows) == 240 and len(groups) == 12
        medians = [median(g["seconds"] for g in values) for values in groups.values()]
        summary.append({"multiplier": multiplier, "pooled": median(g["seconds"] for g in rows),
                        "group_median": median(medians), "minimum": min(medians),
                        "under25": sum(m < 25 for m in medians),
                        "timeouts": sum(g["winner"] == "timeout" for g in rows)})
        for (a, b), values in groups.items():
            assert len(values) == 20
            durations.append([multiplier, a, roster[a]["name"], b, roster[b]["name"], 20,
                              median(g["seconds"] for g in values), min(g["seconds"] for g in values),
                              max(g["seconds"] for g in values), values[0]["label"]])
    tsv("时长逐组.tsv", [["multiplier", "a", "a_name", "b", "b_name", "n", "median", "min", "max", "coverage"]]
        + durations)
    tsv("倍率汇总.tsv", [["multiplier", "pooled_median", "median_of_group_medians", "min_group", "under25", "timeouts"]]
        + [list(s.values()) for s in summary])
    four_rows = []
    for (a, b), values in sorted(four.items()):
        ko = [v["game"]["seconds"] for v in values if v["ko"]]
        four_rows.append([a, roster[a]["name"], b, roster[b]["name"], ",".join(values[0]["moves"]),
                          len(values), len(ko), median(ko) if ko else "NA", min(ko) if ko else "NA",
                          median(v["game"]["seconds"] for v in values),
                          sum(v["fourDamage"] for v in values)])
    tsv("四倍克制.tsv", [["attacker", "attacker_name", "defender", "defender_name", "fourfold_moves", "n",
                         "defender_KOs", "KO_median_seconds", "KO_min_seconds", "all_game_median", "fourfold_damage"]]
        + four_rows)
    pure = [n for n in roster if style[n] == "纯近战"]
    mixed = [n for n in roster if n not in pure]
    timeouts = sum(g["winner"] == "timeout" for g in games)
    draws = sum(g["winner"] == "draw" for g in games)
    def names(ids):
        return "、".join(f"{roster[n]['name']}（#{n}，{winrate[n]:.2f}%）" for n in ids) or "无"
    report = [
        "# Poight T9 平衡报告", "",
        "> 结论：功能与全量数据已完成，时长验收未全达标。分支暂取 HP_MULTIPLIER = 6；不是宣称已满足全部时长门槛。",
        "> 保留原定12组，不移除失败的四倍克制对局，不改招式/配招/AI策略。候选调整须导演审批。", "",
        "## 1. 测量协议与复现", "",
        "- 浏览器真实引擎，headless Chromium；不是另写伤害公式。`?test=1` 才实例化测试控制器。",
        "- 玩家侧通过临时交换调用上下文复用原 `thinkEnemy`，独立 brain/tier；包含该档位的预瞄误差、反应、寻路、闪避。",
        "- 120 Hz整数步、每步原 update；不跳碰撞，不省略会消耗随机数的粒子。仅省略逐帧渲染；逻辑仍与普通 step 一致。",
        "- 固定种子LCG；每局重置seed/serial/草丛/招式状态/brain。JSONL只含模拟时间，不含墙钟或帧性能字段。",
        "- 固定卡那兹市原生出生点（emerald-rustborocity，间距240px），默认合法四招；不摆到空白竞技场，不改地图。",
        "- 结论只覆盖该地图、出生点和默认四招，不外推人类玩家/其他地图/自选配招。红白球AI是近似，不是真实新手试验。",
        "- 校准：12组各20局，种子1001+组序号×100 ... +19，同种子跨倍率配对；共10个倍率/2400局。",
        "- 全量：50选2=1225对，每对6局（左右换边各3局），共7350局，每只294局；不跑镜像，不抽样。",
        "- 全量种子20261011+无序配对序号×10+[0,1,2]，换边使用同种子；档位均great，HP×6。",
        "- 固定600秒截尾；timeout单列，不凭剩余血量判胜，且不丢弃。超时局的600秒是下界；本次12组中位数均未落到截尾值。", 
        "- 全量执行曾被外层200秒限时打断；保留1561局，按计划精确续跑5789局，汇总验证7350个(a,b,seed)与完整计划逐项一致。",
        "- TSV胜率为严格胜局/全部局数（%）；平局不算胜，另给半分得分率；矩阵对角NA。6局/对的统计方差很大。",
        "- 单物种294局在p≈0.5下粗略95%抽样误差±5.7个百分点；种子/配招/对手相关性使它不等于真实玩家置信区间。", "",
        "```bash",
        'PY=python3',
        'export POIGHT_TEST_URL=http://localhost:8829/',
        '"$PY" 工具-平衡模拟.py --a 25 --b 6 --tier poke --n 5 --seed 1',
        '"$PY" 工具-平衡模拟.py --plan 验收记录/平衡/全量计划.json --out 验收记录/平衡/全量对局-完整.jsonl',
        '"$PY" 工具-平衡报告.py',
        "```", "",
        "`--hp-multiplier` 仅供test钩子离线比较，不写游戏配置或存档；`--player-tier` 可单独指定玩家托管档位。",
        "每局JSONL包含tick、秒数、胜方、双方HP、伤害/承伤，以及按来源/目标/招式/直接/持续/反伤/治疗分组的金额和命中时间。", "",
        "## 2. 全局血量校准：未全达标", "",
        "先固定12组覆盖大/小、纯近战/远程、混合、抵抗/免疫和四类4倍弱点，再测倍率。没有用实测结果替换较难达标的组。",
        "选用6而非6.5：总体中位数离60秒上限有余量，整数血量无半整数取整争议；但不能修复极端克制的短局。", "",
        "|倍率|240局总体中位数(s)|12个组中位数的中位数(s)|最短组(s)|低于25秒组数|超时|",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    report += [f"|{s['multiplier']}|{s['pooled']:.3f}|{s['group_median']:.3f}|{s['minimum']:.3f}|{s['under25']}|{s['timeouts']}|" for s in summary]
    report += ["", "HP×6详细结果（每组n=20；双方poke）：", "",
               "|A|B|覆盖|中位数(s)|最短—最长(s)|", "|---|---|---|---:|---:|"]
    report += [f"|{r[2]} #{r[1]}|{r[4]} #{r[3]}|{r[9]}|{r[6]:.3f}|{r[7]:.3f}—{r[8]:.3f}|" for r in durations if r[0] == 6]
    report += ["",
               "**冲突**：×6总体54.879秒合格，但喷火龙vs巨钳螳螂16.242秒不合格。×6.5总体59.921秒仍有17.421秒短组；",
               "×10使最短组27.104秒越过25秒，却把总体拉到93.329秒。已测候选没有同时满足两条门槛；不能据有限采样证明所有实数倍率绝无解。",
               "停止进一步修改数值，不通过改配招、改AI、删组或提高下限时间来伪造达标。需导演决定放宽极端4倍对局下限，或另开调整克制/招式的任务。",
               "另一个体验风险：指定的皮卡丘vs喷火龙在×6下中位数83.238秒，若导演要求该组自身40–60秒，也未满足。", "",
               "## 3. 50只全量胜率", "",
               f"总计{len(games)}局；平局{draws}；600秒超时{timeouts}；玩家侧胜{sum(g['winner'] == 'a' for g in games)}，电脑侧胜{sum(g['winner'] == 'b' for g in games)}。",
               "逐对见 `胜率矩阵.tsv`，逐物种见 `各物种总胜率.tsv`。",
               "左右出生点和每tick先玩家后电脑的原引擎处理顺序可能带来位置优势；换边各3局用于均衡，未修改原顺序。", "",
               "### >65%", names([n for n in sorted(roster, key=lambda k: -winrate[k]) if winrate[n] > 65]), "",
               "### <35%", names([n for n in sorted(roster, key=lambda k: winrate[k]) if winrate[n] < 35]), "",
               "## 4. 近战 vs 远程", "",
               "分类依据实际运行时默认配招：除支援招以外全为melee/rush/spin才算纯近战，其余叫“带远程混合”，不是官方角色定位。",
               f"纯近战{len(pure)}只：" + "、".join(roster[n]["name"] for n in pure) + "。",
               f"纯近战全对手平均胜率{sum(winrate[n] for n in pure)/len(pure):.2f}%；带远程混合{len(mixed)}只平均{sum(winrate[n] for n in mixed)/len(mixed):.2f}%。",
               f"两类交叉对局{sum(cross.values())}局：纯近战胜{cross['win']}，负{cross['loss']}，平{cross['draw']}，超时{cross['timeout']}；纯近战胜率{cross['win']/sum(cross.values())*100:.2f}%。",
               "实际伤害合计（非DPS、非独立因果归因）：`" + json.dumps(dict(composition), ensure_ascii=False) + "`。",
               "**本批结果不支持“纯近战整体吃亏”的预设，反而纯近战组占优。** 不能据此全局增强近战或削弱远程。",
               "属性、体型、移速和默认招式同时变化，不能把分组差距全归因于风筝。尤其大钢蛇的160移速/庞大体型不能直接代表所有近战。",
               "下方近战留人/远程减速仅针对人工实测中的局部风筝问题，需挑对应失败对局先AB；不是本批全量统计支持的上线建议。", "",
               "## 5. 四倍克制击倒时间", "",
               "只统计默认配招中确有4倍招的有向物种组合；KO中位数仅统计该防守者真实被击倒的局，不把攻击者败北算成防守者TTK。",
               "因此KO统计有幸存者偏差；同时列n/KO数，并保留全体时长与4倍实际伤害于 `四倍克制.tsv`。0次KO记NA。", "",
               "|攻击方|防守方|4倍招|局数/防守方KO|KO中位(s)|最快KO(s)|",
               "|---|---|---|---:|---:|---:|"]
    report += [f"|{r[1]}|{r[3]}|{r[4]}|{r[5]}/{r[6]}|{r[7]:.3f}|{r[8]:.3f}|" if r[6]
               else f"|{r[1]}|{r[3]}|{r[4]}|{r[5]}/0|NA|NA|" for r in four_rows]
    report += ["", "## 6. 候选调整（全部未落实，影响为估算，不是实测）", "",
               "|问题|候选|估算依据/可能影响|风险与下一步|", "|---|---|---|---|",
               "|4倍短局与全局时长冲突|仅将复合4倍封顶到2.5倍|受影响直接伤害−37.5%；若全靠该伤害，TTK约×1.6；16.242秒粗估≈25.99秒|固定DOT/控制/取整/命中节奏会偏离；会淡化属性相克，必须另任务实测|",
               "|近战接触后被拉开|近战命中后的受击硬直由0.20增至0.26秒；不增加空挥收益|多留0.06秒，对手200px/s至多少跑12px，给连招接触窗口|可能形成压制锁；与现有0.14秒免疫窗、双方先后顺序一起回归|",
               "|远程放风筝|远程出招移动系数0.72降至0.55|出招期200px/s时少34px/s；0.4秒动作少走13.6px，近战200px/s追击闭合速度56→90，追上时间约−38%|仅是直线模型，转向/闪避/CD改变实际值；勿一并削弱近战现有移动|",
               "|慢弹速与新步速|对确实偏弱的慢弹候选增加15%速度，或保留弹速而增加10%半径（二选一AB）|175px距离，350px/s弹飞0.50秒，200px/s目标可横移100px；速度+15%使飞行缩至0.435秒，少横移13px|AI会预瞄；本统计无发射尝试数，不能声称测得命中率。实际需记录发射/命中/距离，再判断|",
               "|高胜率/低胜率物种|先按上表近战/远程/4倍机制做分组AB，而非逐只改血量|294局/只的点估计只用于排优先级；候选目标是异常物种向35–65%靠拢，不承诺具体百分点|不把共享配招造成的整族偏差误判成某只独有问题|",
               "|多数普通对局拉长、极端对局仍短|若导演接受4倍封顶候选，再重新搜索全局HP倍率|整体×6已经54.879秒，但多组>80秒，HP越高越难同时约束长尾|此分支不暗改任何招式，当前×6仅为待审折中|", "",
               "以上百分比/时间是机械近似，不是AB结果；没有落实任何候选。", "",
               "## 7. 产物与边界", "",
               "- `时长计划-*.json`、`时长-*.jsonl`：所有倍率的原始240局；`时长逐组.tsv`、`倍率汇总.tsv`：从原始输出重新计算。",
               "- `全量计划.json`、`全量对局-完整.jsonl`：7350局；`胜率矩阵.tsv`、`各物种总胜率.tsv`、`四倍克制.tsv`。",
               "- `复现-1.jsonl` / `复现-2.jsonl`：指定命令逐字节对比；`平衡钩子.log`及五套既有验收日志另见同目录。",
               "- 新存档poke，旧存档原有4档均保留；未改AI策略参数、单招伤害、冷却、体力消耗、配招、HUD或地图。",
               "- 旧血量断言唯一一处：120招回归的敌方`hp<100`改为`hp<maxHP`；对应诊断伤害`100-hp`改为`maxHP-hp`。实际命中行为未弱化。",
               "- 本轮五套通过数484/362/1428/137/12，均0失败、0JS错误；新增平衡钩子88/0/0。",
               "- 共同规则写486，但tag base实际已是484：基线授权移除游戏数据.py/世界地图.js两条源码SHA守卫（见协作/冲刺基线.md与P0-体型移速.log）。T9未改此脚本、未删行为断言。",
               "- 三尺寸截图1440×900/390×844/844×390均已打开目检：对战角色、HP×6和红白球级可见；首轮截图等待resize不足，已修验收等待两帧后重拍，未改游戏相机。", 
               "- 治疗/反伤按实际HP变化记录，过量伤害只计实际扣血；全量每侧均验证伤害收支等于HP差。",
               "- 报告与截图按仓库现有.gitignore留在本地验收目录，不强行加入git。", ""]
    (OUT / "平衡报告.md").write_text("\n".join(report))
    receipt = {"games": len(games), "pairs": len(pair) // 2, "gamesPerPair": 6,
               "gamesPerSpecies": 294, "timeouts": timeouts, "draws": draws,
               "hpMultiplier": 6, "durationGatePassed": False,
               "calibrationGames": 2400,
               "rawSHA256": hashlib.sha256((OUT / args.results).read_bytes()).hexdigest()}
    (OUT / "汇总收据.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
