"""Published ROS2 CDR field-order checks for mavros_msgs and sensor_msgs/Range."""
import math
import struct
import unittest
from robot_incident_analyzer.telemetry import decode_standard, TelemetryAnalyzer


class CDRWriter:
    def __init__(self):
        self.data = bytearray(b'\x00\x01\x00\x00')
    def put(self, fmt, val):
        alignment = struct.calcsize(fmt)
        self.data.extend(b'\0' * ((-(len(self.data) - 4)) % alignment))
        self.data.extend(struct.pack('<' + fmt, val))
        return self
    def text(self, val):
        blob = val.encode('utf-8') + b'\0'
        self.put('I', len(blob))
        self.data.extend(blob)
        return self
    def header(self):
        return self.put('i', 0).put('I', 0).text('robot_1')
    def finish(self):
        return bytes(self.data)


def state(*, connected=True, armed=False, mode='MANUAL', system_status=3):
    c = CDRWriter().header()
    for v in (connected, armed, False, False):
        c.put('?', v)
    return c.text(mode).put('B', system_status).finish()


def ext(vtol=3, landed=1):
    return CDRWriter().header().put('B', vtol).put('B', landed).finish()


def status(severity=4, message='Radio link lost'):
    return CDRWriter().header().put('B', severity).text(message).finish()


def rng(distance=float('inf'), min_dist=0.1, max_dist=2.5):
    c = CDRWriter().header().put('B', 0)
    for x in (0.26, min_dist, max_dist, distance, 0.0):
        c.put('f', x)
    return c.finish()


class MavrosCDRTests(unittest.TestCase):
    def test_published_state_schema(self):
        o = decode_standard('mavros_msgs/msg/State', state(connected=False, armed=True, mode='OFFBOARD', system_status=5))
        self.assertEqual((o['connected'], o['armed'], o['mode'], o['system_status']), (False, True, 'OFFBOARD', 5))
        self.assertFalse(o['guided'])

    def test_extended_state_schema(self):
        self.assertEqual(decode_standard('mavros_msgs/msg/ExtendedState', ext()), {'vtol_state':3, 'landed_state':1})

    def test_status_text_schema(self):
        self.assertEqual(decode_standard('mavros_msgs/msg/StatusText', status(2,'Motor failure')),
                         {'severity':2,'text':'Motor failure'})

    def test_range_inf_rep117(self):
        for d in (float('inf'), -float('inf')):
            self.assertTrue(math.isinf(decode_standard('sensor_msgs/msg/Range',rng(d))['distance']))

    def test_truncated_message_is_rejected(self):
        for t, b in [('mavros_msgs/msg/State',state()),
                     ('mavros_msgs/msg/ExtendedState',ext()),
                     ('mavros_msgs/msg/StatusText',status()),
                     ('sensor_msgs/msg/Range',rng())]:
            with self.subTest(t=t), self.assertRaises(ValueError):
                decode_standard(t, b[:-2])

    def test_mavros_transitions_are_evidence_only(self):
        a=TelemetryAnalyzer('sample.mcap')
        t='mavros_msgs/msg/State';topic='/robot_a/mavros/state'
        a.ingest(topic,t,0.0,state(mode='MANUAL'))
        a.ingest(topic,t,1.0,state(mode='MANUAL'))
        a.ingest(topic,t,2.0,state(mode='OFFBOARD',armed=True))
        self.assertEqual([x.code for x in a.events],['MAVROS_STATE_CHANGE'])
        self.assertIn('mode',a.events[0].message)
        self.assertNotIn('root cause is',a.events[0].message)
        self.assertEqual(a.unsupported,set())
        self.assertIn('armed (0/1)', {e['field'] for e in a.signal_sampler.result()['signals']})

    def test_multi_robot_isolation(self):
        a=TelemetryAnalyzer('sample.mcap')
        t='mavros_msgs/msg/State'
        a.ingest('/robot_a/mavros/state',t,0,state(mode='MANUAL'))
        a.ingest('/robot_b/mavros/state',t,0,state(mode='OFFBOARD'))
        a.ingest('/robot_a/mavros/state',t,1,state(mode='OFFBOARD'))
        self.assertEqual(len(a.events),1)
        self.assertEqual(a.events[0].robot_id,'robot_a')

    def test_extended_state_first_observation_not_alarm(self):
        a=TelemetryAnalyzer('sample.mcap');t='mavros_msgs/msg/ExtendedState'
        a.ingest('/mavros/extended_state',t,0,ext())
        self.assertFalse(a.events)
        a.ingest('/mavros/extended_state',t,1,ext(3,2))
        self.assertEqual(a.events[0].code,'MAVROS_EXTENDED_STATE_CHANGE')

    def test_status_text_severity_dedup_and_separation(self):
        a=TelemetryAnalyzer('sample.mcap');t='mavros_msgs/msg/StatusText';topic='/mavros/statustext'
        a.ingest(topic,t,1,status(4,'<script>alert(1)</script>'))
        a.ingest(topic,t,2,status(4,'<script>alert(1)</script>'))
        a.ingest(topic,t,3,status(7,'debug'))
        a.ingest(topic,t,4,status(3,'motor error'))
        self.assertEqual([x.severity for x in a.events],['WARN','ERROR'])
        self.assertEqual([x.code for x in a.events],['MAVROS_STATUS_TEXT']*2)

    def test_range_inf_not_failure_and_finite_signal(self):
        a=TelemetryAnalyzer('sample.mcap');topic='/robot_a/sonar'
        for i,d in enumerate((float('inf'),-float('inf'),0.72)):
            a.ingest(topic,'sensor_msgs/msg/Range',i,rng(d))
        self.assertEqual(a.events,[])
        series=a.signal_sampler.result()['signals']
        ranges=[s for s in series if s['field']=='range (m)']
        self.assertEqual(len(ranges),1)
        self.assertEqual(ranges[0]['recorded_count'],1)
        self.assertAlmostEqual(ranges[0]['samples'][0][1],0.72)

