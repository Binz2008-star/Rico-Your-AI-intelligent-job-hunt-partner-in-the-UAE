# Rico Local Model Discovery — Unrestricted Open-Weight Candidates

- Date: 2026-09-19
- Phase: RESEARCH / MODEL DISCOVERY ONLY — no benchmarking, no installs, no Rico changes
- Target hardware: Intel i7-8700 · 32 GB DDR4 · **NVIDIA GTX 1060 6 GB** · Windows 11 · Ollama
- Explicitly out of scope: RTX 2070 Super (not our hardware), Rico production code/config/DB/routing

## Evidence grading used throughout

| Tag | Meaning |
|---|---|
| **[FACT]** | Stated by a cited source. |
| **[INFERENCE]** | Derived by this reviewer from specs or arithmetic. Not measured. |
| **[UNVERIFIED]** | Could not be checked from here — see the egress limitation below. |

### Verification limitation — read before trusting any size/tag figure

This environment's network egress policy **blocks `ollama.com`, `huggingface.co`, and
several model-catalogue sites**. Those are the primary sources for exact Ollama tags,
quantization names, and file sizes. Every tag and size in this document is therefore
**[UNVERIFIED]** — sourced from search-result summaries, not read off the registry.

Confirming them takes seconds at the PC (`ollama show <tag>`, or the model page in a
browser) and **must be done before any download decision**. Nothing here is invented;
but nothing here has been read from the registry either.

---

## 0. The finding that reframes the whole exercise

The brief asks for two things that the evidence says are in tension:

- "as unrestricted/uncensored as possible"
- "reliable structured JSON", "good instruction following", "agent/tool workflows"

