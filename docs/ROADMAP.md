# Signal Peak Roadmap

This roadmap reflects the state of Signal Peak 1.1.0. The guiding principle remains: UI and output improvements must not silently change the established terrain/ITM/link-margin foundation.

## Completed through 1.1.0

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
- [x] Add 1.1.0 release notes.
- [x] Provide offline Help/About access to bundled documentation.

## Next recommended work

### 1. Real-world validation

Collect controlled comparisons between modeled margin and observed APRS/mobile reception. Use those results to evaluate the 138 dB reference cap, antenna assumptions, and whether named field profiles are justified.

### 2. Preserve below-threshold margin explicitly

The current operational per-station raster intentionally collapses below-threshold cells to nodata. A future diagnostic raster could preserve negative modeled margin with a distinct nodata sentinel. That would make it possible to map *how far below threshold* a dead zone is, rather than only where positive operational coverage is absent.

This should be added as a separate diagnostic product so it cannot be confused with the current operational coverage surface.

### 3. DEM-assisted correction review

Add read-only terrain context to Corrections:

- elevation at reported/model/proposed coordinates
- local elevation delta
- optional hillshade
- conservative terrain-plausibility warnings

Terrain context should never automatically relocate a station.

### 4. Large-region projection strategy

Signal Peak currently uses one local UTM CRS per job. Regional jobs are the target use case. If nationwide or very broad multi-zone jobs become important, evaluate a projection/mosaicking strategy designed for that scale.

### 5. Output/GIS refinement

Consider:

- explicit metadata when useful margin reaches the configured calculation boundary
- cleaner export of network best-margin and inverse GeoTIFFs into the primary output folder
- machine-readable run metadata summarizing radio, heatmap, projection, and terrain settings

### 6. Release engineering

Continue improving:

- dependency pinning and audit records
- source/binary release pairing required by GPLv2
- checksums for published Windows artifacts
- automated tests for non-Utah station validation, UTM selection, heatmap band generation, and KMZ layer visibility
