"""Synthetic wire-format regression tests; not physical-robot ground truth."""
from __future__ import annotations

import math
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path

from robot_incident_analyzer.fixture_v2 import Encoder, mcap_record, field
from robot_incident_analyzer.inputs import read_rosbag
from robot_incident_analyzer.telemetry import TelemetryAnalyzer, decode_standard
from robot_incident_analyzer.analysis import build_findings


def battery_payload(*, health=1, percentage=0.8, present=True):
    e = Encoder()
    e.header(1.2, 'battery')
    for v in (24.0, 22.0, -1.0, 12.0, 15.0, 20.0, percentage):
        e.item('f', v, 4)
    for v in (2, health, 2):
        e.item('B', v, 1)
    e.item('?', present, 1)
    for values in ([3.7, 3.8], [22.0]):
        e.item('I', len(values), 4)
        for value in values:
            e.item('f', value, 4)
    e.text('bay-A')
    e.text('sensor-test')
    return e.bytes()


def imu_payload(*, orientation=(0, 0, 0, 1), orient_available=True):
    e = Encoder()
    e.header(1.2, 'imu_link')
    e.vec(orientation)
    e.vec([0.0 if orient_available else -1.0] + [0.0] * 8)
    e.vec((0.0, 0.0, 0.1))
    e.vec([0.0] * 9)
    e.vec((0.0, 0.0, 9.81))
    e.vec([0.0] * 9)
    return e.bytes()


class SensorInspectionTests(unittest.TestCase):
    def test_battery_wire_payload_and_fields(self):
        value = decode_standard('sensor_msgs/msg/BatteryState', battery_payload())
        self.assertEqual(value['health'], 1)
        self.assertAlmostEqual(value['percentage'], 0.8, places=5)
        self.assertTrue(value['present'])

    def test_battery_nan_is_unmeasured_not_failure(self):
        a = TelemetryAnalyzer('case.mcap')
        a.ingest('/battery', 'sensor_msgs/msg/BatteryState', 1.0,
                 battery_payload(percentage=float('nan')))
        a.ingest('/battery', 'sensor_msgs/msg/BatteryState', 2.0,
                 battery_payload(percentage=0.02, health=1))
        self.assertEqual(a.events, [])

    def test_battery_abnormal_health_deduplicates_and_recovers(self):
        a = TelemetryAnalyzer('case.mcap')
        for t,health in [(1,2), (2,2), (3,1), (4,2)]:
            a.ingest('/battery', 'sensor_msgs/msg/BatteryState', t,
                     battery_payload(health=health))
        self.assertEqual([e.code for e in a.events], ['BATTERY_HEALTH_ABNORMAL'] * 2)
        self.assertEqual(len([f for f in build_findings(a.events) if f.code == 'BATTERY_HEALTH_ABNORMAL']), 1)

    def test_imu_unavailable_orientation_is_not_invalid(self):
        a = TelemetryAnalyzer('case.mcap')
        a.ingest('/imu/data', 'sensor_msgs/msg/Imu', 1.0,
                 imu_payload(orientation=(0,0,0,0), orient_available=False))
        self.assertEqual(a.events, [])

    def test_imu_invalid_orientation_detection_transition(self):
        a = TelemetryAnalyzer('case.mcap')
        for t,q in [(1,(0,0,0,0)), (2,(0,0,0,0)), (3,(0,0,0,1)), (4,(0,0,0,0))]:
            a.ingest('/imu/data', 'sensor_msgs/msg/Imu', t, imu_payload(orientation=q))
        self.assertEqual([e.code for e in a.events], ['IMU_INVALID_QUATERNION'] * 2)

    def test_truncated_messages_fail_closed_without_events(self):
        a = TelemetryAnalyzer('case.mcap')
        a.ingest('/imu/data', 'sensor_msgs/msg/Imu', 1, imu_payload()[:30])
        a.ingest('/battery', 'sensor_msgs/msg/BatteryState', 2, battery_payload()[:20])
        self.assertEqual(a.decode_failures, 2)
        self.assertEqual(len(a.events), 0)

    def test_db3_and_mcap_end_to_end_payloads(self):
        streams = [('/battery','sensor_msgs/msg/BatteryState',battery_payload(health=2)),
                   ('/imu/data','sensor_msgs/msg/Imu',imu_payload(orientation=(0,0,0,0)))]
        with tempfile.TemporaryDirectory() as tmp:
            db3 = Path(tmp)/'sample.db3'
            conn = sqlite3.connect(db3)
            conn.execute('CREATE TABLE topics(id INTEGER PRIMARY KEY,name TEXT,type TEXT,serialization_format TEXT,offered_qos_profiles TEXT)')
            conn.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER,timestamp INTEGER,data BLOB)')
            for i,(topic,typ,data) in enumerate(streams,1):
                conn.execute('INSERT INTO topics VALUES(?,?,?,?,?)',(i,topic,typ,'cdr',''))
                conn.execute('INSERT INTO messages(topic_id,timestamp,data) VALUES(?,?,?)',(i,1700000000000000000+i*1000000,data))
            conn.commit();conn.close()
            for f in [db3,Path(tmp)/'sample.mcap']:
                if f.suffix=='.mcap':
                    body=[mcap_record(0x01,field('ros2')+field('sensor-test'))]
                    for i,(topic,typ,data) in enumerate(streams,1):
                        body.append(mcap_record(0x03,struct.pack('<H',i)+field(typ)+field('ros2msg')+struct.pack('<I',0)))
                        body.append(mcap_record(0x04,struct.pack('<HH',i,i)+field(topic)+field('cdr')+struct.pack('<I',0)))
                        body.append(mcap_record(0x05,struct.pack('<HIQQ',i,i,1700000000000000000+i*1000000,1700000000000000000+i*1000000)+data))
                    body.append(mcap_record(0x0f,struct.pack('<I',0)))
                    body.append(mcap_record(0x02,struct.pack('<QQI',0,0,0)))
                    f.write_bytes(b'\x89MCAP0\r\n'+b''.join(body)+b'\x89MCAP0\r\n')
                events, stats, warnings = read_rosbag(f)
                self.assertEqual({e.code for e in events}, {'BATTERY_HEALTH_ABNORMAL','IMU_INVALID_QUATERNION'})
                self.assertFalse(any('unsupported message type' in w for w in warnings), warnings)


if __name__ == '__main__':
    unittest.main()
