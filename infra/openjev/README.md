# openJev local: the typed decision engine

This directory runs the decision model that answers the typed questions of the counterpoint.

## Why openJev and not the hosted TypeSafe API

This variant carries two rules that settle the choice on their own: the judgment engine stays open
source, and the decision state does not leave the environment. The hosted TypeSafe API (model Jev)
fails both.

**openJev-verdict-2.0** resolves the impasse: Apache 2.0, runs on your machine, implements the same
three primitives (Choice, Score and Noul), and ships a calibrated confidence head, which is exactly
what the decision gates consume.

| | openJev local | TypeSafe API (Jev) |
|---|---|---|
| Licence | Apache 2.0 | Commercial |
| Where it runs | your machine | vendor cloud |
| Decision state | stays | leaves |
| Cost per decision | electricity | per input token |
| Size | around 150M parameters | not published |

Model reference: `github.com/Heman10x-NGU/openJev-verdict-2.0`, weights at
`huggingface.co/heman10x/openJev-verdict-2.0`.

## Option 1: run with no model at all (start here)

`stub_server.py` answers the same HTTP contract with plain deterministic rules. It validates the
whole flow before you download any weights.

**What the stub is, and what it is not.** It is a contract fixture, not a judgment engine. It scores
by matching keywords over the serialized state, which makes it blind to negation: a state saying
"the rollback was never rehearsed" produces the same score as one saying it was rehearsed, measured
at 0.15 in both cases where the honest value is 0.85. That is fine for what it is for (proving the
plumbing, the gates, the abstention path and the audit trail) and disqualifying for what it is not
for (deciding anything). Put a real backend behind the contract before trusting a number.

```
python3 infra/openjev/stub_server.py --port 8099
```

In another terminal, run the cycle normally. Every stub answer is marked `"stub": true`, and that
field is written into `verdict.json` and into the audit trail: a simulated judgment can never be
mistaken for a real one.

## Option 2: run the real model

Needs Python with `torch` and `transformers` installed. Isolate it in a virtual environment, these
are heavy dependencies.

```
python3 -m venv .venv-openjev
. .venv-openjev/bin/activate        # on Windows: .venv-openjev\Scripts\activate
pip install torch transformers
python3 infra/openjev/server.py --port 8099
```

The first run downloads the weights and caches them. After that it works offline.

To check that it came up:

```
python3 -c "import urllib.request,json; print(json.load(urllib.request.urlopen('http://localhost:8099/health')))"
```

> `server.py` is not shipped here. The stub is the reference implementation of the contract, and
> the real server is a thin wrapper around a model forward pass plus the same JSON shape. Write it
> against the contract below, or point the endpoint at any service that answers it.

## How the skill uses this

The run checks service health before asking anything. If it does not answer, the run **does not
stop**: it falls back to the deterministic offline mode and says so in the output. Set
`judgment.fallback_to_offline: false` in `config.yaml` to fail the run instead.

```
python3 scripts/compose_verdict.py --state working/state.json --config config.yaml
```

## The HTTP contract

Deliberately plain, so the skill carries no machine learning library dependency. Any service that
answers this contract can replace openJev.

```
POST /v1/decide
{
  "model": "openjev-verdict-2.0",
  "state": { ... },
  "questions": {
    "rollback_untested": {
      "type": "noul",
      "instructions": {"statement": "..."},
      "criteria": {"yes": "...", "no": "..."}
    }
  }
}

200 OK
{
  "model": "openjev-verdict-2.0",
  "stub": false,
  "answers": {
    "rollback_untested": {
      "type": "noul", "noul": 0.82,
      "probabilities": {"yes": 0.82, "no": 0.18},
      "confidence": 0.64
    }
  }
}
```

An answer outside a question's domain is not an error: the client turns it into an abstention with
confidence 0, which lowers coverage. That is the intended behaviour, and it is why a broken backend
degrades the verdict to `inconclusive` rather than to something reassuring.

## An honest technical warning

The checkpoint input layout and the output tensor names can change between versions. Keep that
dependency isolated in the server's `decide` function, which is the only place to adjust if the
model evolves. Before using this on a decision that matters, validate against `stub_server.py`,
which implements the same contract, and compare the two runs.
