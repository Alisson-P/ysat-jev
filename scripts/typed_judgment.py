#!/usr/bin/env python3
"""Typed judgment layer for ysat-jev.

The model never writes a verdict here. It answers ATOMIC TYPED QUESTIONS about a
decision state, and the verdict is composed in code by compose_verdict.py.

Three primitives, following the System One shape:

    Noul    Is this statement true?          -> a number between 0 and 1
    Choice  Which of these options?          -> the option, distribution, confidence
    Score   Which level on this rubric?      -> the level, distribution, confidence

Four backends behind one interface, so swapping one changes no other line:

    openjev   openJev-verdict-2.0 served locally (default)
    local     a served language model, probability by self consistency
    typesafe  hosted API, comparison arbiter only, state leaves the environment
    offline   deterministic rules, the safety net and the automatic fallback

Nothing outside a question's domain is ever accepted. A value that does not fit
comes back as an ABSTENTION with confidence 0, which the composition reads as
"do not know" and never as "no".
"""
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter

DEFAULT_TIMEOUT = 60
USER_AGENT = "ysat-jev-typed-judgment/1.0"


# ------------------------------------------------------------------ questions

class Question(object):
    """Base of the three primitives. instructions and criteria accept str or dict."""

    kind = "base"

    def __init__(self, instructions, criteria=None, weight=1.0):
        self.instructions = instructions
        self.criteria = criteria
        self.weight = weight

    def payload(self):
        body = {"type": self.kind, "instructions": self.instructions}
        if self.criteria is not None:
            body["criteria"] = self.criteria
        return body

    def domain(self):
        """Values the answer may take. Nothing outside this is accepted."""
        raise NotImplementedError


class Noul(Question):
    """Is the statement true? Answer between 0 and 1."""

    kind = "noul"

    def domain(self):
        return ["yes", "no"]


class Choice(Question):
    """Pick one option. criteria is the option -> description map."""

    kind = "choice"

    def __init__(self, instructions, criteria, weight=1.0):
        Question.__init__(self, instructions, criteria, weight)

    def domain(self):
        return list(self.criteria.keys())


class Score(Question):
    """Rate the state on a rubric. criteria is the level list, lowest first."""

    kind = "score"

    def __init__(self, instructions, criteria, weight=1.0):
        Question.__init__(self, instructions, criteria, weight)

    def domain(self):
        return [str(i) for i in range(len(self.criteria))]


# -------------------------------------------------------------------- answer

class Answer(object):
    """A typed answer. Never carries prose: value, distribution and confidence only."""

    def __init__(self, kind, value=None, probabilities=None, confidence=0.0,
                 abstain=False, backend="offline", note="", stub=False):
        self.kind = kind
        self.value = value
        self.probabilities = probabilities or {}
        self.confidence = float(confidence)
        self.abstain = bool(abstain)
        self.backend = backend
        self.note = note
        self.stub = bool(stub)

    @property
    def noul(self):
        return float(self.value) if self.kind == "noul" and self.value is not None else 0.0

    @property
    def choice(self):
        return self.value if self.kind == "choice" else None

    @property
    def score(self):
        return float(self.value) if self.kind == "score" and self.value is not None else 0.0

    def to_dict(self):
        return {"kind": self.kind, "value": self.value,
                "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
                "confidence": round(self.confidence, 4), "abstain": self.abstain,
                "backend": self.backend, "note": self.note, "stub": self.stub}

    def __repr__(self):
        return "Answer({}={}, conf={:.2f}, backend={})".format(
            self.kind, self.value, self.confidence, self.backend)


def abstained(question, backend, note):
    return Answer(question.kind, None, {}, 0.0, True, backend, note)


# ------------------------------------------------------------------ backends

class OfflineBackend(object):
    """No model at all. Every question abstains and the code proceeds on its rules.

    This is the safety net: the whole flow has to work with no judgment service
    running. A fully abstained run has coverage 0, which lands on inconclusive,
    which is the honest outcome when nothing was actually judged.
    """

    name = "offline"

    def ask(self, state, questions):
        return {k: abstained(q, self.name, "offline mode, no judgment service")
                for k, q in questions.items()}


