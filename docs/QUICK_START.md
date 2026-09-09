# Signal Peak Quick Start

This is the shortest path from launching Signal Peak 1.2.0 to producing a coverage result.

## 1. Launch Signal Peak

Run `SignalPeak.exe` from the extracted Windows package, or run `python viewshed_app.py` from source.

Persistent data is stored under `ViewshedData/` beside the executable when possible, with a user-home fallback if that location is not writable.

## 2. Use Area mode

1. Open **Area**.
2. Click the map or enter a center latitude/longitude.
3. Set **Area radius**.
4. Set **Max calculation range** for each station.
5. Choose Digipeaters and/or iGates.
6. Click **Find stations**.

Finding stations does not run terrain propagation. Signal Peak samples APRS-IS, merges cache/seed data, applies reviewed coordinate corrections, and can cross-check nearby OpenStreetMap communications infrastructure.

## 3. Review station locations

If the Area panel reports stations needing review, open **Corrections**. OSM corroboration is evidence only and does not automatically move a station.

## 4. Review station RF data

Open **Station Data** when you have known station-specific RF information.

The table can be sorted by callsign, type, position, height, power, gain, frequency, path-loss cap, or RF source. Double-click an editable RF cell to change it, then click **Save edits**.

Saved per-station values take precedence over station JSON and Advanced defaults. They are stored separately from APRS/cache position data and survive station refreshes.

## 5. Set radio, units, and output assumptions

Open **Advanced** for Area/Station radio assumptions. TX power can be entered in **Watts or dBm**.

Advanced also contains the input-unit selector:

- **Metric** — km / m
- **Imperial** — mi / ft

This changes input/display units only. Signal Peak converts values before the job reaches the propagation engine, which remains metric internally.

Open **Output** for presentation controls such as heatmap band size, maximum displayed margin, per-station display floor, and opacity.

## 6. Run propagation

Return to **Area** and click **Run area propagation**. The job log shows terrain preparation, propagation, merge, and export progress. Cached DEM tiles are retained for future runs.

## 7. Open the result

After completion use **Open Output Folder**, **Open KMZ**, or **Open GeoTIFF**.

The KMZ contains:

- **Granular Network Margin** — best remaining modeled link margin from any included station.
- **Inverse Coverage — APRS Not Expected** — cells where no included station has positive modeled margin.
- **Per-station viewsheds** — individual digipeater/iGate overlays.

**0 dB remaining margin is the modeled operational edge.**

Job files are stored under `ViewshedData/jobs/<timestamp>/output/`.

## Station mode

After an Area station search, the Station tab shows only that search's station set. Use **Load full cached catalog** when you intentionally want the cumulative station cache.

## Default reference profile

Area and Station modes use fallback assumptions including:

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

Known per-station RF values override these fallbacks when present.

## Important limitation

Signal Peak predicts terrain-dependent VHF coverage. It does not know every site's actual antenna pattern, feedline loss, clutter, local noise, or maintenance state. Treat output as an analysis/planning product, not a communications guarantee.
