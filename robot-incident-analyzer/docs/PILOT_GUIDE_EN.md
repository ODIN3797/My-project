# Robot Incident Analyzer — Early ROS 2 Engineer Pilot

**Experimental alpha, v0.4.1. Not suitable for robot control, safety, or automated root-cause decisions.**

## What is it?
An offline Python tool that reads selected ROS 2 MCAP/DB3 and event CSV files, identifies *candidate* sensor/telemetry incidents, and writes an evidence-linked HTML report and machine-readable JSON. It does not modify the robot or send data to a cloud service.

## Quick start

Use Python 3.10 or newer. Extract the project ZIP on your own computer.

```bash
python3 -m robot_incident_analyzer demo --output demo_data
python3 -m robot_incident_analyzer analyze demo_data --output output
# Open output/report.html in your web browser.
```

**Browser GUI:**

```bash
python3 -m robot_incident_analyzer gui --port 8765
# Open http://127.0.0.1:8765
```

GUI currently accepts a **single <=50 MiB** input file. For bigger authorized logs use the CLI:

```bash
python3 -m robot_incident_analyzer analyze /path/to/your/file.mcap --output local_report
```

For vendor-specific messages use a JSON mapping and `.msg` schemas as described in README and `examples/config_custom.json`. If command vs odometry matching is ambiguous, explicitly select the matching topics and confirm robot identity.

## Safety and confidentiality

- Use only **recordings you are permitted to inspect**. Do not provide your employer's or a customer's proprietary files to the developer.
- The application is local, but does not provide hardened isolation for malicious bag files. Analyze trusted files only.
- The GUI development server binds to localhost only. Never expose it to the public internet.
- Findings do **not** prove the root cause. A near-zero odometry speed may reflect a safety stop, navigation idle state, disabled motors, unit/frame mismatch, or missing data.
- This alpha parses a limited subset of ROS 2 CDR messages; zstd/lz4 may require separately installed dependencies. Its coverage may be partial. Check the warnings section.

## 15-minute usability tasks

1. Start from extracted sources and open the built-in example HTML report. Time yourself.
2. Try a *permitted* ROS 2 bag or generate another synthetic test. Confirm the tool discovered the command and odometry topics correctly.
3. Point to one finding and the exact evidence that supports it. Explain whether it is an observation or a confirmed cause.
4. Find one limitation, ambiguous mapping, or warning. Can you tell what data wasn't analyzed?
5. Rate whether the report reduces your investigation effort compared with your current workflow.

**Do not share the raw recording.** We only ask for optional non-sensitive feedback and timings.

## Feedback form (copy/paste)

- Role and ROS 2 distribution (optional):
- OS and Python version:
- Sample type: synthetic / authorized internal (no file upload) / public dataset
- Time from extraction to first HTML report: ____ minutes
- Did the tool correctly find your command and odom streams? Yes / No / N/A
- Which findings were useful? Any incorrect or missed anomaly?
- How long would equivalent triage take with your current tools? ____ minutes
- How long did you spend with the analyzer? ____ minutes
- Would you use it on a real project again? Why or why not?
- Would your team consider a paid pilot? If yes, what outcome would justify paying?
- Permission to quote your anonymized response? Yes / No

## What we'll do with this feedback

Prioritize reproducible false positives, crashes, and unsupported message types before adding AI features. No claims of validated root cause, commercial readiness, or user adoption will be made until those have been separately demonstrated.
