"""Purely fictional *valid CDR payloads* and MCAP/DB3 files for offline QA.

Not produced by a deployed robot. The tiny MCAP file intentionally uses
unchunked/uncompressed data records to keep the sample fully reproducible.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import sqlite3
import struct

BASE = datetime(2026,10,10,12,0,tzinfo=timezone.utc).timestamp()


class Encoder:
    def __init__(self): self.data=bytearray(b'\x00\x01\x00\x00')
    def item(self,fmt,val,align=None):
        align=align or struct.calcsize(fmt)
        self.data.extend(b'\0'*((-(len(self.data)-4))%align))
        self.data.extend(struct.pack('<'+fmt,val))
    def text(self,val):
        raw=val.encode()+b'\0'
        self.item('I',len(raw),4);self.data.extend(raw)
    def vec(self,items):
        for x in items: self.item('d',x,8)
    def header(self,ts,frame):
        self.item('i',int(ts),4);self.item('I',int(round((ts-int(ts))*1e9)),4);self.text(frame)
    def twist(self,linear,angular=0.):
        self.vec((linear,0.,0.)); self.vec((0.,0.,angular))
    def bytes(self): return bytes(self.data)


def twist_payload(linear):
    e=Encoder(); e.twist(linear);return e.bytes()


def odom_payload(ts,x,velocity):
    e=Encoder();e.header(ts,'odom');e.text('base_link')
    e.vec((x,0.,0.));e.vec((0.,0.,0.,1.))
    e.vec([0.]*36)
    e.twist(velocity)
    e.vec([0.]*36)
    return e.bytes()


def tf_payload(ts, translation, quaternion=(0.,0.,0.,1.)):
    e=Encoder();e.item('I',1,4);e.header(ts,'map');e.text('odom');e.vec(translation);e.vec(quaternion)
    return e.bytes()


def diagnostic_payload(ts, level, msg):
    e=Encoder();e.header(ts,'');e.item('I',1,4)
    e.item('B',level,1);e.text('Motor driver');e.text(msg);e.text('motor-1')
    e.item('I',1,4);e.text('can_timeout');e.text('1')
    return e.bytes()


def message_records():
    msgs=[]
    for i in range(15):
        dt=i*.1
        ts=BASE+dt
        msgs.append(('/cmd_vel','geometry_msgs/msg/Twist',round(ts*1e9),twist_payload(.5)))
        # 0.0 -> 0.9s show unresponsive odom, 1.0s onward moving.
        vel = 0.0 if i < 10 else .5
        xpos=0.0 if i<10 else (i-9)*.05
        if i==14: xpos+=2.0
        msgs.append(('/odom','nav_msgs/msg/Odometry',round((ts+.01)*1e9),odom_payload(ts+.01,xpos,vel)))
    for d,xyz,quat in [(0.05,(0,0,0),(0,0,0,1)),(.25,(1.5,0,0),(0,0,0,1)),(.45,(1.5,0,0),(0,0,0,0))]:
        ts=BASE+d
        msgs.append(('/tf','tf2_msgs/msg/TFMessage',round(ts*1e9),tf_payload(ts,xyz,quat)))
    for d,level,msg in [(0.5,1,'Bus latency increased'),(.95,2,'CAN device timeout')]:
        ts=BASE+d
        msgs.append(('/diagnostics','diagnostic_msgs/msg/DiagnosticArray',round(ts*1e9),diagnostic_payload(ts,level,msg)))
    return sorted(msgs,key=lambda x:x[2])


def make_db3(path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():path.unlink()
    records=message_records()
    conn=sqlite3.connect(path)
    try:
        conn.execute('CREATE TABLE topics(id INTEGER PRIMARY KEY,name TEXT,type TEXT,serialization_format TEXT,offered_qos_profiles TEXT)')
        conn.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER,timestamp INTEGER,data BLOB)')
        types=sorted(set((topic,typ) for topic,typ,*_ in records))
        index={pair:i+1 for i,pair in enumerate(types)}
        for pair,tid in index.items():
            conn.execute('INSERT INTO topics VALUES(?,?,?,?,?)',(tid,pair[0],pair[1],'cdr',''))
        for topic,typ,ts,data in records:
            conn.execute('INSERT INTO messages(topic_id,timestamp,data) VALUES(?,?,?)',(index[(topic,typ)],ts,data))
        conn.commit()
    finally: conn.close()
    return path


def mcap_record(op:int,raw:bytes):
    return bytes([op])+struct.pack('<Q',len(raw))+raw


def field(s):
    raw=s.encode();return struct.pack('<I',len(raw))+raw


def make_mcap(path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    records=message_records()
    types=sorted(set((topic,typ) for topic,typ,*_ in records))
    channel_id={pair:i+1 for i,pair in enumerate(types)}
    body=[mcap_record(0x01,field('ros2')+field('robot-incident-analyzer-fixture'))]
    for (topic,typ),num in channel_id.items():
        # Empty schema data because this minimal fixture uses standard ROS2 types known to our decoder.
        body.append(mcap_record(0x03,struct.pack('<H',num)+field(typ)+field('ros2msg')+struct.pack('<I',0)))
        body.append(mcap_record(0x04,struct.pack('<HH',num,num)+field(topic)+field('cdr')+struct.pack('<I',0)))
    for idx,(topic,typ,ts,data) in enumerate(records):
        channel=channel_id[(topic,typ)]
        body.append(mcap_record(0x05,struct.pack('<HIQQ',channel,idx,ts,ts)+data))
    body.append(mcap_record(0x0f,struct.pack('<I',0)))  # DataEnd (CRC not computed)
    body.append(mcap_record(0x02,struct.pack('<QQI',0,0,0)))
    path.write_bytes(b'\x89MCAP0\r\n'+b''.join(body)+b'\x89MCAP0\r\n')
    return path


def make_telemetry_demo(directory:Path):
    # Standalone MCAP sample; DB3 sample generated in tests to avoid duplicate demo events.
    return make_mcap(directory/'fictional_telemetry.mcap')
