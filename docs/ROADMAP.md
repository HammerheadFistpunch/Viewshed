# Viewshed Roadmap

This roadmap captures the current product direction after the map-first UI, station confidence/correction workflow, long-run seed builder, and large-DEM memory work.

The guiding principle remains: UI modes and workflow changes must not silently change the underlying propagation foundation. Area, Station, and Custom should continue to feed the same terrain/ITM/link-margin pipeline, with differences limited to explicit site and radio inputs.

## Priority order

1. Cancel a running propagation job.
2. Improve completion and output actions in the UI.
3. Replace or simplify the current heatmap presentation with more operationally useful output categories.
4. Add a topographic basemap option for station corrections.
5. Build the complete user/developer documentation set.
6. Add an About / Help interface that exposes documentation, dependency/license information, and special considerations.
7. Add DEM-assisted correction tools such as elevation readout and hillshade/terrain visualization.
8. Add terrain-based station-location plausibility checks that warn for suspicious sites without automatically relocating them.

## 1. Cancel a running job

Add a visible **Cancel Run** control while propagation is active.

Desired behavior:

- Ask for confirmation before stopping a run.
- Stop the worker process cleanly where possible.
- Mark the job as **Cancelled**, not **Failed**.
- Preserve reusable DEM tiles already downloaded into the shared cache.
- Remove or clearly mark incomplete job outputs/intermediates where safe.
- Longer term, add cooperative cancellation checkpoints inside the worker instead of relying only on process termination.

## 2. Completion and output actions

When a job completes, the application should make the result immediately accessible from the UI.

Preferred actions:

- **Open output folder**
- **Open KMZ**
- **Open GeoTIFF**
- **Copy output path**

Because Viewshed is a desktop application and outputs are already local files, opening or exposing the files is preferred over describing this as a download workflow.

## 3. Coverage presentation / heatmap replacement

The current continuous link-margin heatmap can imply more precision than the underlying installation assumptions justify and is not the most useful default visualization.

The preferred default presentation is categorical coverage:

- **Strong** — at least 20 dB remaining operational margin
- **Good** — 10 to 20 dB
- **Marginal** — 0 to 10 dB
- **No predicted operational coverage** — below the assumed operating threshold

The exact thresholds remain tied to the explicit reference radio profile and should be documented in the output legend.

For Area analysis, add an operational overlap product showing how many modeled infrastructure sites cover each point, for example:

- 0 stations
- 1 station
- 2 stations
- 3+ stations

Raw link-margin GeoTIFF output should remain available for advanced/technical analysis even if the default KMZ/UI presentation becomes categorical.

## 4. Topographic basemap for corrections

The Corrections workflow should support a topographic basemap so ridges, peaks, valleys, roads, and named terrain features are visible while reviewing station positions.

Initial map layer choices should move toward:

- Standard map
- Topographic map
- Additional imagery/terrain layers if practical and license-compatible

The first topo implementation should remain independent of the propagation engine.

## 5. Complete documentation set

Build and maintain a complete documentation package. Planned documents:

- `README.md` — project overview and entry point
- `docs/QUICK_START.md` — shortest path from EXE to first result
- `docs/USER_GUIDE.md` — Area, Station, Custom, Corrections, Seed Builder, outputs, and settings
- `docs/PROPAGATION_MODEL.md` — DEM, ITM/Longley-Rice, path loss, link margin, reference radio assumptions, and large-area resolution handling
- `docs/STATION_DATA.md` — APRS-IS, aprs.fi fallback, cache, optional seed files, and long-run seed generation
- `docs/LOCATION_CORRECTIONS.md` — confidence scoring, reported/model coordinates, candidate vs reviewed corrections, and provenance
- `docs/OUTPUTS.md` — KMZ, GeoTIFF, overlap/categorical products, directories, and interpretation
- `docs/TROUBLESHOOTING.md` — acquisition, map, DEM, memory, propagation, and packaging issues
- `docs/LICENSES_AND_DEPENDENCIES.md` — runtime/build dependencies, licenses, and attribution requirements
- `docs/SPECIAL_CONSIDERATIONS.md` — modeling assumptions and limitations that users must understand

Documentation should reflect the shipped UI and behavior rather than legacy prototype workflows.

## 6. About / Help interface

Add an in-application **About / Help** area with access to:

- Viewshed version
- project description
- README
- Quick Start
- User Guide
- propagation/model assumptions
- dependency and license list
- special considerations
- location of `ViewshedData`
- optional diagnostic/version information useful for troubleshooting

For the portable Windows build, these documents should be bundled with the EXE and remain available offline.

## 7. DEM-assisted correction view

Viewshed already downloads USGS 3DEP DEM data for propagation. Reuse that data to make correction review more informative.

Desired capabilities:

- Show elevation at the reported station coordinate.
- Show elevation at the proposed/model coordinate.
- Render hillshade or another terrain visualization derived from the DEM where practical.
- Keep the raw APRS-reported point visible while displaying the proposed/reviewed point separately.

Example station information:

```text
Reported elevation: 1,302 m
Proposed elevation: 2,756 m
```

This is particularly useful for infrastructure expected to be on peaks or ridgelines.

## 8. Terrain-based location plausibility checks

Extend location confidence with terrain-derived warnings while preserving human review as the authority for corrections.

Potential checks include:

- reported elevation relative to nearby terrain
- local percentile/rank of the reported point
- distance to substantially higher terrain
- large inconsistency between a station expected to be mountaintop infrastructure and a low-lying reported point

Example warning:

```text
Reported elevation: 1,287 m
Highest terrain within 15 km: 2,755 m
Reported point is in the lower 20% of local terrain.
Location may be inconsistent with a mountaintop infrastructure site.
```

These checks must only **warn or suggest review**. Viewshed should not automatically move a station to a nearby summit based on terrain or callsign/name.

## Special considerations to document prominently

The documentation and About/Help system should make the following limitations explicit:

- APRS station positions may be stale, incomplete, or incorrect.
- Station antenna height, ERP, feedline loss, and antenna pattern are generally not available from APRS data.
- Area and Station modes use an explicit reference radio profile rather than claiming to know each site's real installation parameters.
- Coverage is a terrain/propagation prediction, not a communications guarantee.
- Weather, vegetation, buildings, local clutter, polarization mismatch, receiver quality, coax loss, and other real-world factors are not fully modeled.
- APRS-IS live observations are samples of a live packet stream, not a complete station directory.
- aprs.fi is optional and only used when configured.
- Seed files are optional fallback/continuity data and may themselves contain stale coordinates.
- Reviewed location corrections alter the model coordinate while preserving the reported coordinate and correction provenance.
- Extremely large analyses may use a reduced-resolution analysis DEM to keep memory bounded; this behavior must be reported in logs and documentation.

## Longer-term direction

After the priorities above, continue toward:

- cleaner separation of terrain, propagation, station-source, and export modules
- improved generalized CRS/geography support beyond the original Utah prototype assumptions
- output clipping to the user-requested analysis region
- stronger automated tests around station acquisition, location corrections, large DEMs, cancellation, and output products
- map-centered workflows that remain interchangeable front ends to one common propagation engine
