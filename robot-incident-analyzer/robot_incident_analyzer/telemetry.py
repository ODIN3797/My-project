"""Bounded CDR decoding of selected common ROS2 message types.

This is NOT a general-purpose CDR/ROSIDL implementation. Unsupported/custom schemas
are deliberately skipped. All observations are heuristics, not root-cause claims.
"""
from __future__ import annotations

from collections import defaultdict
from bisect import bisect_left
from .discovery import discover, canonical_type, robot_namespace
import math
import struct
from typing import Any

from .models import Event


class CDR:
    def __init__(self, payload: bytes):
        if len(payload) < 4 or payload[0] != 0 or payload[1] not in (0, 1):
            raise ValueError('Invalid CDR encapsulation')
        self.data, self.endian, self.pos = payload, ('<' if payload[1] == 1 else '>'), 4

    def read(self, fmt: str, alignment: int | None = None):
        alignment = alignment or struct.calcsize(fmt)
        self.pos += (-(self.pos - 4)) % alignment
        size = struct.calcsize(fmt)
        if self.pos + size > len(self.data):
            raise ValueError('Truncated CDR message')
        result = struct.unpack_from(self.endian + fmt, self.data, self.pos)[0]
        self.pos += size
        return result

    def skip(self, count: int, alignment: int = 8):
        self.pos += (-(self.pos - 4)) % alignment
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError('Truncated CDR array')
        self.pos += count

    def string(self):
        length = self.read('I', 4)
        if length > 65536 or length < 1 or self.pos + length > len(self.data):
            raise ValueError('Malformed or overly long CDR string')
        data = self.data[self.pos: self.pos + length]
        self.pos += length
        return data.rstrip(b'\x00').decode('utf-8', errors='replace')

    def sequence_count(self, limit: int = 500):
        count = self.read('I', 4)
        if count > limit:
            raise ValueError(f'CDR sequence exceeds safety limit {limit}')
        return count

    def vector3(self):
        return (self.read('d'), self.read('d'), self.read('d'))

    def quaternion(self):
        return tuple(self.read('d') for _ in range(4))

    def header(self):
        sec = self.read('i', 4)
        nanosec = self.read('I', 4)
        return (sec + nanosec / 1e9, self.string())

    def twist(self):
        return {'linear': self.vector3(), 'angular': self.vector3()}


def decode_standard(msgtype: str, payload: bytes) -> Any:
    """Return a normalized dict for supported ROS2 standard types or None."""
    msgtype = msgtype.replace('/msg/', '/')
    supported = (
        'geometry_msgs/Twist', 'geometry_msgs/TwistStamped', 'nav_msgs/Odometry',
        'tf2_msgs/TFMessage', 'diagnostic_msgs/DiagnosticArray',
    )
    if msgtype not in supported:
        return None
    c = CDR(payload)
    if msgtype == 'geometry_msgs/Twist':
        return c.twist()
    if msgtype == 'geometry_msgs/TwistStamped':
        c.header()
        return c.twist()
    if msgtype == 'nav_msgs/Odometry':
        stamp, frame = c.header()
        child = c.string()
        position, orientation = c.vector3(), c.quaternion()
        c.skip(36 * 8)
        twist = c.twist()
        c.skip(36 * 8)
        return {'position': position, 'orientation': orientation, 'linear': twist['linear'],
                'angular': twist['angular'], 'frame': frame, 'child': child, 'stamp': stamp}
    if msgtype == 'tf2_msgs/TFMessage':
        transforms = []
        for _ in range(c.sequence_count(500)):
            stamp, parent = c.header()
            child = c.string()
            translation = c.vector3()
            rotation = c.quaternion()
            transforms.append({'stamp': stamp, 'parent': parent, 'child': child,
                               'translation': translation, 'rotation': rotation})
        return transforms
    if msgtype == 'diagnostic_msgs/DiagnosticArray':
        c.header()
        statuses = []
        for _ in range(c.sequence_count(500)):
            level = c.read('B', 1)
            name, message, hardware_id = c.string(), c.string(), c.string()
            values = {}
            for n in range(c.sequence_count(100)):
                key, value = c.string(), c.string()
                if n < 8:
                    values[key[:80]] = value[:120]
            statuses.append({'level': level, 'name': name, 'message': message,
                             'hardware_id': hardware_id, 'values': values})
        return statuses
    return None


def valid_quat(q):
    norm = sum(v*v for v in q)
    return all(math.isfinite(v) for v in q) and .8 <= norm <= 1.2


