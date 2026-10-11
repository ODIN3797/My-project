from __future__ import annotations

import csv
import math
import sqlite3
import statistics
import struct
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .models import Event, TopicStats

LOG_LEVELS = {10: 'DEBUG', 20: 'INFO', 30: 'WARN', 40: 'ERROR', 50: 'FATAL'}
SEVERITIES = {'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL'}


def parse_time(value: str) -> float:
    value = str(value).strip()
    if not value:
        raise ValueError('Empty timestamp')
    try:
        parsed = float(value)
    except ValueError:
        parsed = None
    if parsed is not None:
        if not math.isfinite(parsed) or not -62135596800 <= parsed <= 253402300799:
            raise ValueError(f'Invalid CSV timestamp: {value!r}')
        return parsed
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    stamp = dt.timestamp()
    if not math.isfinite(stamp) or not -62135596800 <= stamp <= 253402300799:
        raise ValueError(f'Invalid CSV timestamp: {value!r}')
    return stamp


def classify(message: str, fallback: str = 'ROS_LOG') -> str:
    msg = message.lower()
    if 'tf_' in msg or 'transform' in msg or 'extrapolation' in msg:
        return 'TF_ERROR'
    if 'charging' in msg or 'charger' in msg or 'charge current' in msg:
        return 'CHARGING'
    if 'disconnect' in msg or 'connection lost' in msg or 'network' in msg or 'mqtt' in msg:
        return 'COMMUNICATION'
    if 'timeout' in msg or 'timed out' in msg:
        return 'TIMEOUT'
    if 'navigation' in msg or 'nav2' in msg or 'controller failed' in msg or 'goal aborted' in msg:
        return 'NAVIGATION'
    if 'lidar' in msg or 'laser' in msg or 'imu' in msg or 'scan' in msg:
        return 'SENSOR'
    if 'motor' in msg or 'traction' in msg:
        return 'MOTOR'
    return fallback


