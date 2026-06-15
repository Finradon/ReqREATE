# Rule Recreation Prompts

Use this wrapper instruction for every rule:

```text
You are recreating one ReqRE DPO rule for an LLM-rule-generation study.

Task:
- Create exactly one new rule JSON at `json_rules/fbi_rules/.../<rule>.json`.
- Set `rule_id` to the filename stem.
- Follow the ReqRE DPO JSON schema exactly.
- Do not inspect or copy the existing canonical rule under `json_rules/`.
- Use only the rule description I provide below.
- The rule description is structured as LHS, RHS, and NAC.
- Do not add any separate textual “interface” section; interface information should only appear inside the JSON rule itself where required.
- Keep the JSON minimal and schema-compliant.

After writing the rule:
1. Run:
   `uv run python scripts/validate_and_document_rule.py json_rules/fbi_rules/.../<rule>.json --compare-to json_rules/.../<canonical-rule>.json`
2. If `uv` is not available, run:
   `~/.local/bin/uv run python scripts/validate_and_document_rule.py json_rules/fbi_rules/.../<rule>.json --compare-to json_rules/.../<canonical-rule>.json`

Output requirements:
- Write the JSON rule file.
- Run the validation/documentation command.
- Report briefly whether validation succeeded and what similarity percentage was recorded.

Rule description:

```

## 1. `json_rules/fbi_rules/requirements/satisfy_d1_1_bridge.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/requirements/satisfy_d1_1_bridge.json`.

LHS: one `Requirement` node `req_d1_1` with `external_id: "D1.1"`.

RHS: the same `req_d1_1` node appears again. Add four `FunctionalElement` nodes named `Bridge`, `Substructure`, `Superstructure`, and `Foundation`. Add one `SATISFIES` edge from `req_d1_1` to `Bridge`. Add three `DECOMPOSES` edges from `Substructure`, `Superstructure`, and `Foundation` to `Bridge`.

NAC: block the rule if `req_d1_1` already has any outgoing `SATISFIES` edge to an existing satisfier.
```

## 2. `json_rules/fbi_rules/requirements/satisfy_d2_1_girder.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/requirements/satisfy_d2_1_girder.json`.

LHS: a `Requirement` node `req_d2_1` with `external_id: "D2.1"`, a `FunctionalElement` node `fe_superstructure` named `Superstructure`, a `FunctionalElement` node `fe_abutment` named `Abutment`, and two `BuildingElement` + `AbutmentElement` nodes `be_abutment_element_1` and `be_abutment_element_2`, both with `gh_file: "gh_samples/abutment_d1.gh"` and `detail_level: "D1"`, named `AbutmentElement1` and `AbutmentElement2`.

RHS: all LHS nodes appear again. Add a `FunctionalElement` node `fe_girder` named `Girder` and a `BuildingElement` + `GirderElement` node `be_girder_element` named `GirderElement` with `gh_file: "gh_samples/Girder.gh"` and `detail_level: "D1"`. Add eight `Parameter` + `D1InputParameter` nodes with keys `D1_I1_WIDTH`, `D1_I1_LEDGE_HEIGHT`, `D1_I1_LEDGE_WIDTH`, `D1_I1_OFFSET`, `D1_I2_WIDTH`, `D1_I2_LEDGE_HEIGHT`, `D1_I2_LEDGE_WIDTH`, and `D1_I2_OFFSET`, all with `value: null` and `unit: "mm"`. Add `SATISFIES` from `req_d2_1` to `fe_girder`, `DECOMPOSES` from `fe_girder` to `fe_superstructure`, and `DECOMPOSES` from `be_girder_element` to `fe_girder`. Add one `INTERFACES` edge from `be_abutment_element_1` to `be_girder_element` using `ABT_interface2 -> GRD_interface1`, and one from `be_abutment_element_2` to `be_girder_element` using `ABT_interface2 -> GRD_interface2`. Add `USES_PARAM` edges so abutment 1 and the girder share width, ledge height, and offset for interface 1, abutment 1 alone uses ledge width for interface 1, abutment 2 and the girder share width, ledge height, and offset for interface 2, and abutment 2 alone uses ledge width for interface 2. Use the same input names as the canonical rule: `ABT_width`, `GRD_width`, `ABT_ledgeheight`, `GRD_height`, `ABT_ledgewidth`, `ABT_offset`, and `GRD_offset2`.

NAC: block the rule if `req_d2_1` already has any outgoing `SATISFIES` edge.
```

## 3. `json_rules/fbi_rules/requirements/satisfy_d2_1_1_girder_element.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/requirements/satisfy_d2_1_1_girder_element.json`.

