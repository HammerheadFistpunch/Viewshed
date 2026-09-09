# Signal Peak Roadmap

This roadmap reflects the state of Signal Peak 1.2.0. The guiding principle remains: UI and data-quality improvements must not silently change the established terrain/ITM/link-margin foundation.

## Completed through 1.2.0

### Regional operation

- [x] Remove the hard-coded Utah station validation box.
- [x] Select a local UTM CRS from each job's geography.
- [x] Use broad CONUS elevation sanity checks.
- [x] Derive USGS 3DEP terrain requests from the actual job region.

### Job workflow

- [x] Cancel running jobs from the UI.
- [x] Preserve shared DEM cache on cancellation.
- [x] Reuse the application for repeated jobs without restarting.
- [x] Keep Station mode scoped to the latest Area station search, with an explicit full-cache option.

### Station corrections and confidence

- [x] Separate coordinate confidence from freshness.
- [x] Provide Needs Review / Show All correction queues.
- [x] Add Standard/Topo basemap switching.
- [x] Add OpenStreetMap communications-site cross-reference.
- [x] Require human approval before moving a model coordinate.

### Propagation assumptions

- [x] Use the 138 dB reference operational path-loss cap.
- [x] Use 1080 reference radials with reduced lateral gap fill.
- [x] Provide persistent Advanced Area/Station assumptions.
- [x] Allow Area/Station TX power entry in Watts or dBm while keeping dBm internally.
- [x] Allow per-station height, TX power, gain, frequency, and path-loss overrides.
- [x] Resolve station RF values with user override → station JSON → Advanced fallback precedence.

### Station data workflow

- [x] Add a spreadsheet-style Station Data tab.
- [x] Sort by callsign, station type, position, height, power, gain, frequency, path-loss cap, or source.
- [x] Filter digipeaters and iGates.
- [x] Edit RF fields in place and save callsign-based overrides.
- [x] Store RF overrides separately from APRS/cache position records so refreshes do not erase curated RF data.

### Operator units

- [x] Add Metric / Imperial input-display selection in Advanced.
- [x] Keep all propagation backend distance/height calculations metric.
- [x] Convert Imperial values before jobs reach the propagation engine.

### Network output presentation

- [x] Retain individual per-station link-margin viewsheds.
- [x] Add a network best-margin surface.
- [x] Add configurable stepped dB heatmap bands.
- [x] Add a binary inverse/dead-zone layer.
- [x] Add Output-tab controls for band size, display maximum, display floor, and opacity.
- [x] Make the network margin heatmap visible by default in KMZ output.
- [x] Match the KMZ legend to the configured network banding.

### Windows robustness

- [x] Package and smoke-test a portable Windows executable.
- [x] Protect spawned worker logging from Windows legacy `charmap` Unicode failures.

### Documentation

- [x] Maintain bundled Quick Start, User Guide, Propagation Model, Station Data, Location Corrections, Outputs, Troubleshooting, dependency/license notes, Special Considerations, and CONUS documentation.
- [x] Add 1.1.0 and 1.2.0 release notes.
- [x] Provide offline Help/About access to bundled documentation.

## Next recommended work

### 1. Real-world validation

Collect controlled comparisons between modeled margin and observed APRS/mobile reception. Use those results to evaluate the 138 dB reference cap, antenna assumptions, and whether named field profiles are justified.

### 2. Improve station RF provenance

Add optional source/provenance notes and confidence metadata for manually curated RF overrides so measured values, published values, APRS PHG-derived values, and operator estimates are distinguishable.

### 3. Preserve below-threshold margin explicitly

The current operational per-station raster intentionally collapses below-threshold cells to nodata. A future diagnostic raster could preserve negative modeled margin with a distinct nodata sentinel.

### 4. DEM-assisted correction review

Add read-only terrain context to Corrections, including elevation at reported/model/proposed coordinates, local elevation delta, optional hillshade, and conservative terrain-plausibility warnings. Terrain context should never automatically relocate a station.

### 5. Large-region projection strategy

Signal Peak currently uses one local UTM CRS per job. If nationwide or very broad multi-zone jobs become important, evaluate a projection/mosaicking strategy designed for that scale.

### 6. Output/GIS refinement

Consider explicit metadata when useful margin reaches the configured calculation boundary, cleaner export of network best-margin and inverse GeoTIFFs, and machine-readable run metadata summarizing radio, station overrides, heatmap, projection, and terrain settings.

### 7. Release engineering

Continue improving dependency pinning, source/binary release pairing required by GPLv2, checksums for published Windows artifacts, and automated tests for per-station RF resolution, unit conversion, CONUS station validation, UTM selection, heatmap band generation, and KMZ layer visibility.
