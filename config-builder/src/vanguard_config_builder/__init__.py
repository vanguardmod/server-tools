# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""VanguardMod config-builder — GUI and CLI for editing server.cfg.

The package surface mirrors what the v0.1.0 prototype exposed at the
top of ``main.py`` so existing callers (the smoke suite, downstream
scripts) keep working without code changes:

* ``CVARS`` — flat dict of cvar metadata, loaded from
  ``data/cvars.yaml`` at import time.
* ``CATEGORIES`` — list of ``(id, label)`` tuples in display order.
* ``PROFILES`` — flat dict of profile-name -> values dict, with each
  profile resolved through its ``extends`` chain.
* ``__version__`` — tool version string.
* ``generate_cfg``, ``parse_cfg``, ``validate`` — the same wrapper
  functions the GUI calls; they delegate to ``core/`` and inject the
  module-level cvar table.
* ``main()`` — launch the GUI. Used by ``python -m
  vanguard_config_builder`` and by the legacy entry point.

The GUI implementation lives in ``vanguard_config_builder.gui``; the
CLI in ``vanguard_config_builder.cli``.
"""

from __future__ import annotations

from typing import Any

from .core.cfg_generator import generate_cfg as _generate_cfg
from .core.cfg_parser import parse_cfg as _parse_cfg
from .core.cvar_database import default_database_path, load_cvar_database
from .core.profiles import default_profiles_path, load_profile_set
from .core.validator import validate as _validate

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
# Kept in sync with ../../VERSION manually as part of the release flow
# (M11 of Phase 2 bumps both). M11 also updates pyproject.toml's
# ``[project] version`` to match. Reading from the VERSION file at
# import time is intentionally NOT done here — it would require either
# extra package data or fragile path math that breaks in PyInstaller
# bundles. One hardcoded number, three sources to keep aligned, all
# touched together at release time.
__version__ = "0.1.0"


# ---------------------------------------------------------------------------
# Cvar database — loaded once at import
# ---------------------------------------------------------------------------
_DATABASE = load_cvar_database(default_database_path())

# v0.1.0-shaped flat dict that the GUI layout code and smoke tests
# inspect. Generated from the typed schema; the YAML is the source
# of truth.
CVARS: dict[str, dict[str, Any]] = _DATABASE.as_legacy_dict()

# v0.1.0-shaped list of ``(id, label)`` tuples in display order.
CATEGORIES: list[tuple[str, str]] = [
    (cat.id, cat.label) for cat in _DATABASE.categories
]


# ---------------------------------------------------------------------------
# Profile set — loaded once and rendered into the v0.1.0 PROFILES shape
# ---------------------------------------------------------------------------
_PROFILE_SET = load_profile_set(default_profiles_path())


def _build_legacy_profiles_dict() -> dict[str, dict[str, Any]]:
    """Render the loaded ProfileSet into the v0.1.0 inline shape.

    Each user-visible profile resolves through its inheritance chain;
    the human-readable ``profile_name`` becomes the dict key
    (matching the v0.1.0 keys ``"Cup / Tournament"``, ``"Public
    Server"``, ``"Practice / Scrim"``) and the merged values dict
    becomes the value. Cvar names are validated against ``CVARS``
    during the resolve so a typo in a profile YAML fails at module
    import, not silently in the GUI.
    """
    known = set(CVARS.keys())
    out: dict[str, dict[str, Any]] = {}
    for stem in _PROFILE_SET.list_names():
        resolved = _PROFILE_SET.resolve(stem, valid_cvars=known)
        out[resolved.profile_name] = resolved.values
    return out


PROFILES: dict[str, dict[str, Any]] = _build_legacy_profiles_dict()


# ---------------------------------------------------------------------------
# Wrapper functions — keep the v0.1.0 call signatures
# ---------------------------------------------------------------------------
def generate_cfg(
    values: dict[str, Any],
    profile_name: str = "custom",
    with_header: bool = True,
) -> str:
    """Render *values* into server.cfg syntax (delegates to core)."""
    return _generate_cfg(
        values, CVARS, __version__,
        profile_name=profile_name, with_header=with_header,
    )


def parse_cfg(text: str) -> dict[str, Any]:
    """Parse server.cfg text and return a dict of cvar -> value."""
    return _parse_cfg(text, CVARS)


def validate(values: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation issues."""
    return _validate(values, CVARS)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def main() -> int:
    """Launch the GUI. Used by ``python -m vanguard_config_builder``."""
    from .gui.main_window import run_gui
    return run_gui()


__all__ = [
    "CATEGORIES",
    "CVARS",
    "PROFILES",
    "__version__",
    "generate_cfg",
    "main",
    "parse_cfg",
    "validate",
]
