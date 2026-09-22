#!/usr/bin/env python3
"""Compose the verdict in code, from typed answers.

    python3 scripts/compose_verdict.py --state working/state.json \
        --config config.yaml --out working/verdict.json

The model answered atomic questions. This file decides, and it is the ONLY place
a verdict is produced. The coefficients are visible in config.yaml: when your
priorities change you edit a number here, instead of rewriting a prompt and
hoping.

Three gates, applied before any verdict is accepted:

  COVERAGE      Below coverage_floor the verdict is inconclusive, whatever the
                answered questions said. Missing evidence is not reassurance.

  AGREEMENT     "No strong reason to disagree" is gated HARDER than disagreement:
                it needs agreement_coverage_floor (default 0.80) and confidence
                at or above act_at. Agreement has to be earned.

  ABSTENTION    An unanswered question lowers coverage. It never becomes the
                comfortable value.

Determinism is the point. The verdict is a pure function of the state: the same
state hash yields the same verdict on any day, whatever tone the request had.
Rhetorical pressure is not a field in the state, so it has no path to the result.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from question_bank import CONTEXT_QUESTIONS, RISK_QUESTIONS, all_questions, default_weights
from typed_judgment import Answer, build_backend, gate, mean_confidence, weighted

DEFAULTS = {
    "backend": "openjev",
    "endpoint": None,
    "model": None,
    "timeout_seconds": 30,
    "fallback_to_offline": True,
    "coverage_floor": 0.60,
    "agreement_coverage_floor": 0.80,
    "act_at": 0.75,
    "review_below": 0.50,
    "would_not_band": 0.60,
    "guardrails_band": 0.35,
}

VERDICTS = {
    "would_not": "would not do it this way",
    "guardrails": "would do it with guardrails",
    "agree": "no strong reason to disagree",
    "inconclusive": "inconclusive, not enough was actually judged",
}


def load_config(path):
    """Read config.yaml. Missing file or missing PyYAML falls back to defaults."""
    cfg = dict(DEFAULTS)
    cfg["coefficients"] = default_weights()
    cfg["notes"] = []
    if not path or not os.path.exists(path):
        cfg["notes"].append("config not found, defaults applied")
        return cfg
    try:
        import yaml
    except ImportError:
        cfg["notes"].append("PyYAML unavailable, defaults applied")
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except Exception as exc:                     # a broken config must not stop the run
        cfg["notes"].append("config unreadable ({}), defaults applied".format(str(exc)[:80]))
        return cfg

    judgment = raw.get("judgment") or {}
    thresholds = raw.get("thresholds") or {}
    for key in ("backend", "endpoint", "model", "timeout_seconds", "fallback_to_offline"):
        if judgment.get(key) is not None:
            cfg[key] = judgment[key]
    for key in ("coverage_floor", "agreement_coverage_floor", "act_at",
                "review_below", "would_not_band", "guardrails_band"):
        if thresholds.get(key) is not None:
            cfg[key] = float(thresholds[key])

    coefficients = raw.get("coefficients") or {}
    known = set(default_weights())
    filtered = {k: float(v) for k, v in coefficients.items() if k in known}
    unknown = [k for k in coefficients if k not in known]
    if unknown:
        cfg["notes"].append("coefficients ignored, no such question: {}".format(", ".join(unknown)))
    if filtered:
        cfg["coefficients"] = filtered

    # The agreement floor may only be stricter than the coverage floor, never looser.
    if cfg["agreement_coverage_floor"] < cfg["coverage_floor"]:
        cfg["agreement_coverage_floor"] = cfg["coverage_floor"]
        cfg["notes"].append("agreement_coverage_floor raised to coverage_floor, it may "
                            "only be stricter")
    return cfg


def normalize(coefficients, notes):
    total = float(sum(coefficients.values()))
    if total <= 0:
        notes.append("coefficients sum to zero, defaults applied")
        return default_weights()
    if abs(total - 1.0) > 0.001:
        notes.append("coefficients summed to {:.3f}, renormalized".format(total))
        return {k: v / total for k, v in coefficients.items()}
    return coefficients


def state_hash(state):
    """Canonical hash of the state. The verdict is a function of exactly this."""
    canonical = json.dumps(state, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def decide(risk_index, coverage, confidence, cfg):
    """The whole decision, in one readable function. No model involved."""
    if coverage < cfg["coverage_floor"]:
        return "inconclusive", ("coverage {:.2f} is below the floor {:.2f}, too little was "
                                "judged to conclude anything".format(coverage,
                                                                     cfg["coverage_floor"]))
    if risk_index >= cfg["would_not_band"]:
        return "would_not", "risk index {:.2f} is at or above {:.2f}".format(
            risk_index, cfg["would_not_band"])
    if risk_index >= cfg["guardrails_band"]:
        return "guardrails", "risk index {:.2f} sits in the guardrail band".format(risk_index)

    # Below the guardrail band, agreement becomes POSSIBLE. It still has to be earned.
    if coverage < cfg["agreement_coverage_floor"]:
        return "guardrails", ("risk index {:.2f} is low, but coverage {:.2f} is below the "
                              "agreement floor {:.2f}: not enough was judged to agree"
                              .format(risk_index, coverage, cfg["agreement_coverage_floor"]))
    if confidence < cfg["act_at"]:
        return "guardrails", ("risk index {:.2f} is low, but confidence {:.2f} is below "
                              "{:.2f}: not confident enough to agree".format(
                                  risk_index, confidence, cfg["act_at"]))
    return "agree", "risk index {:.2f} is low, with coverage {:.2f} and confidence {:.2f}".format(
        risk_index, coverage, confidence)


def run(state, cfg, stored_answers=None):
    notes = list(cfg["notes"])
    questions = all_questions()

    if stored_answers:
        answers = {k: Answer(**v) for k, v in stored_answers.items() if k in questions}
        backend_name = "replay"
        stub = False
    else:
        backend = build_backend(cfg["backend"], endpoint=cfg["endpoint"], model=cfg["model"],
                                timeout=cfg["timeout_seconds"])
        answers = backend.ask(state, questions)
        backend_name = getattr(backend, "name", cfg["backend"])
        if all(a.abstain for a in answers.values()) and backend_name != "offline":
            if cfg["fallback_to_offline"]:
                notes.append("{} answered nothing, fell back to offline".format(backend_name))
                backend_name = "offline (fallback)"
            else:
                notes.append("{} answered nothing and fallback is off".format(backend_name))
        stub = any(getattr(a, "stub", False) for a in answers.values())

    coefficients = normalize(dict(cfg["coefficients"]), notes)
    risk_index, coverage = weighted(answers, coefficients)
    risk_answers = {k: v for k, v in answers.items() if k in RISK_QUESTIONS}
    confidence = mean_confidence(risk_answers)
    key, reason = decide(risk_index, coverage, confidence, cfg)

    return {
        "verdict": VERDICTS[key],
        "verdict_key": key,
        "reason": reason,
        "risk_index": round(risk_index, 4),
        "coverage": round(coverage, 4),
        "confidence": round(confidence, 4),
        "routing": gate(confidence, cfg["act_at"], cfg["review_below"]),
        "state_hash": state_hash(state),
        "backend": backend_name,
        "stub": stub,
        "coefficients": {k: round(v, 4) for k, v in coefficients.items()},
        "thresholds": {k: cfg[k] for k in ("coverage_floor", "agreement_coverage_floor",
                                           "act_at", "review_below", "would_not_band",
                                           "guardrails_band")},
        "answers": {k: v.to_dict() for k, v in answers.items()},
        "abstained": sorted(k for k, v in answers.items() if v.abstain),
        "context": {k: answers[k].to_dict() for k in CONTEXT_QUESTIONS if k in answers},
        "notes": notes,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compose a typed verdict from a decision state.")
    parser.add_argument("--state", required=True, help="path to state.json")
    parser.add_argument("--config", default="config.yaml", help="path to config.yaml")
    parser.add_argument("--answers", default=None,
                        help="replay a stored answers file instead of asking a backend")
    parser.add_argument("--out", default=None, help="where to write verdict.json")
    args = parser.parse_args(argv)

    with open(args.state, "r", encoding="utf-8") as handle:
        state = json.load(handle)
    stored = None
    if args.answers and os.path.exists(args.answers):
        with open(args.answers, "r", encoding="utf-8") as handle:
            stored = json.load(handle).get("answers")

    result = run(state, load_config(args.config), stored)

    if args.out:
        directory = os.path.dirname(os.path.abspath(args.out))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)

    print(json.dumps({k: result[k] for k in
                      ("verdict", "reason", "risk_index", "coverage", "confidence",
                       "routing", "state_hash", "backend", "stub", "abstained", "notes")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
