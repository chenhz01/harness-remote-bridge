#!/usr/bin/env python3
"""Self-test for harness-remote-bridge (v0.1: mock adapter + skeleton).

Tiers: [A] functional / [B] exception paths / [C] extreme edges.
Run: python self_test.py
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from adapters import (AdapterError, ClaudeCodeAdapter, CodexAdapter,
                      MockAdapter, NotSupported, SessionNotFound, instantiate,
                      registry, new_event)
from gateway import (Outbox, build_snapshot, dispatch, resolve_target)
from main import main

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


fd, MOCK = tempfile.mkstemp(suffix=".json")
os.close(fd)
os.unlink(MOCK)
mock = MockAdapter(path=MOCK)

# ---------------------------------------------------------------- A
print("[A] functional unit tests")
reg = registry()
check("registry has mock + claude-code + codex",
      set(reg) == {"mock", "claude-code", "codex"})
check("mock detect() True", mock.detect())
check("skeleton detect() is bool", isinstance(ClaudeCodeAdapter.detect(), bool))
d = mock.describe()
check("describe fields", d["name"] == "mock" and set(d["implemented"]) ==
      {"list_sessions", "get_session", "send_input", "events"})

s = mock.create_session("demo")
check("create_session schema", set(s) >= {"id", "title", "state", "harness"})
check("initial state idle", s["state"] == "idle")
check("list_sessions includes it", any(x["id"] == s["id"] for x in mock.list_sessions()))
check("get_session matches", mock.get_session(s["id"])["title"] == "demo")

ev = mock.send_input(s["id"], "fix the flaky test")
check("send_input returns event seq 1", ev["seq"] == 1 and ev["type"] == "output")
check("echo text present", "[mock echo]" in ev["text"])
ev2 = mock.send_input(s["id"], "second turn")
check("seq monotonic", ev2["seq"] == 2)
evs = mock.events(s["id"], after_seq=0)
check("events full fetch", [e["seq"] for e in evs] == [1, 2])
evs2 = mock.events(s["id"], after_seq=1)
check("events after_seq filter", [e["seq"] for e in evs2] == [2])
check("poll is idempotent", mock.events(s["id"], 1) == evs2)

s2 = mock.create_session("other")
check("sessions isolated", len(mock.list_sessions()) == 2)
check("event schema keys", set(new_event("output", "x", 1)) == {"seq", "ts", "type", "text"})

# CLI smoke
rc = main(["list-adapters"])
check("CLI list-adapters exit 0", rc == 0)
rc = main(["--mock-file", MOCK, "sessions", "--adapter", "mock"])
check("CLI sessions exit 0", rc == 0)
rc = main(["--mock-file", MOCK, "send", "--adapter", "mock",
           "--session", s["id"], "--text", "cli turn"])
check("CLI send exit 0", rc == 0)
rc = main(["--mock-file", MOCK, "events", "--adapter", "mock", "--session", s["id"], "--after", "2"])
check("CLI events exit 0", rc == 0)

# ---------------------------------------------------------------- B
print("[B] exception / error paths")
try:
    mock.get_session("nope")
    check("unknown session raises", False)
except SessionNotFound:
    check("unknown session raises", True)
try:
    mock.send_input("nope", "hi")
    check("send to unknown session raises", False)
except SessionNotFound:
    check("send to unknown session raises", True)
try:
    mock.send_input(s["id"], "   ")
    check("whitespace input rejected", False)
except AdapterError:
    check("whitespace input rejected", True)
try:
    mock.events(s["id"], after_seq=-1)
    check("negative after_seq rejected", False)
except AdapterError:
    check("negative after_seq rejected", True)
try:
    new_event("bogus", "x", 1)
    check("bad event type rejected", False)
except AdapterError:
    check("bad event type rejected", True)
try:
    instantiate("does-not-exist")
    check("unknown adapter rejected", False)
except AdapterError:
    check("unknown adapter rejected", True)
try:
    CodexAdapter().list_sessions()
    check("codex skeleton raises NotSupported", False)
except NotSupported as e:
    check("codex skeleton raises NotSupported", "SPEC" in str(e))
for verb, args in (("list_sessions", ()), ("get_session", ("x",)),
                   ("send_input", ("x", "y")), ("events", ("x",))):
    sk = ClaudeCodeAdapter()
    try:
        getattr(sk, verb)(*args)
        check(f"skeleton {verb} raises NotSupported", False)
    except NotSupported as e:
        check(f"skeleton {verb} raises NotSupported", "SPEC" in str(e))
rc = main(["sessions", "--adapter", "claude-code"])
check("CLI skeleton verb exit 2", rc == 2)
rc = main(["sessions", "--adapter", "ghost"])
check("CLI ghost adapter exit 2", rc == 2)

# ---------------------------------------------------------------- C
print("[C] extreme edges")
empty = MockAdapter(path=MOCK + ".empty.json")
check("empty store lists []", empty.list_sessions() == [])
long_text = "x" * 200_000
prev_seq = mock.events(s["id"], 0)[-1]["seq"]
ev3 = mock.send_input(s["id"], long_text)
check("200KB input accepted", ev3["seq"] == prev_seq + 1)
check("echo truncates to 200 chars", len(ev3["text"]) <= 200 + len("[mock echo] "))
# corrupted state file
with open(MOCK + ".corrupt.json", "w") as f:
    f.write("{definitely not json")
corrupt = MockAdapter(path=MOCK + ".corrupt.json")
try:
    corrupt.list_sessions()
    check("corrupt store raises AdapterError", False)
except (AdapterError, json.JSONDecodeError):
    check("corrupt store raises AdapterError", True)
# wrong schema
with open(MOCK + ".schema.json", "w") as f:
    json.dump({"hello": []}, f)
try:
    MockAdapter(path=MOCK + ".schema.json").list_sessions()
    check("wrong-schema store raises", False)
except AdapterError:
    check("wrong-schema store raises", True)
# many sessions
for i in range(100):
    mock.create_session(f"bulk-{i}")
check("100+ sessions listed", len(mock.list_sessions()) >= 102)
t0 = time.perf_counter()
mock.list_sessions()
dt = time.perf_counter() - t0
check("list 100 sessions < 1s (measured)", dt < 1.0)
print(f"  PERF  list_sessions of {len(mock.list_sessions())} sessions: {dt*1000:.1f} ms")

# ---------------------------------------------------------------- D
# v0.1.2 differentiation layer: cross-harness dispatch, snapshot audit,
# offline outbox. None of these exist in the anchor product space.
print("[D] differentiation layer (v0.1.2)")
# D1: unified adapter:session addressing
check("resolve_target splits adapter:session", resolve_target("mock:" + s["id"]) == ("mock", s["id"]))
for bad in ("no-colon", ":nosuch", "ghost:abc"):
    try:
        resolve_target(bad)
        check(f"resolve_target rejects {bad!r}", False)
    except AdapterError:
        check(f"resolve_target rejects {bad!r}", True)
# D2: batch dispatch across harnesses
mock2 = MockAdapter(path=MOCK)
t1 = mock2.create_session("d-target")
plan = [{"to": f"mock:{t1['id']}", "text": "batch turn"},
        {"to": "claude-code:whatever", "text": "hi"}]
results = dispatch(plan, mock_path=MOCK)
check("dispatch returns one result per item", len(results) == 2)
check("dispatch mock item delivered", results[0]["status"] == "delivered" and results[0]["seq"] == 1)
check("dispatch skeleton item errors honestly",
      results[1]["status"] == "error" and "SPEC" in results[1]["detail"])
plan_bad_session = [{"to": "mock:doesnotexist", "text": "x"}]
r2 = dispatch(plan_bad_session, mock_path=MOCK)
check("dispatch missing session reported as error", r2[0]["status"] == "error"
      and "no mock session" in r2[0]["detail"].lower())
try:
    dispatch([], mock_path=MOCK)
    check("dispatch empty plan rejected", False)
except AdapterError:
    check("dispatch empty plan rejected", True)
try:
    dispatch([{"to": "mock:x"}], mock_path=MOCK)
    check("dispatch item missing text rejected", False)
except AdapterError:
    check("dispatch item missing text rejected", True)
# D3: snapshot audit
snapd = build_snapshot(mock_path=MOCK)
names = {a["name"] for a in snapd["adapters"]}
check("snapshot covers all 3 adapters", names == {"mock", "claude-code", "codex"})
mock_row = next(a for a in snapd["adapters"] if a["name"] == "mock")
check("snapshot counts mock sessions", mock_row["session_count"] >= 3)
sk_row = next(a for a in snapd["adapters"] if a["name"] == "claude-code")
check("snapshot records skeleton error honestly",
      sk_row["session_count"] == 0 and "SPEC" in sk_row["error"])
check("snapshot sha256 present", len(snapd["sha256"]) == 64
      and all(c in "0123456789abcdef" for c in snapd["sha256"]))
snapd2 = build_snapshot(mock_path=MOCK)
check("snapshot hash deterministic", snapd2["sha256"] == snapd["sha256"])
# D4: offline outbox + ordered replay
ob_path = MOCK + ".outbox.jsonl"
if os.path.exists(ob_path):
    os.unlink(ob_path)
ob = Outbox(ob_path)
ob.enqueue("mock", t1["id"], "queued turn 1")
ob.enqueue("claude-code", "w", "queued turn 2")
check("outbox preserves order", [i["text"] for i in ob.items()] == ["queued turn 1", "queued turn 2"])
rep = ob.replay(mock_path=MOCK)
check("replay delivers mock item", rep["delivered"] == 1)
check("replay keeps undeliverable item", rep["still_queued"] == 1)
check("failed item gains attempt count", ob.items()[0]["attempts"] == 1)
rep2 = ob.replay(mock_path=MOCK)
check("second replay increments attempts", rep2["still_queued"] == 1 and ob.items()[0]["attempts"] == 2)
try:
    ob.enqueue("mock", t1["id"], "   ")
    check("outbox rejects blank text", False)
except AdapterError:
    check("outbox rejects blank text", True)
# CLI smoke for new verbs
fd3, PLAN = tempfile.mkstemp(suffix=".json"); os.close(fd3)
with open(PLAN, "w", encoding="utf-8") as f:
    json.dump([{"to": f"mock:{t1['id']}", "text": "cli batch"}], f)
rc = main(["--mock-file", MOCK, "dispatch", "--plan", PLAN])
check("CLI dispatch exit 0", rc == 0)
rc = main(["--mock-file", MOCK, "snapshot"])
check("CLI snapshot exit 0", rc == 0)
rc = main(["--mock-file", MOCK, "queue-send", "--adapter", "mock",
           "--session", t1["id"], "--text", "cli queued", "--outbox", ob_path])
check("CLI queue-send exit 0", rc == 0)
rc = main(["--mock-file", MOCK, "replay", "--outbox", ob_path])
check("CLI replay exit 0", rc == 0)
rc = main(["queue-send", "--adapter", "ghost", "--session", "x",
           "--text", "y", "--outbox", ob_path])
check("CLI queue-send ghost adapter exit 2", rc == 2)
for p in (PLAN, ob_path):
    try:
        os.unlink(p)
    except OSError:
        pass

for p in (MOCK, MOCK + ".empty.json", MOCK + ".corrupt.json", MOCK + ".schema.json"):
    try:
        os.unlink(p)
    except OSError:
        pass

print(f"\nRESULT: PASS {PASS}/{PASS + FAIL}")
sys.exit(0 if FAIL == 0 else 1)
