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

# ============================================================================
# VERSION
# ============================================================================
# TODO Phase 2: Read this from the VERSION file at repo root so we don't
# have two sources of truth.
__version__ = "0.1.0"


# ============================================================================
# CVAR DATABASE
# ============================================================================
# TODO Phase 2: Move this dict into data/cvars.yaml and load via PyYAML.
#               Schema should validate on load (jsonschema or pydantic).
# TODO Phase 2: Add per-cvar tooltip support in the GUI.
# TODO Phase 3: Add a `validation` field — regex string, lambda name, or
#               cross-cvar rule reference.
# TODO Phase 3: Add `requires` field (e.g. g_warmup requires g_doWarmup=1).
# TODO Phase 4: Add `since_version` so the tool can warn when generating
#               cfgs for older VanguardMod releases.
#
# Schema (current rough version):
#   key:         cvar name (str)
#   type:        'bool' | 'int' | 'string' | 'enum'
#   default:     default value
#   range:       (min, max) for int, list of options for enum, None otherwise
#   category:    'identity' | 'network' | 'match' | 'hitbox' | 'anticheat'
#   description: human-readable tooltip text
#   archive:     bool — write as `seta` (archived) vs `set` (session-only)?
#   secret:      bool — render as password input, redact in logs?

CVARS: dict[str, dict[str, Any]] = {
    # ---- Server Identity ---------------------------------------------------
    "sv_hostname": {
        "type": "string",
        "default": "VanguardMod Server",
        "range": None,
        "category": "identity",
        "description": "Server name shown in the server browser",
        "archive": True,
        "secret": False,
    },
    "g_motd": {
        "type": "string",
        "default": "",
        "range": None,
        "category": "identity",
        "description": "Message of the Day shown to connecting players",
        "archive": True,
        "secret": False,
    },
    "rconpassword": {
        "type": "string",
        "default": "",
        "range": None,
        "category": "identity",
        "description": "Remote console password (KEEP SECRET)",
        "archive": False,
        "secret": True,
    },
    "g_password": {
        "type": "string",
        "default": "",
        "range": None,
        "category": "identity",
        "description": "Server join password (leave empty for public server)",
        "archive": False,
        "secret": True,
    },

    # ---- Network Settings --------------------------------------------------
    "sv_fps": {
        "type": "int",
        "default": 20,
        "range": (20, 125),
        "category": "network",
        "description": "Server tick rate. Cup standard: 40. Public default: 20.",
        "archive": True,
        "secret": False,
    },
    "sv_maxclients": {
        "type": "int",
        "default": 32,
        "range": (2, 64),
        "category": "network",
        "description": "Maximum number of player slots",
        "archive": True,
        "secret": False,
    },
    "g_antilag": {
        "type": "bool",
        "default": 1,
        "range": None,
        "category": "network",
        "description": "Enable lag compensation for hit detection",
        "archive": True,
        "secret": False,
    },
    "g_antiwarp": {
        "type": "bool",
        "default": 1,
        "range": None,
        "category": "network",
        "description": "Enable anti-warp (rejects abnormal client movement)",
        "archive": True,
        "secret": False,
    },

    # ---- Match Rules -------------------------------------------------------
    "g_friendlyFire": {
        "type": "bool",
        "default": 1,
        "range": None,
        "category": "match",
        "description": "Allow players to damage their own teammates",
        "archive": True,
        "secret": False,
    },
    "g_doWarmup": {
        "type": "bool",
        "default": 0,
        "range": None,
        "category": "match",
        "description": "Enable warmup phase before round start",
        "archive": True,
        "secret": False,
    },
    "g_warmup": {
        "type": "int",
        "default": 30,
        "range": (0, 300),
        "category": "match",
        "description": "Warmup duration in seconds (only if g_doWarmup=1)",
        "archive": True,
        "secret": False,
    },
    "g_speed": {
        "type": "int",
        "default": 320,
        "range": (100, 999),
        "category": "match",
        "description": "Player movement speed (320 = vanilla)",
        "archive": True,
        "secret": False,
    },
    "g_gravity": {
        "type": "int",
        "default": 800,
        "range": (1, 9999),
        "category": "match",
        "description": "World gravity (800 = vanilla)",
        "archive": True,
        "secret": False,
    },
    "g_knockback": {
        "type": "int",
        "default": 1000,
        "range": (0, 9999),
        "category": "match",
        "description": "Damage knockback multiplier (1000 = vanilla)",
        "archive": True,
        "secret": False,
    },
    "team_maxSoldiers": {
        "type": "int",
        "default": -1,
        "range": (-1, 32),
        "category": "match",
        "description": "Max soldiers per team (-1 = unlimited)",
        "archive": True,
        "secret": False,
    },
    "team_maxMedics": {
        "type": "int",
        "default": -1,
        "range": (-1, 32),
        "category": "match",
        "description": "Max medics per team (-1 = unlimited)",
        "archive": True,
        "secret": False,
    },
    "team_maxEngineers": {
        "type": "int",
        "default": -1,
        "range": (-1, 32),
        "category": "match",
        "description": "Max engineers per team (-1 = unlimited)",
        "archive": True,
        "secret": False,
    },
    "team_maxFieldops": {
        "type": "int",
        "default": -1,
        "range": (-1, 32),
        "category": "match",
        "description": "Max field ops per team (-1 = unlimited)",
        "archive": True,
        "secret": False,
    },
    "team_maxCovertops": {
        "type": "int",
        "default": -1,
        "range": (-1, 32),
        "category": "match",
        "description": "Max covert ops per team (-1 = unlimited)",
        "archive": True,
        "secret": False,
    },

    # ---- Hitbox / Combat (VanguardMod-specific) ---------------------------
    "vanguard_hitbox_strict": {
        "type": "bool",
        "default": 1,
        "range": None,
        "category": "hitbox",
        "description": "Strict mode: reject hits without bone-region match",
        "archive": True,
        "secret": False,
    },
    "vanguard_hitbox_debug": {
        "type": "bool",
        "default": 0,
        "range": None,
        "category": "hitbox",
        "description": "Print VG_DIAG strict-hitbox reject lines to log",
        "archive": False,
        "secret": False,
    },
    "vanguard_diag_dump": {
        "type": "bool",
        "default": 0,
        "range": None,
        "category": "hitbox",
        "description": "One-shot capsule diagnostic dump (auto-resets)",
        "archive": False,
        "secret": False,
    },
    "vanguard_netcode_profile": {
        "type": "enum",
        "default": "public",
        "range": ["cup", "public", "custom"],
        "category": "network",
        "description": "Netcode preset: cup=40fps tight, public=20fps standard",
        "archive": True,
        "secret": False,
    },

    # ---- Anti-Cheat / Misc ------------------------------------------------
    "vanguard_dev": {
        "type": "bool",
        "default": 0,
        "range": None,
        "category": "anticheat",
        "description": "Enable dev features (gates cg_vanguardDevMultibox etc.)",
        "archive": False,
        "secret": False,
    },

    # TODO Phase 2: Add WolfGuard cvars when WolfGuard public hooks are
    #               documented (currently closed-source, only stub cvars).
    # TODO Phase 2: Add g_xpSaver, g_logSync, g_log, g_inactivity, etc.
    # TODO Phase 2: Pull full cvar list from VanguardMod
    #               docs/notes/PHASE_TOOLING_AUDIT.md when it ships.
}


