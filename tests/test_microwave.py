import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from microwave_settings import microwave_radio
from propagation_sampling import microwave_distances, profile_to_distance
from station_rf_worker import _resolve_max_path_loss


VALUES = dict(frequency_ghz=5.8, tx_power_dbm=20, tx_gain_dbi=24,
              rx_gain_dbi=24, rx_sensitivity_dbm=-85, tx_height_m=10,
              rx_height_m=2, system_loss_db=2, reserve_db=10,
              path_loss_cap_db=200, loss_sample_spacing_m=250,
              polarization="Vertical", radius_km=20)


class MicrowaveTests(unittest.TestCase):
    def test_ghz_and_isotropic_link_budget(self):
        radio = microwave_radio(VALUES)
        self.assertEqual(radio["freq_mhz"], 5800)
        self.assertAlmostEqual(_resolve_max_path_loss(radio), 141)
        self.assertEqual(radio["itm_pol"], 1)

    def test_frequency_boundaries_and_nonfinite_values(self):
        for frequency in (1, 10):
            self.assertEqual(microwave_radio(dict(VALUES, frequency_ghz=frequency))["freq_mhz"], frequency * 1000)
        for frequency in (0.9, 10.1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                microwave_radio(dict(VALUES, frequency_ghz=frequency))

    def test_sampling_starts_near_site_and_includes_endpoint(self):
        distances = microwave_distances(20000, 10, 250)
        self.assertEqual(len(distances), 82)
        self.assertEqual(distances[0], 10)
        self.assertIn(1000, distances)
        self.assertEqual(distances[-1], 20000)
        coarse = microwave_distances(2000, 500, 25)
        self.assertEqual(len(coarse), 6)
        with self.assertRaises(ValueError):
            microwave_distances(500000, 10, 25)

    def test_profile_has_exact_endpoint_and_retains_ridge(self):
        profile = profile_to_distance([0, 10, 100, 30, 40], 400, 250)
        self.assertEqual(profile[0], 0)
        self.assertEqual(profile[-1], 65)
        self.assertGreater(max(profile), 60)
        self.assertEqual(profile_to_distance([0, 10, 100, 30, 40], 400, 400), [0, 10, 100, 30, 40])

    def test_microwave_job_keeps_metric_values_and_selected_site(self):
        from power_ui_cleanup_workspace import ViewshedWorkspace
        class Var:
            def __init__(self, value): self.value = str(value)
            def get(self): return self.value
        started = []
        ui = SimpleNamespace(_microwave_vars={key: Var(value) for key, value in VALUES.items()},
                             custom_lat=Var(40), custom_lon=Var(-111), _imperial=True,
                             _advanced_settings=lambda **kw: {},
                             app=SimpleNamespace(source_var=Var("stations.json"),
                                                 start_job=lambda *args: started.append(args)))
        with patch("power_ui_cleanup_workspace.prepare_job", return_value=(None, "job.json")) as prepare:
            ViewshedWorkspace.run_microwave(ui)
        args, kwargs = prepare.call_args
        self.assertEqual(args[0].radius_km, 20)
        self.assertEqual(kwargs["radio_settings"]["antenna_height_digi_m"], 10)
        self.assertEqual(kwargs["selected_records"][0]["lon"], -111)
        self.assertEqual(started[0][0], "job.json")


if __name__ == "__main__":
    unittest.main()
