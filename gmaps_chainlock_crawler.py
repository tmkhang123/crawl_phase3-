from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import re
import shutil
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth


FIELDNAMES = ["brand_id", "name", "address", "city", "province", "lat", "lng"]
DEFAULT_REGISTRY = Path(__file__).resolve().parent / "brand_registry.csv"
DEFAULT_REGIONS = Path(__file__).resolve().parent / "districts.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output"
DEFAULT_ENV_FILES: list[Path] = []

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def strip_accents(value: str | None) -> str:
    value = (value or "").replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value)
        if unicodedata.category(ch) != "Mn"
    )


def norm_words(value: str | None) -> str:
    value = strip_accents(value).lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9+\s]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def norm_compact(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", norm_words(value))


def registry_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9+]+", "", norm_words(value))


def clean_filename(value: str) -> str:
    value = strip_accents(value).lower()
    value = re.sub(r'[\\/*?:"<>|]', "", value)
    value = value.replace("+", "_plus")
    value = re.sub(r"[^a-z0-9_!-]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def parse_pipe_list(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split("|") if item.strip()]


def clean_coord(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return str(float(value))
    except ValueError:
        return ""


def coord_key(lat: str | None, lng: str | None) -> str:
    lat = clean_coord(lat)
    lng = clean_coord(lng)
    if not lat or not lng:
        return ""
    return f"{float(lat):.6f},{float(lng):.6f}"


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def short_error(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        return exc.__class__.__name__
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line[:240] if first_line else exc.__class__.__name__


def name_address_key(name: str | None, address: str | None) -> str:
    address_key = norm_compact(address)
    if not address_key:
        return ""
    return f"{norm_compact(name)[:80]}|{address_key}"


def extract_coords_from_url(url: str | None) -> tuple[str, str]:
    if not url:
        return "", ""
    match = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url)
    if match:
        return match.group(1), match.group(2)
    match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if match:
        return match.group(1), match.group(2)
    return "", ""


def parse_vietnam_address(address: str) -> tuple[str, str, str]:
    if not address:
        return "", "", ""
    clean = re.sub(r",\s*(Vietnam|Việt Nam)$", "", address.strip(), flags=re.I)
    parts = [p.strip() for p in clean.split(",") if p.strip()]
    province = parts[-1] if len(parts) >= 1 else ""
    city = parts[-2] if len(parts) >= 2 else ""
    ward = parts[-3] if len(parts) >= 3 else ""
    province = re.sub(r"\s+\d{5,6}$", "", province).strip()
    return ward, city, province


@dataclass
class ChainConfig:
    target_chain: str
    search_query: str
    name_aliases: list[str]
    name_blacklist: list[str]
    expected_count: str
    concurrency: int
    priority: int
    notes: str = ""

    @property
    def aliases_compact(self) -> list[str]:
        aliases = self.name_aliases or [self.target_chain]
        return [norm_compact(alias) for alias in aliases if norm_compact(alias)]

    @property
    def blacklist_compact(self) -> list[str]:
        return [norm_compact(item) for item in self.name_blacklist if norm_compact(item)]


@dataclass
class RegionStats:
    candidates_seen: int = 0
    invalid_name_skipped: int = 0
    duplicates_skipped: int = 0
    details_opened: int = 0
    stores_saved: int = 0
    errors: int = 0
    regions_done: int = 0
    elapsed_seconds: float = 0.0
    blocked: int = 0
    captcha_detected: int = 0
    feed_timeout: int = 0
    proxy_enabled: int = 0
    proxy_age_seconds: float = 0.0

    def add(self, other: "RegionStats") -> None:
        self.candidates_seen += other.candidates_seen
        self.invalid_name_skipped += other.invalid_name_skipped
        self.duplicates_skipped += other.duplicates_skipped
        self.details_opened += other.details_opened
        self.stores_saved += other.stores_saved
        self.errors += other.errors
        self.regions_done += other.regions_done
        self.elapsed_seconds += other.elapsed_seconds
        self.blocked += other.blocked
        self.captcha_detected += other.captcha_detected
        self.feed_timeout += other.feed_timeout
        self.proxy_enabled = max(self.proxy_enabled, other.proxy_enabled)
        self.proxy_age_seconds = max(self.proxy_age_seconds, other.proxy_age_seconds)


@dataclass
class ProgressTracker:
    total_regions: int
    initial_completed: int
    completed: int
    start_time: float = field(default_factory=time.monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def mark_completed(self) -> dict[str, float]:
        async with self.lock:
            self.completed += 1
            done = self.initial_completed + self.completed
            elapsed = max(0.001, time.monotonic() - self.start_time)
            rate_per_hour = self.completed / elapsed * 3600
            remaining = max(0, self.total_regions - done)
            eta_seconds = remaining / (self.completed / elapsed) if self.completed > 0 else 0
            percent = (done / self.total_regions * 100) if self.total_regions else 100.0
            return {
                "done": float(done),
                "total": float(self.total_regions),
                "percent": percent,
                "rate_per_hour": rate_per_hour,
                "eta_seconds": eta_seconds,
            }


@dataclass
class DeferredRetries:
    items: list[tuple[str, int]] = field(default_factory=list)
    seen_regions: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add(self, region: str, retry_count: int) -> None:
        async with self.lock:
            if region in self.seen_regions:
                return
            self.seen_regions.add(region)
            self.items.append((region, retry_count))

    async def snapshot(self) -> list[tuple[str, int]]:
        async with self.lock:
            return list(self.items)


@dataclass
class SeenState:
    place_urls: set[str] = field(default_factory=set)
    coord_keys: set[str] = field(default_factory=set)
    name_address_keys: set[str] = field(default_factory=set)
    reserved_place_urls: set[str] = field(default_factory=set)
    reserved_coord_keys: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def reserve_candidate(self, place_url: str, lat: str, lng: str) -> bool:
        ck = coord_key(lat, lng)
        async with self.lock:
            if place_url and (place_url in self.place_urls or place_url in self.reserved_place_urls):
                return False
            if ck and (ck in self.coord_keys or ck in self.reserved_coord_keys):
                return False
            if place_url:
                self.reserved_place_urls.add(place_url)
            if ck:
                self.reserved_coord_keys.add(ck)
            return True

    async def release_candidate(self, place_url: str, lat: str, lng: str) -> None:
        ck = coord_key(lat, lng)
        async with self.lock:
            if place_url:
                self.reserved_place_urls.discard(place_url)
            if ck:
                self.reserved_coord_keys.discard(ck)

    async def commit_store(self, place_url: str, lat: str, lng: str, key: str) -> bool:
        ck = coord_key(lat, lng)
        async with self.lock:
            if key and key in self.name_address_keys:
                if place_url:
                    self.place_urls.add(place_url)
                if ck:
                    self.coord_keys.add(ck)
                return False
            if place_url:
                self.place_urls.add(place_url)
            if ck:
                self.coord_keys.add(ck)
            if key:
                self.name_address_keys.add(key)
            return True

    async def snapshot(self) -> dict[str, list[str]]:
        async with self.lock:
            return {
                "place_urls": sorted(self.place_urls),
                "coord_keys": sorted(self.coord_keys),
                "name_address_keys": sorted(self.name_address_keys),
            }


class ChainWriter:
    def __init__(self, output_file: Path, progress_file: Path, stats_file: Path, seen_file: Path):
        self.output_file = output_file
        self.progress_file = progress_file
        self.stats_file = stats_file
        self.seen_file = seen_file
        self.lock = asyncio.Lock()

    async def append_stores(self, rows: list[dict[str, str]]) -> None:
        if not rows:
            return
        async with self.lock:
            with self.output_file.open("a", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)
                for row in rows:
                    writer.writerow({field: row.get(field, "") for field in FIELDNAMES})

    async def mark_region_done(self, task_key: str, region: str, stats: RegionStats) -> None:
        async with self.lock:
            with self.progress_file.open("a", encoding="utf-8") as f:
                f.write(task_key + "\n")
            await self._append_region_stats(region, stats, completed=1)

    async def mark_region_attempt(self, region: str, stats: RegionStats) -> None:
        async with self.lock:
            await self._append_region_stats(region, stats, completed=0)

    async def _append_region_stats(self, region: str, stats: RegionStats, completed: int) -> None:
        new_file = not self.stats_file.exists()
        with self.stats_file.open("a", encoding="utf-8-sig", newline="") as f:
            fields = [
                "ts",
                "region",
                "completed",
                "candidates_seen",
                "invalid_name_skipped",
                "duplicates_skipped",
                "details_opened",
                "stores_saved",
                "errors",
                "elapsed_seconds",
                "blocked",
                "captcha_detected",
                "feed_timeout",
                "proxy_enabled",
                "proxy_age_seconds",
            ]
            writer = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
            if new_file:
                writer.writeheader()
            writer.writerow(
                {
                    "ts": int(time.time()),
                    "region": region,
                    "completed": completed,
                    "candidates_seen": stats.candidates_seen,
                    "invalid_name_skipped": stats.invalid_name_skipped,
                    "duplicates_skipped": stats.duplicates_skipped,
                    "details_opened": stats.details_opened,
                    "stores_saved": stats.stores_saved,
                    "errors": stats.errors,
                    "elapsed_seconds": f"{stats.elapsed_seconds:.2f}",
                    "blocked": stats.blocked,
                    "captcha_detected": stats.captcha_detected,
                    "feed_timeout": stats.feed_timeout,
                    "proxy_enabled": stats.proxy_enabled,
                    "proxy_age_seconds": f"{stats.proxy_age_seconds:.2f}",
                }
            )

    async def save_seen(self, seen: SeenState) -> None:
        data = await seen.snapshot()
        tmp = self.seen_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.seen_file)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env_files() -> None:
    for path in DEFAULT_ENV_FILES:
        load_env_file(path)


def resolve_proxy_url(raw_value: str | None) -> str:
    return (raw_value or os.environ.get("GMAPS_PROXY_URL") or "").strip()


def build_proxy_config(proxy_url: str) -> dict[str, str] | None:
    proxy_url = proxy_url.strip()
    if not proxy_url:
        return None
    if not re.match(r"^[a-z][a-z0-9+.-]*://", proxy_url, flags=re.I):
        proxy_url = "http://" + proxy_url
    parsed = urllib.parse.urlparse(proxy_url)
    if not parsed.hostname:
        raise SystemExit("Invalid proxy URL: missing host. Set GMAPS_PROXY_URL as http://user:pass@host:port")
    try:
        port = parsed.port
    except ValueError as exc:
        raise SystemExit("Invalid proxy URL: bad port.") from exc
    if not port:
        raise SystemExit("Invalid proxy URL: missing port. Set GMAPS_PROXY_URL as http://user:pass@host:port")
    server = f"{parsed.scheme}://{parsed.hostname}:{port}"
    config: dict[str, str] = {"server": server}
    if parsed.username:
        config["username"] = urllib.parse.unquote(parsed.username)
    if parsed.password:
        config["password"] = urllib.parse.unquote(parsed.password)
    return config


def ckey_proxy_key_from_args(args) -> str:
    return (args.ckey_proxy_key or os.environ.get("GMAPS_CKEY_PROXY_KEY") or "").strip()


def ckey_api_key_from_args(args) -> str:
    return (args.ckey_api_key or os.environ.get("GMAPS_CKEY_API_KEY") or "").strip()


class CkeyCooldownError(RuntimeError):
    def __init__(self, message: str, wait_seconds: float) -> None:
        super().__init__(message)
        self.wait_seconds = wait_seconds


def ckey_wait_seconds(message: str) -> float:
    match = re.search(r"\b(?:con|còn)\s+(\d+)\s*s", strip_accents(message).lower())
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+)\s*s", message.lower())
    return float(match.group(1)) if match else 0.0


def parse_ckey_proxy_value(value: str, proxy_type: str) -> dict[str, str]:
    parts = [part.strip() for part in (value or "").split(":")]
    if len(parts) < 2:
        raise RuntimeError(f"Bad CKEY proxy value: {value!r}")
    host, port = parts[0], parts[1]
    if not host or not port:
        raise RuntimeError(f"Bad CKEY proxy value: {value!r}")
    scheme = "socks5" if proxy_type == "socks5" else "http"
    config: dict[str, str] = {"server": f"{scheme}://{host}:{port}"}
    if len(parts) >= 3 and parts[2]:
        config["username"] = parts[2]
    if len(parts) >= 4 and parts[3]:
        config["password"] = ":".join(parts[3:])
    return config


def fetch_ckey_proxy_config(args) -> dict[str, str]:
    keyproxy = ckey_proxy_key_from_args(args)
    if not keyproxy:
        raise RuntimeError("Missing CKEY proxy key. Set GMAPS_CKEY_PROXY_KEY or pass --ckey-proxy-key.")
    proxy_type = args.ckey_proxy_type
    params = {
        "keyproxy": keyproxy,
        "nhamang": args.ckey_nhamang,
        "tinhthanh": args.ckey_tinhthanh,
    }
    api_key = ckey_api_key_from_args(args)
    if api_key:
        params["key"] = api_key
    if args.ckey_whitelist:
        params["whitelist"] = args.ckey_whitelist
    url = args.ckey_api_url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=args.ckey_api_timeout) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    status = str(data.get("status", ""))
    if status != "100":
        message = data.get("message") or data.get("msg") or data
        message_text = str(message)
        wait_seconds = ckey_wait_seconds(message_text)
        if wait_seconds > 0:
            raise CkeyCooldownError(f"CKEY getproxyxoay cooldown: {message_text}", wait_seconds)
        raise RuntimeError(f"CKEY getproxyxoay failed: {message_text}")
    field = "proxysocks5" if proxy_type == "socks5" else "proxyhttp"
    proxy_value = data.get(field)
    if not proxy_value:
        raise RuntimeError(f"CKEY response missing {field}")
    return parse_ckey_proxy_value(proxy_value, proxy_type)


