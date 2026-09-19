# Rico Local Model Evaluation — Second-Reviewer Findings

- Date: 2026-09-19
- Reviewer role: second technical reviewer (not the benchmark author)
- Branch: `claude/rico-local-model-eval-msqw3p`
- Scope: evaluation only. No Rico production code, provider routing, or
  configuration is changed by this work.

## Evidence provenance — read this first

The benchmark CSVs, the 35 `quality_*.txt` files, and `quality_results_MASTER.csv`
live on the owner's Windows development PC. **They are not in this repository, so
this reviewer could not re-verify a single measurement.** Every number in
Section 1 is quoted from the owner's handoff and is marked `[reported]`.
Numbers this reviewer derived are marked `[derived]` and are estimates, not
measurements. Nothing here is a substitute for a re-run.

That gap is itself finding **F-0** below.

---

## Decision

**Provisionally, `qwen2.5:7b` is the evidence leader — but the benchmark as run
cannot support a final model selection, and the current five-model set should
not be the set you choose from.**

Two things must happen before selection:

1. Fix three methodology defects (prefill blindness, n=1 JSON, non-admissible
   cells scored as quality). These change the ranking, not just the confidence.
2. Add two genuinely different candidates — `qwen3:4b` and `qwen3:30b-a3b`.
   The current five are four Qwen2.5-7B derivatives plus one Llama-3.1-8B
   finetune. That is effectively a two-model test, not a five-model test.

Do **not** restart the benchmark. Re-run the corrected suite against the two
new candidates plus `qwen2.5:7b` as the carried-forward control.

---

## 1. Findings

### F-0 — The evidence is single-copy and off-repo (process risk, highest)

P0 benchmark evidence exists only on one machine. The brief's own storage policy
says never leave the only copy in one place. A disk failure destroys the entire
investigation, and no second reviewer can audit conclusions they cannot read.

**Action:** commit the MASTER CSV and the 21 valid API outputs into
`AI_WORKSPACE/EVALS/local-model-eval/evidence/`. They are small text files with
no secrets and no user data.

### F-1 — The benchmark measures the wrong half of the latency (highest technical)

Reported throughput is **decode** throughput — tokens generated per second.
Rico's dominant AI workload is the opposite shape: **long input, short
structured output.**

From the repo, Rico's actual generation budgets are:

| Workload | Source | Output budget |
|---|---|---|
| Chat / advice reply | `src/rico_openai_agent.py:370` | 300 tokens |
| Job scoring prompt | `src/job_agent.py:310` | 180 tokens |
| CV + cover letter tailoring | `src/rico_apply_ai.py:62` | 2000 tokens |
| Image/CV extraction | `src/services/image_extractor.py:149` | 800 tokens |

A job-analysis call sends roughly 1,200–1,800 prompt tokens (job posting + CV
excerpt + profile + schema) and asks for ~250 back. On CPU, prefill of that
prompt is **compute**-bound while decode is **memory-bandwidth**-bound; they are
different speeds and the benchmark only reports one.

`[derived]` On an i7-8700 (6 cores, AVX2, no AVX-512), llama.cpp prefill for a
7B Q4 model typically lands around 15–25 tok/s. A 1,500-token prompt is
therefore **60–100 seconds before the first output token appears**, on top of
~70 s to generate 250 tokens at the reported rate.

**Realistic end-to-end for one Rico job analysis: 2–3 minutes.** The
`~3.77 tok/s` figure never surfaces that. The corrected harness reports
`prefill_tok_s`, `decode_tok_s`, and wall-clock separately.

### F-2 — Sanity check: the reported CPU numbers are internally consistent

`[derived]` Worth stating, because it means the measurements are trustworthy as
far as they go. The i7-8700 runs dual-channel DDR4-2666 ≈ 42.7 GB/s theoretical,
~30–35 GB/s realistic. A 7B Q4_K_M model is ~4.4 GB of weights, so the
bandwidth ceiling for decode is ~7–8 tok/s. The reported 3.5–4 tok/s is ~50% of
ceiling, which is exactly where llama.cpp lands on six cores.

