# Customization guide

Three layers of customization, and one layer that is deliberately out of reach.

1. **`config.yaml`**: persistent settings, edited once, applied to every run.
2. **Inline overrides**: written in the request, apply to that run only, win over the file.
3. **The question bank**: your own atomic questions, in `scripts/question_bank.py`.
4. **Locked invariants**: not configurable at any layer, by design.

## Layer 1: config.yaml

### Presentation, identical to the base skill

| Key | Default | Allowed | Notes |
|---|---|---|---|
| `language` | `auto` | `auto` or any locale tag | `auto` mirrors the language of the request |
| `depth` | `standard` | `quick`, `standard`, `deep` | `quick` skips external research, never skips the pre mortem |
| `max_risks` | `5` | `3` to `8` | below 3 is clamped to 3 |
| `bluntness` | `direct` | `plain`, `direct`, `blunt` | wording only, never the verdict |
| `focus_domains` | all | any subset of the 9 domains | non focused domains still get a fast pass |
| `sources` | all | `m365`, `code`, `web`, `calendar` | narrowing is declared in the answer |
| `output_format` | `chat` | `chat`, `document`, `card` | section order is identical in all three |
| `avoid_dashes` | `true` | `true`, `false` | typography preference |

### The judgment layer

| Key | Default | Notes |
|---|---|---|
| `judgment.backend` | `openjev` | `openjev`, `local`, `typesafe`, `offline` |
| `judgment.endpoint` | `http://localhost:8099/v1/decide` | any service answering the contract |
| `judgment.model` | `openjev-verdict-2.0` | passed through to the service |
| `judgment.timeout_seconds` | `30` | per request |
| `judgment.fallback_to_offline` | `true` | when false, a dead service fails the run instead |

### Thresholds

| Key | Default | What it changes |
|---|---|---|
| `thresholds.coverage_floor` | `0.60` | below this, the verdict is `inconclusive` |
| `thresholds.agreement_coverage_floor` | `0.80` | agreement needs this much coverage. May only be **stricter** than `coverage_floor`, a lower value is raised back |
| `thresholds.act_at` | `0.75` | at or above, the verdict stands alone |
| `thresholds.review_below` | `0.50` | below, it escalates |
| `thresholds.would_not_band` | `0.60` | risk index at or above means "would not do it this way" |
| `thresholds.guardrails_band` | `0.35` | risk index at or above means "would do it with guardrails" |

### Coefficients

The whole point of the variant. Each key matches a question in `scripts/question_bank.py`, and the
values must sum to 1.0 (the script renormalizes and says so if they do not).

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

Reweighting is how you encode what your organisation actually gets hurt by. A team that has been
burned by unowned systems raises `no_named_owner`. A team under audit raises `evidence_thin`. The
change is one number, it is versioned in the file, and every run records the coefficients it used.

A coefficient naming a question that does not exist is ignored and reported. A question with no
coefficient is still asked and still recorded, it simply does not move the index, which is a good
way to watch a signal before trusting it.

### house_rules and custom_domains

Same as the base skill. `house_rules` lines are appended to the analysis rules; `custom_domains`
adds your own sweep categories. A house rule may add strictness. One that tries to remove it
("skip the pre mortem", "agree if I already decided") is ignored and reported.

## Layer 2: inline overrides

| Phrase | Effect |
|---|---|
| "quick mode", "modo rapido" | `depth: quick` |
| "deep mode", "vai fundo" | `depth: deep` |
| "top 3 only", "so os 3 principais" | `max_risks: 3` |
| "offline", "sem modelo" | `judgment.backend: offline` |
| "use the stub", "roda no stub" | point the endpoint at `stub_server.py` |
| "brutal", "sem filtro" | `bluntness: blunt` |
| "in English", "responde em portugues" | sets `language` |
| "as a document", "manda em doc" | `output_format: document` |

Note what is missing from that table: there is no inline override for a threshold or a coefficient.
Those live in the file, under version control, because a verdict you can retune mid-argument is a
verdict that can be argued down, which is the whole failure this variant exists to prevent.

## Layer 3: your own questions

Add to `RISK_QUESTIONS` in `scripts/question_bank.py`, then give the key a coefficient in
`config.yaml`.

```python
"data_leaves_tenant": Noul(
    {"statement": "Customer data crosses a boundary it does not cross today.",
     "note": "Region, tenant, vendor or country."},
    {"yes": "At least one class of customer data lands outside the current boundary.",
     "no": "All data stays inside the current boundary."},
    weight=0.10),
```

One rule governs every question you add: **phrase it so that 1.0 means more risk**. The composition
is a plain weighted sum, and a question phrased as a virtue silently inverts the index.

Second rule: **keep it atomic**. If you can answer your new question with "well, partly, because
two different things are going on", it is two questions.

## Layer 4: what cannot be customized

| Not configurable | Why |
|---|---|
| Risk first, no praise opening | The moment validation leads, the skill stops being a counterpoint |
| Agreement gated harder than disagreement | "Agreement must be earned", expressed as an inequality |
| Low coverage never resolves to agreement | Missing evidence is not reassurance |
| Abstention never counts as a "no" | Reading an unanswered question as the comfortable value is the exact failure mode |
| The verdict is composed in code | A narrated verdict can drift, a computed one cannot |
| Same state, same verdict | The state hash is the anti-sycophancy guarantee |
| Pressure is not state | Otherwise pressure, not evidence, decides |
| Read only | A counterpoint that changes things is no longer a counterpoint |
| No evaluation of people | Risk analysis is about process and dependency |
| The user decides | The skill advises and then helps execute, including against itself |

### Why the lock exists

An assistant that adapts to its user tends toward agreement: it reads approval as success and
friction as failure. A skill whose entire value is friction has to be protected from that pull.

The base skill protects the pressure sensitive parts by writing them as rules. This variant does
something stronger: it removes them from the model's reach entirely. The model here cannot soften a
verdict under pressure, because it is not the thing producing the verdict.

## Recipes

**Audit trail for a contested decision**

```yaml
judgment: {backend: openjev}
thresholds: {coverage_floor: 0.70, agreement_coverage_floor: 0.90}
max_risks: 6
output_format: document
```

**No model at all, permanently**

```yaml
judgment: {backend: openjev, endpoint: "http://localhost:8099/v1/decide"}
# with stub_server.py running: deterministic, no weights, every answer flagged as stub
```

**Comparison run against the hosted arbiter**

```yaml
judgment: {backend: typesafe}   # state redacted by default, confirm with the user first
```
