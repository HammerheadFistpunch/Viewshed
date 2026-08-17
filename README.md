# Signal Peak 1.0.0

**Signal Peak** is a portable APRS/VHF terrain-propagation analysis application with a map-first Windows desktop workflow. Area, Station, and Custom modes use the same terrain-profile, Longley-Rice/ITM, path-loss, and link-margin foundation.

The 1.0.0 CONUS branch adds automatic local UTM-zone selection, map-based station review/corrections, repeatable jobs in one application session, a longer-duration APRS seed builder, and the current conservative reference profile.

## Quick links

- [Quick Start](docs/QUICK_START.md)
- [User Guide](docs/USER_GUIDE.md)
- [CONUS support](docs/CONUS.md)
- [Propagation Model](docs/PROPAGATION_MODEL.md)
- [Station Data](docs/STATION_DATA.md)
- [Location Corrections](docs/LOCATION_CORRECTIONS.md)
- [Outputs](docs/OUTPUTS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Dependencies / Licenses](docs/LICENSES_AND_DEPENDENCIES.md)
- [1.0 Legal / Security Audit](docs/RELEASE_AUDIT_1.0.0.md)
- [Special Considerations](docs/SPECIAL_CONSIDERATIONS.md)
- [Roadmap](docs/ROADMAP.md)

The packaged Windows application includes these documents under **Help / About**.

## Current UI modes

### Area

Choose an analysis region, acquire the station list, inspect/correct questionable locations, then run propagation on the reviewed station set. Clicking a new location after completion starts a fresh workflow without requiring an application restart.

### Station

Select one known digipeater or iGate and run the same propagation engine for that individual site.

### Custom

Click a proposed site and supply antenna height, transmitter power, gain, frequency, and maximum calculation range.

### Corrections

Review reported/model coordinates, topographic context, confidence, freshness, and OpenStreetMap communications-site corroboration. Reviewed corrections change the modeled coordinate while preserving the reported coordinate and provenance.

### Advanced

Area and Station assumptions can be changed and persisted, including link-budget assumptions, antenna/observer heights, frequency, radial count, display bounds, DEM resolution, and ITM environmental parameters.

## Reference profile

Current defaults include:

- Frequency: 144.390 MHz
- TX power: 47 dBm (50 W)
- TX antenna gain: 0 dBd
- RX sensitivity: -119 dBm
- RX antenna gain: +2 dBd
- Operational path-loss cap: **138 dB**
- Digipeater antenna height: 20 m AGL
- iGate antenna height: 3 m AGL
- Observer/receiver height: 2 m AGL
- Radials: **1080 per station**
- Reduced lateral radial gap fill

These are explicit modeling assumptions, not measured installation data for each APRS site. Custom mode derives a site-specific budget and applies a 20 dB operational reserve.

## CONUS behavior

Signal Peak chooses the projected UTM CRS from the geographic center of each job. For example, Salt Lake City uses Zone 12N, Denver uses 13N, Los Angeles uses 11N, and New York City uses 18N. Terrain acquisition uses USGS 3DEP data derived from the requested geography rather than a fixed Utah extent.

The legacy propagation module retains an old Utah-oriented filename internally to avoid a risky mechanical rewrite, but the active CONUS projection layer is no longer fixed to Utah.

## Station acquisition

Normal Area discovery can use receive-only APRS-IS sampling, then merge cache and optional seed/fallback records. A built-in **Build Seed…** tool performs longer APRS collection and saves reusable JSON under `ViewshedData/seeds/`.

An aprs.fi API key is optional. Signal Peak 1.0.0 treats that key as **session-only** and removes it from persisted application settings.

## Outputs

Jobs are written under:

```text
ViewshedData/jobs/<timestamp>/output/
```

After completion, the UI provides **Open Output Folder**, **Open KMZ**, and **Open GeoTIFF**. Previous output buttons remain available until the next run starts.

## Run from source

Python 3.12 is recommended.

```bash
python -m pip install -r requirements.txt
python viewshed_app.py
```

## Build the Windows executable

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
pyinstaller --clean --noconfirm viewshed.spec
```

The resulting executable is:

```text
dist/SignalPeak.exe
```

A packaged smoke test is available:

```bash
SignalPeak.exe --self-test
```

GitHub Actions builds and smoke-tests the Windows executable on pushes to `CONUS` and uploads the `Signal-Peak-Windows-1.0.0` artifact.

## Legal release status

The codebase has been reviewed for release concerns, but **1.0.0 should not yet be treated as legally cleared for public binary redistribution**. The most important unresolved item is `aprslib`, which is GPLv2-licensed and is currently bundled as a runtime dependency. The repository also does not yet contain a top-level project license selected by the copyright owner. See [the 1.0 legal/security audit](docs/RELEASE_AUDIT_1.0.0.md) before publishing a public download.

## Modeling caution

Signal Peak generates predicted VHF coverage. APRS positions and infrastructure inventories can be incomplete; actual ERP, antenna pattern, feedline loss, clutter, foliage, local noise, weather, and receiver installation are not fully known or modeled. Results are planning/analysis predictions, not communications guarantees.
