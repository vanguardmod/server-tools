# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Per-category tab + per-cvar row factory functions.

Pure factories — they take a parent widget, a cvar metadata dict, and
the corresponding ``tk.Variable``, and return / mutate the widget
tree. No app state, no dependencies on the package's CVARS dict.

M9 split-out from the v0.1.0 single-file ``main.py``. Phase 3 may
introduce per-type panel classes (BoolPanel, IntPanel, ...) so custom
widgets (map-rotation editor, RCON test button, ...) can be plugged
in; the current functions stay as the simple base.

TODO Phase 3: hover tooltip with full doc + default value.
TODO Phase 3: highlight row red when value is out of range.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any


def build_category_tab(
    parent: ttk.Notebook,
    cat_id: str,
    cvars: dict[str, dict[str, Any]],
    variables: dict[str, tk.Variable],
) -> ttk.Frame:
    """Build a scrollable form for every cvar in *cat_id*.

    Args:
        parent: The notebook holding the tab.
        cat_id: The category identifier (e.g. ``"network"``); only
            cvars whose ``meta["category"]`` matches end up in the
            tab.
        cvars: The flat cvar metadata dict (the v0.1.0 ``CVARS``
            shape).
        variables: Pre-built ``tk.Variable`` instances keyed by cvar
            name. The main window owns these so the same variable
            backs both the GUI input and the live preview's read.

    Returns:
        The outer frame the notebook adds as a tab.
    """
    outer = ttk.Frame(parent)

    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    inner = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=inner, anchor=tk.NW)
    inner.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )

    row = 0
    for cvar_name, meta in cvars.items():
        if meta["category"] != cat_id:
            continue
        build_cvar_row(inner, row, cvar_name, meta, variables[cvar_name])
        row += 1

    return outer


def build_cvar_row(
    parent: ttk.Frame,
    row: int,
    cvar: str,
    meta: dict[str, Any],
    var: tk.Variable,
) -> None:
    """Render a single cvar input row in *parent* at grid *row*."""
    ttk.Label(parent, text=cvar, font=("TkDefaultFont", 9, "bold")) \
        .grid(row=row, column=0, sticky=tk.W, padx=4, pady=2)

    if meta["type"] == "bool":
        widget: tk.Widget = ttk.Checkbutton(
            parent, variable=var, onvalue=1, offvalue=0,
        )
    elif meta["type"] == "int":
        rng = meta["range"]
        if rng:
            widget = ttk.Spinbox(
                parent, from_=rng[0], to=rng[1],
                textvariable=var, width=10,
            )
        else:
            widget = ttk.Entry(parent, textvariable=var, width=12)
    elif meta["type"] == "enum":
        widget = ttk.Combobox(
            parent, textvariable=var,
            values=meta["range"], state="readonly", width=14,
        )
    else:  # string
        show = "*" if meta.get("secret") else ""
        widget = ttk.Entry(parent, textvariable=var, show=show, width=30)

    widget.grid(row=row, column=1, sticky=tk.W, padx=4, pady=2)

    ttk.Label(
        parent,
        text=meta["description"],
        font=("TkDefaultFont", 8),
        foreground="#666",
    ).grid(row=row, column=2, sticky=tk.W, padx=4, pady=2)
