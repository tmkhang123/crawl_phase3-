from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
DEFAULT_OUTPUT = PIPELINE_DIR / "config" / "regions" / "grid_regions_dense.json"


# Bounding boxes are intentionally broad city/metro boxes. They are meant for
# coverage boosting, not administrative-boundary accuracy.
CITY_BOXES: dict[str, dict[str, float | str]] = {
    "hcm": {"name": "TP.HCM", "lat_min": 10.35, "lat_max": 11.15, "lng_min": 106.35, "lng_max": 107.05},
    "hn": {"name": "Hà Nội", "lat_min": 20.75, "lat_max": 21.35, "lng_min": 105.25, "lng_max": 106.15},
    "binh_duong": {"name": "Bình Dương", "lat_min": 10.82, "lat_max": 11.35, "lng_min": 106.55, "lng_max": 107.05},
    "dong_nai": {"name": "Đồng Nai", "lat_min": 10.65, "lat_max": 11.25, "lng_min": 106.75, "lng_max": 107.45},
    "danang": {"name": "Đà Nẵng", "lat_min": 15.95, "lat_max": 16.18, "lng_min": 108.05, "lng_max": 108.35},
    "haiphong": {"name": "Hải Phòng", "lat_min": 20.65, "lat_max": 21.05, "lng_min": 106.45, "lng_max": 107.05},
    "cantho": {"name": "Cần Thơ", "lat_min": 9.90, "lat_max": 10.20, "lng_min": 105.62, "lng_max": 105.90},
}

CITY_BOXES.update(
    {
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
)

DEFAULT_CITIES = [
    "hcm",
    "hn",
    "binh_duong",
    "dong_nai",
    "danang",
    "haiphong",
    "cantho",
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


def km_to_lat_degrees(km: float) -> float:
    return km / 111.32


def km_to_lng_degrees(km: float, lat: float) -> float:
    return km / (111.32 * max(0.2, math.cos(math.radians(lat))))


def generate_city_grid(city_key: str, cell_km: float, zoom: float) -> list[dict[str, object]]:
    box = CITY_BOXES[city_key]
    lat_min = float(box["lat_min"])
    lat_max = float(box["lat_max"])
    lng_min = float(box["lng_min"])
    lng_max = float(box["lng_max"])
    city_name = str(box["name"])

    lat_step = km_to_lat_degrees(cell_km)
    regions: list[dict[str, object]] = []
    row = 0
    lat = lat_min + lat_step / 2
    while lat <= lat_max:
        lng_step = km_to_lng_degrees(cell_km, lat)
        col = 0
        lng = lng_min + lng_step / 2
        while lng <= lng_max:
            regions.append(
                {
                    "id": f"{city_key}_{row:03d}_{col:03d}",
                    "label": f"{city_key}_{row:03d}_{col:03d}_{city_name}",
                    "city_key": city_key,
                    "city_name": city_name,
                    "lat": round(lat, 6),
                    "lng": round(lng, 6),
                    "zoom": zoom,
                    "cell_km": cell_km,
                }
            )
            col += 1
            lng += lng_step
        row += 1
        lat += lat_step
    return regions


def generate_regions(cities: list[str], cell_km: float, zoom: float) -> list[dict[str, object]]:
    regions: list[dict[str, object]] = []
    for city in cities:
        if city not in CITY_BOXES:
            raise SystemExit(f"Unknown city {city!r}. Choices: {', '.join(sorted(CITY_BOXES))}")
        regions.extend(generate_city_grid(city, cell_km, zoom))
    return regions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Google Maps viewport grid regions for dense-city coverage boosting.")
    parser.add_argument("--cities", default=",".join(DEFAULT_CITIES), help=f"Comma-separated city keys. Choices: {', '.join(sorted(CITY_BOXES))}")
    parser.add_argument("--cell-km", type=float, default=4.0, help="Approximate grid cell size in kilometers. Use 2-3 for deeper dense-city recrawl.")
    parser.add_argument("--zoom", type=float, default=15.0, help="Google Maps viewport zoom used by the UI crawler.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cities = [item.strip() for item in args.cities.split(",") if item.strip()]
    if args.cell_km <= 0:
        raise SystemExit("--cell-km must be positive.")
    regions = generate_regions(cities, args.cell_km, args.zoom)
    payload = {
        "kind": "gmaps_grid_regions_v1",
        "cell_km": args.cell_km,
        "zoom": args.zoom,
        "cities": cities,
        "region_count": len(regions),
        "regions": regions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote={args.output}")
    print(f"regions={len(regions)} cities={','.join(cities)} cell_km={args.cell_km:g} zoom={args.zoom:g}")


if __name__ == "__main__":
    main()
