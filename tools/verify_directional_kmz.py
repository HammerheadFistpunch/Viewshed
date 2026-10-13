import json, tempfile, zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer
import operator_tools_workspace
import aprs_viewshed_utah_parallel as engine
from rendering import install_rendering_fix
from microwave_settings import microwave_radio
from PIL import Image


def main(polarization='Vertical'):
    install_rendering_fix(engine)
    station = {'callsign': 'CUSTOM-MW', 'type': 'digi', 'lat': 40.0, 'lon': -111.0}
    cx, cy = Transformer.from_crs('EPSG:4326','EPSG:32612',always_xy=True).transform(-111,40)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); work = root/'output'/'work'; work.mkdir(parents=True)
        dem = root/'terrain.tif'
        with rasterio.open(dem,'w',driver='GTiff',width=201,height=201,count=1,dtype='float32',crs='EPSG:32612',transform=from_origin(cx-10050,cy+10050,100,100),nodata=-9999) as t:
            t.write(np.full((201,201),100,dtype=np.float32),1)
        radio = microwave_radio(dict(frequency_ghz=5.8,tx_power_dbm=20,tx_gain_dbi=24,rx_gain_dbi=24,rx_sensitivity_dbm=-85,tx_height_m=10,rx_height_m=2,system_loss_db=2,reserve_db=10,path_loss_cap_db=200,loss_sample_spacing_m=250,polarization=polarization,tx_pattern='directional',tx_az_beamwidth_deg=10,tx_el_beamwidth_deg=10))
        cfg = dict(engine.CONFIG); cfg.update(radio)
        cfg.update(n_radials=72,max_radius_km=10,worker_dem_max_px=500,cpu_workers=1,margin_display_floor_db=0,work_dir=str(work),output_network_heatmap=True,output_per_station_heatmaps=True,output_kmz='viewshed.kmz')
        for az in (0,90):
            cfg['tx_azimuth_deg']=az
            results = engine.compute_viewsheds([dict(station)],dem,cfg,work)
            assert results
            cov,station_tifs = engine.merge_viewsheds(results,dem,work,cfg)
            png,bbox=engine.raster_to_png_overlay(cov,work,cfg)
            kmz=engine.build_kmz([station],png,bbox,cfg,work,station_tifs=station_tifs)
            with rasterio.open(work/'network_best_margin.tif') as t: data=t.read(1)
            with zipfile.ZipFile(kmz) as z:
                kml=z.read('doc.kml').decode()
                assert f'{az:.1f}° grid azimuth' in kml
                assert polarization in kml
                assert 'network/network_margin_bands.png' in z.namelist(), z.namelist()
                import io
                image=np.array(Image.open(io.BytesIO(z.read('network/network_margin_bands.png'))))
            north,east=data[50,100],data[100,150]
            n_alpha,e_alpha=image[50,100,3],image[100,150,3]
            print('EXPORT CHECK:',az,'north/east margins:',north,east,'PNG alpha:',n_alpha,e_alpha)
            if az==0: assert north>0 and east<0 and n_alpha>0 and e_alpha==0
            else: assert east>0 and north<0 and e_alpha>0 and n_alpha==0
        print('Spawned worker, network heatmap and KMZ rotation checks passed.')

if __name__ == '__main__': main('Dual (H + V)' if '--dual' in sys.argv else 'Vertical')

