"""Unit tests for identity.py — brand router, dmidecode, sysfs fallback."""

import unittest
from unittest.mock import patch, mock_open, MagicMock
from collector import identity


class TestIdentity(unittest.TestCase):

    def _make_dmidecode(self, manufacturer, serial, model="TestModel",
                        bios="1.0", date="2022-01-01", mobo="TestMobo",
                        uuid="abc-def", asset=""):
        def side_effect(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            keyword = args[2]
            mapping = {
                "system-manufacturer": manufacturer,
                "system-serial-number": serial,
                "system-product-name": model,
                "bios-version": bios,
                "bios-release-date": date,
                "baseboard-product-name": mobo,
                "system-uuid": uuid,
                "chassis-asset-tag": asset,
            }
            result.stdout = mapping.get(keyword, "")
            return result
        return side_effect

    @patch("collector.identity.Path.exists", return_value=False)
    @patch("collector.identity.subprocess.run")
    def test_dell_brand_router(self, mock_run, mock_exists):
        mock_run.side_effect = self._make_dmidecode(
            manufacturer="Dell Inc.",
            serial="Service Tag: ABC1234",
        )
        result = identity.collect()

        self.assertEqual(result["brand"], "Dell Inc.")
        self.assertEqual(result["serial_number"], "ABC1234")

    @patch("collector.identity.Path.exists", return_value=False)
    @patch("collector.identity.subprocess.run")
    def test_dmidecode_failure_falls_back_to_sysfs(self, mock_run, mock_exists):
        mock_run.side_effect = FileNotFoundError("dmidecode not installed")

        result = identity.collect()

        self.assertEqual(result["brand"], "Unknown")
        self.assertEqual(result["serial_number"], "N/A")

    @patch("collector.identity.Path.exists", return_value=False)
    @patch("collector.identity.subprocess.run")
    def test_lenovo_serial_parsing(self, mock_run, mock_exists):
        mock_run.side_effect = self._make_dmidecode(
            manufacturer="Lenovo",
            serial="20XJS0M100-PF3XYZ12",
        )
        result = identity.collect()
        self.assertEqual(result["serial_number"], "PF3XYZ12")

    @patch("collector.identity.Path.exists", return_value=False)
    @patch("collector.identity.subprocess.run")
    def test_hp_not_specified_serial(self, mock_run, mock_exists):
        mock_run.side_effect = self._make_dmidecode(
            manufacturer="HP",
            serial="Not Specified",
        )
        result = identity.collect()
        self.assertEqual(result["serial_number"], "")

    @patch("collector.identity.Path.exists", return_value=False)
    @patch("collector.identity.subprocess.run")
    def test_surface_serial_unavailable(self, mock_run, mock_exists):
        mock_run.side_effect = self._make_dmidecode(
            manufacturer="Microsoft Corporation",
            serial="",
        )
        result = identity.collect()
        self.assertIn("N/A", result["serial_number"])


if __name__ == "__main__":
    unittest.main()
