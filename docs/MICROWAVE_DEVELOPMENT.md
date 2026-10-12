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

Remaining features: directional patterns/aiming, Fresnel clearance inspection,
clutter/vegetation, atmospheric/rain loss and availability predictions, optional
bandwidth/modulation presets, and a dedicated 10–20 GHz workflow. Gains currently
apply equally in every direction. No weather or clutter losses are computed.

Validation: polarization impedance and production ITM loss regression, GHz range
and finite-value validation, isotropic link-budget arithmetic, sampling spacing
and endpoint/ridge checks, and job creation including imperial UI mode. A Windows
visual check and packaged executable smoke test remain required before release.
