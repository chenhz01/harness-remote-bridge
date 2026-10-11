One gateway in front of many coding-agent CLIs. This repo ships the adapter interface spec plus working skeleton adapters, so a phone UI, dashboard, or cron bot can drive Claude Code, Codex, and friends through one uniform session/event protocol instead of reverse-engineering six different CLI flags. The mock adapter is fully drivable today; real-harness adapters are roadmap items.

You need this if you run 2+ coding-agent CLIs and want one remote control surface. If you use a single harness, its own CLI is enough.

## Problem

Agent *harnesses* multiply faster than the ways to reach them. One working answer exists (pingdotgg/t3code: a local service + iOS/Web/Console remote that controls six harnesses), and its most under-appreciated part is not the UI — it is the **adapter layer**: six heterogeneous CLIs reduced to a uniform "list sessions / send input / poll events" contract. That layer is treated as an implementation detail when it is really the API-server position of the agent ecosystem. The gap: no open, testable *specification* of that contract that new harness adapters can be written against.

**Why not just reverse each CLI ad hoc?** Because every client (phone, CI, chat bot) then re-learns each protocol. Confidence: **Medium (60-79%)** — the contract is implemented and tested against the mock; claims about real-harness behavior are untested here by design (see Limits).

## How it works

- **ADAPTER-SPEC.md** defines the contract: 5 verbs (`detect`, `list_sessions`, `get_session`, `send_input`, `events`), a 5-state vocabulary (`idle/running/waiting_input/unavailable/unknown`), append-only events with per-session monotonic `seq`, and an error discipline (only `AdapterError` subclasses cross the boundary).
- **Adapters** implement the spec. This build ships:
  - `mock` — complete reference implementation (in-process, JSON-backed, drivable end-to-end).
  - `claude-code`, `codex` — honest skeletons: real `detect()` via PATH check, `NotSupported` elsewhere, with spec pointers.
- **Gateway** (`main.py`) is a thin registry + CLI so you can exercise any adapter uniformly.
- **Gateway layer** (`gateway.py`, v0.1.2) adds the three cross-adapter verbs no single adapter can provide: batch `dispatch` over uniform `adapter:session` targets, a hashed `snapshot` audit export, and a durable offline `queue-send`/`replay` outbox.

## Quickstart (~5 min)

```bash
# 1. self-test (~5 s) — three-tier suite over the mock adapter
python self_test.py

# 2. drive the mock adapter end-to-end (~1 min)
python main.py create --adapter mock --title "demo"
python main.py sessions --adapter mock
python main.py send --adapter mock --session <id> --text "fix the flaky test"
python main.py events --adapter mock --session <id> --after 0

# 3. see what's detected on this machine (~10 s)
python main.py list-adapters
```

Next step (roadmap): implement a real adapter by following ADAPTER-SPEC.md section 5.

## How this differs from Claude-Code-Remote

Read against the JessyTsui/Claude-Code-Remote README (its Features, Changelog, and TODO sections as of 2026-10): it delivers multi-channel notifications (Email/Telegram/LINE/Desktop), reply-to-send two-way control, tmux/PTY injection into a running Claude Code, execution traces, sender whitelists, and hooks-based completion detection — all for ONE harness, with multi-tool support listed in its own TODO as not yet done. It is a working product; this repo is a spec-first layer beneath products like it. Three capabilities its README does not describe anywhere:

| Capability | Here | Anchor README status |
|---|---|---|
| Cross-harness batch dispatch (`dispatch`, `adapter:session` targets) | One client routes one batch of inputs to sessions on different harnesses; per-item results, single failures don't kill the batch | Not present; its TODO "AI Tools Support" means even single-harness-plus-one is future work |
| Snapshot audit (`snapshot`) | One JSON export of every adapter's sessions + states, with skeleton errors recorded (not hidden) and a sha256 over the content for tamper-evidence | No audit/snapshot export mentioned |
| Offline outbox (`queue-send` / `queue` / `replay`) | Inputs recorded durably (JSONL) while a target is unreachable, replayed oldest-first later; failed items keep an attempt count | Not present; injection is live tmux/PTY, and nothing in the README queues commands for later delivery |

Scope honesty: these are implemented and tested against the mock adapter (self_test tier [D]); against real harnesses they are unproven, same as the rest of v0.1.

## Why not X

