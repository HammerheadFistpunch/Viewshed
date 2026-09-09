# Signal Peak Troubleshooting

## No stations found

- Increase the live APRS sample duration.
- Verify internet access to APRS-IS.
- Use a longer-running seed built with **Build Seed…**.
- Configure aprs.fi only if desired; it is optional.
- Remember that APRS-IS is a live packet stream, not a complete station directory.

## Many stations show LOW confidence

Open Corrections and inspect the confidence reason. Missing timestamps are freshness information and should not by themselves lower coordinate confidence. Explicit candidates, weak provenance, or material disagreement with OSM corroboration can keep a station in the review queue.

## OSM cross-check fails

Overpass is an external service and can be slow or unavailable. Signal Peak continues without OSM corroboration. Retry later with **Cross-check OSM**. OSM is optional and never required for propagation.

## Hard circular coverage edges

This normally means the station reached the configured maximum calculation range while still having positive modeled margin. The circle is a calculation boundary, not an RF wall. Increase the range if needed or review the path-loss budget in Advanced.

## Coverage seems too optimistic or pessimistic

Check both **Station Data** and **Advanced**.

A station-specific override takes precedence over station JSON and Advanced defaults, so a single incorrect height/power/gain value can affect one station while the rest of the network looks normal.

Important fields include:

- operational path-loss cap
- TX/RX assumptions
- antenna heights
- frequency
- station-specific power and gain

The current default Area/Station path-loss cap is **138 dB**.

## Station Data edit does not appear to apply

- Click **Save edits** after changing a cell.
- Check the **RF Source** column to confirm the row shows a user override.
- Confirm you are modeling the same callsign shown in the editor.
- Use **Clear selected overrides** if you want to return to station JSON or Advanced defaults.
- The registry is stored in `ViewshedData/station_rf_overrides.json`.

## Height or range looks wrong after switching units

The Metric/Imperial selector in Advanced changes operator-facing distance and height fields only.

- Metric uses km / m.
- Imperial uses mi / ft.
- The backend remains metric.

If a manually researched station height is implausible, verify the source datum. A published value may be AGL, AMSL, HAAT, tower height, or APRS PHG effective height; these are not interchangeable.

## Large job uses too much memory or takes too long

Large areas and long station calculation ranges can span many DEM tiles and many per-station computations. Signal Peak bounds DEM memory and worker raster size, but very large jobs can still be expensive. Reduce area radius, maximum calculation range, station count, radial count, or worker DEM dimension.

## DEM download/merge errors

- Verify internet access to USGS services.
- Retry the job; successfully downloaded DEM tiles remain cached.
- If a cached tile is corrupt, remove the affected file under `ViewshedData/cache/dem/` and retry.

## Map tiles do not load

Standard and topo basemaps require internet access. Propagation can still use cached DEM data independently of map tile availability.

## A run is stuck

Use **Cancel Run**. On Windows, Signal Peak terminates the worker process tree and preserves the shared DEM cache.

## EXE starts but a feature is missing

Use the newest GitHub Actions artifact for the intended release. Signal Peak 1.2.0 Windows builds are named `Signal-Peak-Windows-1.2.0`.

The packaged `--self-test` validates core imports/data but does not exercise every interactive map/network workflow.

## Geography outside Utah behaves unexpectedly

Current Signal Peak uses WGS84 station validation, USGS 3DEP terrain, and a job-local UTM projection for regional CONUS workflows. Very broad jobs spanning several UTM zones should still be interpreted cautiously.
