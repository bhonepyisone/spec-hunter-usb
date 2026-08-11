"""Unit tests for display.py — edid-decode, sysfs EDID, xrandr fallback."""

import unittest
from unittest.mock import patch
from pathlib import Path
from collector import display


class TestDisplay(unittest.TestCase):

    @patch("collector.display.subprocess.run")
    def test_edid_decode(self, mock_run):
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "EDID structure version: 1.4\n"
            "Manufacturer: LGD\n"
            "Display Product Name: LP140WF9-SPU1\n"
            "Detailed mode: Clock 152.840 MHz, 1920x1080\n"
            "                1920 2008 2056 2250\n"
            "                1080 1084 1089 1132\n"
            "Horizontal resolution: 1920\n"
            "Vertical resolution: 1080\n"
        )
        mock_run.return_value = mock_result

        result = display._edid_decode()

        self.assertEqual(result["resolution"], "1920x1080")
        self.assertEqual(result["manufacturer"], "LGD")
        self.assertEqual(result["model"], "LP140WF9-SPU1")

    @patch("collector.display.subprocess.run")
    def test_edid_decode_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError("edid-decode not installed")

        result = display._edid_decode()

        self.assertEqual(result, {})

    @patch("collector.display.subprocess.run")
    def test_xrandr_resolution(self, mock_run):
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "eDP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 344mm x 194mm\n"
        )
        mock_run.return_value = mock_result

        resolution = display._xrandr_resolution()

        self.assertEqual(resolution, "1920x1080")

    @patch("collector.display.subprocess.run")
    def test_xrandr_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError("xrandr not installed")

        result = display._xrandr_resolution()

        self.assertIsNone(result)

    @patch("collector.display._edid_decode", return_value={})
    @patch("collector.display._xrandr_resolution", return_value="1920x1080")
    @patch("collector.display.DRM_PATH")
    def test_collect_fallback_to_xrandr(self, mock_drm_path, mock_xrandr, mock_edid):
        mock_drm_path.glob.return_value = []

        result = display.collect()

        self.assertEqual(result["resolution"], "1920x1080")

    @patch("collector.display._edid_decode", return_value={})
    @patch("collector.display._xrandr_resolution", return_value=None)
    @patch("collector.display.DRM_PATH")
    def test_collect_no_display_available(self, mock_drm_path, mock_xrandr, mock_edid):
        mock_drm_path.glob.return_value = []

        result = display.collect()

        self.assertEqual(result["resolution"], "N/A")
        self.assertEqual(result["manufacturer"], "N/A")
        self.assertEqual(result["model"], "N/A")

    def test_sysfs_edid_resolution_parse(self):
        """Raw EDID: manufacturer bytes + preferred-timing resolution.

        mock_open can't intercept Path.read_bytes() (it opens via io.FileIO,
        not builtins.open), so the Path method itself must be patched.
        """
        data = bytearray(128)
        data[8] = 0x30  # manufacturer "LGD" (L=12,G=7,D=4 packed into 16 bits)
        data[9] = 0xE4
        data[56] = 0x80  # H active low byte = 128
        data[58] = 0x70  # H active high nibble = 7  → 1920
        data[59] = 0x38  # V active low byte = 56
        data[61] = 0x40  # V active high nibble = 4  → 1080

        with patch("collector.display.Path.read_bytes", return_value=bytes(data)):
            info = display._parse_edid_binary(Path("/fake/edid"))

        self.assertEqual(info.get("resolution"), "1920x1080")
        self.assertEqual(info.get("manufacturer"), "LGD")

    @patch("collector.display._edid_decode")
    def test_collect_with_edid(self, mock_edid):
        mock_edid.return_value = {
            "resolution": "1920x1080",
            "manufacturer": "LGD",
            "model": "LP140WF9-SPU1",
        }

        result = display.collect()

        self.assertEqual(result["resolution"], "1920x1080")
        self.assertEqual(result["manufacturer"], "LGD")
        self.assertEqual(result["model"], "LP140WF9-SPU1")


if __name__ == "__main__":
    unittest.main()
