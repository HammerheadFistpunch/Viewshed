# Signal Peak Quick Start

This is the shortest path from launching Signal Peak 1.1.0 to producing a coverage result.

## 1. Launch Signal Peak

Run `SignalPeak.exe` from the extracted Windows package, or run `python viewshed_app.py` from source.

Persistent data is stored under `ViewshedData/` beside the executable when possible, with a user-home fallback if that location is not writable.

## 2. Use Area mode

1. Open **Area**.
2. Click the map or enter a center latitude/longitude.
3. Set **Area radius** for the region you want to inspect.
4. Set **Max calculation range** for each station. This is a hard computation limit, not a predicted RF boundary.
5. Choose Digipeaters and/or iGates.
6. Click **Find stations**.

Signal Peak samples APRS-IS, merges cache/seed data, applies reviewed corrections, and can cross-check nearby OpenStreetMap communications infrastructure. Finding stations does not run the terrain propagation engine.

## 3. Review station locations

If the Area panel reports stations needing review, open **Corrections**. Use the topo/standard basemap, OSM cross-check, and human-reviewed correction tools as needed. OSM corroboration does not automatically relocate a station.

## 4. Set radio and output assumptions

Open **Advanced** for Area/Station radio assumptions. TX power can be entered in **Watts or dBm**; Watts are converted to dBm internally before link-budget math.

Open **Output** for presentation controls:

- granular network heatmap band size (default 3 dB)
- maximum displayed margin
- per-station display floor
- overlay/inverse opacity

These output controls change presentation, not the underlying ITM path-loss calculation.

## 5. Run propagation

Return to **Area** and click **Run area propagation**. The job log shows terrain preparation, propagation, merge, and export progress. Cached DEM tiles are retained for future runs.

## 6. Open the result

After completion use **Open Output Folder**, **Open KMZ**, or **Open GeoTIFF**.

The KMZ contains:

- **Granular Network Margin** — visible by default; best remaining modeled link margin from any included station, displayed in configurable dB bands.
- **Inverse Coverage — APRS Not Expected** — off by default; cells inside the requested analysis region where no included station has positive modeled margin.
- **Per-station viewsheds** — individual digipeater/iGate overlays for inspection.

The legend matches the configured network banding. **0 dB remaining margin is the modeled operational edge.**

Job files are stored under:

```text
ViewshedData/jobs/<timestamp>/output/
```

## Station mode

After an Area station search, the Station tab shows only that search's station set. Use **Load full cached catalog** when you intentionally want the cumulative station cache. Station mode produces the same network-margin/inverse products, with one station contributing.

## Default reference profile

Area and Station modes use a practical reference profile including:

- 144.390 MHz
- 50 W TX power (approximately 47 dBm)
- 0 dBd TX antenna gain
- -119 dBm RX sensitivity
- +2 dBd RX antenna gain
- 138 dB operational path-loss cap
- 20 m digipeater antenna height AGL
- 3 m iGate antenna height AGL
- 2 m observer/receiver height
- 1080 radials per station

These are assumptions, not measured parameters for each APRS site.

## Important limitation

Signal Peak predicts terrain-dependent VHF coverage. It does not know every site's actual ERP, antenna pattern, feedline loss, clutter, foliage, local noise, weather, receiver installation, or maintenance state. Treat output as an analysis/planning product, not a communications guarantee.
