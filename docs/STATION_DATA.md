# Station Data Sources and RF Overrides

Signal Peak combines several station-location sources while keeping provenance visible. Version 1.2.0 also keeps manually curated RF assumptions separate from position acquisition so station refreshes do not erase operator-entered RF data.

## APRS-IS

Normal Area discovery uses a receive-only APRS-IS connection and a regional filter around the requested analysis area. This is a live packet stream, not a complete infrastructure directory, so a short sample can miss quiet stations.

## Cache

Observed station records are cached under `ViewshedData/cache/stations.json`. Cache data improves continuity when live APRS sampling is incomplete or unavailable.

## Seed/fallback JSON

The Optional seed/fallback file provides long-lived station knowledge. A seed is an enhancement, not a requirement for normal Area discovery.

Arbitrary station JSON fields are preserved. Signal Peak 1.2.0 recognizes these per-station RF fields when present:

- `antenna_height_m` or `antenna_height_agl_m`
- `tx_power_dbm` or `tx_power_w`
- `tx_antenna_gain_dbd` or `tx_antenna_gain_dbi`
- `freq_mhz`
- `max_path_loss_db`

## Station Data editor

The **Station Data** tab shows the effective RF values for all currently loaded stations in a spreadsheet-style table.

The table can be sorted by any displayed column, including callsign, station type, latitude/longitude, antenna height, TX power, gain, frequency, path-loss cap, and RF source. It can also be filtered to all stations, digipeaters, or iGates.

Double-click an RF cell to edit it. Editable fields are:

- antenna height AGL
- TX power
- TX antenna gain
- frequency
- path-loss cap

Click **Save edits** to persist changes. Click **Clear selected overrides** to remove saved user overrides for the selected callsigns and return those fields to station JSON or Advanced defaults.

## Persistent RF override registry

Station Data edits are stored in:

```text
ViewshedData/station_rf_overrides.json
```

The file is keyed by callsign and stores only RF overrides. It does not replace APRS/cache coordinates, timestamps, confidence, or location-correction records.

This separation is intentional: live APRS and cache refreshes may update position/status information without destroying manually researched height, power, gain, or frequency values.

## RF precedence

For Area and Station propagation, the effective value is resolved in this order:

1. saved user RF override from `station_rf_overrides.json`;
2. RF field already present in the station record/JSON;
3. Advanced/global fallback.

Only fields that are present at a higher-precedence level override the fallback. A station can therefore override only height while continuing to inherit global power, gain, frequency, and path-loss assumptions.

TX power supplied in Watts is converted to dBm before the propagation worker runs. TX gain supplied in dBi is converted to dBd. Per-station RF changes force the worker to resolve the station's link budget locally rather than reusing a single pre-resolved global budget.

## Seed Builder

**Build Seed…** performs a longer APRS collection session than the normal Area sample. It accumulates infrastructure calls, observed positions, packet counts, unresolved calls, reconnect information, and optional aprs.fi resolutions across the session.

The resulting JSON is compatible with the normal station loader and is typically stored under `ViewshedData/seeds/`.

## aprs.fi

aprs.fi is optional. If a key is configured, Signal Peak can use it to resolve infrastructure calls observed on APRS-IS that did not provide a usable position during the live sample.

APRS PHG-derived height values should not be assumed to be surveyed antenna AGL. Use Station Data overrides only when the source and datum are understood.

## OpenStreetMap

OSM communications infrastructure is not a primary APRS station source. It is an independent geographic cross-reference used to corroborate or question an existing station coordinate.

## Merge behavior

When stronger/live position data replaces seed fallback data, Signal Peak clears stale seed-only position provenance so the new coordinate is scored according to its actual source.

Reviewed user location corrections and user RF overrides remain separate from acquisition data and are reapplied after station records are loaded.

For acquisition behavior, also see [station-acquisition.md](station-acquisition.md).
