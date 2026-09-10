# Signal Peak 2.1.0

**Signal Peak** is a portable APRS/VHF terrain-propagation analysis application with a map-first Windows desktop workflow. Area, Station, and Custom modes use the same terrain-profile, Longley-Rice/ITM, path-loss, and link-margin foundation.

Version 2.1.0 adds a redesigned output architecture with independently selectable station pins and coverage layers, unified composite/per-station heat-map styling, positive coverage, coverage gaps, redundancy mapping, configurable colors, and more reliable Corrections behavior. It also makes the Resources model the sole user-facing controller for DEM sizing and worker planning.

Version 2.0 introduced resource-aware terrain-detail planning, automatic worker limits based on available RAM/CPU, resolution-aware DEM caching, and stricter Area scoping. Version 1.2 added persistent per-station RF overrides, the Station Data editor, and Metric/Imperial input/display selection.

## License

Signal Peak is free and open-source software licensed under the **GNU General Public License version 2 only (GPL-2.0-only)**. See [LICENSE](LICENSE).

## Quick links

- [Quick Start](docs/QUICK_START.md)
- [User Guide](docs/USER_GUIDE.md)
- [2.1.0 Release Notes](docs/RELEASE_NOTES_2.1.0.md)
- [2.0.1 Release Notes](docs/RELEASE_NOTES_2.0.1.md)
- [Propagation Model](docs/PROPAGATION_MODEL.md)
- [Station Data](docs/STATION_DATA.md)
- [Location Corrections](docs/LOCATION_CORRECTIONS.md)
- [Outputs](docs/OUTPUTS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [DEM Bulk Downloader](docs/DEM_BULK_DOWNLOADER.md)
- [Dependencies / Licenses](docs/LICENSES_AND_DEPENDENCIES.md)
- [Special Considerations](docs/SPECIAL_CONSIDERATIONS.md)
- [Roadmap](docs/ROADMAP.md)

The packaged Windows application includes the current documentation under **Help / About**.

## Current UI modes

### Area

Choose an analysis region, acquire the station list, inspect/correct questionable locations, then run propagation on the reviewed station set. Acquisition may look beyond the requested Area to find relevant infrastructure, but propagation is clipped back to station centers inside the selected Area radius.

### Station

Select one known digipeater or iGate and run the same propagation engine for that individual site. After an Area search, the Station tab shows that search's station set; **Load full cached catalog** deliberately restores the cumulative cache.

### Custom

Click a proposed site and supply antenna height, transmitter power, gain, frequency, and maximum calculation range.

### Corrections

Reviewed coordinate corrections are stored separately from seed/cache/APRS data in `ViewshedData/station_location_overrides.json` and reapplied by callsign. The UI distinguishes saved corrections, pending review candidates, stations needing review, and uncorrected stations.

### Station Data

The Station Data tab provides a spreadsheet-style editor for station-specific height, TX power, gain, frequency, and path-loss assumptions. Saved values are keyed by callsign and persist independently from refreshed station position data.

### Advanced

Advanced contains RF/link-budget assumptions, antenna/observer heights, frequency, ITM environmental parameters, and display units. TX power can be entered in Watts or dBm. Legacy worker DEM sizing is no longer exposed here.

### Resources

The Resources tab owns terrain/detail and compute planning. Terrain detail presets are:

- **Auto** — safe balanced planning from the actual run and current system resources
- **Fast** — favors speed and lower memory use
- **Standard** — balances speed and terrain detail
- **High** — preserves more terrain detail at higher compute cost
- **Max** — prioritizes stability first and terrain resolution second; may reduce processing to one worker and can be very slow

An optional **Memory limit (GB)** caps the RAM Signal Peak plans around. `0` means automatic. The planner chooses DEM resolution, analysis size, and safe worker count immediately before each run.

### Output

The Output tab controls presentation independently from propagation math. Current layers include:

- Station pins / metadata
- Composite heat map
- Positive coverage
- Coverage gaps
- Coverage redundancy
- Per-station heat maps

Output presets are **Standard**, **Coverage Analysis**, **Station Analysis**, **Everything**, and **Custom**. Composite and per-station heat maps share the same configurable stepped link-margin palette. Positive, gap, and redundancy colors are also configurable.

## Terrain cache behavior

DEM cache entries are resolution-aware. Cached terrain is reused only when it satisfies the requested detail. A higher-detail run can therefore trigger higher-resolution terrain preparation instead of silently reusing a coarser cache product.

For offline disaster recovery or long-term reproducibility, `dem_bulk_downloader.py` can build a separate frozen USGS 3DEP archive. See [DEM Bulk Downloader](docs/DEM_BULK_DOWNLOADER.md).

## Reference profile

Current Area/Station fallback assumptions include:

- Frequency: 144.390 MHz
- TX power: 50 W (approximately 47 dBm)
- TX antenna gain: 0 dBd
- RX sensitivity: -119 dBm
- RX antenna gain: +2 dBd
- Operational path-loss cap: **138 dB**
- Digipeater antenna height: 20 m AGL
- iGate antenna height: 3 m AGL
- Observer/receiver height: 2 m AGL

These are fallback modeling assumptions, not measured installation data. Known station-specific RF values can override them.

## Outputs

Jobs are written under:

```text
ViewshedData/jobs/<timestamp>/output/
```

After completion, the UI provides **Open Output Folder**, **Open KMZ**, and **Open GeoTIFF**.

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

The resulting executable is `dist/SignalPeak.exe`. A packaged smoke test is available with:

```bash
SignalPeak.exe --self-test
```

GitHub Actions builds and smoke-tests the Windows executable and uploads the `Signal-Peak-Windows-2.1.0` artifact for the 2.1 development branch.

## Modeling caution

Signal Peak generates predicted VHF coverage. APRS positions and infrastructure inventories can be incomplete; actual ERP, antenna pattern, feedline loss, clutter, foliage, local noise, weather, and receiver installation are not fully known or modeled. Results are planning/analysis predictions, not communications guarantees.
