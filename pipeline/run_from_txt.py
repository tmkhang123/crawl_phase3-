from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
DEFAULT_BRANDS_FILE = PIPELINE_DIR / "brands_to_crawl.txt"


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


def clean_brand_line(line: str) -> str:
    # Allow comments after a brand name, for example: KFC # high priority
    return line.split("#", 1)[0].strip()


def read_brands_file(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Brands file not found: {path}")

    brands: list[str] = []
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for line in lines:
        brand = clean_brand_line(line)
        if brand:
            brands.append(brand)

    if not brands:
        raise SystemExit(f"No brands found in {path}. Add one brand per line.")
    return brands


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read brand names from txt and run pipeline crawl.")
    parser.add_argument("--brands-file", type=Path, default=DEFAULT_BRANDS_FILE)
    parser.add_argument(
        "--mode",
        choices=("discovery", "normal", "proxy"),
        default="discovery",
        help="discovery = national-lite discovery then build crawl_plan; normal/proxy = direct grid crawl for listed brands.",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--concurrency", type=int, default=0)
    parser.add_argument("--sample-regions", type=int, default=0)
    parser.add_argument("--grid-cities", default="")
    parser.add_argument("--proxy-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def mask_proxy(command: list[str]) -> list[str]:
    masked: list[str] = []
    skip_next = False

    for item in command:
        if skip_next:
            masked.append("***")
            skip_next = False
            continue
        masked.append(item)
        if item == "--proxy-url":
            skip_next = True

    return masked


def build_command(args: argparse.Namespace, chains: str) -> list[str]:
    if args.mode == "discovery":
        command = [
            sys.executable,
            str(PIPELINE_DIR / "run_discovery.py"),
            "--chains",
            chains,
        ]
        if args.output is not None:
            command.extend(["--output", str(args.output)])
        if args.concurrency:
            command.extend(["--concurrency", str(args.concurrency)])
        if args.proxy_url.strip():
            command.extend(["--proxy-url", args.proxy_url.strip()])
        if args.dry_run:
            command.append("--dry-run")
        return command

    script = "run_crawl_normal.py"
    if args.mode == "proxy":
        script = "run_crawl_proxy.py"

    command = [
        sys.executable,
        str(PIPELINE_DIR / script),
        "--chains",
        chains,
    ]
    if args.output is not None:
        command.extend(["--output", str(args.output)])
    if args.concurrency:
        command.extend(["--concurrency", str(args.concurrency)])
    if args.sample_regions:
        command.extend(["--sample-regions", str(args.sample_regions)])
    if args.grid_cities.strip():
        command.extend(["--grid-cities", args.grid_cities.strip()])
    if args.mode == "proxy" and args.proxy_url.strip():
        command.extend(["--proxy-url", args.proxy_url.strip()])
    if args.dry_run:
        command.append("--dry-run")

    return command


def main() -> int:
    args = parse_args()
    load_env_file(PROJECT_ROOT / ".env")

    brands = read_brands_file(args.brands_file)
    chains = ",".join(brands)
    command = build_command(args, chains)

    print(f"brands_file={args.brands_file}")
    print(f"brand_count={len(brands)}")
    print(",".join(brands))
    print("command=" + subprocess.list2cmdline(mask_proxy(command)))

    return subprocess.call(command, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