**Implication:** no amount of tuning makes a dense 7B meaningfully faster on
this box. Getting faster requires a smaller model or fewer active parameters —
see F-7. This closes off "just optimize the current setup" as a path.

### F-3 — n=1 per cell cannot measure JSON reliability

Seven tests, five models, one run each at `temperature=0`. Temperature 0 makes a
re-run return the same answer, so the benchmark has **zero** information about
variance under prompt rephrasing — which is the only variance that matters in
production, where users phrase things differently every turn.

"JSON: valid" from one sample is consistent with a true pass rate anywhere from
about 20% to 100%. Rico needs schema conformance in the high 90s. **The current
evidence cannot distinguish a reliable model from an unreliable one.**

The corrected harness runs 5 prompt phrasings × 4 samples = 20 strict-JSON
attempts per model and reports a pass rate, plus separate Arabic-JSON and
eligibility-detection contracts.

### F-4 — `instruction_following` is eliminating models on a test Rico does not run

Three of five models "failed" or went "partial" on this test. The qwen2.5:7b
detail shows exactly what the test is: started with `ACKNOWLEDGED: YES` ✓, ended
with `?` ✓, produced 2 sentences instead of 3 ✗, said "blue" twice instead of
once ✗.

That is a multi-constraint *counting* task. Two problems:

- **It is fragile to grade.** Counting sentences and word occurrences by string
  match is ambiguous (does the model restating the instruction count? does
  "blueprint" contain "blue"?). Some of these "failures" are probably grader
  artifacts, and the raw outputs should be re-read before the label stands.
- **It does not resemble any Rico workload.** Rico never asks for exactly three
  sentences with a colour mentioned once. Rico asks for **schema adherence** —
  and schema adherence is a different capability that 7B models are markedly
  better at than constraint-counting.

**No model should be eliminated on this axis.** Weight in the corrected suite
goes to strict-JSON conformance instead, which is what Rico actually depends on.

### F-5 — The refusal test has no discriminative power

All five models passed, **including `huihui_ai/qwen2.5-abliterate:7b`** — a model
whose entire purpose is having its refusal behaviour surgically removed. If an
abliterated model scores identically to the base model, the test is not
measuring refusal.

Separately, and more important than the test: **drop the abliterated model from
the candidate set on governance grounds.** Rico handles real CVs, PII, salary
data and gives career advice to real people. Deliberately removing safety
behaviour from the model that touches that data is a liability with no
compensating benefit — its reported scores sit within noise of base `qwen2.5:7b`
(3.96 vs 3.88 tok/s `[reported]`). There is nothing to trade off.

### F-6 — `deepseek-r1:7b`'s three bad cells are one cause, and it is not reasoning quality

The brief correctly says the 600 s reasoning timeout is a performance limit, not
a reasoning-quality verdict. I'd sharpen this in two ways:

- **The JSON and Arabic "incomplete/failed" cells are almost certainly the same
  root cause** — R1-distill models emit a long `<think>` chain before the answer,
  so they exhaust the token budget mid-thought and never reach the payload. Those
  two cells are **truncation artifacts and must be struck from the quality
  matrix**, not recorded as failures. Right now the matrix reads as though
  deepseek is bad at JSON and Arabic. There is no evidence for that.
- **But the conclusion for this hardware is still elimination**, and calling it
  "infrastructure" understates it. Long thinking chains are a permanent
  architectural property of R1-distills, not a transient environment problem.
  At 3.5 tok/s, a 2,000-token reasoning chain costs ~10 minutes *before* the
  answer starts. The honest label is **"architecturally impractical on CPU at
  this throughput"** — a property of (this model × this hardware) that no
  re-run fixes.

Also note `deepseek-r1:7b` is itself a Qwen2.5-7B distillation, which feeds F-7.

### F-7 — The five candidates are two models wearing five labels

