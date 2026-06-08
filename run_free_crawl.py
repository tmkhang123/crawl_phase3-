from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parent
CRAWLER = KIT_ROOT / "gmaps_chainlock_crawler.py"
DEFAULT_REGISTRY = KIT_ROOT / "brand_registry.csv"
DEFAULT_BRANDS_FILE = KIT_ROOT / "brands_to_crawl.txt"
DEFAULT_REGIONS = KIT_ROOT / "districts.json"
DEFAULT_OUTPUT = KIT_ROOT / "output"


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


REGISTRY_FIELDS = [
    "target_chain",
    "search_query",
    "name_aliases",
    "name_blacklist",
    "expected_count",
    "concurrency",
    "priority",
    "notes",
]


def clean_brand_line(line: str) -> str:
    return line.split("#", 1)[0].strip()


def read_brands_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    brands = [clean_brand_line(line) for line in path.read_text(encoding="utf-8-sig").splitlines()]
    return [brand for brand in brands if brand]


def write_simple_registry(path: Path, brands: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, brand in enumerate(brands, start=1):
        rows.append(
            {
                "target_chain": brand,
                "search_query": brand,
                "name_aliases": brand,
                "name_blacklist": "",
                "expected_count": "",
                "concurrency": "1",
                "priority": str(index),
                "notes": "Generated from brands_to_crawl.txt",
            }
        )
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def read_registry(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [(row.get("target_chain") or "").strip() for row in csv.DictReader(f) if row.get("target_chain")]


def select_chains(registry: Path, args: argparse.Namespace) -> list[str]:
    chains = read_registry(registry)
    if args.chains:
        wanted = [item.strip() for item in args.chains.split(",") if item.strip()]
        lookup = {chain.lower(): chain for chain in chains}
        missing = [chain for chain in wanted if chain.lower() not in lookup]
        if missing:
            raise SystemExit(f"Chains not found in registry: {', '.join(missing)}")
        chains = [lookup[chain.lower()] for chain in wanted]
    if args.start_at:
        target = args.start_at.strip().lower()
        for idx, chain in enumerate(chains):
            if chain.lower() == target:
                chains = chains[idx:]
                break
        else:
            raise SystemExit(f"--start-at not found: {args.start_at}")
    if args.limit_brands:
        chains = chains[: args.limit_brands]
    return chains


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone Google Maps crawl runner.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--brands-file", type=Path, default=DEFAULT_BRANDS_FILE)
    parser.add_argument("--regions", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chains", default="", help="Advanced: comma-separated chain names from brand_registry.csv.")
    parser.add_argument("--start-at", default="", help="Start from a chain name in the selected list.")
    parser.add_argument("--limit-brands", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--chain-parallelism", type=int, default=1)
    parser.add_argument("--limit-regions", type=int, default=0)
    parser.add_argument("--sample-regions", type=int, default=0)
    parser.add_argument("--sample-seed", type=int, default=20260607)
    parser.add_argument("--goto-timeout", type=int, default=45000)
    parser.add_argument("--feed-timeout", type=int, default=12000)
    parser.add_argument("--detail-timeout", type=int, default=20000)
    parser.add_argument("--region-hard-timeout", type=float, default=240.0)
    parser.add_argument("--min-delay", type=float, default=3.0)
    parser.add_argument("--max-delay", type=float, default=6.0)
    parser.add_argument("--detail-min-delay", type=float, default=1.5)
    parser.add_argument("--detail-max-delay", type=float, default=3.0)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    configure_console()
    args = parse_args()
    brands_from_file = read_brands_file(args.brands_file)
    if args.brands_file.exists() and not args.chains:
        write_simple_registry(args.registry, brands_from_file)
    chains = select_chains(args.registry, args)
    if not chains:
        raise SystemExit("No chains selected. Add brand names to brands_to_crawl.txt.")

    cmd = [
        sys.executable,
        str(CRAWLER),
        "--registry",
        str(args.registry),
        "--chains",
        ",".join(chains),
        "--regions",
        str(args.regions),
        "--output",
        str(args.output),
        "--chain-parallelism",
        str(args.chain_parallelism),
        "--concurrency",
        str(args.concurrency),
        "--goto-timeout",
        str(args.goto_timeout),
        "--feed-timeout",
        str(args.feed_timeout),
        "--detail-timeout",
        str(args.detail_timeout),
        "--region-hard-timeout",
        str(args.region_hard_timeout),
        "--min-delay",
        str(args.min_delay),
        "--max-delay",
        str(args.max_delay),
        "--detail-min-delay",
        str(args.detail_min_delay),
        "--detail-max-delay",
        str(args.detail_max_delay),
    ]
    if args.limit_regions:
        cmd.extend(["--limit-regions", str(args.limit_regions)])
    if args.sample_regions:
        cmd.extend(["--sample-regions", str(args.sample_regions), "--sample-seed", str(args.sample_seed)])
    if not args.no_shuffle:
        cmd.append("--shuffle")
    if args.visible:
        cmd.append("--no-headless")

    print(f"free_crawl_chains={len(chains)} output={args.output}", flush=True)
    print(",".join(chains), flush=True)
    print(" ".join(cmd), flush=True)
    if args.dry_run:
        return
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(subprocess.call(cmd, cwd=KIT_ROOT, env=env))


if __name__ == "__main__":
    main()
