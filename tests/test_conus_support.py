from __future__ import annotations

import unittest

from conus_support import projected_crs_for_location


class ProjectionSelectionTests(unittest.TestCase):
    def test_salt_lake_city_uses_zone_12_north(self):
        self.assertEqual(
            projected_crs_for_location(40.7608, -111.8910),
            ("EPSG:32612", 12, "N"),
        )

    def test_denver_uses_zone_13_north(self):
        self.assertEqual(
            projected_crs_for_location(39.7392, -104.9903),
            ("EPSG:32613", 13, "N"),
        )

    def test_los_angeles_uses_zone_11_north(self):
        self.assertEqual(
            projected_crs_for_location(34.0522, -118.2437),
            ("EPSG:32611", 11, "N"),
        )

    def test_new_york_uses_zone_18_north(self):
        self.assertEqual(
            projected_crs_for_location(40.7128, -74.0060),
            ("EPSG:32618", 18, "N"),
        )

    def test_southern_hemisphere_helper_uses_327xx(self):
        self.assertEqual(
            projected_crs_for_location(-33.8688, 151.2093),
            ("EPSG:32756", 56, "S"),
        )


if __name__ == "__main__":
    unittest.main()
