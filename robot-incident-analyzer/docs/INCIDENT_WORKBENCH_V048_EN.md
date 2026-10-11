# Incident Workbench — quick evaluation guide (v0.4.8)

## Starting point

Analyze an authorized MCAP or DB3 recording. Open `report.html` offline. Select a finding via the Investigation Queue's **Inspect synchronized evidence** button, the Incident Workbench selector, or an event row's **Investigate** button.

## Workflow

1. Confirm the **source recording**, robot identifier where present and timestamp of the observation.
2. Start with ±10 seconds, then expand to ±30 seconds if a suspected precursor lies outside the initial view.
3. Review up to four **ranked numeric signal traces**. Ranking selects useful *views*, not a root-cause verdict.
4. Check the **approximate XY odometry event marker** (pink); when no nearby odometry sample exists, the report explicitly refuses to place the marker.
5. Read nearby WARN/ERROR events and follow the original event IDs to corroborate in the source recording.
6. Verify the cause with independent measurement or a reproducible experiment. A rule match is not a diagnosis.

## PDF export

- Inside `report.html`, click **Print / Save as PDF** and select a PDF printer in your browser. Some dynamic SVG plots are rendered at the currently selected incident and window.
- Or run `python3 -m pip install '.[pdf]'`, then `python3 -m robot_incident_analyzer analyze FILE.mcap --output result --pdf` to generate `result/report.pdf` offline with vector charts and evidence summaries.

## Important caveats

Recording timestamp != hardware sensor stamp. No causal inference. Downsampled curves cannot replace the original recording. Some custom CDR types are not decoded without authorized `.msg` schemas; do not upload employer/customer logs. The CLI PDF includes at most 20 incident cases with 2 signal charts each, while the HTML view can show more.
