"""Record/replay of planner calls (D-21): reproducible regression runs without calling a model."""

import json
from pathlib import Path
from typing import Any, Protocol


class ReplayMiss(Exception):
    """Replay mode found no recording for a request. Regression must fail loudly, never call a model silently."""


class RecordingStore(Protocol):
    def get(self, request_hash: str) -> dict[str, Any] | None: ...

    def put(
        self, request_hash: str, *, model: str, prompt_version: str, request: dict[str, Any], response: dict[str, Any]
    ) -> None: ...


class NullStore:
    def get(self, request_hash: str) -> dict[str, Any] | None:
        return None

    def put(self, request_hash: str, **_: Any) -> None:
        return None


class MemoryStore:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def get(self, request_hash: str) -> dict[str, Any] | None:
        return self.items.get(request_hash)

    def put(
        self, request_hash: str, *, model: str, prompt_version: str, request: dict[str, Any], response: dict[str, Any]
    ) -> None:
        self.items[request_hash] = response


class JsonDirStore:
    """One JSON file per request hash; used by the batch runner so recordings can be committed and replayed."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, request_hash: str) -> dict[str, Any] | None:
        path = self.root / f"{request_hash}.json"
        return json.loads(path.read_text(encoding="utf-8"))["response"] if path.exists() else None

    def put(
        self, request_hash: str, *, model: str, prompt_version: str, request: dict[str, Any], response: dict[str, Any]
    ) -> None:
        payload = {"model": model, "prompt_version": prompt_version, "request": request, "response": response}
        (self.root / f"{request_hash}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
