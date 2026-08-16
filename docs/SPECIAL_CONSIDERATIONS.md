# Special Considerations

Viewshed is an engineering-analysis tool. The following limitations should be understood before interpreting coverage as operational truth.

## Station parameters are usually assumed

APRS packets generally do not provide reliable transmitter ERP, antenna pattern, feedline loss, antenna efficiency, or antenna height AGL. Area and Station modes therefore use a documented reference profile rather than claiming to know each site's actual installation.

The default operational path-loss cap is currently 148 dB. Advanced settings allow it and related assumptions to be changed.

## A model edge is not necessarily an RF edge

Each station has a maximum calculation range. If useful modeled margin remains at that distance, the output can end in a clean circular arc. That is the computation boundary, not a physical radio wall.

## Coverage is probabilistic/approximate in practice

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

APRS, cache, seed, and third-party locations can be stale or wrong. Viewshed preserves reported coordinates and applies only reviewed human corrections to the propagation model.

Timestamp freshness is tracked separately from location confidence. An unknown timestamp does not by itself mean the coordinate is inaccurate.

## OpenStreetMap is corroborating evidence

A nearby OSM communications tower/mast can strongly support an APRS coordinate, but it does not prove that the APRS equipment is located on that exact structure. OSM may describe cellular, microwave, broadcast, public-safety, or shared infrastructure and is not complete everywhere.

Viewshed may automatically increase confidence in an existing coordinate when independent OSM data closely agrees. It does not automatically move a station to an OSM feature.

## APRS-IS is a live stream, not a directory

A short APRS-IS sample can miss infrastructure that simply did not transmit during the observation window. Longer Seed Builder sessions, cache data, and optional aprs.fi resolution improve continuity but do not create a guaranteed complete inventory.

## Large-area terrain analysis trades detail for bounded memory

Very large geographic requests can require enormous native DEM mosaics. Viewshed uses memory-bounded terrain preparation and can downsample large analyses. This makes large runs practical but can reduce fine terrain detail.

## Current geographic scope is not fully generalized

The original propagation backend contains Utah-oriented validation and UTM assumptions. Map display and station acquisition are more geographically general than the backend propagation engine. Do not assume fully validated nationwide/worldwide RF calculations yet.

## Advanced settings can produce plausible-looking but invalid output

Numeric validation only verifies that an Advanced value lies within a broad acceptable range. It does not prove the value is appropriate for a specific site, radio, climate, ground type, or analysis objective.

Record non-default settings when sharing or comparing results.

## External services

Live station acquisition, OSM/Overpass cross-reference, map tiles, and missing DEM downloads depend on external network services. Cached terrain and seed data can reduce network dependence, but not all workflows are fully offline.
