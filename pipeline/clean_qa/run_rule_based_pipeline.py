from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback for machines without rapidfuzz
    fuzz = None
    from difflib import SequenceMatcher


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
PHASE_1_2_DIR = PROJECT_ROOT / "phase_1_2"
PHASE1_DIR = PHASE_1_2_DIR / "hybrid_v3_controlled" / "output" / "final_46_by_brand"
PHASE2_DIR = PHASE_1_2_DIR / "raw_legacy" / "data_chainlock_phase2"
REGISTRY_FILES = [
    PIPELINE_DIR / "config" / "brand_registry_phase1.csv",
    PIPELINE_DIR / "config" / "brand_registry_phase2.csv",
]
POLICY_FILE = PIPELINE_DIR / "config" / "brand_policy.json"
GOSOM_WINMART_PLUS_FILE = (
    PHASE_1_2_DIR / "raw_legacy" / "data_gosom_topup_grid_winmart" / "grid" / "winmart_plus_gosom_raw.csv"
)
GOSOM_TOPUP_DIRS = [
    PHASE_1_2_DIR / "raw_legacy" / "data_gosom_topup_grid_winmart" / "grid",
    PIPELINE_DIR / "output",
]

FINAL_FIELDS = ["brand_id", "name", "address", "city", "province", "lat", "lng"]
META_FIELDS = [
    "brand_slug",
    "brand_name",
    "source",
    "source_file",
    "source_row_number",
    "crawl_date",
    "pipeline_run_id",
    "qa_status",
    "qa_reason",
]
AUDIT_FIELDS = [
    "brand_slug",
    "brand_name",
    "raw_rows",
    "normalized_rows",
    "keep_rows",
    "suspect_rows",
    "reject_rows",
    "duplicate_rows",
]


@dataclass
class SourceFile:
    source: str
    brand_slug: str
    brand_name: str
    path: Path


def clean_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    output = []
    for char in normalized:
        if unicodedata.category(char) == "Mn":
            continue
        output.append(char)
    text = "".join(output)
    text = text.replace("đ", "d").replace("Đ", "D")
    return text


