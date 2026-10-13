# Microwave propagation development

Branch: `feature/microwave-propagation`, based on the polarization fix in main.

Custom contains Proposed site — 20 MHz to 1 GHz and Proposed site — 1 to 10 GHz.
The microwave section shares the map coordinates above, with independent metric
radius and antenna heights, GHz frequency, dBm power and sensitivity, dBi gains,
polarization, combined system loss, operational reserve, path-loss cap, and loss
sample spacing. Choose receiver sensitivity for the intended bandwidth/modulation.
Advanced and station frequency inputs support ITM's full 20–20000 MHz range;
the dedicated microwave section currently supports the requested 1–10 GHz range.

Microwave jobs retain the working DEM's available radial profile points instead
of capping profiles at 1200. Loss samples are uniformly spaced using the larger
of the requested spacing and working DEM pixel size, including the far endpoint.
Each sampled profile is interpolated to its exact physical endpoint. More than
4096 loss samples per radial is rejected: reduce radius or increase spacing.
The DEM preparation/resampling limits and configured angular radial count still
apply. Smaller spacing increases CPU time; it does not improve source terrain.

ITM is used at distances of at least 1 km. Below 1 km the provisional estimate
uses free-space loss for geometric line of sight; geometrically blocked paths
are excluded. This is not a Fresnel-clearance or short-range multipath model.
Microwave runs require itmlogic and do not silently fall back to geometric-only
coverage when it is missing. Legacy sampling remains unchanged for other jobs.

Both antenna gains are entered relative to isotropic and included in the free-space
link budget with the correct reference conversion. Combined system losses are
subtracted before the path-loss cap; the operational reserve follows the cap.
Legacy reference link budgets are retained for other jobs.

Remaining features: measured antenna pattern import, receiver pattern/aiming, Fresnel clearance inspection,
clutter/vegetation, atmospheric/rain loss and availability predictions, optional
bandwidth/modulation presets, and a dedicated 10–20 GHz workflow. No weather or
clutter losses are computed.

## Antenna presets

TX and RX selectors include uniform/manual, generic Yagi (14 dBi, 30°), dish
(24 dBi, 10°), sector (16 dBi, 90° / 10°), TP-Link CPE510 panel/MIMO (13 dBi,
45° / 30°), and RocketDish 5G30 LW dish/MIMO (30 dBi, symmetric 5.8° approximation).
Generic presets are illustrative starting points, not specifications for every
antenna in that category. All gains and beamwidths remain editable.

TX presets set peak gain, pattern and beamwidth; named 5 GHz presets also set a
5.5 GHz starting frequency. RX presets set peak gain only and assume boresight
alignment toward the proposed site. Gain figures are per antenna/channel; MIMO
does not add gain or simulate throughput/diversity. A selected H or V setting
represents one channel of a dual-polarized antenna. Dual (H + V) evaluates both
ITM polarizations independently and uses the larger path loss (weaker margin),
so both channels must meet the budget. It is a conservative two-channel check,
not spatial multiplexing, combining gain, or a throughput prediction. Below 1 km,
the free-space estimate is polarization independent. Check hardware frequency
range after editing frequency; antenna gain and beamwidth are not automatically
scaled with frequency.

Directional TX loss is a simplified quadratic main-lobe approximation:
`min(off_axis_cap, 12*(az_offset/az_beamwidth)^2 + 12*(el_offset/el_beamwidth)^2)`.
Full beamwidth means 3 dB attenuation at half beamwidth along either axis.
It has no measured sidelobes or nulls and is not an ITU reference-pattern
implementation. Bearings use the DEM's projected grid north; 90° is east.
Positive tilt points upward, negative tilt downward. Elevation uses terrain,
antenna heights and the engine's effective-earth curvature. Directional loss
is subtracted from link margin at each sample before raster interpolation and
the existing gap-fill/smoothing stages; sharp beam edges may be smoothed.

Manufacturer references for named presets:
- CPE710: https://www.tp-link.com/us/business-networking/outdoor-radio/cpe710/v1/
- CPE710 H/V pattern plots: https://static.tp-link.com/upload/product-overview/2025/202511/20251106/CPE%20series-Datasheet.pdf
- CPE510: https://static.tp-link.com/CPE510-Datasheet.pdf
- RocketDish LW: https://techspecs.ui.com/uisp/wireless/rd-5g30-lw

