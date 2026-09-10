# Signal Peak 2.0.0 Release Notes

Signal Peak 2.0.0 is the resource-planning and terrain-detail release. It keeps the established terrain-profile, Longley-Rice/ITM, path-loss, link-margin, station-correction, and per-station RF foundations while making large jobs safer and more predictable.

## Terrain detail presets

The new **Resources** tab provides five operator-facing detail levels:

- **Auto** — safe balanced planning from the actual run and currently available system resources.
- **Fast** — favors lower memory use and faster completion.
- **Standard** — balances speed and terrain detail.
- **High** — preserves smaller terrain features at a higher compute/memory cost.
- **Max** — prioritizes stability first and terrain resolution second. Parallel processing may be reduced to one station at a time, and large Max runs can be very slow.

The selected preset is translated immediately before each run into concrete DEM sizing, analysis raster sizing, and parallel-worker limits.

## Memory-aware worker planning

Signal Peak now reads available system RAM and CPU information when planning a propagation run. The planner reserves memory for Windows and other applications, then limits parallel workers to stay inside the safe budget.

An optional **Memory limit (GB)** lets the operator impose a lower ceiling. `0` leaves memory management automatic.

This allows terrain resolution to be prioritized without blindly increasing concurrency or risking memory overflow.

## Resolution-aware DEM caching

Terrain cache reuse now considers requested detail/resolution. A cached DEM is reused only when it satisfies the resolution required by the current run.

If a later run requests finer terrain than an existing cache product provides, Signal Peak prepares a higher-resolution terrain product instead of silently reusing the coarser cache.

## Area scoping fix

Area station acquisition can intentionally look beyond the selected Area radius so relevant infrastructure can be discovered. In 2.0.0, the final propagation station set is clipped back to station centers inside the selected Area radius.

This fixes the case where a large seed file or acquisition envelope could cause propagation to run the entire seed rather than the operator-selected Area.

## Repeat-run stability

Completed or cancelled jobs no longer leave stale run-state presentation that can interfere with immediately starting a new job. Selecting new Area, Station, or Custom inputs resets the completion presentation while preserving prior outputs.

## Tooltips and operator guidance

Resource-control tooltips now explain:

- what Auto/Fast/Standard/High/Max actually prioritize;
- that Max may fall back to one worker and can be very slow;
- that the memory limit is a planning ceiling rather than a forced allocation;
- that worker count is reduced before risking memory overflow;
- that cached terrain is reused only when it meets the requested resolution.

## Packaging and documentation

- Product version updated to **2.0.0**.
- Windows Actions artifact renamed to `Signal-Peak-Windows-2.0.0`.
- README, Quick Start, User Guide, Help/About release links, and packaged documentation updated for the V2 resource model.
- V2 resource/cache modules explicitly included in the PyInstaller configuration.

## Compatibility and modeling behavior

2.0.0 does not intentionally change the established APRS/VHF RF interpretation, station-specific RF precedence, ITM model foundation, or network margin/inverse-coverage meaning. The principal change is how terrain detail and compute resources are selected and protected.
