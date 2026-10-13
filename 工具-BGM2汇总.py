"""Verify unchanged candidate and combine 24 full-run suites with unchanged retry suites.

No browser is launched here. Preserve the initial bootstrap-error log; do not count a
missing report as a pass. Hand-feel and music must have genuinely passed after retry.
"""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "验收记录/集成批次/BGM2-final"
STAGE = ROOT / "验收记录/战斗音乐"


def load(path):
    return json.loads(path.read_text())


def main():
    performance = load(ROOT / "验收记录/丰缘全图/性能对比.json")
    candidate_sha = hashlib.sha256((ROOT / "候选试玩.html").read_bytes()).hexdigest()
    assert candidate_sha == performance["runs"][1]["candidateSHA256"]
    summary = load(STAGE / "BGM2-首次汇总.json")
    assert len(summary) == 24
    assert all(s["exitCode"] == s["failed"] == s["jsErrors"] == 0 for s in summary)
    for name, path, log in [
        ("手感", ROOT / "验收记录/手感/浏览器验收.json", ROOT / "BGM2-手感补验.log"),
        ("战斗音乐", STAGE / "report.json", ROOT / "BGM2-音乐验收.log"),
    ]:
        report = load(path)
        assert report["failed"] == report["jsErrors"] == 0 and not report.get("failure")
        assert not report.get("errors")
        assert log.stat().st_mtime > (STAGE / "BGM2-首次汇总.json").stat().st_mtime
        shutil.copy2(path, OUT / f"{name}.json")
        shutil.copy2(log, OUT / f"{name}.log")
        summary.append({"test": name, "exitCode": 0, "passed": report["passed"],
                        "failed": 0, "jsErrors": 0})
        print(name + " " + json.dumps({k: report[k] for k in ["passed", "failed", "jsErrors"]}))
    previous = load(ROOT / "验收记录/集成批次/BGM-final/summary.json")
    old = {s["test"]: s["passed"] for s in previous if s["test"] != "战斗音乐"}
    current = {s["test"]: s["passed"] for s in summary if s["test"] != "战斗音乐"}
    assert old == current and sum(current.values()) == 67876
    old_checks = load(ROOT / "验收记录/集成批次/BGM-final/战斗音乐.json")["checks"]
    new_checks = load(STAGE / "report.json")["checks"]
    assert len(old_checks) == 86
    assert {c["name"] for c in old_checks} <= {c["name"] for c in new_checks}
    total = {"suites": len(summary), "passed": sum(s["passed"] for s in summary),
             "failed": sum(s["failed"] for s in summary),
             "jsErrors": sum(s["jsErrors"] for s in summary)}
    assert total["suites"] == 26 and total["failed"] == total["jsErrors"] == 0
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "补验核验.json").write_text(json.dumps({
        "candidateSHA256": candidate_sha, "retainedMusicChecks": 86, "total": total,
        "initialBootstrapErrorLog": str(STAGE / "BGM2-首次全量加载异常.log"),
        "retrySuites": ["手感", "战斗音乐"], "oldSuiteCountsUnchanged": True,
    }, ensure_ascii=False, indent=2) + "\n")
    print("TOTAL " + json.dumps(total))


if __name__ == "__main__":
    main()
