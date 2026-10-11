"""User-editable runtime settings, loaded from ``settings.ini``.

Why this file exists
--------------------
Lab operators need to change a few things *without touching Python*: which PC
the instruments live on, the VISA addresses, and the furnace COM port.  Those
values live in a plain-text ``settings.ini`` next to the application (or next
to the ``.exe`` once packaged).

This module reads that file once at import time and exposes the result as a
single, typed ``settings`` object::

    from app_config import settings
    if settings.remote_mode:
        ...

``constants.py`` re-exports these values under their familiar names
(``REMOTE_MODE``, ``DAQ_RESOURCE``, ``EUROTHERM_COM_PORT`` …), so the rest of
the code base keeps importing from ``constants`` exactly as before.

Design rules
------------
* **Safe when the file is missing.**  Every value has a built-in default, so a
  fresh checkout with no ``settings.ini`` still runs (in safe *local* mode with
  no secrets).
* **Secrets stay out of source.**  The real host/token live only in
  ``settings.ini`` (git-ignored).  ``settings.example.ini`` is the committed
  template.  The defaults here are deliberately neutral (localhost, empty
  token) so nothing sensitive is ever baked into the code.
* **No heavy dependencies.**  Pure standard library (``configparser``) so it
  imports cleanly everywhere, including on the lab PC and in the frozen build.
* **Bad values never crash the app.**  A malformed entry falls back to its
  default and prints a one-line warning instead of raising.
"""

from __future__ import annotations

import configparser
import os
import sys
from dataclasses import dataclass
from pathlib import Path

SETTINGS_FILENAME = "settings.ini"


def _app_dir() -> Path:
    """Directory the app runs from.

    Frozen (PyInstaller) build → the folder containing the ``.exe``.
    Normal run → the project root (where this file lives).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _settings_path() -> Path:
    """Resolve the settings file path.

    The ``TMS_SETTINGS`` environment variable overrides the default location,
    which is handy for tests or running several configurations side by side.
    """
    override = os.environ.get("TMS_SETTINGS")
    return Path(override) if override else _app_dir() / SETTINGS_FILENAME


@dataclass(frozen=True)
class Settings:
    """Every user-configurable value, with its built-in default."""

    # [mode]
    remote_mode: bool = False

    # [remote]
    remote_host: str = "localhost"
    remote_port: int = 8765
    remote_token: str = ""

    # [instruments]
    daq_resource: str = "USB0::0x05E6::0x6510::04619482::0::INSTR"
    ps_resource: str = "USB0::0x05E6::0x2230::805224014787570003::0::INSTR"

    # [eurotherm]
    eurotherm_com_port: int = 5
    eurotherm_device_address: int = 1
    eurotherm_baud_rate: int = 9600
    eurotherm_timeout: float = 2.0
    eurotherm_auto_detect: bool = True
    eurotherm_probe_timeout: float = 1.0

    # [sample]
    default_sample_thickness_mm: float = 2.1
    default_sample_diameter_mm: float = 15.0


def _load(path: Path) -> Settings:
    """Build a ``Settings`` from ``path``; missing file/keys → defaults."""
    defaults = Settings()
    # Inline comments ("com_port = 5   # COM5") are allowed; interpolation is
    # off so a '%' in a token is taken literally.
    parser = configparser.ConfigParser(
        inline_comment_prefixes=("#", ";"), interpolation=None
    )
    try:
        parser.read(path, encoding="utf-8")
    except (configparser.Error, OSError) as exc:
        print(f"[settings] Could not read {path}: {exc} — using defaults")

    def _get(section: str, key: str, default, cast=str):
        if not parser.has_option(section, key):
            return default
        raw = parser.get(section, key).strip()
        try:
            if cast is bool:
                return parser.getboolean(section, key)
            return cast(raw)
        except ValueError:
            print(f"[settings] Invalid [{section}] {key} = {raw!r} "
                  f"— using default {default!r}")
            return default

    d = defaults
    return Settings(
        remote_mode=_get("mode", "remote", d.remote_mode, bool),
        remote_host=_get("remote", "host", d.remote_host),
        remote_port=_get("remote", "port", d.remote_port, int),
        remote_token=_get("remote", "token", d.remote_token),
        daq_resource=_get("instruments", "daq_resource", d.daq_resource),
        ps_resource=_get("instruments", "ps_resource", d.ps_resource),
        eurotherm_com_port=_get("eurotherm", "com_port", d.eurotherm_com_port, int),
        eurotherm_device_address=_get(
            "eurotherm", "device_address", d.eurotherm_device_address, int),
        eurotherm_baud_rate=_get("eurotherm", "baud_rate", d.eurotherm_baud_rate, int),
        eurotherm_timeout=_get("eurotherm", "timeout", d.eurotherm_timeout, float),
        eurotherm_auto_detect=_get(
            "eurotherm", "auto_detect", d.eurotherm_auto_detect, bool),
        eurotherm_probe_timeout=_get(
            "eurotherm", "probe_timeout", d.eurotherm_probe_timeout, float),
        default_sample_thickness_mm=_get(
            "sample", "default_thickness_mm", d.default_sample_thickness_mm, float),
        default_sample_diameter_mm=_get(
            "sample", "default_diameter_mm", d.default_sample_diameter_mm, float),
    )


#: Module-level singleton — import this.
settings: Settings = _load(_settings_path())
