from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "dem_bulk_config.json"
DOWNLOADER = HERE / "dem_bulk_downloader.py"


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bbox = cfg.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("bbox must contain [west, south, east, north]")
    cmd = [sys.executable, str(DOWNLOADER), "--resolution", str(cfg.get("resolution", "1")), "--output", str(cfg.get("output", "D:/DEM_Archive")), "--workers", str(cfg.get("workers", 6)), "--api-timeout", str(cfg.get("api_timeout", 45)), "--download-timeout", str(cfg.get("download_timeout", 180)), "--retries", str(cfg.get("retries", 3)), "--bbox", ",".join(map(str, bbox))]
    if cfg.get("discover_only", False): cmd.append("--discover-only")
    if cfg.get("refresh", False): cmd.append("--refresh")
    return subprocess.call(cmd, cwd=str(HERE))


if __name__ == "__main__":
    raise SystemExit(main())
