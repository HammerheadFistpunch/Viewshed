# Signal Peak 1.2.0 Release Notes

Signal Peak 1.2.0 focuses on better station-specific RF assumptions and cleaner operator input without changing the established terrain/ITM/link-margin foundation.

## Per-station RF overrides

Area and Station propagation can now use station-specific RF values when reliable data is available.

Supported station fields include:

- `antenna_height_m` or `antenna_height_agl_m`
- `tx_power_dbm` or `tx_power_w`
- `tx_antenna_gain_dbd` or `tx_antenna_gain_dbi`
- `freq_mhz`
- `max_path_loss_db`

Effective precedence is:

1. saved Station Data user override;
2. RF value already present in station JSON;
3. Advanced/global fallback.

Only fields actually supplied by a station override the global profile. Unknown fields continue to use the documented reference assumptions.

TX power entered in Watts is converted to dBm before propagation. TX gain entered in dBi is converted to dBd. Station-specific RF data forces the worker to resolve that station's effective link budget locally instead of reusing a single pre-resolved global value.

## Station Data editor

A new **Station Data** tab provides a spreadsheet-style view of the currently loaded station catalog.

The table can be sorted by:

- callsign
- station type (`digi` or `igate`)
- latitude / longitude
- antenna height AGL
- TX power
- TX antenna gain
- frequency
- path-loss cap
- RF source

The table can also be filtered to all stations, digipeaters, or iGates.

Height, power, gain, frequency, and path-loss cells can be edited in place. **Save edits** persists callsign-based overrides. **Clear selected overrides** returns selected stations to station JSON or Advanced fallback values.

User RF overrides are stored separately in:

```text
ViewshedData/station_rf_overrides.json
```

This keeps manually researched RF data from being erased by normal APRS/cache refreshes.

## Metric / Imperial input selection

The **Advanced** tab now includes a Metric/Imperial input selector:

- Metric: kilometers / meters
- Imperial: miles / feet

This is intentionally an operator-interface feature only. Signal Peak converts values before job creation; the propagation backend continues to use metric distance/height units and dBm for link-budget calculations.

The selected unit mode applies to Area, Station, Custom, Advanced height/range fields, and Station Data height display.

## Advanced remains the fallback profile

The existing Area/Station Advanced profile remains the fallback when a station has no specific RF value.

Current reference assumptions include:

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

## Reverse HAAT prototype removed

A reverse-HAAT calculator was prototyped during 1.2.0 development and removed before release. APRS PHG height is not a reliable substitute for surveyed FCC-style HAAT or actual antenna AGL, so the tool was not useful enough for Signal Peak's station-data workflow.

## Compatibility

The propagation engine remains based on the existing terrain-profile and Longley-Rice/ITM worker. Version 1.2.0 changes how station assumptions are resolved and how units are presented to the operator; it does not introduce an imperial propagation backend or replace the established network heatmap/inverse calculations.

## Windows build

The GitHub Actions artifact for this release is named:

```text
Signal-Peak-Windows-1.2.0
```

The packaged executable remains `SignalPeak.exe`.
