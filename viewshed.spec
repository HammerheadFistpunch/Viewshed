# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = []
for package in ("itmlogic", "rasterio", "scipy", "pyproj", "PIL", "tkintermapview"):
    hiddenimports += collect_submodules(package)

datas = [
    ("utah_stations_scraped.json", "."),
    ("utah_seed_stations.csv", "."),
    ("station_location_overrides.json", "."),
]
datas += collect_data_files("rasterio")

a = Analysis(
    ["viewshed_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + ["aprs_viewshed_utah_parallel", "map_workspace"],
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
    name="Viewshed",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
