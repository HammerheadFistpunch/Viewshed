# Signal Peak Outputs

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

## Output architecture

Signal Peak 2.1.0 introduced the current output architecture, separating station metadata from coverage visualization. Station pins no longer imply that per-station coverage overlays must also be exported.

The Output tab provides presets plus independent layer selection for:

- Station pins / metadata
- Composite heat map
- Positive coverage
- Coverage gaps
- Coverage redundancy
- Per-station heat maps

Presets are **Standard**, **Coverage Analysis**, **Station Analysis**, **Everything**, and **Custom**.

## Composite heat map

The composite heat map keeps the strongest remaining modeled link margin available from any included station at each cell.

The color scale is stepped in configurable dB bands. `0 dB` is the modeled operational edge. The weak-to-strong palette can be customized without changing the underlying propagation calculation or margin thresholds.

## Per-station heat maps

Individual station heat maps use the same stepped remaining-link-margin palette as the composite heat map. The older station-specific monochrome color scheme is retired.

Per-station heat maps are independent from station pins/metadata and can be omitted without removing the station markers.

## Positive coverage

The Positive Coverage layer marks cells where at least one modeled station has positive remaining link margin. Its display color and opacity are configurable.

## Coverage gaps

The Coverage Gaps layer marks cells inside the requested analysis region where no included station has positive modeled remaining margin.

This is a threshold/dead-zone product, not a negative-margin gradient.

## Coverage redundancy

The Coverage Redundancy layer is derived from the number of modeled stations with positive remaining margin at each cell:

- **1 station** — single-source / fragile coverage
- **2 stations** — some redundancy
- **3+ stations** — stronger network redundancy

The three redundancy classes have configurable colors.

## Styling and opacity

The Output tab controls:

- heat-map band size
- maximum displayed margin
- overlay opacity
- weak-to-strong heat-map palette
- positive coverage color
- coverage-gap color
- redundancy colors

Styling changes presentation only. They do not change terrain, ITM, path-loss, or link-budget math.

## KMZ organization

KMZ output separates stations from coverage products. The current structure is:

```text
Signal Peak Analysis
├─ Stations
├─ Coverage Analysis
│  ├─ Composite Heat Map
│  ├─ Positive Coverage
│  ├─ Coverage Gaps
│  └─ Coverage Redundancy
└─ Per-Station Heat Maps
```

Only selected output products are included. Station pins and per-station heat maps are independent roots so either can be toggled without forcing the other.

## GeoTIFF and raster products

`coverage_count.tif` counts how many unique per-station rasters have positive modeled margin at each grid cell. It is useful for GIS processing and redundancy analysis but is not a signal-strength surface.

The work/output data can also include:

- `network_best_margin.tif` — strongest remaining margin from the modeled network
- `network_margin_bands.png` — rendered composite heat map
- `positive_coverage.png` — positive-coverage mask
- `inverse_coverage.png` — gap/dead-zone mask
- `coverage_redundancy.png` — redundancy classes
- per-station viewshed rasters

## DEM archive tooling

Signal Peak 2.2.1 includes a documented bulk DEM workflow for building reusable offline USGS 3DEP terrain archives. This archive workflow is separate from the normal per-run DEM cache and does not change the propagation output format.

Version 2.2.1 also improves runtime terrain acquisition when TNMAccess returns products whose URLs do not contain the expected tile identifier. Exact bbox-scoped requests are treated as authoritative, while broad discovery remains tile-filtered to avoid unrelated products. This is particularly important for large-area/CONUS runs, where missing or incorrectly rejected DEM products can otherwise interrupt a job.

## Hard circular edges

A clean circular edge centered on a station usually indicates the configured **maximum calculation range**, not a physical propagation boundary. Increase the calculation range if useful modeled margin remains at the edge and a longer analysis is required.

## Units

Metric/Imperial changes operator-facing distance and height input/display only. Propagation and raster coordinate math remain metric internally.

## Interpreting results

Coverage is a prediction based on terrain and configured radio/model assumptions. Review Station Data RF sources, Advanced assumptions, and Resources settings when comparing results.

See `SPECIAL_CONSIDERATIONS.md` and `PROPAGATION_MODEL.md` before using results for operational decisions.
