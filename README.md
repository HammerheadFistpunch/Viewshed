# Viewshed

Viewshed is becoming a portable, one-click APRS RF coverage generator. The intended user workflow is simple: choose an area, click **Generate Viewshed**, and receive Google Earth KMZ and GeoTIFF coverage outputs without manually running the scraper, DEM tools, or propagation scripts.

## Current application milestone (v0.1)

The repository now contains the first application shell around the existing propagation engine:

- Tkinter GUI (`viewshed_app.py`)
- center-point + radius search area
- configurable maximum propagation radius
- digipeater / iGate filtering
- propagation-aware station selection (search area plus RF buffer)
- automatic DEM download and caching through the existing engine
- parallel ITM Longley-Rice viewshed calculation
- KMZ and GeoTIFF output
- deterministic per-job output folders
- PyInstaller configuration for a single Windows executable
- GitHub Actions build that produces a `Viewshed.exe` artifact on every push to `main`

The existing Utah station dataset is bundled as the default station source for v0.1. The GUI can also browse to another compatible JSON dataset. Automatic general-purpose station discovery is the next major data-source milestone.

## User workflow

1. Run `Viewshed.exe` (or `run_viewshed.bat` when developing from source).
2. Enter a center latitude, longitude, and output radius.
3. Choose the maximum RF propagation radius and station types.
4. Click **Generate Viewshed**.
5. The application selects stations that can affect the requested area, downloads/reuses elevation data, computes viewsheds, and writes the results.

Outputs are written under a portable `ViewshedData/jobs/<timestamp>/output/` directory next to the executable when that location is writable. If it is not writable, the application falls back to `~/ViewshedData`.

Primary outputs:

- `viewshed.kmz` — Google Earth visualization
- `coverage_count.tif` — combined coverage-count GeoTIFF

Intermediate DEM and station viewshed files live under the job's `output/work/` directory. Reusable DEM downloads are kept in `ViewshedData/cache/dem/`.

## Area semantics

The **output radius** describes the area the user cares about. Station selection uses a larger acquisition radius:

```text
station search radius = output radius + maximum propagation radius
```

This prevents a transmitter just outside the selected area from being excluded even though its RF footprint reaches into the selected area.

At the v0.1 milestone, the legacy backend still creates the complete coverage footprint for the selected stations rather than cropping every product to the user's output circle. Exact output clipping is planned as the generalized engine is migrated out of the Utah prototype.

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

The old direct backend remains in `aprs_viewshed_utah_parallel.py` for development and regression comparison, but it is no longer the intended user entry point.

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

GitHub Actions performs the same build and smoke test on Windows and uploads the executable as the `Viewshed-Windows` artifact.

## Station JSON format

The application currently accepts the same station records used by the prototype. A source can be a JSON list or an object containing a `stations`, `results`, or `data` list. Each usable record needs at least:

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

The application is being migrated toward these boundaries:

```text
GUI / CLI
   |
Region + job controller
   |
Station source  -> station cache/filter
   |
Terrain source  -> DEM cache
   |
Propagation engine
   |
KMZ / GeoTIFF exporters
```

`viewshed_core.py` now owns the region, job, station-filtering, portable-data, and worker-controller responsibilities. The large Utah prototype remains the propagation backend temporarily so the working ITM/raster implementation can be migrated incrementally rather than rewritten all at once.

## Near-term roadmap

1. Generalize the propagation backend beyond Utah-specific validation and UTM zone 12.
2. Crop outputs to the requested region.
3. Replace the bundled Utah-only station source with automatic regional station acquisition/cache.
4. Add bounding-box area selection.
5. Add a visual map area selector after the core geographic pipeline is stable.
6. Move DEM, propagation, and export code into focused modules.
7. Add automated unit/integration tests around region selection, DEM acquisition, and output generation.

## Scope

The project currently focuses only on **generating predicted viewshed / RF coverage data**. Historical KML/KMZ track comparison is intentionally out of scope for this application phase.
