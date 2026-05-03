# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Unit tests for ``core.cfg_parser``.

Like ``test_cfg_generator.py``, these tests hit the extracted core
function directly — no GUI import, no tkinter stub. The smoke suite
keeps a round-trip check that exercises generator + parser together
through the main.py wrappers.
"""
from __future__ import annotations

from vanguard_config_builder.core.cfg_parser import parse_cfg

# Minimal cvar table for type-coercion behavior. ``parse_cfg`` accepts
# ``cvars=None`` (the default) and returns raw strings in that mode;
# tests that care about coercion pass this table explicitly.
_CVARS: dict[str, dict[str, object]] = {
    "sv_fps": {
        "type": "int",
        "default": 20,
        "range": (20, 125),
        "category": "network",
        "description": "tick rate",
        "archive": True,
        "secret": False,
    },
    "g_password": {
        "type": "string",
        "default": "",
        "range": None,
        "category": "identity",
        "description": "join pw",
        "archive": False,
        "secret": True,
    },
    "g_antilag": {
        "type": "bool",
        "default": 1,
        "range": None,
        "category": "network",
        "description": "lag comp",
        "archive": True,
        "secret": False,
    },
}


class TestParser:
    def test_parses_basic_seta(self) -> None:
        result = parse_cfg('seta sv_fps "40"', _CVARS)
        assert result == {"sv_fps": 40}

    def test_parses_basic_set(self) -> None:
        result = parse_cfg('set g_password "secret"', _CVARS)
        assert result == {"g_password": "secret"}

    def test_skips_comments(self) -> None:
        text = "// this is a comment\nseta sv_fps \"40\"\n// another"
        assert parse_cfg(text, _CVARS) == {"sv_fps": 40}

    def test_strips_inline_comments(self) -> None:
        result = parse_cfg('seta sv_fps "40" // tickrate', _CVARS)
        assert result == {"sv_fps": 40}

    def test_skips_blank_lines(self) -> None:
        text = "\n\nseta sv_fps \"40\"\n\n"
        assert parse_cfg(text, _CVARS) == {"sv_fps": 40}

    def test_coerces_int_types(self) -> None:
        result = parse_cfg('seta sv_fps "40"', _CVARS)
        assert isinstance(result["sv_fps"], int)

    def test_coerces_bool_to_int(self) -> None:
        result = parse_cfg('seta g_antilag "1"', _CVARS)
        assert result["g_antilag"] == 1
        assert isinstance(result["g_antilag"], int)

    def test_no_cvars_means_no_coercion(self) -> None:
        # When the caller doesn't pass a cvars table (e.g. raw-view tooling),
        # everything stays as a string regardless of type.
        result = parse_cfg('seta sv_fps "40"')
        assert result == {"sv_fps": "40"}

    def test_unknown_cvar_kept_verbatim(self) -> None:
        result = parse_cfg('seta some_future_cvar "xyz"', _CVARS)
        assert result == {"some_future_cvar": "xyz"}

    def test_handles_setu_and_sets_keywords(self) -> None:
        text = 'setu sv_fps "40"\nsets sv_fps "60"'
        result = parse_cfg(text, _CVARS)
        # Last write wins; both keywords are accepted as set-aliases.
        assert result == {"sv_fps": 60}

    def test_int_value_with_garbage_falls_back_to_string(self) -> None:
        # Coercion is best-effort; bad ints stay as strings so the
        # validator can flag them with a useful message.
        result = parse_cfg('seta sv_fps "not-a-number"', _CVARS)
        assert result == {"sv_fps": "not-a-number"}
