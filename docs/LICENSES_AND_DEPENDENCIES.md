# Signal Peak Dependencies and Licenses

Signal Peak 1.2.0 is distributed under the **GNU General Public License version 2 only (GPL-2.0-only)**. See the repository `LICENSE` file for the complete license text.

Third-party Python packages, map providers, APIs, and datasets retain their own licenses and terms. Signal Peak does not relicense those dependencies.

## Python/runtime dependencies

The current runtime dependency set is defined in `requirements.txt`. Major components include:

- `itmlogic` — Longley-Rice / ITM propagation calculations
- `rasterio` — raster/GeoTIFF and DEM processing
- `numpy` / `scipy` — numerical processing
- `shapely` / `pyproj` — geometry and coordinate transformation
- `Pillow` — image processing
- `requests` — HTTP access for supported external services
- `tkintermapview` and Python/Tk — desktop map/UI support
- `psutil` — Signal Peak V2 system RAM and CPU telemetry for safe terrain/resource planning

The V2 resource planner includes a standard-library fallback for basic RAM and CPU-count detection when `psutil` is unavailable, but packaged V2 builds should include `psutil` for accurate available-memory and CPU-load reporting.

Use the package metadata installed by `pip` and the upstream projects for the authoritative license text and current dependency notices.

## Build dependencies

Windows packaging uses PyInstaller and the packages listed in `requirements-build.txt`. The PyInstaller spec bundles Signal Peak documentation, station fallback data, application icons, and the Python modules required by the desktop workspace chain.

Signal Peak 1.2.0 additionally packages the Station Data / per-station RF modules and `docs/RELEASE_NOTES_1.2.0.md`.

## External data and services

### USGS 3DEP

Terrain acquisition uses U.S. Geological Survey 3DEP elevation products. USGS data and services remain subject to USGS terms, attribution guidance, and availability.

### APRS-IS

Live station acquisition can use APRS-IS. APRS-IS access is an external network service and is subject to its own operational policies.

### aprs.fi

aprs.fi is optional and may be used to resolve specific discovered infrastructure calls when the user supplies an API key. The key is treated as session-only by Signal Peak. aprs.fi data and API use remain subject to aprs.fi terms.

### OpenStreetMap / Overpass

OpenStreetMap communications features may be used as corroborating geographic evidence. OSM data is licensed under the Open Database License (ODbL); Overpass endpoints are external services with their own availability and usage policies.

### Map tiles

Standard/topographic basemaps are provided by external tile services. Their data, attribution, access limits, and terms remain those of the respective providers.

## GPL distribution note

If you distribute a Signal Peak executable, comply with GPLv2 source-availability requirements for Signal Peak itself. Keep the license and corresponding source available as required, and do not assume third-party dependency licenses are replaced by Signal Peak's GPLv2 license.

This document is a practical inventory, not legal advice. For redistribution, review the exact dependency versions in the build and their upstream license files.
