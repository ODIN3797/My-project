"""Conservative topic-role matching based on ROS message type and human-readable names.

Matching a *type* establishes structural compatibility, not operational meaning.
Ambiguous candidates deliberately disable cross-topic fault correlation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re

ROLES = {'command': {'geometry_msgs/Twist', 'geometry_msgs/TwistStamped'},
         'odometry': {'nav_msgs/Odometry'}}


def canonical_type(t: str) -> str:
    return t.replace('/msg/', '/')


def role_score(role: str, topic: str) -> int:
    name = re.sub(r'([a-z])([A-Z])', r'\1_\2', topic).lower()
    normalized = re.sub(r'[^a-z0-9]+', '_', name).strip('_')
    tokens = normalized.split('_')
    if role == 'command':
        if 'cmd_vel' in normalized or 'vel_cmd' in normalized: return 20
        if 'velocity_cmd' in normalized or 'cmd_velocity' in normalized: return 20
        if 'twist_cmd' in normalized or 'cmd_twist' in normalized: return 18
        if ('cmd' in tokens or 'command' in tokens) and ('velocity' in tokens or 'vel' in tokens or 'twist' in tokens): return 16
        if 'command' in tokens or 'cmd' in tokens: return 7
        return 0
    if role == 'odometry':
        if 'odom' in tokens or 'odometry' in tokens: return 20
        if 'odom' in normalized: return 14
        return 0
    return 0


def robot_namespace(topic: str) -> str:
    parts = topic.strip('/').split('/')
    if not parts: return ''
    # Only explicit robot-like prefixes are used as identity evidence.
    p = parts[0].lower()
    if re.fullmatch(r'(robot[-_]?\w+|amr[-_]?\w+|agv[-_]?\w+|r\d+)',p):
        return p
    if p == 'robots' and len(parts) > 1:
        return 'robots/' + parts[1].lower()
    return ''


@dataclass
class Discovery:
    selected: dict[str, str] = field(default_factory=dict)
    candidates: dict[str, list[dict]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return {'selected': self.selected, 'candidates': self.candidates, 'warnings': self.warnings}


def discover(topics: dict[str, str], overrides: dict[str, str] | None = None,
             custom_roles: dict | None = None) -> Discovery:
    overrides = overrides or {}
    unknown = set(overrides) - set(ROLES)
    if unknown: raise ValueError(f'Unsupported topic-map roles: {sorted(unknown)}')
    result = Discovery()
    custom_roles = custom_roles or {}
    for role, standard in ROLES.items():
        accepted = standard | {t for t, mapping in custom_roles.items() if mapping['role'] == role}
        options = sorted([{'topic': t, 'message_type': ty, 'name_score': role_score(role,t)}
                          for t,ty in topics.items() if canonical_type(ty) in accepted],
                         key=lambda x:(-x['name_score'],x['topic']))
        result.candidates[role] = options
        if role in overrides:
            name=overrides[role]
            if name not in topics:
                result.warnings.append(f'Manual mapping {role}={name!r} not in bag; role not analyzed')
            elif canonical_type(topics[name]) not in accepted:
                result.warnings.append(f'Manual mapping {role}={name!r} has incompatible type {topics[name]}; role not analyzed')
            else:
                result.selected[role] = name
            continue
        if len(options) == 1:
            result.selected[role] = options[0]['topic']
            if options[0]['name_score'] == 0:
                result.warnings.append(f'{role}: selected sole type-compatible stream {options[0]["topic"]}; validate its semantic role')
        elif len(options) > 1:
            first,second=options[:2]
            if first['name_score'] >= 14 and first['name_score']-second['name_score'] >= 8:
                result.selected[role]=first['topic']
                result.warnings.append(f'{role}: selected likely stream {first["topic"]}; others: {len(options)-1}. Verify mapping.')
            else:
                result.warnings.append(f'{role}: ambiguous ({len(options)} type-compatible topics): '
                                       +', '.join(o['topic'] for o in options[:8])+'; provide --config with topics mapping')
        else:
            result.warnings.append(f'{role}: no compatible standard ROS2 topic found')
    cmd,odo=result.selected.get('command'),result.selected.get('odometry')
    if cmd and odo:
        cmd_ns,odom_ns=robot_namespace(cmd),robot_namespace(odo)
        if cmd_ns!=odom_ns:
            # Distinct named robots are never joined, even with manual overrides.
            # A named robot and global topic may legitimately belong together,
            # but require an explicit confirmation of both role mappings.
            if cmd_ns and odom_ns or not ('command' in overrides and 'odometry' in overrides):
                result.warnings.append(f'Command and odom namespaces differ ({cmd_ns or "global"} vs {odom_ns or "global"}); cross-topic comparison disabled. ' +
                                       'If the global stream really belongs to this robot, explicitly map both roles.')
                result.selected.pop('command',None)
                result.selected.pop('odometry',None)
            else:
                result.warnings.append('Explicitly mapped a named robot command and global odometry stream; verify robot identity before interpreting results')
    return result
