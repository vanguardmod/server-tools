#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Command-line interface for the VanguardMod config-builder.

The CLI is a thin layer over the same ``core/`` modules the GUI
consumes, so server admins can script profile rendering and config
validation in CI / Ansible / cron without touching the desktop UI.

Subcommands:
  generate       — render a profile to a server.cfg file
  validate       — check an existing server.cfg for problems
  list-profiles  — print the bundled profiles
  list-cvars     — print the known cvar database (filterable / JSON)
  diff           — diff two cfg files cvar-by-cvar

When invoked without a subcommand the GUI launches, preserving the
v0.1.0 double-click behavior. The pyproject.toml ``[project.scripts]``
entry that drives the ``vanguard-config-builder`` console script
switches from ``main:main`` to ``cli:main`` in M9 alongside the
src/-layout repackage; until then the CLI is reachable as
``python cli.py ...``.

Exit codes:
  0  success
  2  validation issues found (``validate``, or ``generate --strict``)
  3  IO / configuration error (file not found, profile not found, …)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .core.cfg_generator import generate_cfg
from .core.cfg_parser import parse_cfg
from .core.cvar_database import (
    CvarDatabase,
    CvarDatabaseError,
    default_database_path,
    load_cvar_database,
)
from .core.profiles import (
    ProfileError,
    ProfileSet,
    default_profiles_path,
    load_profile_set,
)
from .core.validator import validate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_VALIDATION = 2
EXIT_IO = 3


