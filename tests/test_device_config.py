import json
import tempfile
import unittest
from pathlib import Path

from device_config import load_polar_devices, load_polar_macs


class LoadPolarDevicesTests(unittest.TestCase):
    def test_loads_named_devices_and_normalizes_macs(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "device_macs.json"
            config_path.write_text(
                json.dumps(
                    {
                        "polar_devices": [
                            {"name": "Pessoa 1", "mac": "aa:bb:cc:dd:ee:ff"},
                            {"name": "Pessoa 2", "mac": "11:22:33:44:55:66"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                load_polar_devices(config_path),
                (
                    ("Pessoa 1", "AA:BB:CC:DD:EE:FF"),
                    ("Pessoa 2", "11:22:33:44:55:66"),
                ),
            )

    def test_keeps_legacy_mac_list_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "device_macs.json"
            config_path.write_text(
                json.dumps({"polar_macs": ["aa:bb:cc:dd:ee:ff"]}),
                encoding="utf-8",
            )

            self.assertEqual(load_polar_macs(config_path), ("AA:BB:CC:DD:EE:FF",))
            self.assertEqual(
                load_polar_devices(config_path),
                (("Polar 1", "AA:BB:CC:DD:EE:FF"),),
            )

    def test_rejects_missing_device_name(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "device_macs.json"
            config_path.write_text(
                json.dumps({"polar_devices": [{"mac": "AA:BB:CC:DD:EE:FF"}]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "non-empty name"):
                load_polar_devices(config_path)


if __name__ == "__main__":
    unittest.main()
