# Viewshed Troubleshooting

## No stations found

- Increase the live APRS sample duration.
- Verify internet access to APRS-IS.
- Use a longer-running seed built with **Build Seed…**.
- Configure aprs.fi only if desired; it is optional.
- Remember that APRS-IS is a live packet stream, not a complete station directory.

## Many stations show LOW confidence

Open Corrections and inspect the confidence reason. Missing timestamps are freshness information and should not by themselves lower coordinate confidence. Explicit candidates, weak provenance, or material disagreement with OSM corroboration can keep a station in the review queue.

## Corrections list becomes empty

If all current review items are resolved, the UI should report the review queue complete and fall back to the full station catalog. If it does not, restart with the latest build and report the exact workflow that caused it.

## OSM cross-check fails

Overpass is an external service and can be slow or unavailable. Viewshed continues without OSM corroboration. Retry later with **Cross-check OSM**. OSM is optional and never required for propagation.

## Hard circular coverage edges

This normally means the station reached the configured maximum calculation range while still having positive modeled margin. The circle is a calculation boundary, not an RF wall. Increase the range if needed or review the path-loss budget in Advanced.

## Coverage seems too optimistic or pessimistic

Check the **Advanced** tab, especially:

- operational path-loss cap
- TX/RX assumptions
- antenna heights
- frequency
- margin floor

Reset to Viewshed defaults if you are unsure. The current default Area/Station path-loss cap is 148 dB.

## Large job uses too much memory or takes too long

Large areas and long station calculation ranges can span many DEM tiles and many per-station computations. Viewshed bounds DEM memory and worker raster size, but very large jobs can still be expensive. Reduce area radius, maximum calculation range, station count, radial count, or worker DEM dimension.

## DEM download/merge errors

- Verify internet access to USGS services.
- Retry the job; successfully downloaded DEM tiles remain cached.
- If a cached tile is corrupt, remove the affected file under `ViewshedData/cache/dem/` and retry.

## Map tiles do not load

Standard and topo basemaps require internet access. Propagation can still use cached DEM data independently of map tile availability.

## A run is stuck

Use **Cancel Run**. On Windows, Viewshed terminates the worker process tree and preserves the shared DEM cache.

## EXE starts but a feature is missing

Use the newest GitHub Actions `Viewshed-Windows` artifact. The packaged `--self-test` validates core imports/data but does not exercise every interactive map/network workflow.

## Geography outside Utah behaves unexpectedly

The current legacy propagation backend still contains Utah-oriented validation and CRS assumptions. Acquisition and maps are more general than the propagation backend. Full national/generalized propagation remains future work.
