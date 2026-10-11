# Invitation: ROS2 incident analysis pilot (alpha)

**Status:** not yet sent to external engineers. No customer feedback has been collected.

We are testing an open-source *offline* ROS2 MCAP/DB3 incident investigation tool. It checks standard ROS2 topic metadata and selected payloads, then produces evidence-linked HTML and JSON reports. It is **not** intended for safety-critical decisions and does **not** claim verified root-cause diagnosis.

## Who should test

- ROS2 engineers familiar with `rosbag2` and normal/error recordings.
- Users who can share feedback without disclosing employer/customer private data.
- Ideally owners of verified real robot recordings with known incident times and authorized sharing rights.

## 10-minute setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m robot_incident_analyzer demo --output demo_data
python -m robot_incident_analyzer analyze demo_data --output output
```

Open `output/report.html`. Try your *own authorized* local bag:

```bash
python -m robot_incident_analyzer field-validate recording.mcap \
  --origin physical --output results
```

Choose `--origin physical` **only** when that provenance is independently known; otherwise select `unknown`/`simulation`. Validation exit code **3** means human review required, not a crash.

## Questions to answer (no data upload required)

1. Did installation and first report take less than 10 minutes? If not, what failed?
2. Did topic auto-discovery map the actual velocity command and feedback correctly?
3. Which warnings or findings were misleading? Please describe without sharing confidential logs.
4. How much time did the tool save or add compared with your normal workflow?
5. Which currently unsupported ROS2 message types matter most to your team?
6. Would your team pay for an improved evidence-first workflow? Why or why not?

## Safety and privacy

- Never upload proprietary, personally identifying, or employer/customer data to a public issue.
- Report excerpts may contain private node names, maps, and identifiers. Redact them.
- A `/rosout` error is not proof of the physical root cause.
- Unsupported types and truncated message limits are shown as incomplete coverage.

## Acceptance gate for a future public beta

- At least 3 independently sourced real-recording tests with verified provenance.
- At least 5 independent ROS2 engineers complete or attempt the tutorial.
- Human-labelled incidents and false alarms reviewed; publish results and failure cases.
- At least 4/5 complete installation without direct assistance, with observation documented.
