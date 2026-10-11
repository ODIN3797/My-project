# v0.5.1 — Comparing independent ROS2 recordings

Use the *operator-chosen* reference recording to compare topic reception frequencies in other `.db3` or `.mcap` files. **The tool does not know whether the reference is healthy, nor whether any change is a fault, attack, regression or intentional difference in the robot mission.**

```bash
python3 -m robot_incident_analyzer compare-bags \
  normal.db3 attack.db3 another_run.db3 \
  --ratio-threshold 3 \
  --min-baseline-hz 2 \
  --min-candidate-hz 10 \
  --output comparison_output
xdg-open comparison_output/comparison.html
```

Output: `comparison.html` (dashboard with topic table and relative 1-second rate sketches), `comparison.json` (source hashes and measurements), and `COMPARISON.md` (text summary). No uploaded raw bag data, no external dependencies or network calls. ROS2 is not required for the native reader.

## How measured rates are calculated

* Compare *the same topic and message type*, not topic names alone.
* Average measured ROS2 bag reception frequency: **(message_count - 1) / (last_timestamp - first_timestamp)**, in Hz. Captures can have different durations.
* Maximum one-second message count is calculated over **the first 1000 seconds starting with each topic's first message**. Graph examples show only the first 120 topic-relative one-second bins; **the two bag clocks and task phases are NOT synchronized.**
* Status `RATE_INCREASE` requires baseline rate ≥2Hz, candidate rate ≥10Hz, both spans ≥3 seconds, at least 10 messages in each recording, and candidate mean ≥3× baseline mean by default. All heuristics are adjustable.
* A topic not recorded, a different message type, an empty bag, or too short a sample must not be called a detected fault. The report shows NOT_COMPARABLE or INSUFFICIENT_DATA.
* When a ROS2 bag exceeds `--max-messages` (default 2 million), the command **refuses a partial comparison** rather than silently returning wrong whole-recording rates.
* The tool never decodes private CDR message fields for this comparison. It reads timestamps and topic metadata only.

## First independent validation dataset

[Zenodo 17649537](https://zenodo.org/records/17649537): `Experiment_1.zip` contains two independent recorded ROS2 SQLite bags:

* `E1-1`: publisher describes normal conditions, 1501 recorded `/mobile_base_controller/cmd_vel` messages across 75.57 seconds = **19.85Hz**.
* `E1-2`: publisher describes simulated 500Hz flood of **upstream** `/input_joy/cmd_vel`; **downstream** `/mobile_base_controller/cmd_vel` records 6630 messages across 40.13 seconds = **165.19Hz**.

The downstream **8.32x observed mean rate increase** is a reproducible comparison of the two recordings and is **not the injected 500Hz rate** and **not proof that the robot failed**. The dataset intentionally simulates an attack; no independently labeled, real-world equipment fault or attack-onset timestamps have been evaluated.

## Multiple dataset coverage

* University of Vigo [RPSC Navigation.zip](https://zenodo.org/records/15433859), ~9MB compressed, physical navigation trials under different RTK/encoder/speed configurations. Differences are **expected between configurations** and cannot be called failures without reference labels.
* [BAGEL](https://github.com/Hussain004/BAGEL) `tour.mcap`, ~3.94MB, public MCAP parser compatibility example. Its physical-robot provenance is unconfirmed.
* JKK Research Dataset 02 initially looked useful, but its publicly linked download paths returned 404 on GitHub CI. **No JKK bag was analyzed**.

`.github/workflows/robot-incident-multibag-validation.yml` collects the first three independent sources on GitHub Actions and uploads **only analysis summaries**, no original bag files.

## Engineering acceptance gate before selling

1. Human-labeled fault episodes and complete nonfault windows for false-alarm/hour and recall measurements.
2. Compare real robot work phases, frame continuity, rate expectations and known controller modes.
3. Report confidence and provenance and always permit a human to inspect raw message graphs.
4. Users of third-party datasets must follow the original dataset usage, license and privacy requirements.

## Field-data-discovered semantic mapping guard

The University of Vigo bag includes `/rpsc4/global_position/raw/gps_vel` with a velocity-compatible message type. An earlier version of topic auto-discovery **mistook this GPS velocity estimate for an actuation command**, merely because it was the only matching message type. The analyzer now requires an explicit command-like topic name (such as `cmd_vel`, `velocity_cmd`) before mapping a sole standard Twist/TwistStamped topic as `command`; otherwise the operator must explicitly supply and verify an override. This prevents false command/odometry mismatch evidence in the Vigo dataset.

The real-data CI suite asserts that GPS velocity cannot be assigned to the command role. A manually overridden non-command-looking topic is allowed only with an explicit semantic warning.
