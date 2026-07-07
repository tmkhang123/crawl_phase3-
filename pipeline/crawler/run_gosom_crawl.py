from __future__ import annotations

import argparse
import csv
import json
import os
import re
import random
import subprocess
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path


VERSION = "1.16.0"
DOWNLOAD_URL = (
    "https://github.com/gosom/google-maps-scraper/releases/download/"
    f"v{VERSION}/google_maps_scraper-{VERSION}-windows-amd64.exe"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
CONFIG_DIR = PIPELINE_DIR / "config"
BINARY = PIPELINE_DIR / "tools" / "gosom" / "google-maps-scraper.exe"
REGISTRY_PHASE2 = CONFIG_DIR / "brand_registry_phase2.csv"
REGISTRY_PHASE1 = CONFIG_DIR / "brand_registry_phase1.csv"
DEFAULT_OUTPUT = PIPELINE_DIR / "output" / "gosom_candidates"
DEFAULT_GRID_REGIONS = CONFIG_DIR / "regions" / "grid_regions_dense.json"
DEFAULT_DISTRICTS = CONFIG_DIR / "regions" / "districts.json"
LAT_MIN, LAT_MAX = 8.0, 24.0
LNG_MIN, LNG_MAX = 102.0, 115.0
PROGRESS_FIELDS = [
    "timestamp",
    "chain",
    "region_id",
    "status",
    "returncode",
    "raw_rows",
    "city_file",
    "message",
]


CITY_CENTERS = {
    "hcm": ("TP.HCM", "10.78,106.65"),
    "hn": ("Hà Nội", "21.03,105.85"),
    "danang": ("Đà Nẵng", "16.05,108.22"),
    "haiphong": ("Hải Phòng", "20.84,106.68"),
    "cantho": ("Cần Thơ", "10.04,105.78"),
    "binh_duong": ("Bình Dương", "10.98,106.67"),
    "dong_nai": ("Đồng Nai", "10.95,106.82"),
}

CITY_CENTERS.update(
    {
        "bac_ninh": ("Bac Ninh", "21.12,106.08"),
        "hung_yen": ("Hung Yen", "20.93,106.05"),
        "hai_duong": ("Hai Duong", "20.94,106.33"),
        "quang_ninh": ("Quang Ninh", "20.97,107.08"),
        "thanh_hoa": ("Thanh Hoa", "19.81,105.78"),
        "nghe_an": ("Nghe An", "18.68,105.68"),
        "hue": ("Hue", "16.46,107.59"),
        "khanh_hoa": ("Khanh Hoa", "12.24,109.19"),
        "lam_dong": ("Lam Dong", "11.94,108.44"),
        "binh_dinh": ("Binh Dinh", "13.77,109.22"),
        "ba_ria_vung_tau": ("Ba Ria Vung Tau", "10.50,107.18"),
        "long_an": ("Long An", "10.63,106.45"),
        "tien_giang": ("Tien Giang", "10.36,106.36"),
        "an_giang": ("An Giang", "10.39,105.43"),
    }
)

CITY_BOXES: dict[str, dict[str, float | str]] = {
    "hcm": {"name": "TP.HCM", "lat_min": 10.35, "lat_max": 11.15, "lng_min": 106.35, "lng_max": 107.05},
    "hn": {"name": "Ha Noi", "lat_min": 20.75, "lat_max": 21.35, "lng_min": 105.25, "lng_max": 106.15},
    "binh_duong": {"name": "Binh Duong", "lat_min": 10.82, "lat_max": 11.35, "lng_min": 106.55, "lng_max": 107.05},
    "dong_nai": {"name": "Dong Nai", "lat_min": 10.65, "lat_max": 11.25, "lng_min": 106.75, "lng_max": 107.45},
    "danang": {"name": "Da Nang", "lat_min": 15.95, "lat_max": 16.18, "lng_min": 108.05, "lng_max": 108.35},
    "haiphong": {"name": "Hai Phong", "lat_min": 20.65, "lat_max": 21.05, "lng_min": 106.45, "lng_max": 107.05},
    "cantho": {"name": "Can Tho", "lat_min": 9.90, "lat_max": 10.20, "lng_min": 105.62, "lng_max": 105.90},
    "bac_ninh": {"name": "Bac Ninh", "lat_min": 21.00, "lat_max": 21.25, "lng_min": 105.85, "lng_max": 106.25},
    "hung_yen": {"name": "Hung Yen", "lat_min": 20.80, "lat_max": 21.05, "lng_min": 105.85, "lng_max": 106.15},
    "hai_duong": {"name": "Hai Duong", "lat_min": 20.85, "lat_max": 21.15, "lng_min": 106.15, "lng_max": 106.55},
    "quang_ninh": {"name": "Quang Ninh", "lat_min": 20.85, "lat_max": 21.25, "lng_min": 106.90, "lng_max": 107.35},
    "thanh_hoa": {"name": "Thanh Hoa", "lat_min": 19.65, "lat_max": 20.05, "lng_min": 105.65, "lng_max": 106.05},
    "nghe_an": {"name": "Nghe An", "lat_min": 18.55, "lat_max": 19.05, "lng_min": 105.55, "lng_max": 105.95},
    "hue": {"name": "Hue", "lat_min": 16.35, "lat_max": 16.60, "lng_min": 107.45, "lng_max": 107.75},
    "khanh_hoa": {"name": "Khanh Hoa", "lat_min": 12.15, "lat_max": 12.35, "lng_min": 109.05, "lng_max": 109.35},
    "lam_dong": {"name": "Lam Dong", "lat_min": 11.45, "lat_max": 12.10, "lng_min": 107.75, "lng_max": 108.60},
    "binh_dinh": {"name": "Binh Dinh", "lat_min": 13.65, "lat_max": 13.90, "lng_min": 109.10, "lng_max": 109.35},
    "ba_ria_vung_tau": {"name": "Ba Ria Vung Tau", "lat_min": 10.35, "lat_max": 10.75, "lng_min": 107.05, "lng_max": 107.35},
    "long_an": {"name": "Long An", "lat_min": 10.45, "lat_max": 10.80, "lng_min": 106.25, "lng_max": 106.75},
    "tien_giang": {"name": "Tien Giang", "lat_min": 10.25, "lat_max": 10.50, "lng_min": 106.20, "lng_max": 106.55},
    "an_giang": {"name": "An Giang", "lat_min": 10.25, "lat_max": 10.75, "lng_min": 105.05, "lng_max": 105.45},
}


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("đ", "d")
    value = re.sub(r"[^a-z0-9+]+", " ", value)
    value = re.sub(r"\s*\+\s*", "+", value)
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    slug = normalize_text(value).replace("+", " plus ")
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug or "brand"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ensure_binary() -> None:
    if BINARY.exists() and BINARY.stat().st_size > 1_000_000:
        print(f"gosom_binary=ready version={VERSION}")
        return
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    print(f"gosom_binary=downloading version={VERSION}")
    request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "CodexGosomCrawler"})
    with urllib.request.urlopen(request, timeout=180) as response, BINARY.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    print(f"gosom_binary=ready bytes={BINARY.stat().st_size}")


