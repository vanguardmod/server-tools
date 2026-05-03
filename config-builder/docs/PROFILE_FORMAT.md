# Profile Format

A *profile* is a named bundle of cvar values you can apply with one
click in the GUI or one CLI invocation: "Cup", "Public", "Practice",
or any custom one you write yourself. Profiles live as YAML files so
you don't need to edit code to add or change them.

## Where profiles live

```
config-builder/src/vanguard_config_builder/data/profiles/
├── _base.yaml      # shared defaults inherited by every concrete profile
├── cup.yaml        # ESL-ready competitive setup
├── public.yaml     # 32-slot pub setup
└── scrim.yaml      # Practice/Scrim with diagnostics on
```

Each `*.yaml` file becomes a profile. The filename stem (without the
extension) is the profile's lookup name — that's what you pass to the
CLI as `--profile cup`. The human-readable label inside the file is
what the GUI shows on its quick-profile buttons.

Files starting with an underscore (`_base.yaml`) are *abstract* — they
exist only to be inherited from. They're filtered out of the GUI's
profile list and the CLI's `list-profiles` output.

## File structure

Two shapes are accepted depending on whether the profile inherits or not.

### Base profile (no `extends`)

```yaml
profile_name: "Base Defaults"
description: "Shared baseline inherited by all concrete profiles"

values:
  g_speed: 320
  g_gravity: 800
  g_warmup: 30
  vanguard_hitbox_strict: 1
  # ...
```

| Field | Required | Description |
|---|---|---|
| `profile_name` | yes | Display label. Quoted because it usually contains spaces and slashes. |
| `description` | optional | One-line caption shown in CLI listings. |
| `values` | yes | Cvar -> value mapping. Every key must be a known cvar (see [CVAR_DATABASE_SCHEMA.md](CVAR_DATABASE_SCHEMA.md)). |

### Concrete profile (with `extends`)

```yaml
profile_name: "Cup / Tournament"
description: "ESL-ready competitive setup (40fps, 6v6, strict class limits)"
extends: _base

overrides:
  sv_fps: 40
  sv_maxclients: 12
  g_doWarmup: 1
  g_warmup: 60
  # ...
```

| Field | Required | Description |
|---|---|---|
| `profile_name` | yes | Display label. |
| `description` | optional | One-line caption. |
| `extends` | yes | Filename stem of the parent profile (no `.yaml` extension). Single-string only — multiple inheritance is not supported. |
| `overrides` | yes | Cvar -> value mapping. Only the deltas vs. the parent. |

A concrete profile must use `overrides:`, never `values:`. A base
profile must use `values:`, never `overrides:`. Mixing them is a
schema error caught at load time.

## How inheritance resolves

When you ask for a profile, the resolver walks the `extends:` chain
from the leaf up to the root, then merges values root-to-leaf with
*last-write-wins* semantics:

1. Start with an empty values dict.
2. Apply the root's `values:` block.
3. For each child in chain order, apply its `overrides:` block on top.
4. Validate: every key in the merged dict must be a known cvar.

### Override semantics — child always wins

The merger uses straight `dict.update` — there's no None-coalesce, no
"only override if non-zero" trick. If the child says `g_warmup: 0`,
the resolved value is `0`, even if the parent said `g_warmup: 30`.
This is the contract the bundled `public.yaml` and `scrim.yaml`
depend on.

```yaml
# _base.yaml
values:
  g_warmup: 30          # cvar default, would trip a validator warning
                        # if combined with g_doWarmup=0

# public.yaml
extends: _base
overrides:
  g_doWarmup: 0
  g_warmup: 0           # ← MUST stay zero in the resolved profile
```

If the public profile didn't override `g_warmup` to `0` here, the
resolved values would carry `g_warmup: 30` from `_base`, and the
validator would warn ("warmup is set but g_doWarmup=0"). That's why
the override is explicit even though `0` is the "default off" value.

### Inheritance depth

