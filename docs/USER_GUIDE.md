# Signal Peak User Guide

## Overview

Signal Peak is a map-first VHF/APRS propagation-analysis application. Area, Station, and Custom modes use the same terrain/ITM/link-margin foundation; the difference is how the site and radio inputs are selected.

Version 2.0.0 adds resource-aware terrain-detail presets, live RAM/CPU visibility, dynamic parallel-worker limits, resolution-aware DEM caching, and stricter Area scoping. Version 1.2.0 introduced persistent per-station RF overrides, the Station Data editor, and Metric/Imperial input/display selection.

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

Station acquisition may inspect infrastructure outside the Area radius so nearby stations can be discovered reliably. Before propagation, Signal Peak 2.0.0 clips the acquired station set back to station centers inside the selected Area radius. This prevents a seed file or wide acquisition search from expanding the modeled Area beyond what the operator selected.

## Resources mode

The **Resources** tab controls terrain-detail/resource planning without changing the RF assumptions themselves.

### Terrain detail presets

- **Auto** — selects a safe balanced plan from the actual station set, requested range, and currently available system resources.
- **Fast** — favors faster execution and lower memory use.
- **Standard** — balances speed and terrain detail.
- **High** — increases terrain detail and preserves smaller terrain features at a higher memory/compute cost.
- **Max** — prioritizes stability first and terrain resolution second. Signal Peak may reduce parallel processing to a single station at a time. Large Max runs can be **very slow**.

The selected preset is translated immediately before a propagation run into concrete values for terrain resolution, DEM dimensions, analysis raster dimensions, and safe worker count.

### Memory limit

**Memory limit (GB)** is an optional ceiling for planning. `0` means automatic.

Signal Peak reads currently available RAM, keeps a reserve for Windows and other applications, and then determines how many worker processes can run without exceeding the safe budget. A user-supplied memory limit can further reduce that budget. The limit is a planning ceiling; Signal Peak does not intentionally allocate the full amount.

### CPU and worker planning

The Resources tab reports logical CPUs, physical cores when available, and current CPU load when the operating system exposes it. CPU count establishes an upper bound, while memory safety can reduce the actual parallel-worker count below that bound.

This means higher-detail presets do not simply increase worker count or force a fixed raster size. The planner may trade parallelism for terrain resolution to remain stable.

## Resolution-aware DEM cache

Signal Peak 2.0.0 records terrain cache information with the detail/resolution needed to determine whether a cached DEM is suitable for a later run.

A cached terrain product is reused when it meets or exceeds the requested resolution. If a later run asks for finer terrain detail than the cache provides, Signal Peak prepares/downloads a higher-resolution terrain product instead of silently reusing the coarser one.

## Station mode

Station mode runs the same propagation engine for one known station.

After an Area **Find stations** operation, the Station dropdown is scoped to that search's station set rather than the entire cumulative cache. Use **Load full cached catalog** when you explicitly want every cached station.

Select a station, choose the maximum calculation range, and run the job. Reviewed coordinate corrections and saved station-specific RF overrides are honored.

## Custom mode

Custom mode models a proposed/future station. Click the map to place the site, then enter maximum calculation range, antenna height AGL, transmitter power in Watts, transmitter antenna gain, and frequency.

Custom mode calculates its own job-specific path-loss budget from the entered transmitter assumptions plus the reference receiver assumptions and operational reserve. It does not automatically inherit the Area/Station Advanced path-loss cap.

## Corrections mode

Corrections preserves three concepts separately:

- **Reported coordinate** — original APRS/seed/cache coordinate.
- **Model coordinate** — coordinate currently used for propagation.
- **Proposed/reviewed coordinate** — human-selected candidate or approved override.

The default queue shows stations needing attention and sorts lower-confidence entries first. **Show All** exposes the full correction catalog. OSM corroboration is evidence only and never silently relocates a station.

## Station Data mode

The **Station Data** tab is the spreadsheet-style editor for station-specific RF assumptions.

Double-click height, power, gain, frequency, or path-loss cells to edit them. Use **Save edits** to persist changes. Use **Clear selected overrides** to return selected stations to their station-JSON value or Advanced fallback.

Saved edits are stored in `ViewshedData/station_rf_overrides.json`, keyed by callsign. They are deliberately separate from APRS/cache position data so a live refresh can update station location/status without erasing manually curated RF values.

Effective RF precedence is:

1. Station Data user override;
2. station JSON RF value;
3. Advanced/global fallback.

## Advanced mode

Advanced settings apply to Area and Station runs and persist in `ViewshedData/advanced_settings.json`.

Radio/link settings include operational path-loss cap, TX power, TX/RX antenna gain, RX sensitivity, antenna heights, observer height, frequency, and ITM environmental assumptions. **TX power can be entered in Watts or dBm.** Signal Peak converts Watts to dBm before link-budget calculation.

### Metric / Imperial input mode

The Advanced tab contains the application input-unit selector:

- **Metric (km / m)**
- **Imperial (mi / ft)**

Changing this setting converts distance and height fields in the operator UI. It does not switch the propagation engine into an imperial backend. Jobs are converted back to metric before propagation, and link-budget power remains dBm internally.

## Output mode

The **Output** tab controls how the modeled result is presented without changing the underlying ITM path-loss calculation.

- **Heatmap band size (dB)** — default 3 dB.
- **Maximum displayed margin (dB)** — top of the network heatmap color scale.
- **Overlay / inverse opacity (%)** — transparency of network and inverse overlays.
- **Per-station display floor (dB)** — display threshold used for individual station viewsheds.

## Network heatmap and inverse coverage

The **Granular Network Margin** layer keeps the highest remaining modeled link margin available from any included station at each cell. `0 dB` is the modeled operational edge.

**Inverse Coverage — APRS Not Expected** marks cells inside the requested analysis region where no included station has positive modeled margin. The inverse product is binary and should not be interpreted as a negative-margin gradient.

## CONUS operation

Signal Peak uses normal WGS84 station validation, selects a local UTM projection from the job location, and derives USGS 3DEP terrain requests from the actual geography. Very broad jobs spanning multiple UTM zones should still be interpreted cautiously because one projected CRS is used per job.

## Cancelling and repeating jobs

While a propagation job is active, click **Cancel Run**. Signal Peak asks for confirmation and terminates the worker process tree. Shared DEM cache files are preserved.

Completed runs can be followed immediately by another run; the workspace clears stale completion state when new Area, Station, or Custom inputs are selected.

## Completed outputs

After a successful run, the header provides **Open Output Folder**, **Open KMZ**, and **Open GeoTIFF**.

## Help / About

Help/About provides offline access to the bundled README, quick start, current release notes, propagation/model documentation, station/correction documentation, output interpretation, license/dependency notes, special considerations, and the current `ViewshedData` directory.
