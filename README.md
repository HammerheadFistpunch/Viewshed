# Viewshed

Utah APRS coverage modeling tools for collecting station data and generating terrain-aware VHF coverage overlays for Google Earth.

## What is here

- `aprs_is_scrape_utah.py` — listens to APRS-IS, collects Utah digipeater/iGate data, and writes `utah_stations_scraped.json`.
- `aprs_viewshed_utah_parallel.py` — builds DEM inputs, computes per-station terrain/ITM coverage, merges the results, and writes `aprs_coverage_utah.kmz`.
- `aprs_validator.py` — validates APRS station data.
- `DEM grab raw.py` — standalone DEM download/merge utility.
- `run_viewshed.bat` — Windows launcher for the viewshed generator.
- `utah_seed_stations.csv` — seed/override station list used by the scraper.
- `APRS dataset/` — retained sample/reference KMZ data.

## Quick start

Requires Python 3 and the packages in `requirements.txt`.

```bash
python -m pip install -r requirements.txt
```

### Generate or refresh station data

```bash
python aprs_is_scrape_utah.py
```

The scraper writes `utah_stations_scraped.json`. It is designed as a long-running APRS-IS listener; review its configuration before starting a collection run.

### Generate the coverage model

```bash
python aprs_viewshed_utah_parallel.py
```

On Windows, `run_viewshed.bat` is also provided for a double-click-friendly launch.

The generator downloads/caches required elevation tiles, computes coverage for the configured stations, and creates:

```text
aprs_coverage_utah.kmz
```

Open that file in Google Earth Pro. Intermediate DEMs, rasters, station overlays, and caches are written under `dem_cache/` and `aprs_viewshed_work/`; those generated directories are intentionally ignored by Git.

## Configuration

The main coverage settings are in the `CONFIG` dictionary near the top of `aprs_viewshed_utah_parallel.py`. Current defaults include:

- APRS frequency: `144.390 MHz`
- maximum modeled radius: `180 km`
- 720 radials per station
- DEM resolution setting: `30m`
- parallel CPU workers: automatic (`os.cpu_count()`)

The script also contains link-budget, antenna-height, ITM, rendering, cache, and coordinate-override settings. Review those values before treating an output as an engineering prediction.

## Generated files

The following are runtime artifacts and should normally stay out of version control:

- `.vs/`
- `*.log` and `run_log.txt`
- `dem_cache/`
- `aprs_viewshed_work/`
- `aprs_coverage_utah.kmz`

Reference/input datasets that are already tracked are not excluded globally; for example, KMZ files under `APRS dataset/` remain versioned.

## Notes

This repository is currently a working research/prototyping project rather than a packaged Python library. The cleanup intentionally keeps the existing analysis algorithms and data flow intact while separating source files from machine-specific and generated artifacts.
