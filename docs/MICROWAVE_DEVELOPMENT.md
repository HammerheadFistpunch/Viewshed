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
does not add gain or simulate throughput/diversity. The selected ITM H/V setting
represents one channel of a dual-polarized antenna. Check hardware frequency
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

A directional pattern does not exclude every point outside its half-power
beamwidth: sufficient link margin may still support off-axis coverage. The
editable off-axis loss cap limits attenuation in this approximate model.

Validation: polarization impedance and production ITM loss regression, GHz range
and finite-value validation, isotropic link-budget arithmetic, sampling spacing
and endpoint/ridge checks, and job creation including imperial UI mode. A Windows
visual check and packaged executable smoke test remain required before release.