async def resolve_session_proxy_config(args) -> dict[str, str] | None:
    if args.proxy_config:
        return args.proxy_config
    if args.ckey_proxy_key:
        async with args.ckey_proxy_lock:
            cached = getattr(args, "ckey_cached_proxy_config", None)
            last_fetch = float(getattr(args, "ckey_last_proxy_fetch", 0.0) or 0.0)
            cache_age = time.monotonic() - last_fetch if last_fetch else 0.0
            if cached and cache_age < args.ckey_cache_seconds:
                return cached
            for attempt in range(max(1, args.ckey_fetch_retries)):
                try:
                    config = await asyncio.to_thread(fetch_ckey_proxy_config, args)
                    args.ckey_cached_proxy_config = config
                    args.ckey_last_proxy_fetch = time.monotonic()
                    return config
                except CkeyCooldownError as exc:
                    cached = getattr(args, "ckey_cached_proxy_config", None)
                    if cached:
                        return cached
                    if attempt >= max(1, args.ckey_fetch_retries) - 1:
                        raise
                    await asyncio.sleep(max(1.0, exc.wait_seconds + 1.0))
    return None


def load_registry(path: Path) -> dict[str, ChainConfig]:
    configs: dict[str, ChainConfig] = {}
    for row in read_csv(path):
        target_chain = (row.get("target_chain") or "").strip()
        if not target_chain:
            continue
        aliases = parse_pipe_list(row.get("name_aliases")) or [target_chain]
        try:
            concurrency = int((row.get("concurrency") or "2").strip() or "2")
        except ValueError:
            concurrency = 2
        try:
            priority = int((row.get("priority") or "50").strip() or "50")
        except ValueError:
            priority = 50
        configs[registry_key(target_chain)] = ChainConfig(
            target_chain=target_chain,
            search_query=(row.get("search_query") or target_chain).strip(),
            name_aliases=aliases,
            name_blacklist=parse_pipe_list(row.get("name_blacklist")),
            expected_count=(row.get("expected_count") or "").strip(),
            concurrency=max(1, concurrency),
            priority=priority,
            notes=(row.get("notes") or "").strip(),
        )
    return configs


