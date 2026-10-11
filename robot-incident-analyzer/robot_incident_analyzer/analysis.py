from __future__ import annotations
from collections import Counter, defaultdict
from .models import Event, Finding


def same_robot_or_source(a: Event, b: Event) -> bool:
    # Unknown identities are never cross-correlated between input files.
    if a.robot_id == 'unknown' or b.robot_id == 'unknown':
        return a.robot_id == b.robot_id == 'unknown' and a.source == b.source
    return a.robot_id == b.robot_id


def build_findings(events: list[Event]) -> list[Finding]:
    findings: list[Finding] = []

    # Incidents are linked by proximity; proximity is not proof of causation.
    for event in events:
        if event.code == 'NAVIGATION' and event.severity in ('ERROR','FATAL'):
            earlier = [e for e in events if same_robot_or_source(e,event) and
                       event.timestamp-30 <= e.timestamp <= event.timestamp and
                       e.code in ('COMMUNICATION','TIMEOUT','TOPIC_GAP') and e.event_id != event.event_id]
            if earlier:
                evidence = earlier[-2:] + [event]
                findings.append(Finding(
                    code='NAV_WITH_PRECEDING_SIGNAL', title='Navigation failure follows another anomaly',
                    severity='HIGH', explanation='Navigation error was recorded within 30 seconds of '
                    'a communication / timeout / sensor-gap event. The earlier event may be related; '
                    'timestamp correlation alone does not prove causality.',
                    suggested_checks=['Compare node clocks, ROS logs and controller state.',
                                      'Inspect connectivity and sensor streams before the navigation failure.'],
                    evidence_ids=[e.event_id for e in evidence]))

        if event.code == 'CHARGING' and event.severity in ('ERROR', 'FATAL'):
            earlier = [e for e in events if same_robot_or_source(e,event) and
                       event.timestamp - 120 <= e.timestamp <= event.timestamp and
                       ('dock' in e.message.lower() and 'success' in e.message.lower())]
            if earlier:
                findings.append(Finding(
                    code='DOCK_OK_CHARGE_FAILED', title='Charging issue after successful docking',
                    severity='HIGH', explanation='A charging error occurred after a docking-success log. '
                    'Physical alignment and charging contact are not independently verified.',
                    suggested_checks=['Compare charger status and battery current around the event.',
                                      'Inspect contact alignment and charging handshake state.'],
                    evidence_ids=[earlier[-1].event_id, event.event_id]))

    groups: dict[tuple[str,str], list[Event]] = defaultdict(list)
    for event in events:
        if event.severity in ('WARN', 'ERROR', 'FATAL'):
            groups[(event.robot_id if event.robot_id != 'unknown' else 'source:' + event.source, event.code)].append(event)

    for (robot_id, code), grouped in groups.items():
        if len(grouped) >= 3 and grouped[-1].timestamp - grouped[0].timestamp <= 600:
            findings.append(Finding(
                code='RECURRING_ALERT', title=f'Repeated {code} alerts', severity='MEDIUM',
                explanation=f'{len(grouped)} alerts of type {code} appeared for {robot_id} within 10 minutes.',
                suggested_checks=['Compare the first event and subsequent recovery attempts.'],
                evidence_ids=[e.event_id for e in grouped[:6]]))

    telemetry_checks = {
        'CMD_ODOM_MISMATCH': ('Commanded velocity diverges from odometry',
                              'A sustained velocity command was followed by near-zero odometry velocity. Check timestamps and motion enable state.',
                              ['Check safety stop / motor enable status.', 'Compare /cmd_vel and /odom timestamps and velocity units.']),
        'ODOM_POSITION_JUMP': ('Odometry position discontinuity',
                               'A large position change was observed between consecutive odometry samples.',
                               ['Check odom frame resets and wheel encoder jumps.', 'Compare localization and robot ground truth.']),
        'TF_MAP_ODOM_JUMP': ('map to odom transform discontinuity',
                            'A sudden translation jump was observed in the map → odom transform.',
                            ['Check localization resets and relocalization events.', 'Verify frame tree and map switching history.']),
        'TF_INVALID_QUATERNION': ('Invalid TF rotation',
                                  'A published TF rotation quaternion is not approximately unit length.',
                                  ['Inspect TF publisher math and initialization state.']),
        'ODOM_INVALID_QUATERNION': ('Invalid odometry rotation',
                                    'A published odometry quaternion is invalid or not normalized.',
                                    ['Inspect odometry publisher and quaternion normalization.']),
        'TF_FRAME_INVALID': ('Invalid TF frame identifiers',
                             'A TF transform contains missing or identical parent and child frames.',
                             ['Check TF publisher frame IDs and namespace prefixes.']),
        'DIAGNOSTIC_ERROR': ('Hardware or software diagnostic ERROR',
                             'At least one ROS diagnostic status reported an ERROR.',
                             ['Inspect diagnostic hardware ID and nearby /rosout events.', 'Check whether the status later recovered.']),
        'DIAGNOSTIC_STALE': ('Stale diagnostics reported',
                             'A diagnostic status was marked STALE.',
                             ['Verify monitoring frequency and publisher connectivity.']),
    }
    for code, (title, explanation, checks) in telemetry_checks.items():
        matching = [e for e in events if e.code == code]
        if matching:
            findings.append(Finding(code=code, title=title, severity='HIGH' if code in (
                'DIAGNOSTIC_ERROR','TF_INVALID_QUATERNION','ODOM_INVALID_QUATERNION') else 'MEDIUM',
                explanation=explanation + f' ({len(matching)} observation(s) in the selected recordings.)',
                suggested_checks=checks, evidence_ids=[e.event_id for e in matching[:6]],
                confidence='direct observed signal / root cause not verified'))

    # Context windows around representative critical observations. Related events are
    # temporal evidence only; they must not be interpreted as causal dependencies.
    focus_codes={'CMD_ODOM_MISMATCH','TF_MAP_ODOM_JUMP','ODOM_POSITION_JUMP',
                 'DIAGNOSTIC_ERROR','TOPIC_GAP'}
    seen=set()
    for focal in sorted(events,key=lambda e:e.timestamp):
        if focal.code not in focus_codes: continue
        grouping=(focal.source,focal.code)
        if grouping in seen: continue
        seen.add(grouping)
        nearby=[e for e in events if e.event_id!=focal.event_id and
                same_robot_or_source(e,focal) and
                -10 <= e.timestamp-focal.timestamp <= 10]
        nearby.sort(key=lambda e:abs(e.timestamp-focal.timestamp))
        if nearby:
            evidence=[focal]+nearby[:5]
            before=sum(e.timestamp<focal.timestamp for e in nearby[:5])
            after=sum(e.timestamp>focal.timestamp for e in nearby[:5])
            findings.append(Finding(
                code='INCIDENT_CONTEXT',title=f'Nearby events around {focal.code}',severity='MEDIUM',
                explanation=f'Found {before} preceding and {after} subsequent event(s) in a ±10 s recording-time window. '
                            'These are contextual observations, not proof of a common root cause.',
                suggested_checks=['Compare clocks and affected robot/frame identities.',
                                  'Inspect related events before drawing conclusions.'],
                evidence_ids=[e.event_id for e in evidence],confidence='timestamp proximity only'))

    # Keep key errors visible even without multi-signal correlations.
    common = Counter(e.code for e in events if e.severity in ('ERROR','FATAL'))
    for code, count in common.most_common(6):
        evidence = [e for e in events if e.code == code and e.severity in ('ERROR','FATAL')]
        findings.append(Finding(
            code='OBSERVED_ERROR', title=f'Observed error: {code} ({count})', severity='MEDIUM',
            explanation='Recorded error event. The text is evidence of an error, not a confirmed root cause.',
            suggested_checks=['Inspect the referenced log records and related telemetry.'],
            evidence_ids=[e.event_id for e in evidence[:5]], confidence='observed event / cause unconfirmed'))

    if not findings:
        findings.append(Finding(code='NO_CORRELATED_INCIDENT', title='No matching incident rule',
                                severity='INFO', explanation='No configured incident rule matched the analyzed data. '
                                'This does not establish that the robot was healthy.',
                                suggested_checks=['Review topic coverage and recording completeness.'],
                                evidence_ids=[], confidence='limited coverage'))
    order = {'HIGH': 0, 'MEDIUM': 1, 'INFO': 2}
    findings.sort(key=lambda x: order.get(x.severity, 3))
    return findings
