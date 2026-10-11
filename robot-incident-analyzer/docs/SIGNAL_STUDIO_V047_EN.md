# Signal Studio v0.4.7 — field explorer (alpha)

## Try it without ROS installation

```bash
python3 -m robot_incident_analyzer demo-studio --output studio_data
python3 -m robot_incident_analyzer analyze studio_data/fictional_signal_studio.mcap --output studio_report
xdg-open studio_report/report.html
```

The generated sample is **100% fictional** and was not recorded from a physical robot.

## Using the dashboard

In **Signal Studio · synchronized evidence**, choose a topic and a numeric scalar field such as `/battery → percentage (%)`, `/imu/data → angular_velocity.z`, `/scan → valid_return_ratio (%)`, or `/odom → position.x (m)`. Move the **Recording cursor** slider to view a time-aligned value, local Odometry XY position, and command-versus-Odometry chart. Click the XY path to jump to its nearest sampled position, or click a velocity chart to change the shared time. The event-activity timeline and finding-evidence links also update the shared cursor.

Data displays are provided for supported standard decoded ROS2 messages and for user-supplied `.msg` schemas configured with `schema_dirs` — *even when no semantic command/odometry role is assigned*. Nested numeric scalar fields are supported; arbitrary arrays and unknown/unsupported message types are not automatically plotted. Providing a schema allows **visualization**, not automatic diagnostic interpretation. A `custom_messages` role mapping is still required before any custom command/odometry comparison.

## Supported plot data

| ROS2 message type | Example plotted fields |
|---|---|
| `geometry_msgs/msg/Twist` (+ `TwistStamped`) | `linear.x`, `angular.z` |
| `nav_msgs/msg/Odometry` | `linear.x`, `angular.z`, `position.x`, `position.y`; XY path by frame |
| `sensor_msgs/msg/BatteryState` | voltage, current, percentage, temperature |
| `sensor_msgs/msg/Imu` | angular velocity Z, acceleration X, quaternion norm if orientation is available |
| `sensor_msgs/msg/LaserScan` | percentage of valid returns, count of NaN ranges (not every raw beam) |
| Explicit `.msg` schemas | finite scalar fields, recursively up to depth 5 |

`tf2_msgs/msg/TFMessage` is inspected for errors but does not yet have an interactive per-frame plot. Binary image/pointcloud arrays are not rendered. Unsupported XCDR2/custom IDL must be handled separately.

## Limits / safety

- Recording **timestamps**, not synchronized sensor acquisition timestamps; clock jumps, replay gaps, and network delay can invalidate apparent alignment.
- A plotted incident marker is **not evidence of causality**, and a low battery percentage is **not by itself a hardware fault**.
- Different Odometry topics and frames are **never connected** into one XY trace. Trajectories are not ground-truth maps.
- Plots are **bounded/downsampled**: at most 72 scalar series and 650 samples per series, 8 trajectories with at most 650 points each, and the first 500 WARN/ERROR/FATAL markers. See raw MCAP for precise evidence.
- The existing `--max-messages` flag defaults to 200,000 messages per input. The system warns when the recording is only partially analyzed.
- The standalone HTML file contains **excerpts of recorded data**. Review content before sharing; some source messages can contain private site details.
- No telemetry or external API requests are required. There is no external JS library.
- This is an **experimental, non-safety-critical alpha**, not validated on labeled physical robot failure data.

## What to test with independent ROS2 engineers

1. Can they choose a custom scalar without changing source code?
2. Can they locate an existing known log incident and correlate time windows faster than their current workflow?
3. Do the sampled curves mislead because of clock mismatch, sparse sampling or frame labels?
4. Which missing types (PointCloud2, Image, Nav2 action status, motor driver custom types) prevent useful triage?
5. How do actual analysis time and memory use scale on their own approved 1 GB and 5 GB bags?

Avoid sharing employer/customer logs without written authorization.