def resolve_chains(raw_chains: str, registry: dict[str, ChainConfig]) -> list[ChainConfig]:
    names = [item.strip() for item in raw_chains.split(",") if item.strip()]
    if not names:
        raise SystemExit("No chains provided. Use --chains \"Chain A,Chain B\".")
    resolved: list[ChainConfig] = []
    missing: list[str] = []
    for name in names:
        config = registry.get(registry_key(name))
        if config:
            resolved.append(config)
        else:
            missing.append(name)
    if missing:
        known = ", ".join(sorted(config.target_chain for config in registry.values())[:12])
        raise SystemExit(f"Unknown chain(s): {', '.join(missing)}. Registry sample: {known} ...")
    return resolved


def load_regions(path: Path, limit: int = 0) -> list[str]:
    regions = json.loads(path.read_text(encoding="utf-8"))
    if limit:
        return regions[:limit]
    return regions


def init_output_files(output_dir: Path, config: ChainConfig) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "_seen").mkdir(parents=True, exist_ok=True)
    slug = clean_filename(config.target_chain)
    output_file = output_dir / f"{slug}_gmaps_chainlock.csv"
    progress_file = output_dir / f"{slug}_gmaps_chainlock.progress.log"
    stats_file = output_dir / f"{slug}_gmaps_chainlock.stats.csv"
    seen_file = output_dir / "_seen" / f"{slug}.json"
    if not output_file.exists():
        with output_file.open("w", encoding="utf-8-sig", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL).writeheader()
    else:
        migrate_output_schema(output_file)
    return output_file, progress_file, stats_file, seen_file


