# Signal Peak 2.3.0

## DEM reliability and bulk archive tooling

- Improved USGS 3DEP / TNMAccess DEM product selection for runtime terrain preparation.
- Exact bbox-scoped NED queries are authoritative and do not require the tile name to appear in the returned product URL.
- Broad discovery queries retain tile-name filtering to avoid unrelated products.
- Added a packaged bulk DEM workflow under `tools/dem_bulk/` with JSON configuration and a Windows launcher.
- Bulk downloads remain resume-safe and support configurable resolution, bbox, output directory, workers, timeouts, retries, discovery-only mode, and refresh mode.

Signal Peak is now **v2.3.0**.
