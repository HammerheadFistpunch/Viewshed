# Signal Peak 1.0.0 Release Readiness

Date: 2026-08-16

This document records release-readiness findings. It is not legal advice or a professional penetration test.

## Legal status

Signal Peak should not yet be treated as cleared for public binary redistribution.

### Project license

The repository does not currently contain a top-level project LICENSE selected by the copyright owner. Choose an explicit license before a formal public release.

### aprslib GPLv2 dependency

The runtime dependency aprslib 0.7.2 is published under GNU GPLv2. Signal Peak imports it for APRS packet parsing and PyInstaller may bundle it into the Windows executable. Before distributing the binary, choose one of these paths:

- use a GPLv2-compatible project/distribution strategy and provide required source/notices;
- replace aprslib with a suitably licensed parser and audit again; or
- obtain separate permission from the aprslib copyright holder.

Making the application free of charge does not by itself remove software-license obligations.

### aprs.fi

The optional aprs.fi API requires distributed applications to have users provide their own API keys, identify the application by name/version/home page in the HTTP User-Agent, credit aprs.fi as a data source, and contact the service operator when distributing an application using the API.

Signal Peak 1.0.0 does not bundle a shared key and identifies API HTTP requests as SignalPeak/1.0.0. Before public release, add visible aprs.fi source credit when its data is used and contact the operator as requested by the API terms.

### Maps and terrain

OpenStreetMap attribution must remain visible and OSM tile-service usage policy must be respected. OpenTopoMap also requires visible attribution. USGS 3DEP terrain products are public-domain U.S. government data; retaining source provenance is recommended.

### Product name

This review did not perform a comprehensive trademark clearance for “Signal Peak.” Do a proper name/trademark search before broad promotion or commercial use.

## Security status

### API key persistence fixed

Older builds could persist the optional aprs.fi API key in ViewshedData/settings.json. Signal Peak 1.0.0 removes any saved aprs_fi_api_key and keeps it session-only.

### Build reproducibility

Runtime requirements mostly specify minimum versions. Before a final public binary:

- pin exact dependency versions and preferably hashes;
- retain a pip-freeze or SBOM manifest from the successful build;
- preserve required third-party notices;
- review known advisories for the pinned versions;
- consider pinning GitHub Actions to full commit SHAs.

### Windows binary provenance

The current PyInstaller executable is unsigned. Publish a SHA-256 checksum with each release and consider Authenticode signing when practical.

### Untrusted network data

The application consumes APRS packets, aprs.fi JSON, OSM/Overpass responses, map tiles, and USGS raster data. Continue validating coordinates, raster dimensions, file paths, and payload bounds, and do not execute remote text as shell commands.

### APRS-IS transport

The APRS-IS receive connection currently uses plaintext TCP port 14580. The app uses receive-only pass -1 rather than a secret APRS password, but APRS traffic should not be treated as confidential.

## Before public release

- [ ] Select a Signal Peak project license.
- [ ] Resolve the GPLv2 aprslib dependency strategy.
- [ ] Contact aprs.fi if the optional API integration will ship.
- [ ] Add aprs.fi credit when aprs.fi data is used.
- [ ] Pin exact Python release dependencies and retain hashes/manifest.
- [ ] Bundle required third-party notices.
- [ ] Review dependency advisories.
- [ ] Confirm OSM/OpenTopoMap usage and attribution for expected public traffic.
- [ ] Publish SHA-256 checksums.
- [ ] Consider code signing.
- [ ] Perform a trademark/name clearance search for Signal Peak.

If the goal is the fastest open-source release while retaining aprslib, a GPLv2-compatible distribution is the most straightforward path to evaluate. If the goal is MIT/BSD/Apache-style licensing or closed-source freeware, replace/remove aprslib first and rerun the license review.
