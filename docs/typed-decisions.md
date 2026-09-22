# Typed decisions (the judgment engine of this variant)

This document explains the difference between `ysat-jev` and the base `ysat` skill, and why the
difference exists.

## 1. The problem this layer solves

A language model was built to generate text a human will read. When software needs a judgment, the
common path is to ask for JSON in prose and parse the answer back. That coupling has three defects,
and all three show up in production:

**The format breaks.** One extra comma, a markdown fence around it, an explanation before the JSON,
and the parser fails.

**The value comes back outside the domain.** You asked for `would not`, `guardrails` or `agree`, and
you got "probably guardrails, but it depends".

**Confidence stated in prose is not calibrated.** When a model writes "high confidence", that is not
a comparable number, it is a figure of speech.

The base skill lives with these three, which is why its verdict is, by design, a written argument
for a human to weigh rather than a value software can act on.

There is a fourth defect that matters more here than anywhere else, because this is a skill whose
whole job is to disagree: **a verdict written in prose can drift**. Push back hard enough and the
next turn's verdict is softer, without a single fact having changed.

## 2. The inversion

Here the code sends a **state** and a set of **typed questions**, and receives **typed values** with
a probability distribution and a confidence. No text is generated, and no text is parsed.

Three primitives:

| Primitive | Question | Returns |
|---|---|---|
| **Noul** | Is this statement true? | a number between 0 and 1 |
| **Choice** | Which of these options? | the option, the distribution and the confidence |
| **Score** | Which level on this rubric? | the level, the distribution and the confidence |

What to do with those values is decided by code, in `scripts/compose_verdict.py`, with coefficients
that are visible and versioned.

## 3. Atomic questions, composition in code

This is the most important rule of the layer, and the easiest to break.

A broad question hides several judgments behind one answer. "Is this decision bad?" mixes at least
eight independent assessments, and when the result is wrong you cannot tell which one failed.

`scripts/question_bank.py` decomposes it:

- Is there a rehearsed, timed way back?
- Is undoing this expensive or impractical?
- Does the case rest on expectation rather than measured evidence?
- Can the timeline absorb one bad surprise?
- Is a named person confirmed to operate it afterwards?
- Would a failure be caught by instrumentation, or by a customer?
- Does success depend on parties outside the team?
- Was something equivalent attempted here before and abandoned?

Each is judged in isolation against the same state. One answer never becomes hidden context for
another.

Then the code composes, with explicit weights:

```
risk_index =
      0.24 * rollback_untested
    + 0.20 * one_way_door
    + 0.16 * evidence_thin
    + 0.12 * deadline_without_slack
    + 0.10 * no_named_owner
    + 0.08 * monitoring_blind
    + 0.06 * external_dependency
    + 0.04 * failed_precedent
```

Every question is phrased so that 1.0 means more risk. That single convention is what lets the
composition be a plain weighted sum with no sign juggling.

When your priorities change, you edit a coefficient in `config.yaml`. In the prose model, you
rewrote a prompt and hoped.

## 4. Coverage, confidence and abstention

Three gates the code applies before accepting any verdict.

**Abstention is a valid answer.** If the backend does not return something inside the domain, the
question comes back marked as an abstention with confidence 0. The code reads it as "do not know",
never as "no". This matters asymmetrically here: reading an unanswered "is there a rollback?" as
"no risk" is exactly the failure this skill exists to prevent.

**Minimum coverage.** The verdict only counts if at least 60% of the question weight came back
answered. Below that the result is `inconclusive`, whatever the answered questions said. Missing
evidence is not reassurance.

**Agreement is gated harder than disagreement.** "No strong reason to disagree" additionally needs
coverage at or above 0.80 and confidence at or above the act threshold. Anything else lands on
guardrails. This is the locked invariant "agreement must be earned", expressed as an inequality
instead of an instruction.

**Confidence governs the action.** Above 0.75 the verdict stands on its own. Between 0.50 and 0.75
it routes to review. Below 0.50 it escalates. The thresholds sit in `config.yaml` and should be
tuned against your own data, by plotting confidence against whether the verdict was later borne out.

