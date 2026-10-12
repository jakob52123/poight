"""Run the actual browser engine at fixed 120 Hz, without rendering between ticks.

Single pair: --a 25 --b 6 --tier poke --n 5 --seed 1
Batch: --plan plan.json --out results.jsonl (plan is a list of the same options).
Seeds increment modulo 2**32 per game. JSONL stdout contains no wall-clock timings.
Timeouts remain explicitly censored, never awarded by remaining HP.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
URL = os.environ.get("POIGHT_TEST_URL", "http://localhost:8829/").rstrip("/")


def ready(page):
    deadline = time.monotonic() + 60
    while not page.evaluate("window.__waterTest?.snapshot().artReady"):
        if time.monotonic() > deadline:
            raise TimeoutError("artReady")
        time.sleep(0.025)


def simulate(page, catalog, job):
    roster = {c["id"]: c for c in catalog["roster"]}
    a, b = int(job["a"]), int(job["b"])
    tier = job.get("tier", "poke")
    profile = page.evaluate("window.__waterTest.snapshot().profile")
    profile.update(player=a, enemy=b, playerMoves=roster[a]["defaultMoves"],
                   enemyMoves=roster[b]["defaultMoves"], tier=tier,
                   map=job.get("map", "emerald-rustborocity"))
    if not page.evaluate("v => window.__waterTest.select(v)", profile):
        raise RuntimeError(f"select failed: {a}/{b}")
    for i in range(int(job.get("n", 1))):
        opts = {"seed": (int(job.get("seed", 1)) + i) % 2**32,
                "tier": tier, "playerTier": job.get("playerTier", tier),
                "maxSeconds": job.get("maxSeconds", 600)}
        if job.get("hpMultiplier") is not None:
            opts["hpMultiplier"] = job["hpMultiplier"]
        result = page.evaluate("v => window.__waterTest.simulate(v)", opts)
        if "label" in job:
            result["label"] = job["label"]
        yield result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", type=int, default=25)
    parser.add_argument("--b", type=int, default=6)
    parser.add_argument("--tier", choices=["poke", "great", "ultra", "master"], default="poke")
    parser.add_argument("--player-tier", dest="playerTier")
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-seconds", dest="maxSeconds", type=float, default=600)
    parser.add_argument("--hp-multiplier", dest="hpMultiplier", type=float)
    parser.add_argument("--map", default="emerald-rustborocity")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--html", type=Path, help="Archived engine HTML; assets use the preview origin")
    args = parser.parse_args()
    jobs = json.loads(args.plan.read_text()) if args.plan else [
        {k: v for k, v in vars(args).items() if v is not None}
    ]
    if any(int(j.get("n", 1)) < 1 for j in jobs):
        parser.error("n must be positive")
    errors = []
    output = sys.stdout
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        output = args.out.open("w")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda e: errors.append(str(e)))
            if args.html:
                page.route(URL + "/?test=1", lambda route: route.fulfill(
                    body=args.html.read_bytes(), content_type="text/html; charset=utf-8",
                    headers={"Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'"}))
            page.goto(URL + "/?test=1")
            ready(page)
            catalog = page.evaluate("window.__waterTest.catalog()")
            if args.catalog:
                args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
            for job in jobs:
                for result in simulate(page, catalog, job):
                    output.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                    output.flush()
                if errors:
                    raise RuntimeError(errors)
            browser.close()
    finally:
        if output is not sys.stdout:
            output.close()
    if errors:
        raise RuntimeError(errors)


if __name__ == "__main__":
    main()
