# config-builder

Desktop GUI tool for generating and validating VanguardMod `server.cfg`
files. Save server admins the pain of hand-editing cvars in a text editor.

**Status:** rough prototype (v0.1.x) — single-file scaffold with
extension markers throughout. See the TODOs in `main.py` for the
modularization roadmap.

## Features (current)

- Tabbed editor with sections: Server Identity, Network, Match Rules,
  Hitbox/Combat, Anti-Cheat
- Three built-in profile templates: Cup/Tournament, Public Server,
  Practice/Scrim
- Live preview pane that re-renders the `server.cfg` as you type
- Real-time validation (range checks, enum membership, basic
  cross-cvar sanity rules)
- Import existing `server.cfg` files and edit them
- Export with optional metadata header (date, profile, tool version)

## Features (planned — TODO markers in code)

- Externalize the cvar database into `data/cvars.yaml` so non-coders
  can extend it
- Externalize profile templates into `data/profiles/*.yaml` with
  inheritance support
- Tooltips on every cvar
- Modern look (customtkinter or PySide6)
- Headless `--profile cup --output server.cfg` mode for CI/Ansible
- Multi-server tab mode
- Diff mode for comparing two cfgs side by side

## Requirements

- Python 3.10 or newer
- Tkinter (ships with Python on Windows/macOS; on Linux you may need
  `sudo apt install python3-tk` or your distro's equivalent)

No third-party packages required for the rough version. This will
change once we move the cvar database to YAML (PyYAML) and add the
modern GUI (customtkinter).

## Run

```bash
cd config-builder
python main.py
```

That's it. The GUI opens with the default values pre-filled.

## Quick walkthrough

1. Click **Cup / Tournament** in the Quick Profile bar — every field
   updates and the preview on the right re-renders
2. Switch to the **Server Identity** tab and set `sv_hostname` and
   `rconpassword`
3. Watch the validation panel below the preview — it flashes warnings
   the moment you set an out-of-range value
4. Click **Export...** to save to disk

To round-trip an existing config: **File → Import server.cfg...**,
edit, then **File → Export server.cfg...**.

## Documentation

For server admins extending the tool or scripting it from CI / Ansible:

- [Cvar Database Schema](docs/CVAR_DATABASE_SCHEMA.md) — how to add
  new cvars and categories to `data/cvars.yaml` without touching Python.
- [Profile Format](docs/PROFILE_FORMAT.md) — how profile inheritance
  works and how to write your own `data/profiles/<name>.yaml`.
- [CLI Usage](docs/CLI_USAGE.md) — every subcommand, every flag, with
  real-world Ansible / CI examples.

## Development

### Running the smoke tests

```bash
cd config-builder
python -m pytest tests/ -v
```

The smoke tests stub tkinter so they run in headless CI environments.

### Project layout

The current single-file layout will be split as the tool matures.
See the docstring at the top of `main.py` for the planned final
architecture.

### Versioning and releases

This tool follows the monorepo tag-prefix convention:

- Version is stored in `VERSION` (single line, e.g. `v0.1.0`)
- Tags are pushed as `config-builder-v<MAJOR>.<MINOR>.<PATCH>`
- Pushing such a tag triggers `.github/workflows/config-builder-release.yml`,
  which builds artifacts and creates a GitHub Release

Release procedure:

```bash
# 1. Bump VERSION
echo "v0.2.0" > config-builder/VERSION

# 2. Update CHANGELOG.md (Keep a Changelog format)

# 3. Commit and push to main; wait for CI green
git add config-builder/VERSION config-builder/CHANGELOG.md
git commit -m "config-builder: prepare v0.2.0 release"
git push origin main

# 4. Tag and push
git tag -a config-builder-v0.2.0 -m "config-builder v0.2.0"
git push origin config-builder-v0.2.0
```

## License

GPL-3.0-or-later — see [../LICENSE](../LICENSE).
