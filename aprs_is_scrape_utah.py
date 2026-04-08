"""
aprs_is_scrape_utah.py  —  Utah APRS-IS 24-hour listener  (v4.2 - CSV & PHG Overrides + Sync)
=======================================================================
Listens to APRS-IS for 24 hours, collects digipeaters and I-gates
heard within the Utah bounding box, then writes a JSON file that
aprs_viewshed_utah_parallel.py can load directly.

Output file:  utah_stations_scraped.json

=======================================================================
NEW IN v4.2
=======================================================================
- SYNC BACK: High-confidence data (Consensus/API) is now written back 
             to the seed CSV at the end of the run.
- PROTECTED: Stations marked 'Override: Y' in CSV are never overwritten.
=======================================================================
"""

import os
import sys

# ── Auto-install aprslib if not present ───────────────────────────────────────
try:
    import aprslib
except ImportError:
    import subprocess
    print("aprslib not found — installing via pip...")

    def _pip_install(extra_args=()):
        cmd = [sys.executable, '-m', 'pip', 'install', 'aprslib'] + list(extra_args)
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return result.returncode == 0, result.stdout
        except Exception as exc:
            return False, str(exc)

    ok, out = _pip_install()
    if not ok:
        print("  Standard install failed, retrying with --user flag...")
        ok, out = _pip_install(['--user'])

    if ok:
        import site
        if hasattr(site, 'getusersitepackages'):
            user_site = site.getusersitepackages()
            if user_site not in sys.path:
                sys.path.insert(0, user_site)
        try:
            import aprslib
            print("aprslib installed successfully.")
        except ImportError:
            print("aprslib was installed but still cannot be imported.")
            print("Please restart the script, or run:  pip install aprslib")
            sys.exit(1)
    else:
        print("ERROR: Could not install aprslib automatically.")
        print("pip output:")
        for line in out.strip().splitlines():
            print(" ", line)
        sys.exit(1)

import json
import math
import time
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
import re
import csv

# ───────────────────────────────────────────────────────────────────────────────
# Logging — Tee mirrors every print() to both console and log file
# ───────────────────────────────────────────────────────────────────────────────

class _Tee:
    def __init__(self, log_path: str, console=None):
        self._console = (console
                         or sys.stdout
                         or sys.__stdout__
                         or open(os.devnull, 'w'))
        self._log     = open(log_path, 'w', encoding='utf-8', buffering=1)
        ts = datetime.now(tz=datetime.UTC if hasattr(datetime, "UTC")
                          else timezone.utc
                          ).strftime('%Y-%m-%d %H:%M:%S')
        self._log.write(f"Utah APRS-IS Scraper run log  |  started {ts} UTC\n")
        self._log.write("=" * 65 + "\n\n")

    def write(self, text: str):
        self._console.write(text)
        self._log.write(text)

    def flush(self):
        self._console.flush()
        self._log.flush()

    def close(self):
        self._log.flush()
        self._log.close()

    def fileno(self):
        try:
            return self._console.fileno()
        except Exception:
            return -1

    def isatty(self):
        try:
            return self._console.isatty()
        except Exception:
            return False

_tee: "_Tee | None" = None


# ───────────────────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────────────────

CALLSIGN = "Ki7nnk"                # ← your callsign (e.g. "W7XYZ")
PASSCODE = "16814"                 # ← aprslib.passcode("W7XYZ"), or -1 for RX-only
APRSDOTFI_API_KEY = "143845.TFc6FRsMdRQMLR" # ← e.g. "XXXX.XXXXXXXXXXXXX"

APRS_HOST = "rotate.aprs2.net"
APRS_PORT = 14580

UTAH_LAT_MIN =  37.0
UTAH_LAT_MAX =  42.0
UTAH_LON_MIN = -114.05
UTAH_LON_MAX = -109.05

UTAH_FILTER = (f"a/{UTAH_LAT_MAX + 0.5}/{UTAH_LON_MIN - 0.5}"
               f"/{UTAH_LAT_MIN - 0.5}/{UTAH_LON_MAX + 0.5}")

LISTEN_HOURS   = 24
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE    = os.path.join(BASE_DIR, 'utah_stations_scraped.json')
LOG_FILE       = os.path.join(BASE_DIR, 'scraper_run.log')
SEED_CSV_FILE  = os.path.join(BASE_DIR, 'utah_seed_stations.csv')
PROGRESS_EVERY = 300

CONSENSUS_RADIUS_M  = 500
CONSENSUS_MIN_COUNT = 3
APRSDOTFI_MAX_AGE_DAYS = 90
APRSDOTFI_BATCH_SIZE = 20

# ───────────────────────────────────────────────────────────────────────────────
# Position confidence levels
# ───────────────────────────────────────────────────────────────────────────────
CONF_NONE      = 0   
CONF_SEED      = 1   
CONF_OBJ_ITEM  = 2   
CONF_ANY_BCN   = 3   
CONF_SYM_BCN   = 4   
CONF_CONSENSUS = 5  
CONF_MANUAL    = 99  