LHS: a `Requirement` node `req_d2_1_1` with `external_id: "D2.1.1"` and a `FunctionalElement` node `fe_girder` named `Girder`.

RHS: both LHS nodes appear again. Add a `BuildingElement` + `GirderElement` node `be_girder_element` named `GirderElement` with `gh_file: "gh_samples/t_girder_d2.gh"` and `detail_level: "D2"`. Add `SATISFIES` from `req_d2_1_1` to `be_girder_element` and `DECOMPOSES` from `be_girder_element` to `fe_girder`.

NAC: block the rule if `req_d2_1_1` already has any outgoing `SATISFIES` edge.
```

## 4. `json_rules/fbi_rules/substructure/decompose_substructure_abutment.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/substructure/decompose_substructure_abutment.json`.

LHS: one `FunctionalElement` node `substructure` named `Substructure`.

RHS: the same `substructure` node appears again. Add a `FunctionalElement` node `abutment` named `Abutment`. Add two `BuildingElement` + `AbutmentElement` nodes `abutment_element_1` and `abutment_element_2`, both with `gh_file: "gh_samples/abutment_d1.gh"` and `detail_level: "D1"`, named `AbutmentElement1` and `AbutmentElement2`. Add `DECOMPOSES` from `abutment` to `substructure`, and from each abutment element to `abutment`.

NAC: block the rule if an `Abutment` functional element already decomposes this `Substructure`.
```

## 5. `json_rules/fbi_rules/superstructure/refine_girder_d1_to_d2.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/superstructure/refine_girder_d1_to_d2.json`.

LHS: one `BuildingElement` + `GirderElement` node `girder_element_d1` named `GirderElement` with `gh_file: "gh_samples/Girder.gh"` and `detail_level: "D1"`.

RHS: the same `girder_element_d1` node appears again. Add a `BuildingElement` + `GirderElement` node `girder_element_d2` named `GirderElement` with `gh_file: "gh_samples/t_girder_d2.gh"` and `detail_level: "D2"`. Add `DECOMPOSES` from `girder_element_d2` to `girder_element_d1`.

NAC: block the rule if a D2 girder element with `gh_file: "gh_samples/t_girder_d2.gh"` already decomposes `girder_element_d1`.
```

## 6. `json_rules/fbi_rules/substructure/decompose_abutment_d1_if1.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/substructure/decompose_abutment_d1_if1.json`.

LHS: a `Requirement` node `req_d2_2` with `external_id: "D2.2"`, a D1 `AbutmentElement` building element `abutment_element_d1`, a D1 `GirderElement` building element `girder_element_d1` with `gh_file: "gh_samples/Girder.gh"`, a D2 `GirderElement` building element `girder_element_d2` with `gh_file: "gh_samples/t_girder_d2.gh"`, and one `INTERFACES` edge from `abutment_element_d1` to `girder_element_d1` using `ABT_interface2 -> GRD_interface1`.

RHS: all LHS nodes appear again, and the same `INTERFACES` edge from the abutment to the D1 girder appears again. Add three D2 building elements: `abutment_1_side_wall_1`, `abutment_1_side_wall_2`, and `abutment_1_middle_wall`, with the side walls using `gh_samples/abutment_side_d2.gh`, the middle wall using `gh_samples/abutment_middle_d2.gh`, and all with `detail_level: "D2"`. Add `SATISFIES` from `req_d2_2` to `abutment_1_middle_wall`. Add `DECOMPOSES` from each of the three new D2 nodes to `abutment_element_d1`. Add two `INTERFACES` edges from the side walls to the middle wall using `ABT_SD_interface2 -> ABT_MD_interface1` and `ABT_SD_interface2 -> ABT_MD_interface2`. Add one `INTERFACES` edge from `abutment_1_middle_wall` to `girder_element_d2` using `ABT_MD_interface4 -> D2_GRD_interface1`.

NAC: block the rule if a D2 `AbutmentMiddleWallElement` already decomposes `abutment_element_d1`.
```

## 7. `json_rules/fbi_rules/substructure/decompose_abutment_d1_if2.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/substructure/decompose_abutment_d1_if2.json`.

LHS: a `Requirement` node `req_d2_2` with `external_id: "D2.2"`, a D1 `AbutmentElement` building element `abutment_element_d1`, a D1 `GirderElement` building element `girder_element_d1` with `gh_file: "gh_samples/Girder.gh"`, a D2 `GirderElement` building element `girder_element_d2` with `gh_file: "gh_samples/t_girder_d2.gh"`, and one `INTERFACES` edge from `abutment_element_d1` to `girder_element_d1` using `ABT_interface2 -> GRD_interface2`.

