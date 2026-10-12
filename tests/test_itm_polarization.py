import ast
import math
import unittest
from pathlib import Path

from itmlogic.preparatory_subroutines.qlrpfl import qlrpfl
from itmlogic.statistics.avar import avar
from aprs_viewshed_utah_parallel import _itm_ground_impedance


class PolarizationTests(unittest.TestCase):
    def test_ground_impedance_matches_analytic_initialization(self):
        import cmath
        for frequency in (20, 144.39, 1000, 5800, 20000):
            dielectric = complex(15, 376.62 * 0.001 / (frequency / 47.7))
            horizontal = cmath.sqrt(dielectric - 1)
            for polarization, expected in ((0, horizontal), (1, horizontal / dielectric)):
                self.assertAlmostEqual(_itm_ground_impedance(frequency, 15, 0.001, polarization), expected)
        with self.assertRaises(ValueError):
            _itm_ground_impedance(144.39, 15, 0.001, 2)

    def test_worker_loss_changes_with_polarization(self):
        # Execute the production loss function without DEM downloads or shared memory.
        tree = ast.parse(Path("aprs_viewshed_utah_parallel.py").read_text())
        loss = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_itm_loss_for_slice")
        scope = dict(math=math, qlrpfl=qlrpfl, avar=avar,
                     _itm_ground_impedance=_itm_ground_impedance,
                     FREQ_MHZ=5800, ant_h=20, TARGET_H=2, ITM_ENS=301,
                     ITM_SGM=0.001, ITM_EPSR=15, ITM_CLIMATE=4)
        exec(compile(ast.Module(body=[loss], type_ignores=[]), "worker_loss", "exec"), scope)
        results = []
        for polarization in (0, 1):
            scope["ITM_POL"] = polarization
            results.append(scope["_itm_loss_for_slice"]([100.0] * 101, 10000))
        self.assertTrue(all(math.isfinite(x) for x in results))
        self.assertGreater(abs(results[0] - results[1]), 0.01)


if __name__ == "__main__":
    unittest.main()
