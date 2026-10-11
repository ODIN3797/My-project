from __future__ import annotations
from io import BytesIO
import json
from pathlib import Path
import struct
import tempfile
import unittest

from robot_incident_analyzer.analysis import build_findings
from robot_incident_analyzer.bag_reader import MAGIC, iter_mcap
from robot_incident_analyzer.fixture_v2 import (BASE, diagnostic_payload, make_db3, make_mcap,
                                                mcap_record, field, odom_payload, tf_payload,
                                                twist_payload)
from robot_incident_analyzer.inputs import collect_inputs
from robot_incident_analyzer.models import Event
from robot_incident_analyzer.report import save_report
from robot_incident_analyzer.telemetry import CDR, decode_standard


EXPECTED={'CMD_ODOM_MISMATCH','ODOM_POSITION_JUMP','TF_MAP_ODOM_JUMP',
          'TF_INVALID_QUATERNION','DIAGNOSTIC_WARN','DIAGNOSTIC_ERROR'}


class TelemetryV2Tests(unittest.TestCase):
    def test_cd_standards(self):
        tw=decode_standard('geometry_msgs/msg/Twist',twist_payload(.5))
        self.assertAlmostEqual(tw['linear'][0],.5)
        od=decode_standard('nav_msgs/msg/Odometry',odom_payload(BASE,.2,.4))
        self.assertAlmostEqual(od['linear'][0],.4)
        self.assertEqual(od['frame'],'odom')
        self.assertAlmostEqual(od['position'][0],.2)
        tf=decode_standard('tf2_msgs/msg/TFMessage',tf_payload(BASE,(1,2,3)))
        self.assertEqual(tf[0]['parent'],'map')
        self.assertEqual(tf[0]['translation'],(1.,2.,3.))
        diag=decode_standard('diagnostic_msgs/msg/DiagnosticArray',diagnostic_payload(BASE,2,'Fault'))
        self.assertEqual(diag[0]['level'],2)
        self.assertEqual(diag[0]['values']['can_timeout'],'1')

    def test_invalid_cdr_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_standard('geometry_msgs/msg/Twist',b'\0\x01\0\0\0')
        self.assertIsNone(decode_standard('custom_msgs/msg/Foo',b'fake'))
        with self.assertRaises(ValueError):
            CDR(b'not cdr')

    def _analyze(self,path):
        events, stats, warnings, files=collect_inputs([path])
        codes={e.code for e in events}
        self.assertTrue(EXPECTED.issubset(codes),codes)
        self.assertEqual(len(stats),4)
        self.assertFalse(warnings,warnings)
        return events,stats,warnings,files

    def test_real_cdr_db3_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=make_db3(Path(tmp)/'real_cdr_demo.db3')
            events,stats,_,_=self._analyze(path)
            self.assertTrue(any(s.topic=='/odom' and s.count==15 for s in stats))
            codes={f.code for f in build_findings(events)}
            self.assertIn('CMD_ODOM_MISMATCH',codes)

    def test_native_mcap_cdr_messages_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=make_mcap(root/'recording.mcap')
            events,stats,warnings,files=self._analyze(path)
            save_report(root/'output',events,build_findings(events),stats,warnings,files)
            report=json.loads((root/'output'/'report.json').read_text())
            self.assertEqual(report['version'],'0.5.0')
            self.assertTrue(any(x['code']=='TF_MAP_ODOM_JUMP' for x in report['findings']))
            self.assertIn('CDR types decoded', (root/'output'/'report.html').read_text())

    def test_chunked_uncompressed_mcap(self):
        # Convert a tiny message to MCAP CHUNK record (chunk with embedded Message).
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'chunked.mcap'
            ts=round(BASE*1e9)
            schema=mcap_record(3,struct.pack('<H',1)+field('geometry_msgs/msg/Twist')+field('ros2msg')+struct.pack('<I',0))
            channel=mcap_record(4,struct.pack('<HH',1,1)+field('/cmd_vel')+field('cdr')+struct.pack('<I',0))
            message=mcap_record(5,struct.pack('<HIQQ',1,0,ts,ts)+twist_payload(.25))
            # Chunk layout: time start/end, uncompressed length, crc, compression string, length64 + records
            chunk=struct.pack('<QQQI',ts,ts,len(message),0)+field('')+struct.pack('<Q',len(message))+message
            path.write_bytes(MAGIC+mcap_record(1,field('ros2')+field('test'))+schema+channel+
                             mcap_record(6,chunk)+mcap_record(15,struct.pack('<I',0))+
                             mcap_record(2,struct.pack('<QQI',0,0,0))+MAGIC)
            warnings=[]
            messages=list(iter_mcap(path,warnings))
            self.assertEqual(len(messages),1)
            self.assertEqual(messages[0][1],'geometry_msgs/msg/Twist')
            self.assertEqual(warnings,[])

    def test_mcap_invalid_magic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'invalid.mcap'
            path.write_bytes(b'not a bag')
            with self.assertRaises(ValueError):
                list(iter_mcap(path,[]))

    def test_no_cross_file_matching_when_robot_unknown(self):
        error=Event(timestamp=BASE+2,severity='ERROR',category='navigation',code='NAVIGATION',
                    message='navigation aborted',source='file-b.db3',event_id='E2')
        timeout=Event(timestamp=BASE,severity='WARN',category='network',code='TIMEOUT',
                      message='timeout',source='file-a.db3',event_id='E1')
        findings=build_findings([timeout,error])
        self.assertNotIn('NAV_WITH_PRECEDING_SIGNAL',{f.code for f in findings})

    def test_truncated_v2_bag_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=make_mcap(Path(tmp)/'truncated.mcap')
            _,stats,warnings,_=collect_inputs([path],max_messages=3)
            self.assertTrue(any('partial' in w for w in warnings))
            self.assertTrue(stats)

if __name__=='__main__':unittest.main()
