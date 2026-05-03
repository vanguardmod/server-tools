# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Top-level GUI controller.

``ConfigBuilderApp`` orchestrates the v0.1.0 widget layout — paned
window with tabbed editor on the left, live cfg preview + validation
status on the right — using the factories in
``section_panels`` and ``cfg_preview``. The class itself is light;
heavy lifting (rendering, parsing, validating) lives in the
package's wrapper functions which delegate to ``core/``.

M9 split-out from the v0.1.0 single-file ``main.py``.

TODO Phase 3: switch tkinter → customtkinter for a modern look.
TODO Phase 3: settings dialog, recent-files menu, hover tooltips.
TODO Phase 4: drag-and-drop import; multi-server tab mode.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .. import (
    CATEGORIES,
    CVARS,
    PROFILES,
    __version__,
    generate_cfg,
    parse_cfg,
    validate,
)
from .cfg_preview import PreviewWidgets, build_preview_panel, render_preview
from .section_panels import build_category_tab


class ConfigBuilderApp:
    """Top-level GUI controller wired up against the package's data."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"VanguardMod Config Builder v{__version__}")
        self.root.geometry("1100x720")

        # Live values, keyed by cvar. Backed by tk.Variable instances
        # so GUI edits propagate automatically into the preview via
        # the trace we attach below.
        self.vars: dict[str, tk.Variable] = {}
        for cvar, meta in CVARS.items():
            v: tk.Variable
            if meta["type"] == "int":
                v = tk.IntVar(value=int(meta["default"]))
            elif meta["type"] == "bool":
                v = tk.IntVar(value=int(meta["default"]))
            else:
                v = tk.StringVar(value=str(meta["default"]))
            v.trace_add("write", lambda *_: self._refresh_preview())
            self.vars[cvar] = v

        self.current_profile_name = tk.StringVar(value="custom")
        self._preview: PreviewWidgets | None = None

        self._build_menu()
        self._build_layout()
        self._refresh_preview()

    # ----------------------------------------------------------------------
    # Menu bar
    # ----------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import server.cfg...", command=self._import_cfg)
        filemenu.add_command(label="Export server.cfg...", command=self._export_cfg)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        profmenu = tk.Menu(menubar, tearoff=0)
        for name in PROFILES:
            profmenu.add_command(
                label=f"Load: {name}",
                command=lambda n=name: self._load_profile(n),
            )
        menubar.add_cascade(label="Profile", menu=profmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(
            label="About",
            command=lambda: messagebox.showinfo(
                "About",
                f"VanguardMod Config Builder v{__version__}\n\n"
                "Generates and validates server.cfg files for VanguardMod.\n"
                "https://github.com/vanguardmod/server-tools",
            ),
        )
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)

    # ----------------------------------------------------------------------
    # Main layout: left = section tabs, right = live preview
    # ----------------------------------------------------------------------
    def _build_layout(self) -> None:
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---- Left: profile picker + tabbed editor ------------------------
        left = ttk.Frame(paned)
        paned.add(left, weight=3)

        profile_frame = ttk.LabelFrame(left, text="Quick Profile")
        profile_frame.pack(fill=tk.X, pady=(0, 8))
        for name in PROFILES:
            ttk.Button(
                profile_frame,
                text=name,
                command=lambda n=name: self._load_profile(n),
            ).pack(side=tk.LEFT, padx=4, pady=4)

        notebook = ttk.Notebook(left)
        notebook.pack(fill=tk.BOTH, expand=True)
        for cat_id, cat_label in CATEGORIES:
            tab = build_category_tab(notebook, cat_id, CVARS, self.vars)
            notebook.add(tab, text=cat_label)

        # ---- Right: live preview + status -------------------------------
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        self._preview = build_preview_panel(
            right,
            on_refresh=self._refresh_preview,
            on_export=self._export_cfg,
        )

    # ----------------------------------------------------------------------
    # State <-> values plumbing
    # ----------------------------------------------------------------------
    def _collect_values(self) -> dict[str, Any]:
        """Snapshot the current GUI state into a plain dict."""
        out: dict[str, Any] = {}
        for cvar, var in self.vars.items():
            try:
                out[cvar] = var.get()
            except tk.TclError:
                # IntVar can throw if the field is empty mid-edit.
                out[cvar] = CVARS[cvar]["default"]
        return out

    def _apply_values(self, values: dict[str, Any]) -> None:
        """Push a values dict back into the GUI."""
        for cvar, value in values.items():
            if cvar in self.vars:
                try:
                    self.vars[cvar].set(value)
                except tk.TclError:
                    pass

    # ----------------------------------------------------------------------
    # Profile / import / export actions
    # ----------------------------------------------------------------------
    def _load_profile(self, name: str) -> None:
        if name not in PROFILES:
            return
        self._apply_values(PROFILES[name])
        self.current_profile_name.set(name)
        self._refresh_preview()

    def _import_cfg(self) -> None:
        path = filedialog.askopenfilename(
            title="Import server.cfg",
            filetypes=[("Config files", "*.cfg"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            parsed = parse_cfg(text)
            self._apply_values(parsed)
            self.current_profile_name.set(f"imported:{Path(path).name}")
            messagebox.showinfo(
                "Import",
                f"Imported {len(parsed)} cvars from\n{path}",
            )
        except Exception as exc:  # noqa: BLE001 — user-facing error
            messagebox.showerror("Import failed", str(exc))

    def _export_cfg(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save server.cfg",
            defaultextension=".cfg",
            filetypes=[("Config files", "*.cfg"), ("All files", "*.*")],
            initialfile="server.cfg",
        )
        if not path:
            return
        try:
            text = generate_cfg(
                self._collect_values(),
                profile_name=self.current_profile_name.get(),
            )
            Path(path).write_text(text, encoding="utf-8")
            messagebox.showinfo("Export", f"Saved to\n{path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    # ----------------------------------------------------------------------
    # Preview & validation refresh
    # ----------------------------------------------------------------------
    def _refresh_preview(self) -> None:
        # Tk traces fire before __init__ finishes building the preview
        # widget; guard against that.
        if self._preview is None:
            return
        values = self._collect_values()
        text = generate_cfg(
            values, profile_name=self.current_profile_name.get(),
        )
        issues = validate(values)
        render_preview(self._preview, text, issues)


def run_gui() -> int:
    """Start the GUI event loop. Used by ``main()`` and the CLI default."""
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    ConfigBuilderApp(root)
    root.mainloop()
    return 0
