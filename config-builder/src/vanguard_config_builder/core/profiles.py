# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Load and resolve VanguardMod profile templates.

A *profile* is a named bundle of cvar overrides — "Cup", "Public",
"Practice/Scrim" etc. v0.1.0 carried these as inline Python dicts.
M6 externalizes them to ``data/profiles/<stem>.yaml`` so server admins
can add or tweak profiles without touching code.

Two YAML shapes are accepted:

* **Base profiles** (no ``extends``) carry a full ``values:`` block —
  the baseline every concrete profile inherits. By convention these
  files are named with a leading underscore (``_base.yaml``) and are
  hidden from ``list_names()`` so users don't accidentally pick them.

* **Concrete profiles** (with ``extends:``) carry only an ``overrides:``
  block — the deltas relative to the parent. Single-string ``extends``
  only; multiple inheritance is not supported.

The resolver walks the parent chain (max depth 4, with cycle
detection), merges values root-to-leaf with simple last-write-wins
semantics (a child override of ``0`` correctly beats a parent value
of ``30``), and optionally validates that every referenced cvar is
declared in the loaded ``CvarDatabase``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_INHERITANCE_DEPTH = 4
"""Hard cap on the length of an ``extends:`` chain. Realistic profile
hierarchies sit at depth 2–3; the cap is just a guard against
runaway configurations and accidental cycles that escape the explicit
cycle detector."""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class ProfileError(Exception):
    """Raised when a profile YAML is missing, unparseable, fails schema
    validation, or cannot be resolved (unknown parent, cycle, depth
    exceeded, unknown cvar). Messages are user-facing — the GUI
    surfaces them in a dialog without the raw stack trace.
    """


# ---------------------------------------------------------------------------
# Schema models (pydantic v2)
# ---------------------------------------------------------------------------
class Profile(BaseModel):
    """Raw, unresolved profile as read from a single YAML file.

    Either ``values`` (for a base profile) or ``overrides`` (for a
    profile with ``extends``) may be set, but not both. The
    cross-field rule is enforced in the model validator below so a
    malformed YAML fails at load time rather than producing a
    surprising merge result downstream.
    """

    model_config = ConfigDict(extra="forbid")

    profile_name: str
    description: str = ""
    extends: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_values_overrides_xor(self) -> Profile:
        if self.extends is None and self.overrides:
            raise ValueError(
                "profile without `extends` must use `values:`, not `overrides:`"
            )
        if self.extends is not None and self.values:
            raise ValueError(
                "profile with `extends` must use `overrides:`, not `values:`"
            )
        return self

    def payload(self) -> dict[str, Any]:
        """Return whichever of ``values``/``overrides`` is in use."""
        return self.overrides if self.extends is not None else self.values


# ---------------------------------------------------------------------------
# Resolved profile (post-inheritance, flat values)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResolvedProfile:
    """A profile after its inheritance chain has been merged.

    Attributes:
        name: The YAML filename stem (e.g. ``"cup"``). Used by the
            CLI as a stable key (``--profile cup``).
        profile_name: The human-readable label from the leaf YAML
            (e.g. ``"Cup / Tournament"``). Used by the GUI.
        description: Free-text description from the leaf YAML.
        values: Flat dict of cvar -> value, fully resolved.
        chain: Names in the inheritance chain, leaf to root
            (``["cup", "_base"]``). Useful for diagnostics.
    """

    name: str
    profile_name: str
    description: str
    values: dict[str, Any]
    chain: tuple[str, ...]


