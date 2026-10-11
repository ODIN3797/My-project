# Overseas ROS 2 outreach — not yet sent

The templates below are for prospective **voluntary** interviews. No contact or outreach has been performed.

## Direct message

Hi! I'm developing a small **offline ROS 2 incident-analysis tool** for MCAP/DB3 recordings. It links anomalous velocity/odom/TF and diagnostics signals to an HTML timeline, with the goal of reducing manual log triage. It's an early alpha — I haven't validated its accuracy on field data yet. Would you be open to a 15-minute usability test with the included synthetic demo? You would not need to share any company or customer logs. I'd especially value feedback on false positives and what's missing from your workflow. Thanks!

## Public forum post

**Seeking ROS 2 engineer feedback: offline incident triage alpha (MCAP/DB3)**

I'm testing a small Python tool that analyzes standard ROS 2 telemetry and generates an offline evidence-linked incident report. It can detect certain command/odometry mismatches, invalid TF values, position jumps, and diagnostic statuses. It uses heuristic thresholds; it does **not** determine root causes and currently supports only selected CDR types.

I'd appreciate people trying the included synthetic demo and telling me: (1) where the workflow breaks, (2) which false positives are likely on their robots, and (3) whether reports like these would save any time. No proprietary files requested. I'll share setup instructions, a short example report, and source code for review. This is not a production-ready diagnosis tool.

## Five interview prompts

1. What was the last robot incident that consumed more than 30 minutes of debugging? Which ROS data did you inspect?
2. How do you currently combine /rosout, rosbag, TF, and hardware-controller logs?
3. Which command/odom comparison would be invalid on your robot, and why?
4. What would make a report trustworthy enough to attach to a customer issue?
5. Have you paid for or advocated buying debugging tools? What evidence would justify a paid trial?
