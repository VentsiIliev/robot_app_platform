# `DispenseChannelSettings`

`DispenseChannelSettings` is the glue-system settings screen for configuring declared dispense channels instead of editing raw cells directly.

Each channel is declared in `GlueRobotSystem.dispense_channels` and binds:
- one `weight_cell_id`
- one `pump_motor_address`
- one persisted glue-type selection

The app is channel-centric by design. It keeps the operator-facing model aligned with the real glue domain: a dispensing lane is a scale plus a pump, not just a weight cell.

---

## Data Sources

The screen combines three settings domains:

- `glue/cells.json`
  - low-level weight-cell runtime settings
- `glue/dispense_channels.json`
  - selected glue type per channel
- `glue/catalog.json`
  - available glue types

It also reads the declared channel identities from `GlueRobotSystem.dispense_channels`.

---

## Exposed Actions

For each channel the user can:
- edit glue type
- edit scale URL/capacity/fetch timing
- edit calibration offset and scale
- edit measurement tuning
- tare the bound weight cell
- start and stop a pump test on the bound pump motor

`temperature_compensation` is intentionally not exposed because it is no longer part of the weight calibration model.

---

## Save Semantics

Saving a channel updates:

1. the bound `CellConfig` inside `glue/cells.json`
2. the bound `DispenseChannelConfig` inside `glue/dispense_channels.json`

The service also keeps the stored cell `motor_address` aligned to the declared channel pump address so the low-level config cannot drift away from the robot-system declaration.

For current runtime compatibility, the selected glue type is mirrored into the bound `CellConfig.type`, because some existing glue services still resolve glue type from `GLUE_CELLS`.
