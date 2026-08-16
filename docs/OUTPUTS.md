# Viewshed Outputs

## Output location

Each job is written under:

```text
ViewshedData/jobs/<timestamp>/
```

Primary exported products are under:

```text
ViewshedData/jobs/<timestamp>/output/
```

The UI provides **Open Output Folder**, **Open KMZ**, and **Open GeoTIFF** after a successful run.

## KMZ

The KMZ is intended for visual inspection in Google Earth or another compatible viewer. It contains station placemarks and coverage overlays.

The combined Area overlay is best interpreted as **coverage overlap**: how many modeled stations meet the selected operational threshold at each location.

Do not interpret the overlay as measured signal strength.

## GeoTIFF

`coverage_count.tif` is the primary combined raster copied into the output directory. Per-station rasters may also exist under the work directory and retain modeled link-margin values.

GeoTIFF output is useful for GIS analysis, archiving, and later processing.

## Coverage categories

Current combined rendering groups overlap into operational categories such as:

- one station
- two to three stations
- four or more stations

Per-station modeled link margin uses 0 dB as the reference operational edge. Positive margin indicates remaining modeled budget; below-threshold values are not treated as reliable operational coverage.

## Hard circular edges

A clean circular edge centered on a station usually indicates the configured **maximum calculation range**, not a physical propagation boundary.

If modeled margin remains positive at that range, the calculation stops before the model reaches its predicted edge. Increase maximum calculation range if the analysis requires following that lobe farther, while considering runtime and DEM size.

## Large-area resolution

For very large geographic jobs, Viewshed may reduce terrain-analysis resolution to remain memory bounded. This can reduce fine terrain detail compared with a small-area run. The job log should be retained with the outputs because it records terrain preparation and analysis settings.

## Interpreting results

Coverage output is a prediction based on terrain and configured radio/model assumptions. It does not include every real-world factor. See `SPECIAL_CONSIDERATIONS.md` and `PROPAGATION_MODEL.md` before using results for operational decisions.
