# Signal Peak 2.1.0 Release Notes

Signal Peak 2.1.0 focuses on output control, correction reliability, and a cleaner separation between propagation, resource planning, and visualization.

## Output architecture

2.1.0 separates station metadata from coverage overlays. Station pins no longer imply that a per-station coverage layer must also be included.

The Output tab now supports presets and independent layer selection for:

- station pins / metadata
- composite heat map
- positive coverage
- coverage gaps
- coverage redundancy
- per-station heat maps

Per-station heat maps now use the same stepped link-margin palette as the composite heat map instead of the older station-specific monochrome color scheme.

## Output styling

Heat-map colors can be customized from weak to strong while keeping the same underlying link-margin thresholds. Positive coverage, coverage gaps, and redundancy classes also have configurable colors.

Available presets are:

- **Standard** — station pins and composite heat map
- **Coverage Analysis** — stations, composite heat map, positive coverage, gaps, and redundancy
- **Station Analysis** — stations and per-station heat maps
- **Everything** — all current output layers
- **Custom** — explicit layer selection

## Coverage redundancy

A new redundancy product shows how many modeled stations provide positive remaining link margin at each location:

- 1 station — single-source / fragile coverage
- 2 stations — some redundancy
- 3+ stations — stronger network redundancy

## Location corrections

Corrections remain stored separately from seed and APRS station data in `ViewshedData/station_location_overrides.json` and are reapplied by callsign on future runs.

The Corrections UI now exposes state more clearly:

- **Saved correction — approved and used for propagation**
- **Needs review — saved candidate awaiting approval**
- **Needs review**
- **Uncorrected**

Corrections rendering and catalog filtering were also stabilized so the selected station is redrawn when the Corrections tab becomes visible and an empty review queue falls back to the full catalog.

## Resources and Advanced

The Resources model now owns DEM sizing and parallel-worker planning. The legacy **Worker DEM max dimension** field is no longer exposed in Advanced.

Terrain-detail modes remain:

- Auto
- Fast
- Standard
- High
- Max

Memory safety is prioritized before speed. Max may reduce processing to a single worker and can be very slow on large jobs.

## Build and packaging

The product version is now consistently reported as **2.1.0** in the application, Help/About, core self-test, documentation, and Windows build artifact name.

The `2.1` branch is included in the Windows GitHub Actions build workflow so branch pushes automatically build and smoke-test `SignalPeak.exe`.

## Compatibility

Signal Peak 2.1.0 retains the existing Area, Station, Custom, Station Data, Advanced, and Resources workflows. Existing persistent location and RF override files under `ViewshedData` continue to be used.
