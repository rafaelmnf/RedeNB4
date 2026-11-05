import json
import re
from pathlib import Path


_MAC_PATTERN = re.compile(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\Z")
_DEFAULT_CONFIG = Path(__file__).resolve().with_name("device_macs.json")


def load_polar_macs(config_path=None):
    """Load and normalize the configured Polar MAC addresses."""
    path = Path(config_path) if config_path is not None else _DEFAULT_CONFIG
    try:
        with path.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Missing {path}. Copy device_macs.example.json to device_macs.json "
            "and add your device addresses to the polar_macs list."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(config, dict) or not isinstance(config.get("polar_macs"), list):
        raise ValueError(f"{path} must contain a 'polar_macs' list.")

    addresses = []
    for index, address in enumerate(config["polar_macs"]):
        if not isinstance(address, str) or not _MAC_PATTERN.fullmatch(address.strip()):
            raise ValueError(
                f"Invalid MAC at polar_macs[{index}] in {path}; "
                "expected the format AA:BB:CC:DD:EE:FF."
            )
        normalized = address.strip().upper()
        if normalized not in addresses:
            addresses.append(normalized)

    if not addresses:
        raise ValueError(f"No MAC addresses configured in {path} (polar_macs is empty).")

    return tuple(addresses)
