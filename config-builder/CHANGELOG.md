# Changelog

All notable changes to **config-builder** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tags follow the monorepo prefix convention: `config-builder-vMAJOR.MINOR.PATCH`.

## [Unreleased]

### Planned

- Tooltips on every cvar field with full doc + default value
- Switch GUI from tkinter to customtkinter for modern look
- Cross-cvar validation rule engine driven from `cvars.yaml`
- Live profile reload (re-pick up edits without restart)
- Per-cvar `requires` field (e.g. `g_warmup` only valid with `g_doWarmup=1`)
- Surface `since_version` / `deprecated` warnings in the GUI

## [0.2.0] — 2026-05-03

This release lifts the v0.1.0 single-file prototype into an
extensible product. Server admins can now add cvars, build profiles,
and script the tool from CI / Ansible without touching Python.

### Added

- **Externalized cvar database** at
  `data/cvars.yaml`. Schema-validated on load via pydantic v2
  (discriminated union over bool/int/string/enum, unknown-field
  rejection, range and enum-membership checks). Errors surface in
  the GUI / CLI as readable messages, not stack traces.
- **Externalized profile templates** at `data/profiles/*.yaml` with
  single-string `extends:` inheritance, max-depth 4, cycle
  detection, and root-to-leaf merge with last-write-wins semantics.
  Files starting with an underscore (`_base.yaml`) are abstract and
  hidden from user-facing listings.
- **Headless CLI** — `vanguard-config-builder` ships five
  subcommands: `generate` (render a profile to `server.cfg`),
  `validate` (check an existing cfg), `list-profiles`, `list-cvars`
  (with `--category` filter and `--format json`), `diff` (cvar-by-
  cvar comparison). Default `--strict` blocks `generate` on
  validation issues; exit codes match CI expectations
  (0 / 2 / 3).
- **`python -m vanguard_config_builder`** as an alternative entry
  point that dispatches to the same CLI.
- **Three reference docs** under `docs/` for admins:
  `CVAR_DATABASE_SCHEMA.md` (cvar YAML format + cookbook),
  `PROFILE_FORMAT.md` (inheritance rules + cookbook), `CLI_USAGE.md`
  (every subcommand with Ansible / CI examples).
- **Unit test suites** for every core module — generator, parser,
  validator, cvar database loader, profile loader, CLI dispatcher.
  104 tests run on a 3 OS × 4 Python matrix in CI.

### Changed

- **Repackaged as `src/vanguard_config_builder/`** (proper
  src-layout). The single-file `main.py` is gone; module layout is
  now `__init__.py` + `__main__.py` + `cli.py` + `_resources.py` +
  `core/` + `gui/` + `data/`.
- **GUI split** into three modules: `gui/main_window.py`
  (orchestrator), `gui/section_panels.py` (per-cvar form factories),
  `gui/cfg_preview.py` (preview pane factory + render). The
  `ConfigBuilderApp` class now delegates widget construction to
  pure factory functions.
- **Bundle data lookup** centralized in `_resources.py` — handles
  both source/editable installs and PyInstaller `--onefile` bundles
  (`sys._MEIPASS`).
- **Runtime dependencies**: PyYAML >= 6.0, pydantic >= 2.0 (declared
  in `pyproject.toml [project] dependencies`; `requirements.txt` and
  `requirements-dev.txt` are now pointer files (`-e .` / `-e .[dev]`)
  with pyproject as the single source of truth).
- **Release workflow** adds `--add-data` for the bundled YAMLs with
  cross-OS path separator handling, and switches the PyInstaller
  build target from `main.py` to `entrypoint.py` (a one-line
  driver). PyInstaller bundles now ship the YAML files inside the
  executable.

### Fixed

- **Cross-OS PowerShell line-continuation bug** in CI workflow
  defaults — `shell: bash` is now the default for both
  `config-builder-ci.yml` and `config-builder-release.yml`, so
  multi-line `run:` blocks build cleanly on `windows-latest`.

### Removed

- The inline `CVARS` and `PROFILES` Python dicts that lived in the
  v0.1.0 `main.py`. Same data, now in YAML.
- The single-file `main.py` (replaced by the package; the legacy
  `main:main` entry point was switched to
  `vanguard_config_builder.cli:main`).

## [0.1.0] — 2026-05-01

Initial rough prototype scaffold. Working end-to-end but intentionally
single-file with extension markers throughout — see the TODOs in
`main.py` for the modularization roadmap.

### Added

- Tabbed GUI editor (Server Identity / Network / Match Rules /
  Hitbox / Anti-Cheat)
- Three built-in profile templates: Cup/Tournament, Public Server,
  Practice/Scrim
- Live preview pane that re-renders `server.cfg` as values change
- Real-time validation: range checks, enum membership, two
  cross-cvar sanity rules (warmup-without-doWarmup, fps>=40-without-antilag)
- Import existing `server.cfg` files via File menu
- Export with optional metadata header (creation date, profile name,
  generator version)
- Inline cvar database covering ~25 cvars across all categories
- Smoke test suite that runs without tkinter (CI-safe)
