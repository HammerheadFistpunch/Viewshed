# Signal Peak 2.2.1 Release Notes

Signal Peak 2.2.1 is a focused reliability release following 2.2.0. It concentrates on **USGS 3DEP / TNMAccess terrain acquisition, large-area reliability, edge-of-coverage handling, and release/version consistency** while preserving the established propagation model and output architecture.

## DEM acquisition reliability

Signal Peak 2.2.1 improves the way runtime terrain products are selected from USGS 3DEP / TNMAccess.

- Exact bbox-scoped NED requests are treated as authoritative for the requested geographic extent.
- A returned product URL no longer has to contain the expected one-degree tile identifier for an exact spatial request to be accepted.
- Broader discovery searches remain tile-filtered so unrelated DEM products are not accidentally selected.
- TNMAccess response differences are handled more defensively while preserving the requested terrain extent.
- Historical product URLs can be mapped toward current USGS objects before falling back to the historical product when necessary.

These changes are especially important for **large CONUS and edge-of-coverage analyses**, where a single missing or incorrectly rejected terrain product could previously terminate an otherwise valid job.

## Ocean and no-data terrain handling

Large geographic searches can legitimately include one-degree cells containing ocean or other areas without terrestrial 3DEP coverage.

When TNMAccess successfully confirms that no DEM product exists for a requested tile, Signal Peak 2.2.1 now creates a validated nodata terrain tile rather than treating the absence of terrestrial elevation data as a fatal download error.

This allows the analysis to continue across legitimate no-data areas while preserving the distinction between **missing terrain data** and an actual terrain-download failure.

## Bulk DEM archive workflow

The packaged bulk DEM workflow introduced in 2.2.0 now uses the same improved terrain-product selection logic as runtime acquisition.

The archive workflow supports:

- 1 arc-second, 1/3 arc-second, or both resolutions;
- configurable geographic bounding boxes;
- configurable output directories;
- parallel discovery/download workers;
- request and download timeouts;
- retries;
- resume-safe downloads;
- discovery-only mode; and
- deliberate refresh mode.

The archive remains separate from the normal per-run DEM cache and is intended for long-lived offline terrain resources and reproducible workflows.

## Large-area / CONUS behavior

Signal Peak continues to distinguish **station acquisition scope** from **propagation scope**.

Area-mode acquisition may intentionally search beyond the requested Area so stations near the edge of the analysis can be discovered. The final propagation set remains clipped to station centers inside the selected Area radius.

The propagation calculation range remains an independent setting and continues to control how far the model is calculated around each selected station. A clean circular edge in the resulting map therefore remains a possible indication of the configured maximum calculation range rather than a software fault.

The wider acquisition margin is intentional and remains part of the analysis workflow.

## Version and packaging consistency

Version 2.2.1 establishes `VERSION` as the canonical packaged release number.

The release entry point applies that version to the runtime core and packaged UI components, including Help/About and resource-related release identity. The Windows GitHub Actions workflow reads the same value for the downloadable artifact name.

The current Windows artifact name is:

```text
Signal-Peak-Windows-2.2.1
```

## Documentation

Current operator documentation is aligned to Signal Peak 2.2.1, including:

- README / project overview
- Quick Start
- User Guide
- Outputs documentation
- DEM bulk downloader documentation
- Help/About current release selection

Historical release notes remain versioned separately so previous releases continue to describe their own behavior accurately.

## What has not changed

Signal Peak 2.2.1 does **not intentionally change the established RF propagation interpretation**.

The existing foundations remain in place, including:

- terrain-profile analysis;
- Longley-Rice / ITM propagation;
- link-margin calculations;
- per-station RF overrides;
- station-location correction workflow;
- APRS station acquisition;
- resource-aware terrain-detail planning;
- resolution-aware DEM caching;
- network best-margin heatmaps;
- positive coverage, coverage-gap, and redundancy products; and
- independently selectable output layers.

The intentional Area acquisition margin and propagation-range behavior are unchanged.

## Compatibility

Signal Peak 2.2.1 retains the existing Area, Station, Custom, Station Data, Corrections, Advanced, Resources, and Output workflows. Existing persistent location corrections, station RF overrides, cached terrain, and other `ViewshedData` files remain compatible.

## Summary

Signal Peak 2.2.1 is primarily a reliability and maintenance release. The major user-facing improvement is more dependable terrain acquisition from USGS 3DEP / TNMAccess, particularly for large geographic analyses where product-selection edge cases or legitimate ocean/no-data tiles could otherwise stop a run. The release also carries the improved bulk DEM workflow forward and makes the packaged release identity consistently **2.2.1**.
