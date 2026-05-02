# Changelog

All notable changes to **config-builder** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Tags follow the monorepo prefix convention: `config-builder-vMAJOR.MINOR.PATCH`.

## [Unreleased]

### Planned

- Externalize cvar database into `data/cvars.yaml`
- Externalize profile templates into `data/profiles/*.yaml`
- Tooltips on every cvar field
- Switch GUI to customtkinter for modern look
- Headless `--profile NAME --output FILE` CLI mode
- Cross-cvar validation rule engine

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
