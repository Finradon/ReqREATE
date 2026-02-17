from __future__ import annotations

import pytest

from reqre.gh.param_resolver import (
    _resolve_d1_pair_values,
    resolve_d1_parameters,
    resolve_d2_module_plan,
)


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, query: str, params=None):
        self.calls.append((query, params))
        if "RETURN DISTINCT" in query:
            return list(self._rows)
        return []


class _FakeD2Client:
    def __init__(self, girder_props: dict, module_count: int):
        self._girder_props = girder_props
        self._module_count = module_count
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, query: str, params=None):
        self.calls.append((query, params))
        if "gh_samples/t_girder_d2.gh" in query:
            return [{"girder_id": "g_d2_1", "girder_props": dict(self._girder_props)}]
        if "module_count" in query:
            return [{"module_count": self._module_count}]
        return []


def test_resolve_d1_pair_values_uses_abutment_values_and_derives_offset1() -> None:
    abutment_props = {
        "gh_params": {
            "ABT_width": 6400.0,
            "ABT_ledgeheight": 750.0,
            "ABT_ledgewidth": 1400.0,
            "ABT_offset": 450.0,
        }
    }
    girder_props = {
        "gh_params": {
            "GRD_width": 5000.0,
            "GRD_height": 500.0,
            "GRD_offset1": 500.0,
            "GRD_offset2": 500.0,
        }
    }
    abutment_defaults = {}
    girder_defaults = {}

    abutment_updates, girder_updates = _resolve_d1_pair_values(
        abutment_props,
        girder_props,
        {},
        {},
        abutment_defaults,
        girder_defaults,
    )

    assert abutment_updates == {
        "ABT_width": 6400.0,
        "ABT_ledgeheight": 750.0,
        "ABT_ledgewidth": 1400.0,
        "ABT_offset": 450.0,
    }
    assert girder_updates == {
        "GRD_width": 6400.0,
        "GRD_height": 750.0,
        "GRD_offset1": 700.0,
        "GRD_offset2": 450.0,
    }


def test_resolve_d1_pair_values_can_backsolve_ledgewidth_from_girder_offset1() -> None:
    abutment_props = {"gh_params": {}}
    girder_props = {"gh_params": {"GRD_offset1": 600.0}}
    abutment_defaults = {
        "ABT_width": 5000.0,
        "ABT_ledgeheight": 500.0,
        "ABT_offset": 500.0,
    }
    girder_defaults = {
        "GRD_width": 5000.0,
        "GRD_height": 500.0,
        "GRD_offset2": 500.0,
    }

    abutment_updates, girder_updates = _resolve_d1_pair_values(
        abutment_props,
        girder_props,
        {},
        {},
        abutment_defaults,
        girder_defaults,
    )

    assert abutment_updates["ABT_ledgewidth"] == 1200.0
    assert girder_updates["GRD_offset1"] == 600.0


def test_resolve_d1_parameters_writes_updates() -> None:
    client = _FakeClient(
        [
            {
                "abutment_id": "a1",
                "girder_id": "g1",
                "abutment_props": {
                    "gh_params": {
                        "ABT_width": 6200.0,
                        "ABT_ledgeheight": 700.0,
                        "ABT_ledgewidth": 1200.0,
                        "ABT_offset": 450.0,
                    }
                },
                "girder_props": {"gh_params": {}},
                "dst_interface": "GRD_interface1",
            }
        ]
    )

    resolved = resolve_d1_parameters(client, write_shared_parameter_nodes=False)

    assert len(resolved) == 1
    assert resolved[0].girder_updates["GRD_offset1"] == 600.0
    assert len(client.calls) == 4
    _, params = client.calls[3]
    assert params["abutment_id"] == "a1"
    assert params["girder_id"] == "g1"
    assert params["girder_updates"]["GRD_width"] == 6200.0
    assert params["girder_updates"]["GRD_height"] == 700.0
    assert params["girder_updates"]["GRD_offset2"] == 450.0


def test_resolve_d1_parameters_detects_conflicting_updates_for_same_girder() -> None:
    client = _FakeClient(
        [
            {
                "abutment_id": "a1",
                "girder_id": "g1",
                "abutment_props": {
                    "gh_params": {
                        "ABT_width": 6200.0,
                        "ABT_ledgeheight": 700.0,
                        "ABT_ledgewidth": 1200.0,
                        "ABT_offset": 450.0,
                    }
                },
                "girder_props": {"gh_params": {}},
                "dst_interface": "GRD_interface1",
            },
            {
                "abutment_id": "a2",
                "girder_id": "g1",
                "abutment_props": {
                    "gh_params": {
                        "ABT_width": 6800.0,
                        "ABT_ledgeheight": 700.0,
                        "ABT_ledgewidth": 1200.0,
                        "ABT_offset": 450.0,
                    }
                },
                "girder_props": {"gh_params": {}},
                "dst_interface": "GRD_interface2",
            },
        ]
    )

    with pytest.raises(RuntimeError, match="Conflicting resolved value"):
        resolve_d1_parameters(client, write_shared_parameter_nodes=False)


def test_resolve_d1_pair_values_prefers_bound_parameter_values() -> None:
    abutment_props = {"gh_params": {"ABT_width": 5000.0, "ABT_ledgewidth": 1000.0}}
    girder_props = {"gh_params": {"GRD_width": 5000.0}}
    abutment_bound = {
        "ABT_width": 6600.0,
        "ABT_ledgeheight": 800.0,
        "ABT_ledgewidth": 1600.0,
        "ABT_offset": 550.0,
    }
    girder_bound = {}
    abutment_defaults = {}
    girder_defaults = {}

    abutment_updates, girder_updates = _resolve_d1_pair_values(
        abutment_props,
        girder_props,
        abutment_bound,
        girder_bound,
        abutment_defaults,
        girder_defaults,
    )

    assert abutment_updates["ABT_width"] == 6600.0
    assert abutment_updates["ABT_ledgeheight"] == 800.0
    assert abutment_updates["ABT_ledgewidth"] == 1600.0
    assert abutment_updates["ABT_offset"] == 550.0
    assert girder_updates["GRD_width"] == 6600.0
    assert girder_updates["GRD_height"] == 800.0
    assert girder_updates["GRD_offset1"] == 800.0
    assert girder_updates["GRD_offset2"] == 550.0


def test_resolve_d2_module_plan_counts_missing_modules_from_length() -> None:
    client = _FakeD2Client(
        girder_props={"param_D2_GRD_length": 10000.0},
        module_count=1,
    )

    plan = resolve_d2_module_plan(client, module_length=1000.0)

    assert plan.girder_id == "g_d2_1"
    assert plan.girder_length == 10000.0
    assert plan.target_modules == 10
    assert plan.current_modules == 1
    assert plan.insertions_required == 9


def test_resolve_d2_module_plan_falls_back_to_default_d2_length() -> None:
    client = _FakeD2Client(girder_props={}, module_count=1)

    plan = resolve_d2_module_plan(client, module_length=1000.0)

    assert plan.girder_length == 20000.0
    assert plan.target_modules == 20
    assert plan.insertions_required == 19


def test_resolve_d2_module_plan_rejects_non_positive_module_length() -> None:
    client = _FakeD2Client(girder_props={}, module_count=0)

    with pytest.raises(ValueError, match="positive"):
        resolve_d2_module_plan(client, module_length=0)
