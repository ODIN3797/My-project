# Public MCAP: what we know

The BAGEL `tour.mcap` sample (pinned commit `dc25e7ef395546bfbeea2ca07b71091fe70f5112`) has been analyzed in GitHub Actions.

- 18 topics, 3,057 messages, 4 WARN/ERROR log events.
- The known initial repeat-alert false positive was fixed in v0.4.3.
- Original recording provenance and fault ground truth are **not verified**.
- BatteryState and Imu payload inspection is added in v0.4.4, following ROS2 common_interfaces schemas.
- No claims about diagnostic precision, recall, actual robot failures, or real customer usage.

Do not upload proprietary robot logs or customer sensor data.