| Alternative | What it does | Why not enough |
|---|---|---|
| t3code (closed exploration of the same idea) | Polished local service + apps controlling six harnesses | Product, not a reusable open spec; you cannot write a new adapter against it |
| Wrapper scripts per CLI (`claude -p`, `codex exec` in bash) | Automates one harness | Every client re-implements session tracking, state mapping, error handling |
| MCP servers for agents | Standardized *tool* access into agent runtimes | Different layer: tool protocol, not session remote-control; no unified session/event model across CLIs |
| tmux/screen + send-keys | Send keystrokes to any TUI | No structured events or states — you screen-scrape, and every harness breaks it differently |

## Minimal Fallback (PLAN B)

No Python at all? The spec's core is state polling over a file: have your agent CLI append JSON lines (`{"seq":1,"type":"output","text":"..."}`) to `events.jsonl`, and your remote client polls with `tail -n +$((LAST+1)) events.jsonl`. You lose session listing and state mapping, but keep the uniform event log.

## Design Trade-offs

Priority order: **interface stability > honesty > coverage > features.**

- **Spec-first, adapters later.** v0.1 ships 1 working + 2 skeleton adapters rather than 6 fake ones. A skeleton that raises `NotSupported` with a spec pointer is more useful than an adapter that parses a CLI incorrectly. Coverage is a roadmap, marked per-adapter (`implemented` field).
- **Polling, not push.** `events(after_seq)` is poll-safe and trivially restartable; streaming adds transport complexity (websocket, reconnect) that would destabilize the v0.1 contract.
- **Detection never spawns the harness.** `detect()` is a PATH check only — side-effect-free by contract (tested).
- **In-process mock as reference.** Real-harness protocol reverse-engineering is environment-fragile; the mock pins the contract so adapter implementations can be tested offline.

## Limits & Second-order Effects

- **No real-harness adapter is functional in v0.1.** The spec is tested against the mock only; actual CLI behavior (flags, output formats, auth) may drift. Numbers on the roadmap are intentions, not measurements.
- **Skeleton `detect()` can false-positive** (a binary named `claude` on PATH is not proof of a usable harness).
- **Second-order effect 1 — remote-control risk:** the easier it is to drive agent CLIs from a phone, the more people run agents unattended. A stolen laptop + this gateway is a remote agent driver; deployers must add their own auth layer (explicit non-goal for v0.1).
- **Second-order effect 2 — state flattening:** mapping 6 harnesses into 5 states loses harness-specific nuance (e.g. permission prompts vs questions); clients built on the abstraction may mis-handle cases the vocabulary can't express.
- **Second-order effect 3 — spec drift:** if real adapters land without updating ADAPTER-SPEC.md, the spec becomes fiction. Section 5's acceptance checklist exists to slow this.

## FAQ

**Q: Does this actually control Claude Code today?**
No. Detection yes, control no. That is stated in the adapter's `implemented` field, the CLI output, and here — the mock adapter is what works end-to-end in v0.1.

**Q: Why JSON events instead of a websocket stream?**
Polling is restartable, debuggable with `jq`, and sufficient for turn-based harnesses. Streaming is a v0.2+ concern that must not break the event schema.

**Q: Can I add an adapter without touching the gateway?**
Drop a module in `adapters/`, subclass `Adapter`, add it to `BUILTIN`. The registry is a list, not magic.

**Q: When NOT to use this tool?** *(ask this first)*
- You use one harness and are happy in its CLI — the gateway adds indirection, not value.
- You need a production remote-control product today — this is a spec + skeletons, not that.
- You need streaming token output — out of scope by design (see trade-offs).
- You need auth/multi-user remote access — you must build that layer yourself.

**Q: Why release skeletons at all?**
So the contract gets reviewed before six implementations bake in wrong assumptions. Cheaper to fix a spec than six adapters.

## [Core Assumptions]

1. Coding-agent CLIs can ultimately be driven by (a) listing resumable sessions, (b) submitting one text input, (c) observing text/state events. If a harness is GUI-only or API-only, it does not fit this spec.
2. Turn-based interaction is the norm for coding agents; polling at turn granularity is acceptable for remote-control use cases.
3. Every harness state can be honestly mapped into the 5-state vocabulary (or `unknown` — visible, not hidden).
4. Adapter authors will keep ADAPTER-SPEC.md authoritative; the code exists to test the spec, not to replace it.

---
Contact: hcac4735@agent.qq.com · License: MIT · No time-sensitive vendor data in this README. Mock perf: ~2 ms to list 102 sessions (measured, repro: `python self_test.py`).
