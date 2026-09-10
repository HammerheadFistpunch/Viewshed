# USGS 3DEP bulk DEM archive

`dem_bulk_downloader.py` is a standalone utility for building an offline archive of the current USGS 3DEP DEM tiles used by Signal Peak. It is intentionally separate from the application's runtime DEM acquisition code so the archive can be created once and wired into the application later.

USGS distributes the 1 arc-second (~30 m) and 1/3 arc-second (~10 m) seamless DEM products as 1-degree GeoTIFF tiles. The TNMAccess API is used to discover the actual current download URL instead of constructing legacy S3 paths. USGS documents TNMAccess as the API for downloadable National Map products, and both DEM products are publicly available. citeturn0search1turn0search2turn0search5

## Install

The downloader uses `requests`, which is already a Signal Peak dependency:

```text
python -m pip install -r requirements.txt
```

## Recommended backup

For a full CONUS snapshot, start with the default bounding box:

```text
-125,24,-66,50
```

This is a rectangular CONUS bounding box, so it intentionally includes some fringe ocean, Canada, and Mexico 1-degree cells. That is simpler and safer than trying to maintain a separate state-boundary mask. The resulting extra tiles can be deleted later if desired.

### 1 arc-second only

```bash
python dem_bulk_downloader.py --resolution 1 --output DEM_Archive
```

### 1/3 arc-second only

```bash
python dem_bulk_downloader.py --resolution 1/3 --output DEM_Archive
```

### Both resolutions

```bash
python dem_bulk_downloader.py --resolution both --output DEM_Archive
```

For the first run, I recommend keeping the default `--workers 6`. The downloader is intentionally conservative because this is a large public-data transfer rather than a latency-sensitive application operation.

## Test the inventory first

Before committing to a large download, query TNMAccess without downloading files:

```bash
python dem_bulk_downloader.py --resolution 1 --discover-only --output DEM_Archive
```

Then inspect `DEM_Archive/manifest.json`. Repeat with `--resolution 1/3` if desired.

## Resume behavior

The downloader is safe to rerun:

- Existing non-empty files are skipped.
- Failed downloads are removed and retried.
- Downloads use temporary `.part` files and are renamed only after completion.
- `manifest.json` records the TNM URL, product metadata, relative file path, size, and SHA-256 for downloaded files.
- A rerun discovers only missing/unrecorded tiles unless `--refresh` is specified.

To refresh TNM product discovery while retaining existing files:

```bash
python dem_bulk_downloader.py --resolution 1 --refresh --output DEM_Archive
```

## Archive layout

A completed archive looks approximately like:

```text
DEM_Archive/
├── 1arcsec/
│   ├── USGS_1_n35w112.tif
│   ├── USGS_1_n35w113.tif
│   └── ...
├── 1_3arcsec/
│   ├── USGS_13_n35w112.tif
│   ├── USGS_13_n35w113.tif
│   └── ...
└── manifest.json
```

USGS notes that current and historical DEM products are pre-staged as 1-degree GeoTIFFs, and updated current tiles can replace earlier versions. For a backup, keep this archive as a frozen snapshot rather than continually overwriting it. citeturn0search12turn0search6

## Important: current snapshot vs. historical library

The downloader intentionally targets the **current** product set. It does not attempt to mirror every historical USGS revision. That is the useful backup for Signal Peak: one known-good, internally consistent terrain snapshot that can be kept offline.

If a specific tile is later replaced by USGS, the archive remains unchanged unless you explicitly rerun with `--refresh` and replace the stored file.

## Storage planning

The 1/3 arc-second dataset is substantially larger than 1 arc-second. USGS describes 1 arc-second as approximately 30 m ground spacing and 1/3 arc-second as approximately 10 m. citeturn0search5

For that reason, a practical approach is:

1. Archive **1 arc-second** first as the primary emergency backup.
2. Add **1/3 arc-second** if you have sufficient disk space and want a higher-detail offline source.
3. Keep the two resolutions in separate directories so the eventual Signal Peak integration can choose between them without ambiguity.
