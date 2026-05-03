# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Entry point for ``python -m vanguard_config_builder``.

Delegates to ``cli.main`` so the same dispatcher handles GUI default
and CLI subcommands. PyInstaller's ``--onefile`` bundle uses this
module as its entry script via ``pyinstaller -m vanguard_config_builder``.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
