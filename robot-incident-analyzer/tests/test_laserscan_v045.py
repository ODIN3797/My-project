"""Wire-format LaserScan quality checks: synthetic data, not hardware fault diagnosis."""
import math
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from robot_incident_analyzer.fixture_v2 import Encoder, make_mcap, mcap_record, field
from robot_incident_analyzer.telemetry import decode_standard, TelemetryAnalyzer
from robot_incident_analyzer.analysis import build_findings
from robot_incident_analyzer.inputs import read_rosbag


def scan_payload(ranges, *, range_min=0.1, range_max=12., increment=0.01, intensities=(), frame='laser'):
    enc = Encoder()
    enc.header(1.25, frame)
    vals = (-1.0, 1.0, increment, 0.0001, 0.1, range_min, range_max)
    for val in vals:
        enc.item('f', val, 4)
    enc.item('I', len(ranges), 4)
    for v in ranges:
        enc.item('f', v, 4)
    enc.item('I', len(intensities), 4)
    for v in intensities:
        enc.item('f', v, 4)
    return enc.bytes()


class LaserScanV045Tests(unittest.TestCase):
    def test_cdr_summary_and_inf_no_return_is_not_error(self):
        msg = decode_standard('sensor_msgs/msg/LaserScan', scan_payload([float('inf'), 1.2, .05, 18.0]))
        self.assertEqual(msg['beam_count'], 4)
        self.assertEqual(msg['valid_returns'], 1)
        self.assertEqual(msg['nan_count'], 0)
        a=TelemetryAnalyzer('sample.mcap')
        for i in range(5):
            a.ingest('/scan','sensor_msgs/msg/LaserScan',1+i*.1,scan_payload([float('inf')]*5))
        self.assertEqual(a.events, [])

    def test_three_all_nan_scans_are_quality_observation_not_hardware_diagnosis(self):
        a=TelemetryAnalyzer('sample.mcap')
        for i in range(10):
            a.ingest('/scan','sensor_msgs/msg/LaserScan',i*.1,scan_payload([float('nan')]*10))
        self.assertEqual([e.code for e in a.events], ['LASER_SCAN_ALL_NAN'])
        self.assertIn('data-quality',a.events[0].message)
        self.assertTrue(any(f.code == 'LASER_SCAN_ALL_NAN' for f in build_findings(a.events)))
        a.ingest('/scan','sensor_msgs/msg/LaserScan',2,scan_payload([1.]))
        for i in range(3):
            a.ingest('/scan','sensor_msgs/msg/LaserScan',3+i,scan_payload([float('nan')]))
        self.assertEqual([e.code for e in a.events].count('LASER_SCAN_ALL_NAN'),2)

    def test_zero_returns_and_empty_sequences_not_false_positive(self):
        a=TelemetryAnalyzer('sample.mcap')
        for i in range(4):
            a.ingest('/scan','sensor_msgs/msg/LaserScan',i,scan_payload([]))
        self.assertEqual(a.events,[])

    def test_bad_range_metadata_transition_and_recovery(self):
        a=TelemetryAnalyzer('sample.mcap')
        for ts,low,high in [(0,4.,2.),(1,4.,2.),(2,.1,12.),(3,4.,2.)]:
            a.ingest('/scan','sensor_msgs/msg/LaserScan',ts,scan_payload([1.,2.],range_min=low,range_max=high))
        self.assertEqual([e.code for e in a.events],['LASER_SCAN_METADATA_INVALID']*2)

    def test_missing_angles_and_bad_intensity_length(self):
        a=TelemetryAnalyzer('sample.mcap')
        a.ingest('/a/scan','sensor_msgs/msg/LaserScan',1,scan_payload([1.,2.],increment=0.))
        a.ingest('/b/scan','sensor_msgs/msg/LaserScan',2,scan_payload([1.,2.],intensities=[4.]))
        self.assertEqual([e.code for e in a.events],['LASER_SCAN_METADATA_INVALID']*2)

    def test_truncated_and_huge_array_fail_closed(self):
        a=TelemetryAnalyzer('sample.mcap')
        valid=scan_payload([1.,2.])
        a.ingest('/scan','sensor_msgs/msg/LaserScan',1,valid[:-4])
        a.ingest('/scan','sensor_msgs/msg/LaserScan',2,valid[:45]+struct.pack('<I',250001))
        self.assertEqual(a.decode_failures,2)
        self.assertEqual(a.events,[])

    def test_scans_are_isolated_per_robot_topic(self):
        a=TelemetryAnalyzer('sample.mcap')
        for i in range(3):
            a.ingest('/robot1/scan','sensor_msgs/msg/LaserScan',i,scan_payload([float('nan')]))
            a.ingest('/robot2/scan','sensor_msgs/msg/LaserScan',i,scan_payload([float('inf')]))
        self.assertEqual(len(a.events),1)
        self.assertEqual(a.events[0].robot_id,'robot1')

    def test_laserscan_db3_and_mcap_integration(self):
        payloads=[scan_payload([float('nan')]*2) for _ in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            db=d/'test.db3'
            con=sqlite3.connect(db)
            con.execute('CREATE TABLE topics(id INTEGER PRIMARY KEY,name TEXT,type TEXT)')
            con.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER,timestamp INTEGER,data BLOB)')
            con.execute('INSERT INTO topics VALUES(1,?,?)',('/scan','sensor_msgs/msg/LaserScan'))
            con.executemany('INSERT INTO messages(topic_id,timestamp,data) VALUES(1,?,?)',[(1700000000000000000+i*100000000,p) for i,p in enumerate(payloads)])
            con.commit();con.close()
            m=d/'test.mcap'
            typ='sensor_msgs/msg/LaserScan'; topic='/scan'
            seq=[mcap_record(0x01,field('ros2')+field('synthetic')),
                 mcap_record(0x03,struct.pack('<H',1)+field(typ)+field('ros2msg')+struct.pack('<I',0)),
                 mcap_record(0x04,struct.pack('<HH',1,1)+field(topic)+field('cdr')+struct.pack('<I',0))]
            for i,p in enumerate(payloads):
                seq.append(mcap_record(0x05,struct.pack('<HIQQ',1,i,1700000000000000000+i*100000000,1700000000000000000+i*100000000)+p))
            seq.extend([mcap_record(0x0f,struct.pack('<I',0)),mcap_record(0x02,struct.pack('<QQI',0,0,0))])
            m.write_bytes(b'\x89MCAP0\r\n'+b''.join(seq)+b'\x89MCAP0\r\n')
            for f in (db,m):
                ev,st,warnings=read_rosbag(f)
                self.assertEqual([x.code for x in ev],['LASER_SCAN_ALL_NAN'])
                self.assertFalse(any('not inspected' in w.lower() or 'failed schema' in w.lower() for w in warnings))

if __name__=='__main__':unittest.main()
