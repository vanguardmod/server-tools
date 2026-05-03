# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Parse VanguardMod `server.cfg` text into a values dict.

Extracted from `main.py` during Phase 2 (M2). Behavior is unchanged
from the v0.1.0 prototype; the only structural difference is that the
cvar metadata table is now an optional parameter instead of a module
global, which lets the parser be used standalone (without the GUI's
``CVARS`` dict — useful in tests and in headless tooling that only
cares about raw parsed values).
"""

from __future__ import annotations

from typing import Any


def parse_cfg(
    text: str,
    cvars: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Parse server.cfg *text* and return a dict of cvar -> value.

    Args:
        text: Raw cfg text (newline-separated).
        cvars: Cvar metadata table for type-coercion. When provided,
            values for cvars declared as ``int`` or ``bool`` are
            coerced to ``int``; everything else (and unknown cvars)
            stays as the parsed string. When ``None`` (the default),
            no coercion happens and every value is returned as a
            string — useful for "raw view" tooling and for unit tests
            that don't want a fixture cvars table.

    Returns:
        Mapping of cvar name to value, in the order the cvars appeared
        in the input.
    """
    cvars = cvars or {}
    result: dict[str, Any] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue

        # Strip inline comments
        if "//" in line:
            line = line.split("//", 1)[0].strip()

        # Tokenize: `set CVAR "VALUE"` or `seta CVAR "VALUE"` or `cvar VALUE`
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue

        if parts[0].lower() in ("set", "seta", "sets", "setu"):
            if len(parts) < 3:
                continue
            cvar = parts[1]
            value: Any = parts[2].strip().strip('"')
        else:
            # Bare assignment e.g. `sv_hostname "Foo"`
            cvar = parts[0]
            value = parts[1].strip().strip('"')
            if len(parts) > 2:
                value = (parts[1] + " " + parts[2]).strip().strip('"')

        # Type-coerce based on known schema
        meta = cvars.get(cvar)
        if meta:
            if meta["type"] == "int":
                try:
                    value = int(value)
                except ValueError:
                    pass  # leave as string, validator will flag
            elif meta["type"] == "bool":
                try:
                    value = int(value)
                except ValueError:
                    pass

        result[cvar] = value

    return result