| Tested tag | Actual base | Family |
|---|---|---|
| `qwen2.5:7b` | Qwen2.5-7B-Instruct | Qwen2.5-7B |
| `qwen2.5-coder:7b` | Qwen2.5-7B, code-tuned | Qwen2.5-7B |
| `huihui_ai/qwen2.5-abliterate:7b` | Qwen2.5-7B, safety-removed | Qwen2.5-7B |
| `deepseek-r1:7b` | Qwen2.5-7B, R1-distilled | Qwen2.5-7B |
| `dolphin3:8b` | Llama-3.1-8B finetune | Llama-3.1-8B |

Four of five share one base. The benchmark has thoroughly characterised
**Qwen2.5-7B** and given one data point on **Llama-3.1-8B**. It has not tested a
different size class, a different generation, or a different architecture.

This answers question **D: the set is not sufficient** — but not because it
lacks a bigger model. It lacks *diversity*, and specifically it never tested the
one architecture that changes the CPU maths (F-9).

### F-8 — `qwen2.5-coder:7b` is the wrong optimisation target for Rico

It will win the coding test; that is what it was tuned for. But coder-tuned
models characteristically **lose general-chat and multilingual quality** relative
to their base instruct sibling — and Rico's user-facing load is Arabic/English
career advice, not code. Rico's own coding is done by this agent and the owner's
tools, not by a local 7B.

Optimising the local model choice for the coding axis would be optimising for
the workload Rico least needs from it.

### F-9 — The highest-leverage untested candidate is an MoE, and it inverts the size intuition

The brief says "the goal is NOT simply to find the biggest model", which is
right for dense models. But on CPU, **Mixture-of-Experts breaks the
size↔speed coupling**, because decode speed tracks *active* parameters, not
total parameters.

`[derived]` `qwen3:30b-a3b` — 30B total, ~3B active per token:

- Q4_K_M weights ≈ 17–18 GB, comfortably inside 32 GB RAM
- per-token bytes touched ≈ 2.0–2.5 GB vs 4.4 GB for a dense 7B
- bandwidth ceiling ≈ 14–16 tok/s; realistic at the same ~50% efficiency
  → **~6–8 tok/s, roughly double the tested 7B models**

So the largest untested model is also plausibly the **fastest** one, while
delivering quality well above any 7B. That is a counter-intuitive result worth
measuring rather than assuming, in either direction.

Caveats to measure, not hand-wave: MoE expert-locality on CPU is worse than the
clean maths suggests, and 18 GB of weights plus KV cache leaves ~10–12 GB
headroom on a 32 GB box — fine for a dedicated run, tight if an IDE and browser
are open. Both are exactly what a re-run settles.

---

## 2. Answers to the review questions

### A. Which model currently has the strongest evidence?

**`qwen2.5:7b`** — provisionally, and on weak evidence.

It is the only candidate with a complete valid matrix across all seven tests and
no disqualifying property. It did not *win* any axis; it is the one left standing
once the others are correctly disqualified:

- `huihui_ai/qwen2.5-abliterate:7b` → governance (F-5), no quality upside
- `deepseek-r1:7b` → architecturally impractical on CPU (F-6)
- `qwen2.5-coder:7b` → optimised for Rico's least-needed axis (F-8)
- `dolphin3:8b` → Llama-3.1-8B has weaker Arabic than Qwen2.5 and is larger
  (slower) on CPU; no axis where it leads

Note this is selection by elimination, not by demonstrated superiority. That is
the honest description of what the current evidence supports.

### B. Best balance across the seven axes?

Same answer, with the caveat that **the balance cannot be computed from the
current data**, because two of the seven axes are unusable:
`instruction_following` is measuring the wrong thing (F-4) and `refusal_test`
discriminates nothing (F-5). A weighted score over seven axes where two are
invalid is not a balanced score.

The axes that should carry the weight for Rico, in order:

1. **Strict JSON conformance rate** — everything downstream breaks without it
2. **Arabic quality** (prose *and* Arabic-in-JSON, which is strictly harder)
3. **Wall-clock latency on Rico-shaped prompts** (prefill + decode)
4. **Honest fit assessment** — Rico must not flatter; this is a real product
   requirement, not a nice-to-have
