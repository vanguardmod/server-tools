# server-tools

Utilities and helper applications for VanguardMod server administrators.

This repository is a **monorepo** — each tool lives in its own subfolder
and is versioned and released independently using a tag-prefix convention.

## Tools

| Tool | Status | Description |
|---|---|---|
| [config-builder](config-builder/) | early prototype (v0.1.x) | Desktop GUI to generate and validate VanguardMod `server.cfg` files |

Future tools will be added here as they appear.

## Repository Layout

```
server-tools/
├── README.md                       (this file)
├── LICENSE                         GPL-3.0-or-later
├── .github/
│   └── workflows/                  one CI + one release workflow per tool
└── <tool-name>/                    each tool is fully self-contained
    ├── README.md
    ├── VERSION
    ├── CHANGELOG.md
    └── (tool source)
```

Every tool ships with:
- its own `README.md` with install + usage instructions
- its own `VERSION` file (single-line, e.g. `v0.1.0`)
- its own `CHANGELOG.md` in [Keep a Changelog](https://keepachangelog.com/) format
- its own GitHub Actions workflows in `.github/workflows/<tool-name>-*.yml`

## Versioning and Releases

Each tool is tagged with its own prefix, e.g.:

```
config-builder-v0.1.0
log-analyzer-v0.3.2
admin-bot-v1.0.0
```

Pushing a tag with one of these prefixes triggers **only** that tool's
release workflow, which builds artifacts and creates a GitHub Release
with the tag-prefixed name.

CI runs are also scoped per tool via path filters — a change inside
`config-builder/` only triggers `config-builder-ci.yml`, never the
others. This keeps the build pipeline fast even as the repo grows.

## Adding a New Tool

1. Create a new folder at the repo root, e.g. `log-analyzer/`
2. Add `VERSION`, `README.md`, `CHANGELOG.md`, and your source
3. Copy `.github/workflows/config-builder-ci.yml` →
   `.github/workflows/log-analyzer-ci.yml` and replace every occurrence
   of `config-builder` with `log-analyzer`
4. Same for the release workflow
5. Update the table at the top of this README

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
Matches the VanguardMod main repository license.

## Related Repositories

- [vanguardmod/vanguard](https://github.com/vanguardmod/vanguard) — the mod itself
- [vanguardmod.com](https://vanguardmod.com) — community website (in preparation)
