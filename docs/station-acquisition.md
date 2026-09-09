# Station Acquisition

Signal Peak 1.2.0 uses live APRS observation, a persistent station cache, optional seed/fallback data, reviewed location corrections, and independent RF overrides. A long capture is not required before every propagation run.

## Normal Area flow

1. The optional seed/fallback JSON supplies known stations when available.
2. `ViewshedData/cache/stations.json` supplies previously observed station records.
3. When refreshing, Signal Peak opens a short receive-only APRS-IS connection using a range filter centered on the requested area.
4. Digipeaters are inferred from APRS path use and relevant symbols; iGates are inferred from APRS-IS q-construct entry stations.
5. Position packets heard during the sample are merged into the cache.
6. If an aprs.fi API key is supplied for the session, unresolved discovered infrastructure calls may be looked up in batches and merged into the cache.
7. Reviewed location corrections are applied after acquisition.
8. Saved station RF overrides are applied separately by callsign.
9. The Area search filters the resulting station set to the requested acquisition region and selected station types.

If live services are unavailable, the application can continue with cached/seed records where possible.

## UI settings

Current acquisition controls are available in the application header rather than requiring environment variables:

- **APRS callsign** — optional callsign for receive-only APRS-IS login.
- **aprs.fi key** — optional, session-only API key.
- **Live sample (s)** — observation duration for the Area refresh.
- **Optional seed/fallback** — optional compatible station JSON.
- **Build Seed…** — longer collection workflow for building reusable seed data.

Environment variables remain supported by lower-level components where documented, but the normal desktop workflow does not require them.

## Cache versus RF overrides

The station cache describes observed infrastructure and position/status data. It should be allowed to refresh.

Manually curated RF values are stored separately in:

```text
ViewshedData/station_rf_overrides.json
```

This design prevents APRS/cache refreshes from erasing researched antenna height, power, gain, frequency, or path-loss assumptions.

## Area versus Station catalog scope

After **Find stations**, the Station and Station Data views use the current run-scoped station catalog. Use **Load full cached catalog** in Station mode when the cumulative cache is desired instead.

## Seed Builder

The Seed Builder performs a longer APRS collection than the normal Area refresh and writes reusable JSON under `ViewshedData/seeds/` by default. Seed data is fallback/provenance data; it does not supersede stronger live data or reviewed corrections.

## aprs.fi use

The aprs.fi API is optional and is used only in response to user-started acquisition work. The API key is treated as session-only and is not intentionally persisted by Signal Peak.

APRS PHG-derived RF values should not be treated as surveyed installation data without independent verification.

## Security

Do not put APRS or aprs.fi credentials in source files or station seed files. If a credential was previously committed publicly, rotate it; removing it from the latest tree does not erase Git history.
