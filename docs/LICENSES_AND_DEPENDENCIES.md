# Dependencies, Licenses, and Attribution

## Runtime dependencies

Viewshed currently declares these Python runtime dependencies in `requirements.txt`:

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

## License handling

The repository does not attempt to replace upstream license texts with this summary. Binary redistributors should review and preserve notices required by the exact package versions included in a build. The authoritative license for each Python dependency is the license distributed by that upstream package/version.

Because dependency versions are specified mostly as minimum versions, the exact dependency/license inventory of a packaged EXE can vary as build environments update. A release process should eventually capture a pinned dependency manifest and bundled notices for each release artifact.

## Map and geographic-data attribution

### OpenStreetMap

Viewshed uses OpenStreetMap-derived map data and may query OSM communications features through Overpass. OSM attribution must remain visible where required. OSM data is provided under the Open Database License (ODbL); consult OpenStreetMap's current copyright/attribution guidance before redistribution or publication.

### OpenTopoMap

The Corrections topo layer uses OpenTopoMap raster tiles. The UI displays the required OpenStreetMap/OpenTopoMap attribution. Tile use is subject to the provider's current usage and attribution policy.

### USGS 3DEP

Viewshed downloads elevation data from USGS 3DEP/The National Map services for terrain analysis. USGS data and services have their own source/citation guidance; users publishing derived products should retain appropriate source acknowledgement.

### APRS-IS and aprs.fi

APRS-IS is used as a live receive source. aprs.fi is optional and used only when an API key is configured. Use of those services remains subject to their respective service terms and policies.

## Project license

Before distributing Viewshed as a formal release, ensure the repository contains a clear top-level project license file and that it is compatible with all bundled dependencies and assets. This document intentionally does not invent a project license where the repository has not explicitly declared one.

## Release checklist

For a formal release:

1. Pin dependency versions used for the release build.
2. Export an exact dependency/version manifest.
3. Bundle or link required third-party license notices.
4. Preserve OSM/OpenTopoMap attribution in the UI.
5. Document USGS elevation-data provenance.
6. Verify APRS-IS/aprs.fi usage remains compatible with current service policies.