def read_registry(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    return [row["target_chain"].strip() for row in rows if row.get("target_chain", "").strip()]


def read_registry_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def load_brand_rules() -> dict[str, dict[str, list[str]]]:
    rules: dict[str, dict[str, list[str]]] = {}
    for row in read_registry_rows(REGISTRY_PHASE1) + read_registry_rows(REGISTRY_PHASE2):
        chain = row.get("target_chain", "").strip()
        if not chain:
            continue
        aliases = [chain, row.get("search_query", "").strip()]
        aliases.extend(item.strip() for item in row.get("name_aliases", "").split("|") if item.strip())
        blacklist = [item.strip() for item in row.get("name_blacklist", "").split("|") if item.strip()]
        rules[chain.lower()] = {
            "aliases": sorted({normalize_text(item) for item in aliases if normalize_text(item)}),
            "blacklist": sorted({normalize_text(item) for item in blacklist if normalize_text(item)}),
        }
    return rules


def row_matches_brand(row: dict[str, str], chain: str, brand_rules: dict[str, dict[str, list[str]]]) -> bool:
    rules = brand_rules.get(chain.lower())
    if not rules:
        aliases = [normalize_text(chain)]
        blacklist: list[str] = []
    else:
        aliases = rules["aliases"] or [normalize_text(chain)]
        blacklist = rules["blacklist"]
    title = normalize_text(row.get("title", ""))
    if not title:
        return False
    if any(term and term in title for term in blacklist):
        return False
    return any(alias and alias in title for alias in aliases)


def select_chains(args: argparse.Namespace) -> list[str]:
    if args.chains:
        return [item.strip() for item in args.chains.split(",") if item.strip()]
    chains: list[str] = []
    if args.include_phase1:
        chains.extend(read_registry(REGISTRY_PHASE1))
    chains.extend(read_registry(REGISTRY_PHASE2))
    seen = set()
    unique = []
    for chain in chains:
        key = chain.lower()
        if key not in seen:
            seen.add(key)
            unique.append(chain)
    if args.limit_brands:
        unique = unique[: args.limit_brands]
    return unique


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists() or path.stat().st_size == 0:
        return [], []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mask_command_for_log(command: list[str]) -> list[str]:
    masked = []
    skip_next = False
    for item in command:
        if skip_next:
            masked.append("***")
            skip_next = False
            continue
        masked.append(item)
        if item == "-proxies":
            skip_next = True
    return masked


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def append_progress(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=PROGRESS_FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in PROGRESS_FIELDS})