def sync_csv_only(output_file: Path) -> None:
    csv_only_dir = output_file.parent / "csv_only"
    csv_only_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_file, csv_only_dir / output_file.name)


def migrate_output_schema(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        old_fields = reader.fieldnames or []
        if old_fields == FIELDNAMES:
            return
        missing = [field for field in FIELDNAMES if field not in old_fields and field != "city"]
        if missing:
            raise SystemExit(f"Cannot migrate {path}: missing columns {missing}")
        rows = []
        for row in reader:
            migrated = {field: row.get(field, "") for field in FIELDNAMES}
            if not migrated.get("city") or not migrated.get("province"):
                _, city, province = parse_vietnam_address(migrated.get("address", ""))
                if not migrated.get("city"):
                    migrated["city"] = city
                if not migrated.get("province"):
                    migrated["province"] = province
            rows.append(migrated)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def load_seen_state(output_file: Path, seen_file: Path) -> SeenState:
    state = SeenState()
    if seen_file.exists():
        try:
            data = json.loads(seen_file.read_text(encoding="utf-8"))
            state.place_urls.update(data.get("place_urls", []))
            state.coord_keys.update(data.get("coord_keys", []))
            state.name_address_keys.update(data.get("name_address_keys", []))
        except Exception:
            pass
    for row in read_csv(output_file):
        ck = coord_key(row.get("lat"), row.get("lng"))
        if ck:
            state.coord_keys.add(ck)
        nak = name_address_key(row.get("name"), row.get("address"))
        if nak:
            state.name_address_keys.add(nak)
    return state


def load_completed(progress_file: Path, target_chain: str) -> set[str]:
    completed: set[str] = set()
    if not progress_file.exists():
        return completed
    for line in progress_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|||" in line:
            chain, region = line.split("|||", 1)
            if chain == target_chain:
                completed.add(region)
        else:
            completed.add(line)
    return completed


def is_valid_name(config: ChainConfig, name: str) -> bool:
    raw_words = norm_words(name)
    name_compact = norm_compact(name)
    name_key = registry_key(name)
    for phrase in config.name_blacklist:
        phrase_words = norm_words(phrase)
        phrase_compact = norm_compact(phrase)
        if not phrase_words:
            continue
        if "+" in phrase:
            if phrase_words in raw_words:
                return False
            continue
        if phrase_words in raw_words or (phrase_compact and phrase_compact in name_compact):
            return False
    for alias in config.name_aliases or [config.target_chain]:
        alias_words = norm_words(alias)
        alias_compact = norm_compact(alias)
        alias_key = registry_key(alias)
        if not alias_words:
            continue
        if "+" in alias:
            if alias_key in name_key or alias_words in raw_words:
                return True
            continue
        if alias_words in raw_words or (alias_compact and alias_compact in name_compact):
            return True
    return False


async def block_resources(route):
    try:
        if route.request.resource_type in {"image", "media", "font"}:
            await route.abort()
        else:
            await route.continue_()
    except Exception:
        # A page can close while Playwright still has route callbacks in flight.
        # Ignore these cleanup races so a completed/rotated browser session does
        # not crash the whole crawl.
        pass


async def accept_consent(page) -> None:
    try:
        consent = page.locator('button:has-text("Chấp nhận"), button:has-text("Accept"), button:has-text("Tôi đồng ý")')
        if await consent.is_visible(timeout=1000):
            await consent.click()
    except Exception:
        pass


async def detect_block_state(page) -> tuple[bool, bool]:
    url = (getattr(page, "url", "") or "").lower()
    captcha = "captcha" in url or "/sorry/" in url
    blocked = captcha or "consent.google" in url
    try:
        if await page.locator('iframe[src*="recaptcha"], iframe[title*="reCAPTCHA"]').count():
            captcha = True
            blocked = True
    except Exception:
        pass
    try:
        body = (await page.locator("body").inner_text(timeout=1000)).lower()
    except Exception:
        body = ""
    if body:
        captcha_terms = ["captcha", "not a robot", "không phải là rô-bốt", "khong phai la ro bot"]
        block_terms = [
            "unusual traffic",
            "detected unusual traffic",
            "automated queries",
            "our systems have detected",
            "sorry",
        ]
        if any(term in body for term in captcha_terms):
            captcha = True
        if captcha or any(term in body for term in block_terms):
            blocked = True
    return blocked, captcha


async def get_address(page) -> str:
    locator = page.locator('button[data-item-id="address"]').first
    if await locator.is_visible(timeout=2500):
        label = await locator.get_attribute("aria-label")
        if label:
            return label.replace("Địa chỉ: ", "").strip()
    return ""


async def scrape_single_result(page, config: ChainConfig, seen: SeenState, stats: RegionStats) -> list[dict[str, str]]:
    stores: list[dict[str, str]] = []
    name = (await page.locator("h1.DUwDvf.lfPIob").inner_text()).strip()
    stats.candidates_seen += 1
    if not is_valid_name(config, name):
        stats.invalid_name_skipped += 1
        return stores
    place_url = page.url
    lat, lng = extract_coords_from_url(place_url)
    if not await seen.reserve_candidate(place_url, lat, lng):
        stats.duplicates_skipped += 1
        return stores
    stats.details_opened += 1
    address = await get_address(page)
    if not address:
        await seen.release_candidate(place_url, lat, lng)
        return stores
    key = name_address_key(name, address)
    if not await seen.commit_store(place_url, lat, lng, key):
        stats.duplicates_skipped += 1
        return stores
    _, city, province = parse_vietnam_address(address)
    stores.append({"brand_id": "", "name": name, "address": address, "city": city, "province": province, "lat": lat, "lng": lng})
    stats.stores_saved += 1
    return stores


async def scrape_region(search_page, detail_page, config: ChainConfig, region: str, seen: SeenState, args) -> tuple[list[dict[str, str]], RegionStats]:
    stats = RegionStats()
    stores: list[dict[str, str]] = []
    query = f"{config.search_query} {region}"
    search_url = "https://www.google.com/maps/search/" + urllib.parse.quote(query)
    await search_page.goto(search_url, wait_until="domcontentloaded", timeout=args.goto_timeout)
    await accept_consent(search_page)
    blocked, captcha = await detect_block_state(search_page)
    if blocked:
        stats.blocked = 1
        stats.captcha_detected = int(captcha)
        return stores, stats

    is_single = await search_page.locator("h1.DUwDvf.lfPIob").is_visible(timeout=1500)
    if is_single:
        stores.extend(await scrape_single_result(search_page, config, seen, stats))
        return stores, stats

    try:
        await search_page.wait_for_selector('div[role="feed"]', timeout=args.feed_timeout)
    except Exception:
        stats.feed_timeout = 1
        blocked, captcha = await detect_block_state(search_page)
        if blocked:
            stats.blocked = 1
            stats.captcha_detected = int(captcha)
        return stores, stats

    panel = search_page.locator('div[role="feed"]').first
    last_count = -1
    stagnant_rounds = 0
    for _ in range(args.scroll_rounds):
        try:
            if await search_page.locator('span:has-text("Bạn đã đi đến cuối danh sách"), span:has-text("Đã hết danh sách")').is_visible(timeout=300):
                break
        except Exception:
            pass
        locations = await search_page.query_selector_all('div[role="article"]')
        count = len(locations)
        if count == last_count:
            stagnant_rounds += 1
        else:
            stagnant_rounds = 0
        if count > 0 and stagnant_rounds >= args.scroll_stagnant_rounds:
            break
        last_count = count
        await panel.evaluate("element => element.scrollTo(0, element.scrollHeight)")
        await asyncio.sleep(args.scroll_delay)

    locations = await search_page.query_selector_all('div[role="article"]')
    for loc in locations:
        try:
            name = await loc.get_attribute("aria-label")
            if not name:
                continue
            stats.candidates_seen += 1
            if not is_valid_name(config, name):
                stats.invalid_name_skipped += 1
                continue
            a_tag = await loc.query_selector("a")
            place_url = await a_tag.get_attribute("href") if a_tag else ""
            if not place_url:
                continue
            lat, lng = extract_coords_from_url(place_url)
            if not await seen.reserve_candidate(place_url, lat, lng):
                stats.duplicates_skipped += 1
                continue

            stats.details_opened += 1
            await detail_page.goto(place_url, wait_until="domcontentloaded", timeout=args.detail_timeout)
            blocked, captcha = await detect_block_state(detail_page)
            if blocked:
                stats.blocked = 1
                stats.captcha_detected = int(captcha)
                await seen.release_candidate(place_url, lat, lng)
                break
            await asyncio.sleep(random.uniform(args.detail_min_delay, args.detail_max_delay))
            detail_lat, detail_lng = extract_coords_from_url(detail_page.url)
            lat = detail_lat or lat
            lng = detail_lng or lng
            address = await get_address(detail_page)
            if not address:
                await seen.release_candidate(place_url, lat, lng)
                continue
            key = name_address_key(name, address)
            if not await seen.commit_store(place_url, lat, lng, key):
                stats.duplicates_skipped += 1
                continue
            _, city, province = parse_vietnam_address(address)
            stores.append({"brand_id": "", "name": name.strip(), "address": address, "city": city, "province": province, "lat": lat, "lng": lng})
            stats.stores_saved += 1
        except Exception:
            stats.errors += 1
            continue
    return stores, stats


async def open_worker_session(playwright, stealth: Stealth, args) -> dict[str, Any]:
    launch_kwargs: dict[str, Any] = {"headless": args.headless}
    proxy_config = await resolve_session_proxy_config(args)
    if proxy_config:
        launch_kwargs["proxy"] = proxy_config
    browser = await playwright.chromium.launch(**launch_kwargs)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="vi-VN",
    )
    search_page = await context.new_page()
    detail_page = await context.new_page()
    await search_page.route("**/*", block_resources)
    await detail_page.route("**/*", block_resources)
    await stealth.apply_stealth_async(search_page)
    await stealth.apply_stealth_async(detail_page)
    ttl = 0.0
    if proxy_config:
        min_seconds = max(0.0, float(args.proxy_min_session_seconds))
        max_seconds = max(min_seconds, float(args.proxy_max_session_seconds))
        ttl = random.uniform(min_seconds, max_seconds)
    return {
        "browser": browser,
        "proxy_config": proxy_config,
        "search_page": search_page,
        "detail_page": detail_page,
        "started": time.monotonic(),
        "ttl": ttl,
    }


