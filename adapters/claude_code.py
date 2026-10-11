"""Claude Code adapter — SKELETON (roadmap item, not yet functional).

Implements `detect()` truthfully (checks PATH for the `claude` binary) and
declares every data verb as unimplemented. See ADAPTER-SPEC.md section 4 for
the observed CLI behaviors an implementer must encode, and ROADMAP in README.
"""
from __future__ import annotations

import shutil

from .base import Adapter, NotSupported


class ClaudeCodeAdapter(Adapter):
    name = "claude-code"
    display = "Claude Code CLI (skeleton)"
    implemented = ("detect",)

    @classmethod
    def detect(cls) -> bool:
        return shutil.which("claude") is not None

    def list_sessions(self):
        raise NotSupported(
            "claude-code adapter is a skeleton: session discovery requires "
            "parsing `claude` CLI output — see ADAPTER-SPEC.md section 4")

    def get_session(self, session_id: str):
        raise NotSupported(
            "claude-code adapter is a skeleton — see ADAPTER-SPEC.md section 4")

    def send_input(self, session_id: str, text: str):
        raise NotSupported(
            "claude-code adapter is a skeleton: sending input requires the "
            "flagged/interactive mode contract in ADAPTER-SPEC.md section 4")

    def events(self, session_id: str, after_seq: int = 0):
        raise NotSupported(
            "claude-code adapter is a skeleton — see ADAPTER-SPEC.md section 4")
