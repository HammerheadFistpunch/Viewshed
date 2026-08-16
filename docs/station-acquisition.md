# Station acquisition

Viewshed 0.2 uses a local station cache so viewshed generation does not require a 24-hour capture before every run.

## Normal flow

1. The bundled station JSON (or a user-selected compatible JSON) is used as seed/fallback data.
2. `ViewshedData/cache/stations.json` is reused when it is less than six hours old **and** covers the requested acquisition area.
3. Otherwise the worker opens a short APRS-IS connection using a range filter centered on the requested area. The default observation window is 45 seconds.
4. Digipeaters are inferred from used APRS path entries and digipeater symbols. iGates are inferred from APRS-IS q-construct entry stations.
5. Position packets heard during the observation are merged into the cache.
6. If an aprs.fi API key is configured, discovered infrastructure calls without a position are looked up in batches through aprs.fi and merged into the same cache.
7. If live services are unavailable, the application continues with cached/seed data.

## Optional settings

For the current 0.2 build these are environment variables. A settings panel is planned for the GUI.

- `VIEWSHED_APRS_CALLSIGN` — callsign used for the read-only APRS-IS login. If omitted, `N0CALL` is used with pass `-1`.
- `VIEWSHED_APRSFI_API_KEY` — the user's own aprs.fi API key. It is never committed to the repository.
- `VIEWSHED_LIVE_REFRESH_SECONDS` — APRS-IS observation time when refreshing, from `0` to `300` seconds. Default: `45`.

The aprs.fi API is used only in response to a user-started viewshed job and only for specific callsigns discovered or already known. It is not used for background harvesting.

## Security

Do not put APRS or aprs.fi credentials in source files. The older experimental Utah scraper that contained embedded credentials has been removed from the current branch. If a credential was previously committed publicly, rotate it; removing it from the latest tree does not erase Git history.
