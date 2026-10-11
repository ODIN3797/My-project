"""Entirely fictional ROS2 MCAP with explicit controller state logs and sensors."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
from .fixture_v2 import BASE, Encoder, make_mcap
from .fixture_studio import studio_records


def log_message(ts, level, node, message):
    e=Encoder()
    e.item('i',int(ts),4)
    e.item('I',int(round((ts-int(ts))*1e9)),4)
    e.item('B',level,1)
    e.text(node)
    e.text(message)
    e.text('controller.py')
    e.text('step')
    e.item('I',88,4)
    return e.bytes()


def state_records():
    records=studio_records()
    changes=[
        (.45,20,'mode=AUTONOMOUS; docking_state=IDLE'),
        (1.42,20,'docking_state=APPROACH mission_state=RUNNING command_state=EXECUTING'),
        (2.65,20,'docking_state=ALIGN'),
        (3.22,20,'docking_state=CONTACT'),
        (4.5,20,'charging_state=HANDSHAKE; docking_state=CHARGING'),
        (5.11,30,'safety_state=STOPPED; mode=PAUSED; command_state=PAUSED'),
        (5.22,40,'Charger handshake timeout; charging_state=FAILED'),
        (6.10,20,'charging_state=RETRYING'),
    ]
    for offset,level,text in changes:
        t=BASE+offset
        records.append(('/robot_a/rosout','rcl_interfaces/msg/Log',round(t*1e9),
                        log_message(t,level,'robot_a/mission_manager',text)))
    # The other robot's transition must not leak into robot_a summaries.
    t=BASE+4.7
    records.append(('/robot_b/rosout','rcl_interfaces/msg/Log',round(t*1e9),
                    log_message(t,20,'robot_b/mission_manager','mode=MANUAL docking_state=IDLE')))
    return sorted(records,key=lambda r:r[2])


def make_state_demo(out:Path):
    out.mkdir(parents=True, exist_ok=True)
    with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=state_records()):
        return make_mcap(out/'fictional_state_transitions.mcap')