**[FACT]** A comparative study of abliteration methods reports that *instruction-following
degrades before MMLU-Pro does* — i.e. the capability Rico depends on most is the one
abliteration damages first, and headline knowledge benchmarks hide it
([arXiv 2512.13655](https://arxiv.org/pdf/2512.13655)).

**[FACT]** On `llama.cpp` discussion #28430, an abliterated Qwen3.8-27B looped on
multi-step agentic tasks — repeating tool calls, then emitting typo'd variants of file
paths inside grammar-constrained JSON, unable to recover from its own errors. Clean
weights of the same model did not. Most of it traced to three misconfigurations, but the
reporter confirmed **"a residual defect" remained after fixing them**
([discussion #28430](https://github.com/ggml-org/llama.cpp/discussions/28430)).

**[FACT]** Rico's own CPU benchmark already saw this: `huihui_ai/qwen2.5-abliterate:7b`
scored *partial* on instruction-following — see `REVIEW.md` finding F-4.

### What Rico probably actually needs

Worth separating, because it changes which model wins. The plausible product reason to
want an unrestricted model here is **over-refusal on legitimate HR content**, and that is
a real problem in the GCC:

- extracting **nationality, visa status, age, gender, marital status** — routinely present
  on GCC CVs and legally material for UAE eligibility and Emiratisation quotas
- answering **"is this candidate a weak fit?"** honestly instead of hedging
- **UAE-Nationals-only** filtering, which a safety-tuned model may read as discriminatory
  and refuse
- salary-band and negotiation advice

That is **low false-refusal on HR-legitimate content** — which is *not* the same property
as "fully abliterated", and is cheaper to obtain. A base instruct model with a firm system
prompt may already clear it, at no cost to JSON reliability.

**Recommendation:** treat "uncensored" as a *measured* axis, not a selection filter. Build
a small over-refusal probe from Rico's real content (nationality extraction, Emiratisation
filtering, blunt fit verdicts, salary advice) and run it against aligned *and* abliterated
candidates. If an aligned model passes, it is the better engineering choice, because it
keeps the instruction-following and JSON reliability that abliteration measurably erodes.

This does not remove unrestricted candidates from the benchmark — the shortlist below
includes them as the brief requires. It means the decision should rest on measured
over-refusal, not on the label.

---

## 1. GPU feasibility — the constraint that sizes everything

### The Pascal situation (this is good news, with a caveat)

**[FACT]** CUDA 13.0 removed support for Maxwell, Pascal (compute 6.x) and Volta. The
GTX 1060 is Pascal, compute capability **6.1**
([Tom's Hardware](https://www.tomshardware.com/pc-components/gpus/nvidia-to-drop-cuda-support-for-maxwell-pascal-and-volta-gpus-with-the-next-major-toolkit-release),
[CUDA 13.1 release notes](https://docs.nvidia.com/cuda/archive/13.1.0/cuda-toolkit-release-notes/index.html)).

**[FACT]** Ollama issue [#17012](https://github.com/ollama/ollama/issues/17012) is *our
exact failure on our exact card*: GTX 1060 6 GB, Windows, `PTX was compiled with an
unsupported toolchain`, plus a `0xc0000409` crash in `ucrtbase.dll`. Reported on Ollama
0.31.1 / driver 560.94 / CUDA 12.6. **The issue is closed.**

**[FACT]** Ollama PR [#17196](https://github.com/ollama/ollama/pull/17196) (July 2026)
fixes Windows CUDA-runtime version detection, which previously mis-parsed the minor
version and mishandled the driver floor — and it exists specifically because
"llama-server aborted when PTX JIT required" a newer driver. It handles both
`cudart64_12.dll` and `cudart64_13.dll`.

**[INFERENCE]** Mechanism, and it is not "Pascal is dead": a CUDA-13-built binary contains
no `sm_61` machine code, so the driver must **JIT the PTX** — and a driver older than the
toolkit cannot. Our reported driver, **560.94, is older than the last Pascal branch**.

**[FACT]** **R580 is the final NVIDIA driver branch supporting Pascal.** Game Ready
support ended October 2025; Pascal continues to receive **quarterly security updates
through October 2028**
([TechPowerUp](https://www.techpowerup.com/338497/nvidias-v580-driver-branch-ends-support-for-maxwell-pascal-and-volta-gpus),
[Phoronix](https://www.phoronix.com/news/NVIDIA-580-Linux-Driver-Last-HW)).

**[INFERENCE — the testable hypothesis, do not act on it blind]** The GPU path is most
likely recoverable by two changes, neither of which is "install arbitrary CUDA packages":
1. move the driver up to the **latest R580-branch release** (560 → 580 is an in-support
   move, not an experiment), and
2. run an **Ollama build that selects the CUDA 12 backend** on this machine.

This is a hypothesis to test at the PC, not a conclusion. It is also the single
highest-value thing to test first, because of the next section.

### Why the GPU question dominates model selection

**[FACT]** GTX 1060 6 GB memory bandwidth is **192 GB/s**. **[INFERENCE]** i7-8700
dual-channel DDR4-2666 is ~35 GB/s realistic — so VRAM is roughly **5.5× faster**.

**[INFERENCE]** Generation on a quantized model is memory-bandwidth-bound, so a model
that fits **entirely** in 6 GB VRAM could plausibly run several times faster than the
3.5–4 tok/s measured on CPU. **Not measured. Do not quote this as a number.**

The consequence for this report: the **6 GB VRAM ceiling**, not the 32 GB RAM ceiling,
decides which models are in the fast tier. And Pascal has no tensor cores, so FP16 gives
no advantage — **[INFERENCE]** INT8/Q4 GGUF paths (DP4A) are the ones that perform.

### VRAM budget — all [INFERENCE], for planning only

Usable VRAM on Windows 11 with a display attached: **~5.3–5.6 GB of the 6 GB**.

| Model class at Q4_K_M | Approx. weights | Full GPU offload on 6 GB? |
|---|---|---|
| 3–4B | ~2.0–2.7 GB | **Yes**, with comfortable context headroom |
| 7–9B | ~4.4–5.6 GB | **Borderline** — likely only at reduced context (~4K) |
| 12–14B | ~7–9 GB | **No** — partial offload only |
| 26–35B MoE (A3B) | ~17–20 GB | **No** — mostly system RAM; fits 32 GB, not 6 GB |
| 27–31B dense | ~16–19 GB | **No** — RAM-resident, slow |

**[INFERENCE]** Note the MoE nuance: a 35B-A3B model still needs all ~18 GB resident even
though only ~3B parameters are active per token. It cannot live in 6 GB VRAM. Its
advantage is **CPU speed** (fewer active parameters per token), not VRAM fit. On this box
MoE is a *CPU-tier* optimisation, not a GPU-tier one — the opposite of the usual intuition.

---

## 2. Candidate pool

Sizes/tags **[UNVERIFIED]** per the egress limitation. Licence and release facts are cited.

| # | Model | Base / arch | Params | Licence | Ollama path | Category |
|---|---|---|---|---|---|---|
| 1 | Qwen3.5-4B | Qwen3.5 dense | 4B | Apache 2.0 [FACT] | registry | C aligned |
| 2 | Qwen3.5-9B | Qwen3.5 dense | 9B | Apache 2.0 [FACT] | registry | C aligned |
| 3 | Qwen3.5-27B | Qwen3.5 dense | 27B | Apache 2.0 [FACT] | registry | C aligned |
| 4 | Qwen3.5-35B-A3B | Qwen3.5 MoE | 35B / ~3B active | Apache 2.0 [FACT] | registry | C aligned |
| 5 | Qwen3.6-27B | Qwen3.6 dense | 27B | open-weight [FACT] | registry | C aligned |
| 6 | Qwen3.6-35B-A3B | Qwen3.6 MoE | 35B / 3B active | open-weight [FACT] | registry | C aligned |
| 7 | Qwen3.8-27B | Qwen3.8 dense | 27B | open-weight [FACT] | registry | C aligned |
| 8 | `huihui_ai/qwen3-abliterated` | Qwen3 dense | 4b/8b/14b + 30b-a3b tags | inherits base | Ollama [FACT] | **A unrestricted** |
| 9 | `huihui_ai/qwen3.5-abliterated` | Qwen3.5 | tags unconfirmed | inherits base | Ollama [FACT] | **A unrestricted** |
| 10 | `huihui_ai/qwen3-coder-abliterated` | Qwen3-Coder | unconfirmed | inherits base | Ollama [FACT] | **A unrestricted** |
| 11 | `huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated` | Qwen3.6 MoE | 35B / 3B active | inherits base | HF; GGUF unconfirmed | **A unrestricted** |
| 12 | Falcon-H1-Arabic-7B-Instruct | hybrid Mamba-Transformer | 7B | Apache 2.0 [FACT] | `hf.co/tiiuae/...-GGUF`, ~5 GB [FACT] | C aligned |
| 13 | Falcon-H1-Arabic 3B / 34B | hybrid Mamba-Tx | 3B / 34B | Apache 2.0 [FACT] | GGUF unconfirmed | C aligned |
| 14 | Falcon-H1R-7B | hybrid Mamba-Tx, reasoning | 7B | Apache 2.0 [FACT] | official GGUF repo [FACT] | C aligned |
| 15 | Ministral 3 (3B / 8B / 14B) | Mistral dense | 3/8/14B | Apache 2.0 [FACT] | registry | C aligned |
| 16 | Mistral NeMo | Mistral dense | 12B | Apache 2.0 [FACT] | registry | C aligned |
| 17 | Gemma 4 (E2B/E4B, 12B, 26B-A3.8B, 31B) | Gemma 4 | 2–31B | **Apache 2.0** [FACT] | registry | C aligned |
| 18 | Hermes 4 14B | Qwen3 + ChatML | 14B | inherits base | GGUF via Modelfile [FACT] | **B reduced-refusal** |
| 19 | Hermes 4 36B / 70B | Llama-3-chat | 36B / 70B | Llama licence | GGUF [FACT] | **B reduced-refusal** |
| 20 | `dolphin3:8b` | Llama-3.1-8B | 8B | Llama licence | Ollama [FACT] | **B reduced-refusal** |
| 21 | Jais 30B | Arabic-native | 30B | Apache 2.0 [FACT] | GGUF unconfirmed | C aligned |
| 22 | `qwen2.5:7b` | Qwen2.5 dense | 7B | Apache 2.0 | Ollama | C aligned — **existing control** |

**Licence note [FACT]:** Llama licences still carry a **700M MAU cap and an EU multimodal
exclusion**; Gemma 4 moved to plain Apache 2.0 in its 2026 release. For a commercial SaaS
this makes the Llama-derived entries (#19, #20) the weakest on licence terms, and Apache
2.0 families the cleanest.

**Key releases [FACT]:** Qwen3.5 Feb 2026 (0.8B/2B/4B/9B/27B dense; 35B-A3B, 122B-A10B
MoE) · Qwen3.6-35B-A3B, 256K context, 201 languages · Gemma 4 April 2026 · Falcon-H1
Arabic Jan 5 2026 · Ministral 3 Dec 2025.

---

## 3. Unrestricted candidates only (Category A)

Category A = weights modified to remove refusal behaviour. **Not** models that merely
refuse less.

| Model | Method | What "uncensored" actually means here | VRAM fit (6 GB) |
|---|---|---|---|
| `huihui_ai/qwen3-abliterated:4b` | abliteration | Refusal direction ablated from weights. Base capability largely intact; **instruction-following is the first thing to degrade** [FACT] | **Fits fully** [INFERENCE] |
| `huihui_ai/qwen3-abliterated:8b` | abliteration | As above | **Borderline**, reduced context [INFERENCE] |
| `huihui_ai/qwen3.5-abliterated` | abliteration | As above, on a newer base | depends on tag [UNVERIFIED] |
| `huihui_ai/qwen3-abliterated:14b` | abliteration | As above | **No** — partial offload [INFERENCE] |
| `huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated` | abliteration | As above, MoE | **No** — ~18 GB, RAM-resident [INFERENCE] |
| `huihui_ai/qwen2.5-abliterate:7b` | abliteration | Already tested; **partial** on instruction-following | Borderline [INFERENCE] |

**[FACT]** huihui-ai's own model cards warn these have significantly reduced safety
filtering and have not undergone rigorous safety optimisation.

### Abliteration is not one technique — and the method matters

**[FACT]** From the comparative study ([arXiv 2512.13655](https://arxiv.org/pdf/2512.13655)):

- Classic abliteration: one ablation weight per layer against a single mean-difference
  refusal direction.
- **Heretic** ([p-e-w/heretic](https://github.com/p-e-w/heretic)): per-layer weight kernels
  against an *interpolated* refusal direction, separate attention/MLP parameters, tuned by
  an Optuna TPE optimiser co-minimising refusals **and** KL divergence.
- Results are **model-specific, not universal**: Heretic hit 3/100 refusals on
  Gemma-3-12B-IT at KL 0.16 vs 1.04 for the best manual abliteration (**6.5× less
  capability damage**) — but averaged **−7.81 pp on GSM8K**, and **−18.81 pp on
  Yi-1.5-9B** while costing only −0.12 pp on Mistral-7B.
- **ErisForge** showed the best capability preservation overall, then **DECCP**.
- Heretic had universal compatibility (16/16 models); DECCP 11/16.

**[INFERENCE]** Two consequences for us: (a) "abliterated" on a model card tells you
nothing about *how much damage* was done — the same label spans −0.12 pp to −18.81 pp;
(b) the variance is per-model, so this **must be measured on our candidates**, not assumed.

### A risk specific to Rico that nobody benchmarks

**[INFERENCE, flagged as a gap]** Abliteration refusal directions are typically computed
from **English** harmful/harmless prompt pairs. Rico needs **Arabic** as a first-class
language. Whether ablating an English-derived direction damages Arabic generation
disproportionately is, as far as this search found, **unmeasured anywhere**. Given Rico's
requirements this is a first-class test for us, not a footnote — and our benchmark suite
already has Arabic prose and Arabic-in-JSON tasks that would expose it.

---

## 4. Hardware feasibility per serious candidate

All **[INFERENCE]**. Nothing below is measured on our machine.

| Candidate | Q4_K_M size | Full GPU offload? | Realistic mode on our box |
|---|---|---|---|
| Qwen3.5-4B / abliterated 4b | ~2.5 GB | **Yes** | Fast tier — full offload + usable context |
| Falcon-H1-Arabic-7B | ~5 GB [FACT] | **Borderline** | Full offload at small ctx, else partial |
| Ministral 3 8B | ~4.9 GB | **Borderline** | Same |
| `qwen3-abliterated:8b` | ~5 GB | **Borderline** | Same |
| `qwen2.5:7b` (control) | ~4.4 GB | **Borderline** | Known 3.5–4 tok/s on CPU |
| Mistral NeMo 12B | ~7 GB | No | Partial offload |
| Hermes 4 14B | ~9 GB | No | Partial offload |
| Gemma 4 26B-A3.8B (MoE) | ~15–16 GB | No | RAM-resident; MoE helps CPU speed only |
| Qwen3.6-35B-A3B (+abliterated) | ~18–20 GB | No | RAM-resident; fits 32 GB, slow but higher quality |
| Qwen3.5/3.6/3.8-27B dense | ~16–19 GB | No | RAM-resident and dense — **expected worst latency** |
| Jais 30B | ~18 GB | No | RAM-resident |
| Falcon-H1-Arabic-34B | ~20 GB | No | RAM-resident |

**Architecture risk [INFERENCE]:** Falcon-H1 is a **hybrid Mamba-Transformer** [FACT].
Hybrid/SSM support in llama.cpp and Ollama has historically lagged plain transformers.
TII publishes official GGUF repos [FACT], which is encouraging, but **whether it loads and
runs correctly under our Ollama build is unverified** and should be checked early — it is
a cheap check that could eliminate the strongest Arabic candidate.

---

## 5. Shortlist — 8 worth downloading later

**Not ranked. No scores. No winner.** Roles only, each justified by cited evidence.

| Role | Candidate | Why this role |
|---|---|---|
| **Smallest / fastest unrestricted** | `huihui_ai/qwen3-abliterated:4b` (or `qwen3.5-abliterated` 4B) | Only tier that plausibly **fully fits 6 GB VRAM** with context headroom [INFERENCE] |
| **Strongest unrestricted Qwen** | `huihui_ai/qwen3.5-abliterated` 8–9B / `qwen3-abliterated:8b` | Newest Qwen base with an abliterated build on Ollama [FACT]; borderline VRAM fit |
| **Strongest Arabic (non-Qwen)** | `Falcon-H1-Arabic-7B-Instruct-GGUF` | **Tops the Open Arabic LLM Leaderboard at 71.47% avg, beating ~10B models** [FACT]; Apache 2.0; ~5 GB GGUF; TII/Abu Dhabi — same market as Rico |
| **Strongest reasoning (non-Qwen)** | `Falcon-H1R-7B` | Reasoning-tuned sibling, Apache 2.0, official GGUF repo [FACT] |
| **Reduced-refusal without abliteration damage** (Category B) | `Hermes 4 14B` | Post-trained for reasoning, **function calling, structured output and reduced refusals** [FACT] — the axis Rico wants, obtained by training not weight surgery |
| **Highest capability, CPU/RAM offload** | `huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated` | Unrestricted + MoE; ~3B active keeps CPU speed tolerable [INFERENCE]; Qwen3.6 rivals much larger dense models [FACT] |
| **Non-Qwen aligned baseline** | `Gemma 4 12B` (or 26B-A3.8B MoE) | **Apache 2.0 with no MAU cap** [FACT] — cleanest licence; different family entirely |
| **Control** | `qwen2.5:7b` | Already measured at 3.5–4 tok/s CPU; keeps new runs comparable to existing evidence |

Deliberately excluded, with reasons:

- **Llama-derived** (`dolphin3:8b`, Hermes 4 36B/70B) as *primary* picks — 700M MAU cap +
  EU multimodal exclusion [FACT] is a poor fit for commercial SaaS. `dolphin3:8b` stays
  useful as an already-measured historical data point only.
- **Dense 27–31B** (Qwen3.5/3.6/3.8-27B, Jais 30B) — RAM-resident *and* dense, the worst
  combination for this box [INFERENCE]. The MoE entry covers the high-capability slot
  better.
- **Qwen3-coder-abliterated** — coder-tuned models trade general/multilingual quality for
  code, and Rico's local model is needed for Arabic career analysis, not coding
  (`REVIEW.md` F-8).

---

## 6. Recommended benchmark set — minimum 5

Satisfies every constraint in the brief with no redundancy:

| # | Model | Constraint satisfied |
|---|---|---|
| 1 | `huihui_ai/qwen3.5-abliterated` (8–9B) | **strong unrestricted Qwen-family** ✓ |
| 2 | `Falcon-H1-Arabic-7B-Instruct-GGUF` | **non-Qwen** ✓ + strongest Arabic evidence |
| 3 | `huihui_ai/qwen3-abliterated:4b` | **smaller/faster** ✓ + only likely full-VRAM-fit |
| 4 | `Huihui-Qwen3.6-35B-A3B-abliterated` | **higher-capability needing CPU offload** ✓ |
| 5 | `qwen2.5:7b` | control, comparability with existing CPU evidence |

Optional 6th if time allows: **Hermes 4 14B**, as the Category-B probe — it is the direct
test of whether reduced-refusal-by-training beats abliteration on Rico's JSON and
tool-calling workloads. Given section 0, this is the most decision-relevant *optional*
model in the set.

**Run order matters.** Test the GPU hypothesis (section 1) *first*, on the 4B. If the GPU
path works, the whole ranking may change, because full-VRAM-fit models gain an advantage
that no CPU benchmark would ever reveal. Benchmarking CPU-only again first would waste the
time and re-answer a question `REVIEW.md` already answered.

Each model runs the existing `bench_ollama.py` suite (prefill/decode/wall-clock separated,
20 strict-JSON attempts, Arabic-in-JSON, UAE-Nationals-only detection), **plus** the new
over-refusal probe from section 0.

---

## 7. What we already know (historical context)

From `REVIEW.md`, CPU-only, **not a hardware verdict**:

- Tested: `qwen2.5:7b`, `qwen2.5-coder:7b`, `huihui_ai/qwen2.5-abliterate:7b`,
  `dolphin3:8b`, `deepseek-r1:7b`
- ~3.5–4 tok/s decode — ~50% of this box's RAM-bandwidth ceiling, i.e. CPU is maxed out
- `qwen2.5:7b` is a useful **control**, explicitly **not** a declared winner
- Those five were four Qwen2.5-7B derivatives + one Llama-3.1-8B — a narrow surface
- The abliterated Qwen2.5 scored **partial** on instruction-following, corroborating the
  abliteration-damage literature above
- `deepseek-r1:7b` timed out on CPU — a model×hardware mismatch, not a quality verdict

---

## 8. Research gaps — cannot be closed without the PC

Ordered by how much each could change the decision.

1. **Does the GPU path work at all?** Everything else is downstream. Test: latest
   R580-branch driver + an Ollama build on the CUDA 12 backend. *Highest value.*
2. **Exact tags, quantizations and file sizes** — blocked by egress here. Confirm on the
   registry before downloading anything.
3. **Real tok/s, prefill and decode, GPU vs CPU** — no throughput claim in this document is
   measured.
4. **Does Falcon-H1's hybrid Mamba-Transformer actually load under our Ollama build?**
   Cheap to check, and a failure eliminates the strongest Arabic candidate.
5. **Does abliteration damage Arabic more than English?** Refusal directions are usually
   computed from English pairs — apparently unmeasured anywhere, and directly material to
   Rico.
6. **How much capability damage did *these specific* abliterated builds take?** The
   literature spans −0.12 pp to −18.81 pp depending on model and method. Per-build, not
   per-label.
7. **Over-refusal rate on Rico's real HR content** — the axis that should actually decide
   "uncensored", and which no public benchmark covers.
8. **JSON reliability at n≥20** for every candidate — unresolved from the previous round.
9. **Whether 6 GB holds a 7–9B Q4 at usable context**, or forces a context cut that breaks
   the long-job-posting workload.
10. **MoE partial-offload behaviour on 6 GB** — experts scatter across layers; whether
    partial offload helps or hurts is genuinely unclear [INFERENCE].

---

## Sources

- CUDA 13 drops Pascal — https://www.tomshardware.com/pc-components/gpus/nvidia-to-drop-cuda-support-for-maxwell-pascal-and-volta-gpus-with-the-next-major-toolkit-release
- CUDA Toolkit 13.1 release notes — https://docs.nvidia.com/cuda/archive/13.1.0/cuda-toolkit-release-notes/index.html
- Ollama issue #17012 (GTX 1060, our exact error) — https://github.com/ollama/ollama/issues/17012
- Ollama issue #17116 — https://github.com/ollama/ollama/issues/17116
- Ollama PR #17196 (Windows CUDA runtime detection / PTX JIT driver floor) — https://github.com/ollama/ollama/pull/17196
- R580 last Pascal driver branch — https://www.techpowerup.com/338497/nvidias-v580-driver-branch-ends-support-for-maxwell-pascal-and-volta-gpus
- Pascal EOL confirmation — https://www.phoronix.com/news/NVIDIA-580-Linux-Driver-Last-HW
- Comparative analysis of LLM abliteration methods — https://arxiv.org/pdf/2512.13655
- Heretic (automatic censorship removal) — https://github.com/p-e-w/heretic
- Abliterated model agentic looping — https://github.com/ggml-org/llama.cpp/discussions/28430
- Structured Output Benchmark — https://arxiv.org/html/2604.25359v1
- Falcon-H1 Arabic launch (TII) — https://www.tii.ae/news/abu-dhabis-tii-launches-falcon-h1-arabic-establishing-worlds-leading-arabic-ai-model
- Falcon-H1 Arabic model page — https://falconllm.tii.ae/falcon-h1-arabic.html
- Falcon-H1R-7B GGUF — https://huggingface.co/tiiuae/Falcon-H1R-7B-GGUF
- Arabic LLM leaderboard landscape 2026 — https://annota8.ai/blog/arabic-llm-benchmark-landscape-2026.html
- Best Arabic local LLMs 2026 (OALL) — https://www.promptquorum.com/local-llms/best-arabic-local-llms-2026
- Qwen3.6-35B-A3B — https://qwen.ai/blog?id=qwen3.6-35b-a3b
- Qwen 3.5 family guide — https://codersera.com/blog/qwen-3-5-complete-guide-2026/
- Mistral 3 / Ministral 3 — https://mistral.ai/news/mistral-3/
- Gemma 4 overview — https://ai.google.dev/gemma/docs/core
- Gemma 4 licence analysis — https://www.interconnects.ai/p/gemma-4-and-what-makes-an-open-model
- huihui_ai Qwen3.6-35B-A3B-abliterated — https://huggingface.co/huihui-ai/Huihui-Qwen3.6-35B-A3B-abliterated
- Nous Hermes 4 local setup — https://vantaige.io/blog/nous-hermes-4-self-hosted-setup-vs-closed-agents-2026
