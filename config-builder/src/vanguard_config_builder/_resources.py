# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Bundle-aware paths to the YAML data files.

Two execution contexts need different lookups:

* **Source / editable / wheel install** — the data files ship as
  package data inside ``vanguard_config_builder/data/``. We can find
  them via ``Path(__file__).parent``.

* **PyInstaller --onefile bundle** — at runtime the bundle extracts
  to a temp directory exposed as ``sys._MEIPASS``. The release
  workflow's ``pyinstaller --add-data`` puts the data files at
  ``sys._MEIPASS/vanguard_config_builder/data/``.

Both core/cvar_database.py and core/profiles.py call into the
helpers below so the path resolution happens in exactly one place.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bundle_root() -> Path:
    """Directory that holds the bundled ``data/`` subtree.

    Returns ``Path(sys._MEIPASS) / "vanguard_config_builder"`` when
    running from a PyInstaller bundle, or the package directory
    (``Path(__file__).parent``) when running from source.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "vanguard_config_builder"
    return Path(__file__).resolve().parent


def cvars_yaml_path() -> Path:
    """Absolute path to the bundled ``cvars.yaml``."""
    return _bundle_root() / "data" / "cvars.yaml"


def profiles_dir() -> Path:
    """Absolute path to the bundled ``data/profiles/`` directory."""
    return _bundle_root() / "data" / "profiles"