## Verifying directionality

Microwave runs print the active TX pattern, aiming and beamwidth in the run log.
The exported station description also records pattern and aiming. The lower-band
button is explicitly labeled Run 20 MHz–1 GHz propagation; antenna settings below
it apply to Run microwave propagation.

Cached worker rasters now carry an RF configuration signature. Changing aim,
gain, pattern, frequency or other settings invalidates the cached raster; older
rasters without a signature are recalculated.

`python tools/verify_directional_kmz.py` exercises the spawned worker, merge,
network heatmap and KMZ exporter using a synthetic flat DEM. It verifies that
0° and 90° TX aiming rotate the visible beam north/east in the actual PNG stored
inside the KMZ, including a rerun in the same work directory. The unit suite
also checks cache reuse with unchanged settings and invalidation on rotation.
`python tools/verify_directional_kmz.py --dual` checks both-channel worker
execution, beam rotation and the exported dual-polarization label.

A directional pattern does not exclude every point outside its half-power
beamwidth: sufficient link margin may still support off-axis coverage. The
editable off-axis loss cap limits attenuation in this approximate model.

Validation: polarization impedance and production ITM loss regression, GHz range
and finite-value validation, isotropic link-budget arithmetic, sampling spacing
and endpoint/ridge checks, and job creation including imperial UI mode. A Windows
visual check and packaged executable smoke test remain required before release.

## CPE710 and realistic distance checks

CPE710 TX/RX antenna presets use 23 dBi, 9° azimuth / 7° elevation and dual H/V.
The TX preset sets 5.8 GHz, gain, beam and polarization; the RX preset sets gain
and polarization. Neither silently applies maximum power or invents a factory
receiver sensitivity. Both retain editable main-lobe approximations.

The optional **CPE710 pair: planning defaults** button configures both antennas,
20 dBm per-channel TX power, -85 dBm assumed sensitivity, 2 dB combined system
loss, 15 dB reserve, 200 dB cap and 30 km inspection radius. These power and
sensitivity settings are planning assumptions, not certified rate-specific
specifications. Antenna heights and aiming stay at their current values.
Replace TX power with actual per-channel power (do not use a summed two-chain
power as each channel's power), and sensitivity with the intended channel width
and modulation's threshold. The published 27 dBm hardware maximum depends on
region/settings; it is not a guaranteed per-stream power at every data rate.

The live budget readout uses:
`raw budget = TX dBm + TX dBi + RX dBi - system losses - sensitivity dBm`;
`effective budget = min(raw budget, cap) - reserve`.
It reports aligned free-space RX power, margin after cap/reserve and the ideal
zero-margin distance. This arithmetic matches the worker's microwave budget.
It is a forward-link estimate; asymmetric hardware needs a separate reverse-link
run. It does not include terrain, interference, weather or receiver misalignment.

For a CPE710 pair at 5.8 GHz with the planning power/loss/reserve above:

| Assumed sensitivity | Ideal free-space distance |
| --- | --- |
| -85 dBm | 20.6 km |
| -75 dBm | 6.5 km |
| -65 dBm | 2.1 km |

These thresholds illustrate why usable range depends on the desired rate; they
are not manufacturer MCS profiles or throughput promises. At 30 km, FSPL is
137.3 dB, received power is -73.3 dBm and margin after the -85 dBm threshold and
15 dB reserve is -3.3 dB. Using 27 dBm *per channel*, if actually available,
would improve that result by 7 dB; do not infer it from an aggregate power spec.

At 30 km the midpoint 60% first-Fresnel radius is 11.8 m and the 4/3-earth bulge
is 13.2 m. The readout shows both values as clearance context, not a terrain
clearance test. On equal-height, level-ground endpoints their sum is about 25 m;
low poles can fail even with enough free-space signal. ITM terrain propagation
remains the coverage calculation. Source DEM resolution, missing trees/buildings,
ground reflection and the editable pattern approximation limit accuracy.

