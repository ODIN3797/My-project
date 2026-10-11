"""Explicitly reviewed rate-episode evaluation; never infer ground truth from filename.

The reviewer controls the positive and negative *coverage*. An unreviewed period
is not evidence that no incident occurred. All timestamps are ROS bag UTC nanoseconds.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

NANO = 1_000_000_000
_ALLOWED_KEYS = {'schema_version', 'recording_sha256', 'topic', 'message_type',
                 'reviewer', 'ground_truth_status', 'positive_intervals',
                 'negative_intervals', 'review_notes'}


def _interval(item: dict, name: str) -> tuple[int, int]:
    if not isinstance(item, dict) or not isinstance(item.get('start_ns'), int) or isinstance(item.get('start_ns'), bool) or not isinstance(item.get('end_ns'), int) or isinstance(item.get('end_ns'), bool):
        raise ValueError(f'{name}: start_ns and end_ns must be integer Unix nanoseconds')
    start, end = item['start_ns'], item['end_ns']
    if start < 0 or end <= start:
        raise ValueError(f'{name}: interval must have positive duration and nonnegative timestamps')
    return start, end


def _nonoverlap(intervals: list[tuple[int, int]], label: str):
    ordered = sorted(intervals)
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError(f'{label}: overlapping annotations are not allowed')


def make_template(report: dict, topic: str) -> dict:
    candidate = next((t for t in report.get('topics', []) if t.get('topic') == topic), None)
    if candidate is None:
        raise ValueError('Exact topic was not included in rate inspection')
    origin = candidate.get('window_origin_ns')
    counts = candidate.get('count_by_second')
    if origin is None or not isinstance(counts, list) or len(counts) < 3:
        raise ValueError('Topic has no reviewed-capable complete timestamp coverage')
    return {
        'schema_version': '1.0',
        'recording_sha256': report['recording']['sha256'],
        'topic': topic, 'message_type': candidate['type'],
        'reviewer': '', 'ground_truth_status': 'unreviewed',
        'positive_intervals': [], 'negative_intervals': [],
        'review_notes': ('Template only: label exact start_ns/end_ns in Unix nanoseconds. '
                         'Set ground_truth_status to reviewed ONLY after independent review; '
                         'positives and explicitly checked negative intervals must not overlap. '
                         'Unreviewed intervals are ignored, not counted as negatives.')
    }


def evaluate_labels(report: dict, labels: dict) -> dict:
    if not isinstance(labels, dict) or set(labels) - _ALLOWED_KEYS:
        raise ValueError('Annotation must be a JSON object containing only allowed keys')
    if labels.get('schema_version') != '1.0':
        raise ValueError('Unsupported annotation schema_version')
    recorded = report.get('recording', {})
    if not isinstance(recorded.get('sha256'), str) or len(recorded['sha256']) != 64 or recorded['sha256'].lower() != str(labels.get('recording_sha256', '')).lower():
        raise ValueError('Annotation SHA-256 must exactly match the inspected recording')
    if labels.get('ground_truth_status') != 'reviewed' or not isinstance(labels.get('reviewer'), str) or not labels['reviewer'].strip():
        raise ValueError('Metrics require explicit reviewed status and a reviewer identifier')
    selected = [t for t in report.get('topics', []) if t.get('topic') == labels.get('topic') and t.get('type') == labels.get('message_type')]
    if len(selected) != 1:
        raise ValueError('Annotation topic/type must match exactly one inspected topic')
    topic = selected[0]
    if topic.get('status') not in ('RATE_EPISODES_FOUND', 'NO_CONFIRMED_EPISODES'):
        raise ValueError('Topic rate coverage is incomplete or ineligible for scoring')
    origin, counts = topic.get('window_origin_ns'), topic.get('count_by_second')
    if not isinstance(origin, int) or not isinstance(counts, list) or len(counts) < 3:
        raise ValueError('No complete timestamp coverage to evaluate')
    first = origin + int(topic.get('first_complete_bin_index', 1)) * NANO
    end = origin + (len(counts)-1) * NANO
    positives = labels.get('positive_intervals', [])
    negatives = labels.get('negative_intervals', [])
    if not isinstance(positives, list) or not isinstance(negatives, list):
        raise ValueError('Annotation intervals must be lists')
    if len(positives) + len(negatives) > 10000:
        raise ValueError('Too many annotation intervals')
    pos = [_interval(x, f'positive[{i}]') for i, x in enumerate(positives)]
    neg = [_interval(x, f'negative[{i}]') for i, x in enumerate(negatives)]
    _nonoverlap(pos, 'positive'); _nonoverlap(neg, 'negative')
    for label, entries in [('positive', pos), ('negative', neg)]:
        for a, b in entries:
            if a < first or b > end:
                raise ValueError(f'{label} interval outside complete recorded histogram coverage [{first},{end})')
    if any(a < d and c < b for a, b in pos for c, d in neg):
        raise ValueError('Reviewed negative intervals must not overlap positives')
    if not pos and not neg:
        raise ValueError('No reviewed positive or negative intervals: no evaluable coverage')
    predictions = [_interval(x, f'prediction[{i}]') for i, x in enumerate(topic.get('episodes', []))]
    # One-to-one matching with maximum cardinality: a single prediction cannot detect
    # several labelled incidents, and duplicated predictions cannot inflate recall.
    adj = [[j for j, (c, d) in enumerate(predictions) if a < d and c < b]
           for a, b in pos]
    pairs = {}  # prediction index -> positive index
    def augment(i: int, visited: set[int]) -> bool:
        for j in sorted(adj[i], key=lambda j: abs(predictions[j][0]-pos[i][0])):
            if j in visited:
                continue
            visited.add(j)
            if j not in pairs or augment(pairs[j], visited):
                pairs[j] = i
                return True
        return False
    for i in range(len(pos)):
        augment(i, set())
    matched_labels = {i: j for j, i in pairs.items()}
    matches = []
    for i, (a, b) in enumerate(pos):
        j = matched_labels.get(i)
        observed = predictions[j][0] if j is not None else None
        matches.append({'positive_index': i, 'label_start_ns': a, 'label_end_ns': b,
                        'found': j is not None,
                        'prediction_start_ns': observed,
                        'onset_difference_s': round((observed-a)/NANO, 3) if observed is not None else None,
                        'detection_delay_s': round(max(0, observed-a)/NANO, 3) if observed is not None else None})
    false_alarms = []
    unreviewed_predictions = []
    for j, (a, b) in enumerate(predictions):
        if j in pairs:
            continue
        # An unmatched prediction touching an annotated positive could be a
        # duplicate rather than a false positive. Do not invent a negative label.
        if any(a < d and c < b for c, d in pos):
            unreviewed_predictions.append(j)
        elif any(c <= a and b <= d for c, d in neg):
            false_alarms.append(j)
        else:
            unreviewed_predictions.append(j)
    negative_s = sum((b-a)/NANO for a, b in neg)
    matched = len(pairs)
    delays = [m['detection_delay_s'] for m in matches if m['found']]
    output = {
        'schema_version': '1.0', 'evaluation_kind': 'human-reviewed-intervals',
        'recording_sha256': recorded['sha256'], 'topic': labels['topic'],
        'message_type': labels['message_type'], 'reviewer': labels['reviewer'].strip(),
        'reference_status': 'operator-declared reviewed, not independently audited',
        'positive_count': len(pos), 'detected_positives': matched,
        'missed_positives': len(pos)-matched,
        'positive_recall': round(matched/len(pos), 4) if pos else None,
        'negative_reviewed_seconds': round(negative_s, 6),
        'false_alarm_count': len(false_alarms),
        'false_alarms_per_hour': round(len(false_alarms)*3600/negative_s, 5) if negative_s else None,
        'detection_delay_median_seconds': sorted(delays)[len(delays)//2] if len(delays)%2 else round((sorted(delays)[len(delays)//2-1]+sorted(delays)[len(delays)//2])/2, 3) if delays else None,
        'unscored_prediction_count': len(unreviewed_predictions),
        'matched_positive_details': matches,
        'false_alarm_prediction_indices': false_alarms,
        'unscored_prediction_indices': unreviewed_predictions,
        'notes': [
            'No precision claim: incidents outside annotated positive/negative coverage are unknown, not false positives.',
            'A predicted episode is counted as false alarm only when fully contained in an explicitly reviewed negative interval.',
            'Detection is time-overlap with a labelled interval, not confirmed root-cause classification.',
            'Median delay is computed from time-binned episode start; onset is manually annotated and not ground-truth verified by software.',
            'Review coverage is per exact topic and message type; results do not measure all robot faults.'
        ]
    }
    return output


def render_html(result: dict) -> str:
    rows = ''.join('<tr><td>'+str(x['positive_index']+1)+'</td><td>'+ ('Matched' if x['found'] else 'Missed') +'</td><td>'+str(x['label_start_ns'])+'</td><td>'+ ('—' if x['onset_difference_s'] is None else str(x['onset_difference_s'])) +'</td></tr>' for x in result['matched_positive_details'])
    val=lambda x: 'Not measured' if x is None else str(x)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rate episode evaluation</title><style>:root{{font:16px system-ui;color:#e5eef7;background:#0a1422}}body{{max-width:920px;margin:auto;padding:28px 22px;line-height:1.55}}h1{{font-size:30px}}header{{margin-bottom:28px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}.box,article{{background:#172537;border:1px solid #32465d;border-radius:12px;padding:18px}}.box strong{{display:block;font-size:25px;color:#68dbd2}}.muted{{color:#afc0d0}}table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #41556a;text-align:left;padding:10px}}.scroll{{overflow:auto}}code{{overflow-wrap:anywhere}}</style></head><body><header><p class="muted">Robot Incident Analyzer · evidence evaluation</p><h1>Human-reviewed rate episode evaluation</h1><p class="muted">Topic: <code>{escape(result['topic'])}</code> · Reviewer: {escape(result['reviewer'])}. Labels are operator declared, not independently audited.</p></header><div class="grid"><div class="box">Labelled positives<strong>{result['positive_count']}</strong></div><div class="box">Labelled recall<strong>{val(result['positive_recall'])}</strong></div><div class="box">False alarms / reviewed hour<strong>{val(result['false_alarms_per_hour'])}</strong></div><div class="box">Median detection delay (s)<strong>{val(result['detection_delay_median_seconds'])}</strong></div></div><article><h2>Labelled intervals</h2><div class="scroll"><table><thead><tr><th>#</th><th>Result</th><th>True onset (ns)</th><th>Detection difference (s)</th></tr></thead><tbody>{rows}</tbody></table></div></article><article><h2>Coverage disclaimer</h2><p class="muted">Reviewed negative coverage: {result['negative_reviewed_seconds']:.1f} seconds. False alarm count: {result['false_alarm_count']}. Unscored predictions: {result['unscored_prediction_count']}. Non-reviewed areas do NOT count as normal. This is not diagnostic precision, robot failure accuracy, proof of attack, or independent ground truth.</p></article></body></html>'''


def write_evaluation(rates_json: Path, annotations_json: Path, output: Path) -> dict:
    rates = json.loads(Path(rates_json).read_text(encoding='utf-8'))
    labels = json.loads(Path(annotations_json).read_text(encoding='utf-8'))
    result = evaluate_labels(rates, labels)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    (output/'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (output/'evaluation.html').write_text(render_html(result), encoding='utf-8')
    return result


def write_template(rates_json: Path, topic: str, output: Path) -> dict:
    rates = json.loads(Path(rates_json).read_text(encoding='utf-8'))
    template = make_template(rates, topic)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding='utf-8')
    from .review_ui import render_review_ui
    Path(output).with_suffix('.html').write_text(render_review_ui(rates, template), encoding='utf-8')
    return template
