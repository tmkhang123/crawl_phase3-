from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLEAN_DIR = ROOT / "notebook" / "output_clean_phase1_phase2" / "by_brand"
DEFAULT_OUTPUT = ROOT / "raw" / "gosom_priority_coverage_benchmark.csv"
PRIORITY_BRANDS = ["WinMart+", "WinMart", "Circle K", "Highlands Coffee", "KFC", "Lotteria"]

FIELDS = [
    "brand",
    "expected_min_count",
    "source_note",
    "current_clean_count",
    "gosom_added_count",
    "final_candidate_count",
    "coverage_ratio",
]


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


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as source:
        return list(csv.DictReader(source))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def stable_key(row: dict[str, str]) -> tuple[str, ...]:
    cid = row.get("cid", "").strip()
    place_id = row.get("place_id", "").strip()
    data_id = row.get("data_id", "").strip()
    if cid or place_id or data_id:
        return ("id", cid, place_id, data_id)
    title = row.get("title") or row.get("name") or ""
    address = row.get("address", "")
    lat = row.get("latitude") or row.get("lat") or ""
    lng = row.get("longitude") or row.get("lng") or ""
    return ("text", normalize_text(title), normalize_text(address), lat.strip(), lng.strip())


def current_clean_rows(clean_dir: Path, brand: str) -> list[dict[str, str]]:
    return read_rows(clean_dir / f"{slugify(brand)}.csv")


def gosom_rows(gosom_outputs: list[Path], brand: str) -> list[dict[str, str]]:
    slug = slugify(brand)
    rows: list[dict[str, str]] = []
    for output in gosom_outputs:
        for path in output.rglob(f"{slug}_gosom_raw.csv"):
            if ".rejected" in path.name:
                continue
            rows.extend(read_rows(path))
    return rows


def load_existing(path: Path) -> dict[str, dict[str, str]]:
    existing: dict[str, dict[str, str]] = {}
    for row in read_rows(path):
        brand = row.get("brand", "").strip()
        if brand:
            existing[brand.lower()] = row
    return existing


def coverage_ratio(final_count: int, expected: str) -> str:
    expected = (expected or "").strip()
    if not expected:
        return ""
    try:
        expected_value = float(expected.replace(",", ""))
    except ValueError:
        return ""
    if expected_value <= 0:
        return ""
    return f"{final_count / expected_value:.3f}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build manual coverage benchmark table for gosom priority top-up brands.")
    parser.add_argument("--gosom-output", action="append", type=Path, default=[], help="Gosom output root. Can be passed multiple times.")
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--brands", default=",".join(PRIORITY_BRANDS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    brands = [item.strip() for item in args.brands.split(",") if item.strip()]
    existing = load_existing(args.output)
    output_rows: list[dict[str, str]] = []
    for brand in brands:
        previous = existing.get(brand.lower(), {})
        clean = current_clean_rows(args.clean_dir, brand)
        gosom = gosom_rows(args.gosom_output, brand)
        seen = {stable_key(row) for row in clean}
        added = 0
        for row in gosom:
            key = stable_key(row)
            if key in seen:
                continue
            seen.add(key)
            added += 1
        final_count = len(seen)
        expected = previous.get("expected_min_count", "")
        output_rows.append(
            {
                "brand": brand,
                "expected_min_count": expected,
                "source_note": previous.get("source_note", ""),
                "current_clean_count": str(len(clean)),
                "gosom_added_count": str(added),
                "final_candidate_count": str(final_count),
                "coverage_ratio": coverage_ratio(final_count, expected),
            }
        )
    write_rows(args.output, output_rows)
    print(f"wrote={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
