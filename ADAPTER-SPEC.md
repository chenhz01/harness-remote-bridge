# ADAPTER-SPEC.md — unified remote-control contract, v0.1

Every adapter wraps ONE coding-agent CLI behind the same five verbs, so any
remote client (phone UI, dashboard, cron bot) can drive any harness without
knowing its protocol.

## 1. Data model

**Session** (dict, JSON-serializable):

```json
{
  "id": "a1b2c3d4e5f6",            // adapter-unique, opaque
  "title": "fix flaky test",       // human-readable
  "state": "idle",                  // see 2
  "harness": "claude-code",         // adapter name
  "created_at": 1781000000.0        // unix seconds
}
```

**Event** (append-only, per-session monotonic `seq` starting at 1):

```json
{ "seq": 3, "ts": 1781000004.2, "type": "output", "text": "..." }
```

## 2. Unified state vocabulary

| state          | meaning                                        |
|----------------|------------------------------------------------|
| `idle`         | turn finished, safe to send input              |
| `running`      | harness is working                             |
| `waiting_input`| harness blocked on a question/permission       |
| `unavailable`  | backing CLI missing / crashed                  |
| `unknown`      | adapter could not map the native state         |

## 3. The five verbs

| verb | signature | contract |
|---|---|---|
| `detect()` | classmethod → bool | True if the harness binary appears on PATH. Must not spawn the CLI. |
| `list_sessions()` | → [Session] | Active or resumable sessions of this harness on this machine. |
| `get_session(id)` | → Session | One session; raise `SessionNotFound` if absent. |
| `send_input(id, text)` | → Event | Submit one user turn. Must reject empty/whitespace input with `AdapterError`. |
| `events(id, after_seq)` | → [Event] | Events with `seq > after_seq`, oldest first. Poll-safe: repeated calls never duplicate or reorder. |

**Error discipline:** adapters raise only `AdapterError` subclasses
(`SessionNotFound`, `NotSupported`) or built-in `ValueError` for bad args.
Skeleton adapters that implement only some verbs raise `NotSupported` with a
pointer to the spec section they need.

**Non-goals for v0.1:** streaming push (polling only), file transfer, auth —
each is a roadmap item, not an interface change.

## 4. Per-harness notes (to be filled by implementers)

- **claude-code** (skeleton shipped): sessions and transcript live on disk
  under the user's config dir; `send_input` candidates are the interactive
  pipe mode and the one-shot `-p` mode — an implementer must decide how
  polling maps to `--output-format stream-json`. Unimplemented on purpose.
- **codex, cursor-agent, opencode, qwen-code, gemini-cli** (roadmap): same
  treatment — write observed CLI behavior into a section here before coding.

## 5. Acceptance checklist for a new adapter

1. `self_test.py` extended with your adapter passes all three tiers.
2. Every native state maps to the section-2 vocabulary (no leaks of native names).
3. `events` survives a process restart with unchanged `seq` numbering.
4. `detect()` never launches the harness binary.
