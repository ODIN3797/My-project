"""Synthetic, fictional ROS2 custom CDR fixture for schema regression testing."""
from __future__ import annotations
from pathlib import Path
from .fixture_v2 import BASE, Encoder, make_mcap, make_db3


def custom_records():
    result = []
    for i in range(16):
        time = BASE + i * 0.10
        command = Encoder()
        command.header(time, 'base_link')
        command.item('d', 0.45)
        command.item('d', 0.02)
        command.item('I', 2, 4)  # variable-length array of wheel RPMs
        command.item('f', 14.5)
        command.item('f', 14.5)
        command.item('H', 1, 2)
        result.append(('/robot1/drive/input','acme_robot_msgs/msg/DriveCommand',int(round(time*1e9)),command.bytes()))
        state = Encoder()
        state.header(time + 0.01, 'odom')
        velocity = 0.0 if i < 10 else 0.45
        pos = 0.0 if i < 10 else (i-9)*0.045
        if i == 15: pos += 1.7  # deliberately suspicious discontinuity
        state.item('d', velocity)
        state.item('d', pos)
        state.item('d', 0.0)
        result.append(('/robot1/drive/feedback','acme_robot_msgs/msg/DriveFeedback',
                       int(round((time+0.01)*1e9)), state.bytes()))
    return sorted(result, key=lambda x:x[2])


def make_custom_demo(directory:Path):
    from unittest.mock import patch
    directory.mkdir(parents=True, exist_ok=True)
    with patch('robot_incident_analyzer.fixture_v2.message_records', side_effect=custom_records):
        mcap = make_mcap(directory / 'fictional_custom_telemetry.mcap')
    return mcap
