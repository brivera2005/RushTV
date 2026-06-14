"""Persist credentials and settings locally in %APPDATA%\\RushTV."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "RushTV"


def config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict[str, Any]) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def clear_credentials() -> None:
    data = load_config()
    for key in ("server_url", "username", "password", "remember"):
        data.pop(key, None)
    save_config(data)
