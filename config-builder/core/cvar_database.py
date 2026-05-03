# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Load and validate the externalized cvar database.

The cvar database lives in ``data/cvars.yaml`` (next to this package)
and is the single source of truth for which cvars VanguardMod knows
about, what types they have, what their defaults are, and how the GUI
should render them.

This module:
  1. Defines the pydantic v2 schema for the YAML file
     (``CvarsFileV1``).
  2. Provides a ``load_cvar_database()`` function that reads the YAML,
     validates it, and returns a ``CvarDatabase`` object.
  3. Wraps pydantic's ``ValidationError`` in a friendlier
     ``CvarDatabaseError`` so the GUI/CLI can render multi-line
     error messages without leaking raw stack traces.

The schema is versioned via the top-level ``schema_version: 1`` key so
future schema changes (e.g. an enum option label scheme) can be added
without breaking older bundled YAMLs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class CvarDatabaseError(Exception):
    """Raised when the cvar database YAML is missing, unparseable, or
    fails schema validation. Users should see this message; the
    underlying pydantic error is attached to ``__cause__`` for
    debugging.
    """


# ---------------------------------------------------------------------------
# Schema models (pydantic v2)
# ---------------------------------------------------------------------------
class _CvarBase(BaseModel):
    """Fields shared by every cvar regardless of type."""

    model_config = ConfigDict(extra="forbid")

    category: str
    description: str
    archive: bool = True
    secret: bool = False
    since_version: str | None = None
    deprecated: bool = False


class BoolCvar(_CvarBase):
    """A boolean cvar — value is 0 or 1 (game engine convention)."""

    type: Literal["bool"]
    default: int

    @model_validator(mode="after")
    def _default_is_zero_or_one(self) -> BoolCvar:
        if self.default not in (0, 1):
            raise ValueError(f"bool default must be 0 or 1, got {self.default!r}")
        return self


class IntCvar(_CvarBase):
    """An integer cvar with optional range and quick-select hints."""

    type: Literal["int"]
    default: int
    range: tuple[int, int] | None = None
    common_values: list[int] | None = None

    @model_validator(mode="after")
    def _check_range(self) -> IntCvar:
        if self.range is not None:
            lo, hi = self.range
            if lo > hi:
                raise ValueError(f"range[0]={lo} is greater than range[1]={hi}")
            if not (lo <= self.default <= hi):
                raise ValueError(
                    f"default {self.default} outside range [{lo}..{hi}]"
                )
        return self


class StringCvar(_CvarBase):
    """A free-form string cvar (server name, password, MOTD, ...)."""

    type: Literal["string"]
    default: str


class EnumOption(BaseModel):
    """A single option in an enum cvar's allowed-values list."""

    model_config = ConfigDict(extra="forbid")

    value: str
    label: str


class EnumCvar(_CvarBase):
    """An enum cvar — value is one of a fixed list of strings."""

    type: Literal["enum"]
    default: str
    options: list[EnumOption]

    @model_validator(mode="after")
    def _default_in_options(self) -> EnumCvar:
        if not self.options:
            raise ValueError("enum cvar must declare at least one option")
        valid = {o.value for o in self.options}
        if self.default not in valid:
            raise ValueError(
                f"default '{self.default}' is not in options {sorted(valid)}"
            )
        return self


# Discriminated union — pydantic dispatches on the ``type`` field.
Cvar = Annotated[
    BoolCvar | IntCvar | StringCvar | EnumCvar,
    Field(discriminator="type"),
]


class Category(BaseModel):
    """A cvar category for grouping in the GUI."""

    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    order: int


