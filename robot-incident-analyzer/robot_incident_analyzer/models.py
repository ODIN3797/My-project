from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def utc_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


@dataclass
class Event:
    timestamp: float
    severity: str
    category: str
    code: str
    message: str
    robot_id: str = 'unknown'
    source: str = ''
    topic: str = ''
    event_id: str = ''

    def to_dict(self) -> dict:
        result = asdict(self)
        result['time_utc'] = utc_iso(self.timestamp)
        return result


@dataclass
class Finding:
    code: str
    title: str
    severity: str
    explanation: str
    suggested_checks: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: str = 'candidate / not confirmed'

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TopicStats:
    topic: str
    message_type: str
    count: int
    duration_s: float
    approx_hz: float
    median_gap_ms: float
    max_gap_ms: float

    def to_dict(self) -> dict:
        return asdict(self)
