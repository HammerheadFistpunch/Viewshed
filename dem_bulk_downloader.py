#!/usr/bin/env python3
"""Bulk-download USGS 3DEP DEM tiles for a local offline archive.

This utility is intentionally separate from Signal Peak's runtime DEM code.
It uses the TNMAccess API to discover actual 1-degree GeoTIFF products and
then downloads them with retry-safe .part files. The resulting archive can be
wired into Signal Peak later without making the application depend on live USGS URLs.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import requests


TNM_API = "https://tnmaccess.nationalmap.gov/api/v1/products"
DEFAULT_BBOX = (-125.0, 24.0, -66.0, 50.0)

RESOLUTIONS = {
    "1": {
        "directory": "1arcsec",
        "dataset": "National Elevation Dataset (NED) 1 arc-second",
        "queries": (
            "1 arc-second DEM",
            "National Elevation Dataset (NED) 1 arc-second Current",
        ),
    },
    "1/3": {
        "directory": "1_3arcsec",
        "dataset": "National Elevation Dataset (NED) 1/3 arc-second",
        "queries": (
            "1/3 arc-second DEM",
            "National Elevation Dataset (NED) 1/3 arc-second Current",
        ),
    },
}

_print_lock = threading.Lock()


def log(message: str) -> None:
    with _print_lock:
        print(message, flush=True)


def tile_name(lat_south: int, lon_west: int) -> str:
    ns = "n" if lat_south >= 0 else "s"
    ew = "w" if lon_west < 0 else "e"
    return f"{ns}{abs(lat_south):02d}{ew}{abs(lon_west):03d}"


def iter_tiles(bbox: tuple[float, float, float, float]):
    west, south, east, north = bbox
    lon0 = math.floor(west)
    lon1 = math.ceil(east) - 1
    lat0 = math.floor(south)
    lat1 = math.ceil(north) - 1
    for lat in range(lat0, lat1 + 1):
        for lon in range(lon0, lon1 + 1):
            yield lat, lon


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        parts = [float(x.strip()) for x in value.split(",")]
        if len(parts) != 4:
            raise ValueError
        west, south, east, north = parts
        if not (west < east and south < north):
            raise ValueError
        return west, south, east, north
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "bbox must be west,south,east,north, for example -125,24,-66,50"
        ) from exc


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "SignalPeak-DEM-Archive/1.1"})
    return session


def iter_product_urls(item: dict[str, Any]):
    """Yield every download URL exposed by a TNMAccess product record."""
    seen: set[str] = set()
    direct = item.get("downloadURL")
    if isinstance(direct, str) and direct and direct not in seen:
        seen.add(direct)
        yield direct
    files = item.get("files")
    if isinstance(files, list):
        for entry in files:
            if not isinstance(entry, dict):
                continue
            for key in ("downloadURL", "url", "downloadUrl"):
                candidate = entry.get(key)
                if isinstance(candidate, str) and candidate and candidate not in seen:
                    seen.add(candidate)
                    yield candidate


def extract_tile_token(value: str) -> str | None:
    """Return a 1-degree tile token found anywhere in a URL/title."""
    import re

    match = re.search(r"(?:^|[^a-z])([ns]\d{2}[ew]\d{3})(?:[^a-z]|$)", value.lower())
    return match.group(1) if match else None


def is_dem_file(url: str) -> bool:
    return url.lower().split("?", 1)[0].endswith((".tif", ".tiff", ".zip"))


def is_current_product(item: dict[str, Any], url: str) -> bool:
    text = " ".join(
        str(item.get(key) or "")
        for key in ("title", "name", "description", "dataset", "dateCreated")
    ).lower()
    lower = url.lower()
    return "/current/" in lower or " current" in text or text.endswith("current")


def publication_key(item: dict[str, Any], url: str) -> str:
    value = item.get("publicationDate") or item.get("dateCreated") or ""
    if value:
        return str(value)
    import re

    match = re.search(r"_(\d{8})(?:\.|$)", url.rsplit("/", 1)[-1])
    return match.group(1) if match else ""


def discover_tile(
    session: requests.Session,
    lat: int,
    lon: int,
    resolution: str,
    timeout: int,
) -> dict[str, Any]:
    spec = RESOLUTIONS[resolution]
    tile = tile_name(lat, lon)
    bbox = f"{lon},{lat},{lon + 1},{lat + 1}"
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()

    requests_to_try: list[dict[str, Any]] = []
    for query in spec["queries"]:
        requests_to_try.append({"q": query})
    requests_to_try.append({"datasets": spec["dataset"]})
    requests_to_try.append({"datasets": spec["dataset"], "q": "current"})

    for extra in requests_to_try:
        params = {
            **extra,
            "bbox": bbox,
            "prodExtents": "1 x 1 degree",
        }
        try:
            response = session.get(TNM_API, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if data.get("errorMessage"):
                raise RuntimeError(str(data["errorMessage"]))
        except Exception as exc:
            errors.append(f"{extra}: {exc}")
            continue

        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            item_tile = extract_tile_token(str(item.get("title") or ""))
            for url in iter_product_urls(item):
                if url in seen or not is_dem_file(url):
                    continue
                if tile not in url.lower() and item_tile != tile.lower():
                    continue
                seen.add(url)
                candidates.append(
                    {
                        "url": url,
                        "title": item.get("title"),
                        "published": publication_key(item, url),
                        "format": item.get("format") or "GeoTIFF",
                        "source_query": extra,
                        "product_current": is_current_product(item, url),
                    }
                )

    if not candidates:
        detail = "; ".join(errors) if errors else "TNMAccess returned no matching product URLs"
        raise RuntimeError(f"{tile.upper()} discovery failed: {detail}")

    # Never silently downgrade to historical if TNMAccess returned a current
    # product. If no current product exists, use the newest dated product.
    candidates.sort(
        key=lambda item: (
            not item["product_current"],
            item["published"],
        ),
        reverse=False,
    )
    current = [item for item in candidates if item["product_current"]]
    if current:
        current.sort(key=lambda item: item["published"], reverse=True)
        chosen = current[0]
    else:
        candidates.sort(key=lambda item: item["published"], reverse=True)
        chosen = candidates[0]
        chosen["fallback_historical"] = True

    chosen["tile"] = tile
    chosen["resolution"] = resolution
    return chosen


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def download_file(
    session: requests.Session,
    item: dict[str, Any],
    target: Path,
    timeout: int,
    retries: int,
) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")

    if target.exists() and target.stat().st_size > 0:
        return {**item, "path": str(target), "size": target.stat().st_size, "skipped": True}

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            part.unlink(missing_ok=True)
            with session.get(item["url"], stream=True, timeout=timeout) as response:
                response.raise_for_status()
                with part.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if part.stat().st_size == 0:
                raise RuntimeError("server returned an empty file")
            part.replace(target)
            return {
                **item,
                "path": str(target),
                "size": target.stat().st_size,
                "sha256": sha256_file(target),
                "skipped": False,
            }
        except Exception as exc:
            last_error = exc
            part.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(min(30, 2 ** (attempt - 1)))

    raise RuntimeError(f"download failed after {retries} attempts: {last_error}")


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 2, "tiles": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("tiles"), dict):
            return data
    except Exception:
        pass
    return {"version": 2, "tiles": {}}


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".part")
    temp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk-download USGS 3DEP 1 arc-second and/or 1/3 arc-second DEM tiles."
    )
    parser.add_argument("--resolution", choices=("1", "1/3", "both"), default="1")
    parser.add_argument("--output", type=Path, default=Path("DEM_Archive"))
    parser.add_argument("--bbox", type=parse_bbox, default=DEFAULT_BBOX, metavar="W,S,E,N")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--api-timeout", type=int, default=45)
    parser.add_argument("--download-timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--discover-only", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.workers < 1 or args.retries < 1:
        parser.error("--workers and --retries must be at least 1")

    resolutions = ("1", "1/3") if args.resolution == "both" else (args.resolution,)
    tiles = list(iter_tiles(args.bbox))
    args.output.mkdir(parents=True, exist_ok=True)
    log(f"Archive root: {args.output.resolve()}")
    log(f"Grid cells: {len(tiles)} (bbox {args.bbox[0]},{args.bbox[1]},{args.bbox[2]},{args.bbox[3]})")

    manifest_path = args.output / "manifest.json"
    manifest = load_manifest(manifest_path)
    manifest.update(
        {
            "version": 2,
            "source": "USGS 3DEP / TNMAccess",
            "bbox": list(args.bbox),
            "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )

    session_local = threading.local()

    def session() -> requests.Session:
        if not hasattr(session_local, "session"):
            session_local.session = make_session()
        return session_local.session

    work: list[tuple[str, int, int]] = []
    for resolution in resolutions:
        for lat, lon in tiles:
            key = f"{resolution}:{tile_name(lat, lon)}"
            if not args.refresh and key in manifest["tiles"]:
                existing = manifest["tiles"][key]
                existing_path = existing.get("path")
                if existing_path and (args.output / existing_path).exists():
                    continue
            work.append((resolution, lat, lon))

    log(f"Tiles needing discovery/download: {len(work)}")
    if not work:
        log("Nothing to do; archive is already populated.")
        save_manifest(manifest_path, manifest)
        return 0

    failures: list[str] = []
    completed = 0

    def process(job: tuple[str, int, int]) -> tuple[str, dict[str, Any]]:
        resolution, lat, lon = job
        item = discover_tile(session(), lat, lon, resolution, args.api_timeout)
        key = f"{resolution}:{item['tile']}"
        if args.discover_only:
            return key, item
        spec = RESOLUTIONS[resolution]
        name = item["url"].split("?", 1)[0].rsplit("/", 1)[-1]
        target = args.output / spec["directory"] / name
        result = download_file(session(), item, target, args.download_timeout, args.retries)
        return key, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, job): job for job in work}
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            resolution, lat, lon = job
            try:
                key, result = future.result()
                if not args.discover_only:
                    result["path"] = os.path.relpath(result["path"], args.output)
                manifest["tiles"][key] = result
                completed += 1
                action = "discovered" if args.discover_only else ("skipped" if result.get("skipped") else "downloaded")
                status = "historical fallback" if result.get("fallback_historical") else action
                log(f"[{completed}/{len(work)}] {resolution} {key.split(':', 1)[1].upper()} {status}")
            except Exception as exc:
                label = f"{resolution} {tile_name(lat, lon).upper()}"
                failures.append(f"{label}: {exc}")
                log(f"[FAIL] {label}: {exc}")
            if completed % 10 == 0 or future.done():
                manifest["updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                save_manifest(manifest_path, manifest)

    manifest["updated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["failures"] = failures
    save_manifest(manifest_path, manifest)

    log("")
    log(f"Completed: {completed}/{len(work)}")
    log(f"Manifest: {manifest_path.resolve()}")
    if failures:
        log(f"Failures: {len(failures)} (rerun the command to retry them)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
