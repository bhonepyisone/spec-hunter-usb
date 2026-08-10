"""Unit tests for camera.py — v4l2 detection, /dev/video* enumeration."""

import unittest
from unittest.mock import patch
from collector import camera


class TestCamera(unittest.TestCase):

    @patch("collector.camera.Path.glob")
    def test_no_video_devices(self, mock_glob):
        mock_glob.return_value = []

        result = camera.collect()

        self.assertFalse(result["exists"])
        self.assertEqual(result["device_path"], "")
        self.assertEqual(result["model"], "N/A")

    @patch("collector.camera.Path.glob")
    @patch("collector.camera.subprocess.run")
    def test_camera_detected_with_v4l2(self, mock_run, mock_glob):
        class FakePath:
            def __init__(self, s):
                self.s = s
            def __str__(self):
                return self.s
            def __lt__(self, other):
                return self.s < other.s
        mock_glob.return_value = [FakePath("/dev/video0"), FakePath("/dev/video1")]

        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Card type: Integrated Camera\n"
        mock_run.return_value = mock_result

        result = camera.collect()

        self.assertTrue(result["exists"])
        self.assertEqual(result["device_path"], "/dev/video0")
        self.assertEqual(result["model"], "Integrated Camera")

    @patch("collector.camera.subprocess.run")
    @patch("collector.camera.Path.glob")
    def test_camera_no_v4l2_falls_back_to_enumeration(self, mock_glob, mock_run):
        video0 = unittest.mock.MagicMock()
        video0.__str__ = lambda s: "/dev/video0"
        mock_glob.return_value = [video0]
        mock_run.side_effect = FileNotFoundError("v4l2-ctl not installed")

        result = camera.collect()

        self.assertTrue(result["exists"])
        self.assertEqual(result["device_path"], "/dev/video0")

    @patch("collector.camera.subprocess.run")
    @patch("collector.camera.Path.glob")
    def test_v4l2_non_camera_device_rejected(self, mock_glob, mock_run):
        video0 = unittest.mock.MagicMock()
        video0.__str__ = lambda s: "/dev/video0"
        mock_glob.return_value = [video0]

        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Card type: TV Capture Card\n"
        mock_run.return_value = mock_result

        result = camera.collect()

        self.assertTrue(result["exists"])
        self.assertEqual(result["device_path"], "/dev/video0")

    @patch("collector.camera.subprocess.run")
    @patch("collector.camera.Path.glob")
    def test_webcam_keyword_detection(self, mock_glob, mock_run):
        video0 = unittest.mock.MagicMock()
        video0.__str__ = lambda s: "/dev/video0"
        mock_glob.return_value = [video0]

        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Card type: Integrated Webcam\n"
        mock_run.return_value = mock_result

        result = camera.collect()

        self.assertTrue(result["exists"])
        self.assertEqual(result["model"], "Integrated Webcam")


if __name__ == "__main__":
    unittest.main()
