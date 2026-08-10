"""Unit tests for network.py — lshw parsing, ip link, bluetooth detection."""

import unittest
from unittest.mock import patch
from collector import network


class TestNetwork(unittest.TestCase):

    def test_ip_mac_wifi_preferred(self):
        ip_output = (
            "1: lo: <LOOPBACK> mtu 65536\n"
            "    link/loopback 00:00:00:00:00:00\n"
            "2: enp0s31f6: <NO-CARRIER> mtu 1500\n"
            "    link/ether 00:1A:2B:3C:4D:5E\n"
            "3: wlp2s0: <UP> mtu 1500\n"
            "    link/ether AA:BB:CC:DD:EE:FF\n"
        )
        with patch("collector.network.subprocess.run") as mock_run:
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ip_output
            mock_run.return_value = mock_result

            result = network._ip_mac()

            self.assertEqual(result["mac_address"], "aa:bb:cc:dd:ee:ff")

    def test_ip_mac_ethernet_fallback(self):
        ip_output = (
            "1: lo: <LOOPBACK>\n"
            "    link/loopback 00:00:00:00:00:00\n"
            "2: enp0s31f6: <UP>\n"
            "    link/ether 00:1A:2B:3C:4D:5E\n"
        )
        with patch("collector.network.subprocess.run") as mock_run:
            mock_result = unittest.mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ip_output
            mock_run.return_value = mock_result

            result = network._ip_mac()

            self.assertEqual(result["mac_address"], "00:1a:2b:3c:4d:5e")

    @patch("collector.network.subprocess.run")
    def test_bluetooth_hciconfig(self, mock_run):
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "hci0:	Type: Primary  Bus: USB\n"
            "	BD Address: 00:11:22:33:44:55  ACL MTU: 1021:4  SCO MTU: 96:6\n"
            "	UP RUNNING\n"
        )
        mock_run.return_value = mock_result

        result = network._bluetooth_info()

        self.assertEqual(result, "Bluetooth detected")

    @patch("collector.network.subprocess.run")
    def test_bluetooth_none(self, mock_run):
        mock_run.side_effect = FileNotFoundError("hciconfig not installed")

        result = network._bluetooth_info()

        self.assertEqual(result, "N/A")

    @patch("collector.network.subprocess.run")
    def test_lshw_network_parsing(self, mock_run):
        lshw_output = (
            "  *-network:0\n"
            "       description: Wireless interface\n"
            "       product: Intel Wi-Fi 6 AX201\n"
            "       vendor: Intel Corporation\n"
            "       physical id: 14.3\n"
            "       logical name: wlp2s0\n"
            "       serial: aa:bb:cc:dd:ee:ff\n"
            "  *-network:1\n"
            "       description: Ethernet interface\n"
            "       product: Intel Ethernet Connection I219-LM\n"
            "       vendor: Intel Corporation\n"
            "       physical id: 1f.6\n"
            "       logical name: enp0s31f6\n"
            "       serial: 00:1a:2b:3c:4d:5e\n"
        )
        mock_result = unittest.mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = lshw_output
        mock_run.return_value = mock_result

        result = network._lshw_network()

        self.assertEqual(result["wifi_card"], "Intel Wi-Fi 6 AX201")
        self.assertEqual(result["lan_adapter"], "Intel Ethernet Connection I219-LM")

    @patch("collector.network._lshw_network")
    @patch("collector.network._ip_mac")
    @patch("collector.network._bluetooth_info")
    def test_collect_integration(self, mock_bt, mock_ip, mock_lshw):
        mock_lshw.return_value = {
            "wifi_card": "Intel Wi-Fi 6 AX201",
            "wifi_vendor": "Intel Corporation",
            "lan_adapter": "Intel Ethernet Connection I219-LM",
        }
        mock_ip.return_value = {"mac_address": "aa:bb:cc:dd:ee:ff"}
        mock_bt.return_value = "Bluetooth detected"

        result = network.collect()

        self.assertEqual(result["wifi_card"], "Intel Wi-Fi 6 AX201")
        self.assertEqual(result["bluetooth"], "Bluetooth detected")
        self.assertEqual(result["mac_address"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(result["lan_adapter"], "Intel Ethernet Connection I219-LM")

    @patch("collector.network._lshw_network", return_value={})
    @patch("collector.network._ip_mac", return_value={})
    @patch("collector.network._bluetooth_info", return_value="N/A")
    def test_collect_no_network_tools(self, mock_bt, mock_ip, mock_lshw):
        result = network.collect()

        self.assertEqual(result["wifi_card"], "N/A")
        self.assertEqual(result["bluetooth"], "N/A")
        self.assertEqual(result["mac_address"], "N/A")
        self.assertEqual(result["lan_adapter"], "N/A")


if __name__ == "__main__":
    unittest.main()