def normalize_for_match(value: Any) -> str:
    # Key dùng để so khớp/dedupe. Output CSV vẫn giữ nguyên dấu tiếng Việt.
    text = clean_cell(value).lower()
    text = strip_accents(text)
    replacements = {
        r"\bd\.\s*": "duong ",
        r"\bduong\s+": "duong ",
        r"\bq\.\s*": "quan ",
        r"\bp\.\s*": "phuong ",
        r"\btp\.\s*": "thanh pho ",
        r"\btttm\b": "trung tam thuong mai",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"[^a-z0-9+]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(value: str) -> str:
    text = normalize_for_match(value)
    text = text.replace("+", " plus ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def slug_to_brand_name(slug: str) -> str:
    parts = slug.split("_")
    names = []
    for part in parts:
        if part == "plus":
            names.append("+")
        else:
            names.append(part.capitalize())
    return " ".join(names).replace(" +", "+")


def text_similarity(left: str, right: str) -> float:
    left_key = normalize_for_match(left)
    right_key = normalize_for_match(right)
    if not left_key or not right_key:
        return 0.0
    if fuzz is not None:
        return float(fuzz.ratio(left_key, right_key))
    return SequenceMatcher(None, left_key, right_key).ratio() * 100


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    # Tính khoảng cách địa lý theo mặt cầu, dùng cho dedupe tọa độ.
    earth_radius_m = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = math.sin(delta_lat / 2) ** 2
    a += math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_m * c


def canonical_location(value: str) -> str:
    text = clean_cell(value)
    key = normalize_for_match(text)
    aliases = {
        "hcm": "Hồ Chí Minh",
        "tp hcm": "Hồ Chí Minh",
        "thanh pho ho chi minh": "Hồ Chí Minh",
        "ho chi minh": "Hồ Chí Minh",
        "ho chi minh city": "Hồ Chí Minh",
        "sai gon": "Hồ Chí Minh",
        "ha noi": "Hà Nội",
        "hn": "Hà Nội",
        "da nang": "Đà Nẵng",
        "hai phong": "Hải Phòng",
        "can tho": "Cần Thơ",
        "hue": "Huế",
    }
    if key in aliases:
        return aliases[key]
    text = re.sub(r"^(Tỉnh|Thành phố|TP\.|Tp\.)\s+", "", text, flags=re.IGNORECASE)
    return text.strip()


def parse_city_province(address: str) -> tuple[str, str]:
    parts = []
    for raw_part in clean_cell(address).split(","):
        part = clean_cell(raw_part)
        if part:
            parts.append(part)
    if parts and normalize_for_match(parts[-1]) in {"viet nam", "vietnam"}:
        parts.pop()
    if not parts:
        return "", ""
    province = canonical_location(parts[-1])
    city = ""
    if len(parts) >= 2:
        city = canonical_location(parts[-2])
    if normalize_for_match(city) in {"thanh pho", "tp", "tinh", "quan", "huyen", "thi xa"}:
        if len(parts) >= 3:
            city = canonical_location(parts[-3])
    return city, province


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as file:
        reader = csv.DictReader(file)
        rows = []
        for row in reader:
            rows.append(dict(row))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def discover_source_files() -> list[SourceFile]:
    sources = []
    if PHASE1_DIR.exists():
        for path in sorted(PHASE1_DIR.glob("*.csv")):
            brand_slug = path.stem
            sources.append(SourceFile("phase1", brand_slug, slug_to_brand_name(brand_slug), path))
    if PHASE2_DIR.exists():
        for path in sorted(PHASE2_DIR.glob("*_gmaps_chainlock.csv")):
            brand_slug = path.name.replace("_gmaps_chainlock.csv", "")
            sources.append(SourceFile("phase2", brand_slug, slug_to_brand_name(brand_slug), path))
    return sources


def discover_gosom_topup_files() -> list[SourceFile]:
    sources: list[SourceFile] = []
    seen_paths = set()

    for search_dir in GOSOM_TOPUP_DIRS:
        if not search_dir.exists():
            continue
        for path in sorted(search_dir.rglob("*_gosom_raw.csv")):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            brand_slug = path.name.replace("_gosom_raw.csv", "")
            sources.append(SourceFile("gosom_topup", brand_slug, slug_to_brand_name(brand_slug), path))

    return sources


def parse_pipe_list(value: str) -> list[str]:
    items = []
    for item in clean_cell(value).split("|"):
        item = clean_cell(item)
        if item:
            items.append(item)
    return items


def load_registry_aliases() -> dict[str, dict[str, list[str]]]:
    registry: dict[str, dict[str, list[str]]] = {}
    for path in REGISTRY_FILES:
        if not path.exists():
            continue
        rows = read_csv_rows(path)
        for row in rows:
            chain = clean_cell(row.get("target_chain", ""))
            if not chain:
                continue
            brand_slug = slugify(chain)
            item = registry.setdefault(brand_slug, {"aliases": [], "blacklist": []})
            for alias in parse_pipe_list(row.get("name_aliases", "")):
                item["aliases"].append(alias)
            if chain:
                item["aliases"].append(chain)
            for keyword in parse_pipe_list(row.get("name_blacklist", "")):
                item["blacklist"].append(keyword)
    return registry


def unique_normalized_list(values: list[str]) -> list[str]:
    output = []
    seen = set()
    for value in values:
        key = normalize_for_match(value)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def build_brand_policies(policy_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    registry = load_registry_aliases()
    overrides = policy_payload.get("brand_overrides", {})
    policies: dict[str, dict[str, Any]] = {}

    all_slugs = set()
    for slug in registry:
        all_slugs.add(slug)
    for slug in overrides:
        all_slugs.add(slug)

    for slug in all_slugs:
        policy: dict[str, Any] = {}
        policy["aliases"] = []
        policy["blacklist"] = []

        if slug in registry:
            for alias in registry[slug].get("aliases", []):
                policy["aliases"].append(alias)
            for keyword in registry[slug].get("blacklist", []):
                policy["blacklist"].append(keyword)

        if slug in overrides:
            override = overrides[slug]
            for key, value in override.items():
                if key in {"aliases", "blacklist"}:
                    existing = policy.setdefault(key, [])
                    for item in value:
                        existing.append(item)
                else:
                    policy[key] = value

        fallback_alias = slug.replace("_plus", "+").replace("_", " ")
        policy["aliases"].append(fallback_alias)
        policy["aliases"] = unique_normalized_list(policy.get("aliases", []))
        policy["blacklist"] = unique_normalized_list(policy.get("blacklist", []))
        policies[slug] = policy

    return policies


def get_policy(brand_slug: str, policies: dict[str, dict[str, Any]], defaults: dict[str, Any]) -> dict[str, Any]:
    policy = {
        "aliases": unique_normalized_list([brand_slug.replace("_", " ")]),
        "blacklist": [],
        "reject_keywords": [],
        "container_brand": False,
        "container_keep_prefixes": [],
        "container_reject_keywords": [],
        "non_store_action": defaults.get("non_store_action", "suspect"),
    }
    if brand_slug in policies:
        for key, value in policies[brand_slug].items():
            policy[key] = value
    return policy


def has_any_keyword(text_key: str, keywords: list[str]) -> bool:
    compact_text = text_key.replace(" ", "")
    for keyword in keywords:
        keyword_key = normalize_for_match(keyword)
        compact_keyword = keyword_key.replace(" ", "")
        if keyword_key and keyword_key in text_key:
            return True
        if compact_keyword and compact_keyword in compact_text:
            return True
    return False


def has_any_phrase_keyword(text_key: str, keywords: list[str]) -> bool:
    # Dùng cho keyword QA như "kho", "văn phòng".
    # Không match substring để tránh bắt nhầm "khóm", "khoa", "khoang".
    padded_text = " " + text_key + " "
    for keyword in keywords:
        keyword_key = normalize_for_match(keyword)
        if not keyword_key:
            continue
        padded_keyword = " " + keyword_key + " "
        if padded_keyword in padded_text:
            return True
    return False


def alias_is_main_entity(name_key: str, aliases: list[str], allowed_prefixes: list[str]) -> bool:
    # The brand must be the main subject of the title, not just a location hint.
    # Example: "WinMart Vincom" is OK, but "C7 Coffee - WinMart" is not.
    for alias in aliases:
        alias_key = normalize_for_match(alias)
        if not alias_key:
            continue

        if name_key == alias_key:
            return True
        if name_key.startswith(alias_key + " "):
            return True
        if alias_key.endswith("+") and name_key.startswith(alias_key):
            return True
        if alias_key.endswith("+"):
            alias_without_plus = alias_key[:-1].rstrip()
            if alias_without_plus and name_key.startswith(alias_without_plus + " +"):
                return True

        for prefix in allowed_prefixes:
            prefix_key = normalize_for_match(prefix)
            if not prefix_key:
                continue

            expected_start = prefix_key + " " + alias_key
            if name_key == expected_start:
                return True
            if name_key.startswith(expected_start + " "):
                return True
            if alias_key.endswith("+") and name_key.startswith(expected_start):
                return True
            if alias_key.endswith("+"):
                expected_without_plus = (prefix_key + " " + alias_key[:-1]).rstrip()
                if name_key.startswith(expected_without_plus + " +"):
                    return True

    return False


def country_reject_reason(row: dict[str, str], defaults: dict[str, Any]) -> str:
    # Bbox VN vẫn có thể bao một phần Thái/Campuchia, nên cần check text country.
    text = ""
    text += " " + row.get("name", "")
    text += " " + row.get("address", "")
    text += " " + row.get("city", "")
    text += " " + row.get("province", "")
    text_key = normalize_for_match(text)
    keywords = defaults.get("foreign_country_keywords", [])
    if has_any_keyword(text_key, keywords):
        return "outside_vietnam_country_keyword"
    return ""


def normalize_source_row(raw: dict[str, str], source: SourceFile, row_number: int, pipeline_run_id: str) -> tuple[dict[str, str] | None, str]:
    name = clean_cell(raw.get("name") or raw.get("title"))
    address = clean_cell(raw.get("address") or raw.get("complete_address"))
    if not name:
        return None, "missing_name"
    if not address:
        return None, "missing_address"

    lat_raw = clean_cell(raw.get("lat") or raw.get("latitude"))
    lng_raw = clean_cell(raw.get("lng") or raw.get("longitude"))
    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
    except ValueError:
        return None, "invalid_or_missing_coord"

    if lat == 0 and lng == 0:
        return None, "invalid_or_missing_coord"
    if lat < 8 or lat > 24 or lng < 102 or lng > 115:
        return None, "coord_outside_vietnam_bounds"

    parsed_city, parsed_province = parse_city_province(address)
    city = canonical_location(raw.get("city", "")) or parsed_city
    province = canonical_location(raw.get("province", "")) or parsed_province

    row = {
        "brand_id": "",
        "name": name,
        "address": address,
        "city": city,
        "province": province,
        "lat": str(lat),
        "lng": str(lng),
        "brand_slug": source.brand_slug,
        "brand_name": source.brand_name,
        "source": source.source,
        "source_file": str(source.path.relative_to(PROJECT_ROOT)),
        "source_row_number": str(row_number),
        "crawl_date": "",
        "pipeline_run_id": pipeline_run_id,
    }
    return row, ""


def classify_row(row: dict[str, str], policy: dict[str, Any], defaults: dict[str, Any]) -> tuple[str, str]:
    country_reason = country_reject_reason(row, defaults)
    if country_reason:
        return "reject_high_confidence", country_reason

    name_key = normalize_for_match(row.get("name", ""))
    address_key = normalize_for_match(row.get("address", ""))
    full_key = normalize_for_match(row.get("name", "") + " " + row.get("address", ""))

    if has_any_keyword(name_key, policy.get("blacklist", [])):
        return "reject_high_confidence", "brand_blacklist_in_name"
    if has_any_keyword(full_key, policy.get("reject_keywords", [])):
        return "reject_high_confidence", "brand_specific_reject_keyword"
    required_positive_keywords = policy.get("required_positive_keywords", [])
    if required_positive_keywords:
        if not has_any_keyword(full_key, required_positive_keywords):
            return "reject_high_confidence", "brand_missing_required_positive_keyword"

    aliases = policy.get("aliases", [])
    alias_in_name = has_any_keyword(name_key, aliases)
    alias_in_address = has_any_keyword(address_key, aliases)

    container_rejects = policy.get("container_reject_keywords", [])
    if policy.get("container_brand"):
        if has_any_keyword(name_key, container_rejects):
            return "reject_high_confidence", "container_tenant_or_infrastructure"
        keep_prefixes = policy.get("container_keep_prefixes", [])
        for prefix in keep_prefixes:
            prefix_key = normalize_for_match(prefix)
            if prefix_key and name_key.startswith(prefix_key):
                return "keep", "container_name_matches_keep_prefix"
        if alias_in_name:
            return "suspect_review", "container_brand_mentioned_but_name_not_main_entity"
        return "reject_high_confidence", "container_brand_alias_not_found"

    if alias_in_name and policy.get("require_alias_as_main_entity"):
        allowed_prefixes = policy.get("main_entity_allowed_prefixes", [])
        if not alias_is_main_entity(name_key, aliases, allowed_prefixes):
            return "suspect_review", "brand_alias_mentioned_but_name_not_main_entity"

    non_store_keywords = defaults.get("non_store_keywords", [])
    if has_any_phrase_keyword(full_key, non_store_keywords):
        action = policy.get("non_store_action", "suspect")
        if action == "reject":
            return "reject_high_confidence", "non_store_keyword"
        return "suspect_review", "possible_non_store_keyword"

    if alias_in_name:
        return "keep", "brand_alias_found_in_name"
    if alias_in_address:
        return "suspect_review", "brand_alias_only_found_in_address"
    return "reject_high_confidence", "brand_alias_not_found"


def choose_better_row(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    left_score = 0
    right_score = 0
    for field in ["city", "province", "address", "name"]:
        left_score += len(left.get(field, ""))
        right_score += len(right.get(field, ""))
    if right_score > left_score:
        return right
    return left


def is_duplicate(left: dict[str, str], right: dict[str, str]) -> bool:
    left_name = normalize_for_match(left.get("name", ""))
    right_name = normalize_for_match(right.get("name", ""))
    left_address = normalize_for_match(left.get("address", ""))
    right_address = normalize_for_match(right.get("address", ""))

    if left_name == right_name and left_address == right_address:
        return True

    lat1 = float(left["lat"])
    lng1 = float(left["lng"])
    lat2 = float(right["lat"])
    lng2 = float(right["lng"])
    distance = haversine_m(lat1, lng1, lat2, lng2)

    if left_address and left_address == right_address and distance < 50:
        return True

    if distance < 35:
        name_score = text_similarity(left.get("name", ""), right.get("name", ""))
        address_score = text_similarity(left.get("address", ""), right.get("address", ""))
        if name_score >= 90 and address_score >= 85:
            return True
    return False


def exact_duplicate_key(row: dict[str, str]) -> str:
    name_key = normalize_for_match(row.get("name", ""))
    address_key = normalize_for_match(row.get("address", ""))
    return name_key + "|" + address_key


def address_duplicate_key(row: dict[str, str]) -> str:
    return normalize_for_match(row.get("address", ""))


def coord_bucket(row: dict[str, str]) -> tuple[int, int]:
    # 0.001 degree ~ 111m latitude. Dedupe fuzzy chỉ cần xem bucket lân cận.
    lat = float(row["lat"])
    lng = float(row["lng"])
    return int(lat * 1000), int(lng * 1000)


def nearby_buckets(bucket: tuple[int, int]) -> list[tuple[int, int]]:
    buckets = []
    base_lat, base_lng = bucket
    for lat_delta in [-1, 0, 1]:
        for lng_delta in [-1, 0, 1]:
            buckets.append((base_lat + lat_delta, base_lng + lng_delta))
    return buckets


def register_row_index(
    index: int,
    row: dict[str, str],
    exact_index: dict[str, int],
    address_index: dict[str, list[int]],
    spatial_index: dict[tuple[int, int], list[int]],
) -> None:
    exact_key = exact_duplicate_key(row)
    if exact_key:
        exact_index[exact_key] = index

    address_key = address_duplicate_key(row)
    if address_key:
        if address_key not in address_index:
            address_index[address_key] = []
        address_index[address_key].append(index)

    bucket = coord_bucket(row)
    if bucket not in spatial_index:
        spatial_index[bucket] = []
    spatial_index[bucket].append(index)


def find_duplicate_index(
    row: dict[str, str],
    kept: list[dict[str, str]],
    exact_index: dict[str, int],
    address_index: dict[str, list[int]],
    spatial_index: dict[tuple[int, int], list[int]],
) -> int:
    exact_key = exact_duplicate_key(row)
    if exact_key in exact_index:
        return exact_index[exact_key]

    address_key = address_duplicate_key(row)
    for index in address_index.get(address_key, []):
        if is_duplicate(row, kept[index]):
            return index

    bucket = coord_bucket(row)
    for nearby_bucket in nearby_buckets(bucket):
        for index in spatial_index.get(nearby_bucket, []):
            if is_duplicate(row, kept[index]):
                return index
    return -1


def dedupe_keep_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    kept: list[dict[str, str]] = []
    duplicates: list[dict[str, str]] = []
    exact_index: dict[str, int] = {}
    address_index: dict[str, list[int]] = {}
    spatial_index: dict[tuple[int, int], list[int]] = {}

    for row in rows:
        duplicate_index = find_duplicate_index(row, kept, exact_index, address_index, spatial_index)

        if duplicate_index == -1:
            kept.append(row)
            register_row_index(len(kept) - 1, row, exact_index, address_index, spatial_index)
            continue

        # Giữ dòng xuất hiện trước để index dedupe ổn định; dòng sau đi vào audit duplicate.
        duplicate = row.copy()
        duplicate["qa_status"] = "reject_high_confidence"
        duplicate["qa_reason"] = "duplicate_within_brand"
        duplicates.append(duplicate)

    return kept, duplicates


def load_phase_rows(source: SourceFile, pipeline_run_id: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    raw_rows = read_csv_rows(source.path)
    normalized_rows: list[dict[str, str]] = []
    rejected_rows: list[dict[str, str]] = []

    row_number = 2
    for raw in raw_rows:
        row, reason = normalize_source_row(raw, source, row_number, pipeline_run_id)
        if row is None:
            rejected = {
                "brand_slug": source.brand_slug,
                "brand_name": source.brand_name,
                "source": source.source,
                "source_file": str(source.path.relative_to(PROJECT_ROOT)),
                "source_row_number": str(row_number),
                "crawl_date": "",
                "pipeline_run_id": pipeline_run_id,
                "qa_status": "reject_high_confidence",
                "qa_reason": reason,
            }
            for field in FINAL_FIELDS:
                rejected[field] = clean_cell(raw.get(field, ""))
            rejected_rows.append(rejected)
        else:
            normalized_rows.append(row)
        row_number += 1
    return normalized_rows, rejected_rows


def build_audit_row(brand_slug: str, brand_name: str) -> dict[str, Any]:
    return {
        "brand_slug": brand_slug,
        "brand_name": brand_name,
        "raw_rows": 0,
        "normalized_rows": 0,
        "keep_rows": 0,
        "suspect_rows": 0,
        "reject_rows": 0,
        "duplicate_rows": 0,
    }


def run_pipeline(
    policy_file: Path,
    include_gosom_winmart_plus: bool,
    pipeline_run_id: str,
    include_gosom_topups: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    policy_payload = read_json(policy_file)
    defaults = policy_payload.get("default", {})
    policies = build_brand_policies(policy_payload)
    sources = discover_source_files()

    raw_by_brand: dict[str, list[dict[str, str]]] = {}
    audit: dict[str, dict[str, Any]] = {}
    rejected_rows: list[dict[str, str]] = []

    for source in sources:
        audit_row = audit.setdefault(source.brand_slug, build_audit_row(source.brand_slug, source.brand_name))
        source_rows = read_csv_rows(source.path)
        audit_row["raw_rows"] += len(source_rows)
        normalized, rejected = load_phase_rows(source, pipeline_run_id)
        audit_row["normalized_rows"] += len(normalized)
        audit_row["reject_rows"] += len(rejected)
        rejected_rows.extend(rejected)
        brand_rows = raw_by_brand.setdefault(source.brand_slug, [])
        for row in normalized:
            brand_rows.append(row)

    gosom_sources: list[SourceFile] = []
    if include_gosom_topups:
        gosom_sources = discover_gosom_topup_files()
    elif include_gosom_winmart_plus:
        gosom_sources = [SourceFile("gosom_topup", "winmart_plus", "WinMart+", GOSOM_WINMART_PLUS_FILE)]

    for source in gosom_sources:
        audit_row = audit.setdefault(source.brand_slug, build_audit_row(source.brand_slug, source.brand_name))
        if source.path.exists():
            source_rows = read_csv_rows(source.path)
            audit_row["raw_rows"] += len(source_rows)
            normalized, rejected = load_phase_rows(source, pipeline_run_id)
            audit_row["normalized_rows"] += len(normalized)
            audit_row["reject_rows"] += len(rejected)
            rejected_rows.extend(rejected)
            brand_rows = raw_by_brand.setdefault(source.brand_slug, [])
            for row in normalized:
                brand_rows.append(row)

    all_keep_rows: list[dict[str, str]] = []
    suspect_rows: list[dict[str, str]] = []

    for brand_slug in sorted(raw_by_brand.keys()):
        brand_rows = raw_by_brand[brand_slug]
        brand_name = brand_rows[0].get("brand_name", slug_to_brand_name(brand_slug))
        audit_row = audit.setdefault(brand_slug, build_audit_row(brand_slug, brand_name))
        policy = get_policy(brand_slug, policies, defaults)

        keep_candidates: list[dict[str, str]] = []
        for row in brand_rows:
            status, reason = classify_row(row, policy, defaults)
            row["qa_status"] = status
            row["qa_reason"] = reason
            if status == "keep":
                keep_candidates.append(row)
            elif status == "suspect_review":
                suspect_rows.append(row)
                audit_row["suspect_rows"] += 1
            else:
                rejected_rows.append(row)
                audit_row["reject_rows"] += 1

        deduped_keep, duplicate_rows = dedupe_keep_rows(keep_candidates)
        audit_row["duplicate_rows"] += len(duplicate_rows)
        audit_row["keep_rows"] += len(deduped_keep)
        audit_row["reject_rows"] += len(duplicate_rows)

        for duplicate in duplicate_rows:
            rejected_rows.append(duplicate)
        for row in deduped_keep:
            all_keep_rows.append(row)

    audit_rows = []
    for brand_slug in sorted(audit.keys()):
        audit_rows.append(audit[brand_slug])

    return {
        "keep_rows": all_keep_rows,
        "suspect_rows": suspect_rows,
        "rejected_rows": rejected_rows,
        "audit_rows": audit_rows,
    }


def sort_output_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def sort_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
        return (
            row.get("brand_slug", ""),
            normalize_for_match(row.get("province", "")),
            normalize_for_match(row.get("city", "")),
            normalize_for_match(row.get("name", "")),
            normalize_for_match(row.get("address", "")),
        )

    return sorted(rows, key=sort_key)


def write_outputs(output_dir: Path, result: dict[str, list[dict[str, Any]]]) -> None:
    keep_rows = sort_output_rows(result["keep_rows"])
    suspect_rows = sort_output_rows(result["suspect_rows"])
    rejected_rows = sort_output_rows(result["rejected_rows"])
    audit_rows = result["audit_rows"]

    by_brand: dict[str, list[dict[str, str]]] = {}
    for row in keep_rows:
        brand_slug = row["brand_slug"]
        brand_rows = by_brand.setdefault(brand_slug, [])
        brand_rows.append(row)

    for brand_slug in sorted(by_brand.keys()):
        path = output_dir / "by_brand" / f"{brand_slug}.csv"
        write_csv(path, by_brand[brand_slug], FINAL_FIELDS)

    winmart_family_rows: list[dict[str, str]] = []
    for slug in ["winmart", "winmart_plus"]:
        for row in by_brand.get(slug, []):
            winmart_family_rows.append(row)
    if winmart_family_rows:
        write_csv(output_dir / "by_group" / "winmart_family.csv", winmart_family_rows, FINAL_FIELDS)

    write_csv(output_dir / "master_keep.csv", keep_rows, FINAL_FIELDS)
    write_csv(output_dir / "qa_suspect_rows.csv", suspect_rows, META_FIELDS + FINAL_FIELDS)
    write_csv(output_dir / "qa_rejected_rows.csv", rejected_rows, META_FIELDS + FINAL_FIELDS)
    write_csv(output_dir / "audit_summary.csv", audit_rows, AUDIT_FIELDS)


def print_summary(result: dict[str, list[dict[str, Any]]]) -> None:
    print("keep_rows=", len(result["keep_rows"]))
    print("suspect_rows=", len(result["suspect_rows"]))
    print("rejected_rows=", len(result["rejected_rows"]))
    print("brand_count=", len(result["audit_rows"]))
    print("top audit rows:")
    sorted_audit = sorted(result["audit_rows"], key=lambda row: int(row["reject_rows"]) + int(row["suspect_rows"]), reverse=True)
    for row in sorted_audit[:12]:
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay raw Phase 1/2 through a readable rule-based clean/QA pipeline.")
    parser.add_argument("--output", default="pipeline/output/rule_based", help="Output folder for new pipeline artifacts.")
    parser.add_argument("--policy", default=str(POLICY_FILE), help="Brand policy JSON path.")
    parser.add_argument("--run-id", default="", help="Pipeline run id. Defaults to current timestamp.")
    parser.add_argument("--include-gosom-winmart-plus", action="store_true", help="Also merge gosom WinMart+ top-up candidates.")
    parser.add_argument("--include-gosom-topups", action="store_true", help="Merge every *_gosom_raw.csv found under pipeline/output and legacy phase_1_2 top-up folders.")
    parser.add_argument("--no-write", action="store_true", help="Run pipeline and print summary without writing output files.")
    args = parser.parse_args()

    pipeline_run_id = args.run_id
    if not pipeline_run_id:
        pipeline_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    policy_file = Path(args.policy)
    result = run_pipeline(
        policy_file,
        args.include_gosom_winmart_plus,
        pipeline_run_id,
        include_gosom_topups=args.include_gosom_topups,
    )
    print_summary(result)

    if args.no_write:
        print("no_write=1 output not written")
        return

    output_dir = (PROJECT_ROOT / args.output).resolve()
    write_outputs(output_dir, result)
    print("output=", output_dir)


if __name__ == "__main__":
    main()
