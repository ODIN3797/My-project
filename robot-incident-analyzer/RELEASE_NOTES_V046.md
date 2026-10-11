# v0.4.6 — Incident-first dashboard

- New self-contained, responsive investigation dashboard. Compatible with offline generated HTML reports and original `report.json` schema.
- 40-bin interactive severity timeline; filtering by selected time window, text query and severity.
- Finding cards with evidence shortcuts, source distribution, topic volume and timing-variance bars.
- Existing cmd_vel ↔ odometry traces and focused windows remain, when the bag provides an unambiguous pair.
- Tested on synthetic ROS2 DB3/MCAP/CSV fixtures; real physical robot incident detection not validated.
- All report text from untrusted input is HTML escaped; no dependencies on browser-hosted services.
- See `docs/COMPETITOR_GAP_V046.md` for feature-level comparison and limitations.

Quick demo:

```bash
python3 -m robot_incident_analyzer demo --output demo_data
python3 -m robot_incident_analyzer analyze demo_data --output output
# Open output/report.html in your browser
```
