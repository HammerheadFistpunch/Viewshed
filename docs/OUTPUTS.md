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

## KMZ layers

Signal Peak 1.2.0 retains the network output products introduced in 1.1.0 while allowing each station to use its own RF assumptions when configured.

### Granular Network Margin

This is the default visible network layer. Signal Peak reprojects the successfully modeled per-station rasters onto the job analysis grid and keeps the **best remaining link margin** at each cell.

The color scale is stepped in configurable dB bands. The default is **3 dB per band**, using a blue → cyan → green → yellow → orange → red progression from the modeled operational edge toward stronger remaining margin. The legend is generated from the same configured band size and maximum displayed margin.

This surface is not a count of stations. A cell represents the strongest modeled remaining margin available from any included station.

### Inverse Coverage — APRS Not Expected

The inverse layer marks cells inside the requested analysis region where no included station has positive modeled remaining margin.

This is a threshold/dead-zone product. It does **not** estimate how many dB below threshold a dead-zone cell is because the current per-station operational raster does not preserve a reliable negative-margin surface.

The inverse layer is included in the KMZ but is off by default.

### Per-station viewsheds

Individual digipeater and iGate overlays remain in the KMZ for site-by-site inspection and can be toggled independently from the network layers.

In 1.2.0, those per-station rasters may be based on station-specific height, TX power, gain, frequency, or path-loss cap rather than one shared global assumption set.

## Legend

The KMZ legend shows:

- the stepped best-margin color scale and configured dB band size
- `0 dB` as the modeled operational edge
- the configured maximum displayed margin
- an inverse/dead-zone swatch
- references for the per-station digipeater and iGate overlays

## GeoTIFF products

`coverage_count.tif` counts how many unique per-station rasters have positive modeled margin at each grid cell. It remains useful for GIS processing but is **not** a signal-strength surface.

The work directory also contains:

- `network_best_margin.tif` — best positive/zero remaining margin from the modeled network
- `inverse_coverage.tif` — binary dead-zone mask used to render the inverse layer
- per-station `viewshed_*.tif` rasters

## Per-station link margin

Per-station modeled link margin uses **0 dB** as the reference operational edge. Positive margin indicates remaining modeled budget; below-threshold values are not treated as reliable operational coverage.

## Hard circular edges

A clean circular edge centered on a station usually indicates the configured **maximum calculation range**, not a physical propagation boundary. Increase the calculation range if useful modeled margin is still present at the edge and a longer analysis is required.

## Units

The Metric/Imperial setting does not change output physics or raster coordinate math. It changes operator-facing distance/height input and display only; jobs are converted to metric before propagation.

## Interpreting results

Coverage is a prediction based on terrain and configured radio/model assumptions. Review the Station Data RF-source column and Advanced settings when comparing results, especially when some stations use curated overrides and others use global fallbacks.

See `SPECIAL_CONSIDERATIONS.md` and `PROPAGATION_MODEL.md` before using results for operational decisions.
