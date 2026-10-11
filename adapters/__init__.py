"""Adapter registry. Add a module here and it auto-registers."""
from .base import (Adapter, AdapterError, EVENT_TYPES, STATES, NotSupported,
                   SessionNotFound, new_event, new_session_id, now)
from .claude_code import ClaudeCodeAdapter
from .codex import CodexAdapter
from .mock import MockAdapter

BUILTIN = [MockAdapter, ClaudeCodeAdapter, CodexAdapter]


def registry() -> dict[str, type[Adapter]]:
    return {a.name: a for a in BUILTIN}


def instantiate(name: str, **kwargs) -> Adapter:
    try:
        return registry()[name](**kwargs)
    except KeyError:
        raise AdapterError(
            f"unknown adapter {name!r}; available: {sorted(registry())}") from None


__all__ = ["Adapter", "AdapterError", "SessionNotFound", "NotSupported",
           "EVENT_TYPES", "STATES", "new_event", "new_session_id", "now",
           "BUILTIN", "registry", "instantiate",
           "MockAdapter", "ClaudeCodeAdapter"]
