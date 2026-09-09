# Signal Peak CONUS Support

Signal Peak 1.2.0 retains the CONUS-oriented station validation, terrain acquisition, and projection work introduced in 1.1.0 while adding per-station RF assumptions and operator-selectable display units.

## Geographic behavior

Signal Peak chooses a projected UTM CRS from the geographic center of the stations in each job. The selected zone is written to the run log.

Examples:

- Yakima, Washington: UTM 10N / EPSG:32610
- Los Angeles, California: UTM 11N / EPSG:32611
- Salt Lake City, Utah: UTM 12N / EPSG:32612
- Denver, Colorado: UTM 13N / EPSG:32613
- New York City, New York: UTM 18N / EPSG:32618

The projected working DEM is named by selected zone, preventing a projection cached for one zone from being silently reused in another.

## Station validation

The legacy worker originally rejected stations outside a hard-coded Utah latitude/longitude box. Current Signal Peak uses normal WGS84 coordinate validation, allowing regional jobs throughout the contiguous United States.

## Terrain source

Terrain acquisition uses USGS 3DEP 1-arcsecond elevation data. Requested tiles are derived from actual station coordinates and maximum calculation range rather than a Utah bounding box.

The legacy source module still contains some Utah-oriented internal filenames. Those are implementation history, not active geographic constraints.

## Elevation checks

The CONUS adapter uses broad physical sanity limits while retaining local DEM validation so legitimate low- and high-elevation sites are not rejected solely because they are outside Utah's typical terrain range.

## Modeling behavior

CONUS support does not replace the established per-station ITM math. Area, Station, and Custom continue to use the same terrain-profile/link-margin foundation.

In 1.2.0, different stations in the same Area job may use different height, TX power, gain, frequency, or path-loss assumptions when reliable station-specific data has been supplied. Missing values continue to use Advanced/global fallbacks.

The Metric/Imperial selector affects only operator-facing input/display units. Geographic coordinates remain WGS84 and the propagation backend continues to use metric projected coordinates.

## Current limits

- USGS 3DEP remains the terrain provider, so the current implementation is aimed at the United States rather than global coverage.
- One local UTM zone is used per job. Very broad jobs spanning several zones should be interpreted cautiously.
- The legacy module remains named `aprs_viewshed_utah_parallel.py`; renaming it is deferred to avoid mixing a large mechanical refactor with propagation changes.
