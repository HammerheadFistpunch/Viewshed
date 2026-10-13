import unittest
from types import SimpleNamespace

from antenna_patterns import ANTENNA_PRESETS, pattern_loss_db, pattern_settings
from microwave_link_budget import CPE710_PLANNING, CPE710_PRESET, free_space_budget
from microwave_settings import microwave_radio, polarized_path_loss
from station_rf_worker import _resolve_max_path_loss
from test_microwave import VALUES


class MicrowaveBudgetTests(unittest.TestCase):
    def test_cpe710_specs_and_half_power_beam(self):
        preset = ANTENNA_PRESETS[CPE710_PRESET]
        self.assertEqual((preset['gain_dbi'], preset['az_bw'], preset['el_bw']), (23, 9, 7))
        cfg = pattern_settings(dict(tx_pattern='directional', tx_az_beamwidth_deg=9, tx_el_beamwidth_deg=7))
        self.assertAlmostEqual(pattern_loss_db(cfg, 4.5, 0), 3)
        self.assertAlmostEqual(pattern_loss_db(cfg, 0, 3.5), 3)

    def test_long_range_budget_matches_engine_without_mimo_bonus(self):
        values = dict(VALUES, **CPE710_PLANNING)
        budget = free_space_budget(values)
        # 5.8 GHz / 30 km: FSPL = 137.26 dB. 20 + 23 + 23 - 2.
        self.assertAlmostEqual(budget['received_dbm'], -73.2609849656, places=6)
        self.assertAlmostEqual(budget['margin_db'], -3.2609849656, places=6)
        self.assertAlmostEqual(budget['effective_budget_db'], _resolve_max_path_loss(microwave_radio(values)))
        self.assertAlmostEqual(budget['ideal_distance_km'], 20.609716, places=4)
        self.assertAlmostEqual(budget['fresnel_60pct_m'], 11.813491, places=4)
        self.assertAlmostEqual(budget['midpoint_bulge_m'], 13.243604, places=4)
        # Raising the required signal for higher rates sharply reduces range.
        fast = free_space_budget(dict(values, rx_sensitivity_dbm=-65))
        self.assertAlmostEqual(fast['ideal_distance_km'], budget['ideal_distance_km'] / 10)

    def test_cap_and_reserve_match_engine_and_bad_distance_rejected(self):
        values = dict(VALUES, path_loss_cap_db=130, reserve_db=20)
        self.assertEqual(free_space_budget(values)['effective_budget_db'], 110)
        for radius in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                free_space_budget(dict(values, radius_km=radius))

    def test_dual_evaluates_both_and_requires_weaker_channel(self):
        cfg = microwave_radio(dict(VALUES, polarization='Dual (H + V)'))
        calls = []
        def evaluate(pol):
            calls.append(pol)
            return (140, 147)[pol]
        self.assertEqual(polarized_path_loss(cfg, evaluate), 147)
        self.assertEqual(calls, [0, 1])
        for choice, expected in (('Horizontal', 140), ('Vertical', 147)):
            self.assertEqual(polarized_path_loss(microwave_radio(dict(VALUES, polarization=choice)), evaluate), expected)
        with self.assertRaises(ValueError):
            polarized_path_loss(cfg, lambda pol: float('nan') if pol else 100)

    def test_cpe710_pair_ui_defaults_and_manual_edits(self):
        from power_ui_cleanup_workspace import ViewshedWorkspace
        class Var:
            def __init__(self, value=''): self.value = str(value)
            def get(self): return self.value
            def set(self, value): self.value = str(value)
        variables = {key: Var(value) for key, value in VALUES.items()}
        variables.update({key: Var() for key in ('tx_antenna_preset', 'rx_antenna_preset', 'tx_pattern', 'tx_az_beamwidth_deg', 'tx_el_beamwidth_deg')})
        ui = SimpleNamespace(_microwave_vars=variables, _antenna_note=Var())
        ui._apply_antenna_preset = lambda side: ViewshedWorkspace._apply_antenna_preset(ui, side)
        ViewshedWorkspace._apply_cpe710_pair(ui)
        self.assertEqual(variables['polarization'].get(), 'Dual (H + V)')
        self.assertEqual(variables['tx_az_beamwidth_deg'].get(), '9')
        self.assertEqual(variables['rx_gain_dbi'].get(), '23')
        self.assertEqual(variables['tx_height_m'].get(), '10')
        variables['rx_sensitivity_dbm'].set('-75')
        self.assertEqual(microwave_radio({k: v.get() for k, v in variables.items()})['rx_sensitivity_dbm'], -75)


if __name__ == '__main__':
    unittest.main()
