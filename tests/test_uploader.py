"""Unit tests for uploader.py — config loading, retry logic, error handling."""

import unittest
from unittest.mock import patch, mock_open
from collector import uploader


class TestUploader(unittest.TestCase):

    def test_load_config(self):
        yaml_content = """
endpoint:
  url: https://us-central1-test.cloudfunctions.net/uploadLaptop
  api_key: secret-key-123
wifi:
  ssid: JM505-Shop
  password: wifi-password
"""
        with patch("builtins.open", mock_open(read_data=yaml_content)):
            config = uploader.load_config("config.yaml")

            self.assertEqual(config.endpoint.url,
                             "https://us-central1-test.cloudfunctions.net/uploadLaptop")
            self.assertEqual(config.endpoint.api_key, "secret-key-123")
            self.assertEqual(config.wifi.ssid, "JM505-Shop")
            self.assertEqual(config.wifi.password, "wifi-password")

    def test_load_config_missing_keys_defaults_empty(self):
        yaml_content = "endpoint:\n  url: http://localhost:5001\n"
        with patch("builtins.open", mock_open(read_data=yaml_content)):
            config = uploader.load_config("config.yaml")

            self.assertEqual(config.endpoint.url, "http://localhost:5001")
            self.assertEqual(config.endpoint.api_key, "")
            self.assertEqual(config.wifi.ssid, "")
            self.assertEqual(config.wifi.password, "")

    @patch("collector.uploader.requests.post")
    def test_upload_success(self, mock_post):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"laptopId": "abc123", "url": "https://example.com/laptops/abc123"}
        mock_post.return_value = mock_resp

        config = uploader.Config(
            endpoint=uploader.EndpointConfig(url="http://test/api", api_key="key"),
            wifi=uploader.WiFiConfig(ssid="test", password="test"),
        )
        payload = {"identity": {"brand": "Test"}}

        result = uploader.upload(payload, config)

        self.assertEqual(result["laptopId"], "abc123")
        self.assertEqual(result["url"], "https://example.com/laptops/abc123")
        mock_post.assert_called_once()

    @patch("collector.uploader.requests.post")
    def test_upload_auth_error_401(self, mock_post):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        config = uploader.Config(
            endpoint=uploader.EndpointConfig(url="http://test/api", api_key="bad-key"),
            wifi=uploader.WiFiConfig(ssid="test", password="test"),
        )

        with self.assertRaises(uploader.AuthError):
            uploader.upload({"identity": {"brand": "Test"}}, config)

    @patch("collector.uploader.requests.post")
    def test_upload_validation_error_422(self, mock_post):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {"details": "identity.brand must be string"}
        mock_post.return_value = mock_resp

        config = uploader.Config(
            endpoint=uploader.EndpointConfig(url="http://test/api", api_key="key"),
            wifi=uploader.WiFiConfig(ssid="test", password="test"),
        )

        with self.assertRaises(uploader.ValidationError):
            uploader.upload({"identity": {"brand": None}}, config)

    @patch("collector.uploader.requests.post")
    @patch("collector.uploader.time.sleep")
    def test_upload_retry_on_500(self, mock_sleep, mock_post):
        mock_resp_500 = unittest.mock.MagicMock()
        mock_resp_500.status_code = 500

        mock_resp_200 = unittest.mock.MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {"laptopId": "retry-ok"}

        mock_post.side_effect = [mock_resp_500, mock_resp_500, mock_resp_200]

        config = uploader.Config(
            endpoint=uploader.EndpointConfig(url="http://test/api", api_key="key"),
            wifi=uploader.WiFiConfig(ssid="test", password="test"),
        )

        result = uploader.upload({"identity": {"brand": "Test"}}, config)

        self.assertEqual(result["laptopId"], "retry-ok")
        self.assertEqual(mock_post.call_count, 3)

    @patch("collector.uploader.requests.post")
    @patch("collector.uploader.time.sleep")
    def test_upload_retry_exhausted(self, mock_sleep, mock_post):
        mock_resp_500 = unittest.mock.MagicMock()
        mock_resp_500.status_code = 500

        mock_post.side_effect = [mock_resp_500, mock_resp_500, mock_resp_500]

        config = uploader.Config(
            endpoint=uploader.EndpointConfig(url="http://test/api", api_key="key"),
            wifi=uploader.WiFiConfig(ssid="test", password="test"),
        )

        with self.assertRaises(uploader.UploadError):
            uploader.upload({"identity": {"brand": "Test"}}, config)

        self.assertEqual(mock_post.call_count, 3)

    @patch("collector.uploader.requests.post")
    @patch("collector.uploader.time.sleep")
    def test_upload_retry_on_connection_error(self, mock_sleep, mock_post):
        from collector.uploader import requests as req_mod

        mock_resp_200 = unittest.mock.MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {"laptopId": "conn-ok"}

        mock_post.side_effect = [
            req_mod.ConnectionError("No network"),
            mock_resp_200,
        ]

        config = uploader.Config(
            endpoint=uploader.EndpointConfig(url="http://test/api", api_key="key"),
            wifi=uploader.WiFiConfig(ssid="test", password="test"),
        )

        result = uploader.upload({"identity": {"brand": "Test"}}, config)

        self.assertEqual(result["laptopId"], "conn-ok")
        self.assertEqual(mock_post.call_count, 2)

    def test_save_fallback(self):
        payload = {"identity": {"brand": "Test"}}
        with patch("builtins.open", mock_open()) as mock_file:
            uploader.save_fallback(payload, "/tmp/test.json")
            mock_file.assert_called_once_with("/tmp/test.json", "w")


if __name__ == "__main__":
    unittest.main()
