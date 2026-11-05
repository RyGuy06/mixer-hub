from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mixer_runtime as runtime


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.ports = [SimpleNamespace(device="COM3", description="USB serial", serial_number="other"),
                      SimpleNamespace(device="COM8", description="Arduino Nano", serial_number="my-nano")]

    def test_remembered_identity_follows_device_when_com_port_changes(self):
        with patch.object(runtime.serial.tools.list_ports, "comports", return_value=self.ports):
            self.assertEqual(runtime.find_mixer_port("COM5", "my-nano"), "COM8")
            self.assertEqual(runtime.find_mixer_port("COM8"), "COM8")
            self.assertEqual(runtime.find_mixer_port(), "COM3")

    def test_absent_selected_device_does_not_connect_to_another_board(self):
        with patch.object(runtime.serial.tools.list_ports, "comports", return_value=self.ports):
            self.assertIsNone(runtime.find_mixer_port("COM5", "missing"))
            self.assertIsNone(runtime.find_mixer_port("COM5"))

    def test_port_list_contains_only_plain_data(self):
        with patch.object(runtime.serial.tools.list_ports, "comports", return_value=self.ports):
            self.assertEqual(runtime.list_mixer_ports()[1],
                             {"port": "COM8", "description": "Arduino Nano", "serial": "my-nano"})