5. Reasoning
6. Coding — lowest weight for a *local* model in Rico's context

### C. Genuine model limitations vs infrastructure limitations?

| Observation | Correct classification |
|---|---|
| GTX 1060 CUDA/PTX error | **Infrastructure.** Real, reproduced through the API, correctly isolated. Keep it documented separately; do not chase it. |
| 3.5–4 tok/s decode | **Hardware ceiling, not a model property.** ~50% of this box's bandwidth limit (F-2). Affects all dense 7B models equally. |
| deepseek-r1 reasoning timeout | **Model×hardware mismatch.** Permanent for this pairing — not a quality verdict, and not a fixable infra issue either (F-6). |
| deepseek-r1 JSON + Arabic "failed" | **Truncation artifact. Strike from the matrix** — no quality evidence exists for these cells (F-6). |
| Three models "failing" instruction-following | **Partly grader artifact, partly a real but Rico-irrelevant weakness** (F-4). Not disqualifying. |
| All five passing refusal | **Invalid test**, including for the abliterated model (F-5). |
| qwen2.5:7b fenced-JSON historical output | **Correctly discounted.** Fencing is a format issue a production adapter strips in one line; it is not a JSON capability failure. The corrected harness records `fenced_but_valid` distinctly from a parse error. |

### D. Is the current five-model set sufficient?

**No** — see F-7. It is four Qwen2.5-7B derivatives and one Llama-3.1-8B. Add
two candidates that are genuinely different, keep `qwen2.5:7b` as the control,
and drop the abliterated model.

### E–F. Recommended additional candidates

