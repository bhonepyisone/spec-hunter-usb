"""Unit tests for battery.py — upower parsing, sysfs fallback, edge cases."""

import unittest
from unittest.mock import patch
from collector import battery


class TestBattery(unittest.TestCase):

    @patch("collector.battery.Path.exists")
    @patch("collector.battery.subprocess.run")
    def test_upower_collect(self, mock_run, mock_exists):
        def run_side_effect(args, **kwargs):
            mock_result = unittest.mock.MagicMock()
            if args[0] == "upower" and args[1] == "-e":
                mock_result.stdout = "/org/freedesktop/UPower/devices/battery_BAT0\n"
            elif args[0] == "upower" and args[1] == "-i":
                mock_result.stdout = (
                    "  energy-full-design:  45.0 Wh\n"
                    "  energy-full:         40.1 Wh\n"
                    "  cycle count:         336\n"
                    "  percentage:          89%\n"
                    "  vendor:              LGC\n"
                    "  serial:              BAT123\n"
                )
            mock_result.returncode = 0
            return mock_result

        mock_run.side_effect = run_side_effect
        mock_exists.return_value = False

        result = battery.collect()

        self.assertEqual(result["design_capacity"], 45000)
        self.assertEqual(result["current_capacity"], 40100)
        self.assertEqual(result["cycle_count"], 336)
        self.assertEqual(result["health_pct"], 89)
        self.assertEqual(result["manufacturer"], "LGC")
        self.assertEqual(result["serial"], "BAT123")

    @patch("collector.battery.Path.exists")
    @patch("collector.battery.subprocess.run")
    def test_no_battery_upower(self, mock_run, mock_exists):
        mock_result = unittest.mock.MagicMock()
        mock_result.stdout = "/org/freedesktop/UPower/devices/line_power_AC\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        mock_exists.return_value = False

        path = battery._upower_path()

        self.assertIsNone(path)

    @patch("collector.battery.Path.exists")
    @patch("collector.battery.subprocess.run")
    def test_no_battery_collect_returns_defaults(self, mock_run, mock_exists):
        def run_side_effect(args, **kwargs):
            mock_result = unittest.mock.MagicMock()
            if args[0] == "upower" and args[1] == "-e":
                mock_result.stdout = "/org/freedesktop/UPower/devices/line_power_AC\n"
            mock_result.returncode = 0
            return mock_result

        mock_run.side_effect = run_side_effect
        mock_exists.return_value = False

        result = battery.collect()

        self.assertIsNone(result["health_pct"])
        self.assertIsNone(result["cycle_count"])
        self.assertEqual(result["manufacturer"], "N/A")

    @patch("collector.battery.SYSFS_BAT0")
    def test_sysfs_collect(self, mock_bat0):
        file_map = {
            "energy_full_design": "45000000",
            "energy_full": "40050000",
            "cycle_count": "336",
            "manufacturer": "LGC",
            "serial_number": "BAT123",
        }

        class FakeFile:
            def __init__(self, name):
                self._name = name
                self._exists = name in file_map
            def exists(self):
                return self._exists
            def read_text(self):
                if not self._exists:
                    raise FileNotFoundError()
                return file_map[self._name]

        def make_path(filename):
            return FakeFile(str(filename))

        mock_bat0.__truediv__.side_effect = make_path
        mock_bat0.exists.return_value = True

        result = battery._sysfs_collect()

        self.assertEqual(result["design_capacity"], 45000000)
        self.assertEqual(result["current_capacity"], 40050000)
        self.assertEqual(result["cycle_count"], 336)
        self.assertAlmostEqual(result["health_pct"], 89)
        self.assertEqual(result["manufacturer"], "LGC")

    @patch("collector.battery.Path.exists")
    def test_sysfs_no_battery(self, mock_exists):
        mock_exists.return_value = False
        result = battery._sysfs_collect()
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
