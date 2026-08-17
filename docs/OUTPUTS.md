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

The KMZ is intended for visual inspection in Google Earth or another compatible viewer. It contains station placemarks and **per-station** modeled coverage overlays.

The composite/combined coverage view has been removed from the KMZ. Overlap counts can be useful for GIS processing, but they do not communicate the modeled link margin of any particular station and were too easy to misread as a propagation result.

Toggle individual station folders to compare predicted footprints and terrain shadows directly.

## GeoTIFF

`coverage_count.tif` may still be written as an internal/analysis merge raster for compatibility and GIS processing. It counts how many per-station rasters have positive modeled margin at each grid cell; it is **not** a signal-strength surface.

Per-station rasters under the work directory retain modeled link-margin values and are the more meaningful technical output when evaluating a particular station.

## Per-station link margin

Per-station modeled link margin uses 0 dB as the reference operational edge. Positive margin indicates remaining modeled budget; below-threshold values are not treated as reliable operational coverage.

The displayed coverage therefore represents modeled operational margin for each station rather than a composite count category.

## Hard circular edges

A clean circular edge centered on a station usually indicates the configured **maximum calculation range**, not a physical propagation boundary.

If modeled margin remains positive at that range, the calculation stops before the model reaches its predicted edge. Increase maximum calculation range if the analysis requires following that lobe farther, while considering runtime and DEM size.

## Large-area resolution

For very large geographic jobs, Viewshed may reduce terrain-analysis resolution to remain memory bounded. This can reduce fine terrain detail compared with a small-area run. The job log should be retained with the outputs because it records terrain preparation and analysis settings.

## Interpreting results

Coverage output is a prediction based on terrain and configured radio/model assumptions. It does not include every real-world factor. See `SPECIAL_CONSIDERATIONS.md` and `PROPAGATION_MODEL.md` before using results for operational decisions.
