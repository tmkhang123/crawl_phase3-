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

    # Read simple KEY=VALUE pairs. Existing environment variables win.
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_proxy_url(cli_proxy_url: str) -> str:
    if cli_proxy_url.strip():
        return cli_proxy_url.strip()
    return os.environ.get("GMAPS_PROXY_URL", "").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl brands with rotating proxy.")
    parser.add_argument("--chains", default="WinMart")
    parser.add_argument("--output", type=Path, default=PIPELINE_DIR / "output" / "crawl_proxy")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--sample-regions", type=int, default=0)
    parser.add_argument("--grid-cities", default="")
    parser.add_argument("--proxy-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(PROJECT_ROOT / ".env")
    proxy_url = resolve_proxy_url(args.proxy_url)
    if not proxy_url:
        print("missing_proxy_url=1 set GMAPS_PROXY_URL in .env or pass --proxy-url")
        return 2

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
        "--proxy-url",
        proxy_url,
    ]
    if args.sample_regions:
        command.extend(["--sample-regions", str(args.sample_regions)])
    if args.grid_cities:
        command.extend(["--grid-cities", args.grid_cities])
    if args.dry_run:
        command.append("--dry-run")

    # Do not print the proxy URL; it may contain credentials.
    safe_command = []
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
