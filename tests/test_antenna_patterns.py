import math
import tempfile
import unittest
from multiprocessing.shared_memory import SharedMemory
from types import SimpleNamespace

from antenna_patterns import ANTENNA_PRESETS, pattern_loss_db, pattern_settings
from microwave_settings import microwave_radio
from test_microwave import VALUES


class AntennaTests(unittest.TestCase):
    def test_half_beamwidth_is_three_db_down(self):
        cfg = pattern_settings(dict(tx_pattern="directional", tx_az_beamwidth_deg=30,
                                    tx_el_beamwidth_deg=10, tx_azimuth_deg=350))
        self.assertEqual(pattern_loss_db(cfg, 350, 0), 0)
        self.assertAlmostEqual(pattern_loss_db(cfg, 5, 0), 3)
        self.assertAlmostEqual(pattern_loss_db(cfg, 350, 5), 3)
        self.assertEqual(pattern_loss_db(cfg, 170, 0), 30)
        cfg["tx_tilt_deg"] = -5
        self.assertEqual(pattern_loss_db(cfg, 350, -5), 0)
        cfg["tx_pattern"] = "uniform"
        self.assertEqual(pattern_loss_db(cfg, 170, 90), 0)

    def test_invalid_patterns_and_nonfinite_angles(self):
        for values in (dict(tx_pattern="MIMO"), dict(tx_azimuth_deg=math.nan),
                       dict(tx_az_beamwidth_deg=0), dict(tx_tilt_deg=100)):
            with self.assertRaises(ValueError):
                pattern_settings(values)

    def test_preset_selection_populates_gain_and_pattern_without_stream_bonus(self):
        from power_ui_cleanup_workspace import ViewshedWorkspace
        class Var:
            def __init__(self, value=""): self.value = str(value)
            def get(self): return self.value
            def set(self, value): self.value = str(value)
        name = "Panel / MIMO — TP-Link CPE510"
        variables = {key: Var(value) for key, value in VALUES.items()}
        variables.update({key: Var() for key in ("tx_antenna_preset", "rx_antenna_preset", "tx_pattern", "tx_az_beamwidth_deg", "tx_el_beamwidth_deg")})
        ui = SimpleNamespace(_microwave_vars=variables, _antenna_note=Var())
        variables["tx_antenna_preset"].set(name)
        ViewshedWorkspace._apply_antenna_preset(ui, "tx")
        self.assertEqual(variables["tx_gain_dbi"].get(), "13")
        self.assertEqual(variables["frequency_ghz"].get(), "5.5")
        self.assertEqual(variables["tx_pattern"].get(), "directional")
        self.assertEqual(variables["tx_az_beamwidth_deg"].get(), "45")
        self.assertEqual(variables["rx_gain_dbi"].get(), "24")
        variables["rx_antenna_preset"].set("Dish / MIMO — RocketDish 5G30 LW")
        ViewshedWorkspace._apply_antenna_preset(ui, "rx")
        self.assertEqual(variables["rx_gain_dbi"].get(), "30")
        radio = microwave_radio({key: var.get() for key, var in variables.items()})
        self.assertAlmostEqual(radio["tx_antenna_gain_dbd"], 10.85)
        self.assertEqual(radio["tx_antenna_preset"], name)

    def test_actual_worker_reduces_coverage_behind_antenna(self):
        import numpy as np
        import rasterio
        import aprs_viewshed_utah_parallel as engine
        from station_rf_worker import install
        install(engine)
        terrain = np.full((101, 101), 100, dtype=np.float32)
        shm = SharedMemory(create=True, size=terrain.nbytes)
        try:
            np.ndarray(terrain.shape, dtype=terrain.dtype, buffer=shm.buf)[:] = terrain
            cfg = dict(engine.CONFIG)
            cfg.update(microwave_radio(dict(VALUES, frequency_ghz=2.4, tx_gain_dbi=18,
                       rx_gain_dbi=0, reserve_db=5, tx_pattern="directional",
                       tx_az_beamwidth_deg=30, tx_el_beamwidth_deg=30)))
            cfg.update(n_radials=36, max_radius_km=2, worker_dem_max_px=500, margin_display_floor_db=0)
            with tempfile.TemporaryDirectory() as tmp:
                args = ({"callsign": "ANTENNA-TEST", "type": "digi", "lat": 40, "lon": -111},
                        {"shm_name": shm.name, "shape": terrain.shape, "dtype": str(terrain.dtype)},
                        (40, 0, 500000, 0, -40, 4500000), "EPSG:32612", 101, 101,
                        cfg, tmp, 50, 50, 100, 0, 1)
                result = engine._process_station(args)
                with rasterio.open(result[1]) as tif:
                    data = tif.read(1)
                self.assertTrue(np.isfinite(data).all())
                self.assertGreater(data[38, 50], 0)
                self.assertGreater(data[38, 50] - data[62, 50], 10)
        finally:
            shm.close()
            shm.unlink()


if __name__ == "__main__":
    unittest.main()
