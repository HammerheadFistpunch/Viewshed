# Viewshed User Guide

## Overview

Viewshed is a map-first VHF/APRS propagation-analysis application. Area, Station, and Custom modes all feed the same terrain/ITM/link-margin foundation; the difference is how the site and radio inputs are selected.

## Shared APRS / data settings

The top of the application contains shared acquisition settings:

- **APRS callsign** — optional. If blank, receive-only APRS-IS access can use the fallback login behavior.
- **aprs.fi key** — optional; used only when configured and when an infrastructure callsign was observed but not positioned.
- **Live sample (s)** — APRS-IS sampling duration, normally 45 seconds and limited to 300 seconds.
- **Optional seed/fallback** — a JSON station file used for continuity and long-lived station knowledge. It is not required for normal live discovery.
- **Build Seed…** — starts a longer APRS collection session and writes a reusable seed JSON.

## Area mode

Area mode is the normal regional workflow.

1. Choose the center and **Area radius**.
2. Set the station **maximum calculation range**. This is the maximum distance calculated from each station; it can create a hard edge if useful predicted margin still exists at that limit.
3. Select Digipeaters and/or iGates.
4. Click **Find stations**.
5. Inspect the station list and review location concerns.
6. Click **Run area propagation**.

Finding stations is intentionally separate from running RF math. The resulting station set is frozen for the propagation job so the map you reviewed is the set that is analyzed.

## Station mode

Station mode runs the same propagation engine for one known station.

Select a station, choose the maximum calculation range, and run the job. Reviewed coordinate corrections are honored.

## Custom mode

Custom mode models a proposed/future station.

Click the map to place the site, then enter:

- maximum calculation range
- antenna height AGL
- transmitter power
- transmitter antenna gain
- frequency

Custom mode calculates its own job-specific path-loss budget from the entered transmitter assumptions plus the reference receiver assumptions and operational reserve. It does not automatically inherit the Area/Station Advanced path-loss cap.

## Corrections mode

Corrections preserves three concepts separately:

- **Reported coordinate** — the original APRS/seed/cache coordinate.
- **Model coordinate** — the coordinate currently used for propagation.
- **Proposed/reviewed coordinate** — a human-selected candidate or approved override.

The default queue shows stations needing attention and sorts lower-confidence entries first. **Show All** exposes the full station catalog. **Next** advances through the current queue. Saving or approving a correction automatically advances when possible.

### OSM cross-reference

Viewshed can cross-reference nearby OpenStreetMap communications infrastructure through Overpass.

- A very close match corroborates the existing station coordinate.
- A moderate match is useful context but is not conclusive.
- A distant/ambiguous match can keep weak-provenance data in the review queue.
- No OSM match does not prove the APRS coordinate is wrong because OSM is incomplete.
- OSM never silently relocates a station.

**Use OSM point** copies the matched feature into the proposed correction fields. Human approval is still required before that coordinate becomes the model coordinate.

### Topographic map

Corrections includes **Topo** and **Standard** basemap controls. The topo view is intended to make ridges, peaks, valleys, roads, and named terrain more visible during site review.

## Advanced mode

Advanced settings apply to Area and Station runs and persist in `ViewshedData/advanced_settings.json`.

Radio/link settings include:

- operational path-loss cap
- TX power
- TX antenna gain
- RX sensitivity
- RX antenna gain
- digipeater and iGate antenna heights
- receiver/observer height
- frequency

Propagation/compute settings include:

- radial count
- displayed margin floor
- maximum displayed margin
- worker DEM maximum dimension
- ITM climate
- surface refractivity
- ground conductivity
- relative permittivity
- polarization

Use **Reset to Viewshed defaults** to restore the reference profile. Advanced values are range-validated, but a value can be numerically valid and still be physically inappropriate for a particular analysis.

## Cancelling a job

While a propagation job is active, click **Cancel Run**. Viewshed asks for confirmation and terminates the worker process tree. Shared DEM cache files are preserved. A cancelled job is reported as **Cancelled**, not **Failed**.

## Completed outputs

After a successful run, the header provides:

- **Open Output Folder**
- **Open KMZ**
- **Open GeoTIFF**

The completion dialog can also open the output directory immediately.

See `OUTPUTS.md` for interpretation details.

## Seed Builder

Use **Build Seed…** when you want a longer APRS collection than the normal Area sample. The builder accumulates infrastructure observations and positions throughout the session and can save the result under `ViewshedData/seeds/` for future fallback use.

## Help / About

The Help/About area provides offline access to the bundled README and documentation, dependency/license notes, special considerations, and the current `ViewshedData` directory.