def load_progress(path: Path) -> tuple[set[tuple[str, str]], set[str]]:
    completed_regions: set[tuple[str, str]] = set()
    completed_chains: set[str] = set()
    if not path.exists() or path.stat().st_size == 0:
        return completed_regions, completed_chains
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as source:
        for row in csv.DictReader(source):
            chain = row.get("chain", "").strip()
            region_id = row.get("region_id", "").strip()
            status = row.get("status", "").strip()
            if not chain:
                continue
            if status == "chain_complete":
                completed_chains.add(chain)
            elif status == "completed" and region_id:
                completed_regions.add((chain, region_id))
    return completed_regions, completed_chains


def row_key(row: dict[str, str]) -> tuple[str, ...]:
    cid = row.get("cid", "").strip()
    place_id = row.get("place_id", "").strip()
    data_id = row.get("data_id", "").strip()
    if cid or place_id or data_id:
        return ("id", cid, place_id, data_id)
    return (
        "text",
        normalize_text(row.get("title", "")),
        normalize_text(row.get("address", "")),
        row.get("latitude", "").strip(),
        row.get("longitude", "").strip(),
    )


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def coord_reject_reason(row: dict[str, str]) -> str:
    lat = parse_float(row.get("latitude") or row.get("lat"))
    lng = parse_float(row.get("longitude") or row.get("lng"))
    if lat is None or lng is None:
        return "invalid_or_missing_coord"
    if lat == 0 and lng == 0:
        return "zero_coord"
    if not (LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX):
        return "coord_outside_vietnam_bounds"
    return ""


def center_regions(cities: list[str]) -> list[dict[str, object]]:
    regions = []
    for city_key in cities:
        city_name, geo = CITY_CENTERS[city_key]
        lat, lng = [float(item) for item in geo.split(",", 1)]
        regions.append(
            {
                "id": city_key,
                "label": city_name,
                "city_key": city_key,
                "city_name": city_name,
                "lat": lat,
                "lng": lng,
            }
        )
    return regions


def grid_regions(path: Path, cities: list[str], sample: int, limit: int, seed: int) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    wanted = set(cities)
    regions = [row for row in payload.get("regions", []) if row.get("city_key") in wanted]
    if sample:
        rng = random.Random(seed)
        regions = rng.sample(regions, min(sample, len(regions)))
    elif limit:
        regions = regions[:limit]
    return regions


def gridbox_regions(cities: list[str], sample: int, limit: int, seed: int) -> list[dict[str, object]]:
    regions = []
    for city_key in cities:
        if city_key not in CITY_BOXES:
            raise SystemExit(f"Unknown gridbox city {city_key!r}. Choices: {', '.join(sorted(CITY_BOXES))}")
        box = CITY_BOXES[city_key]
        lat_min = float(box["lat_min"])
        lat_max = float(box["lat_max"])
        lng_min = float(box["lng_min"])
        lng_max = float(box["lng_max"])
        lat = round((lat_min + lat_max) / 2, 6)
        lng = round((lng_min + lng_max) / 2, 6)
        regions.append(
            {
                "id": city_key,
                "label": str(box["name"]),
                "city_key": city_key,
                "city_name": str(box["name"]),
                "lat": lat,
                "lng": lng,
                "bbox": f"{lat_min},{lng_min},{lat_max},{lng_max}",
            }
        )
    if sample:
        rng = random.Random(seed)
        regions = rng.sample(regions, min(sample, len(regions)))
    elif limit:
        regions = regions[:limit]
    return regions


