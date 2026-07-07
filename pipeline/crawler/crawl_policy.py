from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
POLICY_FILE = PIPELINE_DIR / "config" / "brand_policy.json"

CORE_CITIES = ["hcm", "hn", "danang"]
IMPORTANT_CITIES = ["hcm", "hn", "danang", "haiphong", "cantho", "binh_duong", "dong_nai"]
DENSE_CITIES = [
    "hcm",
    "hn",
    "danang",
    "haiphong",
    "cantho",
    "binh_duong",
    "dong_nai",
    "bac_ninh",
    "hung_yen",
    "hai_duong",
    "quang_ninh",
    "thanh_hoa",
    "nghe_an",
    "hue",
    "khanh_hoa",
    "lam_dong",
    "binh_dinh",
    "ba_ria_vung_tau",
    "long_an",
    "tien_giang",
    "an_giang",
]

CRITICAL_BRANDS = {"winmart", "winmart_plus"}
AMBIGUOUS_BRANDS = {"maycha"}


def normalize_text(value: str) -> str:
    """Normalize text only for keys/matching. Output data still keeps Vietnamese accents."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower().replace("đ", "d").replace("Ä‘", "d")
    text = re.sub(r"[^a-z0-9+]+", " ", text)
    text = re.sub(r"\s*\+\s*", "+", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str) -> str:
    slug = normalize_text(value).replace("+", " plus ")
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    if not slug:
        return "brand"
    return slug


def split_csv_text(value: str) -> list[str]:
    items: list[str] = []
    for raw_item in (value or "").split(","):
        item = raw_item.strip()
        if item:
            items.append(item)
    return items


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader)


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_policy() -> dict[str, object]:
    if not POLICY_FILE.exists():
        return {}
    return json.loads(POLICY_FILE.read_text(encoding="utf-8-sig"))


def load_current_clean_counts(clean_by_brand_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not clean_by_brand_dir.exists():
        return counts

    for path in clean_by_brand_dir.glob("*.csv"):
        rows = read_csv_rows(path)
        counts[path.stem] = len(rows)
    return counts


def get_container_brand_slugs() -> set[str]:
    policy = load_policy()
    overrides = policy.get("brand_overrides", {})
    result: set[str] = set()

    if not isinstance(overrides, dict):
        return result

    for slug, config in overrides.items():
        if isinstance(config, dict) and config.get("container_brand"):
            result.add(slug)
    return result


def summarize_discovery_output(discovery_center_dir: Path, clean_by_brand_dir: Path) -> list[dict[str, object]]:
    audit_path = discovery_center_dir / "gosom_audit_summary.csv"
    audit_rows = read_csv_rows(audit_path)
    current_counts = load_current_clean_counts(clean_by_brand_dir)

    city_counts_by_slug: dict[str, dict[str, int]] = {}
    brand_name_by_slug: dict[str, str] = {}

    for raw_path in discovery_center_dir.glob("*_gosom_raw.csv"):
        slug = raw_path.name.replace("_gosom_raw.csv", "")
        rows = read_csv_rows(raw_path)
        city_counts: dict[str, int] = {}

        for row in rows:
            # Center/grid discovery stores city keys in source_region_id.
            # National-lite discovery stores province labels in source_city.
            city_key = row.get("source_city", "").strip() or row.get("source_region_id", "").strip()
            if not city_key:
                continue
            city_counts[city_key] = city_counts.get(city_key, 0) + 1

            source_chain = row.get("source_chain", "").strip()
            if source_chain:
                brand_name_by_slug[slug] = source_chain

        city_counts_by_slug[slug] = city_counts

    summary_rows: list[dict[str, object]] = []
    seen_slugs: set[str] = set()

    for audit_row in audit_rows:
        brand_name = audit_row.get("chain", "").strip()
        slug = slugify(brand_name)
        seen_slugs.add(slug)

        city_counts = city_counts_by_slug.get(slug, {})
        signal_cities = sorted(city_counts)
        kept_rows = parse_int(audit_row.get("kept_rows", "0"))
        raw_rows = parse_int(audit_row.get("raw_rows", "0"))

        summary_rows.append(
            {
                "brand_name": brand_name,
                "brand_slug": slug,
                "discovery_raw_rows": raw_rows,
                "discovery_kept_rows": kept_rows,
                "signal_city_count": len(signal_cities),
                "signal_cities": ",".join(signal_cities),
                "current_clean_count": current_counts.get(slug, 0),
            }
        )

    # If a raw file exists but audit is missing/incomplete, still expose it in summary.
    for slug, city_counts in city_counts_by_slug.items():
        if slug in seen_slugs:
            continue
        signal_cities = sorted(city_counts)
        summary_rows.append(
            {
                "brand_name": brand_name_by_slug.get(slug, slug),
                "brand_slug": slug,
                "discovery_raw_rows": sum(city_counts.values()),
                "discovery_kept_rows": sum(city_counts.values()),
                "signal_city_count": len(signal_cities),
                "signal_cities": ",".join(signal_cities),
                "current_clean_count": current_counts.get(slug, 0),
            }
        )

    summary_rows.sort(key=sort_summary_row)
    return summary_rows


def parse_int(value: object) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def sort_summary_row(row: dict[str, object]) -> tuple[int, int, str]:
    current_count = parse_int(row.get("current_clean_count", 0))
    discovery_count = parse_int(row.get("discovery_kept_rows", 0))
    name = str(row.get("brand_name", ""))
    return (-current_count, -discovery_count, name.lower())


def build_crawl_plan(summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    plan_rows: list[dict[str, object]] = []
    container_slugs = get_container_brand_slugs()

    for summary in summary_rows:
        brand_name = str(summary.get("brand_name", "")).strip()
        brand_slug = str(summary.get("brand_slug", "")).strip()
        current_count = parse_int(summary.get("current_clean_count", 0))
        discovery_count = parse_int(summary.get("discovery_kept_rows", 0))
        signal_cities = split_csv_text(str(summary.get("signal_cities", "")))
        signal_city_count = len(signal_cities)

        route = choose_route(
            brand_slug,
            current_count,
            discovery_count,
            signal_city_count,
            container_slugs,
        )
        cities = choose_cities(route, signal_cities)
        note = explain_route(route, current_count, discovery_count, signal_city_count)

        plan_rows.append(
            {
                "brand_name": brand_name,
                "brand_slug": brand_slug,
                "route": route,
                "region_mode": route_to_region_mode(route),
                "crawl_cities": ",".join(cities),
                "sample_regions": 0,
                "current_clean_count": current_count,
                "discovery_kept_rows": discovery_count,
                "signal_city_count": signal_city_count,
                "signal_cities": ",".join(signal_cities),
                "notes": note,
            }
        )

    return plan_rows


def choose_route(
    brand_slug: str,
    current_count: int,
    discovery_count: int,
    signal_city_count: int,
    container_slugs: set[str],
) -> str:
    # Critical brands are worth broad grid crawl because missing rows matters more than runtime.
    if brand_slug in CRITICAL_BRANDS:
        return "grid_dense"

    # Container brands like AEON Mall are few but noisy; center crawl + strict QA is safer.
    if brand_slug in container_slugs:
        return "center_container"

    if brand_slug in AMBIGUOUS_BRANDS:
        return "center_ambiguous"

    if current_count >= 500 or discovery_count >= 30 or signal_city_count >= 5:
        return "grid_large"

    if current_count >= 100 or discovery_count >= 8 or signal_city_count >= 2:
        return "grid_signal"

    return "center_lite"


def choose_cities(route: str, signal_cities: list[str]) -> list[str]:
    valid_signal_cities = []
    valid_city_keys = set(DENSE_CITIES)
    for city in signal_cities:
        if city in valid_city_keys:
            valid_signal_cities.append(city)

    if route == "grid_dense":
        return DENSE_CITIES.copy()

    if route == "grid_large":
        return merge_city_lists(IMPORTANT_CITIES, valid_signal_cities)

    if route == "grid_signal":
        if valid_signal_cities:
            return merge_city_lists(valid_signal_cities, CORE_CITIES)
        return CORE_CITIES.copy()

    if valid_signal_cities:
        return merge_city_lists(valid_signal_cities, CORE_CITIES)
    return CORE_CITIES.copy()


def merge_city_lists(first: list[str], second: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for city in first + second:
        city = city.strip()
        if not city or city in seen:
            continue
        result.append(city)
        seen.add(city)
    return result


def route_to_region_mode(route: str) -> str:
    if route.startswith("grid"):
        return "grid"
    return "center"


def explain_route(route: str, current_count: int, discovery_count: int, signal_city_count: int) -> str:
    if route == "grid_dense":
        return "brand critical; crawl dense grid across 21 large markets"
    if route == "center_container":
        return "container brand; use light center crawl and strict tenant/gate QA"
    if route == "center_ambiguous":
        return "ambiguous brand name; use light crawl and strict brand QA"
    if route == "grid_large":
        return "large or strong discovery signal; grid large cities plus signal cities"
    if route == "grid_signal":
        return "medium brand; grid only cities with signal plus core cities"
    return (
        "small/sparse brand; center crawl only "
        f"(current={current_count}, discovery={discovery_count}, signal_cities={signal_city_count})"
    )


SUMMARY_FIELDS = [
    "brand_name",
    "brand_slug",
    "discovery_raw_rows",
    "discovery_kept_rows",
    "signal_city_count",
    "signal_cities",
    "current_clean_count",
]

PLAN_FIELDS = [
    "brand_name",
    "brand_slug",
    "route",
    "region_mode",
    "crawl_cities",
    "sample_regions",
    "current_clean_count",
    "discovery_kept_rows",
    "signal_city_count",
    "signal_cities",
    "notes",
]