# ───────────────────────────────────────────────────────────────────────────────
# Static seed list — fallback generation data
# ───────────────────────────────────────────────────────────────────────────────
UTAH_BACKBONE_SEEDS_FALLBACK = [
    {"callsign": "UTAH",    "lat": 37.5617,  "lon": -113.8108, "type": "digi", "comment": "Utah Hill 7,697ft W7ZDL"},
    {"callsign": "SANDFL",  "lat": 38.5680,  "lon": -109.5113, "type": "digi", "comment": "Sand Flats near Moab"},
    {"callsign": "ABAJO",   "lat": 37.8322,  "lon": -109.4636, "type": "digi", "comment": "Abajo Peak 11,360ft SE Utah"},
    {"callsign": "BALD",    "lat": 40.6650,  "lon": -110.9017, "type": "digi", "comment": "Bald Mountain 11,943ft Uintas"},
    {"callsign": "SCOTTS",  "lat": 40.62277, "lon": -111.56863, "type": "digi", "comment": "Scott's Hill UARC/SLC"},
    {"callsign": "FARNSWT", "lat": 40.7717,  "lon": -112.1972, "type": "digi", "comment": "Farnsworth Peak 9,052ft WB7EED"},
    {"callsign": "ENSIGN",  "lat": 40.7913,  "lon": -111.8994, "type": "digi", "comment": "Ensign Peak SLC N7IVU"},
    {"callsign": "CEDAR",   "lat": 37.6906,  "lon": -113.0789, "type": "digi", "comment": "Cedar Mountain"},
    {"callsign": "BUCKSKN", "lat": 37.9081,  "lon": -110.5900, "type": "digi", "comment": "Buckskin Mesa SE Utah"},
    {"callsign": "BLOW",    "lat": 37.7408,  "lon": -113.0117, "type": "digi", "comment": "Blowhard Mtn 10,000ft K7RB Cedar City area"},
    {"callsign": "BLOWH",   "lat": 37.7408,  "lon": -113.0117, "type": "digi", "comment": "Blowhard Mtn 10,000ft K7RB (alternate callsign)"},
    {"callsign": "BOULDR",  "lat": 37.9550,  "lon": -111.4600, "type": "digi", "comment": "Boulder Mountain ~11,000ft Wayne County"},
    {"callsign": "GOOSBN",  "lat": 37.2400,  "lon": -113.3000, "type": "digi", "comment": "Gooseberry Mesa Washington County"},
    {"callsign": "MILFOR",  "lat": 38.4300,  "lon": -113.0100, "type": "digi", "comment": "Milford Flat Beaver County"},
    {"callsign": "BRYCE",   "lat": 37.6431,  "lon": -112.1669, "type": "digi", "comment": "Bryce Canyon area"},
    {"callsign": "MONTIC",  "lat": 37.8717,  "lon": -109.3411, "type": "digi", "comment": "Monticello San Juan County"},
    {"callsign": "PRICE",   "lat": 39.5986,  "lon": -110.8106, "type": "digi", "comment": "Price Carbon County"},
    {"callsign": "ELBW",    "lat": 38.3900,  "lon": -109.9700, "type": "digi", "comment": "Elbow digi SE Utah — verify on aprs.fi"},
    {"callsign": "W7ZDL-3", "lat": 37.5617,  "lon": -113.8108, "type": "digi", "comment": "Utah Hill (co-located with UTAH)"},
    {"callsign": "WB7EED-3","lat": 41.7281,  "lon": -111.8369, "type": "digi", "comment": "Logan Peak 9,710ft Cache County"},
    {"callsign": "N0NHJ-3", "lat": 38.5680,  "lon": -109.5113, "type": "digi", "comment": "Sand Flats / Moab (co-located with SANDFL)"},
    {"callsign": "K7RB-3",  "lat": 37.7408,  "lon": -113.0117, "type": "digi", "comment": "Blowhard Mountain (co-located with BLOW)"},
    {"callsign": "W7YDD-3", "lat": 40.7717,  "lon": -112.1972, "type": "digi", "comment": "Farnsworth Peak linked digi"},
    {"callsign": "K7UDM-3", "lat": 40.6650,  "lon": -110.9017, "type": "digi", "comment": "Bald Mountain linked digi"},
    {"callsign": "N7IVU-3", "lat": 40.7913,  "lon": -111.8994, "type": "digi", "comment": "Ensign Peak linked digi"},
    {"callsign": "W7ZDL-7", "lat": 37.5617,  "lon": -113.8108, "type": "igate","comment": "Utah Hill igate (co-located with UTAH / W7ZDL-3)"},
    {"callsign": "WB7EED-7","lat": 41.7281,  "lon": -111.8369, "type": "igate","comment": "Logan Peak igate (co-located with WB7EED-3)"},
]

