"""Synthetic uncompressed MCAP performance benchmark. NOT physical robot data.

Run: PYTHONPATH=. python validation/benchmark_mcap.py 75000
"""
from __future__ import annotations
import json
import resource
import struct
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from robot_incident_analyzer.fixture_v2 import mcap_record, field, odom_payload, twist_payload, BASE
from robot_incident_analyzer.__main__ import analyze_files


def run(pairs=75_000):
    if not 1 <= pairs <= 150_000:
        raise ValueError('pairs must be in 1..150000 for local benchmark')
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        path=root/'synthetic_load.mcap'
        base_ns=int(BASE * 1e9)
        with path.open('wb') as f:
            f.write(b'\x89MCAP0\r\n')
            f.write(mcap_record(0x01,field('ros2')+field('synthetic-benchmark')))
            for i,(topic,typ) in enumerate([('/cmd_vel','geometry_msgs/msg/Twist'),('/odom','nav_msgs/msg/Odometry')], 1):
                f.write(mcap_record(0x03,struct.pack('<H',i)+field(typ)+field('ros2msg')+struct.pack('<I',0)))
                f.write(mcap_record(0x04,struct.pack('<HH',i,i)+field(topic)+field('cdr')+struct.pack('<I',0)))
            twist=twist_payload(.5)
            for n in range(pairs):
                ns=base_ns+n*50_000_000
                f.write(mcap_record(0x05,struct.pack('<HIQQ',1,n*2,ns,ns)+twist))
                ts=ns+10_000_000
                odom=odom_payload(ts/1e9,n*.025,.5)
                f.write(mcap_record(0x05,struct.pack('<HIQQ',2,n*2+1,ts,ts)+odom))
            f.write(mcap_record(0x0f,struct.pack('<I',0)))
            f.write(mcap_record(0x02,struct.pack('<QQI',0,0,0)))
            f.write(b'\x89MCAP0\r\n')
        start=perf_counter()
        events,findings,topics,warnings,files,details=analyze_files([path],root/'report')
        elapsed=perf_counter()-start
        assert len(topics)==2
        assert not any(e.code=='CMD_ODOM_MISMATCH' for e in events)
        assert (root/'report'/'report.json').exists()
        return {
            'origin':'synthetic_not_robot', 'python':sys.version.split()[0], 'pairs':pairs,
            'messages_generated':pairs*2,
            'default_message_limit':200_000,
            'file_mib':round(path.stat().st_size/(1024**2),2),
            'analysis_seconds':round(elapsed,3),
            'peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
            'topic_count':len(topics),'event_count':len(events),'warnings':warnings,
            'partial_input':any('Only first' in w for w in warnings),
        }

if __name__=='__main__':
    n = int(sys.argv[1]) if len(sys.argv)>1 else 75_000
    print(json.dumps(run(n),indent=2))
