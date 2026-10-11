"""Fictional ROS2 sensor + trajectory MCAP. Not recorded from a robot."""
from __future__ import annotations
import math
from pathlib import Path
from .fixture_v2 import BASE, Encoder, make_mcap


def _battery(ts,percentage,health):
    e=Encoder();e.header(ts,'battery')
    for x in (24+percentage*.6,22.0,-1.0,10.,12.,16.,percentage):e.item('f',x,4)
    for x in (2,health,2):e.item('B',x,1)
    e.item('?',True,1)
    for values in ([],[]):e.item('I',len(values),4)
    e.text('local');e.text('synthetic-fixture')
    return e.bytes()


def _imu(ts,angular):
    e=Encoder();e.header(ts,'imu_link')
    e.vec((0.,0.,0.,1.));e.vec((0.,)*9)
    e.vec((0.,0.,angular));e.vec((0.,)*9)
    e.vec((0.1,0.,9.81));e.vec((0.,)*9)
    return e.bytes()


def _scan(ts,i):
    e=Encoder();e.header(ts,'laser')
    for v in (-1.57,1.57,.01,.0001,.12,.1,12.):e.item('f',v,4)
    ranges=[float('inf') if j % 6 < (2 if i < 25 else 4) else 1.+j*.01 for j in range(80)]
    if 44 <= i < 47:ranges=[float('nan')]*80
    e.item('I',len(ranges),4)
    for v in ranges:e.item('f',v,4)
    e.item('I',0,4)
    return e.bytes()


def studio_records():
    from .fixture_v2 import odom_payload,twist_payload
    streams=[]
    for i in range(75):
        t=BASE+i*.12
        cmd=.48 if i < 60 else .15
        v=0. if 17<=i<27 else cmd
        # Slight arc, and visible realistic turn rather than flat straight line.
        x=i*.045
        y=1.5*math.sin(i/22.0)
        for topic,typ,ts,data in [
            ('/robot_a/cmd_vel','geometry_msgs/msg/Twist',t,twist_payload(cmd)),
            ('/robot_a/odom','nav_msgs/msg/Odometry',t+.01,odom_payload(t+.01,x,v)),
            ('/robot_a/battery','sensor_msgs/msg/BatteryState',t,_battery(t,.8-i*.004,2 if 46<=i<51 else 1)),
            ('/robot_a/imu/data','sensor_msgs/msg/Imu',t,_imu(t,.05+i*.001)),
            ('/robot_a/scan','sensor_msgs/msg/LaserScan',t,_scan(t,i))]:
            if topic.endswith('/odom'):
                data=odom_xy_payload(t+.01,x,y,v)
            streams.append((topic,typ,round(ts*1e9),data))
    return sorted(streams,key=lambda row:row[2])


def odom_xy_payload(ts,x,y,velocity):
    e=Encoder();e.header(ts,'odom');e.text('base_link')
    e.vec((x,y,0.));e.vec((0.,0.,0.,1.));e.vec([0.]*36)
    e.twist(velocity);e.vec([0.]*36)
    return e.bytes()


def make_studio_demo(out:Path):
    from unittest.mock import patch
    out.mkdir(parents=True, exist_ok=True)
    # This uses a simple built-in MCAP writer from our own synthetic fixture.
    with patch('robot_incident_analyzer.fixture_v2.message_records',return_value=studio_records()):
        return make_mcap(out/'fictional_signal_studio.mcap')
