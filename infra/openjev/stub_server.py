#!/usr/bin/env python3
"""Deterministic stub for the openJev contract.

    python3 infra/openjev/stub_server.py --port 8099

Answers the same HTTP contract as the real service, using plain rules over the
state. It exists so the whole flow can be validated before any model weights are
downloaded, and so this skill has a judgment path that needs no model at all.

Every answer carries "stub": true, and that flag travels into verdict.json and
into the audit trail. A simulated judgment can never be mistaken for a real one.

Binds to the loopback interface only. It is a local development aid, not a
service to expose.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

MODEL = "openjev-stub-1.0"
MAX_BODY = 1 << 20          # 1 MiB, a stub never needs more


def sourced_evidence(state):
    return [e for e in (state.get("evidence") or [])
            if isinstance(e, dict) and e.get("source") and e.get("kind") != "pattern"]


def noul(value, confidence):
    value = max(0.0, min(1.0, float(value)))
    return {"type": "noul", "noul": round(value, 3),
            "probabilities": {"yes": round(value, 3), "no": round(1.0 - value, 3)},
            "confidence": round(confidence, 3)}


def abstain(kind="noul"):
    """Explicit "do not know". Never send 0.0 for this: zero means "no risk here",
    and a state that says nothing must not read as a state that says it is fine."""
    return {"type": kind, "value": None, "abstain": True,
            "probabilities": {}, "confidence": 0.0}


def judge(state):
    """Plain rules over the state. Deterministic by construction: no randomness,
    no clock, no counter. The same state always produces the same answers."""
    evidence = sourced_evidence(state)
    gaps = state.get("gaps") or []
    reversibility = (state.get("reversibility") or "unknown").lower()
    blast = (state.get("blast_radius") or "unknown").lower()
    deadline = state.get("deadline")
    text = json.dumps(state, ensure_ascii=False).lower()

    def mentioned(*words):
        return any(w in text for w in words)

    out = {}

    # An unrehearsed rollback is the default assumption until the state says otherwise.
    rehearsed = mentioned("rehearsed", "rollback tested", "restore tested", "ensaio", "ensaiado")
    out["rollback_untested"] = noul(0.15 if rehearsed else 0.85, 0.72 if rehearsed else 0.66)

    one_way = reversibility == "one_way"
    two_way = reversibility == "two_way"
    out["one_way_door"] = noul(0.9 if one_way else (0.15 if two_way else 0.5),
                               0.8 if (one_way or two_way) else 0.35)

    # Evidence quality drives this one directly: count sourced entries against gaps.
    if not evidence and not gaps:
        out["evidence_thin"] = abstain()
    else:
        ratio = len(evidence) / float(len(evidence) + len(gaps) or 1)
        out["evidence_thin"] = noul(1.0 - ratio, 0.55 + 0.25 * min(len(evidence), 4) / 4.0)

    if not deadline:
        out["deadline_without_slack"] = abstain()
    else:
        tight = mentioned("end of the month", "fim do mes", "freeze", "public date",
                          "data publica", "go live")
        out["deadline_without_slack"] = noul(0.8 if tight else 0.45, 0.6)

    named = mentioned("owner", "on call", "plantao", "responsavel", "dono")
    out["no_named_owner"] = noul(0.2 if named else 0.75, 0.6 if named else 0.5)

    monitored = mentioned("alert", "monitoring", "alerta", "monitorament", "observability")
    out["monitoring_blind"] = noul(0.25 if monitored else 0.7, 0.55)

    external = mentioned("vendor", "fornecedor", "client approval", "aprovacao do cliente",
                         "procurement", "third party", "terceiro")
    out["external_dependency"] = noul(0.75 if external else 0.3, 0.5)

    precedent = mentioned("tried before", "ja tentamos", "reverted", "rolled back before",
                          "abandonado")
    out["failed_precedent"] = noul(0.8 if precedent else 0.1, 0.65 if precedent else 0.4)

    domain = "architecture"
    for needle, name in (("security", "security"), ("seguranca", "security"),
                         ("cost", "cost"), ("custo", "cost"),
                         ("contract", "vendor"), ("contrato", "vendor"),
                         ("deadline", "delivery"), ("prazo", "delivery"),
                         ("data", "data"), ("dados", "data")):
        if needle in text:
            domain = name
            break
    out["dominant_domain"] = {"type": "choice", "choice": domain,
                              "probabilities": {domain: 0.6}, "confidence": 0.45}

    severity = 2 if (one_way or blast in ("production", "contract", "client")) else 1
    out["severity_of_dominant_risk"] = {"type": "score", "score": severity,
                                        "probabilities": {str(severity): 0.6},
                                        "confidence": 0.5}

    quality = 0 if not evidence else (3 if len(evidence) >= 4 else 2)
    out["evidence_quality"] = {"type": "score", "score": quality,
                               "probabilities": {str(quality): 0.7}, "confidence": 0.55}
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "openjev-stub/1.0"

    def _send(self, code, body):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            self._send(200, {"status": "ok", "model": MODEL, "stub": True})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/decide":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send(400, {"error": "bad content length"})
            return
        if length <= 0 or length > MAX_BODY:
            self._send(400, {"error": "empty or oversized body"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            self._send(400, {"error": "body is not valid json"})
            return

        asked = payload.get("questions") or {}
        computed = judge(payload.get("state") or {})
        answers = {key: computed[key] for key in asked if key in computed}
        self._send(200, {"model": MODEL, "stub": True, "answers": answers})

    def log_message(self, fmt, *args):       # keep the console readable
        return


def main():
    parser = argparse.ArgumentParser(description="Deterministic openJev stub.")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--host", default="127.0.0.1",
                        help="loopback by default, this is a local aid")
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), Handler)
    print("openJev stub on http://{}:{}/v1/decide  (every answer carries stub: true)".format(
        args.host, args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
