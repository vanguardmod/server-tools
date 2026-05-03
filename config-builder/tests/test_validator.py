# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Unit tests for ``core.validator``.

Phase 2 / M3 — pure refactor. These tests exercise the rules already
present in v0.1.0; the Phase 3 expansion (severity levels, full
rule engine) gets its own additions on top.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.validator import validate  # noqa: E402

# Minimal cvar table covering each type plus the two cross-cvar rules.
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
    "g_warmup": {
        "type": "int",
        "default": 30,
        "range": (0, 300),
        "category": "match",
        "description": "warmup s",
        "archive": True,
        "secret": False,
    },
    "g_doWarmup": {
        "type": "bool",
        "default": 0,
        "range": None,
        "category": "match",
        "description": "warmup on",
        "archive": True,
        "secret": False,
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
    "vanguard_netcode_profile": {
        "type": "enum",
        "default": "public",
        "range": ["cup", "public", "custom"],
        "category": "network",
        "description": "preset",
        "archive": True,
        "secret": False,
    },
}


class TestValidator:
    def test_clean_values_yield_no_issues(self) -> None:
        values = {"sv_fps": 20, "g_doWarmup": 0, "g_warmup": 0,
                  "g_antilag": 1, "vanguard_netcode_profile": "public"}
        assert validate(values, _CVARS) == []

    def test_int_out_of_range(self) -> None:
        issues = validate({"sv_fps": 999}, _CVARS)
        assert any("out of range" in i for i in issues)

    # Phase 3 TODO: validate({"sv_fps": "abc"}) currently crashes inside
    # the cross-cvar fps>=40 rule because int("abc") is called there
    # without a guard. The single-cvar "not an integer" issue is reported
    # correctly first; the crash is in the trailing cross-check. Fix
    # together with the rule-engine rewrite — out of scope for M3
    # (pure refactor, no behavior change).

    def test_bool_invalid_value(self) -> None:
        issues = validate({"g_antilag": 7}, _CVARS)
        assert any("bool must be 0 or 1" in i for i in issues)

    def test_enum_invalid_option(self) -> None:
        issues = validate({"vanguard_netcode_profile": "bogus"}, _CVARS)
        assert any("not in" in i for i in issues)

    def test_unknown_cvar_flagged(self) -> None:
        issues = validate({"some_made_up_cvar": "value"}, _CVARS)
        assert any("unknown cvar" in i for i in issues)

    def test_warmup_without_dowarmup_warning(self) -> None:
        issues = validate({"g_warmup": 60, "g_doWarmup": 0}, _CVARS)
        assert any("g_warmup" in i and "g_doWarmup" in i for i in issues)

    def test_warmup_with_dowarmup_is_clean(self) -> None:
        # Counter-test for the cross-cvar rule: warmup positive AND
        # doWarmup=1 should not trigger the warning.
        issues = validate({"g_warmup": 60, "g_doWarmup": 1}, _CVARS)
        assert not any("g_warmup is set but" in i for i in issues)

    def test_high_fps_without_antilag_warning(self) -> None:
        issues = validate({"sv_fps": 40, "g_antilag": 0}, _CVARS)
        assert any("antilag" in i for i in issues)

    def test_high_fps_with_antilag_is_clean(self) -> None:
        issues = validate({"sv_fps": 40, "g_antilag": 1}, _CVARS)
        assert not any("antilag" in i for i in issues)
