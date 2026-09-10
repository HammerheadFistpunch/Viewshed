# Signal Peak Quick Start

This is the shortest path from launching Signal Peak 2.0.0 to producing a coverage result.

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

Signal Peak may search beyond the Area boundary for acquisition purposes, but 2.0.0 limits the final propagation station set to station centers inside the selected Area radius.

## 3. Review station locations

If the Area panel reports stations needing review, open **Corrections**. OSM corroboration is evidence only and does not automatically move a station.

## 4. Review station RF data

Open **Station Data** when you have known station-specific RF information. Saved per-station values take precedence over station JSON and Advanced defaults and survive station refreshes.

## 5. Choose terrain detail and resource limits

Open **Resources** before a run when you want to control compute/detail behavior.

- **Auto** — safe balanced planning from the real run and current system resources.
- **Fast** — prioritizes speed and lower memory use.
- **Standard** — balances speed and terrain detail.
- **High** — preserves more terrain detail at higher compute cost.
- **Max** — prioritizes stability first, then the highest terrain detail the machine can safely handle. Worker count may fall to one and large runs can be very slow.

**Memory limit (GB)** is an optional planning ceiling. Enter `0` for automatic management. Signal Peak keeps RAM in reserve for Windows and other applications and automatically reduces parallel workers when necessary.

Use **Refresh system resources** to view available RAM and CPU information.

## 6. Set radio, units, and output assumptions

Open **Advanced** for Area/Station RF assumptions. TX power can be entered in **Watts or dBm**. Metric/Imperial changes operator-facing input/display units only; propagation remains metric internally.

Open **Output** for presentation controls such as heatmap band size, maximum displayed margin, per-station display floor, and opacity.

## 7. Run propagation

Return to **Area** and click **Run area propagation**. Immediately before the run, Signal Peak calculates the safe terrain resolution, analysis raster size, memory budget, and worker count from the selected detail preset and actual station set.

The job log records the resulting resource plan.

DEM cache entries are resolution-aware. Existing terrain is reused when it meets the requested detail. Asking for higher detail can trigger new terrain preparation rather than silently reusing a coarser cached DEM.

## 8. Open the result

After completion use **Open Output Folder**, **Open KMZ**, or **Open GeoTIFF**.

The KMZ contains:

- **Granular Network Margin** — best remaining modeled link margin from any included station.
- **Inverse Coverage — APRS Not Expected** — cells where no included station has positive modeled margin.
- **Per-station viewsheds** — individual digipeater/iGate overlays.

**0 dB remaining margin is the modeled operational edge.**

Job files are stored under `ViewshedData/jobs/<timestamp>/output/`.

## Station mode

After an Area station search, the Station tab shows only that search's station set. Use **Load full cached catalog** when you intentionally want the cumulative station cache.

## Important limitation

Signal Peak predicts terrain-dependent VHF coverage. It does not know every site's actual antenna pattern, feedline loss, clutter, local noise, or maintenance state. Treat output as an analysis/planning product, not a communications guarantee.