RHS: all LHS nodes appear again, and the same `INTERFACES` edge from the abutment to the D1 girder appears again. Add three D2 building elements: `abutment_2_side_wall_1`, `abutment_2_side_wall_2`, and `abutment_2_middle_wall`, with the side walls using `gh_samples/abutment_side_d2.gh`, the middle wall using `gh_samples/abutment_middle_d2.gh`, and all with `detail_level: "D2"`. Add `SATISFIES` from `req_d2_2` to `abutment_2_middle_wall`. Add `DECOMPOSES` from each of the three new D2 nodes to `abutment_element_d1`. Add two `INTERFACES` edges from the side walls to the middle wall using `ABT_SD_interface2 -> ABT_MD_interface1` and `ABT_SD_interface2 -> ABT_MD_interface2`. Add one `INTERFACES` edge from `abutment_2_middle_wall` to `girder_element_d2` using `ABT_MD_interface4 -> D2_GRD_interface2`.

NAC: block the rule if a D2 `AbutmentMiddleWallElement` already decomposes `abutment_element_d1`.
```

## 8. `json_rules/fbi_rules/substructure/decompose_abutment_d1_if1_if2.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/substructure/decompose_abutment_d1_if1_if2.json`.

LHS: a D1 `AbutmentElement` building element `abutment_element_d1`, a D1 `GirderElement` building element `girder_element_d1` with `gh_file: "gh_samples/Girder.gh"`, a D2 `GirderElement` building element `girder_element_d2` with `gh_file: "gh_samples/t_girder_d2.gh"`, and two `INTERFACES` edges from `abutment_element_d1` to `girder_element_d1`, one using `ABT_interface2 -> GRD_interface1` and one using `ABT_interface2 -> GRD_interface2`.

RHS: all LHS nodes appear again, and both original `INTERFACES` edges to the D1 girder appear again. Add six D2 building elements: `abutment_1_side_wall_1`, `abutment_1_side_wall_2`, `abutment_1_middle_wall`, `abutment_2_side_wall_1`, `abutment_2_side_wall_2`, and `abutment_2_middle_wall`. The side walls use `gh_samples/abutment_side_d2.gh`, the middle walls use `gh_samples/abutment_middle_d2.gh`, and all have `detail_level: "D2"`. Add `DECOMPOSES` from all six new D2 nodes to `abutment_element_d1`. Add side-wall-to-middle-wall `INTERFACES` edges for both triplets using `ABT_SD_interface2 -> ABT_MD_interface1` and `ABT_SD_interface2 -> ABT_MD_interface2`. Add one `INTERFACES` edge from `abutment_1_middle_wall` to `girder_element_d2` using `ABT_MD_interface4 -> D2_GRD_interface1`, and one from `abutment_2_middle_wall` to `girder_element_d2` using `ABT_MD_interface4 -> D2_GRD_interface2`.

NAC: block the rule if a D2 `AbutmentMiddleWallElement` already decomposes `abutment_element_d1`.
```

## 9. `json_rules/fbi_rules/modules/girder/seed_girder_module_d3.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/girder/seed_girder_module_d3.json`.

LHS: a `Requirement` node `req_d2_2` with `external_id: "D2.2"`, a D2 `GirderElement` building element `girder_element_d2` with `gh_file: "gh_samples/t_girder_d2.gh"`, two D2 `AbutmentMiddleWallElement` building elements `abutment_middle_wall_1` and `abutment_middle_wall_2` with `gh_file: "gh_samples/abutment_middle_d2.gh"`, and two `INTERFACES` edges from those middle walls to `girder_element_d2`, one using `ABT_MD_interface4 -> D2_GRD_interface1` and one using `ABT_MD_interface4 -> D2_GRD_interface2`.

RHS: the same requirement, D2 girder, and both middle wall nodes appear again. Add one D2 `BuildingElement` + `GirderElement` node `girder_module_d3` with `gh_file: "gh_samples/t_girder_module_d3.gh"`. Add `SATISFIES` from `req_d2_2` to `girder_module_d3`, `DECOMPOSES` from `girder_module_d3` to `girder_element_d2`, and two new `INTERFACES` edges from the two middle walls to `girder_module_d3` using `ABT_MD_interface4 -> D3_GRD_interface1` and `ABT_MD_interface4 -> D3_GRD_interface2`. Do not carry over the old middle-wall-to-D2-girder interface edges into the RHS.