# ============================================================================
# CATEGORY METADATA
# ============================================================================
# TODO Phase 2: Move into cvars.yaml top-level under `categories:` so the
# tool reads category labels and ordering from the database too.

CATEGORIES = [
    ("identity",  "Server Identity"),
    ("network",   "Network Settings"),
    ("match",     "Match Rules"),
    ("hitbox",    "Hitbox / Combat"),
    ("anticheat", "Anti-Cheat & Dev"),
]


# ============================================================================
# PROFILE TEMPLATES
# ============================================================================
# TODO Phase 2: Move each profile into data/profiles/<name>.yaml.
# TODO Phase 3: Profile inheritance — let cup.yaml extend public.yaml with
#               only the deltas, instead of duplicating values.
# TODO Phase 3: Per-profile metadata (description, target audience, since).

PROFILES: dict[str, dict[str, Any]] = {
    "Cup / Tournament": {
        "sv_fps": 40,
        "sv_maxclients": 12,
        "g_antilag": 1,
        "g_antiwarp": 1,
        "g_friendlyFire": 1,
        "g_doWarmup": 1,
        "g_warmup": 60,
        "g_speed": 320,
        "g_gravity": 800,
        "g_knockback": 1000,
        "team_maxSoldiers": 1,
        "team_maxMedics": 2,
        "team_maxEngineers": 2,
        "team_maxFieldops": 1,
        "team_maxCovertops": 1,
        "vanguard_hitbox_strict": 1,
        "vanguard_hitbox_debug": 0,
        "vanguard_netcode_profile": "cup",
        "vanguard_dev": 0,
    },
    "Public Server": {
        "sv_fps": 20,
        "sv_maxclients": 32,
        "g_antilag": 1,
        "g_antiwarp": 1,
        "g_friendlyFire": 0,
        "g_doWarmup": 0,
        "g_warmup": 0,  # warmup disabled — keep value at 0 to avoid validator warning
        "g_speed": 320,
        "g_gravity": 800,
        "g_knockback": 1000,
        "team_maxSoldiers": -1,
        "team_maxMedics": -1,
        "team_maxEngineers": -1,
        "team_maxFieldops": -1,
        "team_maxCovertops": -1,
        "vanguard_hitbox_strict": 1,
        "vanguard_hitbox_debug": 0,
        "vanguard_netcode_profile": "public",
        "vanguard_dev": 0,
    },
    "Practice / Scrim": {
        "sv_fps": 40,
        "sv_maxclients": 16,
        "g_antilag": 1,
        "g_antiwarp": 1,
        "g_friendlyFire": 1,
        "g_doWarmup": 0,
        "g_warmup": 0,  # warmup disabled for fast practice rounds
        "g_speed": 320,
        "g_gravity": 800,
        "g_knockback": 1000,
        "team_maxSoldiers": -1,
        "team_maxMedics": -1,
        "team_maxEngineers": -1,
        "team_maxFieldops": -1,
        "team_maxCovertops": -1,
        "vanguard_hitbox_strict": 1,
        "vanguard_hitbox_debug": 1,  # diagnostics on for practice
        "vanguard_netcode_profile": "cup",
        "vanguard_dev": 1,           # dev features on for practice
    },
}


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
# TODO Phase 3: Move into core/validator.py.
# TODO Phase 3: Add cross-cvar rules (e.g. "g_warmup matters only when
#               g_doWarmup=1", "sv_fps=40 needs g_antilag=1").
# TODO Phase 3: Severity levels (error / warning / info).

def validate(values: dict[str, Any]) -> list[str]:
    """Return a list of human-readable validation issues."""
    issues: list[str] = []

    for cvar, value in values.items():
        meta = CVARS.get(cvar)
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
