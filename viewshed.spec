# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = []
for package in ("itmlogic", "rasterio", "scipy", "pyproj", "PIL", "tkintermapview"):
    hiddenimports += collect_submodules(package)

datas = [
    ("LICENSE", "."),
    ("assets/signal-peak-icon.svg", "assets"),
    ("utah_stations_scraped.json", "."),
    ("utah_seed_stations.csv", "."),
    ("station_location_overrides.json", "."),
    ("README.md", "."),
    ("docs/CONUS.md", "docs"),
    ("docs/ROADMAP.md", "docs"),
    ("docs/QUICK_START.md", "docs"),
    ("docs/USER_GUIDE.md", "docs"),
    ("docs/PROPAGATION_MODEL.md", "docs"),
    ("docs/STATION_DATA.md", "docs"),
    ("docs/station-acquisition.md", "docs"),
    ("docs/LOCATION_CORRECTIONS.md", "docs"),
    ("docs/OUTPUTS.md", "docs"),
    ("docs/TROUBLESHOOTING.md", "docs"),
    ("docs/LICENSES_AND_DEPENDENCIES.md", "docs"),
    ("docs/RELEASE_READINESS_1.0.0.md", "docs"),
    ("docs/SPECIAL_CONSIDERATIONS.md", "docs"),
]
datas += collect_data_files("rasterio")

a = Analysis(
    ["viewshed_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + [
        "aprs_viewshed_utah_parallel",
        "map_workspace",
        "map_workspace_patch",
        "advanced_workspace",
        "repeat_run_workspace",
        "help_workspace",
        "osm_crossref",
        "seed_builder",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SignalPeak",
    icon="build/signal_peak.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    hide_console="hide-early",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
