import time
import requests
import zipfile
import io
import rasterio
from rasterio.merge import merge
from pathlib import Path

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
UTAH_BBOX = (-114.1, 36.9, -109.0, 42.1) 
CACHE_DIR = Path("dem_cache")
MERGED_DEM = CACHE_DIR / "utah_3dep_merged.tif"

# The v1 API endpoint for querying available products
USGS_API_URL = "https://tnmaccess.nationalmap.gov/api/v1/products"

def download_tile(lat, lon, retries=3):
    """Downloads a 1-arcsecond DEM tile covering the given NW corner."""
    CACHE_DIR.mkdir(exist_ok=True)
    
    # Standard output filename we want to save as
    local_tif_path = CACHE_DIR / f"n{lat}w{lon}.tif"
    
    if local_tif_path.exists():
        print(f"  [Cache Hit] n{lat}w{lon}.tif already exists.")
        return local_tif_path

    # Define the exact bounding box for this 1x1 degree tile
    bbox_str = f"{-(lon+1)},{lat-1},-{lon},{lat}"

    params = {
        'datasets': 'National Elevation Dataset (NED) 1 arc-second',
        'bbox': bbox_str,
        'prodFormats': 'GeoTIFF,TIFF' # Try to get TIFF, but might return ZIP
    }

    for attempt in range(retries):
        try:
            print(f"Searching USGS API for N{lat} W{lon} (Attempt {attempt+1})...")
            r = requests.get(USGS_API_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            if not data.get('items'):
                # USGS API sometimes uses '3DEP 1 arc-second' instead of NED
                params['datasets'] = '3DEP 1 arc-second'
                r = requests.get(USGS_API_URL, params=params, timeout=30)
                data = r.json()

            if data.get('items'):
                # Grab the first valid download URL
                download_url = data['items'][0]['downloadURL']
                return perform_download(download_url, local_tif_path)
            
        except requests.exceptions.RequestException as e:
            print(f"  API issue: {e}")
            time.sleep(2)

    print(f"  ❌ Warning: Could not locate tile N{lat} W{lon} via API.")
    return None

def perform_download(url, local_tif_path):
    """Helper to stream file, automatically unzipping if necessary."""
    print(f"  Downloading: {url}")
    
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        
        # Check if the URL or headers indicate it's a ZIP archive
        if url.lower().endswith('.zip') or 'application/zip' in r.headers.get('Content-Type', ''):
            print("  Extracting TIF from ZIP archive...")
            # Download ZIP into memory
            z = zipfile.ZipFile(io.BytesIO(r.content))
            # Find the actual .tif file inside the zip (ignoring .xml/.txt metadata)
            tif_name = next((name for name in z.namelist() if name.lower().endswith('.tif')), None)
            
            if tif_name:
                with open(local_tif_path, 'wb') as f:
                    f.write(z.read(tif_name))
                return local_tif_path
            else:
                print(f"  ❌ Error: No .tif found inside the downloaded zip.")
                return None
        else:
            # It's a direct TIFF stream
            with open(local_tif_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=16384):
                    f.write(chunk)
            return local_tif_path

def build_dem():
    if MERGED_DEM.exists():
        print(f"✅ Success! Merged DEM found at {MERGED_DEM}")
        return MERGED_DEM

    lon_min, lat_min, lon_max, lat_max = UTAH_BBOX
    
    # math.ceil() equivalent logic to get integer grid degrees
    lats = range(int(lat_min) + 1, int(lat_max) + 2)
    lons = range(int(abs(lon_max)), int(abs(lon_min)) + 1)
    
    tifs = []
    for lat in lats:
        for lon in lons:
            path = download_tile(lat, lon)
            if path:
                tifs.append(path)
            # Polite pause to avoid triggering USGS API rate limits
            time.sleep(0.5)

    if not tifs:
        raise RuntimeError("Failed to download any tiles. Check your network or BBOX.")

    print(f"\nFound {len(tifs)} tiles. Merging into a single DEM...")
    
    # Read all TIFs and merge them
    datasets = [rasterio.open(tif) for tif in tifs]
    mosaic, out_trans = merge(datasets)
    
    out_meta = datasets[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans
    })
    
    print("Writing merged DEM to disk...")
    with rasterio.open(MERGED_DEM, "w", **out_meta) as dest:
        dest.write(mosaic)
        
    for ds in datasets:
        ds.close()
        
    print(f"✅ Merged DEM successfully created: {MERGED_DEM}")
    return MERGED_DEM

if __name__ == "__main__":
    build_dem()
