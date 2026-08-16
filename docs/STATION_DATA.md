# Station Data Sources

Viewshed combines several station-location sources while keeping provenance visible.

## APRS-IS

Normal Area discovery uses a receive-only APRS-IS connection and a regional filter around the requested analysis area. This is a live packet stream, not a complete infrastructure directory, so a short sample can miss stations that are quiet during the observation window.

A callsign is optional for normal discovery; Viewshed can use fallback receive-only login behavior when none is configured.

## Cache

Observed station records are cached under `ViewshedData/cache/stations.json`. Cache data improves continuity when live APRS sampling is incomplete or unavailable.

## Seed/fallback JSON

The Optional seed/fallback file provides long-lived station knowledge. A seed is an enhancement, not a requirement for normal Area discovery.

Seed-only coordinates are treated as useful provenance but are not considered equivalent to a current live APRS position. Missing timestamps are tracked as freshness information rather than automatically making the coordinate LOW confidence.

## Seed Builder

**Build Seed…** performs a longer APRS collection session than the normal Area sample. It accumulates infrastructure calls, observed positions, packet counts, unresolved calls, reconnect information, and optional aprs.fi resolutions across the session.

The resulting JSON is compatible with the normal station loader and is typically stored under `ViewshedData/seeds/`.

## aprs.fi

aprs.fi is optional. If a key is configured, Viewshed can use it to resolve infrastructure calls observed on APRS-IS that did not provide a usable position during the live sample.

## OpenStreetMap

OSM communications infrastructure is not a primary APRS station source. It is an independent geographic cross-reference used to corroborate or question an existing station coordinate.

## Merge behavior

When stronger/live position data replaces seed fallback data, Viewshed clears stale seed-only provenance so the new coordinate is scored according to its actual source.

Reviewed user corrections remain separate from acquisition data and are reapplied after station records are loaded.

For implementation details and acquisition behavior, also see [station-acquisition.md](station-acquisition.md).
