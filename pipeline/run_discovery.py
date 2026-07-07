from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from crawler.crawl_policy import (
    PIPELINE_DIR,
    PROJECT_ROOT,
    PLAN_FIELDS,
    SUMMARY_FIELDS,
    build_crawl_plan,
    summarize_discovery_output,
    write_csv_rows,
)


DEFAULT_DISCOVERY_CITIES = (
    "hcm,hn,danang,haiphong,cantho,binh_duong,dong_nai,"
    "bac_ninh,quang_ninh,hue,khanh_hoa,lam_dong,long_an,an_giang"
)
DEFAULT_DISTRICTS = PIPELINE_DIR / "config" / "regions" / "districts.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run light gosom discovery, then build a reusable crawl policy plan."
    )
    parser.add_argument("--chains", default="", help='Optional comma-separated brands. Empty = phase2 registry.')
    parser.add_argument(
        "--coverage-mode",
        choices=("national-lite", "center"),
        default="national-lite",
        help="national-lite = about 3 district/province queries per province; center = old city-center discovery.",
    )
    parser.add_argument("--cities", default=DEFAULT_DISCOVERY_CITIES)
    parser.add_argument("--districts", type=Path, default=DEFAULT_DISTRICTS)
    parser.add_argument("--output", type=Path, default=PIPELINE_DIR / "output" / "discovery")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--proxy-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def province_from_label(label: str) -> str:
    if "," not in label:
        return label.strip()
    return label.split(",")[-1].strip()


def pick_three_labels(labels: list[str]) -> list[str]:
    if len(labels) <= 3:
        return labels

    # Pick first/middle/last district labels so each province gets broad but light coverage.
    indexes = [0, len(labels) // 2, len(labels) - 1]
    picked: list[str] = []
    seen: set[int] = set()

    for index in indexes:
        if index in seen:
            continue
        picked.append(labels[index])
        seen.add(index)

    return picked


def build_national_lite_district_file(source_file: Path, output_file: Path) -> Path:
    all_labels = json.loads(source_file.read_text(encoding="utf-8-sig"))
    labels_by_province: dict[str, list[str]] = {}

    for label in all_labels:
        province = province_from_label(label)
        if province not in labels_by_province:
            labels_by_province[province] = []
        labels_by_province[province].append(label)

    selected_labels: list[str] = []
    for province in sorted(labels_by_province):
        labels = pick_three_labels(labels_by_province[province])
        for label in labels:
            selected_labels.append(label)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(selected_labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"national_lite_provinces={len(labels_by_province)} national_lite_regions={len(selected_labels)}")
    return output_file


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


def run_discovery_crawl(args: argparse.Namespace) -> int:
    discovery_output = args.output / args.coverage_mode.replace("-", "_")
    command = [
        sys.executable,
        str(PIPELINE_DIR / "crawler" / "run_gosom_crawl.py"),
        "--output",
        str(discovery_output),
        "--concurrency",
        str(args.concurrency),
        "--depth",
        str(args.depth),
    ]
    if args.coverage_mode == "national-lite":
        national_lite_file = args.output / "national_lite_3point_districts.json"
        build_national_lite_district_file(args.districts, national_lite_file)
        command.extend(["--region-mode", "district", "--districts", str(national_lite_file)])
    else:
        command.extend(["--region-mode", "center", "--cities", args.cities])

    if args.chains.strip():
        command.extend(["--chains", args.chains.strip()])
    if args.proxy_url.strip():
        command.extend(["--proxy-url", args.proxy_url.strip()])
    if args.dry_run:
        command.append("--dry-run")

    print("command=" + subprocess.list2cmdline(mask_command(command)))
    return subprocess.call(command, cwd=PROJECT_ROOT)


def build_outputs(args: argparse.Namespace) -> None:
    discovery_output = args.output / args.coverage_mode.replace("-", "_")
    clean_by_brand = PIPELINE_DIR / "output" / "rule_based_with_crawled_data" / "by_brand"

    summary_rows = summarize_discovery_output(discovery_output, clean_by_brand)
    plan_rows = build_crawl_plan(summary_rows)

    write_csv_rows(args.output / "discovery_summary.csv", SUMMARY_FIELDS, summary_rows)
    write_csv_rows(args.output / "crawl_plan.csv", PLAN_FIELDS, plan_rows)

    print("discovery_summary=", args.output / "discovery_summary.csv")
    print("crawl_plan=", args.output / "crawl_plan.csv")
    print("brands_planned=", len(plan_rows))


def main() -> int:
    args = parse_args()
    code = run_discovery_crawl(args)
    if code != 0:
        return code

    if not args.dry_run:
        build_outputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