class OpenJevBackend(object):
    """openJev-verdict-2.0 served locally. The DEFAULT backend of this variant.

    An open decision model (Apache 2.0) trained for the same Choice, Score and
    Noul primitives. It does not generate text: one forward pass returns a
    probability distribution over the options plus a dedicated, calibrated
    confidence head.

    Practical difference against the `local` backend: the probability comes from
    the model itself rather than from asking the same question N times. One
    question costs one pass instead of N calls.

    To run the service, see infra/openjev/README.md. The HTTP contract is
    documented there and is deliberately plain, which keeps this layer free of
    any machine learning library dependency.
    """

    name = "openjev"

    def __init__(self, endpoint=None, timeout=30, model=None):
        self.endpoint = endpoint or os.environ.get(
            "OPENJEV_ENDPOINT", "http://localhost:8099/v1/decide")
        self.timeout = timeout
        self.model = model or os.environ.get("OPENJEV_MODEL", "openjev-verdict-2.0")

    def ask(self, state, questions):
        body = {"model": self.model, "state": state,
                "questions": {k: q.payload() for k, q in questions.items()}}
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        req = urllib.request.Request(self.endpoint, data=json.dumps(body).encode("utf-8"),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return {k: abstained(q, self.name,
                                 "openJev service unavailable: {}".format(str(exc)[:140]))
                    for k, q in questions.items()}

        stub = bool(raw.get("stub"))
        answers = raw.get("answers", raw)
        out = {}
        for key, q in questions.items():
            item = answers.get(key)
            if not isinstance(item, dict):
                out[key] = abstained(q, self.name, "answer missing")
                continue
            probs = {k: float(v) for k, v in (item.get("probabilities") or {}).items()}
            conf = float(item.get("confidence", 0.0) or 0.0)
            allowed = q.domain()

            if item.get("abstain"):
                out[key] = abstained(q, self.name, "backend abstained")
                continue

            if q.kind == "noul":
                value = item.get("noul", item.get("value"))
                if value is None:
                    # A null value is NOT zero. Zero is the comfortable answer, and reading
                    # an unanswered question as "no risk here" is the exact failure this
                    # skill exists to prevent. Recover a value only from a real
                    # distribution; otherwise abstain and let coverage carry the signal.
                    if "yes" in probs or "true" in probs:
                        value = probs.get("yes", probs.get("true"))
                    else:
                        out[key] = abstained(q, self.name, "no value and no distribution")
                        continue
                out[key] = Answer("noul", float(value), probs, conf, False, self.name, "", stub)
            elif q.kind == "choice":
                value = item.get("choice", item.get("value"))
                if value not in allowed:        # gate: nothing outside the domain gets in
                    out[key] = abstained(q, self.name, "value outside domain")
                    continue
                out[key] = Answer("choice", value, probs, conf, False, self.name, "", stub)
            else:
                value = item.get("score", item.get("value"))
                out[key] = Answer("score", float(value or 0.0), probs, conf,
                                  False, self.name, "", stub)
        return out


class LocalBackend(object):
    """A served language model, constrained to the domain, probability by voting.

    Use it when a model is already served and you would rather not run another
    service. It costs N calls per question, so it is slower, and the probability
    is an estimate by repetition rather than a calibrated head.
    """

    name = "local"

    def __init__(self, endpoint=None, model=None, samples=5, timeout=DEFAULT_TIMEOUT,
                 api_key=None, temperature=0.7):
        self.endpoint = endpoint or os.environ.get(
            "LOCAL_LLM_ENDPOINT", "http://localhost:11434/v1/chat/completions")
        self.model = model or os.environ.get("LOCAL_LLM_MODEL", "llama3.1")
        self.samples = max(1, int(samples))
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("LOCAL_LLM_KEY", "")
        self.temperature = temperature

    def _prompt(self, state, question):
        allowed = ", ".join(question.domain())
        return ("Answer with ONE token from this list and nothing else: {}\n\n"
                "State:\n{}\n\nQuestion:\n{}\n").format(
                    allowed, json.dumps(state, ensure_ascii=False, indent=1)[:4000],
                    json.dumps(question.instructions, ensure_ascii=False))

    def _call(self, prompt):
        body = {"model": self.model, "temperature": self.temperature,
                "messages": [{"role": "user", "content": prompt}]}
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self.api_key:
            headers["Authorization"] = "Bearer {}".format(self.api_key)
        req = urllib.request.Request(self.endpoint, data=json.dumps(body).encode("utf-8"),
                                     headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        return raw["choices"][0]["message"]["content"]

    @staticmethod
    def _match(text, allowed):
        low = (text or "").strip().lower()
        for option in allowed:
            if re.search(r"\b{}\b".format(re.escape(option.lower())), low):
                return option
        return None

    def ask(self, state, questions):
        out = {}
        for key, q in questions.items():
            allowed = q.domain()
            votes = []
            for _ in range(self.samples):
                try:
                    votes.append(self._match(self._call(self._prompt(state, q)), allowed))
                except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
                    votes.append(None)
            out[key] = self._consolidate(q, votes, allowed)
        return out

    def _consolidate(self, question, votes, allowed):
        valid = [v for v in votes if v in allowed]
        if not valid:
            return abstained(question, self.name, "no answer inside the domain")
        counts = Counter(valid)
        winner, n = counts.most_common(1)[0]
        probs = {k: counts.get(k, 0) / float(len(valid)) for k in allowed}
        confidence = round(n / float(len(votes)), 4)   # abstentions count against confidence
        if question.kind == "noul":
            return Answer("noul", probs.get("yes", 0.0), probs, confidence, False, self.name)
        if question.kind == "choice":
            return Answer("choice", winner, probs, confidence, False, self.name)
        return Answer("score", float(winner), probs, confidence, False, self.name)


class TypeSafeBackend(object):
    """Hosted TypeSafe API (model Jev).

    SCOPE WARNING: the state you send LEAVES your environment. In this variant it
    exists as a COMPARISON ARBITER only, never as an operational dependency, and
    the state is redacted by default. Ask the user before enabling it.
    """

    name = "typesafe"

    REDACT_KEYS = ("evidence", "gaps", "decision")

    def __init__(self, api_key=None, endpoint=None, timeout=30, redact=True):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        self.endpoint = endpoint or os.environ.get(
            "TYPESAFE_ENDPOINT", "https://api.typesafe.ai/v1/decide")
        self.timeout = timeout
        self.redact = redact

    def _redacted(self, state):
        if not self.redact:
            return state
        safe = {k: v for k, v in state.items() if k not in self.REDACT_KEYS}
        safe["redacted"] = True
        safe["evidence_count"] = len(state.get("evidence") or [])
        safe["gap_count"] = len(state.get("gaps") or [])
        return safe

    def ask(self, state, questions):
        if not self.api_key:
            return {k: abstained(q, self.name, "no API key configured")
                    for k, q in questions.items()}
        body = {"state": self._redacted(state),
                "questions": {k: q.payload() for k, q in questions.items()}}
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT,
                   "Authorization": "Bearer {}".format(self.api_key)}
        req = urllib.request.Request(self.endpoint, data=json.dumps(body).encode("utf-8"),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return {k: abstained(q, self.name, "request failed: {}".format(str(exc)[:140]))
                    for k, q in questions.items()}
        answers = raw.get("answers", raw)
        out = {}
        for key, q in questions.items():
            item = answers.get(key)
            if not isinstance(item, dict):
                out[key] = abstained(q, self.name, "answer missing")
                continue
            value = item.get("value", item.get(q.kind))
            if q.kind == "choice" and value not in q.domain():
                out[key] = abstained(q, self.name, "value outside domain")
                continue
            probs = {k: float(v) for k, v in (item.get("probabilities") or {}).items()}
            out[key] = Answer(q.kind, value, probs,
                              float(item.get("confidence", 0.0) or 0.0), False, self.name)
        return out


BACKENDS = {"offline": OfflineBackend, "openjev": OpenJevBackend,
            "local": LocalBackend, "typesafe": TypeSafeBackend}


def build_backend(name, **kwargs):
    """Backend factory. An unknown name falls back to offline, it never breaks the run."""
    cls = BACKENDS.get((name or "offline").lower(), OfflineBackend)
    if cls is OfflineBackend:
        return cls()
    accepted = {"openjev": ("endpoint", "timeout", "model"),
                "local": ("endpoint", "model", "samples", "timeout", "api_key", "temperature"),
                "typesafe": ("api_key", "endpoint", "timeout", "redact")}[cls.name]
    return cls(**{k: v for k, v in kwargs.items() if k in accepted and v is not None})


# --------------------------------------------------------------- composition

def weighted(answers, weights, default=0.0):
    """Weighted sum of Nouls, dropping abstentions and renormalizing the weight.

    Returns (value, coverage). Coverage is the fraction of total weight that came
    back answered. A low coverage value must never decide on its own, which is
    what the coverage floors in compose_verdict.py enforce.
    """
    total_valid, weight_valid = 0.0, 0.0
    for key, weight in weights.items():
        a = answers.get(key)
        if a is None or a.abstain:
            continue
        total_valid += weight * a.noul
        weight_valid += weight
    weight_total = float(sum(weights.values())) or 1.0
    if weight_valid == 0:
        return default, 0.0
    return round(total_valid / weight_valid, 4), round(weight_valid / weight_total, 4)


def mean_confidence(answers):
    """Mean confidence over the answers that did not abstain. 0.0 when all abstained."""
    values = [a.confidence for a in answers.values() if not a.abstain]
    return round(sum(values) / float(len(values)), 4) if values else 0.0


def gate(confidence, act_at=0.75, review_below=0.50):
    """Uncertainty routing: act, review or escalate. Thresholds come from config."""
    if confidence < review_below:
        return "escalate"
    if confidence < act_at:
        return "review"
    return "act"