The resolver caps inheritance chains at **4 levels deep**. Realistic
hierarchies sit at depth 2 or 3 (most concrete profiles extend
`_base` directly); the cap is mostly there to catch typos that lead
to runaway chains.

### Cycle detection

`extends:` cycles are detected and rejected:

```yaml
# a.yaml -> b.yaml -> a.yaml  → ProfileError
```

The error message names every profile in the cycle so you can find
the offending file.

## Common error messages

| Message | Meaning | Fix |
|---|---|---|
| `profiles directory not found` | The bundled directory is missing. | Reinstall the tool or check your fork's data layout. |
| `profile X.yaml is not valid YAML` | YAML parser couldn't read the file. | Check indentation and quoting. |
| `profile 'X' extends unknown profile 'Y'` | The `extends:` value doesn't match any file stem. | Fix the typo, or create the parent. |
| `circular inheritance: a -> b -> a` | A chain loops. | Remove the cycle by breaking one of the `extends:` references. |
| `inheritance depth exceeds 4` | Chain too long. | Flatten the hierarchy. |
| `profile 'X' references unknown cvar(s): [...]` | A key in `values:` or `overrides:` isn't declared in `cvars.yaml`. | Either declare it in the cvar database or remove it. Typos are the most common cause. |
| `schema validation` | The file has an unknown field, missing required field, or wrong type. | Compare against `_base.yaml` or a working profile. |
| `profile with 'extends' must use 'overrides:', not 'values:'` | XOR rule violation. | Switch the field name. |

## Cookbook

### Create a new profile

1. Pick a short lowercase filename stem — that's the CLI key
   (`--profile <stem>`).
2. Decide whether to inherit. Almost always you want
   `extends: _base` so you don't repeat the cross-profile defaults.
3. Write only the deltas in `overrides:`.
4. Save and re-launch the tool.

Example — a "small private LAN" profile:

```yaml
# config-builder/src/vanguard_config_builder/data/profiles/lan.yaml
profile_name: "Private LAN"
description: "8-slot LAN scrim, fast restart, dev features off"
extends: _base

overrides:
  sv_fps: 40
  sv_maxclients: 8
  g_friendlyFire: 1
  g_doWarmup: 1
  g_warmup: 30
  team_maxSoldiers: -1
  team_maxMedics: -1
  team_maxEngineers: -1
  team_maxFieldops: -1
  team_maxCovertops: -1
  vanguard_netcode_profile: cup
```

After saving, the GUI's quick-profile bar gains a "Private LAN"
button, and the CLI accepts `--profile lan`.

### Override a single cvar from a parent

If you only want to flip one value, the override block can be tiny:

```yaml
profile_name: "Cup, no Friendly Fire"
description: "Cup setup but with FF disabled — for casual scrims"
extends: cup

overrides:
  g_friendlyFire: 0
```

This profile inherits all of `cup.yaml`'s settings (which themselves
inherit from `_base.yaml`) and changes exactly `g_friendlyFire`. The
inheritance chain becomes `mycup -> cup -> _base`, depth 3, well
under the cap.

### Edit `_base.yaml` vs. write a new profile

Rule of thumb: edit `_base.yaml` only when the change should affect
**every** concrete profile that inherits from it. Examples of
appropriate `_base` edits:

- Bumping `g_speed` because VanguardMod changed the default.
- Adding a new mandatory cvar that didn't exist before.
- Toggling a security default that should be on everywhere.

Write a new profile (or override in an existing one) when the change
is only relevant to a specific use case — a tournament series, a
particular event, your own private server.

## Validation

Profile values are validated against the cvar database at load time:

- Unknown cvar names → hard error, the tool refuses to start with a
  clear message naming the offending file.
- Wrong types or out-of-range values → not caught at profile load,
  but flagged by the validator as soon as you generate or validate a
  cfg from the resolved values. The CLI's `generate --strict` (the
  default) blocks the write when issues exist.

If you bundle a custom cvar in `cvars.yaml`, you can reference it
from any profile right away.
