#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""
VanguardMod Config Builder — rough prototype (v0.1.0)
======================================================

A desktop GUI tool for generating, validating, and editing VanguardMod
`server.cfg` files.

THIS IS THE "ROUGH VERSION" — a single-file working prototype that
serves as a scaffold for a properly structured tool. Every section
that should be extracted/modularized later is marked with TODO blocks.

DESIGN DECISIONS (locked in for the rough version)
--------------------------------------------------
- GUI framework: tkinter (stdlib, zero install dependencies, runs
  everywhere out of the box). For production we should switch to
  customtkinter (pip install customtkinter — modern look, same API)
  or PySide6 (heavier, but proper widgets). See TODO Phase 3.
- Cvar database: inline Python dict for now. Phase 2 extracts this
  into data/cvars.yaml so non-coders can extend.
- Profiles: inline dicts. Phase 2 extracts into data/profiles/*.yaml.
- Validation: minimal (range checks). Phase 3 adds rule engine.

PLANNED FINAL ARCHITECTURE
--------------------------
    config-builder/
        src/vanguard_config_builder/
            __init__.py
            main.py                  ← entry point
            gui/
                main_window.py       ← top-level window + menu
                section_panels.py    ← per-category panels (this file's tabs)
                cfg_preview.py       ← live preview widget
                dialogs.py           ← about, settings, etc.
            core/
                cvar_database.py     ← loads cvars.yaml
                cfg_parser.py        ← parse existing server.cfg
                cfg_generator.py     ← write server.cfg from values
                validator.py         ← rule engine
                profiles.py          ← load profile templates
            data/
                cvars.yaml
                profiles/
                    cup.yaml
                    public.yaml
                    scrim.yaml
        tests/
            test_parser.py
            test_validator.py
            test_generator.py

USAGE
-----
    python main.py
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from core.cfg_generator import generate_cfg as _generate_cfg
from core.cfg_parser import parse_cfg as _parse_cfg
from core.cvar_database import default_database_path, load_cvar_database
from core.profiles import default_profiles_path, load_profile_set
from core.validator import validate as _validate

# ============================================================================
# VERSION
# ============================================================================
# TODO Phase 2: Read this from the VERSION file at repo root so we don't
# have two sources of truth.
__version__ = "0.1.0"


# ============================================================================
# CVAR DATABASE & CATEGORIES (loaded from data/cvars.yaml)
# ============================================================================
# Phase 2 / M5: cvars and categories are now externalized to YAML so
# server admins can extend the database without touching Python. The
# inline dicts that lived here in v0.1.0 were copied verbatim into
# data/cvars.yaml; schema is enforced on load (pydantic v2).
#
# CVARS and CATEGORIES are kept at module level in their v0.1.0 shapes
# (flat dict-of-dicts and list-of-tuples respectively) for backward
# compatibility with the v0.1.0 GUI layout code and the smoke test
# suite. M9 will refactor the GUI to consume the typed CvarDatabase
# directly and these legacy shims can go.
#
# TODO Phase 3: Add per-cvar tooltip support in the GUI.
# TODO Phase 3: Add a `validation` field — regex string, lambda name, or
#               cross-cvar rule reference.
# TODO Phase 3: Add `requires` field (e.g. g_warmup requires g_doWarmup=1).
# TODO Phase 4: Surface `since_version` warnings when generating cfgs
#               for older VanguardMod releases.

_DATABASE = load_cvar_database(default_database_path())

# v0.1.0-shaped flat dict — what the GUI and smoke tests inspect.
# Generated from the loaded schema; the YAML is the source of truth.
CVARS: dict[str, dict[str, Any]] = _DATABASE.as_legacy_dict()

# v0.1.0-shaped list of (id, label) tuples — same iteration semantics
# the menu and tab construction code already relied on.
CATEGORIES: list[tuple[str, str]] = [
    (cat.id, cat.label) for cat in _DATABASE.categories
]



# ============================================================================
# PROFILE TEMPLATES (loaded from data/profiles/)
# ============================================================================
# Phase 2 / M7: profiles are now loaded from individual YAML files with
# single-string `extends:` inheritance. The exposed PROFILES dict
# preserves the v0.1.0 shape (display-name keys, flat values dicts) so
# the GUI's Quick-Profile buttons and the smoke suite see no
# difference.
#
# TODO Phase 3: surface per-profile description in the GUI (tooltip
#               or status-bar caption when the profile is loaded).

_PROFILE_SET = load_profile_set(default_profiles_path())


def _build_legacy_profiles_dict() -> dict[str, dict[str, Any]]:
    """Render the loaded ProfileSet into the v0.1.0 inline shape.

    Each user-visible profile resolves through its inheritance chain;
    the human-readable ``profile_name`` becomes the dict key (matching
    the v0.1.0 keys "Cup / Tournament", "Public Server", "Practice /
    Scrim") and the merged values dict becomes the value. Cvar names
    are validated against CVARS during the resolve so a typo in a
    profile YAML fails at module import, not silently in the GUI.
    """
    known = set(CVARS.keys())
    out: dict[str, dict[str, Any]] = {}
    for stem in _PROFILE_SET.list_names():
        resolved = _PROFILE_SET.resolve(stem, valid_cvars=known)
        out[resolved.profile_name] = resolved.values
    return out


PROFILES: dict[str, dict[str, Any]] = _build_legacy_profiles_dict()


# ============================================================================
# CFG GENERATOR
# ============================================================================
# Phase 2 / M1: implementation moved to core/cfg_generator.py. This thin
# wrapper preserves the v0.1.0 call signature so existing tests and the
# GUI keep working unchanged. Phase 3 may revisit this once the GUI is
# split — at that point the wrapper can drop entirely.
# TODO Phase 3: Multi-output mode (e.g. one base.cfg + N instance overrides).
# TODO Phase 3: Group cvars by category in the output with section comments.

def generate_cfg(values: dict[str, Any], profile_name: str = "custom",
                 with_header: bool = True) -> str:
    """Render `values` into server.cfg syntax (delegates to core)."""
    return _generate_cfg(
        values, CVARS, __version__,
        profile_name=profile_name, with_header=with_header,
    )


# ============================================================================
# CFG PARSER
# ============================================================================
# Phase 2 / M2: implementation moved to core/cfg_parser.py. Wrapper
# preserves the v0.1.0 call signature and injects CVARS for type
# coercion. Removed in M9.
# TODO Phase 3: Handle `bind`, `exec`, conditionals, and other non-cvar
#               directives — currently we silently skip them.
# TODO Phase 3: Preserve comments and re-emit on round-trip.
# TODO Phase 3: Detect malformed lines and report line numbers.

def parse_cfg(text: str) -> dict[str, Any]:
    """Parse server.cfg text and return a dict of cvar -> value."""
    return _parse_cfg(text, CVARS)


# ============================================================================
# VALIDATOR
# ============================================================================
# Phase 2 / M3: implementation moved to core/validator.py. Pure refactor,
# no new rules — those land in Phase 3.

def validate(values: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation issues."""
    return _validate(values, CVARS)


# ============================================================================
# GUI APPLICATION
# ============================================================================
# TODO Phase 2: Split into gui/main_window.py + gui/section_panels.py +
#               gui/cfg_preview.py.
# TODO Phase 3: Switch tkinter → customtkinter for a modern look. The widget
#               API is mostly compatible (CTkButton, CTkEntry, etc.).
# TODO Phase 3: Add About dialog, Settings dialog, recent-files menu.
# TODO Phase 4: Drag-and-drop import (tkinterdnd2 or native).
# TODO Phase 4: Multi-server mode (manage N server.cfg files in tabs).

class ConfigBuilderApp:
    """Top-level GUI controller."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"VanguardMod Config Builder v{__version__}")
        self.root.geometry("1100x720")

        # Live values, keyed by cvar. Backed by tk.Variable instances so
        # GUI edits propagate automatically into the preview.
        # TODO Phase 2: Wrap this in a proper Model class with observers.
        self.vars: dict[str, tk.Variable] = {}
        for cvar, meta in CVARS.items():
            if meta["type"] == "int":
                v = tk.IntVar(value=int(meta["default"]))
            elif meta["type"] == "bool":
                v = tk.IntVar(value=int(meta["default"]))
            else:
                v = tk.StringVar(value=str(meta["default"]))
            v.trace_add("write", lambda *_: self._refresh_preview())
            self.vars[cvar] = v

        self.current_profile_name = tk.StringVar(value="custom")

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

        # TODO Phase 2: Help menu with About dialog, link to docs.
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

        # ---- Left side: profile picker + tabbed editor --------------------
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
            tab = self._build_category_tab(notebook, cat_id)
            notebook.add(tab, text=cat_label)

        # ---- Right side: live preview + status ----------------------------
        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        ttk.Label(right, text="Live Preview (server.cfg)",
                  font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W)

        self.preview = tk.Text(right, wrap=tk.NONE, font=("TkFixedFont", 9))
        self.preview.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # TODO Phase 3: Add scrollbars to preview, syntax highlighting,
        #               find/replace.

        status_frame = ttk.LabelFrame(right, text="Validation")
        status_frame.pack(fill=tk.X, pady=(8, 0))
        self.status = tk.Text(status_frame, height=6, wrap=tk.WORD,
                              font=("TkDefaultFont", 9))
        self.status.pack(fill=tk.X)

        button_row = ttk.Frame(right)
        button_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(button_row, text="Refresh",
                   command=self._refresh_preview).pack(side=tk.LEFT)
        ttk.Button(button_row, text="Export...",
                   command=self._export_cfg).pack(side=tk.RIGHT)

    def _build_category_tab(self, parent: ttk.Notebook, cat_id: str) -> ttk.Frame:
        """Build a scrollable form for all cvars in `cat_id`."""
        # TODO Phase 2: Extract this into gui/section_panels.py and have
        # one panel class per widget type (BoolPanel, IntPanel, etc.) so
        # custom panels (e.g. map-rotation editor) can be plugged in.

        outer = ttk.Frame(parent)

        # Scrollable canvas pattern (tkinter forms get long fast)
        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL,
                                  command=canvas.yview)
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
        for cvar, meta in CVARS.items():
            if meta["category"] != cat_id:
                continue
            self._build_cvar_row(inner, row, cvar, meta)
            row += 1

        return outer

    def _build_cvar_row(self, parent: ttk.Frame, row: int,
                        cvar: str, meta: dict[str, Any]) -> None:
        """Render a single cvar input row."""
        ttk.Label(parent, text=cvar, font=("TkDefaultFont", 9, "bold")) \
            .grid(row=row, column=0, sticky=tk.W, padx=4, pady=2)

        var = self.vars[cvar]
        if meta["type"] == "bool":
            widget = ttk.Checkbutton(parent, variable=var,
                                     onvalue=1, offvalue=0)
        elif meta["type"] == "int":
            rng = meta["range"]
            if rng:
                widget = ttk.Spinbox(parent, from_=rng[0], to=rng[1],
                                     textvariable=var, width=10)
            else:
                widget = ttk.Entry(parent, textvariable=var, width=12)
        elif meta["type"] == "enum":
            widget = ttk.Combobox(parent, textvariable=var,
                                  values=meta["range"], state="readonly",
                                  width=14)
        else:  # string
            show = "*" if meta.get("secret") else ""
            widget = ttk.Entry(parent, textvariable=var, show=show, width=30)

        widget.grid(row=row, column=1, sticky=tk.W, padx=4, pady=2)

        # Description as muted helper text
        ttk.Label(parent, text=meta["description"],
                  font=("TkDefaultFont", 8), foreground="#666") \
            .grid(row=row, column=2, sticky=tk.W, padx=4, pady=2)

        # TODO Phase 3: Add hover tooltip with full doc + default value.
        # TODO Phase 3: Highlight row red when value is out of range.

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
                # IntVar can throw if the field is empty mid-edit
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
            messagebox.showinfo("Import",
                                f"Imported {len(parsed)} cvars from\n{path}")
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
            text = generate_cfg(self._collect_values(),
                                profile_name=self.current_profile_name.get())
            Path(path).write_text(text, encoding="utf-8")
            messagebox.showinfo("Export", f"Saved to\n{path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    # ----------------------------------------------------------------------
    # Preview & validation refresh
    # ----------------------------------------------------------------------
    def _refresh_preview(self) -> None:
        # Tk traces fire before __init__ finishes building the preview widget;
        # guard against that.
        if not hasattr(self, "preview"):
            return
        values = self._collect_values()
        text = generate_cfg(values,
                            profile_name=self.current_profile_name.get())
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", text)

        issues = validate(values)
        self.status.delete("1.0", tk.END)
        if not issues:
            self.status.insert("1.0", "✓ No issues found")
        else:
            self.status.insert("1.0", "\n".join(f"• {i}" for i in issues))


# ============================================================================
# CLI ENTRY POINT
# ============================================================================
# TODO Phase 2: Add argparse — --headless mode that loads a profile +
#               writes a cfg without launching the GUI (useful for CI,
#               scripted server provisioning, Ansible roles).
# TODO Phase 2: Add --validate-only mode for an existing cfg.
# TODO Phase 4: Add --diff mode to compare two cfgs side by side.

def main() -> int:
    root = tk.Tk()
    # TODO Phase 3: ttk theme selection — 'clam', 'alt', etc., or
    #               sv_ttk for a modern look without changing widgets.
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    ConfigBuilderApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
