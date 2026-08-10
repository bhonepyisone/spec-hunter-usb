"""Unit tests for storage.py — smartctl/nvme parsing, dual drive detection."""

import json
import unittest
from unittest.mock import patch, mock_open
from collector import storage


class TestStorage(unittest.TestCase):

    def test_get_block_devices_normal(self):
        lsblk_json = json.dumps({
            "blockdevices": [
                {"name": "nvme0n1", "model": "Samsung PM981", "size": 512110190592, "rota": 0},
                {"name": "sda", "model": "WD Blue 1TB", "size": 1000204886016, "rota": 1},
            ]
        })
        with patch("collector.storage.subprocess.run") as mock_run:
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = lsblk_json
            mock_run.return_value = mock_result

            devices = storage._get_block_devices()

            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0]["name"], "nvme0n1")
            self.assertEqual(devices[0]["model"], "Samsung PM981")
            self.assertEqual(devices[1]["name"], "sda")

    def test_get_block_devices_filters_loop_zram(self):
        lsblk_json = json.dumps({
            "blockdevices": [
                {"name": "sda", "model": "SSD", "size": 500000000000, "rota": 0},
                {"name": "loop0", "model": "", "size": 1000000, "rota": 0},
                {"name": "zram0", "model": "", "size": 4000000000, "rota": 0},
            ]
        })
        with patch("collector.storage.subprocess.run") as mock_run:
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = lsblk_json
            mock_run.return_value = mock_result

            devices = storage._get_block_devices()

            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0]["name"], "sda")

    def test_get_block_devices_failure(self):
        with patch("collector.storage.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("lsblk not found")
            devices = storage._get_block_devices()
            self.assertEqual(devices, [])

    def test_smartctl_sata_parsing(self):
        smart_output = (
            "smartctl 7.2\n"
            "Device Model:     Samsung SSD 860 EVO 500GB\n"
            "SMART overall-health self-assessment test result: PASSED\n"
            "ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE\n"
            "  9 Power_On_Hours          0x0032   098   098   000    Old_age   Always       -       1742\n"
            " 12 Power_Cycle_Count       0x0032   099   099   000    Old_age   Always       -       386\n"
            "194 Temperature_Celsius     0x0022   065   050   000    Old_age   Always       -       35\n"
            "  5 Reallocated_Sector_Ct   0x0033   100   100   010    Pre-fail  Always       -       0\n"
            "232 Available_Reserved_Space 0x0033  100   100   000    Pre-fail  Always       -       96\n"
        )
        with patch("collector.storage.subprocess.run") as mock_run:
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = smart_output
            mock_run.return_value = mock_result

            result = storage._smartctl_info("sda")

            self.assertEqual(result["model"], "Samsung SSD 860 EVO 500GB")
            self.assertEqual(result["smart_status"], "PASS")
            self.assertEqual(result["power_on_hours"], 1742)
            self.assertEqual(result["power_cycles"], 386)
            self.assertEqual(result["temperature"], 35)
            self.assertEqual(result["bad_sectors"], 0)
            self.assertEqual(result["health_pct"], 96)

    def test_nvme_smart_parsing(self):
        nvme_output = (
            "Smart Log for NVMe device:nvme0 namespace-id:ffffffff\n"
            "percentage_used                     : 4%\n"
            "power_on_hours                      : 1742\n"
            "power_cycles                        : 386\n"
            "temperature                         : 35 C\n"
            "data_units_written                  : 5242880\n"
        )
        nvme_id_output = 'mn : "Samsung PM981"\n'

        call_count = 0
        def run_side_effect(args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            if "smart-log" in args:
                mock_result.stdout = nvme_output
            elif "id-ctrl" in args:
                mock_result.stdout = nvme_id_output
            elif "lsblk" in args:
                mock_result.stdout = json.dumps({
                    "blockdevices": [
                        {"name": "nvme0n1", "model": "Samsung PM981", "size": 512110190592, "rota": 0}
                    ]
                })
            return mock_result

        with patch("collector.storage.subprocess.run") as mock_run:
            mock_run.side_effect = run_side_effect

            # Call _smartctl_info directly
            nvme_result = storage._smartctl_info("nvme0n1")

            self.assertEqual(nvme_result["model"], "Samsung PM981")
            self.assertEqual(nvme_result["health_pct"], 96)
            self.assertEqual(nvme_result["remaining_life_pct"], 96)
            self.assertEqual(nvme_result["power_on_hours"], 1742)
            self.assertEqual(nvme_result["temperature"], 35)

    def test_capacity_from_sysfs(self):
        with patch("builtins.open", mock_open(read_data="1000215216\n")):
            result = storage._capacity_from_sysfs("sda")
            self.assertEqual(result, 1000215216 * 512)

    def test_collect_no_devices(self):
        with patch("collector.storage._get_block_devices", return_value=[]):
            result = storage.collect()
            self.assertEqual(result["model"], "N/A")
            self.assertIsNone(result["capacity_gb"])

    def test_collect_with_storage2(self):
        lsblk_json = json.dumps({
            "blockdevices": [
                {"name": "nvme0n1", "model": "Samsung PM981", "size": 512110190592, "rota": 0},
                {"name": "sda", "model": "WD Blue 1TB", "size": 1000204886016, "rota": 1},
            ]
        })

        with patch("collector.storage.subprocess.run") as mock_run:
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = lsblk_json
            mock_run.return_value = mock_result

            with patch("collector.storage._smartctl_info") as mock_smart:
                mock_smart.return_value = {
                    "model": "Samsung PM981",
                    "capacity_gb": 512,
                    "interface": "NVMe",
                    "health_pct": 96,
                    "power_on_hours": 1742,
                    "remaining_life_pct": 96,
                    "smart_status": "PASS",
                }
                with patch("collector.storage._capacity_from_sysfs", side_effect=[None, None]):
                    result = storage.collect()

                    self.assertEqual(result["model"], "Samsung PM981")
                    self.assertIn("storage2", result)
                    self.assertEqual(result["storage2"]["model"], "Samsung PM981")


if __name__ == "__main__":
    unittest.main()
