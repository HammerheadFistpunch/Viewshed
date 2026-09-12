# USGS 3DEP bulk DEM archive

`dem_bulk_downloader.py` is a standalone utility for building an offline archive of the USGS 3DEP DEM tiles used by Signal Peak. It uses TNMAccess to discover actual products and supports both 1 arc-second and 1/3 arc-second DEMs.

Signal Peak 2.2.1 uses the same improved TNMAccess product-selection logic for runtime terrain preparation and the bulk archive workflow.

## Easiest Windows workflow

You do not need to use IDLE or enter command-line arguments manually.

1. Edit `dem_bulk_config.json` with Notepad.
2. Set the resolution, geographic bounding box, worker count, and **output directory**.
3. Double-click `run_dem_bulk.bat`.
4. The downloader opens a normal console window and resumes an existing archive automatically.

Example configuration:

```json
{
  "resolution": "1",
  "output": "D:/DEM_Archive",
  "bbox": [-125.0, 24.0, -66.0, 50.0],
  "workers": 6,
  "api_timeout": 45,
  "download_timeout": 180,
  "retries": 3,
  "discover_only": false,
  "refresh": false
}
```

### Configuration fields

- `resolution`: `"1"`, `"1/3"`, or `"both"`
- `output`: destination directory for the archive; Windows paths may use `D:/DEM_Archive` or `D:\\DEM_Archive`
- `bbox`: `[west, south, east, north]` in decimal degrees
- `workers`: simultaneous discovery/download workers; `6` is a conservative default
- `api_timeout`: TNMAccess request timeout in seconds
- `download_timeout`: individual DEM download timeout in seconds
- `retries`: number of attempts for a failed download
- `discover_only`: `true` to query the inventory without downloading files
- `refresh`: `true` to rediscover tiles even when the manifest already has them

The launcher translates these JSON settings into the downloader's normal command-line arguments, so the downloader itself remains usable from a terminal as before.

## Command-line workflow

If you prefer a terminal, the downloader still supports direct arguments.

### 1 arc-second only

```text
python dem_bulk_downloader.py --resolution 1 --output DEM_Archive
```

### 1/3 arc-second only

```text
python dem_bulk_downloader.py --resolution 1/3 --output DEM_Archive
```

### Both resolutions

```text
python dem_bulk_downloader.py --resolution both --output DEM_Archive
```

### Test the inventory first

```text
python dem_bulk_downloader.py --resolution 1 --discover-only --output DEM_Archive
```

## Geographic extent

The default CONUS bounding box is:

```text
-125,24,-66,50
```

This rectangular extent intentionally includes some fringe ocean, Canada, and Mexico 1-degree cells. A smaller regional bbox can be entered in `dem_bulk_config.json` when a full CONUS archive is not wanted.

## Current-product selection

The downloader now follows Signal Peak 2.2.1's TNMAccess selection logic. Exact bbox-scoped NED queries are used for spatial/product selection rather than requiring the tile identifier to appear in the product URL. If TNMAccess exposes a historical URL, the downloader derives and tries the corresponding current object first, then retains the historical product as a fallback.

This distinction matters because TNMAccess is a product catalog rather than a guaranteed tile-name index. Broad free-text discovery remains filtered by tile identifier and elevation/NED/3DEP terms to avoid unrelated products.

## Runtime no-data behavior

The runtime Signal Peak DEM adapter can encounter legitimate tiles with no terrestrial 3DEP product, particularly near ocean boundaries in large CONUS analyses. When TNMAccess successfully confirms that no DEM product exists, Signal Peak 2.2.1 can represent that tile as validated nodata terrain rather than failing the entire propagation run.

This behavior applies to runtime terrain preparation; the bulk archive remains an inventory/download tool and does not manufacture terrain products for tiles that USGS does not provide.

## Resume behavior

The downloader is safe to rerun:

- Existing non-empty files are skipped.
- Failed downloads are removed and retried.
- Downloads use temporary `.part` files and are renamed only after completion.
- `manifest.json` records the TNM URL, product metadata, relative file path, size, and SHA-256 for downloaded files.
- A rerun processes only missing/unrecorded tiles unless `refresh` is enabled.

The archive is intended to be a frozen offline snapshot. If USGS later replaces a current tile, use `refresh` deliberately rather than overwriting the archive accidentally.
