"""Gateway-level capabilities layered on the ADAPTER-SPEC (v0.1.2).

Three functions that operate ACROSS adapters, which no single adapter can
provide on its own:

* ``resolve_target``  — one uniform ``adapter:session`` addressing scheme.
* ``dispatch``        — one batch of inputs routed to whatever harness each
                        target belongs to; per-item result, never fails whole
                        batch because one target failed.
* ``build_snapshot``  — a single auditable JSON export of every adapter's
                        session state, with a content hash.
* ``Outbox``          — durable offline queue (JSONL): record inputs while a
                        target is unreachable, replay them in order later.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import (AdapterError, NotSupported, SessionNotFound, instantiate,
                      registry)


def resolve_target(to: str) -> tuple[str, str]:
    """Split the uniform ``adapter:session`` target."""
    if not isinstance(to, str) or ":" not in to:
        raise AdapterError(f"target must be 'adapter:session', got {to!r}")
    adapter, session = to.split(":", 1)
    if not adapter:
        raise AdapterError(f"target {to!r} has empty adapter name")
    if adapter not in registry():
        raise AdapterError(f"unknown adapter in target {to!r}")
    return adapter, session


def _mk(adapter: str, mock_path: str | None):
    return instantiate(adapter, path=mock_path) if adapter == "mock" \
        else instantiate(adapter)


def dispatch(plan: list[dict], mock_path: str | None = None) -> list[dict]:
    """Route a batch of inputs to their targets.

    plan: [{"to": "adapter:session", "text": "..."}, ...]
    Returns one result per item: {"to", "status": "delivered"|"error",
    "seq"?/ "detail"?}. Batch continues past individual failures.
    """
    if not isinstance(plan, list) or not plan:
        raise AdapterError("dispatch plan must be a non-empty list")
    results = []
    for i, item in enumerate(plan):
        if not isinstance(item, dict) or "to" not in item or "text" not in item:
            raise AdapterError(f"plan[{i}] must be an object with 'to' and 'text'")
        try:
            adapter, session = resolve_target(item["to"])
        except AdapterError as e:
            results.append({"to": item["to"], "status": "error", "detail": str(e)})
            continue
        try:
            ad = _mk(adapter, mock_path)
            ev = ad.send_input(session, item["text"])
            results.append({"to": item["to"], "status": "delivered", "seq": ev["seq"]})
        except (AdapterError, NotSupported, SessionNotFound) as e:
            results.append({"to": item["to"], "status": "error", "detail": str(e)})
    return results


def build_snapshot(mock_path: str | None = None) -> dict:
    """One audit artifact: every adapter's sessions + states, hashed.

    Skeleton adapters contribute zero sessions plus their honest error text,
    so an auditor sees coverage gaps instead of silent omissions.
    """
    adapters_out = []
    for name in sorted(registry()):
        row: dict = {"name": name}
        try:
            ad = _mk(name, mock_path)
            desc = ad.describe()
            sessions = ad.list_sessions()
            row["detected"] = desc["detected"]
            row["implemented"] = desc["implemented"]
            row["session_count"] = len(sessions)
            row["sessions"] = sessions
            row["states"] = sorted({s.get("state", "unknown") for s in sessions})
        except (AdapterError, NotSupported) as e:
            row["detected"] = False
            row["implemented"] = []
            row["session_count"] = 0
            row["sessions"] = []
            row["states"] = []
            row["error"] = str(e)
        adapters_out.append(row)
    snap = {"format": "bridge-snapshot/0.1", "generated_at": time.time(),
            "adapters": adapters_out}
    # hash covers the audit content only, not the generation timestamp —
    # two snapshots of an unchanged fleet must compare equal.
    canonical = json.dumps(adapters_out, sort_keys=True, ensure_ascii=False)
    snap["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return snap


class Outbox:
    """Durable offline input queue (one JSON object per line).

    ``enqueue`` appends; ``replay`` walks the queue oldest-first, delivering
    what it can and rewriting the file with only the still-undelivered items
    (attempt count incremented). Delivery order is never reordered.
    """

    def __init__(self, path: str):
        self.path = path

    def _read(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def _write(self, items: list[dict]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")

    def enqueue(self, adapter: str, session: str, text: str) -> dict:
        if not isinstance(text, str) or not text.strip():
            raise AdapterError("outbox text must be a non-empty string")
        items = self._read()
        it = {"id": len(items) + 1, "adapter": adapter, "session": session,
              "text": text.strip(), "queued_at": time.time(), "attempts": 0}
        items.append(it)
        self._write(items)
        return it

    def items(self) -> list[dict]:
        return self._read()

    def replay(self, mock_path: str | None = None) -> dict:
        delivered, results, keep = 0, [], []
        for it in self._read():
            ok = False
            try:
                ad = _mk(it["adapter"], mock_path)
                ad.send_input(it["session"], it["text"])
                ok = True
            except (AdapterError, NotSupported, SessionNotFound):
                ok = False
            if ok:
                delivered += 1
                results.append({"id": it["id"], "status": "delivered"})
            else:
                it["attempts"] = it.get("attempts", 0) + 1
                keep.append(it)
                results.append({"id": it["id"], "status": "queued",
                                "attempts": it["attempts"]})
        self._write(keep)
        return {"delivered": delivered, "still_queued": len(keep),
                "results": results}
