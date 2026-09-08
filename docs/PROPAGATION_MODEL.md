# Signal Peak Propagation Model

## Purpose

Signal Peak estimates VHF coverage using terrain, radio assumptions, and Longley-Rice/ITM path-loss calculations. It is intended for planning and comparative analysis, not as a guarantee of communications performance.

## Pipeline

The current analysis path is:

```text
station coordinate
    -> USGS 3DEP terrain / cached DEM
    -> local job UTM projection
    -> memory-bounded analysis DEM
    -> radial terrain profiles
    -> free-space loss + Longley-Rice/ITM attenuation
    -> total modeled path loss
    -> remaining link margin
    -> per-station raster
    -> network best-margin / inverse products
    -> KMZ + GIS outputs
```

A station-count raster is also produced for compatibility/GIS use, but it is not treated as a signal-strength surface.

## Reference Area/Station profile

Default Area and Station assumptions are currently:

- Frequency: 144.390 MHz
- TX power: 50 W (approximately 47 dBm)
- TX antenna gain: 0 dBd
- RX sensitivity: -119 dBm
- RX antenna gain: +2 dBd
- Operational path-loss cap: 138 dB
- Digipeater antenna height: 20 m AGL
- iGate antenna height: 3 m AGL
- Receiver/observer height: 2 m AGL
- 1080 radial directions per station
- 0 dB displayed operational margin floor
- Reduced lateral radial gap fill (0.25 factor)

Area/Station TX power may be entered in Watts or dBm. Watts are converted to dBm before link-budget math.

These values are a reference profile because APRS normally does not provide reliable station ERP, antenna pattern, feedline loss, or installation-height metadata.

## Link margin

Signal Peak uses:

```text
remaining link margin = operational path-loss budget - modeled path loss
```

At the default 138 dB cap:

- positive margin means modeled loss is below the selected operational budget;
- approximately 0 dB is the reference operational edge;
- below-threshold values are not treated as reliable operational coverage.

The operational path-loss cap is a practical modeling assumption rather than a physical constant. The 138 dB reference cap is deliberately more conservative than the earlier 148 dB profile.

Custom stations calculate their cap from the entered transmitter power and antenna gain, the reference receiver assumptions, and a 20 dB operational reserve.

## Network best-margin heatmap

For each successfully modeled station, Signal Peak has a per-station remaining-margin raster. The 1.1.0 network heatmap reprojects those rasters to the common analysis grid and keeps the highest available margin at each cell:

```text
network best margin(cell) = max(station margin(cell))
```

The displayed network surface is quantized into configurable dB bands. The default is 3 dB. The stepped color progression is blue → cyan → green → yellow → orange → red from the operational edge toward stronger remaining margin.

This product answers “what is the best modeled APRS link available here from the included network?” It is not a station-count surface and is not measured received power.

## Inverse coverage

The inverse layer marks cells inside the requested analysis region where no included station has positive modeled margin. It is a binary threshold product.

The current operational per-station raster does not preserve a reliable negative-margin continuum below threshold, so the inverse layer must not be interpreted as “how many dB below threshold” a location is.

## Maximum calculation range

Each station is evaluated only to the user-selected maximum calculation range. This is a computational boundary, not an RF cutoff.

If a station still has positive modeled margin when its radial reaches that boundary, the result can show a clean circular arc. That means the analysis ended before the model reached the operational threshold in that direction.

## ITM / Longley-Rice

For usable terrain profiles, the worker uses the `itmlogic` implementation of Longley-Rice/ITM attenuation and adds free-space path loss. Exposed Advanced inputs include climate, refractivity, ground conductivity, relative permittivity, and polarization.

These values are technical model parameters. Changing them can materially change predicted loss and should be done only when there is a defensible reason.

## Terrain data and projection

Signal Peak obtains USGS 3DEP 1-arcsecond elevation data and maintains a shared DEM cache under `ViewshedData/cache/dem/`.

Version 1.1.0 selects a local UTM CRS from each job's geography rather than using a fixed Utah/Zone-12 projection. Station validation likewise uses normal WGS84 coordinate bounds rather than the old Utah bounding box.

For large requests, Signal Peak bounds analysis size and can downsample to an analysis-safe raster. Small analyses retain substantially more native terrain detail; very large analyses trade resolution for bounded memory and practical runtime.

One projected CRS is used per job, so unusually broad jobs spanning multiple UTM zones should be interpreted cautiously.

## Worker resolution, radials, and canyon shadows

The propagation worker crops terrain around each station and may downsample that crop to the configured worker maximum dimension. The default is 2500 pixels. The reference profile uses 1080 radials.

Coverage between sampled radials requires a small amount of raster gap filling. The reference gap-fill factor is 0.25 to limit sideways visual spread in terrain shadows and narrow canyons.

## Important unmodeled or simplified effects

Current results do not fully represent:

- exact antenna radiation pattern
- actual ERP/EIRP per site
- feedline and connector loss
- antenna efficiency and mounting loss
- buildings and detailed urban clutter
- local foliage and seasonal vegetation
- receiver noise floor and local interference
- polarization mismatch beyond the selected model assumption
- weather-specific ducting or anomalous propagation
- station hardware condition and maintenance state

The legacy propagation module still has a Utah-oriented filename, but that filename is implementation history rather than an active 1.1.0 geographic restriction.
