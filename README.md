# Viewshed

Viewshed is a portable APRS RF coverage generator built around a shared terrain/propagation foundation. The desktop application now uses a map-first workflow for Area, Station, Custom/future-station, and station-location correction tasks.

## Current application direction

The application is being developed around these principles:

- one common DEM -> terrain profile -> ITM/Longley-Rice -> path loss -> link-margin pipeline
- Area, Station, and Custom modes differ by explicit site/radio inputs rather than hidden changes to propagation math
- APRS station acquisition is live-first with optional cache, aprs.fi resolution, and seed/fallback data
- station-location confidence and reviewed corrections are kept outside the RF math
- large DEM requests are memory-bounded rather than requiring a full native mosaic in RAM
- Windows packaging remains a single portable executable with `ViewshedData` used for persistent cache, jobs, seeds, settings, and user corrections

## Current UI modes

### Area

Choose an area on the map, acquire the station list first, inspect/correct questionable station locations, then run propagation on the reviewed/frozen station set.

### Station

Select one known digi/iGate and run the same propagation engine for that individual site.

### Custom

Click a proposed site on the map and supply explicit radio parameters such as antenna height, power, gain, frequency, and analysis radius.

### Corrections

Compare the reported and model coordinates for a station, visually propose a replacement location, save it as a review candidate, or approve it as a reviewed correction. Reviewed corrections change the model coordinate while preserving the originally reported position and provenance.

## Station acquisition and seed data

Normal Area discovery does not require a seed file, APRS callsign, or aprs.fi API key. Viewshed can connect receive-only to APRS-IS and use live infrastructure/position observations. Optional cache, aprs.fi resolution, and local seed files improve continuity and completeness.

A built-in **Build Seed...** tool can perform a longer APRS collection session and save a reusable JSON seed under `ViewshedData/seeds/`.

See [station acquisition](docs/station-acquisition.md) for more detail.

## Outputs

Job outputs are written under:

```text
ViewshedData/jobs/<timestamp>/output/
```

Current primary products include Google Earth KMZ and GeoTIFF coverage data. The current roadmap calls for simplifying the default visualization from a continuous heatmap toward categorical coverage and infrastructure-overlap products while retaining raw link-margin data for technical use.

## Run from source

Python 3.12 is recommended.

```bash
python -m pip install -r requirements.txt
python viewshed_app.py
```

Or double-click:

```text
run_viewshed.bat
```

The legacy backend remains in `aprs_viewshed_utah_parallel.py` for regression comparison while propagation responsibilities continue to be migrated into focused modules.

## Build the Windows executable

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm viewshed.spec
```

The resulting executable is:

```text
dist/Viewshed.exe
```

A lightweight packaged smoke test is available:

```bash
Viewshed.exe --self-test
```

GitHub Actions builds and smoke-tests the Windows executable on pushes to `main` and uploads the `Viewshed-Windows` artifact.

## Station JSON format

Viewshed accepts a JSON list or an object containing a `stations`, `results`, or `data` list. Each usable record needs at least:

```json
{
  "callsign": "EXAMPLE",
  "type": "digi",
  "lat": 40.7608,
  "lon": -111.8910
}
```

`type` is currently expected to be `digi` or `igate`.

## Architecture direction

```text
Map-first GUI / CLI
       |
Region + job controller
       |
Station source -> confidence/corrections -> frozen station set
       |
Terrain source -> DEM/cache -> memory-bounded analysis DEM
       |
Propagation engine
       |
KMZ / GeoTIFF exporters
```

`viewshed_core.py` owns region/job/station filtering, portable data locations, correction registry integration, and worker-controller responsibilities. The larger original propagation script remains the backend while its working ITM/raster implementation is migrated incrementally rather than rewritten all at once.

## Roadmap

The active roadmap is maintained in [docs/ROADMAP.md](docs/ROADMAP.md).

Current priorities are:

1. Cancel a running propagation job.
2. Improve completion/output actions in the UI.
3. Replace or simplify the current heatmap with categorical coverage and overlap products.
4. Add a topographic basemap for station corrections.
5. Build the complete documentation set.
6. Add an About / Help interface with documentation, dependency/license information, and special considerations.
7. Reuse DEM data for elevation/hillshade assistance during corrections.
8. Add terrain-based location plausibility warnings without automatically relocating stations.

## Scope and modeling caution

Viewshed generates predicted VHF coverage. APRS positions may be incomplete or wrong, station installation parameters are usually unknown, and Area/Station modes therefore use explicit reference assumptions rather than claiming exact station ERP/antenna data. Coverage should be treated as a planning/analysis prediction, not a communications guarantee.
