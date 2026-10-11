"""Generates fictional sample data. Not real workplace/customer logs."""
from __future__ import annotations
import csv
import sqlite3
import struct
from datetime import datetime, timezone
from pathlib import Path

BASE = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc).timestamp()


def rosout_payload(level: int, node: str, message: str, timestamp: float) -> bytes:
    """Encode the known rcl_interfaces/msg/Log layout for integration testing."""
    raw = bytearray(b'\x00\x01\x00\x00')
    raw.extend(struct.pack('<iI', int(timestamp), int((timestamp-int(timestamp))*1e9)))
    raw.extend(struct.pack('<B', level))
    for item in (node, message, 'demo.cpp', 'callback'):
        raw.extend(b'\x00' * ((-(len(raw)-4)) % 4))
        encoded = item.encode('utf-8') + b'\x00'
        raw.extend(struct.pack('<I', len(encoded)))
        raw.extend(encoded)
    raw.extend(b'\x00' * ((-(len(raw)-4)) % 4))
    raw.extend(struct.pack('<I', 42))
    return bytes(raw)


def generate_demo(out: Path) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / 'fictional_events.csv'
    rows = [
        (0, 'robot-A', 'navigation', 'INFO', 'MISSION_START', 'Navigation mission started.'),
        (15, 'robot-A', 'network', 'WARN', 'COMMUNICATION', 'Network packet loss started.'),
        (18, 'robot-A', 'network', 'ERROR', 'TIMEOUT', 'MQTT request timeout after 3 retries.'),
        (22, 'robot-A', 'navigation', 'ERROR', 'NAVIGATION', 'Navigation goal aborted by controller.'),
        (40, 'robot-A', 'docking', 'INFO', 'DOCK_SUCCESS', 'Docking success; robot aligned.'),
        (47, 'robot-A', 'charging', 'ERROR', 'CHARGING', 'Charging current is 0 A after docking.'),
        (80, 'robot-B', 'navigation', 'WARN', 'TF_ERROR', 'Transform unavailable map to base_link.'),
        (85, 'robot-B', 'navigation', 'WARN', 'TF_ERROR', 'Transform unavailable map to base_link.'),
        (90, 'robot-B', 'navigation', 'WARN', 'TF_ERROR', 'Transform unavailable map to base_link.'),
    ]
    with csv_path.open('w', encoding='utf-8', newline='') as fp:
        writer = csv.writer(fp)
        writer.writerow(['timestamp', 'robot_id', 'category', 'severity', 'code', 'message'])
        for seconds,robot_id,cat,sev,code,msg in rows:
            writer.writerow([datetime.fromtimestamp(BASE+seconds,tz=timezone.utc).isoformat(), robot_id, cat, sev, code, msg])

    bag_dir = out / 'fictional_rosbag2'
    bag_dir.mkdir(exist_ok=True)
    bag_path = bag_dir / 'robot_session_0.db3'
    if bag_path.exists():
        bag_path.unlink()
    conn = sqlite3.connect(bag_path)
    try:
        conn.executescript('''
        CREATE TABLE topics(id INTEGER PRIMARY KEY, name TEXT, type TEXT, serialization_format TEXT, offered_qos_profiles TEXT);
        CREATE TABLE messages(id INTEGER PRIMARY KEY, topic_id INTEGER, timestamp INTEGER, data BLOB);
        INSERT INTO topics VALUES(1, '/rosout', 'rcl_interfaces/msg/Log', 'cdr', '');
        INSERT INTO topics VALUES(2, '/scan', 'sensor_msgs/msg/LaserScan', 'cdr', '');
        INSERT INTO topics VALUES(3, '/imu/data', 'sensor_msgs/msg/Imu', 'cdr', '');
        ''')
        def write(topic_id, sec, data):
            conn.execute('INSERT INTO messages(topic_id,timestamp,data) VALUES(?,?,?)',
                         (topic_id, round((BASE + sec)*1e9), sqlite3.Binary(data)))
        for idx in range(60):
            t = idx*.1 + (2.0 if idx >= 25 else 0.)
            write(2, t, b'fictional_scan_payload_timing_only')
        for idx in range(100):
            write(3, idx*.08, b'fictional_imu_payload_timing_only')
        for sec,level,node,msg in [
            (2.4, 30, 'scan_driver', 'Laser scan reconnect after data gap.'),
            (2.8, 40, 'nav2_controller', 'Navigation controller failed after laser timeout.'),
            (3.1, 30, 'nav2_controller', 'Controller retry requested.'),
        ]:
            write(1, sec, rosout_payload(level,node,msg,BASE+sec))
        conn.commit()
    finally:
        conn.close()
    return csv_path, bag_path
