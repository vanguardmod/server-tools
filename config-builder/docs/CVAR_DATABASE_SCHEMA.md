# Cvar Database (`cvars.yaml`)

This document explains the format of the cvar database that drives the
config-builder. If you're a VanguardMod server admin and you want to
add new cvars, change defaults, or restructure the categories shown in
the GUI, this is the file you edit — no Python required.

## Where it lives

The database is shipped at:

```
config-builder/src/vanguard_config_builder/data/cvars.yaml
```

When the config-builder is installed via `pip` it sits next to the
package code; when it's run as a standalone PyInstaller binary it
lives inside the bundle and is extracted to a temporary directory at
launch. Either way, you don't address it directly — the tool reads it
automatically.

If you maintain a fork or want to ship your own cvar set, edit this
file in your checkout and run / package the tool from your tree.

## Top-level structure

```yaml
schema_version: 1

categories:
  - { id: identity,  label: "Server Identity",  order: 1 }
  - { id: network,   label: "Network Settings", order: 2 }
  # ...

cvars:
  sv_hostname:
    type: string
    default: "VanguardMod Server"
    category: identity
    description: "Server name shown in the server browser"
    archive: true
    secret: false
  # ...
```

Three required top-level keys:

| Key | Purpose |
|---|---|
| `schema_version` | Currently `1`. Bumped if the format changes in a backward-incompatible way; the loader rejects unknown versions so an out-of-date binary fails fast. |
| `categories` | Ordered list of category descriptors. The GUI renders one tab per category in `order`. |
| `cvars` | Mapping of cvar name to its declaration. Order is preserved; the GUI renders rows in YAML order within each category. |

The loader rejects any other top-level key. Typos like `cars:` instead
of `cvars:` will fail at startup with a clear message.

## Categories

Each entry has three fields:

```yaml
- { id: network, label: "Network Settings", order: 2 }
```

| Field | Required | Description |
|---|---|---|
| `id` | yes | Short identifier referenced by `cvars[*].category`. Use lowercase. |
| `label` | yes | Human-readable text shown on the GUI tab. |
| `order` | yes | Integer sort key. Categories are displayed in ascending order. |

Category IDs must be unique. Every cvar must point at a declared
category — the loader cross-checks this and rejects orphan references.

## Cvars — the four types

Every cvar declaration shares a baseline of fields and adds type-
specific keys. Unknown fields are rejected.

### Shared fields

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | enum | required | One of `bool`, `int`, `string`, `enum` |
| `default` | type-dependent | required | Initial value used when no profile sets it |
| `category` | string | required | Must match a declared category `id` |
| `description` | string | required | Help text shown next to the field in the GUI |
| `archive` | bool | `true` | Emit as `seta` (persisted across map changes) vs `set` (session-only) |
| `secret` | bool | `false` | Render with masked input in the GUI; mark `[SECRET]` in CLI listings |
| `since_version` | string | unset | When this cvar was introduced (informational; no behavior yet) |
| `deprecated` | bool | `false` | Marks the cvar as scheduled for removal (no behavior yet) |

### `bool`

```yaml
g_antilag:
  type: bool
  default: 1
  category: network
  description: "Enable lag compensation for hit detection"
  archive: true
```

