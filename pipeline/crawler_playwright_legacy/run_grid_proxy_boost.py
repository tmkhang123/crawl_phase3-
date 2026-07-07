from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
sys.path.insert(0, str(PIPELINE_DIR / "crawler"))

from build_grid_regions import DEFAULT_CITIES, DEFAULT_OUTPUT as DEFAULT_GRID, generate_regions
import json


CRAWLER = PIPELINE_DIR / "crawler_playwright_legacy" / "raw_gmaps_chainlock_dedup.py"
REGISTRY = PIPELINE_DIR / "config" / "brand_registry_phase1.csv"
OUTPUT = PIPELINE_DIR / "output" / "grid_proxy_boost"
SEED_SEEN_DIR = PIPELINE_DIR / "output" / "rule_based_with_gosom_winmart" / "by_brand"


DEFAULT_CHAINS = "WinMart+,WinMart"


def write_grid(path: Path, cities: list[str], cell_km: float, zoom: float) -> int:
    regions = generate_regions(cities, cell_km, zoom)
    payload = {
        "kind": "gmaps_grid_regions_v1",
        "cell_km": cell_km,
        "zoom": zoom,
        "cities": cities,
        "region_count": len(regions),
        "regions": regions,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(regions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runner for proxy-backed Google Maps grid coverage boost.")
    parser.add_argument("--chains", default=DEFAULT_CHAINS, help="Comma-separated chains. Default: WinMart+,WinMart")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--grid-output", type=Path, default=DEFAULT_GRID)
    parser.add_argument("--seed-seen-dir", type=Path, default=SEED_SEEN_DIR, help="Existing clean by-brand CSVs used to skip old stores before detail pages.")
    parser.add_argument("--cities", default=",".join(DEFAULT_CITIES))
    parser.add_argument("--cell-km", type=float, default=4.0)
    parser.add_argument("--zoom", type=float, default=15.0)
    parser.add_argument("--grid-max-distance-km", type=float, default=0.0, help="0 = use cell-km times grid-radius-multiplier.")
    parser.add_argument("--grid-radius-multiplier", type=float, default=1.0)
    parser.add_argument("--sample-cells", type=int, default=0, help="Smoke-test only: randomly sample N generated grid cells.")
    parser.add_argument("--sample-seed", type=int, default=20260620)
    parser.add_argument("--concurrency", type=int, default=1, help="One CKEY proxy is most stable with one browser worker.")
    parser.add_argument("--chain-parallelism", type=int, default=1)
    parser.add_argument("--goto-timeout", type=int, default=45000)
    parser.add_argument("--feed-timeout", type=int, default=12000)
    parser.add_argument("--detail-timeout", type=int, default=20000)
    parser.add_argument("--region-hard-timeout", type=float, default=240.0)
    parser.add_argument("--scroll-rounds", type=int, default=10)
    parser.add_argument("--detail-min-delay", type=float, default=1.0)
    parser.add_argument("--detail-max-delay", type=float, default=2.0)
    parser.add_argument("--min-delay", type=float, default=1.0)
    parser.add_argument("--max-delay", type=float, default=2.5)
    parser.add_argument("--proxy-url", default="", help="Optional proxy URL. If omitted, crawler reads GMAPS_PROXY_URL/.env.")
    parser.add_argument("--ckey-proxy-key", default="", help="Optional CKEY proxy key. If omitted, crawler reads GMAPS_CKEY_PROXY_KEY/.env.")
    parser.add_argument("--ckey-proxy-type", default="", help="http or socks5. If omitted, crawler reads GMAPS_CKEY_PROXY_TYPE/.env.")
    parser.add_argument("--proxy-min-session-seconds", type=float, default=60.0)
    parser.add_argument("--proxy-max-session-seconds", type=float, default=900.0)
    parser.add_argument("--proxy-block-cooldown-seconds", type=float, default=60.0)
    parser.add_argument("--proxy-network-error-cooldown-seconds", type=float, default=5.0)
    parser.add_argument("--proxy-network-retry-limit", type=int, default=3)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cities = [item.strip() for item in args.cities.split(",") if item.strip()]
    if not cities:
        raise SystemExit("--cities cannot be empty.")
    region_count = write_grid(args.grid_output, cities, args.cell_km, args.zoom)

    cmd = [
        sys.executable,
        str(CRAWLER),
        "--registry",
        str(args.registry),
        "--chains",
        args.chains,
        "--regions",
        str(args.grid_output),
        "--output",
        str(args.output),
        "--seed-seen-dir",
        str(args.seed_seen_dir),
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
        "--scroll-rounds",
        str(args.scroll_rounds),
        "--grid-max-distance-km",
        str(args.grid_max_distance_km),
        "--grid-radius-multiplier",
        str(args.grid_radius_multiplier),
        "--min-delay",
        str(args.min_delay),
        "--max-delay",
        str(args.max_delay),
        "--detail-min-delay",
        str(args.detail_min_delay),
        "--detail-max-delay",
        str(args.detail_max_delay),
        "--proxy-min-session-seconds",
        str(args.proxy_min_session_seconds),
        "--proxy-max-session-seconds",
        str(args.proxy_max_session_seconds),
        "--proxy-block-cooldown-seconds",
        str(args.proxy_block_cooldown_seconds),
        "--proxy-network-error-cooldown-seconds",
        str(args.proxy_network_error_cooldown_seconds),
        "--proxy-network-retry-limit",
        str(args.proxy_network_retry_limit),
    ]
    if args.sample_cells:
        cmd.extend(["--sample-regions", str(args.sample_cells), "--sample-seed", str(args.sample_seed)])
    if not args.no_shuffle:
        cmd.append("--shuffle")
    if args.visible:
        cmd.append("--no-headless")
    if args.proxy_url:
        cmd.extend(["--proxy-url", args.proxy_url])
    if args.ckey_proxy_key:
        cmd.extend(["--ckey-proxy-key", args.ckey_proxy_key])
    if args.ckey_proxy_type:
        cmd.extend(["--ckey-proxy-type", args.ckey_proxy_type])

    print(f"grid_regions={region_count} cities={','.join(cities)} cell_km={args.cell_km:g} zoom={args.zoom:g}")
    print(f"chains={args.chains}")
    print(f"output={args.output}")
    print(" ".join(cmd))
    if args.dry_run:
        return
    raise SystemExit(subprocess.call(cmd, cwd=PROJECT_ROOT))


if __name__ == "__main__":
    main()