def load_or_create_seed_csv() -> list:
    """Reads seeds from CSV. Creates the CSV template if it doesn't exist."""
    headers = ['Callsign', 'Lat', 'Lon', 'Type', 'Comment', 'Override', 'Power_W', 'Height_ft', 'Gain_dBd', 'Dir_deg']
    
    if not os.path.exists(SEED_CSV_FILE):
        print(f"  [CSV ] Creating default seed template: {SEED_CSV_FILE}")
        with open(SEED_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for s in UTAH_BACKBONE_SEEDS_FALLBACK:
                writer.writerow([s['callsign'], s['lat'], s['lon'], s['type'], s['comment'], 'N', '', '', '', ''])
    
    seeds = []
    with open(SEED_CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            call = row.get('Callsign', '').strip()
            if not call: continue
            try:
                lat = float(row.get('Lat', 0))
                lon = float(row.get('Lon', 0))
            except ValueError:
                print(f"  [CSV ] Invalid coordinates for {call} - skipping")
                continue
            
            stype = row.get('Type', 'digi').strip().lower()
            comment = row.get('Comment', '').strip()
            override_str = row.get('Override', 'N').strip().upper()
            override = True if override_str in ('Y', 'YES', 'TRUE', '1') else False
            
            p_w   = row.get('Power_W', '').strip()
            h_ft  = row.get('Height_ft', '').strip()
            g_dbd = row.get('Gain_dBd', '').strip()
            d_deg = row.get('Dir_deg', '').strip()

            seed_data = {
                'callsign': call,
                'lat': lat,
                'lon': lon,
                'type': stype,
                'comment': comment,
                '_override': override
            }

            if p_w and h_ft and g_dbd:
                try:
                    seed_data['phg_power_w']   = int(p_w)
                    seed_data['phg_height_ft'] = int(h_ft)
                    seed_data['phg_height_m']  = round(int(h_ft) * 0.3048, 1)
                    seed_data['phg_gain_dbd']  = int(g_dbd)
                    seed_data['phg_gain_dbi']  = round(int(g_dbd) + 2.15, 2)
                    seed_data['phg_directivity'] = int(d_deg) if d_deg else None
                    seed_data['phg_raw'] = 'MANUAL'
                except ValueError:
                    print(f"  [CSV ] Invalid PHG data format for {call} - skipping PHG injection")

            seeds.append(seed_data)
    return seeds


# ───────────────────────────────────────────────────────────────────────────────
# CSV Sync Logic
# ───────────────────────────────────────────────────────────────────────────────
def sync_to_seed_csv():
    """Updates the input CSV with improved data found during the run."""
    if not os.path.exists(SEED_CSV_FILE):
        return

    updated_rows = []
    sync_count = 0
    
    with open(SEED_CSV_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    with lock:
        for row in rows:
            call = row.get('Callsign', '').strip()
            override_str = row.get('Override', 'N').strip().upper()
            override = True if override_str in ('Y', 'YES', 'TRUE', '1') else False
            
            if override or call not in stations:
                updated_rows.append(row)
                continue
            
            s = stations[call]
            if s.get('_pos_conf', CONF_NONE) >= CONF_ANY_BCN:
                row['Lat'] = f"{s['lat']:.6f}"
                row['Lon'] = f"{s['lon']:.6f}"
                
                if 'phg_power_w' in s:
                    row['Power_W']   = str(s['phg_power_w'])
                    row['Height_ft'] = str(s['phg_height_ft'])
                    row['Gain_dBd']  = str(s['phg_gain_dbd'])
                    row['Dir_deg']   = str(s.get('phg_directivity', '') or '')
                
                sync_count += 1
            
            updated_rows.append(row)

    with open(SEED_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    print(f"  [SYNC ] Updated {sync_count} stations in '{os.path.basename(SEED_CSV_FILE)}' with live data.")

# ───────────────────────────────────────────────────────────────────────────────
# Routing alias detection
# ───────────────────────────────────────────────────────────────────────────────

_ROUTING_BLACKLIST = frozenset({
    'WIDE', 'RELAY', 'TRACE', 'ECHO', 'TEMP',
    'ARISS', 'RS0ISS', 'PCSAT', 'APRSAT',
    'TCPIP', 'TCPXX', 'NOGATE', 'RFONLY', 'IGATECALL',
    'LOCAL', 'NET', 'SGATE', 'CWOP', 'GATE',
})

def is_routing_alias(token: str) -> bool:
    base = token.upper().split('-')[0]
    if base in _ROUTING_BLACKLIST:
        return True
    if base and base[-1].isdigit():
        return True
    return False

# ───────────────────────────────────────────────────────────────────────────────
# Station ID validation
# ───────────────────────────────────────────────────────────────────────────────

_CALLSIGN_RE    = re.compile(r'^[A-Z0-9]{1,3}[0-9][A-Z]{1,4}(-[A-Z0-9]{1,3})?$', re.IGNORECASE)
_Q_CONSTRUCT_RE = re.compile(r'^q[A-Z]{1,2}$', re.IGNORECASE)

def is_valid_callsign(call: str) -> bool:
    if not call or is_routing_alias(call) or _Q_CONSTRUCT_RE.match(call):
        return False
    return bool(_CALLSIGN_RE.match(call))

def is_valid_station_id(call: str) -> bool:
    if not call or is_routing_alias(call) or _Q_CONSTRUCT_RE.match(call):
        return False
    base = call.upper().split('-')[0]
    if is_valid_callsign(call):
        return True
    if re.match(r'^[A-Z][A-Z0-9]{2,8}$', base):
        return True
    return False

def in_utah(lat: float, lon: float) -> bool:
    return (UTAH_LAT_MIN - 0.5 <= lat <= UTAH_LAT_MAX + 0.5 and
            UTAH_LON_MIN - 0.5 <= lon <= UTAH_LON_MAX + 0.5)

IGATE_Q_SET = frozenset({'qAR', 'qAO', 'qAr', 'qAo'})

def _is_digi_symbol(sym: str) -> bool:
    return sym == '#'

def _is_igate_symbol(sym: str) -> bool:
    return sym == '&'

# ───────────────────────────────────────────────────────────────────────────────
# PHG / RNG / DFS data extraction (v3.1 Fixes applied)
# ───────────────────────────────────────────────────────────────────────────────

_PHG_RE = re.compile(r'\bPHG([0-9])([0-9])([0-9])([0-8])', re.ASCII | re.IGNORECASE)
_RNG_RE = re.compile(r'\bRNG(\d{4})\b',                     re.ASCII | re.IGNORECASE)
_DFS_RE = re.compile(r'\bDFS([0-9])([0-9])([0-9])([0-8])', re.ASCII | re.IGNORECASE)

_PHG_POWER_W  = [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
_PHG_HEIGHT_FT = [10 * (2**h) for h in range(10)]

def parse_phg(comment: str) -> dict:
    result = {}
    clean_comment = re.sub(r'[^\x20-\x7E]', '', comment)
    m = _PHG_RE.search(clean_comment)
    if m:
        p, h, g, d = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        height_ft = _PHG_HEIGHT_FT[h]
        result['phg_raw']         = 'PHG' + m.group(1) + m.group(2) + m.group(3) + m.group(4)
        result['phg_power_w']     = _PHG_POWER_W[p]
        result['phg_height_ft']   = height_ft
        result['phg_height_m']    = round(height_ft * 0.3048, 1)
        result['phg_gain_dbd']    = g
        result['phg_gain_dbi']    = round(g + 2.15, 2)
        result['phg_directivity'] = None if d == 0 else d * 45
    return result

def parse_rng(comment: str) -> dict:
    result = {}
    clean_comment = re.sub(r'[^\x20-\x7E]', '', comment)
    m = _RNG_RE.search(clean_comment)
    if m:
        miles = int(m.group(1))
        result['rng_miles'] = miles
        result['rng_km']    = round(miles * 1.60934, 1)
    return result

def parse_dfs(comment: str) -> dict:
    result = {}
    clean_comment = re.sub(r'[^\x20-\x7E]', '', comment)
    m = _DFS_RE.search(clean_comment)
    if m:
        s, h, g, d = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        result['dfs_raw']         = 'DFS' + m.group(1) + m.group(2) + m.group(3) + m.group(4)
        result['dfs_signal']      = s 
        result['dfs_height_ft']   = _PHG_HEIGHT_FT[h]
        result['dfs_height_m']    = round(_PHG_HEIGHT_FT[h] * 0.3048, 1)
        result['dfs_gain_dbd']    = g
        result['dfs_directivity'] = None if d == 0 else d * 45
    return result

# ───────────────────────────────────────────────────────────────────────────────
# Core path extraction 
# ───────────────────────────────────────────────────────────────────────────────

def extract_digis_and_igate(path_raw) -> tuple:
    if isinstance(path_raw, str):
        tokens = [t.strip() for t in path_raw.split(',') if t.strip()]
    elif path_raw:
        tokens = list(path_raw)
    else:
        return [], None

    q_idx = next((i for i, t in enumerate(tokens)
                  if len(t) >= 3 and t[0] == 'q' and t[1].isupper()), len(tokens))
    rf_path = tokens[:q_idx]

    igate = None
    if q_idx < len(tokens):
        q_tok = tokens[q_idx]
        if q_tok in IGATE_Q_SET and q_idx + 1 < len(tokens):
            candidate = tokens[q_idx + 1]
            if is_valid_station_id(candidate):
                igate = candidate

    digis = []
    if rf_path:
        last_star = max((i for i, t in enumerate(rf_path) if t.endswith('*')), default=-1)
        if last_star >= 0:
            for raw in rf_path[:last_star + 1]:
                base = raw.rstrip('*')
                if not base or is_routing_alias(base):
                    continue
                if is_valid_station_id(base):
                    digis.append(base)

    return digis, igate

# ───────────────────────────────────────────────────────────────────────────────
# Packet classification
# ───────────────────────────────────────────────────────────────────────────────

def classify_packet(packet: dict) -> list:
    path    = packet.get('path', [])
    sym     = packet.get('symbol', '')  or ''
    lat     = packet.get('latitude')
    lon     = packet.get('longitude')
    call    = packet.get('from', '')    or ''
    comment = packet.get('comment', '') or ''
    fmt     = packet.get('format', '')  or ''

    results = []
    digi_calls, igate_call = extract_digis_and_igate(path)
    for dc in digi_calls:
        results.append(('digi', dc, None, None, '', CONF_NONE))
    if igate_call:
        results.append(('igate', igate_call, None, None, '', CONF_NONE))

    if lat is not None and lon is not None and call and is_valid_station_id(call):
        if _is_digi_symbol(sym):
            results.append(('digi',  call, lat, lon, comment, CONF_SYM_BCN))
        elif _is_igate_symbol(sym):
            results.append(('igate', call, lat, lon, comment, CONF_SYM_BCN))

    if fmt in ('object', 'item'):
        obj_name = (packet.get('object_name') or packet.get('item_name') or '').strip()
        obj_lat  = packet.get('latitude')
        obj_lon  = packet.get('longitude')
        obj_sym  = packet.get('symbol', '') or ''
        obj_cmt  = packet.get('comment', '') or ''
        if obj_name and obj_lat is not None and obj_lon is not None:
            if is_valid_station_id(obj_name):
                if _is_digi_symbol(obj_sym):
                    results.append(('digi',  obj_name, obj_lat, obj_lon, obj_cmt, CONF_OBJ_ITEM))
                elif _is_igate_symbol(obj_sym):
                    results.append(('igate', obj_name, obj_lat, obj_lon, obj_cmt, CONF_OBJ_ITEM))

    return results

# ───────────────────────────────────────────────────────────────────────────────
# Station registry
# ───────────────────────────────────────────────────────────────────────────────

stations     = {}
lock         = threading.Lock()
start_time   = None
stop_event   = threading.Event()
packet_count = 0
error_count  = 0


def update_station(stype: str, callsign: str,
                   lat, lon, comment: str, conf: int,
                   altitude_m=None, symbol=None, symbol_table=None):
    if not callsign:
        return
    now_str = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    phg_data = parse_phg(comment) if comment else {}
    rng_data = parse_rng(comment) if comment else {}
    dfs_data = parse_dfs(comment) if comment else {}

    with lock:
        existing = stations.get(callsign)
        if existing is None:
            rec = {
                'callsign':    callsign,
                'lat':         lat,
                'lon':         lon,
                'type':        stype,
                'comment':     comment,
                'first_seen':  now_str,
                'lasttime':    now_str,
                '_heard':      1,
                '_pos_conf':   conf if lat is not None else CONF_NONE,
                '_seeded':     False,
                '_pos_history': ([{'lat': lat, 'lon': lon, 'conf': conf, 'time': now_str}]
                                  if lat is not None and conf >= CONF_ANY_BCN else []),
            }
            if altitude_m is not None:
                rec['altitude_m'] = round(altitude_m, 1)
                rec['altitude_ft'] = round(altitude_m * 3.28084, 0)
            if symbol is not None:
                rec['symbol']       = symbol
            if symbol_table is not None:
                rec['symbol_table'] = symbol_table
            rec.update(phg_data)
            rec.update(rng_data)
            rec.update(dfs_data)
            stations[callsign] = rec

            if lat is not None:
                phg_str = (f"  PHG={phg_data.get('phg_raw','')} "
                           f"{phg_data.get('phg_power_w','')}W "
                           f"{phg_data.get('phg_height_ft','')}ft "
                           f"{phg_data.get('phg_gain_dbd','')}dBd"
                           if phg_data else "")
                print(f"  [NEW  {stype.upper():5s}] {callsign:12s}  "
                      f"lat={lat:.4f} lon={lon:.4f}  (conf={conf}){phg_str}")
            else:
                print(f"  [NEW  {stype.upper():5s}] {callsign:12s}  (no position yet)")
            return

        existing['lasttime'] = now_str
        existing['_heard']  += 1

        if conf == CONF_SYM_BCN and existing['type'] != stype and existing.get('_pos_conf') != CONF_MANUAL:
            print(f"  [TYPE ] {callsign:12s}  {existing['type']} -> {stype}  (symbol beacon)")
            existing['type'] = stype

        if lat is not None and lon is not None:
            cur_conf = existing.get('_pos_conf', CONF_NONE)
            if conf >= cur_conf:
                if existing.get('lat') is None:
                    print(f"  [POS  {stype.upper():5s}] {callsign:12s}  lat={lat:.4f} lon={lon:.4f}  (conf={conf})")
                elif conf > cur_conf:
                    print(f"  [UPDT {stype.upper():5s}] {callsign:12s}  lat={lat:.4f} lon={lon:.4f}  (conf {cur_conf}->{conf})")
                existing['lat']       = lat
                existing['lon']       = lon
                existing['_pos_conf'] = conf

        if altitude_m is not None:
            if conf >= existing.get('_pos_conf', CONF_NONE) or 'altitude_m' not in existing:
                existing['altitude_m']  = round(altitude_m, 1)
                existing['altitude_ft'] = round(altitude_m * 3.28084, 0)

        if symbol is not None and conf >= CONF_ANY_BCN:
            existing['symbol'] = symbol
        if symbol_table is not None and conf >= CONF_ANY_BCN:
            existing['symbol_table'] = symbol_table

        if comment:
            if not existing.get('comment'):
                existing['comment'] = comment
            elif conf >= CONF_SYM_BCN and existing.get('_pos_conf') != CONF_MANUAL:
                existing['comment'] = comment

        if phg_data and (conf >= existing.get('_pos_conf', CONF_NONE) or 'phg_raw' not in existing):
            if not (existing.get('_pos_conf') == CONF_MANUAL and existing.get('phg_raw') == 'MANUAL'):
                existing.update(phg_data)
                if conf >= CONF_ANY_BCN:
                    print(f"  [PHG  ] {callsign:12s}  power={phg_data.get('phg_power_w')}W  "
                          f"height={phg_data.get('phg_height_ft')}ft  gain={phg_data.get('phg_gain_dbd')}dBd  "
                          f"dir={phg_data.get('phg_directivity') or 'omni'}")

        if rng_data and rng_data.get('rng_miles', 0) >= existing.get('rng_miles', 0):
            existing.update(rng_data)

        if dfs_data and 'dfs_raw' not in existing:
            existing.update(dfs_data)

        if lat is not None and lon is not None and conf >= CONF_ANY_BCN:
            existing.setdefault('_pos_history', []).append({
                'lat': lat, 'lon': lon, 'conf': conf, 'time': now_str,
            })

def process_packet(packet: dict):
    global packet_count, error_count
    packet_count += 1
    try:
        entries = classify_packet(packet)
        pkt_alt      = packet.get('altitude')
        pkt_symbol   = packet.get('symbol') or None
        pkt_sym_tbl  = packet.get('symbol_table') or None
        from_call    = packet.get('from', '') or ''
        pkt_lat      = packet.get('latitude')
        pkt_lon      = packet.get('longitude')

        for stype, call, lat, lon, comment, conf in entries:
            if call == from_call and lat is not None:
                update_station(stype, call, lat, lon, comment, conf,
                               altitude_m=pkt_alt, symbol=pkt_symbol, symbol_table=pkt_sym_tbl)
            else:
                update_station(stype, call, lat, lon, comment, conf)

        if from_call and pkt_lat is not None and pkt_lon is not None:
            with lock:
                existing = stations.get(from_call)
            if existing is not None and existing.get('_pos_conf', CONF_NONE) == CONF_NONE:
                update_station(existing['type'], from_call, pkt_lat, pkt_lon,
                               packet.get('comment', '') or '', CONF_ANY_BCN,
                               altitude_m=pkt_alt, symbol=pkt_symbol, symbol_table=pkt_sym_tbl)
    except Exception as exc:
        error_count += 1
        if error_count <= 20 or error_count % 500 == 0:
            call_str = packet.get('from', '?') if isinstance(packet, dict) else '?'
            print(f"  [ERR ] pkt from {call_str}: {exc}")

# ───────────────────────────────────────────────────────────────────────────────
# Seed and save
# ───────────────────────────────────────────────────────────────────────────────

def seed_backbone():
    """Pre-populate the station dict from CSV (auto-generated if missing)."""
    now_str = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    seeds = load_or_create_seed_csv()
    count = 0
    locked = 0
    with lock:
        for s in seeds:
            if s['callsign'] not in stations:
                conf = CONF_MANUAL if s['_override'] else CONF_SEED
                rec = {
                    'callsign':  s['callsign'],
                    'lat':       s['lat'],
                    'lon':       s['lon'],
                    'type':      s['type'],
                    'comment':   s['comment'],
                    'first_seen': now_str,
                    'lasttime':  now_str,
                    '_heard':    0,
                    '_pos_conf': conf,
                    '_seeded':   True,
                }
                
                for key in ('phg_raw', 'phg_power_w', 'phg_height_ft', 'phg_height_m', 'phg_gain_dbd', 'phg_gain_dbi', 'phg_directivity'):
                    if key in s:
                        rec[key] = s[key]

                stations[s['callsign']] = rec
                count += 1
                if s['_override']:
                    locked += 1
    print(f"  [SEED] Loaded {count} stations from CSV ({locked} manually locked)")

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def apply_position_consensus(verbose: bool = False):
    promoted = 0
    flagged  = 0
    with lock:
        for s in stations.values():
            if s.get('_pos_conf', CONF_NONE) == CONF_MANUAL:
                continue

            history = s.get('_pos_history', [])
            if len(history) < CONSENSUS_MIN_COUNT:
                continue

            lats = [h['lat'] for h in history]
            lons = [h['lon'] for h in history]

            med_lat = sum(lats) / len(lats)
            med_lon = sum(lons) / len(lons)
            for _ in range(20):
                weights = []
                for la, lo in zip(lats, lons):
                    d = _haversine_m(med_lat, med_lon, la, lo)
                    weights.append(1.0 / max(d, 1.0))
                tw = sum(weights)
                med_lat = sum(w*la for w, la in zip(weights, lats)) / tw
                med_lon = sum(w*lo for w, lo in zip(weights, lons)) / tw

            inliers  = [(la, lo) for la, lo in zip(lats, lons)
                        if _haversine_m(med_lat, med_lon, la, lo) <= CONSENSUS_RADIUS_M]
            outliers = len(history) - len(inliers)

            if len(inliers) < CONSENSUS_MIN_COUNT:
                if outliers > 0:
                    flagged += 1
                    if verbose:
                        print(f"  [CNSNS] {s['callsign']:<12} SCATTERED positions "
                              f"({len(history)} reports, {outliers} outliers) "
                              f"— keeping current conf={s['_pos_conf']}")
                continue

            c_lat = sum(la for la, lo in inliers) / len(inliers)
            c_lon = sum(lo for la, lo in inliers) / len(inliers)
            variance_m = max(_haversine_m(c_lat, c_lon, la, lo) for la, lo in inliers)

            prev_conf = s.get('_pos_conf', CONF_NONE)
            old_lat, old_lon = s.get('lat'), s.get('lon')
            shift_m = (_haversine_m(old_lat, old_lon, c_lat, c_lon) if old_lat is not None else 0.0)

            s['lat']            = c_lat
            s['lon']            = c_lon
            s['_pos_conf']      = CONF_CONSENSUS
            s['_pos_variance_m'] = round(variance_m, 1)

            promoted += 1
            shift_str = f"  shift={shift_m:.0f}m" if shift_m > 10 else ""
            outlier_str = f"  outliers={outliers}" if outliers else ""
            if verbose:
                print(f"  [CNSNS] {s['callsign']:<12} consensus from {len(inliers)} "
                      f"reports  variance={variance_m:.0f}m{shift_str}{outlier_str}")

    if verbose or promoted or flagged:
        print(f"  [CNSNS] Promoted {promoted} station(s) to CONF_CONSENSUS ({flagged} scattered/flagged)")

def verify_seeds_via_aprsdotfi():
    if not APRSDOTFI_API_KEY:
        print("  [APRSFI] No API key set — skipping seed verification.")
        return

    with lock:
        to_check = [dict(s) for s in stations.values() if s.get('_pos_conf', CONF_NONE) <= CONF_SEED]

    if not to_check:
        print("  [APRSFI] All stations already have confirmed/locked positions — nothing to verify.")
        return

    n_seed = sum(1 for s in to_check if s.get('_pos_conf', CONF_NONE) == CONF_SEED)
    n_none = sum(1 for s in to_check if s.get('_pos_conf', CONF_NONE) == CONF_NONE)
    print(f"  [APRSFI] Verifying {len(to_check)} stations via aprs.fi API "
          f"(seed-only={n_seed}, path-heard-no-pos={n_none})...")

    cutoff  = (datetime.now(tz=timezone.utc).timestamp() - APRSDOTFI_MAX_AGE_DAYS * 86400)
    updated = 0
    failed  = 0
    snap = {s['callsign']: s for s in to_check}
    callsigns = list(snap.keys())

    for batch_start in range(0, len(callsigns), APRSDOTFI_BATCH_SIZE):
        batch = callsigns[batch_start:batch_start + APRSDOTFI_BATCH_SIZE]
        try:
            params = urllib.parse.urlencode({'name': ','.join(batch), 'what': 'loc', 'apikey': APRSDOTFI_API_KEY, 'format': 'json'})
            with urllib.request.urlopen(f"https://api.aprs.fi/api/get?{params}", timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            print(f"  [APRSFI] Batch request failed: {exc}")
            failed += len(batch)
            time.sleep(2)
            continue

        if data.get('result') != 'ok':
            failed += len(batch)
            time.sleep(1)
            continue

        found_map = {entry.get('name', '').upper().strip(): entry for entry in data.get('entries', []) if entry.get('name', '').upper().strip()}

        for callsign in batch:
            entry = found_map.get(callsign.upper())
            if entry is None:
                failed += 1
                continue

            fi_lat  = float(entry.get('lat', 0))
            fi_lon  = float(entry.get('lng', 0))
            fi_time = int(entry.get('lasttime', 0))

            if fi_time < cutoff or not in_utah(fi_lat, fi_lon):
                failed += 1
                continue

            s_snap    = snap[callsign]
            seed_lat  = s_snap.get('lat')
            seed_lon  = s_snap.get('lon')
            prev_conf = s_snap.get('_pos_conf', CONF_NONE)
            dist_m = _haversine_m(seed_lat, seed_lon, fi_lat, fi_lon) if seed_lat is not None else None

            with lock:
                station = stations.get(callsign)
                if station is None: continue
                if CONF_ANY_BCN >= station.get('_pos_conf', CONF_NONE):
                    station['lat'] = fi_lat
                    station['lon'] = fi_lon
                    station['_pos_conf'] = CONF_ANY_BCN

            updated += 1
            if prev_conf == CONF_NONE:
                print(f"  [APRSFI] {callsign:<12} NEW position from aprs.fi ({fi_lat:.4f},{fi_lon:.4f})")
            elif dist_m is not None and dist_m > 100:
                print(f"  [APRSFI] {callsign:<12} CORRECTED seed by {dist_m:.0f}m")

        time.sleep(1)

    print(f"  [APRSFI] Verification done: {updated} updated/confirmed, {failed} failed/skipped")

def save_results(final: bool = False):
    with lock:
        out = []
        skipped = 0
        for s in stations.values():
            if s.get('lat') is None or s.get('lon') is None or not in_utah(s['lat'], s['lon']):
                skipped += 1
                continue
            pos_conf = s.get('_pos_conf', 0)
            entry = {
                'callsign':   s['callsign'],
                'lat':        round(s['lat'], 6),
                'lon':        round(s['lon'], 6),
                'type':       s['type'],
                'comment':    s.get('comment', ''),
                'first_seen': s.get('first_seen', ''),
                'lasttime':   s['lasttime'],
                '_pos_conf':  pos_conf,
                '_heard':     s.get('_heard', 0),
                '_seed_only': (s.get('_seeded', False) and pos_conf <= CONF_SEED),
            }
            if pos_conf == CONF_MANUAL:
                entry['_manual_override'] = True

            if '_pos_variance_m' in s: entry['_pos_variance_m'] = s['_pos_variance_m']
            if 'altitude_m' in s:
                entry['altitude_m'] = s['altitude_m']
                entry['altitude_ft'] = s.get('altitude_ft')
            if 'symbol' in s: entry['symbol'] = s['symbol']
            if 'symbol_table' in s: entry['symbol_table'] = s['symbol_table']

            for key in ('phg_raw', 'phg_power_w', 'phg_height_ft', 'phg_height_m', 'phg_gain_dbd', 'phg_gain_dbi', 'phg_directivity',
                        'rng_miles', 'rng_km', 'dfs_raw', 'dfs_signal', 'dfs_height_ft', 'dfs_height_m', 'dfs_gain_dbd', 'dfs_directivity'):
                if key in s: entry[key] = s[key]

            out.append(entry)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(out, f, indent=2)

    label = "FINAL" if final else "checkpoint"
    print(f"\n  [{label}] {len(out)} positioned stations saved ({skipped} skipped — no position / outside Utah)\n")

def progress_reporter():
    while not stop_event.wait(timeout=PROGRESS_EVERY):
        elapsed   = timedelta(seconds=int(time.time() - start_time))
        remaining = timedelta(hours=LISTEN_HOURS) - elapsed
        with lock:
            nd     = sum(1 for s in stations.values() if s['type'] == 'digi')
            ni     = sum(1 for s in stations.values() if s['type'] == 'igate')
            no_pos = sum(1 for s in stations.values() if s.get('_pos_conf', 0) == CONF_NONE)
        print(f"  [STATUS] elapsed={elapsed}  remaining={remaining}  pkts={packet_count}  err={error_count}  digis={nd}  igates={ni}  awaiting_pos={no_pos}")
        apply_position_consensus()
        verify_seeds_via_aprsdotfi()
        save_results()

# ───────────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────────

def main():
    global start_time, _tee
    start_time = time.time()
    deadline   = start_time + LISTEN_HOURS * 3600

    _tee = _Tee(LOG_FILE, console=sys.stdout)
    sys.stdout = _tee

    print("=" * 65)
    print("  Utah APRS-IS Scraper  --  24-hour listener  (v4.2)")
    print("=" * 65)

    missing = []
    if CALLSIGN in ("N0CALL", "", None): missing.append("  CALLSIGN  — set to your callsign (e.g. 'W7XYZ')")
    if APRSDOTFI_API_KEY is None: missing.append("  APRSDOTFI_API_KEY — required to verify seed coordinates")
    
    if missing:
        print("  ⚠  CONFIGURATION INCOMPLETE — edit the top of this file:")
        for m in missing: print(m)
        if APRSDOTFI_API_KEY is None:
            ans = input("\n  Continue anyway? [y/N] ").strip().lower()
            if ans != 'y':
                return
        print()
        
    print(f"  Filter  : {UTAH_FILTER}")
    print(f"  Output  : {OUTPUT_FILE}")
    print(f"  CSV File: {SEED_CSV_FILE}")
    print(f"  Started : {datetime.now(tz=timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    print(f"  Ends at : {datetime.now(tz=timezone.utc) + timedelta(hours=LISTEN_HOURS):%Y-%m-%d %H:%M:%S} UTC")
    print("  Ctrl+C to stop early and save partial results.")
    print("=" * 65 + "\n")

    seed_backbone()

    reporter = threading.Thread(target=progress_reporter, daemon=True)
    reporter.start()

    while time.time() < deadline and not stop_event.is_set():
        AIS = aprslib.IS(CALLSIGN, PASSCODE, host=APRS_HOST, port=APRS_PORT)
        AIS.set_filter(UTAH_FILTER)
        try:
            print("  Connecting to APRS-IS...")
            AIS.connect()
            print("  Connected.  Listening...\n")
            def _consumer():
                def _cb(pkt):
                    if time.time() >= deadline or stop_event.is_set(): raise KeyboardInterrupt
                    process_packet(pkt)
                AIS.consumer(_cb, raw=False)
            _consumer()
        except KeyboardInterrupt:
            stop_event.set()
            break
        except Exception as e:
            if stop_event.is_set(): break
            print(f"  Connection error: {e}  -- reconnecting in 30 s...")
            time.sleep(30)
        finally:
            try: AIS.close()
            except Exception: pass

    stop_event.set()
    print("\n" + "=" * 65)
    print("  Scraping finished.")

    print("  Running position consensus analysis...")
    apply_position_consensus()
    print("  Verifying seed-only stations via aprs.fi...")
    verify_seeds_via_aprsdotfi()
    print("  Saving final results...")
    save_results(final=True)
    print("  Syncing data back to CSV...")
    sync_to_seed_csv()

    with lock:
        nd = sum(1 for s in stations.values() if s['type'] == 'digi')
        ni = sum(1 for s in stations.values() if s['type'] == 'igate')
        seeded_only = sum(1 for s in stations.values() if s.get('_seeded') and s.get('_heard', 0) == 0)
        n_consensus = sum(1 for s in stations.values() if s.get('_pos_conf', 0) == CONF_CONSENSUS)
        n_manual = sum(1 for s in stations.values() if s.get('_pos_conf', 0) == CONF_MANUAL)
        n_scattered = sum(1 for s in stations.values() if len(s.get('_pos_history', [])) >= CONSENSUS_MIN_COUNT and s.get('_pos_conf', 0) < CONF_CONSENSUS)

    print(f"  Total packets processed : {packet_count}")
    print(f"  Total errors logged     : {error_count}")
    print(f"  Total time elapsed      : {timedelta(seconds=int(time.time() - start_time))}")
    print(f"  Unique digipeaters      : {nd}")
    print(f"  Unique I-gates          : {ni}")
    print(f"  Seed-only (not heard)   : {seeded_only}  <- verify on aprs.fi")
    print(f"  Consensus positions     : {n_consensus}  (>= {CONSENSUS_MIN_COUNT} agreeing reports)")
    print(f"  Manually Locked         : {n_manual}  (From CSV)")
    print(f"  Scattered/suspect pos.  : {n_scattered}  (reports too spread out to trust)")
    print(f"  Output file             : {OUTPUT_FILE}")
    print("=" * 65)

    sys.stdout = _tee._console
    _tee.close()
    print(f"  Log saved : {LOG_FILE}")

if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        save_results(final=True)
    finally:
        if _tee is not None and sys.stdout is _tee:
            sys.stdout = _tee._console
            _tee.close()
