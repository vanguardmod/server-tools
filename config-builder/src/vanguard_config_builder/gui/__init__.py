# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Tkinter GUI for the VanguardMod config-builder.

M9 split-out: ``main_window`` orchestrates the layout, ``section_panels``
and ``cfg_preview`` provide pure factory functions for the per-cvar
form rows and the right-hand preview pane respectively.
"""
from .main_window import ConfigBuilderApp, run_gui

__all__ = ["ConfigBuilderApp", "run_gui"]
