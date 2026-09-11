#!/usr/bin/env python3
"""Launch dem_bulk_downloader.py from a JSON configuration file."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "dem_bulk_config.json"
DOWNLOADER = ROOT / "dem_bulk_downloader.py"


def main() -> int:
    if not CONFIG.exists():
        print(f"Missing configuration file: {CONFIG}")
        return 2

    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Could not read {CONFIG}: {exc}")
        return 2

    if not isinstance(config, dict):
        print("Configuration must contain a JSON object.")
        return 2

    allowed = {
        "resolution": "--resolution",
        "output": "--output",
        "workers": "--workers",
        "api_timeout": "--api-timeout",
        "download_timeout": "--download-timeout",
        "retries": "--retries",
    }
    command = [sys.executable, str(DOWNLOADER)]

    for key, flag in allowed.items():
        if key in config and config[key] is not None:
            command.extend([flag, str(config[key])])

    if "bbox" in config:
        bbox = config["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            print("bbox must be an array of four numbers: [west, south, east, north]")
            return 2
        command.extend(["--bbox", ",".join(str(value) for value in bbox)])

    for key, flag in (("discover_only", "--discover-only"), ("refresh", "--refresh")):
        if bool(config.get(key, False)):
            command.append(flag)

    print("Running:")
    print(" ".join(f'"{part}"' if " " in part else part for part in command))
    print()
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
