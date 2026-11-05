import json
import re
from pathlib import Path


_MAC_PATTERN = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\Z")
_DEFAULT_CONFIG = Path(__file__).resolve().with_name("device_macs.json")


def load_polar_devices(config_path=None):
    """Load and normalize configured Polar devices as (name, MAC) pairs."""
    path = Path(config_path) if config_path is not None else _DEFAULT_CONFIG
    try:
        with path.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Missing {path}. Copy device_macs.example.json to device_macs.json "
            "and add your device addresses to the polar_devices list."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    if "polar_devices" in config:
        devices = config["polar_devices"]
        if not isinstance(devices, list):
            raise ValueError(f"{path} must contain a 'polar_devices' list.")
    elif isinstance(config.get("polar_macs"), list):
        devices = [
            {"name": f"Polar {index + 1}", "mac": address}
            for index, address in enumerate(config["polar_macs"])
        ]
    else:
        raise ValueError(f"{path} must contain a 'polar_devices' list.")

    addresses = []
    for index, device in enumerate(devices):
        if not isinstance(device, dict):
            raise ValueError(f"polar_devices[{index}] in {path} must be an object.")
        name = device.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"polar_devices[{index}] in {path} must have a non-empty name.")
        address = device.get("mac")
        if not isinstance(address, str) or not _MAC_PATTERN.fullmatch(address.strip()):
            raise ValueError(
                f"Invalid MAC at polar_devices[{index}].mac in {path}; "
                "expected the format AA:BB:CC:DD:EE:FF."
            )
        normalized = address.strip().upper()
        if normalized not in [mac for _, mac in addresses]:
            addresses.append((name.strip(), normalized))

    if not addresses:
        raise ValueError(f"No devices configured in {path} (polar_devices is empty).")

    return tuple(addresses)


def load_polar_macs(config_path=None):
    """Load configured MAC addresses, preserving compatibility with existing scripts."""
    return tuple(mac for _, mac in load_polar_devices(config_path))
