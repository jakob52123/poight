"""Stage unchanged historical inputs omitted by the shared remote sync, then run acceptance.

Local: python scripts/D1-远程验收.py --pack
Jade (shared wrapper only): python scripts/D1-远程验收.py D1-final <extra suites>
No browser runs in --pack mode. All extracted paths stay inside this task repository.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "D1-远程夹具.tar.gz"
FROZEN = Path("验收记录/丰缘全图/M-fd1eb0f")
T5 = Path("验收记录/D1-远程夹具/T5")


def pack():
    paths = [
        "验收记录/体型与移速-修改前/收据.json",
        "验收记录/体型与移速-修改前/候选发布清单.json",
        "验收记录/绿宝石-接入前/收据.json",
        "验收记录/绿宝石-接入前/候选发布清单.json",
        "验收记录/平衡/汇总收据.json",
        "验收记录/手感/M4-baseline.html",
    ]
    files = {Path(p): ROOT / p for p in paths}
    # Arena acceptance rebuilds candidate variants and must retain node --check.
    # Bundle the local standalone arm64 executable, never install a global tool.
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Local node is required to pack dynamic-build acceptance")
    files[Path("D1-远程bin/node")] = Path(node).resolve()
    for path in ("候选试玩.html", "候选发布清单.json", "素材/绿宝石场景/场景目录.json"):
        files[FROZEN / path] = ROOT / FROZEN / path
    manifest = json.loads((ROOT / FROZEN / "候选发布清单.json").read_text())
    for path in manifest["assets"]:
        files[FROZEN / path] = ROOT / FROZEN / path
    record_path = Path("招式特效/生图重做/实景预览/构建记录.json")
    record = json.loads((ROOT / record_path).read_text())["assets"]
    mids = ("thunderbolt", "quickattack", "irontail", "thunder", "flamethrower",
            "fireblast", "dragonclaw", "airslash", "stoneedge")
    for mid in mids:
        relative = (Path("招式特效/主角八招") / mid / (mid + "-动画.png")
                    if mid in ("thunderbolt", "thunder") else Path(record[mid]["output"]))
        files[T5 / relative] = ROOT.parent / "T5" / relative
    for relative in (record_path, Path("招式特效/实战打包记录.json")):
        files[T5 / relative] = ROOT.parent / "T5" / relative
    # Integration guards every original raster, not just the nine protected
    # atlases. Preserve the complete original byte comparison and file count.
    for folder in ("素材", "画面"):
        for source in (ROOT.parent / "T5" / folder).rglob("*"):
            if source.is_file() and source.suffix.lower() in (".png", ".jpg", ".gif", ".webp"):
                files[T5 / source.relative_to(ROOT.parent / "T5")] = source
    hashes = {str(dst): hashlib.sha256(src.read_bytes()).hexdigest()
              for dst, src in files.items()}
    with tarfile.open(ARCHIVE, "w:gz") as archive:
        for dst, src in files.items():
            archive.add(src, arcname=str(dst), recursive=False)
    (ROOT / "D1-远程夹具-sha256.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2) + "\n")
    print(f"Packed {len(files)} unchanged historical inputs: {ARCHIVE}")


def run():
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(ROOT, filter="data")
    hashes = json.loads((ROOT / "D1-远程夹具-sha256.json").read_text())
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha
               for path, sha in hashes.items())
    print(f"Verified {len(hashes)} unchanged historical inputs", flush=True)
    env = {**os.environ, "POIGHT_T5_BASELINE": str(ROOT / T5),
           "PATH": str(ROOT / "D1-远程bin") + os.pathsep + os.environ["PATH"],
           "POIGHT_BENCH_REPLAY": "1", "POIGHT_SUITE_TIMEOUT": "1800"}
    subprocess.run([sys.executable, "验收-丰缘性能.py"], cwd=ROOT, env=env,
                   timeout=1800, check=True)
    result = subprocess.run([sys.executable, "验收记录/集成批次/run.py", *sys.argv[1:]],
                            cwd=ROOT, env=env, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    if sys.argv[1:] == ["--pack"]:
        pack()
    else:
        run()
