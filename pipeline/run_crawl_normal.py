from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl brands without proxy.")
    parser.add_argument("--chains", default="WinMart")
    parser.add_argument("--output", type=Path, default=PIPELINE_DIR / "output" / "crawl_normal")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--sample-regions", type=int, default=0)
    parser.add_argument("--grid-cities", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = [
        sys.executable,
        str(PIPELINE_DIR / "crawler" / "run_gosom_grid_crawl.py"),
        "--chains",
        args.chains,
        "--output",
        str(args.output),
        "--concurrency",
        str(args.concurrency),
        "--depth",
        str(args.depth),
    ]
    if args.sample_regions:
        command.extend(["--sample-regions", str(args.sample_regions)])
    if args.grid_cities:
        command.extend(["--grid-cities", args.grid_cities])
    if args.dry_run:
        command.append("--dry-run")
    print(" ".join(command))
    return subprocess.call(command, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
