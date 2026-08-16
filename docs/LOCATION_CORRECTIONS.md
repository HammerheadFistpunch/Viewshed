# Station Location Confidence and Corrections

## Principles

Viewshed keeps reported station data separate from modeled corrections.

- Raw/reported coordinates are preserved.
- Reviewed corrections can change the coordinate used by propagation.
- Candidates do not change propagation until approved.
- Callsigns/names are never used to infer a new coordinate by themselves.
- OpenStreetMap and terrain are corroborating evidence, not automatic relocation authority.

## Location confidence

Location confidence represents trust in the coordinate provenance. It is intentionally separate from observation freshness.

Typical source baselines are:

- reviewed override: HIGH / 100
- APRS-IS coordinate: HIGH
- aprs.fi coordinate: HIGH
- cache: MEDIUM
- seed: MEDIUM
- unknown provenance: MEDIUM unless other concerns apply

An explicit unreviewed correction candidate remains in the review queue until resolved.

## Freshness

Freshness indicates whether Viewshed knows when the station position was observed. Labels include recent, aging, stale, very stale, and unknown.

A missing timestamp does not by itself mean the coordinate is wrong and does not by itself lower location confidence.

## OpenStreetMap corroboration

Viewshed can query nearby OSM communications infrastructure through Overpass.

Current interpretation is conservative:

- Very close communications-site agreement can automatically corroborate the existing APRS/seed coordinate and raise its confidence.
- A moderate match is shown as supporting context.
- A distant match can keep weak-provenance coordinates in the review queue because the datasets do not agree closely.
- No match is not treated as evidence that the station is wrong because OSM is incomplete.
- Strong APRS-IS/aprs.fi provenance is not automatically invalidated by an unrelated nearby OSM site.

OSM corroboration changes confidence in the existing coordinate. It does not automatically move the station.

## Corrections queue

The default Corrections list shows stations needing review and sorts lowest confidence first.

Controls include:

- **Show All / Needs Review**
- **Next**
- **Cross-check OSM**
- **Use OSM point**
- **Topo / Standard** basemap selection
- **Save as candidate**
- **Approve correction**
- **Remove my override**

Saving or approving normally advances to the next station. If the review queue becomes empty, the UI falls back to the full catalog rather than making the station list appear to disappear.

## Candidate vs reviewed

A candidate stores a proposed coordinate and provenance for later review but does not affect propagation.

A reviewed correction becomes the model coordinate. The original reported coordinate remains stored for auditing and display.

## OSM point as a proposal

**Use OSM point** copies the nearest matched communications feature into the proposal fields and records OSM/Overpass as the source. The user must still approve the correction.

This matters because an OSM communications tower may be cellular, microwave, commercial broadcast, public safety, shared infrastructure, or unrelated to the APRS station.

## Future DEM assistance

A future correction enhancement is planned to show DEM-derived elevations and terrain plausibility warnings. Those checks must remain advisory and must not silently move a transmitter to a nearby summit or ridgeline.