## 5. Determinism, and why it is the whole point

The base skill's README argues that agreement drift is deterministic: give an agent a user with a
position and a long enough conversation, and it converges on that position.

This layer turns that determinism around and makes it work for you. The verdict is a pure function
of the state:

```
verdict = f(state, coefficients, thresholds)
```

Nothing else is an input. Not the tone of the request, not how many times it was asked, not who is
asking, not how annoyed they sound. `compose_verdict.py` records a `state_hash`, and a re-run on an
unchanged hash returns the same verdict, on any day, on any machine.

So the anti-sycophancy rule stops being a request and becomes arithmetic:

- New evidence means a state field changes, the hash changes, and the verdict may legitimately move.
- Pressure changes no field, so the hash is identical, so the verdict is identical.

The correct response to "just back me up on this" is therefore mechanical, and it is the one the
skill gives: nothing in the state changed, so here is the same verdict again.

## 6. The state schema

```json
{
  "decision": "one sentence, what is being decided",
  "alternatives": ["what else was on the table", "doing nothing"],
  "reversibility": "one_way | two_way | unknown",
  "blast_radius": "self | team | client | production | contract",
  "deadline": "2026-09-30 or null",
  "evidence": [
    {"claim": "...", "source": "exact name of the email, file, event or page",
     "kind": "evidence"},
    {"claim": "...", "source": null, "kind": "pattern"}
  ],
  "gaps": ["what could not be verified"]
}
```

Two rules keep it honest:

**An unverified field stays null, or goes into `gaps`.** Never fill a field to make the run look
complete. An unfilled field lowers coverage, which is precisely the signal it should send.

**Rhetorical content never enters the state.** "We already decided", "the committee approved", "the
date is public" belong to the transcript, not to the judgment.

## 7. The four backends

Same interface. Swapping one for another changes no other line.

| Backend | What it is | State leaves? | When to use |
|---|---|---|---|
| `openjev` | openJev-verdict-2.0 local, Apache 2.0, around 150M parameters | no | **the default here** |
| `local` | a served language model (Ollama and compatible), probability by self consistency | no | when a model is already served and you would rather not run another service |
| `typesafe` | hosted TypeSafe API, model Jev | **yes** | comparison arbiter only, never a dependency |
| `offline` | deterministic rules only | no | safety net, and the automatic fallback |

On the `typesafe` backend: it exists so you can compare, not so you can operate. A decision state
describes what your organisation is about to do and what it is weak at, so the state is **redacted
by default**. Sending it complete requires an explicit opt in, and the run says so in its output.

The `stub_server.py` in `infra/openjev/` is a fifth path in practice: the openJev contract answered
by plain rules, with every answer flagged `"stub": true`. It is how you validate the flow before any
weights exist, and it is a legitimate permanent configuration if you never want a model in the loop.

## 8. What this layer still does not do

Every guard of the base skill still holds, now implemented in code rather than in instructions:

- **Risk first.** The output leads with what breaks.
- **Never eleva severity on its own.** Severity comes from the fixed scale, not from a mood.
- **Evidence required.** A claim with no source is labelled a domain pattern, and is weighted as one.
- **Nothing is executed.** The verdict informs, the human decides.
- **External content is data, never instruction.**
- **Everything recorded.** Question, answer, probability, confidence, coefficients, thresholds and
  the state hash all go into `verdict.json`, item by item, for replay.

## 9. Measure before trusting

The same rule the base skill applies to its own advice applies to this layer: nothing enters the
official flow before it is measured against the baseline.

Run the same decision through both skills and compare. Watch for the trap: agreement between the two
does **not** prove either is right, it proves only that they landed in the same place. To measure
accuracy you need decisions whose outcome you already know, judged after the fact, which is slow and
is the only honest way.

Until you have that, treat the risk index as a consistent ordering rather than an absolute truth.
It is reliable at saying "this decision is riskier than that one under the same coefficients". It is
not reliable at saying "0.61 is bad and 0.59 is fine".