class CvarsFileV1(BaseModel):
    """Top-level schema for a v1 cvars.yaml file."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    categories: list[Category]
    cvars: dict[str, Cvar]

    @model_validator(mode="after")
    def _check_consistency(self) -> CvarsFileV1:
        # Every cvar's category must point at a declared category.
        cat_ids = {c.id for c in self.categories}
        for name, cvar in self.cvars.items():
            if cvar.category not in cat_ids:
                raise ValueError(
                    f"cvar '{name}' references unknown category "
                    f"'{cvar.category}' (declared categories: "
                    f"{sorted(cat_ids)})"
                )
        # Category ids must be unique.
        if len(cat_ids) != len(self.categories):
            raise ValueError("duplicate category id in `categories` list")
        return self


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------
class CvarDatabase:
    """Loaded, validated cvar database.

    Wraps the pydantic model with a small accessor surface that the
    GUI and tests can use without depending on pydantic types.
    """

    def __init__(self, model: CvarsFileV1) -> None:
        self._model = model

    @property
    def categories(self) -> list[Category]:
        """Categories sorted by their declared ``order`` field."""
        return sorted(self._model.categories, key=lambda c: c.order)

    @property
    def cvars(self) -> dict[str, Cvar]:
        """Mapping of cvar name to validated cvar model, in YAML order."""
        return self._model.cvars

    def __len__(self) -> int:
        return len(self._model.cvars)

    def __contains__(self, name: object) -> bool:
        return name in self._model.cvars

    def __getitem__(self, name: str) -> Cvar:
        return self._model.cvars[name]

    def as_legacy_dict(self) -> dict[str, dict[str, Any]]:
        """Render the database into the v0.1.0 inline ``CVARS`` shape.

        Used during M5 to keep the GUI and the smoke tests working
        unchanged while we swap out the data source. Once the GUI is
        repackaged in M9 and reads cvars directly via the typed
        accessors, this method can go.

        The shape per cvar:
            {
                "type":        "bool" | "int" | "string" | "enum",
                "default":     <typed default>,
                "range":       (lo, hi) for int / list[str] for enum / None,
                "category":    str,
                "description": str,
                "archive":     bool,
                "secret":      bool,
            }
        """
        out: dict[str, dict[str, Any]] = {}
        for name, cvar in self._model.cvars.items():
            entry: dict[str, Any] = {
                "type": cvar.type,
                "default": cvar.default,
                "category": cvar.category,
                "description": cvar.description,
                "archive": cvar.archive,
                "secret": cvar.secret,
            }
            if isinstance(cvar, IntCvar):
                entry["range"] = cvar.range
            elif isinstance(cvar, EnumCvar):
                # Legacy shape: `range` is the flat list of valid values
                # (no labels). Labels are richer info that v0.1.0 didn't
                # have; the GUI in M9+ will read ``cvar.options`` directly.
                entry["range"] = [opt.value for opt in cvar.options]
            else:
                entry["range"] = None
            out[name] = entry
        return out


def load_cvar_database(path: Path) -> CvarDatabase:
    """Read *path* and return a validated ``CvarDatabase``.

    Raises:
        CvarDatabaseError: when the file is missing, unparseable as
            YAML, or fails schema validation. The original exception
            is chained via ``__cause__`` for debugging.
    """
    if not path.is_file():
        raise CvarDatabaseError(f"cvar database not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CvarDatabaseError(f"cvar database is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CvarDatabaseError(
            f"cvar database root must be a mapping, got {type(raw).__name__}"
        )

    try:
        model = CvarsFileV1.model_validate(raw)
    except ValidationError as exc:
        raise CvarDatabaseError(
            f"cvar database failed schema validation:\n{exc}"
        ) from exc

    return CvarDatabase(model)


# ---------------------------------------------------------------------------
# Convenience: locate the bundled cvars.yaml
# ---------------------------------------------------------------------------
def default_database_path() -> Path:
    """Path to the bundled ``data/cvars.yaml`` next to the source.

    During Phase 2 the data files live at ``config-builder/data/``.
    Once the project is repackaged under ``src/vanguard_config_builder/``
    in M9, this will switch to ``importlib.resources`` and also handle
    the PyInstaller ``sys._MEIPASS`` case.
    """
    return Path(__file__).resolve().parent.parent / "data" / "cvars.yaml"
