"""Fully working in-process mock adapter.

Used for integration tests, demo clients, and as the reference
implementation of ADAPTER-SPEC.md. Sessions live in one JSON file
(shared with any other process that points BRIDGE_MOCK_FILE at it).
"""
from __future__ import annotations

import json
import os

from .base import (Adapter, AdapterError, SessionNotFound, new_event,
                   new_session_id, now)


class MockAdapter(Adapter):
    name = "mock"
    display = "In-process mock harness (reference implementation)"
    implemented = ("list_sessions", "get_session", "send_input", "events")

    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("BRIDGE_MOCK_FILE", ".bridge-mock.json")

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {"sessions": {}}
        with open(self.path, "r", encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw) if raw.strip() else {"sessions": {}}
        if not isinstance(data, dict) or "sessions" not in data:
            raise AdapterError("mock state file has wrong schema")
        return data

    def _save(self, data: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)

    @classmethod
    def detect(cls) -> bool:
        return True  # always available; it is in-process

    def create_session(self, title: str = "session") -> dict:
        data = self._load()
        sid = new_session_id()
        s = {"id": sid, "title": title, "state": "idle", "harness": "mock",
             "created_at": now(), "events": []}
        data["sessions"][sid] = s
        self._save(data)
        return {k: v for k, v in s.items() if k != "events"}

    def list_sessions(self) -> list[dict]:
        data = self._load()
        out = []
        for s in data["sessions"].values():
            out.append({k: v for k, v in s.items() if k != "events"})
        return sorted(out, key=lambda s: s["created_at"])

    def get_session(self, session_id: str) -> dict:
        data = self._load()
        if session_id not in data["sessions"]:
            raise SessionNotFound(f"no mock session {session_id!r}")
        s = data["sessions"][session_id]
        return {k: v for k, v in s.items() if k != "events"}

    def send_input(self, session_id: str, text: str) -> dict:
        if not isinstance(text, str) or not text.strip():
            raise AdapterError("input text must be a non-empty string")
        data = self._load()
        s = data["sessions"].get(session_id)
        if s is None:
            raise SessionNotFound(f"no mock session {session_id!r}")
        # simulated turn: input event -> running -> output -> idle
        seq = len(s["events"]) + 1
        ev = new_event("output", f"[mock echo] {text.strip()[:200]}", seq)
        s["events"].append(ev)
        s["state"] = "idle"
        self._save(data)
        return ev

    def events(self, session_id: str, after_seq: int = 0) -> list[dict]:
        data = self._load()
        s = data["sessions"].get(session_id)
        if s is None:
            raise SessionNotFound(f"no mock session {session_id!r}")
        if after_seq < 0:
            raise AdapterError("after_seq must be >= 0")
        return [e for e in s["events"] if e["seq"] > after_seq]
