from __future__ import annotations

import pytest

from reqre.gh.param_resolver import _resolve_d1_pair_values, resolve_d1_parameters


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, query: str, params=None):
        self.calls.append((query, params))
        if "RETURN DISTINCT" in query:
            return list(self._rows)
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
    assert len(client.calls) == 2
    _, params = client.calls[1]
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