async def verify_playwright_browser(args) -> None:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=args.headless)
            await browser.close()
    except Exception as exc:
        message = short_error(exc)
        raise SystemExit(
            "Playwright Chromium is not installed or cannot be launched.\n"
            "Run this command, then crawl again:\n\n"
            "    python -m playwright install chromium\n\n"
            f"Original error: {message}"
        ) from exc


async def close_worker_session(session: dict[str, Any] | None) -> None:
    if not session:
        return
    try:
        for page_key in ("search_page", "detail_page"):
            page = session.get(page_key)
            if page:
                await page.unroute_all(behavior="ignoreErrors")
        await session["browser"].close()
    except Exception:
        pass


def session_age(session: dict[str, Any] | None) -> float:
    if not session:
        return 0.0
    return time.monotonic() - float(session["started"])


def session_expired(session: dict[str, Any] | None, args) -> bool:
    if not session or not args.proxy_enabled:
        return False
    ttl = float(session.get("ttl") or 0.0)
    return ttl > 0 and session_age(session) >= ttl


async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    config: ChainConfig,
    seen: SeenState,
    writer: ChainWriter,
    tracker: ProgressTracker,
    args,
    deferred_retries: DeferredRetries | None = None,
) -> RegionStats:
    total = RegionStats()
    stealth = Stealth()
    async with async_playwright() as p:
        session: dict[str, Any] | None = None
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            region, retry_count = item
            task_key = f"{config.target_chain}|||{region}"
            rotate_session = False
            cooldown_seconds = 0.0
            try:
                if session is None or session_expired(session, args):
                    await close_worker_session(session)
                    session = await open_worker_session(p, stealth, args)

                started = time.monotonic()
                scrape_task = scrape_region(
                    session["search_page"],
                    session["detail_page"],
                    config,
                    region,
                    seen,
                    args,
                )
                if args.region_hard_timeout > 0:
                    stores, stats = await asyncio.wait_for(scrape_task, timeout=args.region_hard_timeout)
                else:
                    stores, stats = await scrape_task
                stats.elapsed_seconds = time.monotonic() - started
                stats.proxy_enabled = int(bool(args.proxy_enabled))
                stats.proxy_age_seconds = session_age(session)
                await writer.append_stores(stores)

                if stats.blocked and retry_count < args.block_retry_limit:
                    await writer.mark_region_attempt(region, stats)
                    total.add(stats)
                    if args.defer_region_retries and deferred_retries is not None:
                        await deferred_retries.add(region, retry_count + 1)
                    else:
                        queue.put_nowait((region, retry_count + 1))
                    rotate_session = True
                    cooldown_seconds = max(
                        float(args.proxy_block_cooldown_seconds),
                        max(0.0, float(args.proxy_min_session_seconds) - session_age(session)),
                    )
                    retry_mode = "queued_final_retry" if args.defer_region_retries else "retry"
                    print(
                        f"[{worker_id}] {config.target_chain} | {region}: blocked/captcha "
                        f"{retry_mode}={retry_count + 1}/{args.block_retry_limit}"
                    )
                else:
                    stats.regions_done = 1
                    await writer.mark_region_done(task_key, region, stats)
                    total.add(stats)
                    progress = await tracker.mark_completed()
                    if args.seen_flush_every <= 1 or total.regions_done % args.seen_flush_every == 0:
                        await writer.save_seen(seen)
                    if stats.blocked:
                        rotate_session = True
                        cooldown_seconds = float(args.proxy_block_cooldown_seconds)
                    print(
                        f"[{worker_id}] {config.target_chain} | {region}: "
                        f"candidates={stats.candidates_seen} dup={stats.duplicates_skipped} "
                        f"details={stats.details_opened} saved={stats.stores_saved} "
                        f"errors={stats.errors} blocked={stats.blocked} elapsed={stats.elapsed_seconds:.1f}s "
                        f"progress={int(progress['done'])}/{int(progress['total'])} "
                        f"{progress['percent']:.1f}% eta={format_duration(progress['eta_seconds'])} "
                        f"rate={progress['rate_per_hour']:.1f}/h"
                    )
            except Exception as exc:
                stats = RegionStats(errors=1)
                stats.proxy_enabled = int(bool(args.proxy_enabled))
                if session:
                    stats.proxy_age_seconds = session_age(session)
                if args.proxy_enabled and retry_count < args.block_retry_limit:
                    await writer.mark_region_attempt(region, stats)
                    total.add(stats)
                    if args.defer_region_retries and deferred_retries is not None:
                        await deferred_retries.add(region, retry_count + 1)
                    else:
                        queue.put_nowait((region, retry_count + 1))
                    rotate_session = True
                    cooldown_seconds = max(
                        float(args.proxy_block_cooldown_seconds),
                        max(0.0, float(args.proxy_min_session_seconds) - session_age(session)),
                    )
                    retry_mode = "queued_final_retry" if args.defer_region_retries else "failed/requeued"
                    print(f"[{worker_id}] {config.target_chain} | {region}: {retry_mode} {short_error(exc)}")
                else:
                    stats.regions_done = 1
                    await writer.mark_region_done(task_key, region, stats)
                    total.add(stats)
                    progress = await tracker.mark_completed()
                    print(
                        f"[{worker_id}] {config.target_chain} | {region}: failed {short_error(exc)} "
                        f"progress={int(progress['done'])}/{int(progress['total'])} "
                        f"{progress['percent']:.1f}% eta={format_duration(progress['eta_seconds'])}"
                    )
            finally:
                if rotate_session:
                    await close_worker_session(session)
                    session = None
                    if cooldown_seconds > 0:
                        await asyncio.sleep(cooldown_seconds)
                else:
                    await asyncio.sleep(post_region_delay(stats, args))
                queue.task_done()

        await close_worker_session(session)
    return total