# ---------------------------------------------------------------------------
# ProfileSet — collection of raw profiles + resolver
# ---------------------------------------------------------------------------
class ProfileSet:
    """A loaded set of raw profiles, indexed by YAML filename stem.

    The class wraps a dict of stem -> ``Profile`` and exposes the two
    operations callers actually want: list user-visible names and
    resolve a chosen profile to a flat values dict.
    """

    def __init__(self, profiles: dict[str, Profile]) -> None:
        self._profiles = profiles

    def __contains__(self, name: object) -> bool:
        return name in self._profiles

    def __len__(self) -> int:
        return len(self._profiles)

    def __getitem__(self, name: str) -> Profile:
        return self._profiles[name]

    def list_names(self) -> list[str]:
        """User-visible profile names, sorted.

        Files whose stem starts with an underscore (``_base.yaml``)
        are treated as abstract bases and filtered out — they're
        loadable for inheritance but not directly selectable.
        """
        return sorted(
            stem for stem in self._profiles if not stem.startswith("_")
        )

    def resolve(
        self,
        name: str,
        valid_cvars: set[str] | None = None,
    ) -> ResolvedProfile:
        """Walk the inheritance chain and merge values root-to-leaf.

        Args:
            name: YAML filename stem of the profile to resolve.
            valid_cvars: When provided, every cvar that ends up in
                the resolved values dict must be in this set; any
                stray name raises ``ProfileError``. Pass
                ``set(db.cvars)`` from the loaded ``CvarDatabase`` to
                enforce that profiles only reference declared cvars.

        Raises:
            ProfileError: when the profile is unknown, references an
                unknown parent, contains a cycle, exceeds
                ``MAX_INHERITANCE_DEPTH``, or (with ``valid_cvars``)
                touches an undeclared cvar.
        """
        if name not in self._profiles:
            raise ProfileError(f"unknown profile: {name!r}")

        chain = self._build_chain(name)

        # Merge root-to-leaf. The leaf-most profile wins every key
        # collision, including the case where the child override is
        # zero or an empty string — `dict.update` is the right
        # primitive for that, no None-coalesce magic.
        merged: dict[str, Any] = {}
        for stem in reversed(chain):
            merged.update(self._profiles[stem].payload())

        if valid_cvars is not None:
            unknown = set(merged) - valid_cvars
            if unknown:
                raise ProfileError(
                    f"profile {name!r} references unknown cvar(s): "
                    f"{sorted(unknown)}"
                )

        leaf = self._profiles[name]
        return ResolvedProfile(
            name=name,
            profile_name=leaf.profile_name,
            description=leaf.description,
            values=merged,
            chain=tuple(chain),
        )

    # ------------------------------------------------------------------
    def _build_chain(self, name: str) -> list[str]:
        """Return the inheritance chain leaf-to-root.

        Detects three pathological inputs:
          * ``extends`` pointing at an unknown profile,
          * a cycle (``a -> b -> a``),
          * an inheritance depth exceeding ``MAX_INHERITANCE_DEPTH``.

        Each of these raises ``ProfileError`` with a message naming
        all profiles involved so the operator can fix the YAML.
        """
        chain: list[str] = []
        seen: set[str] = set()
        current: str | None = name

        while current is not None:
            if current in seen:
                cycle = " -> ".join(chain + [current])
                raise ProfileError(f"circular inheritance: {cycle}")

            if current not in self._profiles:
                if chain:
                    raise ProfileError(
                        f"profile {chain[-1]!r} extends unknown profile "
                        f"{current!r}"
                    )
                # Should be unreachable — resolve() already checks this,
                # but kept defensive in case _build_chain is ever called
                # directly.
                raise ProfileError(f"unknown profile: {current!r}")

            seen.add(current)
            chain.append(current)

            if len(chain) > MAX_INHERITANCE_DEPTH:
                trace = " -> ".join(chain)
                raise ProfileError(
                    f"inheritance depth exceeds {MAX_INHERITANCE_DEPTH}: "
                    f"{trace}"
                )

            current = self._profiles[current].extends

        return chain


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def load_profile_set(directory: Path) -> ProfileSet:
    """Read every ``*.yaml`` under *directory* and return a ProfileSet.

    Each file's stem (filename without extension) becomes the lookup
    key; the file's parsed contents become a ``Profile``. Schema
    validation (the ``values:``/``overrides:`` XOR rule, unknown
    field rejection) happens here so malformed YAMLs fail fast at
    startup rather than mid-resolution.

    Raises:
        ProfileError: if the directory is missing, if any file is
            unparseable as YAML, or if any file fails schema
            validation. The originating error is chained via
            ``__cause__``.
    """
    if not directory.is_dir():
        raise ProfileError(f"profiles directory not found: {directory}")

    profiles: dict[str, Profile] = {}
    for path in sorted(directory.glob("*.yaml")):
        stem = path.stem
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ProfileError(
                f"profile {path.name} is not valid YAML: {exc}"
            ) from exc

        if not isinstance(raw, dict):
            raise ProfileError(
                f"profile {path.name} root must be a mapping, "
                f"got {type(raw).__name__}"
            )

        try:
            profiles[stem] = Profile.model_validate(raw)
        except ValidationError as exc:
            raise ProfileError(
                f"profile {path.name} failed schema validation:\n{exc}"
            ) from exc

    return ProfileSet(profiles)


def default_profiles_path() -> Path:
    """Path to the bundled ``data/profiles/`` directory.

    Resolves both the source/editable install case and the PyInstaller
    bundle case via ``vanguard_config_builder._resources``.
    """
    from .._resources import profiles_dir
    return profiles_dir()
