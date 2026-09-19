# Model selection — ranked by how de-restricted the model is

The priority here is **compliance first**: the least restricted model that will run, with
speed and context treated as the price paid for it. That inverts the usual advice, and it
changes the answer.

## Not all "uncensored" is the same

There are two distinct techniques, and the difference is the single most useful thing to
understand when picking a model.

**Abliteration** identifies the direction in activation space that corresponds to refusal
and projects it out of the weights. It is surgery, not training. It is fast to apply to
any model, and it works — but it is imperfect in two ways: refusals survive in some
phrasings, and cutting out the refusal direction nicks neighbouring capabilities, so the
model gets slightly dumber.

**Uncensored finetuning** (Dolphin, Lexi) retrains the model on data with refusals removed.
It holds up better on capability because nothing is being surgically cut, and it tends to
be more thoroughly compliant because compliance was learned rather than carved in.

**The models that do both are the most de-restricted things available.** Finetune for
openness, then abliterate what survives. That is what the JOSIEFIED family is, and it is
why `hunter-open` is the default here rather than a plain abliterated build.

One more thing that matters more than people expect: **the system prompt is part of the
model.** The JOSIEFIED builds ship a system prompt tuned as part of the openness finetune.
Overriding it with your own generic one measurably weakens compliance. The Modelfiles for
those two models deliberately contain no `SYSTEM` block so the tuned one is inherited.

## The VRAM constraint

Compliance-first does not repeal arithmetic.

```
GTX 1060                          6.0 GB VRAM
- Windows WDDM reserve            ~0.3 GB
- desktop / browser / compositor  ~0.3-0.7 GB
--------------------------------------------
usable for Ollama                 ~5.0 - 5.3 GB
```

That budget covers **weights + KV cache + compute scratch**. The KV cache is the part
people forget, and it grows with context length — a model that fits at 4K stops fitting
at 32K.

```
weights + KV cache  <=  ~4.8 GB    -> safely 100% GPU
weights            5.0-5.5 GB      -> only with q8_0 KV cache and a capped context
weights            > 5.5 GB        -> accept a CPU split, or don't run it
```

---

## Selected, most de-restricted first

### 1. `hunter-open` — `goekdenizguelmez/JOSIEFIED-Qwen3:8b-q4_k_m` · **default**

| | |
|---|---|
| Size | 5.0 GB (Q4_K_M) |
| Treatment | abliterated **and** finetuned for openness — both |
| Placement | 100% GPU, but only just: needs `q8_0` KV cache and `num_ctx 4096` |
| Cost of the choice | knife-edge VRAM, short context, ~half the speed of the 4B |

Josiefied-Qwen3-8B-abliterated-v1. The double treatment is the reason it sits at the top:
the openness finetune handles what abliteration alone leaves behind. It appears on the UGI
(Uncensored General Intelligence) leaderboard, which scores models on willingness rather
than on capability alone — a useful sanity check that this is not just a model card claim.

It ships its own system prompt. Do not override it.

**This is the honest trade.** Prioritising compliance means accepting a 5.0 GB model on a
5.2 GB budget: 4096 tokens of context and a constant risk of spilling to CPU if your
desktop grabs more VRAM. If that becomes annoying, the next entry is the escape hatch.

### 2. `hunter-open-fast` — `goekdenizguelmez/JOSIEFIED-Qwen3:4b-q4_k_m`

| | |
|---|---|
| Size | ~2.5 GB (Q4_K_M) |
| Treatment | same openness finetune + abliteration, smaller base |
| Placement | 100% GPU with ~2.7 GB left over — real context, 16K and up |

Same de-restriction treatment, weaker reasoning. This is the one to use when you want to
paste a long document into an uncensored model, or when you simply want it to be fast.
Compliance is a property of the treatment, not of the parameter count, so you are giving
up intelligence here, not openness.

### 3. `hunter-dolphin` — `huihui_ai/dolphin3-abliterated:8b`

| | |
|---|---|
| Size | ~4.9 GB (Q4_K_M) |
| Treatment | Dolphin 3.0 uncensored finetune on Llama 3.1, then abliterated |
| Why keep it | **different base model** |

This is not redundant with `hunter-open`, and the reason is worth being precise about:
refusal behaviour that survives abliteration is specific to the base model's training.
When a Qwen-lineage model balks at a particular phrasing, a Llama-lineage model very often
does not. Keeping one of each is the cheapest way to raise your effective compliance
ceiling. When `hunter-open` refuses, try this before rewriting your prompt.

