# Signal Peak 1.2.0

**Signal Peak** is a portable APRS/VHF terrain-propagation analysis application with a map-first Windows desktop workflow. Area, Station, and Custom modes use the same terrain-profile, Longley-Rice/ITM, path-loss, and link-margin foundation.

Version 1.2.0 adds persistent per-station RF overrides, a spreadsheet-style Station Data editor, and Metric/Imperial input/display selection in Advanced. The propagation backend remains metric/dBm internally.

Version 1.1.0 introduced CONUS-oriented validation/projection, the network best-margin heatmap, inverse/dead-zone output, run-scoped Station lists, and configurable heatmap presentation.

## License

Signal Peak is free and open-source software licensed under the **GNU General Public License version 2 only (GPL-2.0-only)**. See [LICENSE](LICENSE).

You may use, study, modify, and redistribute Signal Peak under the GPLv2 terms. When distributing executable builds, make the corresponding source code and license information available as required by GPLv2. Third-party libraries, map services, datasets, and APIs retain their own licenses and terms; see [Dependencies / Licenses](docs/LICENSES_AND_DEPENDENCIES.md).

Copyright © 2026 HammerheadFistpunch and Signal Peak contributors.

## Quick links

- [Quick Start](docs/QUICK_START.md)
- [User Guide](docs/USER_GUIDE.md)
- [1.2.0 Release Notes](docs/RELEASE_NOTES_1.2.0.md)
- [1.1.0 Release Notes](docs/RELEASE_NOTES_1.1.0.md)
- [CONUS support](docs/CONUS.md)
- [Propagation Model](docs/PROPAGATION_MODEL.md)
- [Station Data](docs/STATION_DATA.md)
- [Location Corrections](docs/LOCATION_CORRECTIONS.md)
- [Outputs](docs/OUTPUTS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Dependencies / Licenses](docs/LICENSES_AND_DEPENDENCIES.md)
- [Special Considerations](docs/SPECIAL_CONSIDERATIONS.md)
- [Roadmap](docs/ROADMAP.md)

The packaged Windows application includes the current documentation under **Help / About**.

## Current UI modes

### Area

Choose an analysis region, acquire the station list, inspect/correct questionable locations, then run propagation on the reviewed station set. Area results include the network best-margin heatmap, inverse-coverage layer, and individual station viewsheds.

### Station

Select one known digipeater or iGate and run the same propagation engine for that individual site. After an Area station search, the Station tab shows that search's station set; **Load full cached catalog** deliberately restores the cumulative cache.

### Custom

Click a proposed site and supply antenna height, transmitter power in Watts, gain, frequency, and maximum calculation range.

### Corrections

Review reported/model coordinates, topographic context, confidence, freshness, and OpenStreetMap communications-site corroboration. Reviewed corrections change the modeled coordinate while preserving the reported coordinate and provenance.

### Station Data

The Station Data tab shows all currently loaded stations in a sortable table. Height, TX power, TX gain, frequency, and path-loss cap can be edited in place and saved as persistent callsign-based overrides.

RF precedence is:

1. saved Station Data user override;
2. RF value already present in station JSON;
3. Advanced/global fallback.

Saved RF overrides are stored separately from APRS/cache position data, so normal station refreshes do not erase manually curated RF values.

### Advanced

Area and Station assumptions can be changed and persisted, including link-budget assumptions, antenna/observer heights, frequency, radial count, DEM resolution, and ITM environmental parameters. TX power can be entered in **Watts or dBm**.

Advanced also contains the **Metric / Imperial** selector. It changes how distance and height fields are entered and displayed:

- Metric: km / m
- Imperial: mi / ft

Signal Peak converts operator-facing values before creating the propagation job. Internal propagation math remains metric and dBm-based.

### Output

The Output tab controls the granular network heatmap band size, maximum displayed margin, per-station display floor, and overlay/inverse opacity. The default network band size is 3 dB.

## Reference profile

Current Area/Station defaults include:

- Frequency: 144.390 MHz
- TX power: 50 W (approximately 47 dBm)
- TX antenna gain: 0 dBd
- RX sensitivity: -119 dBm
- RX antenna gain: +2 dBd
- Operational path-loss cap: **138 dB**
- Digipeater antenna height: 20 m AGL
- iGate antenna height: 3 m AGL
- Observer/receiver height: 2 m AGL
- Radials: **1080 per station**
- Reduced lateral radial gap fill

These are fallback modeling assumptions, not measured installation data. In 1.2.0, known station-specific RF values can override the fallback per station.

## CONUS behavior

Signal Peak chooses the projected UTM CRS from the geographic center of each job. Terrain acquisition uses USGS 3DEP data derived from the requested geography rather than a fixed Utah extent.

The legacy propagation module retains an old Utah-oriented filename internally, but the active station validation and projection layers are not fixed to Utah.

## Network heatmap and inverse coverage

For Area runs, Signal Peak combines successfully modeled per-station margin rasters into a **best remaining link margin** surface. Each cell represents the strongest modeled remaining margin available from any included station.

The **Inverse Coverage — APRS Not Expected** layer identifies cells inside the requested analysis region where no modeled station has positive remaining link margin. It is a threshold/dead-zone product, not a measurement of how many dB below threshold a location is.

Individual station overlays remain in the KMZ for inspection and can be toggled independently.

## Station acquisition

Normal Area discovery can use receive-only APRS-IS sampling, then merge cache and optional seed/fallback records. A built-in **Build Seed…** tool performs longer APRS collection and saves reusable JSON under `ViewshedData/seeds/`.

An aprs.fi API key is optional and is treated as **session-only** rather than persisted in application settings.

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

The resulting executable is `dist/SignalPeak.exe`.

A packaged smoke test is available:

```bash
SignalPeak.exe --self-test
```

GitHub Actions builds and smoke-tests the Windows executable on pushes to `main` and uploads the `Signal-Peak-Windows-1.2.0` artifact.

## Modeling caution

Signal Peak generates predicted VHF coverage. APRS positions and infrastructure inventories can be incomplete; actual ERP, antenna pattern, feedline loss, clutter, foliage, local noise, weather, and receiver installation are not fully known or modeled. Results are planning/analysis predictions, not communications guarantees.