NAC: none.
```

## 10. `json_rules/fbi_rules/modules/girder/grow_girder_module_d3.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/girder/grow_girder_module_d3.json`.

LHS: a `Requirement` node `req_d2_2` with `external_id: "D2.2"`, a D2 `GirderElement` building element `girder_element_d2` with `gh_file: "gh_samples/t_girder_d2.gh"`, a current D2 `BuildingElement` + `GirderElement` node `girder_module_current` with `gh_file: "gh_samples/t_girder_module_d3.gh"`, a D2 `AbutmentMiddleWallElement` node `abutment_middle_wall_tail` with `gh_file: "gh_samples/abutment_middle_d2.gh"`, a `DECOMPOSES` edge from `girder_module_current` to `girder_element_d2`, and an `INTERFACES` edge from `abutment_middle_wall_tail` to `girder_module_current` using `ABT_MD_interface4 -> D3_GRD_interface1`.

RHS: all LHS nodes appear again, and the `DECOMPOSES` edge from `girder_module_current` to `girder_element_d2` appears again. Add one new D2 `BuildingElement` + `GirderElement` node `girder_module_new` with `gh_file: "gh_samples/t_girder_module_d3.gh"`. Add `SATISFIES` from `req_d2_2` to `girder_module_new`, `DECOMPOSES` from `girder_module_new` to `girder_element_d2`, an `INTERFACES` edge from `girder_module_current` to `girder_module_new` using `D3_GRD_interface4 -> D3_GRD_interface3`, and an `INTERFACES` edge from `abutment_middle_wall_tail` to `girder_module_new` using `ABT_MD_interface4 -> D3_GRD_interface1`. Do not carry over the old tail middle-wall-to-current-module interface edge into the RHS.

NAC: none.
```

## 11. `json_rules/fbi_rules/modules/attachments/attach_kappe_d3_if5.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/attachments/attach_kappe_d3_if5.json`. Keep the filename and rule_id exactly as given even though the actual girder-side interface used in this rule is `D3_GRD_interface6`.

LHS: two `Requirement` nodes `req_d2_4` and `req_d2_2` with `external_id` values `D2.4` and `D2.2`, plus one D2 `BuildingElement` + `GirderElement` node `girder_module` with `gh_file: "gh_samples/t_girder_module_d3.gh"`.

RHS: all LHS nodes appear again. Add one D2 `BuildingElement` + `KappeElement` node `kappe_element` with `gh_file: "gh_samples/kappe_d3.gh"`. Add `SATISFIES` from both requirements to `kappe_element`, `DECOMPOSES` from `kappe_element` to `girder_module`, and an `INTERFACES` edge from `girder_module` to `kappe_element` using `D3_GRD_interface6 -> KP_interface1`.

NAC: block the rule if the girder module already has an `INTERFACES` edge to an existing Kappe element using `D3_GRD_interface6 -> KP_interface1`.
```

## 12. `json_rules/fbi_rules/modules/attachments/attach_kappe_d3_if6.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/attachments/attach_kappe_d3_if6.json`. Keep the filename and rule_id exactly as given even though the actual girder-side interface used in this rule is `D3_GRD_interface5`.

LHS: two `Requirement` nodes `req_d2_4` and `req_d2_2` with `external_id` values `D2.4` and `D2.2`, plus one D2 `BuildingElement` + `GirderElement` node `girder_module` with `gh_file: "gh_samples/t_girder_module_d3.gh"`.

RHS: all LHS nodes appear again. Add one D2 `BuildingElement` + `KappeElement` node `kappe_element` with `gh_file: "gh_samples/kappe_d3.gh"`. Add `SATISFIES` from both requirements to `kappe_element`, `DECOMPOSES` from `kappe_element` to `girder_module`, and an `INTERFACES` edge from `girder_module` to `kappe_element` using `D3_GRD_interface5 -> KP_interface1`.

NAC: block the rule if the girder module already has an `INTERFACES` edge to an existing Kappe element using `D3_GRD_interface5 -> KP_interface1`.
```

## 13. `json_rules/fbi_rules/modules/attachments/attach_expansion_d3_if1.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/attachments/attach_expansion_d3_if1.json`.

LHS: a `Requirement` node `req_d2_1` with `external_id: "D2.1"`, a D2 `BuildingElement` + `GirderElement` node `girder_module` with `gh_file: "gh_samples/t_girder_module_d3.gh"`, a D2 `AbutmentMiddleWallElement` node `abutment_middle_wall` with `gh_file: "gh_samples/abutment_middle_d2.gh"`, and one `INTERFACES` edge from `abutment_middle_wall` to `girder_module` using `ABT_MD_interface4 -> D3_GRD_interface1`.

