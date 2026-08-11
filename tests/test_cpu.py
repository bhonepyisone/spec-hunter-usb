"""Unit tests for cpu.py — lscpu parsing, /proc/cpuinfo fallback."""

import unittest
from unittest.mock import patch, mock_open
from collector import cpu


class TestCpu(unittest.TestCase):

    def test_generation_extract_intel(self):
        self.assertEqual(cpu._extract_generation("Intel Core i5-1145G7"), 11)
        self.assertEqual(cpu._extract_generation("Intel Core i7-1360P"), 13)
        self.assertEqual(cpu._extract_generation("Intel Core i3-6100U"), 6)

    def test_generation_extract_amd(self):
        self.assertEqual(cpu._extract_generation("AMD Ryzen 5 5600U"), 56)
        self.assertEqual(cpu._extract_generation("AMD Ryzen 7 6800HS"), 68)

    def test_generation_extract_none(self):
        self.assertIsNone(cpu._extract_generation("Unknown CPU"))
        self.assertIsNone(cpu._extract_generation(""))

    @patch("collector.cpu.subprocess.run")
    def test_lscpu_parsing(self, mock_run):
        mock_result = unittest.mock.MagicMock()
        mock_result.stdout = (
            "Model name:          Intel Core i5-1145G7\n"
            "CPU(s):              8\n"
            "Core(s) per socket:  4\n"
            "CPU max MHz:         4400.0\n"
            "CPU min MHz:         2600.0\n"
        )
        mock_run.return_value = mock_result

        result = cpu.collect()

        self.assertEqual(result["name"], "Intel Core i5-1145G7")
        self.assertEqual(result["generation"], 11)
        self.assertEqual(result["cores"], 4)
        self.assertEqual(result["threads"], 8)
        self.assertEqual(result["turbo_clock"], 4400.0)
        self.assertEqual(result["base_clock"], 2600.0)

    @patch("collector.cpu.subprocess.run")
    def test_lscpu_failure_returns_defaults(self, mock_run):
        mock_run.side_effect = FileNotFoundError("lscpu not installed")

        result = cpu.collect()

        self.assertEqual(result["name"], "N/A")
        self.assertIsNone(result["cores"])
        self.assertIsNone(result["threads"])

    @patch("builtins.open")
    @patch("collector.cpu.subprocess.run")
    def test_lscpu_partial_output(self, mock_run, mock_file):
        mock_result = unittest.mock.MagicMock()
        mock_result.stdout = "Model name:          AMD Ryzen 5 5600U\nCPU(s):              12\n"
        mock_run.return_value = mock_result

        mock_file.side_effect = FileNotFoundError("/proc/cpuinfo not available")

        result = cpu.collect()

        self.assertEqual(result["name"], "AMD Ryzen 5 5600U")
        self.assertEqual(result["generation"], 56)
        self.assertEqual(result["threads"], 12)
        self.assertIsNone(result["cores"])


if __name__ == "__main__":
    unittest.main()
