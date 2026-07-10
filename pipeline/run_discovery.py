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
DEFAULT_RADIUS_METERS = 25_000

PROVINCE_CENTERS: list[tuple[str, float, float]] = [
    ("Hà Nội", 21.0285, 105.8542),
    ("TP.HCM", 10.8231, 106.6297),
    ("Cần Thơ", 10.0452, 105.7469),
    ("Đà Nẵng", 16.0471, 108.2068),
    ("Hải Phòng", 20.8449, 106.6881),
    ("An Giang", 10.5216, 105.1259),
    ("Bà Rịa - Vũng Tàu", 10.5417, 107.2429),
    ("Bắc Giang", 21.2731, 106.1946),
    ("Bắc Kạn", 22.1470, 105.8348),
    ("Bạc Liêu", 9.2940, 105.7278),
    ("Bắc Ninh", 21.1861, 106.0763),
    ("Bến Tre", 10.2434, 106.3756),
    ("Bình Dương", 10.9804, 106.6519),
    ("Bình Định", 13.7820, 109.2198),
    ("Bình Phước", 11.7512, 106.7235),
    ("Bình Thuận", 10.9333, 108.1000),
    ("Cà Mau", 9.1768, 105.1524),
    ("Cao Bằng", 22.6666, 106.2639),
    ("Đắk Lắk", 12.6667, 108.0500),
    ("Đắk Nông", 12.0042, 107.6907),
    ("Điện Biên", 21.3860, 103.0230),
    ("Đồng Nai", 10.9574, 106.8427),
    ("Đồng Tháp", 10.4938, 105.6882),
    ("Gia Lai", 13.9833, 108.0000),
    ("Hà Giang", 22.8233, 104.9836),
    ("Hà Nam", 20.5411, 105.9139),
    ("Hà Tĩnh", 18.3559, 105.8877),
    ("Hải Dương", 20.9373, 106.3146),
    ("Hậu Giang", 9.7845, 105.4701),
    ("Hòa Bình", 20.8172, 105.3376),
    ("Hưng Yên", 20.6464, 106.0511),
    ("Khánh Hòa", 12.2388, 109.1967),
    ("Kiên Giang", 10.0125, 105.0809),
    ("Kon Tum", 14.3545, 108.0076),
    ("Lai Châu", 22.3964, 103.4707),
    ("Lâm Đồng", 11.9404, 108.4583),
    ("Lạng Sơn", 21.8537, 106.7615),
    ("Lào Cai", 22.4809, 103.9755),
    ("Long An", 10.6956, 106.2431),
    ("Nam Định", 20.4388, 106.1621),
    ("Nghệ An", 18.6796, 105.6813),
    ("Ninh Bình", 20.2506, 105.9745),
    ("Ninh Thuận", 11.5643, 108.9886),
    ("Phú Thọ", 21.3227, 105.4019),
    ("Phú Yên", 13.0955, 109.3209),
    ("Quảng Bình", 17.4689, 106.6223),
    ("Quảng Nam", 15.5736, 108.4740),
    ("Quảng Ngãi", 15.1214, 108.8044),
    ("Quảng Ninh", 20.9712, 107.0448),
    ("Quảng Trị", 16.7500, 107.2000),
    ("Sóc Trăng", 9.6025, 105.9739),
    ("Sơn La", 21.3270, 103.9141),
    ("Tây Ninh", 11.3351, 106.1099),
    ("Thái Bình", 20.4463, 106.3366),
    ("Thái Nguyên", 21.5942, 105.8482),
    ("Thanh Hóa", 19.8067, 105.7852),
    ("Thừa Thiên Huế", 16.4637, 107.5909),
    ("Tiền Giang", 10.4493, 106.3421),
    ("Trà Vinh", 9.9347, 106.3453),
    ("Tuyên Quang", 21.8233, 105.2181),
    ("Vĩnh Long", 10.2537, 105.9722),
    ("Vĩnh Phúc", 21.3089, 105.6049),
    ("Yên Bái", 21.7050, 104.8750),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run light gosom discovery, then build a reusable crawl policy plan."
    )
    parser.add_argument("--chains", default="", help='Optional comma-separated brands. Empty = phase2 registry.')
    parser.add_argument(
        "--coverage-mode",
        choices=("national-lite", "center"),
        default="national-lite",
        help="national-lite = 3 geo/radius searches per province; center = old city-center discovery.",
    )
    parser.add_argument("--cities", default=DEFAULT_DISCOVERY_CITIES)
    parser.add_argument("--radius", type=float, default=DEFAULT_RADIUS_METERS)
    parser.add_argument("--output", type=Path, default=PIPELINE_DIR / "output" / "discovery")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--proxy-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_national_lite_geo_file(output_file: Path) -> Path:
    regions: list[dict[str, object]] = []

    for province, lat, lng in PROVINCE_CENTERS:
        points = [
            ("center", lat, lng),
            ("north_east", lat + 0.18, lng + 0.18),
            ("south_west", lat - 0.18, lng - 0.18),
        ]
        for suffix, point_lat, point_lng in points:
            region_id = province.lower().replace(" ", "_").replace("-", "_") + "_" + suffix
            regions.append(
                {
                    "id": region_id,
                    "label": f"{province} {suffix}",
                    "province": province,
                    "city_name": province,
                    "city_key": "national_lite_geo",
                    "lat": round(point_lat, 6),
                    "lng": round(point_lng, 6),
                }
            )

    payload = {
        "kind": "national_lite_geo_regions_v1",
        "province_count": len(PROVINCE_CENTERS),
        "points_per_province": 3,
        "region_count": len(regions),
        "regions": regions,
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"national_lite_geo_provinces={len(PROVINCE_CENTERS)} national_lite_geo_regions={len(regions)}")
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
        national_lite_file = args.output / "national_lite_geo_regions.json"
        build_national_lite_geo_file(national_lite_file)
        command.extend(
            [
                "--region-mode",
                "geo-list",
                "--geo-regions",
                str(national_lite_file),
                "--radius",
                str(args.radius),
            ]
        )
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
