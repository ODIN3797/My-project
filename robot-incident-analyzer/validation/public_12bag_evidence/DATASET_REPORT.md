# External ROS2 bag evaluation — independent third-party recordings

This file distinguishes downloaded data and actual analysis from planned work. No data source has been judged to be free of fault.

- Bags downloaded: **12**
- Bags successfully summarized: **12**

## experiment1
- Source: https://zenodo.org/records/17649537/files/Experiment_1.zip?download=1
- Download: SUCCESS
- Recordings: 2
- rosbag2_2024_03_11-13_14_19_0.db3: 7,120 messages, 8 topics, 75.5837 seconds
- rosbag2_2024_03_11-13_30_46_0.db3: 10,355 messages, 7 topics, 40.1602 seconds

## vigo_navigation
- Source: https://zenodo.org/records/15433859/files/Navigation.zip?download=1
- Download: SUCCESS
- Recordings: 9
- rosbag2_2024_06_14-12_45_42_0.db3: 18,583 messages, 18 topics, 215.0231 seconds
- rosbag2_2024_06_14-12_52_02_0.db3: 15,602 messages, 18 topics, 177.9069 seconds
- rosbag2_2024_06_14-12_57_11_0.db3: 16,799 messages, 18 topics, 192.7463 seconds
- rosbag2_2024_06_14-13_02_45_0.db3: 15,624 messages, 18 topics, 179.7542 seconds
- rosbag2_2024_06_14-13_07_00_0.db3: 15,284 messages, 18 topics, 174.6967 seconds
- rosbag2_2024_06_14-13_12_43_0.db3: 14,125 messages, 18 topics, 161.9256 seconds
- rosbag2_2024_06_14-13_24_49_0.db3: 12,793 messages, 18 topics, 156.0536 seconds
- rosbag2_2024_06_14-13_30_51_0.db3: 13,883 messages, 18 topics, 163.9607 seconds
- rosbag2_2024_06_14-13_47_51_0.db3: 40,201 messages, 18 topics, 464.1987 seconds

## bagel_example
- Source: https://raw.githubusercontent.com/Hussain004/BAGEL/dc25e7ef395546bfbeea2ca07b71091fe70f5112/public/sample-bags/tour.mcap
- Download: SUCCESS
- Recordings: 1
- bagel_example.mcap: 3,057 messages, 18 topics, 29.98 seconds

## Independent normal-vs-simulated-attack acceptance

{
  "verified": true,
  "command_topic": {
    "topic": "/mobile_base_controller/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "baseline_messages": 1501,
    "candidate_messages": 6630,
    "baseline_mean_hz": 19.8495,
    "candidate_mean_hz": 165.1926,
    "baseline_peak_1s_count": 77,
    "candidate_peak_1s_count": 495,
    "rate_ratio": 8.3223,
    "status": "RATE_INCREASE",
    "reason": "Observed recorded topic rate increase vs supplied baseline; not proof of failure or attack",
    "baseline_histogram": [
      11,
      10,
      10,
      10,
      10,
      6,
      10,
      10,
      9,
      10,
      10,
      10,
      46,
      8,
      22,
      8,
      13,
      10,
      13,
      34,
      6,
      10,
      28,
      11,
      29,
      8,
      32,
      77,
      60,
      26,
      56,
      15,
      8,
      22,
      30,
      25,
      29,
      10,
      22,
      43,
      25,
      42,
      9,
      0,
      52,
      10,
      10,
      10,
      13,
      77,
      25,
      21,
      13,
      26,
      29,
      14,
      27,
      28,
      41,
      15,
      38,
      26,
      13,
      8,
      11,
      10,
      10,
      10,
      9,
      8,
      10,
      10,
      10,
      10,
      8,
      6,
      0
    ],
    "candidate_histogram": [
      10,
      10,
      7,
      10,
      8,
      10,
      7,
      8,
      10,
      8,
      18,
      20,
      8,
      10,
      21,
      22,
      26,
      10,
      13,
      10,
      11,
      19,
      0,
      0,
      0,
      463,
      322,
      495,
      348,
      351,
      325,
      474,
      425,
      420,
      473,
      460,
      433,
      461,
      428,
      417,
      59,
      0
    ],
    "histogram_scope": "first up to 240 topic-relative 1s bins, not wall-clock aligned across recordings"
  },
  "note": "A simulated attack was publisher-described, but only downstream bag rates were measured."
}

## Vigo relative comparison

{
  "bag_count": 9,
  "compared": 8,
  "rate_increases": 0,
  "note": "Different driving configurations; rate differences do not imply defects"
}

## Caveats

- Recorded topic message rates are not publisher-set rates or verified robot control updates.
- A normal publisher label does not make every individual observation normal; manually review normal-case warnings.
- Different vehicle speeds, RTK configurations, and robots can legitimately have different sample rates.
- This test does not establish fault detection precision/recall or a reduction in engineering investigation time.
