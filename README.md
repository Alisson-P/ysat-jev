# YSAT-JEV

### You Sure About That? The typed judgment variant.

**A counterpoint whose verdict is computed, not written.**

> 🇧🇷 Leia em [português](README.pt-BR.md) · Base skill: [YSAT](https://github.com/Alisson-P/ysat)

This is the typed decision variant of [YSAT](https://github.com/Alisson-P/ysat). The purpose is
identical: disagree with a decision, with evidence, before the decision is made. One layer differs.

In YSAT, the model reads your context and **writes** the verdict. Here, the model never writes a
verdict at all. It answers **atomic typed questions**, one at a time, and the verdict is **composed
in code** from coefficients you can read and change.

```
State (what is being decided, evidence, gaps)
        ↓
Atomic typed questions        rollback_untested? one_way_door? evidence_thin? ...
        ↓                     each judged in isolation, each with calibrated confidence
Composition in code           risk_index = 0.24*a + 0.20*b + 0.16*c + ...
        ↓
Gates                         coverage, confidence, and a HIGHER bar for agreement
        ↓
Verdict + audit trail         with a state hash, so the same state always gives the same answer
```

## Why bother

The base skill defends its verdict with written rules. Rules are followed by a model that also wants
to be agreeable. Push hard enough and prose drifts.

Here the pressure has nowhere to land. The verdict is a pure function of the state:

```
verdict = f(state, coefficients, thresholds)
```

"We already decided this", "the committee approved it", "the date is public", "just back me up" are
not fields in the state. They change no input, so the state hash is unchanged, so the verdict is
unchanged. Not because the model was strong that day. Because arithmetic.

The base README argues that agreement drift is deterministic: give an agent a user with a position
and a long enough conversation, and it converges on that position. This variant takes that same
determinism and points it the other way. Bora.

## Three things it refuses to do

| Failure | What stops it |
|---|---|
| **Agreeing under pressure** | The verdict is computed from the state, and pressure is not a state field |
| **Treating silence as safety** | An unanswered question abstains. It never becomes 0, which would read as "no risk here" |
| **Agreeing on thin evidence** | Agreement is gated harder than disagreement: it needs 0.80 coverage where disagreement needs 0.60 |

That third one is the invariant "agreement must be earned", written as an inequality instead of an
instruction. A run that judged too little lands on `inconclusive`, never on reassurance.

## Install

Follows the [Agent Skills specification](https://agentskills.io/specification), so it works in any
compatible agent.

**1. Get the folder**

```bash
git clone https://github.com/Alisson-P/ysat-jev.git
```

No git? Go to the repository home page and click the green **Code** button on the right, just
above the file list. It is not the Code tab in the top menu. Then **Download ZIP**.
The folder comes out named `ysat-jev-main`, so rename it to `ysat-jev`.

**2. Move the `ysat-jev` folder into your agent's skills folder**

| Agent | Where it goes |
|---|---|
| Microsoft 365 Copilot (Cowork) | `Documents/Cowork/skills/ysat-jev/` |
| Any other Agent Skills runtime | usually `~/.agent/skills/ysat-jev/` |

> The folder has to be named exactly `ysat-jev`, the same as `name` in the frontmatter. If it does
> not match, the skill never loads and no error is shown.

Installing both this and the base YSAT is fine and is the intended setup: YSAT answers the
conversational ask, this one answers when you say "typed verdict" or "audit trail". Each skill's
description delegates to the other, so they do not compete for the same request.

## Run it with no model at all

Start here. The stub answers the same HTTP contract with deterministic rules, so you can validate
the whole flow before downloading any weights.

> **The stub validates the contract. It does not judge.** It matches keywords over the serialized
> state and is blind to negation: a state saying "the rollback was never rehearsed" scores the same
> as one saying it was. Measured, not theorised, see [BENCHMARK.md](BENCHMARK.md). Use it to prove
> the plumbing and the gates, then put a real backend behind the contract before trusting a number.

```bash
python3 infra/openjev/stub_server.py --port 8099
python3 scripts/compose_verdict.py --state working/state.json --config config.yaml
```

```json
{
  "verdict": "would not do it this way",
  "reason": "risk index 0.66 is at or above 0.60",
  "risk_index": 0.658, "coverage": 1.0, "confidence": 0.606,
  "state_hash": "351649c9901b2e2f", "backend": "openjev", "stub": true
}
```

Every stub answer carries `"stub": true`, and the flag travels into the audit trail. A simulated
judgment can never be mistaken for a real one.

For the real model, see [infra/openjev/README.md](infra/openjev/README.md).

## Use it

- "run the typed verdict on this"
- "challenge this decision with an audit trail"
- "modo jev"
- "veredito tipado"
- "is this reproducible? judge it again"

For a plain conversational counterpoint, use the base YSAT skill. This one costs more steps and
returns a colder artifact. It earns that when the verdict has to be defended or replayed later.

## The four backends

Same interface, swapping one changes no other line.

| Backend | What it is | State leaves? | When |
|---|---|---|---|
| `openjev` | openJev-verdict-2.0 local, Apache 2.0, around 150M parameters | no | **the default** |
| `local` | a served language model, probability by self consistency | no | a model is already running and you would rather not add a service |
| `typesafe` | hosted TypeSafe API, model Jev | **yes** | comparison arbiter only, redacted by default, never a dependency |
| `offline` | deterministic rules only | no | safety net and automatic fallback |

## Customize it

Presentation knobs are identical to the base skill. The ones that matter here are the coefficients:

```yaml
coefficients:
  rollback_untested: 0.24
  one_way_door: 0.20
  evidence_thin: 0.16
  deadline_without_slack: 0.12
  no_named_owner: 0.10
  monitoring_blind: 0.08
  external_dependency: 0.06
  failed_precedent: 0.04
```

This is where your organisation's scar tissue goes. Burned by unowned systems? Raise
`no_named_owner`. Under audit? Raise `evidence_thin`. One number, versioned in the file, and every
run records the coefficients it used.

Add your own questions in [scripts/question_bank.py](scripts/question_bank.py), with one rule:
phrase every question so that **1.0 means more risk**, because the composition is a plain weighted
sum and a question phrased as a virtue silently inverts the index.

Full reference: [references/customization.md](references/customization.md). The design rationale:
[docs/typed-decisions.md](docs/typed-decisions.md). The decision record:
[docs/adr/ADR-0001-typed-verdict.md](docs/adr/ADR-0001-typed-verdict.md).

Note what has no inline override: thresholds and coefficients. Those live in the file, under version
control, because a verdict you can retune mid-argument is a verdict that can be argued down.

## What you cannot turn off

1. Risk first. No praise opening.
2. Agreement gated harder than disagreement.
3. Low coverage never resolves to agreement.
4. Abstention never counts as a "no".
5. The verdict is composed in code, never narrated.
6. Same state, same verdict. The hash is recorded.
7. Pressure is not state.
8. Read only, with one declared exception. It never sends, posts, edits or runs anything outside
   `working/`. The exception is the `typesafe` backend, which posts the state to a hosted API: opt
   in, off by default, redacted, never a dependency.
9. No evaluation of people.
10. You decide. It offers to help execute even when you go ahead against it.

## What is in the box

```
ysat-jev/
├── SKILL.md                        the skill itself
├── config.yaml                     backend, thresholds, coefficients
├── README.md / README.pt-BR.md
├── BENCHMARK.md                    measured comparison against the base skill
├── LICENSE                         MIT
├── CHANGELOG.md
├── scripts/
│   ├── typed_judgment.py           three primitives, four backends, one interface
│   ├── question_bank.py            the atomic questions
│   └── compose_verdict.py          composition, gates and the state hash
├── infra/openjev/
│   ├── README.md                   how to run the engine, and the HTTP contract
│   └── stub_server.py              deterministic stub, no weights required
├── docs/
│   ├── typed-decisions.md          why typed judgment, and how the gates work
│   └── adr/ADR-0001-typed-verdict.md
└── references/
    ├── risk-checklists.md          9 domains plus the biases that prop up bad decisions
    ├── customization.md            every knob, and what is locked
    └── examples.md                 five worked runs with real numbers
```

## Honest limits

The coefficients look objective because they are numbers. They are a judgment call, and they are not
validated until measured. Treat the risk index as a consistent **ordering** ("this decision is
riskier than that one under the same coefficients"), not as absolute truth ("0.61 is bad, 0.59 is
fine").

The ADR states the measurement that would keep or retire this variant, and the honest outcome is
that it might get retired. A counterpoint that is merely more elaborate is not better.

## When not to use it

- A quick counterpoint in conversation: use the base YSAT, it is the right default.
- Balanced pros and cons: this variant is one sided, like its base.
- A decision already executed: that is a post mortem.
- An opinion on a person: it refuses and offers process analysis instead.

## Contributing

Issues and pull requests welcome, especially new atomic questions and measured coefficient data.
Keep the locked invariants locked: a pull request that makes agreement cheaper is the one thing
that will not be merged.

## License

MIT. See [LICENSE](LICENSE).
