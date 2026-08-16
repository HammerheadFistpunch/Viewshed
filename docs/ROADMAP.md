# Viewshed Roadmap

This roadmap reflects the current state after the map-first UI, APRS/OSM location-confidence workflow, large-DEM memory guard, output/cancellation sprint, Advanced settings, and offline documentation/help work.

The guiding principle remains: UI/workflow changes must not silently change the propagation foundation. Area, Station, and Custom feed the same terrain/ITM/link-margin engine, with differences limited to explicit site/radio inputs.

## Completed product milestones

### Job workflow

- [x] Cancel a running propagation job from the UI.
- [x] Report cancelled jobs separately from failed jobs.
- [x] Preserve shared DEM cache on cancellation.
- [x] Provide Open Output Folder, Open KMZ, and Open GeoTIFF actions after completion.

### Coverage/output presentation

- [x] Rename the combined visual product around **Coverage Overlap** instead of treating it as a generic heatmap.
- [x] Document that clean circular edges can be the configured maximum calculation range rather than a physical RF boundary.
- [x] Lower the Area/Station reference operational path-loss cap to 148 dB after field-review of overly optimistic range behavior.
- [ ] Add explicit range-clipped metadata/legend treatment when useful margin remains at the calculation boundary.
- [ ] Continue improving categorical per-station Strong/Good/Marginal presentation while retaining raw link-margin rasters.

### Station corrections and confidence

- [x] Separate coordinate confidence from position freshness.
- [x] Default Corrections to a Needs Review queue sorted by confidence.
- [x] Add Next and auto-advance after save/approval.
- [x] Keep the full catalog visible when the review queue is exhausted.
- [x] Add Standard/Topo basemap switching.
- [x] Add OpenStreetMap/Overpass communications-site cross-reference.
- [x] Use strong OSM/APRS geographic agreement as automatic corroboration of the existing coordinate.
- [x] Keep human approval mandatory before moving a model coordinate to an OSM location.
- [ ] Add DEM-derived elevation and hillshade assistance.
- [ ] Add terrain plausibility warnings without automatic relocation.

### Advanced assumptions

- [x] Add a persistent Advanced tab for Area/Station radio and propagation assumptions.
- [x] Expose path-loss cap, TX/RX assumptions, antenna heights, frequency, radial count, display limits, worker DEM size, and key ITM parameters.
- [x] Add numeric validation and Reset to Viewshed defaults.
- [ ] Add named/preset reference profiles if real-world validation shows they are useful.

### Documentation and Help

- [x] Refresh `README.md` as the project entry point.
- [x] Add `docs/QUICK_START.md`.
- [x] Add `docs/USER_GUIDE.md`.
- [x] Add `docs/PROPAGATION_MODEL.md`.
- [x] Add `docs/STATION_DATA.md`.
- [x] Add `docs/LOCATION_CORRECTIONS.md`.
- [x] Add `docs/OUTPUTS.md`.
- [x] Add `docs/TROUBLESHOOTING.md`.
- [x] Add `docs/LICENSES_AND_DEPENDENCIES.md`.
- [x] Add `docs/SPECIAL_CONSIDERATIONS.md`.
- [x] Add an offline Help/About tab and bundle the documentation in the Windows executable.
- [ ] Add an exact pinned dependency/license manifest as part of a formal release process.
- [ ] Add a clear top-level project license before formal distribution.

## Next recommended sprint

### 1. DEM-assisted correction review

Reuse the USGS 3DEP data already downloaded by Viewshed to add:

- elevation at reported coordinate;
- elevation at proposed/model coordinate;
- optional hillshade/local terrain display;
- elevation delta/local terrain context.

The first version should be read-only/advisory. It must not automatically relocate a station.

### 2. Terrain-based location plausibility

Once elevation readout is stable, add conservative warnings such as:

- reported point is unusually low relative to nearby terrain;
- much higher terrain exists nearby;
- coordinate is inconsistent with an infrastructure site expected to be on a ridge/peak.

These checks should only change review priority/confidence when evidence is strong and explainable.

### 3. Range-clipping diagnostics

The propagation engine currently stops at the selected station maximum calculation range. Add diagnostics that detect when one or more radials still have positive operational margin at the outer boundary, then:

- mark the station/result as range-clipped;
- expose that fact in the job log;
- distinguish calculation-ended-here from modeled-no-coverage in output metadata/legend.

### 4. Geographic generalization

Remove remaining Utah prototype assumptions, especially:

- hardcoded station validation bounds;
- fixed UTM 12N behavior;
- Utah-oriented legacy naming.

Do not claim national/generalized propagation support until this is complete and tested.

### 5. Validation and regression tests

Strengthen automated and manual tests around:

- station acquisition/provenance merges;
- OSM corroboration thresholds;
- reviewed correction persistence;
- Advanced settings propagation into jobs;
- large-area DEM behavior;
- cancellation;
- range clipping;
- documentation packaging;
- KMZ/GeoTIFF output semantics.

## Special considerations that remain part of the product contract

- APRS positions may be stale, incomplete, or incorrect.
- Missing timestamps describe freshness, not coordinate accuracy.
- Station ERP, antenna height, pattern, and feedline losses are generally not available from APRS.
- Area and Station modes therefore use explicit reference assumptions, currently including a 148 dB operational path-loss cap.
- OSM communications infrastructure is corroborating evidence, not proof of station identity.
- Coverage is a terrain/propagation prediction, not a communications guarantee.
- Weather, vegetation, buildings, local clutter, receiver quality/noise, feedline loss, polarization mismatch, and other real-world factors are not fully modeled.
- APRS-IS is a live packet stream, not a complete station directory.
- Extremely large analyses may use reduced terrain resolution to keep memory bounded.
- The legacy propagation backend still contains Utah-oriented assumptions.
