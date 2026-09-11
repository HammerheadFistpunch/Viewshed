# Signal Peak 2.2.0 Release Notes

Signal Peak 2.2.0 focuses on more reliable USGS terrain acquisition and a packaged workflow for building a reusable DEM archive.

## DEM reliability

- Improved USGS 3DEP / TNMAccess DEM product selection for runtime terrain preparation.
- Exact bbox-scoped NED queries are authoritative and do not require the tile name to appear in the returned product URL.
- Broad discovery queries retain tile-name filtering to avoid unrelated products.
- Runtime fallback handling is more tolerant of TNMAccess product-response differences while preserving the requested geographic extent.

## Bulk DEM archive tooling

- Added a packaged bulk DEM workflow under `tools/dem_bulk/` with JSON configuration and a Windows launcher.
- Bulk downloads remain resume-safe and support configurable resolution, bbox, output directory, workers, timeouts, retries, discovery-only mode, and refresh mode.
- The standalone archive workflow is documented separately from the normal per-run DEM cache so operators can build long-lived offline terrain resources without changing normal propagation behavior.

## Packaging and versioning

- The Windows package is versioned from the repository `VERSION` file.
- The packaged application entry point applies that release version consistently to the Help/About display, runtime version, network user-agent, and other existing release identity fields.
- GitHub Actions uses the same version source for the downloadable Windows artifact name.

Signal Peak is now **v2.2.0**.
