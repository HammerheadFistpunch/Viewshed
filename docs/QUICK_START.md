# Viewshed Quick Start

This is the shortest path from launching Viewshed to producing a coverage result.

## 1. Launch Viewshed

Run `Viewshed.exe` from the extracted Windows package, or run `python viewshed_app.py` from source.

Viewshed stores persistent data beside the executable when possible under `ViewshedData/`. If that location is not writable, it falls back to a `ViewshedData` folder in the user home directory.

## 2. Use Area mode

1. Open **Area**.
2. Click the map or enter a center latitude/longitude.
3. Set **Area radius** for the region you want to inspect.
4. Set the station **maximum calculation range**. This is a hard outer computation limit for each station, not a predicted RF boundary.
5. Choose Digipeaters and/or iGates.
6. Click **Find stations**.

Viewshed samples APRS-IS, merges cache/seed data, applies reviewed corrections, and cross-checks nearby OpenStreetMap communications infrastructure when available. Finding stations does not run the terrain propagation engine.

## 3. Review station locations

If the Area panel reports stations needing review, open **Corrections**.

- The default list shows stations that need review.
- Use **Next** to move through the queue.
- A topographic basemap is available.
- OSM matches are corroborating evidence only.
- **Use OSM point** copies a matched OSM location into the proposal fields but does not approve it automatically.
- **Approve correction** changes the modeled coordinate while preserving the APRS-reported coordinate.

A close OSM communications-site match can automatically improve confidence in the existing APRS/seed coordinate. Viewshed does not automatically move a station to an OSM feature.

## 4. Run propagation

Return to **Area** and click **Run area propagation**.

The job log shows acquisition, terrain preparation, propagation, merge, and export progress. Use **Cancel Run** to stop a job. Cached DEM tiles are kept for future runs.

## 5. Open the result

When a run completes, use:

- **Open Output Folder**
- **Open KMZ**
- **Open GeoTIFF**

Job files are stored under:

```text
ViewshedData/jobs/<timestamp>/output/
```

## Default radio profile

Area and Station modes currently default to a practical reference profile including:

- 144.390 MHz
- 47 dBm transmitter power (50 W)
- 0 dBd TX antenna gain
- -119 dBm receiver sensitivity
- +2 dBd RX antenna gain
- 148 dB operational path-loss cap
- 20 m digipeater antenna height AGL
- 3 m iGate antenna height AGL
- 2 m observer/receiver height

These are assumptions, not measured parameters for each APRS site.

## Advanced settings

Open **Advanced** to change the reference assumptions used by Area and Station jobs. Settings are persisted to `ViewshedData/advanced_settings.json` and can be reset to Viewshed defaults.

Changing advanced parameters can materially change predicted coverage. Use the defaults unless you understand the parameter being changed.

## Important limitation

Viewshed predicts terrain-dependent VHF coverage. It does not know the actual ERP, antenna pattern, feedline loss, clutter, foliage, buildings, local noise, weather, receiver installation, or maintenance state of every site. Treat output as an analysis/planning product, not a communications guarantee.
