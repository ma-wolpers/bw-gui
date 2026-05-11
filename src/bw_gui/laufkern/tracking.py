"""Tracking and completion aggregation primitives for LaufKern."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
import re

from .models import CompletionSummary, TrackingArtifact
from .reason_codes import (
    LK_TRK_CHECKSUM_INVALID,
    LK_TRK_MISSING_MANDATORY,
    LK_TRK_PRODUCER_UNTRUSTED,
    LK_TRK_SEQUENCE_GAP,
    REASON_CODE_CATALOG,
)

_STEP_ID_RE = re.compile(r"^LK-([A-I])-([A-Z]{3})-(\d{3})$")
_AREA_CODES = frozenset({"ARC", "API", "MAN", "RTC", "RCH", "TRK", "MIG", "ROL", "GOV"})
_COMPLETED_STATES = frozenset({"done", "completed", "passed", "ok"})


def validate_step_id(step_id: str) -> bool:
    """Validate canonical step id format and supported area codes."""

    match = _STEP_ID_RE.match(step_id)
    if not match:
        return False
    area_code = match.group(2)
    return area_code in _AREA_CODES


def emit_tracking_artifact(
    *,
    run_id: str,
    repo_name: str,
    step_id: str,
    phase: str,
    state: str,
    sequence: int,
    mandatory: bool,
    producer: str,
    reason_code: str | None = None,
    evidence_ref: str | None = None,
    timestamp: str | None = None,
) -> TrackingArtifact:
    """Create one validated tracking artifact with deterministic checksum."""

    if not validate_step_id(step_id):
        raise ValueError(f"Invalid step_id: {step_id}")

    if reason_code is not None and reason_code not in REASON_CODE_CATALOG:
        raise ValueError(f"Unknown reason_code: {reason_code}")

    ts = timestamp or datetime.now(UTC).isoformat()
    payload = {
        "run_id": run_id,
        "repo_name": repo_name,
        "step_id": step_id,
        "phase": phase,
        "state": state,
        "timestamp": ts,
        "sequence": sequence,
        "mandatory": mandatory,
        "producer": producer,
        "reason_code": reason_code,
        "evidence_ref": evidence_ref,
    }
    checksum = TrackingArtifact.build_checksum(payload)
    return TrackingArtifact(checksum=checksum, **payload)


def aggregate_completion(
    artifacts: Sequence[TrackingArtifact] | Iterable[TrackingArtifact],
    *,
    mandatory_steps: set[str] | None = None,
    trusted_producers: set[str] | None = None,
) -> CompletionSummary:
    """Aggregate artifact stream into one completion summary."""

    values = tuple(artifacts)
    trusted = trusted_producers or {"laufkern"}

    errors: list[str] = []
    by_step_latest: dict[str, TrackingArtifact] = {}
    mandatory_candidates: set[str] = set(mandatory_steps or ())

    grouped_sequences: dict[tuple[str, str], list[int]] = defaultdict(list)

    for artifact in values:
        if not artifact.has_valid_checksum():
            errors.append(f"{LK_TRK_CHECKSUM_INVALID}:{artifact.step_id}")
        if artifact.producer not in trusted:
            errors.append(f"{LK_TRK_PRODUCER_UNTRUSTED}:{artifact.step_id}")
        grouped_sequences[(artifact.run_id, artifact.repo_name)].append(artifact.sequence)
        if artifact.mandatory:
            mandatory_candidates.add(artifact.step_id)

        previous = by_step_latest.get(artifact.step_id)
        if previous is None or artifact.sequence >= previous.sequence:
            by_step_latest[artifact.step_id] = artifact

    for key, seq_values in grouped_sequences.items():
        ordered = sorted(seq_values)
        for left, right in zip(ordered, ordered[1:]):
            if right != left + 1:
                errors.append(f"{LK_TRK_SEQUENCE_GAP}:{key[0]}:{key[1]}")
                break

    blockers: list[str] = []
    completed_steps = 0
    for step_id in sorted(mandatory_candidates):
        artifact = by_step_latest.get(step_id)
        if artifact is None:
            blockers.append(f"{LK_TRK_MISSING_MANDATORY}:{step_id}")
            continue
        if artifact.state not in _COMPLETED_STATES:
            blockers.append(f"{LK_TRK_MISSING_MANDATORY}:{step_id}")
            continue
        completed_steps += 1

    status = "complete"
    if blockers or errors:
        status = "non-complete"

    return CompletionSummary(
        status=status,
        total_steps=len(by_step_latest),
        completed_steps=completed_steps,
        mandatory_steps=len(mandatory_candidates),
        blockers=tuple(sorted(set(blockers))),
        errors=tuple(sorted(set(errors))),
    )
