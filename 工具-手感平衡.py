"""Re-run T9's exact full plan on archived M4 and live H1, serially."""
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/手感"
T9 = ROOT.parent / "T9/验收记录/平衡"
ENV = {**os.environ, "POIGHT_TEST_URL": os.environ.get("POIGHT_TEST_URL", "http://localhost:8868/")}


def run(args, log):
    with log.open("w") as stream:
        subprocess.run([sys.executable, *args], cwd=ROOT, env=ENV,
                       stdout=stream, stderr=subprocess.STDOUT, check=True)


def main():
    for label, archived in [("M4", True), ("H1", False)]:
        folder = OUT / (label + "平衡")
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(T9 / "全量计划.json", folder / "全量计划.json")
        # Legacy report has a separate historical HP calibration section. These
        # inputs are explicitly labelled as T9 history, not new H1 calibration.
        for source in T9.glob("时长-*.jsonl"):
            shutil.copy2(source, folder / source.name)
        args = ["工具-平衡模拟.py", "--plan", str(folder / "全量计划.json"),
                "--out", str(folder / "全量对局-完整.jsonl"),
                "--catalog", str(folder / "catalog.json")]
        if archived:
            args += ["--html", str(OUT / "M4-baseline.html")]
        print(label + " full plan started", flush=True)
        run(args, folder / "模拟.log")
        run(["工具-平衡报告.py", "--out-dir", str(folder)], folder / "报告.log")
        report = folder / "平衡报告.md"
        note = (f"> {label} 全员结果为本次真实引擎重跑；共7350局，T9原计划/种子/换边/档位/HP×6原样。\n"
                "> 下方旧T9模板的HP校准、候选建议、验收静态文字仅为历史；"
                "不代表H1结论。本次结果读第3–5节、TSV和汇总收据。\n\n")
        report.write_text(note + report.read_text())
        print(label + " full plan finished: " + (folder / "报告.log").read_text(), flush=True)
    data = {}
    for label in ["M4", "H1"]:
        with (OUT / (label + "平衡") / "各物种总胜率.tsv").open() as stream:
            data[label] = {int(row["id"]): row for row in csv.DictReader(stream, delimiter="\t")}
    lines = ["# H1 全员平衡与冷却校准", "", "基线M4：f64982be201b70212a8a6b3e0ff5fad6618f6cad。",
             "两版均按T9全量计划：1225对×6局，换边各3局，great，HP×6，600秒截尾，原种子；各7350局。",
             "仅报告，不逐只调整。胜率=胜局/全部294局，平局和超时不算胜。", "",
             "## 指定对局冷却系数", "", "|系数|20局中位数(s)|25–40s|", "|---:|---:|---|"]
    for path in sorted(OUT.glob("cd-*.jsonl")):
        values = [json.loads(line)["seconds"] for line in path.read_text().splitlines()]
        value = median(values)
        lines.append(f"|{path.stem[3:]}|{value:.6f}|{'通过' if 25<=value<=40 else '未达标'}|")
    lines += ["", "原始逐局输出保留在cd-*.jsonl，未改伤害/体力/AI/HP；最终保留初值0.4。",
              "仅有限系数采样，不声称证明整个实数区间无解。", "",
              "## H1最高与最低各5只", "", "|组|物种|M4胜率|H1胜率|变化(百分点)|", "|---|---|---:|---:|---:|"]
    ordered = sorted(data["H1"], key=lambda n: -float(data["H1"][n]["win_percent"]))
    for group, ids in [("最高", ordered[:5]), ("最低", list(reversed(ordered[-5:])) )]:
        for n in ids:
            old, new = data["M4"][n], data["H1"][n]
            delta = float(new["win_percent"])-float(old["win_percent"])
            lines.append(f"|{group}|{new['name']} #{n}|{old['win_percent']}%|{new['win_percent']}%|{delta:+.4f}|")
    lines += ["", "## 原样工具输出", "", "```text"]
    for label in ["M4", "H1"]:
        lines.append(label + ": " + (OUT / (label + "平衡") / "报告.log").read_text().strip())
    lines += ["```", ""]
    (OUT / "平衡对比.md").write_text("\n".join(lines))
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
