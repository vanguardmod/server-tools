#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""PyInstaller entry script.

PyInstaller's CLI consumes a script file, not a module spec, so we
can't point ``pyinstaller`` at ``vanguard_config_builder`` directly.
This one-liner imports the installed package's CLI and hands control
over. The release workflow points PyInstaller at this file.

For interactive use during development, run ``python -m
vanguard_config_builder`` instead — the ``__main__.py`` inside the
package does the same dispatch.
"""

from vanguard_config_builder.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
