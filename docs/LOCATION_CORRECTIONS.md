# Signal Peak Location Corrections

Signal Peak keeps station-location corrections separate from seed/cache/APRS station data and from station RF assumptions. A reviewed coordinate answers **where should this station be modeled?**; a Station Data override answers **what radio assumptions should this station use?**.

## Coordinate concepts

Signal Peak preserves three coordinate concepts:

- **Reported coordinate** — the position received from APRS, cache, seed, or another acquisition source.
- **Model coordinate** — the coordinate currently used by the propagation engine.
- **Proposed/reviewed coordinate** — a candidate or human-approved replacement.

A reviewed correction changes the model coordinate while preserving the reported coordinate and provenance.

## Persistent correction storage

Reviewed corrections are stored in:

```text
ViewshedData/station_location_overrides.json
```

They are keyed by callsign and are reapplied whenever that station is loaded again. Correcting a station does **not** rewrite the seed file or APRS/cache source record.

As long as the persistent `ViewshedData` correction registry remains available and the callsign remains the same, an approved station does not need to be corrected again simply because a different seed file or refreshed station cache is used.

## Correction states in 2.1.0

The Corrections UI now exposes the current state directly:

- **Saved correction — approved and used for propagation**
- **Needs review — saved candidate awaiting approval**
- **Needs review**
- **Uncorrected**

The default queue prioritizes stations requiring attention. If no stations currently need review, Signal Peak falls back to the full correction catalog rather than presenting an empty list.

The selected station is also redrawn after the Corrections tab becomes visible, preventing the earlier behavior where the map could remain blank until **Next** was clicked.

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
3. Review the Needs Review queue or use **Show All**.
4. Compare reported/model coordinates with map context and available evidence.
5. Select or enter a proposed coordinate when a correction is justified.
6. Save as a candidate or approve the correction.

## Relationship to Station Data

RF edits are stored separately in:

```text
ViewshedData/station_rf_overrides.json
```

Changing RF height, power, gain, frequency, or path-loss assumptions does not change the station coordinate. Likewise, correcting a coordinate does not create or alter RF assumptions.

This separation lets live APRS data refresh, reviewed coordinate corrections, and manually curated RF information coexist without overwriting one another.

## Caution

A station name or mountaintop name is not enough by itself to justify a correction. Use the strongest available evidence and preserve uncertainty when the actual installation cannot be verified.
