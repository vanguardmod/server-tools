# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Validate a values dict against the cvar schema.

Extracted from `main.py` during Phase 2 (M3) — pure refactor, no new
rules. The Phase 3 work (severity levels, full cross-cvar rule engine,
config-driven rules from cvars.yaml) lands separately on top of this
module.

The validator returns a list of human-readable issue strings. Callers
decide how to surface them (the GUI renders them in the validation
panel; the CLI's ``validate`` subcommand prints them and exits non-zero
when the list is non-empty).
"""

from __future__ import annotations

from typing import Any


def validate(
    values: dict[str, Any],
    cvars: dict[str, dict[str, Any]],
) -> list[str]:
    """Return a list of human-readable validation issues.

    Args:
        values: Mapping of cvar name to current value (the GUI's live
            state, or a parsed cfg).
        cvars: Cvar metadata table — used for type checks, range
            checks, enum membership, and detecting unknown cvars.

    Returns:
        Empty list when *values* is fully valid. Otherwise one short
        string per problem, suitable for direct rendering in a status
        panel or CLI output.
    """
    issues: list[str] = []

    for cvar, value in values.items():
        meta = cvars.get(cvar)
        if not meta:
            issues.append(f"unknown cvar: {cvar}")
            continue

        if meta["type"] == "int":
            try:
                ivalue = int(value)
            except (TypeError, ValueError):
                issues.append(f"{cvar}: value '{value}' is not an integer")
                continue
            rng = meta["range"]
            if rng and not (rng[0] <= ivalue <= rng[1]):
                issues.append(
                    f"{cvar}: value {ivalue} out of range "
                    f"[{rng[0]}..{rng[1]}]"
                )

        elif meta["type"] == "bool":
            if value not in (0, 1, "0", "1"):
                issues.append(f"{cvar}: bool must be 0 or 1, got '{value}'")

        elif meta["type"] == "enum":
            options = meta["range"] or []
            if value not in options:
                issues.append(
                    f"{cvar}: value '{value}' not in {options}"
                )

    # ---- Cross-cvar sanity checks (rough, expand in Phase 3) --------------
    if values.get("g_doWarmup") in (0, "0") and int(values.get("g_warmup", 0)) > 0:
        issues.append(
            "g_warmup is set but g_doWarmup=0 — warmup will be ignored"
        )

    if int(values.get("sv_fps", 20)) >= 40 and values.get("g_antilag") in (0, "0"):
        issues.append(
            "sv_fps>=40 without g_antilag=1 is unusual for high-tickrate play"
        )

    return issues
