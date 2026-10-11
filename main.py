#!/usr/bin/env python3
"""harness-remote-bridge: one gateway, many coding-agent CLIs.

This build ships the ADAPTER-SPEC plus two adapters:
  * mock        — fully working reference implementation (safe to drive)
  * claude-code — detection skeleton (roadmap; raises NotSupported on verbs)

CLI:
  python main.py list-adapters
  python main.py sessions   --adapter mock
  python main.py create     --adapter mock --title "demo"
  python main.py send       --adapter mock --session <id> --text "fix the test"
  python main.py events     --adapter mock --session <id> [--after N]

Pure stdlib. No network calls in this build.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adapters import (AdapterError, MockAdapter, NotSupported, SessionNotFound,
                      instantiate, registry)
from gateway import Outbox, build_snapshot, dispatch


def _dump(x) -> str:
    return json.dumps(x, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="harness-remote-bridge",
                                description="unified remote-control gateway for coding agent CLIs")
    p.add_argument("--mock-file", default=None,
                   help="state file for the mock adapter (default: .bridge-mock.json)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-adapters", help="show adapters and detection status")
    sp = sub.add_parser("sessions"); sp.add_argument("--adapter", required=True)
    sp = sub.add_parser("create"); sp.add_argument("--adapter", required=True)
    sp.add_argument("--title", default="session")
    sp = sub.add_parser("send"); sp.add_argument("--adapter", required=True)
    sp.add_argument("--session", required=True); sp.add_argument("--text", required=True)
    sp = sub.add_parser("events"); sp.add_argument("--adapter", required=True)
    sp.add_argument("--session", required=True); sp.add_argument("--after", type=int, default=0)

    # v0.1.2 gateway layer
    sp = sub.add_parser("dispatch"); sp.add_argument("--plan", required=True,
        help="JSON file: [{\"to\": \"adapter:session\", \"text\": \"...\"}]")
    sub.add_parser("snapshot", help="audit export: all adapters, sessions, sha256")
    sp = sub.add_parser("queue-send"); sp.add_argument("--adapter", required=True)
    sp.add_argument("--session", required=True); sp.add_argument("--text", required=True)
    sp.add_argument("--outbox", default=".bridge-outbox.jsonl")
    sp = sub.add_parser("queue"); sp.add_argument("--outbox", default=".bridge-outbox.jsonl")
    sp = sub.add_parser("replay"); sp.add_argument("--outbox", default=".bridge-outbox.jsonl")

    a = p.parse_args(argv)

    if a.cmd == "list-adapters":
        rows = []
        for name, cls in sorted(registry().items()):
            inst = cls(path=a.mock_file) if name == "mock" else cls()
            rows.append(inst.describe())
        print(_dump(rows))
        return 0

    try:
        def _ad():
            return instantiate(a.adapter, path=a.mock_file) if a.adapter == "mock" \
                else instantiate(a.adapter)
        if a.cmd == "sessions":
            print(_dump(_ad().list_sessions()))
        elif a.cmd == "create":
            ad = _ad()
            if not isinstance(ad, MockAdapter):
                raise NotSupported("create is a mock-adapter convenience verb")
            print(_dump(ad.create_session(a.title)))
        elif a.cmd == "send":
            print(_dump(_ad().send_input(a.session, a.text)))
        elif a.cmd == "events":
            print(_dump(_ad().events(a.session, a.after)))
        elif a.cmd == "dispatch":
            try:
                with open(a.plan, "r", encoding="utf-8") as f:
                    plan = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                raise AdapterError(f"cannot read plan {a.plan}: {e}") from None
            print(_dump(dispatch(plan, mock_path=a.mock_file)))
        elif a.cmd == "snapshot":
            print(_dump(build_snapshot(mock_path=a.mock_file)))
        elif a.cmd == "queue-send":
            instantiate(a.adapter)  # reject unknown adapters up front
            Outbox(a.outbox).enqueue(a.adapter, a.session, a.text)
            print(_dump({"queued": True, "adapter": a.adapter,
                         "session": a.session, "outbox": a.outbox}))
        elif a.cmd == "queue":
            print(_dump(Outbox(a.outbox).items()))
        elif a.cmd == "replay":
            print(_dump(Outbox(a.outbox).replay(mock_path=a.mock_file)))
    except (AdapterError, NotSupported) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
