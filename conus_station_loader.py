from __future__ import annotations

import json
from collections import defaultdict


def install_conus_station_loader(engine) -> None:
    """Replace the legacy Utah-only station validator with geographic validation.

    The legacy RF module originally rejected any station outside a Utah-sized
    bounding box before the newer CONUS projection adapter ever got a chance
    to run.  This loader preserves the existing station filtering, coordinate
    overrides, seed warnings, and co-location behavior while accepting any
    valid WGS84 latitude/longitude.  Terrain/provider limits are handled later
    by the DEM stage rather than by a hidden Utah gate.
    """
    if getattr(engine, "_conus_station_loader_installed", False):
        return

    def load_stations(path: str, cfg: dict) -> tuple[list[dict], dict[str, str]]:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, list):
            raise ValueError("Station source must contain a JSON list.")

        raw = [s for s in raw if isinstance(s, dict) and s.get("type") in cfg["include_types"]]

        seed_only = [s for s in raw if s.get("_seed_only")]
        if seed_only:
            print(
                f"   ⚠  {len(seed_only)} station(s) have UNCONFIRMED seed coordinates "
                "(never heard on-air — position may be wrong):"
            )
            for s in seed_only:
                try:
                    print(
                        f"      {s['callsign']:<12} lat={float(s['lat']):.5f} "
                        f"lon={float(s['lon']):.5f}  ← seed-list only, not verified by live beacon"
                    )
                except Exception:
                    print(f"      {s.get('callsign', '?'):<12} invalid seed coordinates")
            print("      Tip: verify unconfirmed station positions before relying on the RF result.")

        overrides = cfg.get("coordinate_overrides", {})
        if overrides:
            for s in raw:
                call = s.get("callsign")
                if call not in overrides:
                    continue
                fix = overrides[call]
                old_lat, old_lon = s.get("lat"), s.get("lon")
                s["lat"] = fix["lat"]
                s["lon"] = fix["lon"]
                try:
                    print(
                        f"   📍 Coordinate override: {call} "
                        f"({float(old_lat):.5f}, {float(old_lon):.5f}) → "
                        f"({float(fix['lat']):.5f}, {float(fix['lon']):.5f})"
                    )
                except Exception:
                    print(f"   📍 Coordinate override applied: {call}")

        valid: list[dict] = []
        for station in raw:
            call = str(station.get("callsign") or "?")
            try:
                lat = float(station["lat"])
                lon = float(station["lon"])
            except (KeyError, TypeError, ValueError):
                print(f"   ⚠  Skipping {call} -- missing or invalid coordinates")
                continue

            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                print(f"   ⚠  Skipping {call} -- invalid WGS84 coordinates ({lat:.4f}, {lon:.4f})")
                continue

            station["lat"] = lat
            station["lon"] = lon
            valid.append(station)

        loc_groups: defaultdict[tuple[float, float], list[str]] = defaultdict(list)
        for station in valid:
            loc_key = (round(station["lat"], 4), round(station["lon"], 4))
            loc_groups[loc_key].append(station["callsign"])

        colocation_map: dict[str, str] = {}
        for members in loc_groups.values():
            canonical = sorted(members)[0]
            for member in members:
                colocation_map[member] = canonical

        shared_sites = {key: value for key, value in loc_groups.items() if len(value) > 1}
        if shared_sites:
            print(f"   Co-located station groups ({len(shared_sites)} sites):")
            for (lat, lon), members in sorted(shared_sites.items()):
                canonical = colocation_map[members[0]]
                aliases = [m for m in sorted(members) if m != canonical]
                print(
                    f"      {canonical} (canonical) + {', '.join(aliases)}"
                    f"  @ ({lat:.4f}, {lon:.4f})"
                )
            print("   Viewshed will be computed once per site and shared.")

        n_unique_sites = len(set(colocation_map.values()))
        print(
            f"   Loaded {len(valid)} stations "
            f"({len(shared_sites)} co-located sites, "
            f"{n_unique_sites} unique viewshed computations needed)."
        )
        return valid, colocation_map

    engine.load_stations = load_stations
    engine._conus_station_loader_installed = True
