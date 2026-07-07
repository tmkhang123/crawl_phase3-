from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run policy-based crawl with rotating proxy.")
    parser.add_argument("--plan", type=Path, default=PIPELINE_DIR / "output" / "discovery" / "crawl_plan.csv")
    parser.add_argument("--output", type=Path, default=PIPELINE_DIR / "output" / "crawl_by_policy_proxy")
    parser.add_argument("--chains", default="")
    parser.add_argument("--routes", default="")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--limit-brands", type=int, default=0)
    parser.add_argument("--proxy-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(PROJECT_ROOT / ".env")
    proxy_url = args.proxy_url.strip() or os.environ.get("GMAPS_PROXY_URL", "").strip()

    if not proxy_url:
        print("missing_proxy_url=1 set GMAPS_PROXY_URL in .env or pass --proxy-url")
        return 2

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
        "--proxy-url",
        proxy_url,
    ]

    if args.chains.strip():
        command.extend(["--chains", args.chains.strip()])
    if args.routes.strip():
        command.extend(["--routes", args.routes.strip()])
    if args.limit_brands:
        command.extend(["--limit-brands", str(args.limit_brands)])
    if args.dry_run:
        command.append("--dry-run")

    safe_command: list[str] = []
    skip_next = False
    for item in command:
        if skip_next:
            safe_command.append("***")
            skip_next = False
            continue
        safe_command.append(item)
        if item == "--proxy-url":
            skip_next = True

    print(" ".join(safe_command))
    return subprocess.call(command, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
