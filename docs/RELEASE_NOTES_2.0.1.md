# Signal Peak 2.0.1

Signal Peak 2.0.1 is a propagation-consistency patch release.

## Fixed

- Custom/future-station runs now start from the same validated Advanced propagation profile used by Area and Station runs.
- Custom mode overrides only its intended proposed-site transmitter values: location/range, antenna height, TX power, TX gain, and frequency.
- Custom runs now inherit the same receiver assumptions, operational path-loss cap, observer height, Longley-Rice/ITM environmental parameters, terrain/detail settings, DEM limits, and output/margin settings as the other run modes.
- Removed the separate Custom operational-reserve path-budget calculation so link-budget handling is uniform across Area, Station, and Custom modes.
- Verified that single-station runs already use the same core propagation engine and shared profile as Area runs, with only explicit per-station RF overrides applied.

## Result

Area, Station, and Custom modes now share one propagation foundation. Differences between results are driven by the station/site inputs and explicit overrides rather than by different propagation rules.
