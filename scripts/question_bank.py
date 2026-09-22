#!/usr/bin/env python3
"""The atomic question bank for ysat-jev.

This is the most important rule of the layer, and the easiest one to break:
ONE question, ONE judgment.

A broad question hides several judgments behind a single answer. "Is this
decision bad?" mixes at least eight independent assessments, and when the answer
comes back wrong you cannot tell which one failed. Each question below is
evaluated in isolation against the same state, and no answer is ever fed into
another question as hidden context.

The keys here are the keys the coefficients in config.yaml refer to. Adding a
question without giving it a coefficient means it is recorded in the audit trail
but does not move the risk index, which is a legitimate way to observe a signal
before trusting it.
"""
from typed_judgment import Choice, Noul, Score

# Every Noul is phrased so that 1.0 means MORE RISK. That single convention is
# what lets the composition be a plain weighted sum with no sign juggling, and it
# is why the keys read as problems ("rollback_untested") and not as virtues.

RISK_QUESTIONS = {
    "rollback_untested": Noul(
        {"statement": "There is no rehearsed, timed way back from this decision.",
         "note": "A documented rollback that was never executed counts as untested."},
        {"yes": "No rollback, or one that exists only on paper.",
         "no": "A rollback was executed at least once and its duration is known."},
        weight=0.24),

    "one_way_door": Noul(
        {"statement": "Undoing this decision later is expensive or impractical.",
         "note": "Judge the cost of reversal, not the cost of the decision itself."},
        {"yes": "Reversal means migration, renegotiation, rewrite or contractual exit.",
         "no": "Reversal is a configuration change, a flag, or a few days of work."},
        weight=0.20),

    "evidence_thin": Noul(
        {"statement": "The case for this decision rests on expectation rather than "
                      "measured evidence in the provided state.",
         "note": "Count only evidence entries carrying a source. Entries marked as "
                 "pattern are not evidence about this context."},
        {"yes": "The state carries no sourced evidence for the load bearing claims.",
         "no": "Load bearing claims each trace to a named source in the state."},
        weight=0.16),

    "deadline_without_slack": Noul(
        {"statement": "The timeline cannot absorb one bad surprise.",
         "note": "A null deadline is not slack, it is an unknown. Abstain instead."},
        {"yes": "Any single delay pushes past the committed date.",
         "no": "There is room for at least one failure and a retry."},
        weight=0.12),

    "no_named_owner": Noul(
        {"statement": "No named person is confirmed to operate this after the change.",
         "note": "Frame as role and coverage. Never judge a person's competence."},
        {"yes": "Ownership after handover is unassigned or implied.",
         "no": "A named role or person is confirmed, including out of hours."},
        weight=0.10),

    "monitoring_blind": Noul(
        {"statement": "A failure on the new path would be noticed by a human or a "
                      "customer before it is noticed by instrumentation.",
         "note": "Existing monitoring of the OLD path does not count."},
        {"yes": "No alert, metric or log covers the new path.",
         "no": "The new path emits a signal that alerts someone."},
        weight=0.08),

    "external_dependency": Noul(
        {"statement": "Success depends on parties outside the team's control landing "
                      "on time.",
         "note": "Vendors, other teams, client approvals, procurement."},
        {"yes": "At least one external party must deliver for this to hold.",
         "no": "Everything load bearing is inside the team's control."},
        weight=0.06),

    "failed_precedent": Noul(
        {"statement": "Something equivalent was attempted here before and did not hold.",
         "note": "Only when the state carries a sourced record of the earlier attempt."},
        {"yes": "The state records a prior attempt that was reverted or abandoned.",
         "no": "No prior attempt is recorded."},
        weight=0.04),
}

# Observed but NOT yet in the risk index. They shape the write up, the severity
# and the blind spot line. Give one a coefficient in config.yaml once you have
# measured that it predicts anything.
CONTEXT_QUESTIONS = {
    "dominant_domain": Choice(
        {"question": "Which domain carries the dominant risk of this decision?"},
        {"architecture": "Design, coupling, scale limits, single points of failure.",
         "security": "Access, credentials, exposure, controls bypassed.",
         "data": "Loss, migration, residency, retention, broken consumers.",
         "cost": "Growth variable, licensing, exit cost, budget.",
         "operations": "Who runs it, monitoring, runbook, out of hours.",
         "delivery": "Schedule, dependencies, freeze windows, scope.",
         "vendor": "Contract, lock in, roadmap, support lifecycle.",
         "people": "Process, single point of knowledge, adoption.",
         "compliance": "Policy, regulation, auditability."}),

    "severity_of_dominant_risk": Score(
        {"question": "How severe is the dominant risk, on the fixed scale?"},
        ["low: operational annoyance, cheap to fix later",
         "medium: material rework, deadline slip, recurring cost above plan",
         "high: data loss, outage, contract or compliance breach, irreversible cost"]),

    "evidence_quality": Score(
        {"question": "What is the strongest kind of evidence the state carries for "
                     "the load bearing claims?"},
        ["none: assertion only",
         "anecdote: recalled or second hand, no source",
         "documented: a named source states it",
         "measured: a number obtained from this environment"]),
}


def all_questions():
    """Every question asked in a run, risk bearing first."""
    merged = dict(RISK_QUESTIONS)
    merged.update(CONTEXT_QUESTIONS)
    return merged


def default_weights():
    """Fallback coefficients, used when config.yaml carries none."""
    return {key: q.weight for key, q in RISK_QUESTIONS.items()}
