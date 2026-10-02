"""Load and validate a Person 3 dataset / policy corpus (Data Contract v1 §2–§3).

Validation failures raise IngestError with every problem found, so a bad delivery is fixed in one round.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from episight.contracts.data import (
    FORBIDDEN_FIELD_PREFIXES,
    FORBIDDEN_FIELDS,
    Claim,
    ClinicalNote,
    DatasetManifest,
    Episode,
    Patient,
    PolicyManifest,
    PolicySection,
    Provider,
)

M = TypeVar("M", bound=BaseModel)

# Architecture §10: evaluation labels are never ingested into application storage.
_BLOCKED_DIR_NAMES = {"ground-truth", "ground_truth", "groundtruth"}


class IngestError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__(f"{len(problems)} ingest problem(s):\n  " + "\n  ".join(problems))
        self.problems = problems


@dataclass
class Dataset:
    manifest: DatasetManifest
    patients: list[Patient]
    providers: list[Provider]
    episodes: list[Episode]
    claims: list[Claim]
    notes: list[ClinicalNote]
    issues: list[str] = field(default_factory=list)


@dataclass
class PolicyCorpus:
    manifest: PolicyManifest
    sections: list[PolicySection]


def _guard_path(path: Path) -> Path:
    resolved = path.resolve()
    if any(part.lower() in _BLOCKED_DIR_NAMES for part in resolved.parts):
        raise IngestError([f"refusing to ingest from a ground-truth location: {resolved}"])
    if not resolved.is_dir():
        raise IngestError([f"not a directory: {resolved}"])
    return resolved


def _read_jsonl(path: Path, model: type[M], problems: list[str], id_field: str) -> list[M]:
    if not path.exists():
        problems.append(f"{path.name}: file missing")
        return []
    rows: dict[str, M] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        where = f"{path.name}:{lineno}"
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            problems.append(f"{where}: invalid JSON ({exc.msg})")
            continue
        forbidden = [k for k in obj if k in FORBIDDEN_FIELDS or k.startswith(FORBIDDEN_FIELD_PREFIXES)]
        if forbidden:
            problems.append(f"{where}: forbidden label-like field(s) {forbidden}")
            continue
        try:
            item = model.model_validate(obj)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"]) or "(row)"
                problems.append(f"{where}: {loc}: {err['msg']}")
            continue
        key = getattr(item, id_field)
        if key in rows:
            if rows[key] != item:
                problems.append(f"{where}: duplicate {id_field} {key} with different content")
            continue
        rows[key] = item
    return list(rows.values())


def load_dataset(path: Path) -> Dataset:
    root = _guard_path(path)
    problems: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise IngestError([f"{manifest_path}: manifest missing"])
    try:
        manifest = DatasetManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise IngestError([f"manifest.json: {e['loc']}: {e['msg']}" for e in exc.errors()]) from exc

    patients = _read_jsonl(root / "patients.jsonl", Patient, problems, "patient_id")
    providers = _read_jsonl(root / "providers.jsonl", Provider, problems, "provider_id")
    episodes = _read_jsonl(root / "episodes.jsonl", Episode, problems, "episode_id")
    claims = _read_jsonl(root / "claims.jsonl", Claim, problems, "claim_id")
    notes = _read_jsonl(root / "clinical_notes.jsonl", ClinicalNote, problems, "note_id")

    patient_ids = {p.patient_id for p in patients}
    provider_ids = {p.provider_id for p in providers}
    episode_ids = {e.episode_id for e in episodes}
    for e in episodes:
        if e.patient_id not in patient_ids:
            problems.append(f"episodes: {e.episode_id}: unknown patient_id {e.patient_id}")
        if e.provider_id not in provider_ids:
            problems.append(f"episodes: {e.episode_id}: unknown provider_id {e.provider_id}")
        if e.start_at and e.end_at and e.end_at < e.start_at:
            problems.append(f"episodes: {e.episode_id}: end_at before start_at")
    claimed: set[str] = set()
    for c in claims:
        if c.episode_id not in episode_ids:
            problems.append(f"claims: {c.claim_id}: unknown episode_id {c.episode_id}")
        if c.episode_id in claimed:
            problems.append(f"claims: {c.claim_id}: second claim for episode {c.episode_id} (1:1 in v1)")
        claimed.add(c.episode_id)
    for n in notes:
        if n.episode_id not in episode_ids:
            problems.append(f"clinical_notes: {n.note_id}: unknown episode_id {n.episode_id}")

    if problems:
        raise IngestError(problems)
    return Dataset(manifest, patients, providers, episodes, claims, notes)


def load_policies(path: Path) -> PolicyCorpus:
    root = _guard_path(path)
    problems: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise IngestError([f"{manifest_path}: manifest missing"])
    try:
        manifest = PolicyManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise IngestError([f"manifest.json: {e['loc']}: {e['msg']}" for e in exc.errors()]) from exc
    sections = _read_jsonl(root / "policy_sections.jsonl", PolicySection, problems, "policy_id")
    if problems:
        raise IngestError(problems)
    return PolicyCorpus(manifest, sections)
