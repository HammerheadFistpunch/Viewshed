# Signal Peak User Guide

## Overview

Signal Peak 2.2.0 is a map-first VHF/APRS propagation-analysis application. Area, Station, and Custom modes use the same terrain/ITM/link-margin foundation; the difference is how the site and radio inputs are selected.

Version 2.2.0 improves USGS 3DEP / TNMAccess DEM selection and fallback behavior and adds a packaged bulk DEM archive workflow. Exact bbox-scoped NED requests are treated as authoritative, while broad discovery remains filtered to avoid unrelated products. The bulk downloader supports resume-safe downloads and configurable resolution, geographic extent, output location, workers, timeouts, retries, discovery-only mode, and refresh mode.

Version 2.1.0 added independent output-layer selection, unified heat-map styling, positive/gap/redundancy products, clearer correction states, Corrections rendering fixes, and removed the legacy user-facing worker DEM dimension control from Advanced. The Resources model now owns DEM sizing and worker planning.

## Shared APRS / data settings

The top of the application contains shared acquisition settings:

- **APRS callsign** — optional receive-only APRS-IS login input.
- **aprs.fi key** — optional and session-only.
- **Live sample (s)** — APRS-IS sampling duration.
- **Optional seed/fallback** — an optional JSON station source.
- **Build Seed…** — performs a longer APRS collection and writes reusable seed JSON.

## Area mode

Area mode is the normal regional workflow.

1. Choose the center and **Area radius**.
2. Set **Max calculation range** for each station.
3. Select Digipeaters and/or iGates.
4. Click **Find stations**.
5. Inspect the station set and review location concerns.
6. Review **Station Data** if you have known per-station RF values.
7. Configure Resources, Advanced, and Output settings if needed.
8. Click **Run area propagation**.

Station acquisition may inspect infrastructure outside the Area radius so nearby stations can be discovered reliably. Before propagation, Signal Peak clips the acquired station set back to station centers inside the selected Area radius.

## Resources mode

The **Resources** tab controls terrain-detail/resource planning without changing RF assumptions.

### Terrain detail presets

- **Auto** — selects a safe balanced plan from the actual station set, requested range, and currently available system resources.
- **Fast** — favors faster execution and lower memory use.
- **Standard** — balances speed and terrain detail.
- **High** — increases terrain detail at a higher memory/compute cost.
- **Max** — prioritizes stability first and terrain resolution second. Signal Peak may reduce parallel processing to one station at a time. Large Max runs can be very slow.

The selected preset is translated immediately before propagation into concrete terrain resolution, DEM dimensions, analysis raster dimensions, and safe worker count.

### Memory limit

**Memory limit (GB)** is an optional planning ceiling. `0` means automatic.

Signal Peak reads currently available RAM, keeps a reserve for Windows and other applications, and determines how many worker processes can run without exceeding the safe budget. A user-supplied memory limit can further reduce that budget.

### DEM sizing ownership

The Resources model owns DEM sizing and worker-count selection. The former **Worker DEM max dimension (px)** field is no longer exposed in Advanced. Internal compatibility values may still exist in job configuration, but the operator controls detail through Resources.

## Resolution-aware DEM cache

Cached terrain is reused when it meets or exceeds the requested detail. If a later run asks for finer terrain detail than the cache provides, Signal Peak prepares a higher-resolution terrain product instead of silently reusing the coarser one.

For long-lived offline operation, the standalone bulk DEM archive workflow can build a separate frozen USGS 3DEP archive without changing normal per-run cache behavior.

## Station mode

Station mode runs the same propagation engine for one known station.

After an Area **Find stations** operation, the Station dropdown is scoped to that search's station set rather than the entire cumulative cache. Use **Load full cached catalog** when you explicitly want every cached station.

Reviewed coordinate corrections and saved station-specific RF overrides are honored.

## Custom mode

Custom mode models a proposed/future station. Click the map to place the site, then enter maximum calculation range, antenna height AGL, transmitter power, transmitter antenna gain, and frequency.

