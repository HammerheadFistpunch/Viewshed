# Signal Peak Location Corrections

Signal Peak keeps station-location correction separate from station RF assumptions. A reviewed coordinate answers **where should this station be modeled?**; a Station Data override answers **what radio assumptions should this station use?**. The two registries are independent.

## Coordinate concepts

Signal Peak preserves three coordinate concepts:

- **Reported coordinate** — the position received from APRS, cache, seed, or another acquisition source.
- **Model coordinate** — the coordinate currently used by the propagation engine.
- **Proposed/reviewed coordinate** — a candidate or human-approved replacement.

A reviewed correction changes the model coordinate while preserving the reported coordinate and provenance.

## Confidence and freshness

Location confidence and timestamp freshness are tracked separately. A missing or old timestamp does not automatically mean a coordinate is geographically wrong.

The correction queue prioritizes records with stronger reasons for review, such as weak provenance, explicit correction candidates, or disagreement with independent geographic evidence.

## OpenStreetMap cross-reference

Signal Peak can compare station coordinates with nearby OSM communications towers/masts. A close match can corroborate an existing coordinate, but OSM is evidence rather than authority:

- OSM may describe cellular, microwave, broadcast, public-safety, or shared infrastructure.
- A nearby tower does not prove the APRS station is installed on that structure.
- OSM coverage is incomplete.

Signal Peak does not silently move a station to an OSM feature. Human review is required before changing the model coordinate.

## Corrections workflow

1. Acquire or load stations.
2. Open **Corrections**.
3. Review stations in the Needs Review queue; use **Show All** when needed.
4. Compare reported/model coordinates with Standard/Topo map context and OSM evidence.
5. Select or enter a proposed coordinate when a correction is justified.
6. Save/approve the correction.

Reviewed corrections are stored under `ViewshedData/station_location_overrides.json` and are reapplied after station acquisition.

## Relationship to Station Data

Signal Peak 1.2.0 stores RF edits separately in `ViewshedData/station_rf_overrides.json`.

Changing RF height, power, gain, frequency, or path-loss assumptions does **not** change the station coordinate. Likewise, correcting a coordinate does not create or alter RF assumptions.

This separation lets live APRS data refresh, reviewed coordinate corrections, and manually curated RF information coexist without overwriting one another.

## Caution

A station name or mountaintop name is not enough by itself to justify a correction. Use the strongest available evidence and preserve uncertainty when the actual installation cannot be verified.
