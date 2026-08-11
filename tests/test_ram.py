"""Unit tests for ram.py — dmidecode parsing, slot detection, /proc/meminfo fallback."""

import unittest
from unittest.mock import patch, mock_open
from collector import ram


class TestRam(unittest.TestCase):

    def test_parse_dmidecode_basic(self):
        output = [
            "Handle 0x000A, DMI type 17",
            "Memory Device",
            "        Size: 8192 MB",
            "        Type: DDR4",
            "        Speed: 3200 MHz",
            "        Manufacturer: Samsung",
            "",
            "Handle 0x000B, DMI type 17",
            "Memory Device",
            "        Size: 8192 MB",
            "        Type: DDR4",
            "        Speed: 3200 MHz",
            "        Manufacturer: Samsung",
        ]
        slots = ram._parse_dmidecode_ram(output)
        self.assertEqual(len(slots), 2)
        self.assertEqual(slots[0]["size_mb"], 8192)
        self.assertEqual(slots[0]["type"], "DDR4")
        self.assertEqual(slots[0]["speed_mhz"], 3200)
        self.assertEqual(slots[0]["manufacturer"], "Samsung")

    def test_parse_dmidecode_gb_units(self):
        output = [
            "Handle 0x0010",
            "Memory Device",
            "        Size: 16 GB",
            "        Type: DDR5",
            "        Speed: 4800 MHz",
        ]
        slots = ram._parse_dmidecode_ram(output)
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["size_mb"], 16384)

    def test_parse_dmidecode_skips_empty(self):
        output = [
            "Handle 0x000A",
            "Memory Device",
            "        Size: No Module Installed",
            "        Speed: Unknown",
        ]
        slots = ram._parse_dmidecode_ram(output)
        self.assertEqual(len(slots), 0)

    def test_parse_dmidecode_skips_out_of_spec_type(self):
        output = [
            "Handle 0x000A",
            "Memory Device",
            "        Size: 8 GB",
            "        Type: <OUT OF SPEC>",
            "        Speed: 2400 MHz",
        ]
        slots = ram._parse_dmidecode_ram(output)
        self.assertEqual(len(slots), 1)
        self.assertNotIn("type", slots[0])

    @patch("collector.ram.subprocess.run")
    def test_collect_success(self, mock_run):
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "Handle 0x000A\n"
            "Memory Device\n"
            "        Size: 8192 MB\n"
            "        Type: DDR4\n"
            "        Speed: 3200 MHz\n"
            "        Manufacturer: Samsung\n"
        )
        mock_run.return_value = mock_result

        result = ram.collect()

        self.assertAlmostEqual(result["total_gb"], 8.0)
        self.assertEqual(result["speed"], 3200)
        self.assertEqual(result["ddr_type"], "DDR4")
        self.assertEqual(result["manufacturer"], "Samsung")

    @patch("collector.ram._meminfo_total_gb", return_value=None)
    @patch("collector.ram.subprocess.run")
    def test_collect_dmidecode_failure(self, mock_run, mock_meminfo):
        mock_run.side_effect = FileNotFoundError("dmidecode not installed")

        result = ram.collect()

        self.assertIsNone(result["total_gb"])
        self.assertEqual(result["ddr_type"], "N/A")

    @patch("collector.ram._meminfo_total_gb", return_value=16.0)
    @patch("collector.ram.subprocess.run")
    def test_collect_dmidecode_failure_uses_meminfo(self, mock_run, mock_meminfo):
        mock_run.side_effect = FileNotFoundError("dmidecode not installed")

        result = ram.collect()

        self.assertEqual(result["total_gb"], 16.0)

    def test_meminfo_total_gb(self):
        with patch(
            "builtins.open",
            mock_open(read_data="MemTotal:       16777216 kB\nSwapTotal:             0 kB\n"),
        ):
            self.assertEqual(ram._meminfo_total_gb(), 16.0)


if __name__ == "__main__":
    unittest.main()
