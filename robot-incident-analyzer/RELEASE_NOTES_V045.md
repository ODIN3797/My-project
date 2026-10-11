# Robot Incident Analyzer v0.4.5 (experimental alpha)

- Adds bounded standard ROS2 LaserScan CDR decoding with metadata and data-quality observations.
- Does not treat infinite readings as sensor failure; all-NaN events require three consecutive scans.
- Includes eight synthetic wire-format tests, including isolated robot namespaces, malformed payloads and DB3/MCAP integration.
- 69 automated tests passing in the development environment; synthetic MCAP and DB3 performance numbers in docs.
- Production readiness NOT established. No verified physical-robot logs or independent diagnosis ground truth.
- Current `--max-messages` defaults to 200,000, and the report warns when the input was truncated.