if __name__=='__main__':unittest.main()

class ROS2BagIntegrationTests(unittest.TestCase):
    def test_db3_and_mcap_with_mavros_and_sonar(self):
        import sqlite3, tempfile
        from pathlib import Path
        from robot_incident_analyzer.fixture_v2 import mcap_record, field
        from robot_incident_analyzer.inputs import read_rosbag
        streams=[
            ('/robot_a/mavros/state','mavros_msgs/msg/State',state(mode='MANUAL')),
            ('/robot_a/mavros/state','mavros_msgs/msg/State',state(mode='AUTO',armed=True)),
            ('/robot_a/mavros/extended_state','mavros_msgs/msg/ExtendedState',ext(3,1)),
            ('/robot_a/mavros/extended_state','mavros_msgs/msg/ExtendedState',ext(3,2)),
            ('/robot_a/mavros/statustext','mavros_msgs/msg/StatusText',status(3,'GPS failsafe')),
            ('/robot_a/sonar','sensor_msgs/msg/Range',rng(float('inf'))),
        ]
        types=sorted(set((topic,typ) for topic,typ,_ in streams))
        ids={p:i+1 for i,p in enumerate(types)}
        base_ns=1700000000000000000
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            db3=root/'mavros.db3'
            with sqlite3.connect(db3) as conn:
                conn.execute('CREATE TABLE topics(id INTEGER PRIMARY KEY,name TEXT,type TEXT,serialization_format TEXT,offered_qos_profiles TEXT)')
                conn.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY,topic_id INTEGER,timestamp INTEGER,data BLOB)')
                for (topic,typ),tid in ids.items():
                    conn.execute('INSERT INTO topics VALUES(?,?,?,?,?)',(tid,topic,typ,'cdr',''))
                for idx,(topic,typ,data) in enumerate(streams):
                    conn.execute('INSERT INTO messages(topic_id,timestamp,data) VALUES(?,?,?)',(ids[(topic,typ)],base_ns+(idx+1)*100000000,data))
            mcap=root/'mavros.mcap'
            body=[mcap_record(0x01,field('ros2')+field('test'))]
            for (topic,typ),tid in ids.items():
                body.append(mcap_record(0x03,struct.pack('<H',tid)+field(typ)+field('ros2msg')+struct.pack('<I',0)))
                body.append(mcap_record(0x04,struct.pack('<HH',tid,tid)+field(topic)+field('cdr')+struct.pack('<I',0)))
            for idx,(topic,typ,data) in enumerate(streams):
                ts=base_ns+(idx+1)*100000000
                body.append(mcap_record(0x05,struct.pack('<HIQQ',ids[(topic,typ)],idx,ts,ts)+data))
            body.append(mcap_record(0x0f,struct.pack('<I',0)))
            body.append(mcap_record(0x02,struct.pack('<QQI',0,0,0)))
            mcap.write_bytes(b'\x89MCAP0\r\n'+b''.join(body)+b'\x89MCAP0\r\n')
            for file in (db3,mcap):
                with self.subTest(fmt=file.suffix):
                    events,stats,warnings,detail=read_rosbag(file,with_details=True)
                    self.assertEqual([e.code for e in events],['MAVROS_STATE_CHANGE','MAVROS_EXTENDED_STATE_CHANGE','MAVROS_STATUS_TEXT'])
                    self.assertEqual(len(stats),4)
                    self.assertFalse([w for w in warnings if 'unsupported message type' in w.lower()],warnings)
                    self.assertGreaterEqual(len(detail['signals']),4)
