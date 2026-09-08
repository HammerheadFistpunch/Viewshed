# Signal Peak 1.1.0 Release Notes

Signal Peak 1.1.0 expands the application from its Utah-focused origins into a practical CONUS regional propagation tool and adds network-level output products designed for area analysis.

## New in 1.1.0

### CONUS regional support

- Removed the hard-coded Utah station-coordinate gate.
- Selects the local UTM zone from each job's geography.
- Uses broad CONUS elevation sanity limits while retaining DEM-pit warnings.
- Continues to use USGS 3DEP terrain derived from the actual requested region.

### Granular network heatmap

- Adds a **Granular Network Margin** KMZ layer.
- Combines successfully modeled station rasters by taking the best remaining link margin at each cell.
- Uses configurable stepped dB bands; 3 dB is the default.
- Opens visible by default in the KMZ.
- Includes a legend generated from the same band size and maximum displayed margin.

### Inverse coverage

- Adds **Inverse Coverage — APRS Not Expected**.
- Marks cells inside the requested analysis region where no included station has positive modeled remaining margin.
- Ships as a toggleable KMZ layer and supporting GeoTIFF/PNG work products.

### Output controls

The new **Output** tab exposes:

- heatmap band size
- maximum displayed margin
- overlay/inverse opacity
- per-station display floor

### TX power input

Area/Station Advanced settings can use **Watts or dBm** for transmitter power. Watts are converted to dBm internally before link-budget math. Custom mode remains a simple Watts-based site input.

### Station workflow

After an Area station search, the Station tab now follows that run's station set instead of automatically presenting the cumulative cache. **Load full cached catalog** remains available when the full cache is intentionally needed.

### Windows robustness

Spawned station workers explicitly configure UTF-8-safe output so diagnostic Unicode characters cannot abort an otherwise valid worker on Windows legacy console encodings.

## Modeling notes

The network heatmap represents the best **remaining modeled link margin**, not received power measured in dBm and not station-overlap count. `0 dB` means the configured modeled operational edge.

The inverse product is a threshold mask, not a negative-margin gradient. The current operational per-station raster does not preserve reliable below-threshold negative margin values for that purpose.

## Compatibility

The legacy ITM worker and its internal Utah-oriented module filename remain in place to avoid unnecessary propagation-engine refactoring. Signal Peak 1.1.0 changes the surrounding validation, projection, output, and UI layers while retaining the established propagation foundation.