Custom mode uses the same Output-layer and styling controls as the other run types.

## Corrections mode

Corrections preserves three coordinate concepts separately:

- **Reported coordinate** — original APRS/seed/cache coordinate.
- **Model coordinate** — coordinate currently used for propagation.
- **Proposed/reviewed coordinate** — human-selected candidate or approved override.

Reviewed corrections are stored in `ViewshedData/station_location_overrides.json`, independently of seed and station-cache files, and are reapplied by callsign on later runs.

Correction state is displayed as one of:

- **Saved correction — approved and used for propagation**
- **Needs review — saved candidate awaiting approval**
- **Needs review**
- **Uncorrected**

The default queue emphasizes stations needing attention. If that queue is empty, the full correction catalog can be shown instead. The current station is redrawn after the Corrections tab becomes visible to avoid the blank-map behavior seen in earlier builds.

OSM corroboration remains evidence only and never silently relocates a station.

## Station Data mode

The **Station Data** tab is the spreadsheet-style editor for station-specific RF assumptions.

Saved edits are stored in `ViewshedData/station_rf_overrides.json`, keyed by callsign. They are deliberately separate from APRS/cache position data.

Effective RF precedence is:

1. Station Data user override;
2. station JSON RF value;
3. Advanced/global fallback.

## Advanced mode

Advanced settings contain RF/link-budget assumptions, antenna heights, observer height, frequency, ITM environmental assumptions, and input/display units. **TX power can be entered in Watts or dBm.** Signal Peak converts Watts to dBm before link-budget calculation.

The legacy worker DEM dimension control is intentionally absent because Resources owns compute/detail planning.

## Output mode

The **Output** tab controls how the modeled result is presented without changing the underlying propagation math.

### Presets

- **Standard** — station pins/metadata plus composite heat map.
- **Coverage Analysis** — stations, composite heat map, positive coverage, coverage gaps, and redundancy.
- **Station Analysis** — stations plus per-station heat maps.
- **Everything** — enables all current output layers.
- **Custom** — explicit layer-by-layer selection.

### Layers

Current independently selectable layers are:

- Station pins / metadata
- Composite heat map
- Positive coverage
- Coverage gaps
- Coverage redundancy
- Per-station heat maps

Station pins do not imply coverage overlays. Per-station heat maps are stored separately from the station metadata folders in KMZ output.

### Styling

Composite and per-station heat maps use the same stepped remaining-link-margin palette. The weak-to-strong heat-map colors can be customized without changing the underlying margin thresholds. Positive coverage, gap coverage, and redundancy class colors are also configurable.

The heat-map band size controls the displayed dB steps, while maximum displayed margin sets the top of the color scale. Overlay opacity controls raster transparency.

## Coverage products

**Composite heat map** keeps the strongest remaining modeled link margin available from any included station at each cell.

**Positive coverage** identifies cells where at least one included station has positive remaining margin.

**Coverage gaps** identify cells within the analysis area where no included station has positive remaining margin.

**Coverage redundancy** counts how many stations provide positive remaining margin:

- 1 station — single-source / fragile coverage
- 2 stations — some redundancy
- 3+ stations — stronger redundancy

`0 dB` remaining margin is the modeled operational edge.

## Cancelling and repeating jobs

While a propagation job is active, click **Cancel Run**. Signal Peak terminates the worker process tree while preserving shared DEM cache files.

Completed runs can be followed immediately by another run; the workspace clears stale completion state when new Area, Station, or Custom inputs are selected.

## Completed outputs

After a successful run, the header provides **Open Output Folder**, **Open KMZ**, and **Open GeoTIFF**.

## Help / About

Help/About reports **Signal Peak 2.2.0** and provides offline access to the bundled README, Quick Start, current release notes, propagation/model documentation, station/correction documentation, output interpretation, license/dependency notes, and the current `ViewshedData` directory.