def read_csv_events(path: Path) -> list[Event]:
    with path.open('r', encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        required = {'timestamp', 'message'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f'{path}: CSV needs columns timestamp,message')
        events = []
        for line, row in enumerate(reader, start=2):
            if not row.get('timestamp') or not row.get('message'):
                continue
            severity = (row.get('severity') or 'INFO').strip().upper()
            if severity == 'WARNING':
                severity = 'WARN'
            if severity not in SEVERITIES:
                severity = 'INFO'
            msg = row['message'].strip()
            events.append(Event(
                timestamp=parse_time(row['timestamp']), severity=severity,
                category=(row.get('category') or 'log').strip()[:80],
                code=(row.get('code') or classify(msg)).strip()[:100], message=msg[:4000],
                robot_id=(row.get('robot_id') or 'unknown').strip()[:100],
                source=f'{path.name}:row{line}', topic=(row.get('topic') or '').strip()[:100],
            ))
        return events


class CDRDecoder:
    """Small, bounded decoder for the standard rcl_interfaces/msg/Log layout only.

    NOT a general ROS deserializer. All other message payloads are skipped.
    """
    def __init__(self, payload: bytes):
        if len(payload) < 4 or payload[0] != 0 or payload[1] not in (0, 1):
            raise ValueError('Not a supported CDR encapsulation')
        self.payload = payload
        self.endian = '<' if payload[1] == 1 else '>'
        self.pos = 4

    def get(self, fmt: str, align: int):
        self.pos += (-(self.pos - 4)) % align
        fmt = self.endian + fmt
        size = struct.calcsize(fmt)
        if self.pos + size > len(self.payload):
            raise ValueError('Truncated CDR data')
        result = struct.unpack_from(fmt, self.payload, self.pos)[0]
        self.pos += size
        return result

    def text(self):
        size = self.get('I', 4)
        if size < 1 or size > 65536 or self.pos + size > len(self.payload):
            raise ValueError('Invalid CDR string length')
        raw = self.payload[self.pos:self.pos + size]
        self.pos += size
        return raw.rstrip(b'\0').decode('utf-8', errors='replace')


def decode_rosout_log(payload: bytes) -> tuple[int, str, str]:
    """Read the level, node name and text of rcl_interfaces/msg/Log.

    Schema: builtin_interfaces/Time stamp, uint8 level, string name, string msg,
    string file, string function, uint32 line.
    """
    dec = CDRDecoder(payload)
    dec.get('i', 4)  # stamp.sec
    dec.get('I', 4)  # stamp.nanosec
    level = dec.get('B', 1)
    name = dec.text()
    message = dec.text()
    return level, name, message


def is_periodic_sensor(topic: str) -> bool:
    lower = topic.lower()
    return any(word in lower for word in ('/scan', '/imu', '/points', '/camera', '/lidar', '/odom', '/tf'))


def read_rosbag(path: Path, max_messages: int = 200_000, *, with_details: bool = False,
                topic_map=None, thresholds=None, schema_registry=None, custom_roles=None):
    from collections import defaultdict
    from .bag_reader import read_bag
    from .telemetry import TelemetryAnalyzer
    warnings: list[str] = []
    times: dict[tuple[str, str], list[float]] = defaultdict(list)
    events: list[Event] = []
    telemetry = TelemetryAnalyzer(path.name, topic_map=topic_map, thresholds=thresholds,
                                  schema_registry=schema_registry, custom_roles=custom_roles)
    for topic, msgtype, timestamp_ns, data in read_bag(path, max_messages, warnings):
        ts = timestamp_ns / 1e9
        if not math.isfinite(ts):
            warnings.append(f'{path.name}: invalid nonfinite message timestamp skipped')
            continue
        times[(topic, msgtype)].append(ts)
        if (msgtype.replace('/msg/', '/') == 'rcl_interfaces/Log' and
            (topic.rstrip('/').split('/')[-1] in ('rosout','ros_log','log'))):
            try:
                level, node, msg = decode_rosout_log(data)
            except (ValueError, struct.error):
                warnings.append(f'{path.name}: one /rosout log could not be decoded')
                continue
            severity = LOG_LEVELS.get(level, 'INFO')
            if severity in ('WARN', 'ERROR', 'FATAL'):
                events.append(Event(timestamp=ts, severity=severity, category='rosout',
                                    code=classify(msg), message=f'[{node}] {msg}'[:4000],
                                    source=path.name, topic=topic))
        else:
            telemetry.ingest(topic,msgtype,ts,data)

    discovery_warnings, trace, mapping = telemetry.finalize()
    warnings.extend(f"{path.name}: {w}" for w in discovery_warnings)
    events.extend(telemetry.events)
    if telemetry.decode_failures:
        warnings.append(f'{path.name}: {telemetry.decode_failures} ROS2 message payload(s) failed schema/CDR decoding; excluded.')
    stats=[]
    for (topic,msgtype), timestamps in times.items():
        if not timestamps: continue
        timestamps.sort()  # messages might be out of order across chunks
        intervals = [b-a for a,b in zip(timestamps, timestamps[1:]) if b-a >= 0]
        duration = max(0.,timestamps[-1]-timestamps[0])
        median_gap=statistics.median(intervals) if intervals else 0.
        max_gap=max(intervals,default=0.)
        stats.append(TopicStats(topic,msgtype,len(timestamps),round(duration,3),
                                round((len(timestamps)-1)/duration,2) if duration else 0.,
                                round(median_gap*1000,2),round(max_gap*1000,2)))
        if is_periodic_sensor(topic) and len(intervals)>=8 and median_gap>0:
            p90=sorted(intervals)[int((len(intervals)-1)*.9)]
            if p90<=median_gap*2.5:
                threshold=max(.4,median_gap*5)
                outliers=sorted([(i,dt) for i,dt in enumerate(intervals) if dt>threshold],
                                key=lambda item:-item[1])[:4]
                for i,dt in outliers:
                    events.append(Event(timestamp=timestamps[i+1],severity='WARN',category='topic_timing',
                                        code='TOPIC_GAP',message=f'{topic}: {dt:.2f}s between messages '
                                        f'(typical {median_gap:.3f}s); recording timestamps only',
                                        source=path.name,topic=topic))
    if with_details:
        return events, stats, warnings, {'source':path.name,'discovery':mapping,'velocity_trace':trace, 'custom_decoded':telemetry.custom_decoded,
                **telemetry.signal_sampler.result()}
    return events, stats, warnings


def read_rosbag_db3(path: Path, max_messages: int = 200_000):
    """Backward-compatible alias; v0.2 decodes standard types as well."""
    return read_rosbag(path,max_messages)


def collect_inputs(inputs: list[Path], max_messages: int = 200_000, *,
                   with_details: bool = False, topic_map=None, thresholds=None,
                   schema_registry=None, custom_roles=None):
    files: list[Path] = []
    for given in inputs:
        if given.is_dir():
            files.extend(p for p in given.rglob('*') if p.suffix.lower() in ('.csv','.db3','.sqlite3','.mcap'))
        elif given.is_file() and given.suffix.lower() in ('.csv','.db3','.sqlite3','.mcap'):
            files.append(given)
        else:
            raise ValueError(f'Unsupported input or missing file: {given}. Supported: CSV, DB3, MCAP')
    files=sorted(set(files))
    if not files:
        raise ValueError('No CSV/DB3/MCAP files found')
    events, stats, warnings, details = [], [], [], []
    for path in files:
        if path.suffix.lower()=='.csv':
            events.extend(read_csv_events(path))
        else:
            if with_details:
                ev,st,warn,detail=read_rosbag(path,max_messages,with_details=True,
                                             topic_map=topic_map,thresholds=thresholds,
                                             schema_registry=schema_registry,custom_roles=custom_roles)
                details.append(detail)
            else:
                ev,st,warn=read_rosbag(path,max_messages,topic_map=topic_map,thresholds=thresholds,
                                             schema_registry=schema_registry,custom_roles=custom_roles)
            events.extend(ev); stats.extend(st); warnings.extend(warn)
    events.sort(key=lambda e:(e.timestamp,e.source,e.code))
    for index,event in enumerate(events,1):
        event.event_id=f'E{index:04d}'
    if with_details:
        return events,stats,warnings,files,details
    return events,stats,warnings,files
