# Changelog

All notable changes to `harness-remote-bridge` (ALIGNMENT-16 rule 93).

## v0.1.2 - 2026-10-11 (round 3: differentiation vs Claude-Code-Remote)

### Added
- Gateway layer (`gateway.py`) — three cross-adapter verbs, each absent from
  the anchor product's README (see README "How this differs"):
  - `dispatch` + uniform `adapter:session` targets: one batch of inputs
    routed across harnesses, per-item results (delivered/error), batch
    survives individual failures.
  - `snapshot` audit export: all adapters' sessions/states, skeleton errors
    recorded not hidden, sha256 over content (timestamp excluded so
    unchanged fleets hash equal).
  - `queue-send` / `queue` / `replay` durable outbox (JSONL): record inputs
    while a target is unreachable, ordered replay, attempt counters.
- self_test tier [D]: 26 new checks (40 → 66) covering addressing rules,
  batch semantics, hash determinism, outbox ordering/attempts, and CLI
  exits for all new verbs.

### Changed
- `main()` adapter instantiation is now per-branch (the new gateway verbs
  take no `--adapter`), fixing a latent AttributeError for adapter-less
  commands.

## v0.1.1 - 2026-10-11 (round 2: self-audit revision)

### Added
- Third adapter skeleton `codex` — proves the ADAPTER-SPEC pattern generalizes
  beyond a single example. Registry 2 → 3 adapters.
- 1 new test (codex skeleton NotSupported w/ spec pointer) and the registry
  membership check widened. Tests 39 → 40; adapter-family coverage +50%.

### Fixed
- Skeleton `NotSupported` messages for `get_session`/`events` now point at
  ADAPTER-SPEC.md section 4 (they previously lacked the spec pointer that the
  error-discipline contract promises — found by the self-test asserting
  `"SPEC" in str(e)`).

### Changed
- Self-test long-input check now derives the expected `seq` dynamically
  instead of assuming a fixed count, removing a brittle-order dependency.

## v0.1.0 - 2026-10-11 (initial release)

### Added
- ADAPTER-SPEC.md: unified session/event contract (5 verbs, 5-state
  vocabulary, monotonic seq, error discipline, per-harness notes, acceptance
  checklist).
- `mock` adapter — complete reference implementation; `claude-code` skeleton.
- Gateway CLI: `list-adapters / sessions / create / send / events`.
- Three-tier self-test suite, 39 checks PASS.
