"""Explicit, bounded ROS2 .msg CDR decoder for *authorized* user-provided schemas.

Subset deliberately supported: ROS2 primitive numeric/bool/string, fixed arrays,
variable arrays and recursively referenced .msg messages. No runtime code execution,
no remote schema fetch, no .idl syntax. Config explicitly maps message types and
field paths to semantic command/odometry roles (never infer from field name alone).
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import struct

from .discovery import canonical_type

MAX_SCHEMA_BYTES = 128 * 1024
MAX_MESSAGES = 200
MAX_DEPTH = 12
MAX_ARRAY = 10000
MAX_STRING = 65536
MAX_FIELDS = 128

PRIMITIVES = {
    'bool': ('B', 1), 'byte': ('B', 1), 'char': ('B', 1),
    'int8': ('b', 1), 'uint8': ('B', 1), 'int16': ('h', 2),
    'uint16': ('H', 2), 'int32': ('i', 4), 'uint32': ('I', 4),
    'int64': ('q', 8), 'uint64': ('Q', 8), 'float32': ('f', 4), 'float64': ('d', 8),
}
# ROS2 builtin interfaces available without user-supplied dependencies.
BUILTINS = {
    'builtin_interfaces/Time': [('int32', 'sec', None), ('uint32', 'nanosec', None)],
    'builtin_interfaces/Duration': [('int32', 'sec', None), ('uint32', 'nanosec', None)],
    'std_msgs/Header': [('builtin_interfaces/Time', 'stamp', None), ('string', 'frame_id', None)],
}
TYPE_RE = re.compile(r'^([\w/]+)(?:<=\d+)?(\[(?:(<=)?(\d+))?\])?$')
FIELD_RE = re.compile(r'^([\w/]+(?:<=\d+)?(?:\[(?:<=?\d+)?\])?)\s+([A-Za-z]\w*)$')
NAME_RE = re.compile(r'^[A-Za-z][\w]*/(?:msg/)?[A-Za-z]\w*$')
PATH_RE = re.compile(r'^[A-Za-z]\w*(?:\.[A-Za-z]\w*)*$')


def resolve_type(typename: str, current_package: str) -> str:
    if typename in PRIMITIVES or typename.startswith('string'):
        return typename
    if '/' not in typename:
        return f'{current_package}/{typename}'
    return canonical_type(typename)


def parse_msg(text: str, package: str):
    fields = []
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line or line == '---' or line.startswith('==='):
            continue
        if '=' in line:  # ROSIDL constants (no field payload)
            continue
        match = FIELD_RE.fullmatch(line)
        if not match:
            raise ValueError(f'Unsupported .msg field declaration: {line[:120]}')
        raw_type, name = match.groups()
        tm = TYPE_RE.fullmatch(raw_type)
        if not tm:
            raise ValueError('Invalid field type: ' + raw_type)
        base, brackets, bound, length = tm.groups()
        # sequence: [] or [<=N]; fixed array: [N]
        if brackets is None:
            array = None
        elif length is None:
            array = ('sequence', MAX_ARRAY)
        elif bound:
            array = ('sequence', min(MAX_ARRAY, int(length)))
        else:
            array = ('fixed', int(length))
        if array and array[1] > MAX_ARRAY:
            raise ValueError('Array size exceeds safety bound')
        fields.append((resolve_type(base, package), name, array))
        if len(fields) > MAX_FIELDS:
            raise ValueError('Schema has too many fields')
    return fields


class CDR:
    def __init__(self, raw: bytes):
        if len(raw) < 4 or raw[0] != 0 or raw[1] not in (0, 1):
            raise ValueError('Unsupported CDR encapsulation')
        self.data = raw
        self.pos = 4
        self.endian = '<' if raw[1] == 1 else '>'

    def read(self, fmt: str, alignment: int):
        self.pos += -(self.pos - 4) % alignment
        size = struct.calcsize(fmt)
        if self.pos + size > len(self.data):
            raise ValueError('CDR payload truncated')
        val = struct.unpack_from(self.endian + fmt, self.data, self.pos)[0]
        self.pos += size
        return val

    def string(self):
        length = self.read('I', 4)
        if not 1 <= length <= MAX_STRING or self.pos + length > len(self.data):
            raise ValueError('Invalid CDR string length')
        raw = self.data[self.pos:self.pos+length]
        self.pos += length
        if raw[-1] != 0:
            raise ValueError('CDR string missing terminator')
        return raw[:-1].decode('utf-8', errors='replace')


class SchemaRegistry:
    def __init__(self, directories: list[str] | None = None):
        self.definitions = dict(BUILTINS)
        for folder in directories or []:
            base = Path(folder).resolve()
            if not base.is_dir():
                raise ValueError(f'Schema directory does not exist: {base}')
            files = sorted(base.glob('*/msg/*.msg'))
            if len(files) > MAX_MESSAGES:
                raise ValueError('Too many schema files in directory')
            for filepath in files:
                pkg = filepath.parent.parent.name
                key = f'{pkg}/{filepath.stem}'
                if len(key) > 150 or key in self.definitions:
                    raise ValueError(f'Duplicate or invalid schema type: {key}')
                if filepath.stat().st_size > MAX_SCHEMA_BYTES:
                    raise ValueError(f'Message schema too large: {filepath}')
                self.definitions[key] = parse_msg(filepath.read_text(encoding='utf-8'), pkg)

    def decode(self, typename: str, payload: bytes) -> dict:
        decoder = CDR(payload)
        return self._message(canonical_type(typename), decoder, 0, ())

    def _message(self, msgtype: str, cdr: CDR, depth: int, ancestors: tuple) -> dict:
        if depth >= MAX_DEPTH or msgtype in ancestors:
            raise ValueError(f'Recursive or deeply nested ROS message: {msgtype}')
        if msgtype not in self.definitions:
            raise ValueError(f'Missing .msg definition for {msgtype}')
        result = {}
        for base, name, array in self.definitions[msgtype]:
            def item():
                if base in PRIMITIVES:
                    fmt, alignment = PRIMITIVES[base]
                    val = cdr.read(fmt, alignment)
                    return bool(val) if base == 'bool' else val
                if base.startswith('string'):
                    return cdr.string()
                return self._message(base, cdr, depth + 1, ancestors + (msgtype,))
            if array is None:
                result[name] = item()
            else:
                kind, limit = array
                length = cdr.read('I', 4) if kind == 'sequence' else limit
                if length > limit:
                    raise ValueError('CDR array count exceeds schema/safety bound')
                result[name] = [item() for _ in range(length)]
        return result


def get_path(message: dict, path: str):
    if not isinstance(path, str) or not PATH_RE.fullmatch(path):
        raise ValueError(f'Invalid custom field path: {path!r}')
    val = message
    for piece in path.split('.'):
        if not isinstance(val, dict) or piece not in val:
            raise ValueError(f'Field path {path!r} not present in decoded ROS message')
        val = val[piece]
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        raise ValueError(f'Custom field {path!r} is not a finite scalar number')
    return float(val)


def validate_custom_roles(mapping: dict, registry: SchemaRegistry) -> dict:
    if not isinstance(mapping, dict):
        raise ValueError('custom_messages must be a JSON object')
    roles = {}
    for typename, props in mapping.items():
        if not isinstance(typename, str) or not NAME_RE.fullmatch(typename):
            raise ValueError(f'Invalid custom ROS message type: {typename!r}')
        key = canonical_type(typename)
        if key not in registry.definitions:
            raise ValueError(f'{typename}: .msg definition missing from schema_dirs')
        if not isinstance(props, dict) or props.get('role') not in ('command', 'odometry'):
            raise ValueError(f'{typename}: role must be command or odometry')
        if set(props) - {'role', 'linear_x', 'angular_z', 'position_x', 'position_y', 'position_z'}:
            raise ValueError(f'{typename}: unknown mapping keys')
        if 'linear_x' not in props:
            raise ValueError(f'{typename}: required linear_x mapping missing')
        for field_name, path in props.items():
            if field_name != 'role' and (not isinstance(path, str) or not PATH_RE.fullmatch(path)):
                raise ValueError(f'{typename}: invalid path {field_name}={path!r}')
        roles[key] = props
    return roles


def as_telemetry(data: dict, mapping: dict) -> dict:
    lin = get_path(data, mapping['linear_x'])
    angular = get_path(data, mapping['angular_z']) if 'angular_z' in mapping else 0.0
    base = {'linear': (lin, 0., 0.), 'angular': (0., 0., angular)}
    if mapping['role'] == 'odometry':
        # Position is optional. Missing fields disable position-jump analysis, NOT
        # silently convert missing position to a fabricated (0,0,0) position.
        if 'position_x' in mapping and 'position_y' in mapping:
            base['position'] = (get_path(data,mapping['position_x']),
                                get_path(data,mapping['position_y']),
                                get_path(data,mapping['position_z']) if 'position_z' in mapping else 0.)
        else:
            base['position'] = None
        base['orientation'] = None
    return base
