"""Core dataclasses for LaufKern manifests, reachability, and tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

from bw_gui.contracts.keybinding import KeyBindingDefinition


@dataclass(frozen=True)
class LaufKernRoute:
    """One keyboard-capable route that can reach one intent."""

    route_id: str
    intent: str
    route_type: str
    modes: tuple[str, ...] = ()
    binding_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LaufKernManifest:
    """Declarative per-program manifest consumed by LaufKern."""

    manifest_id: str
    repo_name: str
    intents: tuple[str, ...]
    keybindings: tuple[KeyBindingDefinition, ...]
    routes: tuple[LaufKernRoute, ...]
    exclusions: dict[str, str] = field(default_factory=dict)
    equivalence: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReachabilityResult:
    """Reachability verdict for one intent and runtime context."""

    intent: str
    reachable: bool
    reason_code: str | None = None
    route_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrackingArtifact:
    """One machine-readable tracking artifact emitted by a verifier run."""

    run_id: str
    repo_name: str
    step_id: str
    phase: str
    state: str
    timestamp: str
    sequence: int
    mandatory: bool
    producer: str
    checksum: str
    reason_code: str | None = None
    evidence_ref: str | None = None

    def checksum_payload(self) -> dict[str, object]:
        """Return checksum payload with stable key order semantics."""

        return {
            "run_id": self.run_id,
            "repo_name": self.repo_name,
            "step_id": self.step_id,
            "phase": self.phase,
            "state": self.state,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "mandatory": self.mandatory,
            "producer": self.producer,
            "reason_code": self.reason_code,
            "evidence_ref": self.evidence_ref,
        }

    @staticmethod
    def build_checksum(payload: dict[str, object]) -> str:
        """Build deterministic checksum from one payload."""

        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def has_valid_checksum(self) -> bool:
        """Validate checksum integrity for this artifact."""

        return self.checksum == self.build_checksum(self.checksum_payload())


@dataclass(frozen=True)
class CompletionSummary:
    """Completion aggregate across emitted artifacts."""

    status: str
    total_steps: int
    completed_steps: int
    mandatory_steps: int
    blockers: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
