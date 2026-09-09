# Special Considerations

Signal Peak is an engineering-analysis tool. The following limitations should be understood before interpreting coverage as operational truth.

## Station parameters are usually assumed

APRS packets generally do not provide reliable transmitter ERP, antenna pattern, feedline loss, antenna efficiency, or antenna height AGL. Area and Station modes therefore use a documented reference profile when station-specific data is unavailable.

The current default operational path-loss cap is **138 dB**. Advanced settings allow it and related assumptions to be changed.

Signal Peak 1.2.0 can use station-specific RF overrides for height, TX power, gain, frequency, and path-loss cap. These values improve the model only when the source is understood. A manually entered value should not be treated as measured merely because it is station-specific.

## RF override provenance matters

The Station Data editor stores curated RF values separately from APRS/cache records. That persistence is intentional, but it also means an old manual assumption can outlive a station hardware change.

When possible, record the source externally and periodically review overrides. APRS PHG-derived values are coarse operator metadata and should not automatically be treated as surveyed antenna AGL or precise transmitter characteristics.

## Metric / Imperial selection is presentation only

The Advanced unit selector changes how distance and height fields are entered and displayed. It does not change the propagation backend. Values are converted to metric before propagation.

When transcribing published station data, verify whether the source is feet or meters and whether height means AGL, AMSL, HAAT, tower height, or antenna radiation-center height.

## A model edge is not necessarily an RF edge

Each station has a maximum calculation range. If useful modeled margin remains at that distance, the output can end in a clean circular arc. That is the computation boundary, not a physical radio wall.

## Coverage is approximate in practice

Terrain/ITM modeling cannot fully account for:

- local buildings and urban clutter
- seasonal foliage
- exact antenna radiation pattern and orientation
- feedline/connector losses
- antenna installation efficiency
- local receiver noise/interference
- vehicle/body shielding
- hardware condition
- weather-specific anomalous propagation
- every polarization and multipath effect

Use results for planning and comparison, not as a guarantee that a packet or voice contact will succeed.

## Station coordinates can be imperfect

APRS, cache, seed, and third-party locations can be stale or wrong. Signal Peak preserves reported coordinates and applies only reviewed human corrections to the propagation model.

Timestamp freshness is tracked separately from location confidence. An unknown timestamp does not by itself mean the coordinate is inaccurate.

## OpenStreetMap is corroborating evidence

A nearby OSM communications tower/mast can strongly support an APRS coordinate, but it does not prove that the APRS equipment is located on that exact structure. OSM may describe cellular, microwave, broadcast, public-safety, or shared infrastructure and is not complete everywhere.

Signal Peak may increase confidence in an existing coordinate when independent OSM data closely agrees. It does not automatically move a station to an OSM feature.

## APRS-IS is a live stream, not a directory

A short APRS-IS sample can miss infrastructure that simply did not transmit during the observation window. Longer Seed Builder sessions, cache data, and optional aprs.fi resolution improve continuity but do not create a guaranteed complete inventory.

## Large-area terrain analysis trades detail for bounded memory

Very large geographic requests can require enormous native DEM mosaics. Signal Peak uses memory-bounded terrain preparation and can downsample large analyses. This makes large runs practical but can reduce fine terrain detail.

## Geographic scope

Current Signal Peak supports regional CONUS-oriented propagation using WGS84 station validation, USGS 3DEP terrain, and a job-local UTM projection. Very broad multi-zone jobs still deserve caution, and global terrain support is not implemented.

## Advanced settings can produce plausible-looking but invalid output

Numeric validation only verifies that an Advanced value lies within a broad acceptable range. It does not prove the value is appropriate for a specific site, radio, climate, ground type, or analysis objective.

Record non-default settings when sharing or comparing results.

## External services

Live station acquisition, OSM/Overpass cross-reference, map tiles, and missing DEM downloads depend on external network services. Cached terrain and seed data can reduce network dependence, but not all workflows are fully offline.
