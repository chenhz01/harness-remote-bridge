"""Adapter base class and unified event/session schema.

See ADAPTER-SPEC.md for the full contract every adapter must honor.
"""
from __future__ import annotations

import abc
import time
import uuid

# Unified state vocabulary across all harnesses (SPEC section 2)
STATES = ("idle", "running", "waiting_input", "unavailable", "unknown")
EVENT_TYPES = ("output", "state", "error")


class AdapterError(Exception):
    """Base error for adapter violations."""


class SessionNotFound(AdapterError):
    pass


class NotSupported(AdapterError):
    """Raised by skeleton adapters that have not implemented a verb yet."""


def now() -> float:
    return time.time()


def new_event(ev_type: str, text: str, seq: int) -> dict:
    if ev_type not in EVENT_TYPES:
        raise AdapterError(f"event type must be one of {EVENT_TYPES}, got {ev_type!r}")
    return {"seq": seq, "ts": now(), "type": ev_type, "text": text}


class Adapter(abc.ABC):
    """Contract: every harness adapter implements these five verbs.

    All methods are synchronous and blocking. Events are monotonically
    numbered per session so a remote client can poll with `after_seq`.
    """

    name: str = "abstract"
    display: str = "Abstract adapter"
    # roadmap flag: skeleton adapters declare which verbs are unimplemented
    implemented: tuple = ("list_sessions",)

    @classmethod
    @abc.abstractmethod
    def detect(cls) -> bool:
        """True if the backing harness CLI appears installed on this machine."""

    @abc.abstractmethod
    def list_sessions(self) -> list[dict]:
        """[{id, title, state, harness}]"""

    @abc.abstractmethod
    def get_session(self, session_id: str) -> dict:
        """One session dict or raise SessionNotFound."""

    @abc.abstractmethod
    def send_input(self, session_id: str, text: str) -> dict:
        """Submit user input; returns the event emitted."""

    @abc.abstractmethod
    def events(self, session_id: str, after_seq: int = 0) -> list[dict]:
        """Events with seq > after_seq, oldest first."""

    def describe(self) -> dict:
        return {
            "name": self.name,
            "display": self.display,
            "detected": self.detect(),
            "implemented": list(self.implemented),
        }


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]
