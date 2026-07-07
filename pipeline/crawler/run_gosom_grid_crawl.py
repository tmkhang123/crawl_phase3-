from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
RUN_GOSOM = PIPELINE_DIR / "crawler" / "run_gosom_crawl.py"
DEFAULT_OUTPUT = PIPELINE_DIR / "output" / "gosom_grid_crawl"
DEFAULT_GRID_CITIES = (
    "hcm,hn,danang,haiphong,cantho,binh_duong,dong_nai,"
    "bac_ninh,hung_yen,hai_duong,quang_ninh,thanh_hoa,nghe_an,hue,"
    "khanh_hoa,lam_dong,binh_dinh,ba_ria_vung_tau,long_an,tien_giang,an_giang"
)


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def mask_command_for_log(command: list[str]) -> list[str]:
    masked = []
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


def run_command(command: list[str], dry_run: bool) -> int:
    print("command=" + subprocess.list2cmdline(mask_command_for_log(command)))
    if dry_run:
        return 0
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Gosom grid runner for crawling brands in large/dense Vietnamese markets. Uses grid fast-mode only."
        )
    )
    parser.add_argument("--chains", required=True, help='Comma-separated brands, e.g. "WinMart+,WinMart,KFC".')
    parser.add_argument(
        "--grid-chains",
        default="",
        help="Comma-separated brands to run dense grid. Default: same as --chains.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--grid-cities", default=DEFAULT_GRID_CITIES)
    parser.add_argument("--sample-regions", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--proxy-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python = sys.executable
    chains = ",".join(split_csv(args.chains))
    grid_chains = ",".join(split_csv(args.grid_chains or args.chains))
    output = args.output

    command = [
        python,
        str(RUN_GOSOM),
        "--chains",
        grid_chains,
        "--region-mode",
        "grid",
        "--cities",
        args.grid_cities,
        "--output",
        str(output / "grid"),
        "--concurrency",
        str(args.concurrency),
        "--depth",
        str(args.depth),
    ]
    if args.sample_regions:
        command.extend(["--sample-regions", str(args.sample_regions)])
    if args.proxy_url:
        command.extend(["--proxy-url", args.proxy_url])
    code = run_command(command, args.dry_run)
    if code != 0:
        return code

    print(f"done output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
