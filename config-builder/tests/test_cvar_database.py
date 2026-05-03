# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Unit tests for ``core.cvar_database``.

Two test surfaces:

1. The bundled ``data/cvars.yaml`` file loads and validates against the
   schema. This is the contract that lets non-coders edit the database
   without breaking the tool: if their YAML is malformed, they see a
   clear error at startup, not a crash deep in the GUI.

2. Schema-level rejections — pinned-down examples for each kind of bad
   input (missing required fields, unknown fields, default outside
   range, etc.). These are the contract for *what counts as a valid
   cvars.yaml*.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.cvar_database import (  # noqa: E402
    CvarDatabase,
    CvarDatabaseError,
    EnumCvar,
    IntCvar,
    default_database_path,
    load_cvar_database,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_yaml(tmp_path: Path, content: str) -> Path:
    """Drop *content* into a temp cvars.yaml and return the path."""
    target = tmp_path / "cvars.yaml"
    target.write_text(textwrap.dedent(content), encoding="utf-8")
    return target


_MINIMAL = """\
schema_version: 1
categories:
  - { id: net, label: "Net", order: 1 }
cvars:
  sv_fps:
    type: int
    default: 20
    range: [20, 125]
    category: net
    description: "tick rate"
    archive: true
    secret: false
"""


# ---------------------------------------------------------------------------
# The bundled file is the reference customers see
# ---------------------------------------------------------------------------
class TestBundledDatabase:
    def test_default_path_resolves(self) -> None:
        path = default_database_path()
        assert path.is_file(), f"bundled cvars.yaml missing at {path}"

    def test_bundled_database_loads(self) -> None:
        db = load_cvar_database(default_database_path())
        assert isinstance(db, CvarDatabase)
        # The 24 v0.1.0 cvars must all be present.
        assert len(db) == 24

    def test_bundled_database_has_five_categories(self) -> None:
        db = load_cvar_database(default_database_path())
        cat_ids = {c.id for c in db.categories}
        assert cat_ids == {"identity", "network", "match", "hitbox", "anticheat"}

    def test_bundled_categories_are_ordered(self) -> None:
        db = load_cvar_database(default_database_path())
        orders = [c.order for c in db.categories]
        assert orders == sorted(orders), "categories accessor is not order-sorted"

    def test_legacy_dict_shape(self) -> None:
        db = load_cvar_database(default_database_path())
        legacy = db.as_legacy_dict()
        # Spot-check the shape — full cross-validation against the live
        # CVARS happens in the M5 wiring tests.
        assert "sv_fps" in legacy
        assert legacy["sv_fps"]["type"] == "int"
        assert legacy["sv_fps"]["range"] == (20, 125)
        assert legacy["vanguard_netcode_profile"]["type"] == "enum"
        assert legacy["vanguard_netcode_profile"]["range"] == \
            ["cup", "public", "custom"]
        assert legacy["sv_hostname"]["range"] is None


# ---------------------------------------------------------------------------
# Schema rejection contract
# ---------------------------------------------------------------------------
class TestSchemaRejections:
    def test_minimal_valid_loads(self, tmp_path: Path) -> None:
        # Sanity: the minimal-valid fixture below must actually be valid,
        # otherwise the negative tests below are meaningless.
        path = _write_yaml(tmp_path, _MINIMAL)
        db = load_cvar_database(path)
        assert "sv_fps" in db

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(CvarDatabaseError, match="not found"):
            load_cvar_database(tmp_path / "does-not-exist.yaml")

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "schema_version: 1\n  : invalid : :\n")
        with pytest.raises(CvarDatabaseError, match="not valid YAML"):
            load_cvar_database(path)

    def test_root_must_be_mapping(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "- just\n- a\n- list\n")
        with pytest.raises(CvarDatabaseError, match="must be a mapping"):
            load_cvar_database(path)

    def test_wrong_schema_version(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, _MINIMAL.replace(
            "schema_version: 1", "schema_version: 2",
        ))
        with pytest.raises(CvarDatabaseError, match="schema validation"):
            load_cvar_database(path)

    def test_unknown_top_level_field(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, _MINIMAL + "rogue_field: 1\n")
        with pytest.raises(CvarDatabaseError, match="schema validation"):
            load_cvar_database(path)

    def test_cvar_references_unknown_category(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, _MINIMAL.replace(
            "category: net", "category: nonexistent",
        ))
        with pytest.raises(CvarDatabaseError, match="unknown category"):
            load_cvar_database(path)

    def test_int_default_outside_range(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, _MINIMAL.replace(
            "default: 20", "default: 9999",
        ))
        with pytest.raises(CvarDatabaseError, match="schema validation"):
            load_cvar_database(path)

    def test_int_inverted_range(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, _MINIMAL.replace(
            "range: [20, 125]", "range: [125, 20]",
        ))
        with pytest.raises(CvarDatabaseError, match="schema validation"):
            load_cvar_database(path)

    def test_enum_default_not_in_options(self, tmp_path: Path) -> None:
        yaml_text = """\
        schema_version: 1
        categories:
          - { id: net, label: "Net", order: 1 }
        cvars:
          mode:
            type: enum
            default: missing
            options:
              - { value: a, label: "A" }
              - { value: b, label: "B" }
            category: net
            description: "mode"
            archive: true
            secret: false
        """
        path = _write_yaml(tmp_path, yaml_text)
        with pytest.raises(CvarDatabaseError, match="schema validation"):
            load_cvar_database(path)

    def test_bool_default_not_zero_or_one(self, tmp_path: Path) -> None:
        yaml_text = """\
        schema_version: 1
        categories:
          - { id: net, label: "Net", order: 1 }
        cvars:
          flag:
            type: bool
            default: 7
            category: net
            description: "flag"
            archive: true
            secret: false
        """
        path = _write_yaml(tmp_path, yaml_text)
        with pytest.raises(CvarDatabaseError, match="schema validation"):
            load_cvar_database(path)


# ---------------------------------------------------------------------------
# Discriminated-union dispatch
# ---------------------------------------------------------------------------
class TestDiscriminatedUnion:
    def test_int_cvar_typed_as_intcvar(self) -> None:
        db = load_cvar_database(default_database_path())
        assert isinstance(db["sv_fps"], IntCvar)

    def test_enum_cvar_typed_as_enumcvar(self) -> None:
        db = load_cvar_database(default_database_path())
        cvar = db["vanguard_netcode_profile"]
        assert isinstance(cvar, EnumCvar)
        assert {o.value for o in cvar.options} == {"cup", "public", "custom"}
