# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Right-hand preview pane: cfg text + validation status + buttons.

Pure factory + render functions, no class. The main window owns the
widgets and re-renders on every cvar edit. M9 split-out from the
v0.1.0 single-file ``main.py``.

TODO Phase 3: scrollbars on the preview, syntax highlighting,
              find/replace.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk


@dataclass
class PreviewWidgets:
    """Handles to the preview pane's widgets the main window needs.

    The dataclass exists so the factory can return everything the
    caller wires up without a tuple-of-five-things signature that's
    impossible to extend.
    """

    preview_text: tk.Text
    status_text: tk.Text


def build_preview_panel(
    parent: ttk.Frame,
    on_refresh: Callable[[], None],
    on_export: Callable[[], None],
) -> PreviewWidgets:
    """Build the preview + status + button-row pane inside *parent*.

    Args:
        parent: The right-hand frame inside the paned window.
        on_refresh: Called when the user clicks the Refresh button.
        on_export: Called when the user clicks the Export button.

    Returns:
        Widget handles the caller stores so it can re-render the
        preview / clear the status line / etc.
    """
    ttk.Label(
        parent,
        text="Live Preview (server.cfg)",
        font=("TkDefaultFont", 10, "bold"),
    ).pack(anchor=tk.W)

    preview = tk.Text(parent, wrap=tk.NONE, font=("TkFixedFont", 9))
    preview.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    status_frame = ttk.LabelFrame(parent, text="Validation")
    status_frame.pack(fill=tk.X, pady=(8, 0))
    status = tk.Text(
        status_frame,
        height=6,
        wrap=tk.WORD,
        font=("TkDefaultFont", 9),
    )
    status.pack(fill=tk.X)

    button_row = ttk.Frame(parent)
    button_row.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(button_row, text="Refresh", command=on_refresh) \
        .pack(side=tk.LEFT)
    ttk.Button(button_row, text="Export...", command=on_export) \
        .pack(side=tk.RIGHT)

    return PreviewWidgets(preview_text=preview, status_text=status)


def render_preview(
    widgets: PreviewWidgets,
    cfg_text: str,
    issues: list[str],
) -> None:
    """Push *cfg_text* and *issues* into the preview / status widgets.

    No business logic — just widget bookkeeping. The caller is
    responsible for calling ``generate_cfg`` and ``validate``.
    """
    widgets.preview_text.delete("1.0", tk.END)
    widgets.preview_text.insert("1.0", cfg_text)

    widgets.status_text.delete("1.0", tk.END)
    if not issues:
        widgets.status_text.insert("1.0", "✓ No issues found")
    else:
        widgets.status_text.insert(
            "1.0", "\n".join(f"• {i}" for i in issues),
        )
