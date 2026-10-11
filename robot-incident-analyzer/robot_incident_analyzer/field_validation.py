"""Offline reproducible acceptance test for external ROS2 recordings.

This is evidence about tool behavior, not proof of incident ground truth.
Data provenance is supplied by the operator and never inferred from file names.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .__main__ import analyze_files, load_config

ALLOWED_ORIGINS = {'unknown', 'physical', 'simulation', 'synthetic'}
CRITICAL_WARNING_TERMS = (
    'chunk skipped', 'chunk too large', 'only first', 'not inspected',
    'not supported', 'could not be decoded', 'failed schema/cdr decoding',
    'no decodable messages', 'ambiguous', 'no compatible',
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def load_labels(path: Path | None):
    if path is None:
        return []
    with path.open(encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        required = {'case_id', 'code', 'time_epoch', 'tolerance_s'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError('Labels CSV requires case_id,code,time_epoch,tolerance_s columns')
        labels = []
        for index, row in enumerate(reader, 2):
            if not row['case_id'].strip() or not row['code'].strip():
                raise ValueError(f'Labels row {index}: missing case_id or code')
            epoch = float(row['time_epoch']); tolerance = float(row['tolerance_s'])
            if not all(map(math.isfinite, [epoch, tolerance])) or tolerance < 0:
                raise ValueError(f'Labels row {index}: invalid timestamp/tolerance')
            labels.append({'case_id': row['case_id'].strip(), 'code': row['code'].strip(),
                           'time_epoch': epoch, 'tolerance_s': tolerance})
        return labels


def match_labels(events, labels):
    """One event per label, greedy closest unused match; ONLY labelled recall.

    Missing labels mean precision and false-positive rates CANNOT be established.
    """
    used = set(); matches = []
    for label in labels:
        candidates = [(abs(event.timestamp-label['time_epoch']), i, event)
                      for i, event in enumerate(events)
                      if i not in used and event.code == label['code'] and
                      abs(event.timestamp-label['time_epoch']) <= label['tolerance_s']]
        if candidates:
            _, i, event = min(candidates, key=lambda v: v[0]); used.add(i)
            matches.append({'label': label, 'found': True,
                            'matched_event_id': event.event_id, 'observed_time': event.timestamp})
        else:
            matches.append({'label': label, 'found': False, 'matched_event_id': None})
    return {'labelled_events': len(labels), 'detected_labelled_events': sum(x['found'] for x in matches),
            'labelled_recall': round(sum(x['found'] for x in matches)/len(labels), 4) if labels else None,
            'precision': None, 'false_positive_rate': None,
            'note': 'Labels may be non-exhaustive. Precision and false-positive rate are NOT calculated.',
            'matches': matches}


def analyze_field_cases(input_paths: list[Path], destination: Path, *, config_file=None,
                        labels_file=None, origin='unknown', max_messages=200000):
    if origin not in ALLOWED_ORIGINS:
        raise ValueError(f'--origin must be one of {", ".join(sorted(ALLOWED_ORIGINS))}')
    if not input_paths:
        raise ValueError('At least one input recording is required')
    if max_messages < 1:
        raise ValueError('max_messages must be positive')
    destination.mkdir(parents=True, exist_ok=True)
    labels = load_labels(labels_file)
    cases = []
    for i, path in enumerate(input_paths, 1):
        if not path.is_file() or path.suffix.lower() not in {'.mcap', '.db3', '.sqlite3'}:
            raise ValueError(f'Field validation accepts only an existing .mcap/.db3/.sqlite3 file: {path}')
        case_id = f'case_{i:02d}'
        output = destination/case_id
        started = time.perf_counter()
        events, findings, stats, warnings, files, details = analyze_files(
            [path], output, load_config(config_file), max_messages)
        elapsed = time.perf_counter()-started
        issues = []
        if not stats: issues.append('no_topics_read')
        if not events: issues.append('no_events_detected_not_equivalent_to_healthy')
        if any(any(term in w.lower() for term in CRITICAL_WARNING_TERMS) for w in warnings):
            issues.append('incomplete_or_ambiguous_analysis')
        if not any(d.get('discovery', {}).get('selected', {}).get('command') and
                   d.get('discovery', {}).get('selected', {}).get('odometry') for d in details):
            issues.append('no_unambiguous_command_odometry_pair')
        labelled = [x for x in labels if x['case_id'] in {case_id, path.name}]
        metrics = match_labels(events, labelled)
        cases.append({
            'id': case_id, 'input_name': path.name, 'bytes': path.stat().st_size,
            'sha256': digest(path), 'provenance': origin,
            'elapsed_s': round(elapsed, 3), 'event_count': len(events),
            'finding_count': len(findings), 'topic_count': len(stats),
            'message_count': sum(s.count for s in stats),
            'event_codes': dict(Counter(e.code for e in events)),
            'topic_types': [{'topic': s.topic, 'type': s.message_type, 'count':s.count} for s in stats],
            'warnings': warnings, 'review_flags': issues,
            'status': 'REVIEW_REQUIRED' if issues else 'READY_FOR_HUMAN_REVIEW',
            'topic_mappings': [d.get('discovery', {}).get('selected', {}) for d in details],
            'label_metrics': metrics,
            'report_html': f'{case_id}/report.html',
            'report_json': f'{case_id}/report.json'
        })
    summary = {
        'tool': 'Robot Incident Analyzer offline field pilot', 'schema_version': '1.0',
        'recording_count': len(cases), 'origin_declared_by_operator': origin,
        'actual_engineer_review_completed': False,
        'ground_truth_validated': False,
        'cases': cases,
        'important': ('Successful parsing and rule triggers do NOT establish diagnostic accuracy. '
                      'Source origin is operator-declared, not independently verified. '
                      'Do not call synthetic or simulated logs field recordings.')
    }
    (destination/'field_results.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    rows = [
        '# ROS2 bag field-pilot results', '',
        f'- Source origin (operator declared): **{origin}**',
        f'- Recordings processed: **{len(cases)}**',
        '- Ground-truth diagnosis: **NOT verified**',
        '- Human engineers interviewed: **0** (this command does not run interviews)',
        '', '| Case | Size (MiB) | Topics | Messages | Events | Status |',
        '|---|---:|---:|---:|---:|---|'
    ]
    for case in cases:
        rows.append(f'| {case["id"]}: {case["input_name"]} | {case["bytes"]/1048576:.2f} | {case["topic_count"]} | {case["message_count"]} | {case["event_count"]} | {case["status"]} |')
    rows += ['', '## Limitations', '',
             '- `READY_FOR_HUMAN_REVIEW` means no configured coverage flag fired; it does NOT imply correct diagnosis.',
             '- Zero detected incidents must NOT be interpreted as a healthy robot.',
             '- The rule-based detector cannot prove causation, calibrated precision, or recall without independent reference labels.',
             '- Selected or ambiguous topic mappings and all warnings must be reviewed by a ROS2 engineer.',
             '- No bag data leaves this machine; HTML/JSON reports may contain private log messages: do not share raw reports without reviewing them.',
             '- See `field_results.json` for file hashes, flags, and any annotated-event recall.', '']
    (destination/'FIELD_RESULTS.md').write_text('\n'.join(rows), encoding='utf-8')
    return summary
