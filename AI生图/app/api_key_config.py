"""Load API credentials from an ignored local config file."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name("api_keys.env")


def load_api_keys(path: str | os.PathLike[str] | None = None) -> dict[str, str]:
    config_path = Path(path or os.environ.get("API_KEYS_FILE", DEFAULT_CONFIG_PATH))
    try:
        lines = config_path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return {}

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{config_path}:{line_number}: expected NAME=VALUE")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not name.replace("_", "").isalnum():
            raise ValueError(f"{config_path}:{line_number}: invalid variable name")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def get_api_key(name: str, path: str | os.PathLike[str] | None = None) -> str:
    """Return an environment override or the value in api_keys.env."""
    return os.environ.get(name, "").strip() or load_api_keys(path).get(name, "").strip()