RHS: all LHS nodes appear again, and the same abutment-middle-wall-to-girder-module `INTERFACES` edge appears again. Add one D2 `BuildingElement` + `ExpansionElement` node `expansion_element` with `gh_file: "gh_samples/expansion_d3.gh"`. Add `SATISFIES` from `req_d2_1` to `expansion_element`, `DECOMPOSES` from `expansion_element` to `girder_module`, and an `INTERFACES` edge from `girder_module` to `expansion_element` using `D3_GRD_interface4 -> EXP_interface1`.

NAC: block the rule if the girder module already has an `INTERFACES` edge to an existing Expansion element using `D3_GRD_interface4 -> EXP_interface1`.
```

## 14. `json_rules/fbi_rules/modules/attachments/attach_expansion_d3_if2.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/attachments/attach_expansion_d3_if2.json`.

LHS: a `Requirement` node `req_d2_1` with `external_id: "D2.1"`, a D2 `BuildingElement` + `GirderElement` node `girder_module` with `gh_file: "gh_samples/t_girder_module_d3.gh"`, a D2 `AbutmentMiddleWallElement` node `abutment_middle_wall` with `gh_file: "gh_samples/abutment_middle_d2.gh"`, and one `INTERFACES` edge from `abutment_middle_wall` to `girder_module` using `ABT_MD_interface4 -> D3_GRD_interface2`.

RHS: all LHS nodes appear again, and the same abutment-middle-wall-to-girder-module `INTERFACES` edge appears again. Add one D2 `BuildingElement` + `ExpansionElement` node `expansion_element` with `gh_file: "gh_samples/expansion_d3.gh"`. Add `SATISFIES` from `req_d2_1` to `expansion_element`, `DECOMPOSES` from `expansion_element` to `girder_module`, and an `INTERFACES` edge from `girder_module` to `expansion_element` using `D3_GRD_interface3 -> EXP_interface2`.

NAC: block the rule if the girder module already has an `INTERFACES` edge to an existing Expansion element using `D3_GRD_interface3 -> EXP_interface2`.
```

## 15. `json_rules/fbi_rules/modules/foundation/attach_foundation_d2_middle_wall.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/foundation/attach_foundation_d2_middle_wall.json`.

LHS: a `Requirement` node `req_d2_5` with `external_id: "D2.5"` and a D2 `AbutmentMiddleWallElement` node `abutment_middle_wall` with `gh_file: "gh_samples/abutment_middle_d2.gh"`.

RHS: both LHS nodes appear again. Add one D2 `BuildingElement` + `FoundationElement` node `foundation_element` with `gh_file: "gh_samples/foundation_d2.gh"`. Add `SATISFIES` from `req_d2_5` to `foundation_element`, `DECOMPOSES` from `foundation_element` to `abutment_middle_wall`, and an `INTERFACES` edge from `abutment_middle_wall` to `foundation_element` using `ABT_MD_interface3 -> FND_interface1`.

NAC: block the rule if the abutment middle wall already has an `INTERFACES` edge to an existing Foundation element using `ABT_MD_interface3 -> FND_interface1`.
```

## 16. `json_rules/fbi_rules/modules/attachments/attach_fahrbahn_d3_if2.json`

```text
Create a new ReqRE DPO rule JSON at `json_rules/fbi_rules/modules/attachments/attach_fahrbahn_d3_if2.json`.

LHS: a D2 `BuildingElement` + `GirderElement` node `girder_module` with `gh_file: "gh_samples/t_girder_module_d3.gh"`, a D2 `AbutmentMiddleWallElement` node `abutment_middle_wall` with `gh_file: "gh_samples/abutment_middle_d2.gh"`, a D2 `ExpansionElement` node `expansion_element` with `gh_file: "gh_samples/expansion_d3.gh"`, an `INTERFACES` edge from `abutment_middle_wall` to `girder_module` using `ABT_MD_interface4 -> D3_GRD_interface2`, an `INTERFACES` edge from `girder_module` to `expansion_element` using `D3_GRD_interface3 -> EXP_interface2`, and a `DECOMPOSES` edge from `expansion_element` to `girder_module`.

RHS: all LHS nodes and all three LHS edges appear again. Add one D2 `BuildingElement` + `FahrbahnElement` node `fahrbahn_element` with `gh_file: "gh_samples/fahrbahn_d3.gh"`. Add `DECOMPOSES` from `fahrbahn_element` to `girder_module`, and an `INTERFACES` edge from `girder_module` to `fahrbahn_element` using `D3_GRD_interface7 -> FB_interface1`.

NAC: block the rule if the girder module already has an `INTERFACES` edge to an existing Fahrbahn element using `D3_GRD_interface7 -> FB_interface1`.
```