DEFAULT_THRESHOLDS = {
    'command_min_mps': 0.20, 'odom_stopped_max_mps': 0.03,
    'sync_tolerance_s': 0.35, 'mismatch_min_samples': 4,
    'mismatch_min_duration_s': 0.25, 'odom_jump_m': 1.0,
    'odom_jump_window_s': 0.5, 'tf_jump_m': 1.0,
    'tf_jump_window_s': 1.0,
}


def validate_thresholds(custom=None):
    values = dict(DEFAULT_THRESHOLDS)
    for key, val in (custom or {}).items():
        if key not in values: raise ValueError(f'Unknown threshold: {key}')
        if isinstance(val, bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or val <= 0:
            raise ValueError(f'Threshold {key} must be finite and positive')
        values[key] = val
    if values['mismatch_min_samples'] != int(values['mismatch_min_samples']):
        raise ValueError('mismatch_min_samples must be an integer')
    return values


class TelemetryAnalyzer:
    def __init__(self, source: str, topic_map=None, thresholds=None, schema_registry=None, custom_roles=None):
        self.source = source
        self.schema_registry = schema_registry
        self.custom_roles = custom_roles or {}
        self.custom_decoded = 0
        self.topic_map = topic_map or {}
        self.thresholds = validate_thresholds(thresholds)
        self.last_odom = {}  # per topic, never cross-correlate distinct odom sources
        self.last_tf = {}
        self.cmd_streams = defaultdict(list)
        self.odom_streams = defaultdict(list)
        self.topics = {}
        self.events: list[Event] = []
        self.unsupported = set()
        self.decode_failures = 0
        self.discovery = None
        self.velocity_trace = []

    def emit(self, ts, code, message, topic, severity='WARN'):
        self.events.append(Event(timestamp=ts, severity=severity, category='telemetry',
                                 code=code, message=message[:4000], source=self.source, topic=topic,
                                 robot_id=robot_namespace(topic) or 'unknown'))

    def ingest(self, topic: str, msgtype: str, ts: float, data: bytes):
        canonical = canonical_type(msgtype)
        self.topics[topic] = msgtype
        standard = {'geometry_msgs/Twist', 'geometry_msgs/TwistStamped', 'nav_msgs/Odometry',
                    'tf2_msgs/TFMessage', 'diagnostic_msgs/DiagnosticArray'}
        custom = canonical in self.custom_roles and canonical not in standard
        if canonical not in standard and not custom:
            self.unsupported.add(msgtype)
            return
        try:
            if custom:
                from .custom_messages import as_telemetry
                decoded = as_telemetry(self.schema_registry.decode(canonical, data), self.custom_roles[canonical])
                self.custom_decoded += 1
            else:
                decoded = decode_standard(msgtype, data)
        except (ValueError, struct.error, OverflowError, RecursionError):
            self.decode_failures += 1
            return
        if canonical.startswith('geometry_msgs/Twist') or (custom and self.custom_roles[canonical]['role'] == 'command'):
            self.cmd_streams[topic].append((ts,decoded))
            return
        if canonical == 'nav_msgs/Odometry' or (custom and self.custom_roles[canonical]['role'] == 'odometry'):
            self.odom_streams[topic].append((ts,decoded))
            if decoded.get('orientation') is not None and not valid_quat(decoded['orientation']):
                self.emit(ts, 'ODOM_INVALID_QUATERNION', 'Odometry orientation has invalid quaternion norm.', topic)
            prev = self.last_odom.get(topic)
            if prev and decoded.get('position') is not None:
                prev_ts,prev_pos=prev
                dt=ts-prev_ts
                dist=math.dist(decoded['position'],prev_pos)
                if 0 < dt <= self.thresholds['odom_jump_window_s'] and dist > self.thresholds['odom_jump_m']:
                    self.emit(ts,'ODOM_POSITION_JUMP', f'{topic}: odometry position jumped {dist:.2f} m over {dt:.3f} s (record timestamps).',topic)
            if decoded.get('position') is not None:
                self.last_odom[topic]=(ts,decoded['position'])
            return
        if canonical == 'tf2_msgs/TFMessage':
            for tf in decoded:
                parent = tf['parent'].strip('/')
                child = tf['child'].strip('/')
                if not parent or not child or parent == child:
                    self.emit(ts, 'TF_FRAME_INVALID', f'Invalid TF frame pair: {parent!r} -> {child!r}', topic)
                if not valid_quat(tf['rotation']):
                    self.emit(ts, 'TF_INVALID_QUATERNION', f'Invalid quaternion in TF {parent} -> {child}.', topic)
                key = (topic,parent,child)
                # Namespace-aware matching: robot1/map -> robot1/odom is accepted.
                is_map_odom=(parent.split('/')[-1]=='map' and child.split('/')[-1]=='odom' and
                             (parent.rsplit('/',1)[0] if '/' in parent else '') == (child.rsplit('/',1)[0] if '/' in child else ''))
                if is_map_odom and key in self.last_tf:
                    prev_ts,prev_xyz=self.last_tf[key]
                    dt=ts-prev_ts
                    dist=math.dist(prev_xyz,tf['translation'])
                    if 0 < dt <= self.thresholds['tf_jump_window_s'] and dist > self.thresholds['tf_jump_m']:
                        self.emit(ts,'TF_MAP_ODOM_JUMP', f'{parent} -> {child} moved {dist:.2f} m over {dt:.3f} s; may reflect localization correction.',topic)
                self.last_tf[key]=(ts,tf['translation'])
            return
        if canonical == 'diagnostic_msgs/DiagnosticArray':
            for status in decoded:
                if status['level'] in (1,2,3):
                    severity = 'ERROR' if status['level'] in (2,3) else 'WARN'
                    level = {1:'WARN',2:'ERROR',3:'STALE'}[status['level']]
                    values=', '.join(f'{k}={v}' for k,v in list(status['values'].items())[:3])
                    self.emit(ts,'DIAGNOSTIC_'+level, f'{status["name"]}: {status["message"]} (level={level})'
                              +(f'; {values}' if values else ''),topic,severity=severity)

    def finalize(self):
        self.discovery=discover(self.topics,self.topic_map,self.custom_roles)
        if self.unsupported:
            names=', '.join(sorted(self.unsupported)[:6])
            self.discovery.warnings.append(f'Payloads of {len(self.unsupported)} unsupported message type(s) were NOT inspected ({names}); topic timing only where present')
        mapping=self.discovery.selected
        command,odometry=mapping.get('command'),mapping.get('odometry')
        if not command or not odometry:
            return self.discovery.warnings, [], self.discovery.to_dict()
        cmds=sorted(self.cmd_streams.get(command,[]),key=lambda x:x[0])
        odoms=sorted(self.odom_streams.get(odometry,[]),key=lambda x:x[0])
        if not cmds or not odoms:
            self.discovery.warnings.append('Selected command or odometry has no decodable messages; velocity matching skipped')
            return self.discovery.warnings,[],self.discovery.to_dict()
        ct=[x[0] for x in cmds]
        count=0;start=None;already=False
        trace=[]
        for ts,obs in odoms:
            at=bisect_left(ct,ts)
            near=min((cmds[i] for i in (at-1,at) if 0<=i<len(cmds)),
                     key=lambda x:abs(x[0]-ts),default=None)
            if near and abs(near[0]-ts)<=self.thresholds['sync_tolerance_s']:
                desired=near[1]['linear'][0]
                observed=obs['linear'][0]
                if math.isfinite(desired) and math.isfinite(observed):
                    trace.append({'time':round(ts,6),'command_mps':round(desired,5),
                                  'odometry_mps':round(observed,5)})
                    mismatch=abs(desired)>=self.thresholds['command_min_mps'] and abs(observed)<=self.thresholds['odom_stopped_max_mps']
                    if mismatch:
                        if start is None: start=ts;count=0;already=False
                        count+=1
                        if not already and count>=self.thresholds['mismatch_min_samples'] and ts-start>=self.thresholds['mismatch_min_duration_s']:
                            self.emit(ts,'CMD_ODOM_MISMATCH',f'{command}: command {desired:.2f} m/s vs {odometry}: odom {observed:.2f} m/s for {ts-start:.2f}s. ' +
                                      'Check safety state, command source and frame/timing alignment.',odometry)
                            already=True
                    else: start=None;count=0;already=False
                else: start=None;count=0;already=False
            else: start=None;count=0;already=False
        if trace:
            # Reduce report size while preserving first/last point.
            step=max(1,(len(trace)+399)//400)
            self.velocity_trace=trace[::step]
            if trace[-1] != self.velocity_trace[-1]: self.velocity_trace.append(trace[-1])
        return self.discovery.warnings,self.velocity_trace,self.discovery.to_dict()