# ---------------------------------------------------------------------------
# Subcommand handlers — each returns the exit code
# ---------------------------------------------------------------------------
def cmd_generate(
    args: argparse.Namespace,
    legacy_cvars: dict[str, dict[str, Any]],
    ps: ProfileSet,
    version: str,
) -> int:
    """Render a profile to a server.cfg file."""
    try:
        resolved = ps.resolve(args.profile, valid_cvars=set(legacy_cvars))
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_IO

    if args.strict:
        issues = validate(resolved.values, legacy_cvars)
        if issues:
            print(f"error: profile {args.profile!r} has validation issues:",
                  file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            print("hint: re-run with --no-strict to write anyway",
                  file=sys.stderr)
            return EXIT_VALIDATION

    cfg_text = generate_cfg(
        resolved.values,
        legacy_cvars,
        version,
        profile_name=resolved.profile_name,
        with_header=not args.no_header,
    )

    try:
        args.output.write_text(cfg_text, encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write to {args.output}: {exc}", file=sys.stderr)
        return EXIT_IO

    print(f"wrote {args.output} ({len(cfg_text.splitlines())} lines)",
          file=sys.stderr)
    return EXIT_SUCCESS


def cmd_validate(
    args: argparse.Namespace,
    legacy_cvars: dict[str, dict[str, Any]],
) -> int:
    """Check a cfg file against the cvar schema and cross-cvar rules."""
    try:
        text = args.file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return EXIT_IO

    values = parse_cfg(text, legacy_cvars)
    issues = validate(values, legacy_cvars)

    if args.format == "json":
        json.dump(
            {
                "file": str(args.file),
                "valid": not issues,
                "issues": issues,
                "cvar_count": len(values),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        if issues:
            print(f"{args.file}: {len(issues)} issue(s):")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"{args.file}: OK ({len(values)} cvars)")

    return EXIT_VALIDATION if issues else EXIT_SUCCESS


def cmd_list_profiles(ps: ProfileSet) -> int:
    """Print the bundled, user-visible profiles."""
    for stem in ps.list_names():
        try:
            resolved = ps.resolve(stem)
        except ProfileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_IO
        chain = " <- ".join(resolved.chain)
        print(f"{stem:10s}  {resolved.profile_name}")
        if resolved.description:
            print(f"            {resolved.description}")
        print(f"            (chain: {chain}, {len(resolved.values)} cvars)")
    return EXIT_SUCCESS


def cmd_list_cvars(args: argparse.Namespace, db: CvarDatabase) -> int:
    """Print the known cvar database, optionally filtered by category."""
    rows = [
        (name, cvar)
        for name, cvar in db.cvars.items()
        if not args.category or cvar.category == args.category
    ]

    if args.format == "json":
        out = [
            {
                "name": name,
                "type": cvar.type,
                "default": cvar.default,
                "category": cvar.category,
                "description": cvar.description,
                "archive": cvar.archive,
                "secret": cvar.secret,
            }
            for name, cvar in rows
        ]
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not rows:
            print(f"(no cvars matched category {args.category!r})",
                  file=sys.stderr)
            return EXIT_SUCCESS
        for name, cvar in rows:
            secret_marker = " [SECRET]" if cvar.secret else ""
            print(
                f"{name:30s}  {cvar.type:8s}  {cvar.category:10s}  "
                f"default={cvar.default!r}{secret_marker}"
            )
    return EXIT_SUCCESS


def cmd_diff(
    args: argparse.Namespace,
    legacy_cvars: dict[str, dict[str, Any]],
) -> int:
    """Diff two cfg files cvar-by-cvar."""
    try:
        a_values = parse_cfg(
            args.a.read_text(encoding="utf-8", errors="replace"),
            legacy_cvars,
        )
        b_values = parse_cfg(
            args.b.read_text(encoding="utf-8", errors="replace"),
            legacy_cvars,
        )
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_IO

    keys = sorted(set(a_values) | set(b_values))
    diffs: list[str] = []
    for key in keys:
        if key not in a_values:
            diffs.append(f"+ {key} = {b_values[key]!r}")
        elif key not in b_values:
            diffs.append(f"- {key} = {a_values[key]!r}")
        elif a_values[key] != b_values[key]:
            diffs.append(
                f"~ {key}: {a_values[key]!r} -> {b_values[key]!r}"
            )

    if not diffs:
        print("(no differences)")
    else:
        print(f"# {args.a} vs {args.b} ({len(diffs)} change(s))")
        for line in diffs:
            print(line)
    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Argparse setup
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="vanguard-config-builder",
        description=(
            "Generate and validate VanguardMod server.cfg files. "
            "Run without a subcommand to launch the GUI."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ---- generate -------------------------------------------------------
    g = sub.add_parser(
        "generate",
        help="Render a profile to a server.cfg file",
        description=(
            "Resolve PROFILE through its inheritance chain, validate "
            "against the cvar schema (unless --no-strict), and write "
            "the result to OUTPUT."
        ),
    )
    g.add_argument("--profile", required=True, metavar="NAME",
                   help="Profile filename stem (e.g. cup, public, scrim)")
    g.add_argument("-o", "--output", required=True, type=Path,
                   metavar="PATH",
                   help="Where to write the rendered server.cfg")
    g.add_argument("--no-header", action="store_true",
                   help="Skip the metadata header block")
    g.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail with exit 2 if validation finds issues "
             "(default: enabled; pass --no-strict to write anyway)",
    )

    # ---- validate -------------------------------------------------------
    v = sub.add_parser(
        "validate",
        help="Validate an existing server.cfg file",
        description=(
            "Parse FILE, check every cvar against the schema (type, "
            "range, enum membership) and the cross-cvar sanity rules, "
            "and report issues. Exits non-zero when issues are found."
        ),
    )
    v.add_argument("file", type=Path, metavar="FILE",
                   help="Path to a server.cfg file")
    v.add_argument("--format", choices=["text", "json"], default="text",
                   help="Output format (default: text)")

    # ---- list-profiles --------------------------------------------------
    sub.add_parser(
        "list-profiles",
        help="List bundled profiles",
        description="Print the user-visible profiles bundled with the tool.",
    )

    # ---- list-cvars -----------------------------------------------------
    lc = sub.add_parser(
        "list-cvars",
        help="List known cvars",
        description="Print every cvar known to the tool, with optional "
                    "filtering by category.",
    )
    lc.add_argument("--category", metavar="ID",
                    help="Restrict to one category (e.g. network)")
    lc.add_argument("--format", choices=["text", "json"], default="text",
                    help="Output format (default: text)")

    # ---- diff -----------------------------------------------------------
    d = sub.add_parser(
        "diff",
        help="Diff two cfg files cvar-by-cvar",
        description="Parse two server.cfg files and report cvar-level "
                    "additions, removals, and value changes.",
    )
    d.add_argument("a", type=Path, metavar="A",
                   help="First cfg file")
    d.add_argument("b", type=Path, metavar="B",
                   help="Second cfg file")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Pass *argv* in tests; falls back to sys.argv."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # No subcommand → launch the GUI. Lazy import so headless commands
    # don't pay the tkinter import cost up front.
    if args.command is None:
        from .gui.main_window import run_gui  # noqa: PLC0415 — intentional lazy
        return run_gui()

    # Headless commands share a single load of the database + profile set.
    try:
        db = load_cvar_database(default_database_path())
    except CvarDatabaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_IO

    legacy_cvars = db.as_legacy_dict()

    try:
        ps = load_profile_set(default_profiles_path())
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_IO

    version = __version__

    if args.command == "generate":
        return cmd_generate(args, legacy_cvars, ps, version)
    if args.command == "validate":
        return cmd_validate(args, legacy_cvars)
    if args.command == "list-profiles":
        return cmd_list_profiles(ps)
    if args.command == "list-cvars":
        return cmd_list_cvars(args, db)
    if args.command == "diff":
        return cmd_diff(args, legacy_cvars)

    # Unreachable — argparse rejects unknown subcommands before this.
    parser.print_help()
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
