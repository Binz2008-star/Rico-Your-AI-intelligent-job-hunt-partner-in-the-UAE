# Decision regression harness

A hermetic, CI-collected regression gate for Rico's **deterministic decision
layer** — the keyword / magic-byte / rule-based decisions made on every request,
underneath the LLM layer.

## Why this exists

Rico's product value rests on a few decisions that must be right every time:

- **what an uploaded file is** — `document_classifier` (CV vs image vs identity
  document vs no-text vs executable)
- **which path a message takes** — the intent router
- **whether an action is allowed** — the safety guardrails

These are deterministic, so unlike the AI layer above them they can be pinned
*exactly*, offline, on every CI run. A silent regression here is invisible until
it reaches a user — two already shipped to production (**#1046** an image routed
into CV extraction, **#1047** an identity document that bypassed the block). This
harness makes that class of regression impossible to merge unnoticed.

It is deliberately **hermetic**: no network, no database, no live AI provider,
and (for the classifier family) no PDF/DOCX libraries — every input is plain text
or magic bytes. It runs in the normal `pytest tests/` sweep.

> On its very first run this harness caught a real gap: ELF (Linux) executables
> were not being rejected — only Windows `MZ` binaries were — on a Linux host.
> That one-line fix shipped with the harness.

## Running

```bash
python -m pytest tests/decision_regression/ -q
```

A machine-readable report is written to `reports/document_classifier_latest.json`
(git-ignored) for drift tracking over time.

## Adding a case

Append one line to the relevant golden file, e.g.
`goldens/document_classification.jsonl`:

```json
{"id": "recruiter_ping_en", "expected": "recruiter_email", "synth": {"kind": "text", "filename": "x.eml", "text": "..."}, "note": "why this case matters"}
```

Fields:

| field            | meaning                                                                 |
|------------------|-------------------------------------------------------------------------|
| `id`             | unique slug                                                             |
| `expected`       | required decision label (e.g. document_type)                           |
| `synth`          | how to build the input — see `build_classifier_input` in `harness.py`  |
| `min_confidence` | optional floor on the decision's confidence                            |
| `hard`           | `true` = encodes a real incident or security invariant; must never regress regardless of the aggregate accuracy floor |
| `note` / `tags`  | documentation                                                          |

`synth` kinds for the classifier (all library-free):

- `{"kind": "text", "text": "...", "filename": "x.txt"}` — raw UTF-8 bytes
- `{"kind": "repeat", "text": "..", "times": N}` — bulk text
- `{"kind": "magic", "magic": "png|jpg|gif|pdf|mz|elf", "pad": N}` — magic header + padding
- `{"kind": "b64", "data": "<base64>"}` — arbitrary decoded bytes

## Adding a new decision family

1. Write a `build_<family>_input` and a `decide_<family>` in `harness.py`
   (`decide_*` must call the **real** production function — never a
   reimplementation).
2. Add a `run_<family>_golden` wrapper and a `goldens/<family>.jsonl`.
3. Add a sibling `test_<family>_regression.py` that loads the goldens, runs the
   family, and asserts `hard_invariants`, a `class_recall` floor for any
   security-critical label, and an `accuracy` floor.

The gate helpers (`assert_hard_invariants`, `assert_class_recall`,
`assert_accuracy`) and the confusion matrix live in `harness.py` and are shared
across families.

## Relationship to `tests/evaluation/`

`tests/evaluation/` is the multi-turn *conversation* simulator (scenario-driven,
optionally against a live backend, run manually). This harness is the
complementary *unit-decision* gate: single deterministic decisions, hermetic, run
in CI on every PR.