def post_region_delay(stats: RegionStats, args) -> float:
    if not args.adaptive_delay:
        return random.uniform(args.min_delay, args.max_delay)
    if stats.details_opened > 0 or stats.stores_saved > 0:
        return random.uniform(args.min_delay, args.max_delay)
    if stats.candidates_seen == 0:
        return random.uniform(args.empty_min_delay, args.empty_max_delay)
    return random.uniform(args.duplicate_min_delay, args.duplicate_max_delay)


async def run_chain(config: ChainConfig, regions: list[str], args) -> None:
    output_file, progress_file, stats_file, seen_file = init_output_files(args.output, config)
    seen = load_seen_state(output_file, seen_file)
    writer = ChainWriter(output_file, progress_file, stats_file, seen_file)
    completed = load_completed(progress_file, config.target_chain)
    pending = [region for region in regions if region not in completed]
    if args.shuffle:
        random.shuffle(pending)
    concurrency = args.concurrency or config.concurrency
    concurrency = max(1, concurrency)
    print(
        f"chain={config.target_chain} regions={len(regions)} completed={len(completed)} "
        f"pending={len(pending)} concurrency={concurrency} proxy={'on' if args.proxy_enabled else 'off'} "
        f"output={output_file}"
    )
    if not pending:
        await writer.save_seen(seen)
        sync_csv_only(output_file)
        return

    tracker = ProgressTracker(total_regions=len(regions), initial_completed=len(completed), completed=0)
    final = RegionStats()
    pass_items = [(region, 0) for region in pending]
    pass_index = 0
    while pass_items:
        retry_collector = DeferredRetries() if args.defer_region_retries else None
        if pass_index > 0:
            print(f"retry_pass={pass_index} chain={config.target_chain} regions={len(pass_items)}")
            if args.deferred_retry_pause_seconds > 0:
                await asyncio.sleep(args.deferred_retry_pause_seconds)

        queue: asyncio.Queue = asyncio.Queue()
        for item in pass_items:
            queue.put_nowait(item)
        tasks = [
            asyncio.create_task(worker(i + 1, queue, config, seen, writer, tracker, args, retry_collector))
            for i in range(concurrency)
        ]
        await queue.join()
        for _ in range(concurrency):
            queue.put_nowait(None)
        totals = await asyncio.gather(*tasks)
        for stats in totals:
            final.add(stats)

        if not args.defer_region_retries or retry_collector is None:
            break
        pass_items = await retry_collector.snapshot()
        pass_index += 1
    await writer.save_seen(seen)
    sync_csv_only(output_file)
    print(
        f"DONE {config.target_chain}: candidates={final.candidates_seen} "
        f"dup={final.duplicates_skipped} details={final.details_opened} "
        f"saved={final.stores_saved} errors={final.errors}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Maps chain-lock crawler with pre-detail dedupe.")
    parser.add_argument("--chains", required=True, help='Comma-separated target chains, e.g. "Matsumoto Kiyoshi,Farmers Market,Watsons".')
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--regions", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--concurrency", type=int, default=0, help="Override registry concurrency for all chains. 0 = use registry.")
    parser.add_argument("--chain-parallelism", type=int, default=1, help="How many target chains to run at the same time. Keep 1 for safest; use 2-3 on PC for speed.")
    parser.add_argument("--limit-regions", type=int, default=0, help="Debug only: use first N regions.")
    parser.add_argument("--sample-regions", type=int, default=0, help="Randomly sample N regions after loading all regions. Better than --limit-regions for proxy smoke tests.")
    parser.add_argument("--sample-seed", type=int, default=20260605)
    parser.add_argument("--shuffle", action="store_true", help="Shuffle regions within each chain.")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--scroll-rounds", type=int, default=12)
    parser.add_argument("--scroll-stagnant-rounds", type=int, default=2)
    parser.add_argument("--scroll-delay", type=float, default=0.45)
    parser.add_argument("--min-delay", type=float, default=1.5)
    parser.add_argument("--max-delay", type=float, default=3.0)
    parser.add_argument("--adaptive-delay", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--empty-min-delay", type=float, default=0.3)
    parser.add_argument("--empty-max-delay", type=float, default=0.8)
    parser.add_argument("--duplicate-min-delay", type=float, default=0.7)
    parser.add_argument("--duplicate-max-delay", type=float, default=1.3)
    parser.add_argument("--detail-min-delay", type=float, default=1.0)
    parser.add_argument("--detail-max-delay", type=float, default=1.8)
    parser.add_argument("--seen-flush-every", type=int, default=25)
    parser.add_argument("--goto-timeout", type=int, default=25000)
    parser.add_argument("--feed-timeout", type=int, default=10000)
    parser.add_argument("--detail-timeout", type=int, default=15000)
    parser.add_argument("--region-hard-timeout", type=float, default=180.0, help="Hard timeout in seconds for one region task. 0 disables it.")
    parser.add_argument("--proxy-url", nargs="?", default="", const="", help="Optional HTTP/HTTPS/SOCKS proxy URL. Falls back to GMAPS_PROXY_URL in .env.")
    parser.add_argument("--proxy-min-session-seconds", type=float, default=60.0)
    parser.add_argument("--proxy-max-session-seconds", type=float, default=1500.0)
    parser.add_argument("--proxy-block-cooldown-seconds", type=float, default=60.0)
    parser.add_argument("--block-retry-limit", type=int, default=1)
    parser.add_argument("--defer-region-retries", action=argparse.BooleanOptionalAction, default=True, help="Retry failed regions at the end of the brand instead of immediately.")
    parser.add_argument("--deferred-retry-pause-seconds", type=float, default=30.0)
    parser.add_argument("--ckey-proxy-key", default="", help="CKEY rotating proxy key. Falls back to GMAPS_CKEY_PROXY_KEY in .env.")
    parser.add_argument("--ckey-api-key", default="", help="Optional CKEY account API key. Falls back to GMAPS_CKEY_API_KEY in .env.")
    parser.add_argument("--ckey-api-url", default="https://ckey.vn/api/getproxyxoay")
    parser.add_argument("--ckey-nhamang", default="", help="CKEY carrier: Random, Viettel, Vinaphone, fpt.")
    parser.add_argument("--ckey-tinhthanh", default="", help="CKEY province code. 0 = random.")
    parser.add_argument("--ckey-whitelist", default="", help="Optional IP whitelist value for CKEY API.")
    parser.add_argument("--ckey-proxy-type", default="", help="http or socks5. Falls back to GMAPS_CKEY_PROXY_TYPE.")
    parser.add_argument("--ckey-api-timeout", type=int, default=30)
    parser.add_argument("--ckey-cache-seconds", type=float, default=60.0, help="Reuse the last CKEY proxy for at least this many seconds.")
    parser.add_argument("--ckey-fetch-retries", type=int, default=2, help="Retries when CKEY says the proxy can only rotate after a cooldown.")
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    await verify_playwright_browser(args)
    registry = load_registry(args.registry)
    configs = resolve_chains(args.chains, registry)
    regions = load_regions(args.regions, 0 if args.sample_regions else args.limit_regions)
    if args.sample_regions:
        regions = list(regions)
        random.Random(args.sample_seed).shuffle(regions)
        regions = regions[:args.sample_regions]
    chain_parallelism = max(1, args.chain_parallelism)
    if chain_parallelism == 1 or len(configs) == 1:
        for config in configs:
            await run_chain(config, regions, args)
        return

    semaphore = asyncio.Semaphore(chain_parallelism)

    async def run_with_limit(config: ChainConfig) -> None:
        async with semaphore:
            await run_chain(config, regions, args)

    await asyncio.gather(*(run_with_limit(config) for config in configs))


def main() -> None:
    args = parse_args()
    # Free crawl kit intentionally ignores all proxy/CKEY environment variables.
    # This keeps helper runs simple and prevents stale proxy keys from breaking
    # the crawl or creating fake progress.
    args.proxy_url = ""
    args.proxy_config = None
    args.ckey_proxy_key = ""
    args.ckey_api_key = ""
    args.ckey_api_url = (args.ckey_api_url or os.environ.get("GMAPS_CKEY_API_URL") or "https://ckey.vn/api/getproxyxoay").strip()
    args.ckey_nhamang = (args.ckey_nhamang or os.environ.get("GMAPS_CKEY_NHAMANG") or "Random").strip()
    args.ckey_tinhthanh = (args.ckey_tinhthanh or os.environ.get("GMAPS_CKEY_TINHTHANH") or "0").strip()
    args.ckey_whitelist = (args.ckey_whitelist or os.environ.get("GMAPS_CKEY_WHITELIST") or "").strip()
    args.ckey_proxy_type = (os.environ.get("GMAPS_CKEY_PROXY_TYPE") or args.ckey_proxy_type or "http").strip().lower()
    if args.ckey_proxy_type not in {"http", "socks5"}:
        raise SystemExit("GMAPS_CKEY_PROXY_TYPE must be http or socks5.")
    args.proxy_enabled = bool(args.proxy_config or args.ckey_proxy_key)
    args.ckey_cache_seconds = max(0.0, float(args.ckey_cache_seconds))
    args.ckey_fetch_retries = max(1, int(args.ckey_fetch_retries))
    args.ckey_proxy_lock = asyncio.Lock()
    args.ckey_cached_proxy_config = None
    args.ckey_last_proxy_fetch = 0.0
    args.block_retry_limit = max(0, int(args.block_retry_limit))
    args.deferred_retry_pause_seconds = max(0.0, float(args.deferred_retry_pause_seconds))
    args.proxy_min_session_seconds = max(0.0, float(args.proxy_min_session_seconds))
    args.proxy_max_session_seconds = max(args.proxy_min_session_seconds, float(args.proxy_max_session_seconds))
    args.proxy_block_cooldown_seconds = max(0.0, float(args.proxy_block_cooldown_seconds))
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
