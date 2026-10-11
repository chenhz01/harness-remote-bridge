"""OpenAI Codex CLI adapter — SKELETON (roadmap item, not yet functional).

Second skeleton proving the ADAPTER-SPEC pattern generalizes: detection only,
all data verbs raise NotSupported with a spec pointer.
"""
from __future__ import annotations

import shutil

from .base import Adapter, NotSupported


class CodexAdapter(Adapter):
    name = "codex"
    display = "OpenAI Codex CLI (skeleton)"
    implemented = ("detect",)

    @classmethod
    def detect(cls) -> bool:
        return shutil.which("codex") is not None

    def list_sessions(self):
        raise NotSupported(
            "codex adapter is a skeleton — see ADAPTER-SPEC.md section 4")

    def get_session(self, session_id: str):
        raise NotSupported(
            "codex adapter is a skeleton — see ADAPTER-SPEC.md section 4")

    def send_input(self, session_id: str, text: str):
        raise NotSupported(
            "codex adapter is a skeleton — see ADAPTER-SPEC.md section 4")

    def events(self, session_id: str, after_seq: int = 0):
        raise NotSupported(
            "codex adapter is a skeleton — see ADAPTER-SPEC.md section 4")
