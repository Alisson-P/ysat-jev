# Changelog

All notable changes to this skill are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-22

Initial release of `ysat-jev`, the typed judgment variant of the `ysat` counterpoint skill. Same
purpose, one layer different: the verdict is composed in code instead of written in prose.

### Added

- Typed judgment layer with the three primitives Noul, Choice and Score, and four interchangeable
  backends behind one interface: `openjev` (local, default), `local`, `typesafe` (comparison arbiter
  only, state redacted by default) and `offline` (safety net and automatic fallback).
- Atomic question bank decomposing decision risk into eight independently judged questions, each
  phrased so that 1.0 means more risk.
- Verdict composition in code with visible, versioned coefficients in `config.yaml`.
- Three gates: coverage floor (0.60), a higher agreement coverage floor (0.80) so agreement is
  earned rather than defaulted to, and uncertainty routing on confidence (act / review / escalate).
- State hash on every run, making the anti-sycophancy invariant arithmetic: the same state produces
  the same verdict, and rhetorical pressure is not a state field.
- Deterministic `stub_server.py` answering the openJev HTTP contract, so the whole flow runs with no
  model weights. Every stub answer is flagged `"stub": true` through to the audit trail.
- JSON audit trail per run: question, value, distribution, confidence, abstentions, coefficients,
  thresholds and the state hash.
- Design documentation (`docs/typed-decisions.md`) and the decision record
  (`docs/adr/ADR-0001-typed-verdict.md`), including the measurement that would retire the variant.
- Documentation in two languages: `README.md` (primary, English) and `README.pt-BR.md`.
- Five worked examples with numbers produced by actually running the engine.

### Fixed before release

- A null Noul value returned by a backend was being coerced to 0.0, which reads as "no risk here".
  It now abstains unless a real distribution is present, so an unanswered question lowers coverage
  instead of quietly becoming the comfortable answer. This was the exact failure mode locked
  invariant 4 exists to prevent, found by running the thin state case.

### Measured

- `BENCHMARK.md`: a measured comparison against the base `ysat` skill. Engine latency and
  determinism at n=100, behavioural spot check at n=1 per arm, context cost, and the sensitivity of
  the risk index to each state field.
- Two findings from that benchmark are documented rather than hidden: the stub is blind to negation
  (a state saying a rollback was never rehearsed scores the same as one saying it was), so the stub
  validates the contract and does not judge; and padding the state with sourced but irrelevant
  evidence lowers the index by a small, audit-visible amount.
- Corrected an overclaim in the READMEs, which described the stub as a legitimate permanent
  configuration. The negation test falsified that, so the claim is gone.

### Delegation

- Routes conversational counterpoint requests to the base `ysat` skill, which remains the default
  for interactive use. This variant triggers on explicit typed verdict, audit trail or `modo jev`
  requests.
