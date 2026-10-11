# Recorded state-change timeline (v0.4.9)

## Demo

```bash
python3 -m robot_incident_analyzer demo-states --output state_demo
python3 -m robot_incident_analyzer analyze state_demo/fictional_state_transitions.mcap --output state_report --pdf
```

Install the optional PDF dependency with `python3 -m pip install '.[pdf]'` when required.

The demo is synthetic and intentionally includes two robot namespaces. Click a row in **Explicit state transitions** to synchronize the time cursor and open its original log. Choose a finding in **Incident workbench** to inspect its last 30 seconds of **recorded** state changes, not inferred controller state.

## Supported explicit syntax

```text
[mission_manager] mode=AUTONOMOUS; docking_state=APPROACH
[mission_manager] docking_state=ALIGN mission_state=RUNNING
[mission_manager] charging_state=HANDSHAKE
[mission_manager] charging_state=FAILED
```

Unlabeled prose like `Going to dock now` is deliberately not interpreted. Only `key=value` or `key: value` with an allowed key and bounded token value counts. Default keys include `mode`, `state`, `phase`, `docking_state`, `charging_state`, `navigation_state`, `mission_state`, `command_state`, `motion_state`, `controller_state` and `safety_state`. For custom names create `state_keys` in a config file (see `examples/state_config.json`).

```bash
python3 -m robot_incident_analyzer analyze recording.mcap --config examples/state_config.json --output out
```

## Evidence boundaries

Each transition includes `source`, `robot_id`, `event_id`, `timestamp`, `field`, `from`, `to` in `report.json`. `from=null` means first seen, **not a verified startup state**. Repeated same value is not a new transition. State is not carried forward as guaranteed truth. Context is limited to observations in the last 30 seconds, scoped to the same source and robot identity. If a robot identity cannot be determined, the tool does not assign a recorded state to a different known robot.

## Next steps

Support explicit custom ROS2 state topics via user-configured message-field mappings, evaluate on consented real robot recordings, and measure diagnosis-time savings against existing visualization tools.