### 4. `hunter-max` — `huihui_ai/qwen3-abliterated:14b-v2-q4_K_M`

| | |
|---|---|
| Size | ~9 GB — does not fit |
| Treatment | abliteration only, no openness finetune |
| Placement | ~55% GPU / 45% system RAM. Single-digit tok/s. |

Included for reasoning, not for compliance — **it refuses more than the three above**. It
is the one place in this repo where capability outranks de-restriction, and it is opt-in
(`setup.ps1 -IncludeMax`) for that reason. If it balks, take the question to `hunter-open`.

### Worth knowing about, not wired in

`Orenguteng/Llama-3.1-8B-Lexi-Uncensored-V2` (~4.9 GB, 32K context) has a strong
reputation as about as compliant as an 8B gets, and is a third lineage if you want one.
It is not in `setup.ps1` because its Ollama tag is less stable than the others — pull it
from Hugging Face directly if you want it, and check the current GGUF tag first.

---

## Rejected, and why

| Candidate | Verdict |
|---|---|
| `huihui_ai/qwen3-abliterated:8b-v2-q4_K_M` | Same size and same base as `hunter-open`, abliteration only. Strictly dominated by the JOSIEFIED build. Was the Tier 2 pick before compliance became the ranking criterion; dropped. |
| `huihui_ai/qwen3.5-abliterated:4B` | Newer generation and slightly smarter per GB than the 4B JOSIEFIED, but abliteration only. Under a compliance-first ranking, `hunter-open-fast` wins. |
| `huihui_ai/qwen3.5-abliterated:9B` | ~5.5–5.8 GB. Over budget, and abliteration only. Loses on both axes. |
| Mistral-Nemo 12B abliterated / `dolphin-mistral-nemo:12b` | 7.48 GB at Q4_K_M — spills, and Qwen3-14B is stronger at a similar penalty. Nemo's 128K context is unusable at this VRAM. |
| Gemma-family abliterated 9B | ~5.8 GB, and Gemma's large vocabulary inflates the KV cache further. |
| `huihui_ai/qwen3-abliterated:30b-a3b` (MoE) | 3B active params sounds ideal, but the full ~18 GB of weights must be resident or streamed. Technically loadable with 32 GB RAM, painfully slow. |
| Any `IQ2_*` / `IQ3_*` / `IQ4_*` quant | Smaller, but i-quants run *slower* than Q4_K_M on Pascal. See `HARDWARE_NOTES.md`. |
| `8b-q3_k_m` (4.1 GB) of JOSIEFIED | Tempting — it would end the knife-edge problem. But Q3 quantization degrades instruction-following, and a model that follows instructions worse also complies worse. Q4_K_M is the floor for this use. |
| 70B anything | Not on 6 GB + 32 GB. Not close. |

---

## Measure it, don't take my word for it

The ranking above is a prior, built from model-card claims and leaderboard positions. Your
prompts are not their prompts. Settle it empirically:

```powershell
python .\scripts\refusal-probe.py --all          # refusal + hedge rate per model
python .\scripts\refusal-probe.py --all --show   # and read the actual responses
```

`probes/false-refusal.json` holds the prompt set: lawful requests spanning the categories
where aligned models most often refuse by mistake — security research, pharmacology,
chemistry, physical security, dark fiction, blunt tone, contested politics, law — plus two
in Arabic, because refusal behaviour is language-dependent and models routinely refuse in
Arabic what they answer in English.

Two numbers come back per model:

- **refusal rate** — it declined outright
- **hedge rate** — it answered, but buried the answer in disclaimers and moralizing

Both matter. A model at 0% refusal that lectures you every time is still not the model you
want. Extend the probe set with your own prompts — that is the point of it being a JSON
file.

Detection is heuristic pattern matching, so `--show` exists to let you check its work.

---

## Tags move

Sizes here were compiled in September 2026 from the Ollama registry. Tags get re-pointed
and new generations land. Before trusting any figure above:

```powershell
ollama show goekdenizguelmez/JOSIEFIED-Qwen3:8b-q4_k_m
ollama list                            # real on-disk sizes
ollama ps                              # GPU/CPU split while loaded
python .\scripts\bench.py --all        # real speed
python .\scripts\refusal-probe.py --all  # real compliance
```

The scripts are the authority. This table is a starting point.
