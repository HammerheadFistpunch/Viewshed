# Signal Peak 2.2.1 Release Notes

## 2.2.1

Patch release for the 2.2.x line.

### Fixes

- Treat confirmed USGS 3DEP/TNMAccess areas with no available DEM tile as nodata rather than failing the propagation run. This allows edge and ocean-adjacent searches to continue when terrain data is legitimately absent.
- Align the packaged release version, source core version, README, Quick Start, User Guide, Outputs documentation, and Help/About release selection on **2.2.1**.

### Compatibility

This release does not change the propagation model or the meaning of the displayed link-margin edge. The existing calculation-range margin behavior remains intentional.
