# Signal Peak User Guide

## Overview

Signal Peak is a map-first VHF/APRS propagation-analysis application. Area, Station, and Custom modes use the same terrain/ITM/link-margin foundation; the difference is how the site and radio inputs are selected.

Version 1.1.0 adds CONUS-oriented station validation/projection, a network best-margin heatmap, inverse/dead-zone output, heatmap presentation controls, run-scoped Station lists, and Watts/dBm input for Area/Station TX power.

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
6. Configure Advanced and Output settings if needed.
7. Click **Run area propagation**.

Finding stations is intentionally separate from RF math. The reviewed station set is frozen for the propagation job.

## Station mode

Station mode runs the same propagation engine for one known station.

After an Area **Find stations** operation, the Station dropdown is scoped to that search's station set rather than the entire cumulative cache. Use **Load full cached catalog** when you explicitly want every cached station.

Select a station, choose the maximum calculation range, and run the job. Reviewed coordinate corrections are honored.

## Custom mode

Custom mode models a proposed/future station. Click the map to place the site, then enter maximum calculation range, antenna height AGL, transmitter power in Watts, transmitter antenna gain, and frequency.

Custom mode calculates its own job-specific path-loss budget from the entered transmitter assumptions plus the reference receiver assumptions and operational reserve. It does not automatically inherit the Area/Station Advanced path-loss cap.

## Corrections mode

Corrections preserves three concepts separately:

- **Reported coordinate** — original APRS/seed/cache coordinate.
- **Model coordinate** — coordinate currently used for propagation.
- **Proposed/reviewed coordinate** — human-selected candidate or approved override.

The default queue shows stations needing attention and sorts lower-confidence entries first. **Show All** exposes the full correction catalog. OSM corroboration is evidence only and never silently relocates a station.

## Advanced mode

Advanced settings apply to Area and Station runs and persist in `ViewshedData/advanced_settings.json`.

Radio/link settings include operational path-loss cap, TX power, TX/RX antenna gain, RX sensitivity, antenna heights, observer height, and frequency. **TX power can be entered in Watts or dBm.** Signal Peak converts Watts to dBm before the link-budget calculation, so the propagation engine continues to use dBm internally.

Propagation/compute settings include radial count, worker DEM maximum dimension, ITM climate, surface refractivity, ground conductivity, relative permittivity, and polarization.

Use **Reset to Viewshed defaults** to restore the reference profile.

## Output mode

The **Output** tab controls how the modeled result is presented without changing the underlying ITM path-loss calculation.

- **Heatmap band size (dB)** — default 3 dB. Smaller values create more granular color steps.
- **Maximum displayed margin (dB)** — top of the network heatmap color scale.
- **Overlay / inverse opacity (%)** — transparency of network and inverse overlays.
- **Per-station display floor (dB)** — display threshold used for individual station viewsheds.

## Network heatmap

The **Granular Network Margin** layer combines all successfully modeled stations. At each map cell, Signal Peak keeps the highest remaining modeled link margin available from any included station.

The stepped palette progresses blue → cyan → green → yellow → orange → red as remaining margin increases. The legend uses the same configured band size and maximum margin. `0 dB` is the modeled operational edge.

For a Station run, the same product is generated with one station contributing.

## Inverse coverage

**Inverse Coverage — APRS Not Expected** marks cells inside the requested analysis region where no included station has positive modeled margin. It is off by default in the KMZ.

The inverse product is binary. It should not be interpreted as a negative-dBm or negative-margin gradient.

## CONUS operation

Signal Peak no longer uses the legacy Utah station bounding box. Jobs select a local UTM projection from the job location, and USGS 3DEP terrain requests are derived from the actual geography. The selected UTM zone is written to the log.

Very broad jobs spanning multiple UTM zones should still be interpreted cautiously because one projected CRS is used per job.

## Cancelling a job

While a propagation job is active, click **Cancel Run**. Signal Peak asks for confirmation and terminates the worker process tree. Shared DEM cache files are preserved.

## Completed outputs

After a successful run, the header provides **Open Output Folder**, **Open KMZ**, and **Open GeoTIFF**.

The KMZ opens with the network best-margin heatmap visible by default. The inverse layer and individual station viewsheds remain independently toggleable. See `OUTPUTS.md` for interpretation details.

## Help / About

Help/About provides offline access to the bundled README, quick start, release notes, propagation/model documentation, station/correction documentation, output interpretation, license/dependency notes, special considerations, and the current `ViewshedData` directory.