def district_regions(path: Path, sample: int, limit: int, seed: int) -> list[dict[str, object]]:
    labels = json.loads(path.read_text(encoding="utf-8-sig"))
    regions = []
    for idx, label in enumerate(labels, start=1):
        province = label.split(",")[-1].strip() if "," in label else ""
        regions.append(
            {
                "id": f"district_{idx:03d}",
                "label": label,
                "city_key": "all_vietnam",
                "city_name": province,
                "lat": "",
                "lng": "",
                "query_suffix": label,
            }
        )
    if sample:
        rng = random.Random(seed)
        regions = rng.sample(regions, min(sample, len(regions)))
    elif limit:
        regions = regions[:limit]
    return regions


def merge_outputs(
    files: list[tuple[Path, dict[str, object]]],
    output_file: Path,
    chain: str,
    brand_rules: dict[str, dict[str, list[str]]],
) -> dict[str, int | str]:
    field_order: list[str] = []
    merged: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    seen = set()
    raw_rows = 0
    duplicate_rows = 0
    rejected_brand = 0
    rejected_coord = 0
    for file, region in files:
        fields, rows = read_csv(file)
        for field in fields + ["source_chain", "source_city", "source_region_id", "source_geo", "source_query"]:
            if field not in field_order:
                field_order.append(field)
        for row in rows:
            raw_rows += 1
            query_suffix = str(region.get("query_suffix", "")).strip()
            row["source_chain"] = chain
            row["source_city"] = str(region.get("city_name", ""))
            row["source_region_id"] = str(region.get("id", ""))
            row["source_geo"] = f"{region.get('lat')},{region.get('lng')}"
            row["source_query"] = f"{chain} {query_suffix}".strip()
            if not row_matches_brand(row, chain, brand_rules):
                rejected_row = dict(row)
                rejected_row["reject_reason"] = "title_does_not_match_brand_alias"
                rejected.append(rejected_row)
                rejected_brand += 1
                continue
            coord_reason = coord_reject_reason(row)
            if coord_reason:
                rejected_row = dict(row)
                rejected_row["reject_reason"] = coord_reason
                rejected.append(rejected_row)
                rejected_coord += 1
                continue
            key = row_key(row)
            if key in seen:
                duplicate_rows += 1
                continue
            seen.add(key)
            merged.append(row)
    if not field_order:
        field_order = ["source_chain", "source_city", "source_query"]
    write_csv(output_file, field_order, merged)
    if rejected:
        rejected_fields = field_order + ["reject_reason"]
        write_csv(output_file.with_suffix(".rejected.csv"), rejected_fields, rejected)
    return {
        "chain": chain,
        "raw_rows": raw_rows,
        "kept_rows": len(merged),
        "duplicate_rows": duplicate_rows,
        "rejected_rows": len(rejected),
        "rejected_brand_rows": rejected_brand,
        "rejected_coord_rows": rejected_coord,
        "output_file": str(output_file),
        "rejected_file": str(output_file.with_suffix(".rejected.csv")) if rejected else "",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch runner for gosom/google-maps-scraper candidate crawl.")
    parser.add_argument("--chains", default="", help="Comma-separated brand list. If omitted, phase2 registry is used.")
    parser.add_argument("--include-phase1", action="store_true", help="Include phase1 registry when --chains is omitted.")
    parser.add_argument("--limit-brands", type=int, default=0)
    parser.add_argument("--cities", default="hcm", help=f"Comma-separated city keys for center/grid mode: {','.join(CITY_CENTERS)}")
    parser.add_argument(
        "--region-mode",
        choices=("center", "grid", "gridbox", "district"),
        default="center",
        help="center = one point per city; grid = prebuilt cells; gridbox = gosom native bbox grid; district = district text queries.",
    )
    parser.add_argument("--grid-regions", type=Path, default=DEFAULT_GRID_REGIONS)
    parser.add_argument("--districts", type=Path, default=DEFAULT_DISTRICTS)
    parser.add_argument("--sample-regions", type=int, default=0, help="Smoke only: random sample N regions after filter.")
    parser.add_argument("--limit-regions", type=int, default=0, help="Smoke only: first N regions after filter.")
    parser.add_argument("--sample-seed", type=int, default=20260629)
    parser.add_argument("--radius", type=float, default=None, help="Meters. Default: 20000 in center mode, 2500 in grid mode, unused in district mode.")
    parser.add_argument("--grid-cell-km", type=float, default=4.0, help="Cell size for gosom native gridbox mode.")
    parser.add_argument("--zoom", type=int, default=15)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--proxy-url", default="", help="Optional gosom proxy URL. Also reads GMAPS_PROXY_URL.")
    parser.add_argument(
        "--full-mode",
        action="store_true",
        help="Disable gosom -fast-mode. District mode also disables fast-mode automatically because gosom requires -geo in fast-mode.",
    )
    parser.add_argument("--raw-keep-city-files", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="Disable progress resume and rerun all selected regions.")
    parser.add_argument("--force", action="store_true", help="Ignore completed chain/region progress and rerun selected work.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--setup-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    configure_console()
    args = parse_args()
    load_env(PROJECT_ROOT / ".env")
    ensure_binary()
    if args.setup_only:
        return 0

    chains = select_chains(args)
    if not chains:
        raise SystemExit("No chains selected.")
    brand_rules = load_brand_rules()
    if args.region_mode == "district":
        cities = ["all_vietnam"]
        regions = district_regions(args.districts, args.sample_regions, args.limit_regions, args.sample_seed)
    else:
        cities = [item.strip() for item in args.cities.split(",") if item.strip()]
        bad_cities = [city for city in cities if city not in CITY_CENTERS]
        if bad_cities:
            raise SystemExit(f"Unknown city key(s): {', '.join(bad_cities)}")
        if args.region_mode == "gridbox":
            regions = gridbox_regions(cities, args.sample_regions, args.limit_regions, args.sample_seed)
        elif args.region_mode == "grid":
            regions = grid_regions(args.grid_regions, cities, args.sample_regions, args.limit_regions, args.sample_seed)
        else:
            regions = center_regions(cities)
    if not regions:
        raise SystemExit("No regions selected.")
    radius = args.radius
    if radius is None:
        radius = 2_500.0 if args.region_mode == "grid" else 20_000.0
    proxy_url = args.proxy_url or os.getenv("GMAPS_PROXY_URL", "")

    args.output.mkdir(parents=True, exist_ok=True)
    temp_dir = args.output / "_city_runs"
    temp_dir.mkdir(parents=True, exist_ok=True)
    progress_file = args.output / "gosom_progress.csv"
    resume_enabled = not args.no_resume and not args.force
    completed_regions, completed_chains = load_progress(progress_file) if resume_enabled else (set(), set())

    print(
        f"gosom_chains={len(chains)} region_mode={args.region_mode} "
        f"cities={','.join(cities)} regions={len(regions)} radius={radius:g}m "
        f"resume={'on' if resume_enabled else 'off'} output={args.output}"
    )
    if args.region_mode == "center":
        print("note=center mode returns up to about 20 fast-mode results per city center.")
    elif args.region_mode == "district":
        print(f"note=district mode runs one text query per district/province label, selected_regions={len(regions)}.")
        print("note=district mode disables gosom fast-mode automatically because fast-mode requires geo coordinates.")
    elif args.region_mode == "gridbox":
        print("note=gridbox mode uses gosom native -grid-bbox/-grid-cell, one process per city box.")
    else:
        print("note=grid mode returns up to about 20 fast-mode results per grid cell; dedupe happens after merge.")
    total_rows = 0
    audit_rows: list[dict[str, int | str]] = []
    for chain in chains:
        chain_slug = slugify(chain)
        output_file = args.output / f"{chain_slug}_gosom_raw.csv"
        if resume_enabled and chain in completed_chains and output_file.exists():
            print(f"skip chain={chain} reason=chain_complete output={output_file}")
            continue
        city_files: list[tuple[Path, dict[str, object]]] = []
        query_files: list[Path] = []
        for idx, region in enumerate(regions, start=1):
            city_name = str(region.get("city_name", ""))
            region_id = str(region.get("id", idx))
            query_suffix = str(region.get("query_suffix", "")).strip()
            query = f"{chain} {query_suffix}".strip()
            query_file = temp_dir / f"{chain_slug}__{slugify(region_id)}.txt"
            query_file.write_text(query + "\n", encoding="utf-8")
            query_files.append(query_file)
            geo = f"{region.get('lat')},{region.get('lng')}"
            city_file = temp_dir / f"{chain_slug}__{slugify(region_id)}.csv"
            if resume_enabled and (chain, region_id) in completed_regions and city_file.exists():
                city_files.append((city_file, region))
                print(f"skip chain={chain} region={idx}/{len(regions)} id={region_id} reason=completed")
                continue
            command = [
                str(BINARY),
                "-input",
                str(query_file),
                "-results",
                str(city_file),
                "-zoom",
                str(args.zoom),
                "-depth",
                str(args.depth),
                "-c",
                str(max(1, args.concurrency)),
                "-browser-pool-size",
                "1",
                "-pages-per-browser",
                str(max(2, args.concurrency)),
                "-lang",
                "vi",
                "-exit-on-inactivity",
                "3m",
            ]
            use_fast_mode = not args.full_mode and args.region_mode not in {"district", "gridbox"}
            if use_fast_mode:
                command.append("-fast-mode")
            if proxy_url:
                command.extend(["-proxies", proxy_url])
            if args.region_mode == "gridbox":
                command.extend(["-geo", geo, "-grid-bbox", str(region.get("bbox", "")), "-grid-cell", str(args.grid_cell_km)])
            elif args.region_mode != "district":
                command.extend(["-geo", geo, "-radius", str(radius)])
            print(f"chain={chain} region={idx}/{len(regions)} city={city_name} id={region_id} file={city_file}")
            if args.dry_run:
                print("command=" + subprocess.list2cmdline(mask_command_for_log(command)))
                continue
            append_progress(
                progress_file,
                {
                    "timestamp": now_iso(),
                    "chain": chain,
                    "region_id": region_id,
                    "status": "started",
                    "city_file": str(city_file),
                },
            )
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.returncode != 0:
                if completed.stdout:
                    useful_lines = [
                        line
                        for line in completed.stdout.splitlines()
                        if line.strip() and "Google Maps Scraper" not in line and "github.com" not in line
                    ]
                    for line in useful_lines[-8:]:
                        print(f"gosom_output {line}", file=sys.stderr)
                print(f"warning chain={chain} city={city_name} returncode={completed.returncode}", file=sys.stderr)
                append_progress(
                    progress_file,
                    {
                        "timestamp": now_iso(),
                        "chain": chain,
                        "region_id": region_id,
                        "status": "failed",
                        "returncode": completed.returncode,
                        "raw_rows": 0,
                        "city_file": str(city_file),
                        "message": "gosom_returncode_nonzero",
                    },
                )
            else:
                _, region_rows = read_csv(city_file)
                append_progress(
                    progress_file,
                    {
                        "timestamp": now_iso(),
                        "chain": chain,
                        "region_id": region_id,
                        "status": "completed",
                        "returncode": completed.returncode,
                        "raw_rows": len(region_rows),
                        "city_file": str(city_file),
                    },
                )
            city_files.append((city_file, region))
            time.sleep(0.5)
        if args.dry_run:
            for query_file in query_files:
                if query_file.exists():
                    query_file.unlink()
            continue
        stats = merge_outputs(city_files, output_file, chain, brand_rules)
        audit_rows.append(stats)
        rows = int(stats["kept_rows"])
        total_rows += rows
        print(
            f"merged chain={chain} raw={stats['raw_rows']} kept={stats['kept_rows']} "
            f"dup={stats['duplicate_rows']} rejected={stats['rejected_rows']} "
            f"coord_rejected={stats['rejected_coord_rows']} output={output_file}"
        )
        if not args.raw_keep_city_files:
            for file, _region in city_files:
                if file.exists():
                    file.unlink()
            for query_file in query_files:
                if query_file.exists():
                    query_file.unlink()
        append_progress(
            progress_file,
            {
                "timestamp": now_iso(),
                "chain": chain,
                "region_id": "",
                "status": "chain_complete",
                "returncode": 0,
                "raw_rows": stats["raw_rows"],
                "city_file": str(output_file),
                "message": "merged",
            },
        )
    if not args.dry_run and audit_rows:
        audit_fields = [
            "chain",
            "raw_rows",
            "kept_rows",
            "duplicate_rows",
            "rejected_rows",
            "rejected_brand_rows",
            "rejected_coord_rows",
            "output_file",
            "rejected_file",
        ]
        write_csv(args.output / "gosom_audit_summary.csv", audit_fields, audit_rows)
        print(f"audit={args.output / 'gosom_audit_summary.csv'}")
    print(f"done total_rows={total_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
