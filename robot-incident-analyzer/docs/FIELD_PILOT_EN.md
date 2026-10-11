# ROS2 Engineer Field Pilot — v0.4.2

**Goal:** determine whether an engineer can run this tool on an independently obtained ROS2 recording, and whether any detected incidents agree with **human-authored, time-stamped reference annotations**. It is *not* a benchmark unless reference labels are complete and independently reviewed.

## Actual-recording setup (offline, no robot required)

Python >= 3.10, Linux (recommended). Install dependencies separately as needed for compressed MCAP files:

```bash
python3 -m pip install --user zstandard lz4 rosbags
python3 -m robot_incident_analyzer field-validate /PATH/TO/recording.mcap \
  --origin physical --output results/robot_a
# A machine-produced HTML report and verification manifest will be created.
# Exit 0: no preconfigured coverage flags (not proof of correctness).
# Exit 3: human review required due to missing/misleading/partial evidence.
# Exit 2: invalid input or other validation error.
```

`--origin physical` is **operator-declared, never automatically verified**. For Gazebo recordings use `--origin simulation`, or `--origin unknown` if uncertain. Do NOT label fabricated test data as physical.

For custom ROS2 messages pass `--config examples/config_custom.json` after filling in your own *authorized* `.msg` definitions and semantic field paths. The tool deliberately refuses to guess vendor-specific semantics.

Run **each bag independently**; do not join unrelated robot fleets into one event timeline.

## Candidate public data sources (NOT bundled)

1. [JKK Research Dataset 02](https://jkk-research.github.io/dataset/jkk_dataset_02/): authentic ROS2/MCAP vehicle-sensor drives, with official sample download. Real-world compatibility/performance exercise; **NOT known to contain labeled incidents**. Expect many unsupported sensor types and incomplete coverage.
2. [Autoware Urban Localization Dataset discussion](https://github.com/orgs/autowarefoundation/discussions/5135): urban localization ROS2 DB3 with setup instructions; real-world localization sequences, but not validated ground-truth failure labels for this tool.
3. [BAGEL bundled tour MCAP](https://github.com/Hussain004/BAGEL): useful independent *file-format interoperability test*. Its sample is constructed by a script; **NOT a field validation dataset**.

**Data download was not possible in the isolated assistant environment.** These are candidate sources, not recordings that were run here. Check source-specific usage rights before any public redistribution. For a meaningful anomaly benchmark, secure three independently annotated incidents from volunteers who may keep their files private and run everything locally.

## Human validation sheet

Create `labels.csv` with this exact schema:

```csv
case_id,code,time_epoch,tolerance_s
case_01,TF_MAP_ODOM_JUMP,1791633600.25,0.3
case_01,CMD_ODOM_MISMATCH,1791633600.31,0.5
```

The numbers above are **fictional demo examples**, not labels from a real robot. Use UTC UNIX seconds for the actual reference incident time. You may also use the actual filename as `case_id`. Each expected event is matched at most once, by exact code within a tolerance window.

```bash
python3 -m robot_incident_analyzer field-validate \
  /PATH/TO/recording.mcap \
  --labels labels.csv --origin physical --output results/annotated
```

`field_results.json` records SHA-256 hash, file size, topic count, selected mappings, warnings, event codes, machine-labeled event recall, and time. `FIELD_RESULTS.md` gives a short summary. Individual `case_XX/report.html` files contain events and may contain **private** log strings.

**Important:** If references are incomplete, only *labelled-event recall* is calculated. Precision, specificity, false-positive rate, or classification accuracy cannot be established. Human reviewers must additionally note missed incidents, false alerts, and whether the command and feedback topics actually represent the same robot.

## 15-minute participant exercise

- Does the tool run without remote data access? Record Python version, OS, installation time.
- Are at least some expected standard message types decoded? Record warnings and unsupported types.
- Is topic discovery correct? Do not assume a matching name means matching semantics.
- Do unexpected warnings appear? Compare with Foxglove or `ros2 bag info`.
- Review at least one predicted anomaly in a trusted reference tool. Mark confirmed observation / false alert / indeterminate.
- Estimate minutes spent with your existing workflow versus this report (same task).
- Without sharing raw data, optionally share *redacted* `field_results.json` and your annotated labels.

No participant feedback has been obtained at publication time. Contacting overseas participants and commercial evaluation are **separate tasks**.
