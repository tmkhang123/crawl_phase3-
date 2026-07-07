from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run policy-based crawl without proxy.")
    parser.add_argument("--plan", type=Path, default=PIPELINE_DIR / "output" / "discovery" / "crawl_plan.csv")
    parser.add_argument("--output", type=Path, default=PIPELINE_DIR / "output" / "crawl_by_policy_normal")
    parser.add_argument("--chains", default="")
    parser.add_argument("--routes", default="")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--limit-brands", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = [
        sys.executable,
        str(PIPELINE_DIR / "run_crawl_from_plan.py"),
        "--plan",
        str(args.plan),
        "--output",
        str(args.output),
        "--concurrency",
        str(args.concurrency),
        "--depth",
        str(args.depth),
    ]

    if args.chains.strip():
        command.extend(["--chains", args.chains.strip()])
    if args.routes.strip():
        command.extend(["--routes", args.routes.strip()])
    if args.limit_brands:
        command.extend(["--limit-brands", str(args.limit_brands)])
    if args.dry_run:
        command.append("--dry-run")

    print(" ".join(command))
    return subprocess.call(command, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