`default` must be `0` or `1` (the game engine's bool convention).

### `int`

```yaml
sv_fps:
  type: int
  default: 20
  range: [20, 125]
  category: network
  description: "Server tick rate. Cup standard: 40."
  archive: true
  common_values: [20, 40]
```

| Field | Required | Description |
|---|---|---|
| `range` | optional | Two-element list `[min, max]`. The validator rejects values outside this range; the GUI renders a Spinbox bounded by it. Omit for unbounded ints. |
| `common_values` | optional | List of integers shown as quick-select hints in the GUI. Purely cosmetic. |

The loader checks that `range[0] <= default <= range[1]` and that
`range[0] <= range[1]`.

### `string`

```yaml
sv_hostname:
  type: string
  default: "VanguardMod Server"
  category: identity
  description: "Server name shown in the server browser"
  archive: true
```

No type-specific fields. `default` may be empty.

### `enum`

```yaml
vanguard_netcode_profile:
  type: enum
  default: public
  options:
    - { value: cup,    label: "Cup (40fps tight)" }
    - { value: public, label: "Public (20fps standard)" }
    - { value: custom, label: "Custom" }
  category: network
  description: "Netcode preset"
  archive: true
```

| Field | Required | Description |
|---|---|---|
| `options` | yes | List of `{ value, label }` pairs. `value` is what's written to `server.cfg`; `label` is what the GUI's dropdown displays. |

`default` must equal one of the `options[*].value` entries.

## Common error messages

The loader stops the tool at startup if `cvars.yaml` is malformed.
You'll see a message in the GUI dialog or in the CLI's stderr.

| Message | Meaning | Fix |
|---|---|---|
| `cvar database not found` | The file is missing or unreadable. | Check the path and permissions. |
| `cvar database is not valid YAML` | YAML parser couldn't read the file. | Look for unbalanced quotes, bad indentation, or stray tabs. The error usually points at the line. |
| `schema validation` (with field path) | A field has the wrong type, is missing, or is unknown. | Compare your cvar entry against an existing one of the same type. |
| `cvar 'X' references unknown category 'Y'` | A cvar's `category` doesn't match any declared category. | Add `Y` to the `categories` list, or fix the typo. |
| `bool default must be 0 or 1` | A `bool` cvar has a default like `true` (literal) or `2`. | Use the integer `0` or `1`. |
| `default 'X' is not in options` | An `enum` cvar's `default` isn't one of its `options[*].value`. | Pick a value from the options list. |
| `default N outside range [LO..HI]` | An `int` cvar's default falls outside its declared range. | Either widen the range or change the default. |

## Cookbook

### Add a new cvar

1. Pick the category. If it doesn't exist yet, see "Add a new category" below.
2. Decide the type (`bool` / `int` / `string` / `enum`).
3. Add the entry under `cvars:`. Keep it grouped near related cvars
   so the GUI ordering stays sensible.
4. Provide a clear `description` — that's the helper text the admin
   sees in the GUI.
5. Save and re-launch the tool.

Example — adding `g_logSync`:

```yaml
g_logSync:
  type: bool
  default: 0
  category: anticheat
  description: "Force a flush of the server log on every write"
  archive: true
```

### Add a new category

1. Pick a short lowercase `id` (e.g. `wolfguard`).
2. Decide where in the tab order it should appear (`order` value).
   Other categories with higher `order` values get nudged to the right.
3. Add it to the `categories:` list.
4. Add (or repoint) the cvars that belong in it.

Example — adding a WolfGuard tab:

```yaml
categories:
  - { id: identity,  label: "Server Identity",  order: 1 }
  - { id: network,   label: "Network Settings", order: 2 }
  - { id: match,     label: "Match Rules",      order: 3 }
  - { id: hitbox,    label: "Hitbox / Combat",  order: 4 }
  - { id: anticheat, label: "Anti-Cheat & Dev", order: 5 }
  - { id: wolfguard, label: "WolfGuard",        order: 6 }    # NEW
```

### Mark a cvar deprecated

Set `deprecated: true`. v0.2.0 doesn't change behavior based on this
flag, but future versions will surface a warning in the GUI and CLI
listings — keeping the field in the schema today means existing
deployments are forward-compatible.

```yaml
g_oldKnockbackHack:
  type: bool
  default: 0
  category: match
  description: "Legacy knockback compatibility shim — slated for removal"
  archive: true
  deprecated: true
```

## Schema versioning

The `schema_version: 1` line at the top is mandatory. If a future
version of the config-builder introduces an incompatible change
(renamed fields, restructured shape), it will bump to `2` and refuse
to load older files; older binaries will likewise refuse to load
newer files. This is intentional — silent partial reads cause far
worse confusion than an explicit "version mismatch" error. Until
that happens, leave `schema_version` at `1`.
