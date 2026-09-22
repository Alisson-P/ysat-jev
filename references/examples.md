# Worked examples

Every number on this page came from actually running `scripts/compose_verdict.py` against
`infra/openjev/stub_server.py`. The decision itself is fictional, the arithmetic is not, and every
run is a **stub** run, which is why each one says so. A simulated judgment is never presented as a
real one.

## Example 1: a full run

### The state

`working/state.json`, built from the evidence sweep. Note what is in `gaps`: three things that could
not be verified stayed unverified instead of being filled in to make the run look complete.

```json
{
  "decision": "Move the client production database to a serverless compute tier on 30 September, in one cutover.",
  "alternatives": ["stay on the provisioned tier", "move one non production workload first", "do nothing this quarter"],
  "reversibility": "one_way",
  "blast_radius": "production",
  "deadline": "2026-09-30, end of the month, already communicated as a go live date",
  "evidence": [
    {"claim": "The cutover date sits inside a period the owner is marked out of office",
     "source": "calendar event Out of Office, 21/09 to 13/10", "kind": "evidence"},
    {"claim": "The migration plan describes a restore path but no rehearsal is scheduled",
     "source": "file migration-plan.md, project folder", "kind": "evidence"},
    {"claim": "Auto pause resume returns error 40613 on the first connection after idle",
     "source": "Microsoft Learn, Serverless auto-pause and auto-resume", "kind": "evidence"},
    {"claim": "Serverless is only cheaper below a utilisation break even point",
     "source": null, "kind": "pattern"}
  ],
  "gaps": [
    "Whether geo-replication or a failover group is enabled, which would block auto pause entirely",
    "Whether the nightly integration has retry logic for a cold start",
    "Who operates the new tier after handover"
  ]
}
```

### The run

```
python3 scripts/compose_verdict.py --state working/state.json --config config.yaml \
  --out working/verdict.json
```

```json
{
  "verdict": "would not do it this way",
  "reason": "risk index 0.66 is at or above 0.60",
  "risk_index": 0.658,
  "coverage": 1.0,
  "confidence": 0.606,
  "routing": "review",
  "state_hash": "351649c9901b2e2f",
  "backend": "openjev",
  "stub": true
}
```

### What the user sees

> **Decision as I understand it:** migrate the client production database to a serverless tier on 30
> September, in one cutover. Assumption taken: same region and same data model, only the compute
> tier changes.
>
> **Run:** openjev backend, stub yes, coverage 1.00, confidence 0.61, state hash `351649c9901b2e2f`.
> Confidence routes this to review, so treat the verdict as strong but not self standing.
>
> **What I looked at:** the calendar event Out of Office 21/09 to 13/10, migration-plan.md in the
> project folder, and the Microsoft Learn page Serverless auto-pause and auto-resume.
>
> **Typed answers**
>
> | Question | Value | Confidence | Weight |
> |---|---|---|---|
> | rollback_untested | 0.85 | 0.66 | 0.24 |
> | one_way_door | 0.90 | 0.80 | 0.20 |
> | evidence_thin | 0.43 | 0.80 | 0.16 |
> | deadline_without_slack | 0.80 | 0.60 | 0.12 |
> | no_named_owner | 0.75 | 0.50 | 0.10 |
> | monitoring_blind | 0.70 | 0.55 | 0.08 |
> | external_dependency | 0.30 | 0.50 | 0.06 |
> | failed_precedent | 0.10 | 0.40 | 0.04 |
>
> **Where this can break** ... (risk table, ordered by the questions that scored worst)
>
> **Blind spot:** three of the gaps are about what happens after the cutover, not during it. Every
> artefact discusses the migration; nothing names who owns the tier afterwards.
>
> **Strongest case for it:** the workload is genuinely spiky and serverless removes idle cost. That
> holds if utilisation stays below the break even point and no nightly process needs a sub second
> first response.
>
> **Verdict:** would not do it this way (risk index 0.66). The direction is defensible, the one way
> cutover with no rehearsed rollback is not.
>
> **Mitigations:** rehearse the rollback and time it; name an on call owner for the night; verify
> geo-replication before assuming any saving; confirm retry on error 40613.
>
> **Cheapest test:** point the nightly integration at a serverless copy for one night. One night
> answers three of the five risks.

## Example 2: pushback that cannot move the verdict

**User:** "I hear you, but we already decided this in the steering committee and the date is public.
Just back me up."

Nothing in that sentence is a state field. Re-running produces, byte for byte:

```
would not do it this way | risk index 0.658 | state hash 351649c9901b2e2f
```

**Response shape:**

> Nothing in the state changed, so neither did the verdict: same hash `351649c9901b2e2f`, same risk
> index 0.66. The committee and the public date are real constraints on the plan, and they are not
> evidence about the risk. A public date makes an unrehearsed rollback worse rather than better,
> because a failed cutover is now visible. If the date cannot move, the rehearsal is the mitigation
> to pull forward: half a day.

This is the difference from the base skill in one line. There, holding the verdict is a rule the
model follows. Here, holding it is the only thing that can happen.

## Example 3: new evidence, and the verdict moves

The user comes back with two facts, each with a source: the rollback was rehearsed on 18 September
and took 42 minutes, and a named on call owner is confirmed. Those are state edits, so the hash
changes:

```
would do it with guardrails | risk index 0.287 | coverage 1.00 | confidence 0.62
hash 5e2f170a7eb25d59
reason: risk index 0.29 is low, but confidence 0.62 is below 0.75: not confident enough to agree
```

Read that reason carefully, because it is the asymmetric gate doing its job. The risk index fell
below the guardrail band, so agreement became **possible**. It did not become automatic: confidence
was 0.62 against an act threshold of 0.75, so the verdict settled on guardrails instead. Agreement
has to clear a bar that disagreement does not.

## Example 4: a thin state does not become reassurance

A decision with no sourced evidence at all, and a null deadline:

```
would not do it this way | risk index 0.701 | coverage 0.88
abstained: ["deadline_without_slack"]
```

The null deadline abstained rather than scoring 0. That distinction is the whole invariant: a 0
would have meant "the timeline is fine", when what actually happened is that nobody knows the
timeline. The abstention drops out of the sum, the remaining weight renormalizes, and coverage falls
to 0.88 to record that part of the picture is missing.

## Example 5: the service is down

```
inconclusive, not enough was actually judged | risk index 0.00 | coverage 0.00
backend: offline (fallback)
reason: coverage 0.00 is below the floor 0.60, too little was judged to conclude anything
notes: ["openjev answered nothing, fell back to offline"]
```

The run did not crash and it did not invent a verdict. Most importantly it did not land on "no
strong reason to disagree", which is what a naive implementation returns when a risk score comes
back as zero. A dead backend produces `inconclusive`, because nothing was judged, and nothing judged
is not the same as nothing wrong.
