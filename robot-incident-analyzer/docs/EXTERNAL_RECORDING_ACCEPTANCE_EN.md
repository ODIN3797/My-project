# External ROS2 bag pilot — v0.4.3

**No field-recorded robot bag has been tested by this release.** The 51 automated tests use generated standard CDR messages, synthetic MCAP containers and deliberately damaged files. They do not establish fault-diagnosis accuracy.

## Reproduce locally on Ubuntu

```bash
python3 -m unittest discover -s tests -v
bash scripts/validate_local_real_bag.sh /absolute/path/to/recording.mcap unknown out
cat out/FIELD_RESULTS.md
```

Use `physical` in place of `unknown` only if the source can be verified as a recording from a real robot. Set `--labels` when independent event annotations exist; without exhaustive labels no precision/false-positive rate can be established.

Public candidates (license and file access must be verified independently):

- [JKK dataset 02](https://jkk-research.github.io/dataset/jkk_dataset_02/), real-world vehicle MCAP (no verified incident labels)
- [RTAB-Map multisession data](https://github.com/introlab/rtabmap_ros/blob/ros2/rtabmap_demos/launch/multisession_mapping_demo.launch.py), externally published DB3 download links
- [BAGEL tour.mcap](https://github.com/Hussain004/BAGEL/tree/main/public/sample-bags), *synthetic/third-party demo* for compatibility checks only

Do not upload confidential customer/employer logs. The HTML and JSON reports can contain unredacted source messages. Command/odometry roles should be manually checked before treating a velocity mismatch as meaningful. TF jumps may reflect planned localization corrections rather than faults.

## Requested pilot feedback

- OS / Python version, bag format, source provenance, file size
- Can the tool install and analyze the file? Total time (including setup)
- Did it choose the intended command and feedback topics? Which alternatives exist?
- Which alert was useful, misleading, or missed? Include timestamps only if cleared to share.
- Estimated minutes saved compared with existing debugging workflow
- Would you use this monthly? Would your team pay for offline incident triage?
