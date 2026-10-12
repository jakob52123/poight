"""Jump hit categories, resolved after generated-art runtime overrides."""


def classify(move):
    mid, kind = move["id"], move["kind"]
    if move["type"] == 3:
        return True, "飞行系例外：可命中空中（含近身、突进和弹体）"
    if mid in {"thunder", "rockslide", "blizzard", "stoneedge", "iciclecrash", "dracometeor"}:
        return True, "从天而降／落点区域例外"
    if mid in {"watergun", "ember", "bubble", "thundershock"}:
        return False, "点名小型招例外（水枪实装为细流beam，仍可跳躲）"
    if mid in {"surf", "hydropump", "waterspout"}:
        return True, "大型水浪例外（不按弹体／突进外观误判）"
    if mid in {"earthquake", "bulldoze", "earthpower"} or (
        move["type"] == 5 and kind in {"nova", "zone"}
    ):
        return False, "地面冲击／从脚下传播"
    if mid in {"fireblast", "poisongas"}:
        return True, "点名大型飞行弹／气团例外"
    if kind in {"shot", "fan"}:
        if move["damage"] >= 21:
            return True, "大型飞行弹（damage ≥ 21），可命中空中"
        return False, "小型飞行道具（damage ≤ 20），可跳躲"
    if kind in {"melee", "spin"}:
        return False, "近身招"
    if kind == "rush":
        return False, "突进撞击"
    if kind == "beam":
        return True, "大型光束"
    if kind in {"nova", "zone"}:
        return True, "非地面系立体范围／落点区域"
    return False, "辅助／无伤动作，不命中目标"


def apply(moves, generated, types, output, revisions=None):
    """Write exactly 121 data rows (no header), without changing combat numbers."""
    rows = []
    for mid, move in moves.items():
        actual = {**move, **generated.get(mid, {}).get("runtime", {}),
                  **(revisions or {}).get(mid, {})}
        hits, reason = classify(actual)
        move["hitsAirborne"] = hits
        rows.append("\t".join([mid, move["name"], actual["kind"], types[move["type"]][0],
                               str(hits).lower(), reason, str(actual["damage"])]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + "\n")
