# Viewshed Propagation Model

## Purpose

Viewshed estimates VHF coverage using terrain, radio assumptions, and Longley-Rice/ITM path-loss calculations. It is intended for planning and comparative analysis, not as a guarantee of communications performance.

## Pipeline

The current analysis path is:

```text
station coordinate
    -> USGS 3DEP terrain / cached DEM
    -> memory-bounded analysis DEM
    -> radial terrain profiles
    -> free-space loss + Longley-Rice/ITM attenuation
    -> total modeled path loss
    -> remaining link margin
    -> per-station raster
    -> per-station KMZ overlays
```

An internal station-count raster may still be produced as a merge/intermediate artifact, but it is no longer presented as the composite coverage view because overlapping modeled footprints are not a useful substitute for per-station link margin.

## Reference Area/Station profile

Default Area and Station assumptions are currently:

- Frequency: 144.390 MHz
- TX power: 47 dBm (50 W)
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

These values are a reference profile because APRS normally does not provide reliable station ERP, antenna pattern, feedline loss, or installation-height metadata.

## Link margin

Viewshed uses:

```text
remaining link margin = operational path-loss budget - modeled path loss
```

At the default 138 dB cap:

- positive margin means modeled loss is below the selected operational budget;
- approximately 0 dB is the reference operational edge;
- negative values are below the reference threshold and are not rendered as operational coverage.

The operational path-loss cap intentionally limits an otherwise more idealized transmitter/receiver link budget. It represents a practical modeling assumption rather than a physical constant. The 138 dB reference cap is deliberately more conservative than the earlier 148 dB profile.

Custom stations calculate their cap from the entered transmitter power and antenna gain, the reference receiver assumptions, and a 20 dB operational reserve. For example, a 5 W transmitter with 0 dBd TX gain produces a 138 dB operational cap under the reference receiver assumptions.

## Maximum calculation range

Each station is evaluated only to the user-selected maximum calculation range. This is a computational boundary, not an RF cutoff.

If a station still has positive modeled margin when its radial reaches that boundary, the resulting coverage can show a clean circular arc. That means the analysis ended before the model reached the operational threshold in that direction; it does not mean propagation actually stops at that circle.

Choose a calculation range large enough for the question being asked, while remembering that very large ranges increase terrain and computation cost.

## ITM / Longley-Rice

For usable terrain profiles, the worker uses the `itmlogic` implementation of Longley-Rice/ITM attenuation and adds free-space path loss. Exposed Advanced inputs include climate, refractivity, ground conductivity, relative permittivity, and polarization.

These values are technical model parameters. Changing them can materially change predicted loss and should be done only when there is a defensible reason.

## Terrain data

Viewshed obtains USGS 3DEP 1-arcsecond elevation data and maintains a shared DEM cache under `ViewshedData/cache/dem/`.

For large geographic requests, building and processing the complete native-resolution mosaic can require excessive memory. Viewshed therefore bounds analysis size and can merge/downsample directly to an analysis-safe raster. Small analyses retain substantially more native terrain detail; very large analyses trade resolution for bounded memory and practical runtime.

## Worker resolution, radials, and canyon shadows

The propagation worker crops terrain around each station and may downsample that crop to the configured worker maximum dimension. The default is 2500 pixels. The radial count controls angular sampling; the reference profile now uses 1080 radials.

Coverage between sampled radials requires a small amount of raster gap filling. Earlier settings allowed this fill to spread too far sideways at long range and could visually leak coverage into terrain shadows or narrow canyons. The reference gap-fill factor is now reduced to 0.25. This does not make the terrain model perfect, but it limits interpolation to a much smaller neighborhood instead of treating nearby radial coverage as equivalent.

Higher compute settings can increase computation and memory use and do not automatically guarantee a more accurate result when the underlying station assumptions are uncertain.

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

## Geographic caveat

Parts of the legacy propagation backend still contain Utah-oriented assumptions, including validation bounds and UTM 12N behavior. The map/acquisition UI is more general than the underlying legacy engine. Full national/generalized propagation support remains future work.
