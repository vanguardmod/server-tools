# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 wahke <info@wahke.lu> (https://wahke.lu)
# SPDX-FileCopyrightText: 2026 VanguardMod Project Contributors
"""Unit tests for ``core.profiles``.

Two test surfaces:

1. The four bundled profile YAMLs (``_base``, ``cup``, ``public``,
   ``scrim``) parse, resolve, and produce flat values dicts that
   match the v0.1.0 inline ``PROFILES`` shape exactly. Without this
   the M7 wiring would silently drift from v0.1.0 behavior.

2. Schema and resolver edge cases — driven from temp-dir fixtures so
   they're hermetic and don't touch the bundled data.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from vanguard_config_builder.core.profiles import (
    MAX_INHERITANCE_DEPTH,
    Profile,
    ProfileError,
    ProfileSet,
    ResolvedProfile,
    default_profiles_path,
    load_profile_set,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    """Drop *files* (filename -> YAML body) into a temp dir."""
    target = tmp_path / "profiles"
    target.mkdir()
    for name, body in files.items():
        (target / name).write_text(textwrap.dedent(body), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# The bundled profiles match v0.1.0 behavior
# ---------------------------------------------------------------------------
class TestBundledProfiles:
    def test_default_path_resolves(self) -> None:
        path = default_profiles_path()
        assert path.is_dir(), f"profiles dir missing at {path}"

    def test_loads_four_files(self) -> None:
        ps = load_profile_set(default_profiles_path())
        # 4 files on disk: _base + cup + public + scrim
        assert len(ps) == 4
        for stem in ("_base", "cup", "public", "scrim"):
            assert stem in ps

    def test_list_names_filters_underscore(self) -> None:
        ps = load_profile_set(default_profiles_path())
        names = ps.list_names()
        assert names == ["cup", "public", "scrim"]
        assert "_base" not in names

    def test_cup_resolves_to_v01_inline_dict(self) -> None:
        ps = load_profile_set(default_profiles_path())
        resolved = ps.resolve("cup")
        assert resolved.profile_name == "Cup / Tournament"
        assert resolved.values == {
            "sv_fps": 40,
            "sv_maxclients": 12,
            "g_antilag": 1,
            "g_antiwarp": 1,
            "g_friendlyFire": 1,
            "g_doWarmup": 1,
            "g_warmup": 60,
            "g_speed": 320,
            "g_gravity": 800,
            "g_knockback": 1000,
            "team_maxSoldiers": 1,
            "team_maxMedics": 2,
            "team_maxEngineers": 2,
            "team_maxFieldops": 1,
            "team_maxCovertops": 1,
            "vanguard_hitbox_strict": 1,
            "vanguard_hitbox_debug": 0,
            "vanguard_netcode_profile": "cup",
            "vanguard_dev": 0,
        }

    def test_public_resolves_to_v01_inline_dict(self) -> None:
        ps = load_profile_set(default_profiles_path())
        resolved = ps.resolve("public")
        assert resolved.profile_name == "Public Server"
        assert resolved.values == {
            "sv_fps": 20,
            "sv_maxclients": 32,
            "g_antilag": 1,
            "g_antiwarp": 1,
            "g_friendlyFire": 0,
            "g_doWarmup": 0,
            "g_warmup": 0,
            "g_speed": 320,
            "g_gravity": 800,
            "g_knockback": 1000,
            "team_maxSoldiers": -1,
            "team_maxMedics": -1,
            "team_maxEngineers": -1,
            "team_maxFieldops": -1,
            "team_maxCovertops": -1,
            "vanguard_hitbox_strict": 1,
            "vanguard_hitbox_debug": 0,
            "vanguard_netcode_profile": "public",
            "vanguard_dev": 0,
        }

    def test_scrim_resolves_to_v01_inline_dict(self) -> None:
        ps = load_profile_set(default_profiles_path())
        resolved = ps.resolve("scrim")
        assert resolved.profile_name == "Practice / Scrim"
        # Flag the two flips relative to _base explicitly so a
        # regression here points at the right line.
        assert resolved.values["vanguard_hitbox_debug"] == 1
        assert resolved.values["vanguard_dev"] == 1
        # And the full shape — same key set the v0.1.0 inline dict had.
        assert resolved.values == {
            "sv_fps": 40,
            "sv_maxclients": 16,
            "g_antilag": 1,
            "g_antiwarp": 1,
            "g_friendlyFire": 1,
            "g_doWarmup": 0,
            "g_warmup": 0,
            "g_speed": 320,
            "g_gravity": 800,
            "g_knockback": 1000,
            "team_maxSoldiers": -1,
            "team_maxMedics": -1,
            "team_maxEngineers": -1,
            "team_maxFieldops": -1,
            "team_maxCovertops": -1,
            "vanguard_hitbox_strict": 1,
            "vanguard_hitbox_debug": 1,
            "vanguard_netcode_profile": "cup",
            "vanguard_dev": 1,
        }

    def test_chain_attribute_records_inheritance(self) -> None:
        ps = load_profile_set(default_profiles_path())
        assert ps.resolve("cup").chain == ("cup", "_base")
        # _base resolved standalone has a chain of just itself.
        assert ps.resolve("_base").chain == ("_base",)


# ---------------------------------------------------------------------------
# Override semantics — explicit, including the zero-wins edge case
# ---------------------------------------------------------------------------
class TestOverrideSemantics:
    def test_child_zero_overrides_parent_nonzero(self) -> None:
        """The risk-#7 scenario from the recon report: _base has
        g_warmup=30, public has overrides.g_warmup=0 — the merged
        value must be 0, not 30. Anything else would re-trigger the
        validator's warmup-vs-doWarmup cross-cvar rule on the public
        profile and silently break the v0.1.0 contract.
        """
        ps = load_profile_set(default_profiles_path())
        assert ps["_base"].values["g_warmup"] == 30
        resolved = ps.resolve("public")
        assert resolved.values["g_warmup"] == 0

    def test_inherited_value_passes_through_unchanged(self) -> None:
        ps = load_profile_set(default_profiles_path())
        # cup does not override g_speed; the resolved value comes
        # from _base.
        assert "g_speed" not in ps["cup"].overrides
        assert ps.resolve("cup").values["g_speed"] == 320


# ---------------------------------------------------------------------------
# Resolver error contract — tested against synthetic fixtures
# ---------------------------------------------------------------------------
class TestResolverErrors:
    def test_unknown_profile(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {})
        ps = load_profile_set(path)
        with pytest.raises(ProfileError, match="unknown profile"):
            ps.resolve("never_existed")

    def test_extends_unknown_parent(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {
            "child.yaml": """\
                profile_name: "Child"
                extends: not_a_real_parent
                overrides: {sv_fps: 40}
            """,
        })
        ps = load_profile_set(path)
        with pytest.raises(ProfileError, match="extends unknown profile"):
            ps.resolve("child")

    def test_self_cycle(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {
            "loop.yaml": """\
                profile_name: "Loop"
                extends: loop
                overrides: {sv_fps: 40}
            """,
        })
        ps = load_profile_set(path)
        with pytest.raises(ProfileError, match="circular inheritance"):
            ps.resolve("loop")

    def test_two_profile_cycle(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {
            "a.yaml": """\
                profile_name: "A"
                extends: b
                overrides: {sv_fps: 40}
            """,
            "b.yaml": """\
                profile_name: "B"
                extends: a
                overrides: {sv_fps: 20}
            """,
        })
        ps = load_profile_set(path)
        with pytest.raises(ProfileError, match="circular inheritance") as exc:
            ps.resolve("a")
        # Both names must be in the message so the operator can find them.
        assert "a" in str(exc.value)
        assert "b" in str(exc.value)

    def test_depth_exceeds_limit(self, tmp_path: Path) -> None:
        # Build a chain longer than MAX_INHERITANCE_DEPTH.
        files = {"_root.yaml": """\
            profile_name: "Root"
            values: {sv_fps: 20}
        """}
        prev = "_root"
        chain_len = MAX_INHERITANCE_DEPTH + 1  # one longer than allowed
        for i in range(chain_len):
            stem = f"_lvl{i}"
            files[f"{stem}.yaml"] = textwrap.dedent(f"""\
                profile_name: "Lvl{i}"
                extends: {prev}
                overrides: {{sv_fps: {30 + i}}}
            """)
            prev = stem
        path = _make_dir(tmp_path, files)
        ps = load_profile_set(path)
        with pytest.raises(ProfileError, match="inheritance depth exceeds"):
            ps.resolve(prev)

    def test_unknown_cvar_with_validation(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {
            "rogue.yaml": """\
                profile_name: "Rogue"
                values: {totally_made_up: 1, sv_fps: 40}
            """,
        })
        ps = load_profile_set(path)
        with pytest.raises(ProfileError, match="unknown cvar"):
            ps.resolve("rogue", valid_cvars={"sv_fps"})

    def test_unknown_cvar_skipped_without_validation(self, tmp_path: Path) -> None:
        # When valid_cvars is None the resolver doesn't check — useful
        # for tooling that wants the raw dict.
        path = _make_dir(tmp_path, {
            "rogue.yaml": """\
                profile_name: "Rogue"
                values: {totally_made_up: 1}
            """,
        })
        ps = load_profile_set(path)
        resolved = ps.resolve("rogue")  # no valid_cvars passed
        assert resolved.values == {"totally_made_up": 1}


# ---------------------------------------------------------------------------
# Schema rejections — caught at load time, before any resolve()
# ---------------------------------------------------------------------------
class TestSchemaRejections:
    def test_missing_directory(self, tmp_path: Path) -> None:
        with pytest.raises(ProfileError, match="not found"):
            load_profile_set(tmp_path / "nope")

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {"bad.yaml": ":\n  : invalid : :\n"})
        with pytest.raises(ProfileError, match="not valid YAML"):
            load_profile_set(path)

    def test_root_must_be_mapping(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {"bad.yaml": "- a\n- b\n"})
        with pytest.raises(ProfileError, match="must be a mapping"):
            load_profile_set(path)

    def test_unknown_top_level_field(self, tmp_path: Path) -> None:
        path = _make_dir(tmp_path, {
            "bad.yaml": """\
                profile_name: "X"
                rogue: 1
                values: {sv_fps: 40}
            """,
        })
        with pytest.raises(ProfileError, match="schema validation"):
            load_profile_set(path)

    def test_extends_with_values_block_rejected(self, tmp_path: Path) -> None:
        # Concrete profiles must use `overrides:`, not `values:`.
        path = _make_dir(tmp_path, {
            "_base.yaml": """\
                profile_name: "Base"
                values: {sv_fps: 20}
            """,
            "child.yaml": """\
                profile_name: "Child"
                extends: _base
                values: {sv_fps: 40}
            """,
        })
        with pytest.raises(ProfileError, match="schema validation"):
            load_profile_set(path)

    def test_no_extends_with_overrides_block_rejected(self, tmp_path: Path) -> None:
        # Base profiles must use `values:`, not `overrides:`.
        path = _make_dir(tmp_path, {
            "rogue.yaml": """\
                profile_name: "Rogue"
                overrides: {sv_fps: 40}
            """,
        })
        with pytest.raises(ProfileError, match="schema validation"):
            load_profile_set(path)


# ---------------------------------------------------------------------------
# ProfileSet API surface
# ---------------------------------------------------------------------------
class TestProfileSetApi:
    def test_returns_profile_objects(self) -> None:
        ps = load_profile_set(default_profiles_path())
        assert isinstance(ps["cup"], Profile)

    def test_resolved_profile_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        ps = load_profile_set(default_profiles_path())
        resolved = ps.resolve("cup")
        assert isinstance(resolved, ResolvedProfile)
        with pytest.raises(FrozenInstanceError):
            resolved.profile_name = "tampered"  # type: ignore[misc]

    def test_isinstance_profileset(self) -> None:
        ps = load_profile_set(default_profiles_path())
        assert isinstance(ps, ProfileSet)
