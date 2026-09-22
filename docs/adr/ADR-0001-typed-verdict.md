# ADR-0001. Typed verdict with a local open decision model

- **Status:** Accepted
- **Date:** 2026-09-22
- **Decider(s):** Alisson Pereira
- **Project:** `ysat-jev` (variant). The base `ysat` skill does not adopt this decision.

## Context

The base skill asks the model to read the context and write the verdict in prose. That carries the
three known defects of prose judgment: the format breaks, the value arrives outside the expected
domain, and confidence declared in words is not a calibrated number a gate can threshold.

For this particular skill there is a fourth defect, and it is the expensive one. The whole value of
a counterpoint is that it does not fold. A verdict written in prose can be argued down: push back
hard enough, with no new facts, and the next turn is softer. The base skill defends against that
with written invariants and an anti-sycophancy protocol. Those are instructions, and instructions
are followed by a model that also wants to be agreeable.

TypeSafe AI published in September 2026 an approach aimed exactly at this gap: "System One" models
that take a state and typed questions and return typed values with probability and confidence,
generating no text. Their model, Jev, is hosted and commercial.

That created a direct conflict with two rules of this variant: the judgment engine stays open
source, and the decision state does not leave the environment.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Keep the base skill's prose verdict | Nothing to change, warmest output | Keeps the three defects; the verdict remains argue-downable |
| Adopt the hosted TypeSafe API (Jev) | Excellent calibration and latency, nothing to train | Not open source; the state leaves the environment; per call cost; vendor dependency |
| **Typed decisions with a local open model (openJev-verdict-2.0)** | Apache 2.0; runs locally; same three primitives; calibrated confidence head; zero marginal cost | New ecosystem; checkpoint layout may change; needs a separate service with torch |
| Typed primitives over a local LLM with constrained decoding | Reuses a model that is already served | Probability by self consistency costs N calls per question; slower |

## Decision

Adopt the **typed decision architecture** as the judgment engine of this variant, with
**openJev-verdict-2.0 local as the default backend**.

The layer is vendor agnostic: `scripts/typed_judgment.py` exposes four backends behind one
interface (`openjev`, `local`, `typesafe`, `offline`). Swapping one for another changes no other
line of the flow.

The `typesafe` backend stays available **only as a comparison arbiter**, with the state redacted by
default, never as an operational dependency.

The verdict is composed in code, in `scripts/compose_verdict.py`, with visible coefficients. The
model answers atomic questions; it does not decide.

## Consequences

**Positive.** The verdict becomes a pure function of the state, so the anti-sycophancy invariant is
arithmetic rather than instruction: same state hash, same verdict, whatever the tone of the request.
Confidence becomes a number the code thresholds, which makes uncertainty routing real instead of
rhetorical. Each judgment is isolated and auditable, question by question. Marginal cost per
decision is zero and no state leaves the environment.

**Negative.** One more service to operate, with heavy dependencies. The output is colder and the run
is longer, which is why the base skill remains the default for conversational use. The ecosystem is
recent and the checkpoint may change layout, a risk isolated in the server's `decide` function. The
coefficients are a judgment call: they look objective because they are numbers, and they are not
validated until measured.

**Risks mitigated in code.** If the service is down, the run falls back to deterministic mode and
continues, saying so. An answer outside the domain becomes an abstention, never an invented value.
Coverage below 60% forces an inconclusive verdict. Agreement carries a higher coverage floor (0.80)
than disagreement, so a thin run can never resolve to reassurance.

## Evidence and review

This decision is **provisional until measured**. The criterion for keeping it is running the same
decisions through the base skill and this variant, over four real decisions, and answering:

How often did the typed verdict and the prose verdict differ, and which one held up afterwards.

How often did a pushback turn move the prose verdict while the typed verdict stayed put, and was
staying put correct.

What the abstention and inconclusive rates were, and whether they tracked genuinely thin cases.

Whether the risk index ordered decisions the way a senior reviewer would have ordered them.

If the gain does not hold over those four, the variant is retired and the base skill remains the
only one. A counterpoint that is merely more elaborate is not better.

**Review:** after four full decisions, or on any checkpoint version change.
