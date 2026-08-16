# Viewshed

Viewshed is a portable APRS/VHF terrain-propagation analysis application with a map-first Windows desktop workflow. Area, Station, and Custom modes all feed the same DEM -> terrain profile -> Longley-Rice/ITM -> path-loss -> link-margin foundation.

## Quick links

- [Quick Start](docs/QUICK_START.md)
- [User Guide](docs/USER_GUIDE.md)
- [Propagation Model](docs/PROPAGATION_MODEL.md)
- [Station Data](docs/STATION_DATA.md)
- [Location Corrections](docs/LOCATION_CORRECTIONS.md)
- [Outputs](docs/OUTPUTS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Dependencies / Licenses](docs/LICENSES_AND_DEPENDENCIES.md)
- [Special Considerations](docs/SPECIAL_CONSIDERATIONS.md)
- [Roadmap](docs/ROADMAP.md)

The packaged Windows application includes these documents offline under **Help / About**.

## Current UI modes

### Area

Choose an analysis region, acquire the station list first, inspect/correct questionable locations, then run propagation on the reviewed/frozen station set.

The station range field is a **maximum calculation range**, not a physical RF boundary. If modeled margin is still positive at that range, coverage can end in a clean circular arc.

### Station

Select one known digi/iGate and run the same propagation engine for that individual site.

### Custom

Click a proposed site and supply explicit antenna height, transmitter power, gain, frequency, and analysis range. Custom mode uses its own site-specific radio settings.

### Corrections

Review reported/model coordinates, topographic context, location confidence, freshness, and OpenStreetMap communications-site corroboration. OSM can improve confidence in an existing coordinate, but it never silently relocates a station. Reviewed corrections change the model coordinate while preserving the reported coordinate and provenance.

### Advanced

Area and Station assumptions can be changed and persisted, including:

- operational path-loss cap
- TX/RX power/gain/sensitivity assumptions
- antenna/observer heights
- frequency
- radial count
- margin display bounds
- worker DEM resolution
- ITM climate/refractivity/ground/polarization parameters

The current default Area/Station operational path-loss cap is **148 dB**. Use **Reset to Viewshed defaults** to restore the reference profile.

### Help / About

Provides offline access to the README, Quick Start, User Guide, model documentation, station/correction/output guides, troubleshooting, dependencies/licenses, special considerations, roadmap, and the active `ViewshedData` folder.

## Station acquisition

Normal Area discovery does not require a seed file, APRS callsign, or aprs.fi API key. Viewshed can use receive-only APRS-IS sampling, then merge cache and optional seed/fallback records.

A built-in **Build Seed…** tool performs a longer APRS collection and saves reusable JSON under `ViewshedData/seeds/`.

Viewshed also cross-references nearby OpenStreetMap communications infrastructure through Overpass when available. Strong geographic agreement is used as independent corroboration of an existing station coordinate. Missing timestamps are treated as freshness information rather than coordinate inaccuracy.

## Reference Area/Station profile

Current defaults include:

- Frequency: 144.390 MHz
- TX power: 47 dBm (50 W)
- TX antenna gain: 0 dBd
- RX sensitivity: -119 dBm
- RX antenna gain: +2 dBd
- Operational path-loss cap: 148 dB
- Digipeater antenna height: 20 m AGL
- iGate antenna height: 3 m AGL
- Observer/receiver height: 2 m AGL
- Radials: 720 per station

These are explicit modeling assumptions, not measured installation data for each APRS site.

## Outputs

Jobs are written under:

```text
ViewshedData/jobs/<timestamp>/output/
```

After completion, the UI provides **Open Output Folder**, **Open KMZ**, and **Open GeoTIFF**. A running job can be stopped with **Cancel Run**; shared DEM cache files are preserved.

The combined Area product is primarily a **coverage overlap** product (number of modeled infrastructure sites meeting the operational threshold), while per-station rasters retain modeled link-margin information.

## Run from source

Python 3.12 is recommended.

```bash
python -m pip install -r requirements.txt
python viewshed_app.py
```

Or use `run_viewshed.bat` on Windows.

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

A packaged smoke test is available:

```bash
Viewshed.exe --self-test
```

GitHub Actions builds and smoke-tests the Windows executable on pushes to `main` and uploads the `Viewshed-Windows` artifact.

## Station JSON format

Viewshed accepts a JSON list or an object containing a `stations`, `results`, or `data` list. A usable record needs at least:

```json
{
  "callsign": "EXAMPLE",
  "type": "digi",
  "lat": 40.7608,
  "lon": -111.8910
}
```

`type` is currently expected to be `digi` or `igate`.

## Architecture

```text
Map-first GUI
       |
Area / Station / Custom / Corrections / Advanced
       |
Station source -> confidence + OSM corroboration + reviewed corrections
       |
Frozen station set
       |
USGS terrain -> DEM cache -> memory-bounded analysis DEM
       |
Longley-Rice/ITM + link-margin engine
       |
Coverage overlap / KMZ / GeoTIFF
```

## Scope and modeling caution

Viewshed generates predicted VHF coverage. APRS positions and infrastructure inventories can be incomplete; actual station ERP, antenna pattern, feedline loss, clutter, foliage, local noise, weather, and receiver installation are not fully known or modeled. Coverage should be treated as a planning/analysis prediction, not a communications guarantee.

The legacy propagation backend still contains Utah-oriented validation/CRS assumptions. Map display and station acquisition are more general than the propagation engine; full nationwide/generalized propagation remains future work.
