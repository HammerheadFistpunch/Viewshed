# CONUS branch

This branch removes the propagation engine's hard-coded Utah projection assumption while retaining the established ITM/Longley-Rice station worker.

## Geographic behavior

Viewshed now chooses a projected UTM CRS from the geographic center of the stations in each job. The selected zone is written to the run log.

Examples:

- Salt Lake City: UTM 12N / EPSG:32612
- Denver: UTM 13N / EPSG:32613
- Los Angeles: UTM 11N / EPSG:32611
- New York City: UTM 18N / EPSG:32618

The projected working DEM is named by the selected zone, such as `region_dem_utm_z13N.tif`, so a cached Utah Zone 12 projection cannot be accidentally reused for a job elsewhere.

## Terrain source

Terrain acquisition continues to use USGS 3DEP 1-arcsecond elevation data. The tile request is derived from the actual station coordinates and propagation radius rather than a Utah bounding box. This makes the current terrain pipeline appropriate for CONUS without replacing the DEM provider.

The legacy source-mosaic implementation still has some Utah-flavored internal names. Those names are implementation history rather than geographic constraints and can be cleaned up independently.

## Elevation checks

The old Utah-oriented 800–4200 m station-elevation sanity range is not used by the CONUS projection adapter. It uses a broad -200 to 5000 m range instead, while retaining the local DEM-pit check.

## Modeling behavior

The CONUS adapter does not change the per-station ITM propagation math, reference link-budget assumptions, radial sampling, or canyon-gap-fill tuning. Its purpose is geographic generalization of the raster projection and validation layer.

## Current limits

- USGS 3DEP remains the terrain provider, so this branch is aimed at the United States rather than global coverage.
- A job uses one local UTM zone selected from its station set. Very large jobs spanning several UTM zones should be treated cautiously; a future nationwide-scale projection strategy may be preferable for unusually broad single jobs.
- The legacy module is still named `aprs_viewshed_utah_parallel.py`; renaming it is deferred to avoid mixing a large mechanical refactor with the projection change.
