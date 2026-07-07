from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"


def main() -> None:
    brands = "Circle K,Highlands Coffee,KFC,Lotteria"
    command = [
        sys.executable,
        str(PIPELINE_DIR / "crawler" / "run_gosom_grid_crawl.py"),
        "--chains",
        brands,
        "--output",
        str(PIPELINE_DIR / "output" / "crawl_priority"),
        "--concurrency",
        "1",
        "--depth",
        "1",
    ]
    print(" ".join(command))
    raise SystemExit(subprocess.call(command, cwd=PROJECT_ROOT))


if __name__ == "__main__":
    main()
