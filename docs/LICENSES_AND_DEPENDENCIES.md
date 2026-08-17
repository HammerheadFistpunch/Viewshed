# Signal Peak — Dependencies, Licenses, and Attribution

## Runtime dependencies

Signal Peak 1.0.0 declares these Python runtime dependencies in `requirements.txt`:

| Dependency | Role |
|---|---|
| itmlogic | Longley-Rice/ITM propagation calculations |
| rasterio | GeoTIFF/DEM raster I/O and reprojection |
| numpy | Numerical array processing |
| Pillow | Image/raster rendering support |
| shapely | Geometry utilities |
| pyproj | Coordinate reference-system transforms |
| requests | HTTP access to USGS/Overpass and related services |
| tqdm | Console progress support in the legacy backend |
| scipy | Raster filters and numerical processing |
| aprslib | APRS packet parsing |
| tkintermapview 1.30 | Embedded desktop map widget |

The Windows build additionally uses PyInstaller from `requirements-build.txt`.

## Important release-license issue

`aprslib` 0.7.2 is distributed under GNU GPLv2. Because Signal Peak imports aprslib and a PyInstaller build may bundle it into `SignalPeak.exe`, public binary distribution requires a GPL-aware licensing strategy. The repository does not currently choose a top-level Signal Peak project license.

Before publishing a formal binary release, the copyright owner should either:

1. choose a GPLv2-compatible project/distribution approach and satisfy corresponding source/notice requirements;
2. replace/remove aprslib and repeat the license audit; or
3. obtain separate permission from the aprslib copyright holder.

See `docs/RELEASE_READINESS_1.0.0.md`.

## Dependency inventory

Most dependency entries currently specify minimum versions, so the exact package versions and notices included in a Windows binary can vary over time. A public release should capture the exact installed versions and preserve the license notices required by those versions.

`itmlogic` is MIT-licensed. Its copyright/license notice must be preserved when distributing copies or substantial portions. Other direct and transitive dependency notices should be generated from the actual release environment rather than inferred only from this summary.

## Map and geographic-data attribution

### OpenStreetMap

Signal Peak uses OpenStreetMap-derived map data and may query OSM communications features through Overpass. Visible attribution must remain present. OSM data is available under ODbL, while use of the public OSM tile service is also subject to its operational tile-usage policy.

### OpenTopoMap

The topo layer uses OpenTopoMap raster tiles. The UI displays OpenStreetMap/OpenTopoMap attribution. Tile use is subject to OpenTopoMap's current attribution and service policy.

### USGS 3DEP

Signal Peak downloads USGS 3DEP/The National Map elevation data for terrain analysis. USGS 3DEP products are public-domain U.S. government data. Retaining USGS/3DEP source acknowledgement is recommended for provenance and reproducibility.

### APRS-IS and aprs.fi

APRS-IS is used as a live receive source. aprs.fi is optional and only used with a user-provided API key. Signal Peak 1.0.0 does not bundle a shared aprs.fi key and removes saved API keys from application settings. Public distribution using aprs.fi should follow the service's current API terms, including application identification, attribution, and contacting the service operator.

## Project license

A top-level Signal Peak `LICENSE` has intentionally not been added by this cleanup because selecting the project's copyright license is a decision for the copyright owner. Public source visibility on GitHub is not a substitute for an explicit software license.

## Release checklist

1. Resolve the aprslib/GPLv2 strategy.
2. Select a Signal Peak project license.
3. Pin exact dependency versions for the release build.
4. Export a dependency/version manifest or SBOM.
5. Bundle required third-party license notices.
6. Preserve OSM/OpenTopoMap attribution and follow tile-service policy.
7. Document USGS 3DEP provenance.
8. Follow aprs.fi distribution/API terms if that optional integration ships.
9. Review the exact pinned dependency set for known vulnerabilities.
