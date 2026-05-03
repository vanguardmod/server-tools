# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Shared pytest configuration for the config-builder test suite.

The package is installed editable via `pip install -e .` (CI does
this from requirements-dev.txt), so all tests can simply
``import vanguard_config_builder`` — no sys.path tweaks needed.

The single thing this conftest does is install a tkinter stub at
import time, so importing ``vanguard_config_builder`` (which pulls
in the GUI module on-demand) doesn't blow up on a CI runner without
a display server. The stub is just enough surface for the import to
succeed; tests don't actually exercise the GUI.
"""

from __future__ import annotations

import sys
import types


def _install_tkinter_stub() -> None:
    """Inject a lightweight tkinter shim so `import` succeeds headless."""
    for name in ("tkinter", "tkinter.ttk", "tkinter.filedialog",
                 "tkinter.messagebox"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    tk = sys.modules["tkinter"]
    tk.IntVar = lambda value=0: types.SimpleNamespace(
        get=lambda: value, set=lambda v: None, trace_add=lambda *a, **kw: None,
    )
    tk.StringVar = lambda value="": types.SimpleNamespace(
        get=lambda: value, set=lambda v: None, trace_add=lambda *a, **kw: None,
    )
    for attr in ("Tk", "Text", "Canvas", "Menu", "Variable", "Widget"):
        setattr(tk, attr, object)
    for attr in ("NW", "W", "LEFT", "RIGHT", "BOTH", "X", "Y", "END",
                 "HORIZONTAL", "VERTICAL", "NONE"):
        setattr(tk, attr, attr.lower())
    tk.TclError = Exception


_install_tkinter_stub()
