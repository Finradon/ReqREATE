# Rule Set

This directory contains the canonical JSON rule set organized into smaller
functional groups.

## Layout

- `requirements/`: requirement satisfaction rules
- `substructure/`: abutment and substructure decomposition rules
- `superstructure/`: girder decomposition rules
- `modules/foundation/`: foundation attachment rules
- `modules/girder/`: D3 girder module growth rules
- `modules/attachments/`: component attachment rules for the girder module

## Naming

- Filenames use lower snake_case.
- The stem starts with the action, such as `satisfy_`, `decompose_`, `refine_`, `seed_`, `grow_`, or `attach_`.
- Detail levels and interface variants are encoded in the stem, for example `d1`, `d2`, `d3`, `if1`, `if2`, or `if5`.
- Each file's `rule_id` now matches its filename stem.

## Notes

- `legacy/` contains the previous flat rule files for reference.
- This reorganizes files only; it does not change rule semantics.
- The interface-variant files are still separate because they differ only by
  interface mappings and are good candidates for later parameterization.
- Each promoted rule file uses a matching filename stem and `rule_id`.
