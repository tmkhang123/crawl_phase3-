from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from crawler.crawl_policy import PIPELINE_DIR, PROJECT_ROOT, read_csv_rows, split_csv_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run gosom crawl from a discovery-generated crawl plan.")
    parser.add_argument("--plan", type=Path, default=PIPELINE_DIR / "output" / "discovery" / "crawl_plan.csv")
    parser.add_argument("--output", type=Path, default=PIPELINE_DIR / "output" / "crawl_by_policy")
    parser.add_argument("--chains", default="", help="Optional comma-separated brand names to run from the plan.")
    parser.add_argument("--routes", default="", help="Optional comma-separated routes, e.g. grid_dense,grid_large.")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--proxy-url", default="")
    parser.add_argument("--limit-brands", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def mask_command(command: list[str]) -> list[str]:
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


def wanted_brand_names(chains_text: str) -> set[str]:
    wanted: set[str] = set()
    for chain in split_csv_text(chains_text):
        wanted.add(chain.lower())
    return wanted


def select_plan_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    rows = read_csv_rows(args.plan)
    wanted_chains = wanted_brand_names(args.chains)
    wanted_routes = set(split_csv_text(args.routes))
    selected: list[dict[str, str]] = []

    for row in rows:
        brand_name = row.get("brand_name", "").strip()
        route = row.get("route", "").strip()

        if wanted_chains and brand_name.lower() not in wanted_chains:
            continue
        if wanted_routes and route not in wanted_routes:
            continue

        selected.append(row)
        if args.limit_brands and len(selected) >= args.limit_brands:
            break

    return selected


def build_command(args: argparse.Namespace, row: dict[str, str]) -> list[str]:
    brand_name = row.get("brand_name", "").strip()
    region_mode = row.get("region_mode", "center").strip() or "center"
    crawl_cities = row.get("crawl_cities", "hcm,hn,danang").strip()
    route = row.get("route", region_mode).strip() or region_mode
    sample_regions = row.get("sample_regions", "0").strip()

    command = [
        sys.executable,
        str(PIPELINE_DIR / "crawler" / "run_gosom_crawl.py"),
        "--chains",
        brand_name,
        "--region-mode",
        region_mode,
        "--cities",
        crawl_cities,
        "--output",
        str(args.output / route),
        "--concurrency",
        str(args.concurrency),
        "--depth",
        str(args.depth),
    ]

    if sample_regions and sample_regions != "0":
        command.extend(["--sample-regions", sample_regions])
    if args.proxy_url.strip():
        command.extend(["--proxy-url", args.proxy_url.strip()])
    if args.dry_run:
        command.append("--dry-run")

    return command


def main() -> int:
    args = parse_args()
    rows = select_plan_rows(args)

    if not rows:
        print(f"no_plan_rows_selected plan={args.plan}")
        return 1

    print(f"selected_brands={len(rows)} output={args.output}")
    for row in rows:
        brand_name = row.get("brand_name", "")
        route = row.get("route", "")
        cities = row.get("crawl_cities", "")
        print(f"plan brand={brand_name} route={route} cities={cities}")

        command = build_command(args, row)
        print("command=" + subprocess.list2cmdline(mask_command(command)))
        code = subprocess.call(command, cwd=PROJECT_ROOT)
        if code != 0:
            return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