All figures `[derived]` and requiring measurement. Quantization assumed Q4_K_M
(Ollama's usual default) — the corrected harness records the actual quant so
this stops being an assumption.

**Priority 1 — `qwen3:30b-a3b` (MoE, ~3B active)**

- Size / RAM: ~17–18 GB Q4_K_M; fits 32 GB with ~10–12 GB headroom
- CPU practicality: **~6–8 tok/s expected, ~2× the tested dense 7Bs** (F-9)
- Arabic: strong — Qwen3 improved multilingual coverage over Qwen2.5
- Coding: well above any 7B in this set
- Structured output: strongest expected of any candidate here
- Reasoning: substantially above 7B; has a controllable thinking mode, so it
  does **not** inherit deepseek-r1's forced-long-chain problem
- Licence: Apache 2.0 — clean for commercial use
- Risk to measure: MoE expert-locality on CPU may undercut the projection;
  RAM headroom is tight with an IDE open

**Priority 2 — `qwen3:4b`**

- Size / RAM: ~2.5 GB Q4_K_M; trivial fit, leaves the box usable
- CPU practicality: **~6–7 tok/s expected**, and much faster prefill — which
  is the metric that actually hurts (F-1)
- Arabic: good; Qwen3-4B is close to Qwen2.5-7B on general tasks
- Coding: adequate, below the 7B coder
- Structured output: good; small models are often *more* obedient to a strict
  schema than mid-size ones
- Reasoning: the weakest axis at this size — measure, don't assume
- Licence: Apache 2.0
- Why it matters: if 4B is within noise of 7B on Rico's real axes, you get 2×
  throughput for free, and that decides the project

**Control — `qwen2.5:7b`**, carried forward unchanged so the new runs are
comparable to the existing evidence.

**Explicitly not recommended:**

- **Phi-4 (14B)** — ~9 GB fits RAM, but dense 14B on this box is `[derived]`
  ~1.5–2 tok/s. Too slow regardless of quality, and weak Arabic.
- **Gemma-2-9B / Gemma-3-12B** — slower than the tested 7Bs, and a custom
  Google licence rather than a clean open-weight one. Not worth the slot.
- **Anything above ~30B dense** — bandwidth-bound below 2 tok/s. Not viable.

---

## 3. Methodology gaps the corrected harness closes

`bench_ollama.py` in this directory implements the fixes. Stdlib only — no
`pip install` on the Windows box.

| Gap | Fix |
|---|---|
| Decode-only throughput (F-1) | Reports `prefill_tok_s`, `decode_tok_s`, wall-clock mean **and max**, separately |
| n=1 JSON (F-3) | 5 prompt phrasings × 4 samples = 20 strict-JSON attempts; reports a pass rate |
| Truncation scored as failure (F-6) | `OK` / `TIMEOUT` / `TRUNCATED` / `ERROR` are distinct; only `OK` is admissible as quality evidence |
| Quantization unrecorded | Queries `/api/show`, records digest + `quantization_level` on every row |
| Tests don't match Rico | Suite is built from Rico's real shapes: long posting → strict JSON, Arabic-in-JSON, nationality-restriction detection, honest-fit advice |
| Arabic scored as a boolean | Arabic script presence is a **floor check only**, explicitly labelled not-a-quality-score; prose goes to human/judge review |
| Ungradable things auto-graded | Fit honesty and coding are marked review-only and excluded from auto-scores |

Grader correctness was verified against known-good and known-bad inputs before
this was committed (clean JSON, fenced JSON, prose preamble, missing keys, wrong
types, out-of-range values, Arabic vs English).

### Commands

```bash
cd AI_WORKSPACE/EVALS/local-model-eval

# Inspect the suite without running anything
python bench_ollama.py --list-suite

# Control + new candidates (expect several hours; run overnight)
python bench_ollama.py --models qwen2.5:7b qwen3:4b --timeout 600
python bench_ollama.py --models qwen3:30b-a3b --timeout 900
```

29 requests per model. `[derived]` at the reported throughput, budget roughly
45–90 minutes per 7B-class model.

---

## 4. What must not happen

Carried from the brief's change-control section, and endorsed:

- No Rico production code, provider default, or configuration changes. Nothing
  in this directory imports or touches Rico runtime code.
- No driver or CUDA toolchain changes to chase the GTX 1060 PTX error. It is
  documented and correctly worked around with `num_gpu: 0`.
- No fabricated results. Cells with no valid run stay empty. Struck deepseek
  cells are struck, not guessed.
- The RTX 2070 Super is not part of this project and appears in no projection
  here.

## 5. Recommended next steps, in order

1. **Commit the existing evidence** (MASTER CSV + 21 valid API outputs) into
   `evidence/`. Single-copy P0 data is the most urgent problem and the cheapest
   to fix. (F-0)
2. **Strike the two deepseek truncation cells** from the quality matrix and
   re-label the reasoning timeout as "architecturally impractical on CPU".
   (F-6)
3. **Re-read the three instruction-following raw outputs** to separate genuine
   misses from grader artifacts before that label stands. (F-4)
4. **Drop `huihui_ai/qwen2.5-abliterate:7b`** from the candidate set. (F-5)
5. **Run the corrected suite** on `qwen2.5:7b` (control), `qwen3:4b`,
   `qwen3:30b-a3b`.
6. **Then, and only then, select.** The decision rule: highest strict-JSON pass
   rate among models whose p95 wall-clock on a Rico-shaped prompt is acceptable
   for the intended use, with Arabic quality as the tiebreak.

## 6. One framing question for the owner

Not blocking, but it changes the acceptance threshold and is worth settling
before step 5:

**What is the local model actually for?**

- *Offline/privacy-sensitive CV parsing, batch, overnight* → 2–3 minute
  latency is fine, and `qwen3:30b-a3b` is very likely the answer.
- *A fallback tier in Rico's live provider chain* → 2–3 minutes is far outside
  any acceptable web request budget, and no model on this hardware qualifies.
  The honest conclusion would be that this box cannot serve live traffic, and
  the project's value is in the offline/privacy use case instead.
- *Development-time testing without burning API credits* → `qwen3:4b` wins on
  iteration speed and quality barely matters.

These have different winners. The benchmark is worth finishing either way — but
the third option in particular would mean the current five-model quality matrix
is over-engineered for the decision it needs to support.
