# Model selection — why these three, and what was rejected

## The constraint

Everything below follows from one number.

```
GTX 1060                      6.0 GB VRAM
- Windows WDDM reserve        ~0.3 GB
- desktop / browser / compositor  ~0.3-0.7 GB   (more if the 1060 drives your monitors)
------------------------------------------------
usable for Ollama             ~5.0 - 5.3 GB
```

That budget has to cover **the model weights + the KV cache + a compute scratch buffer**.
The KV cache is the part people forget, and it grows linearly with context length. A model
file that "fits" at 4K context stops fitting at 32K.

Rule of thumb used throughout this repo:

```
weights + KV cache  <=  ~4.8 GB      -> safely 100% GPU
weights            5.0-5.5 GB        -> only with q8_0 KV cache and a capped context
weights            > 5.5 GB          -> accept a CPU split, or don't run it
```

## What "abliterated" means

Abliteration identifies the direction in the model's activation space that corresponds to
refusal, and projects it out of the weights. It is not a finetune on new data — the
model's knowledge and style are essentially the base model's, minus the ability to refuse.

Practical consequences:

- Quality is very close to the base model, occasionally a hair worse on reasoning.
- It removes *refusal*, not *judgement* — the model can still be wrong, and it will now be
  confidently wrong about dangerous things too.
- Dolphin-style models are different: those are actual uncensored *finetunes*, not
  projections. They tend to be more thoroughly de-restricted but drift further from the
  base model's behaviour.

Both approaches are represented below.

---

## Selected

### Tier 1 · `hunter-fast` — `huihui_ai/qwen3.5-abliterated:4B`

| | |
|---|---|
| Size | ~2.5 GB (Q4_K_M) |
| VRAM after weights | ~2.7 GB free for KV cache — a lot |
| Placement | 100% GPU |
| Why | Newest generation base available in a size that leaves real headroom. |

The reason this is the default and not the 8B: on a 6 GB card, **context is a resource you
are also buying with VRAM**. A 4B model with 32K of usable context and full GPU residency
is more useful day-to-day than an 8B model pinned at 4K that spills the moment you paste a
long document. Qwen 3.5 is a strong enough generation that the 4B is not a toy.

Qwen 3.5 abliterated is published at 0.8B / 2B / 4B / 9B / 27B / 35B / 122B. The 9B at
Q4_K_M lands around 5.5–5.8 GB, which is over budget — hence 4B here and the older Qwen3
8B in Tier 2.

### Tier 2 · `hunter-smart` — `huihui_ai/qwen3-abliterated:8b-v2-q4_K_M`

| | |
|---|---|
| Size | 5.0 GB (Q4_K_M, 8.19B params) |
| VRAM after weights | ~0.2–0.3 GB. Knife edge. |
| Placement | 100% GPU **only** with `OLLAMA_KV_CACHE_TYPE=q8_0` and a small `num_ctx` |
| Why | The most capable model that can still be fully GPU-resident on this card. |

This is included because sometimes you need the extra reasoning, but it must be treated as
a constrained configuration, not a default. The Modelfile caps context deliberately. If
`ollama ps` does not say `100% GPU`, lower `num_ctx` further.

### Tier 2 alternate · `hunter-dolphin` — `huihui_ai/dolphin3-abliterated:8b`

| | |
|---|---|
| Size | ~4.9 GB (Q4_K_M) |
| Base | Dolphin 3.0 on Llama 3.1 8B, 128K native context |
| Why | The most thoroughly de-restricted 8B that fits. |

Dolphin 3.0 is a genuine uncensored finetune rather than a projection, so it refuses less
often than an abliterated model does. Its 128K native context is mostly theoretical here —
you will not have the VRAM to use it — but it degrades gracefully at moderate lengths.
Pick this over Qwen3-8B when compliance matters more than raw reasoning.

### Tier 3 · `hunter-max` — `huihui_ai/qwen3-abliterated:14b-v2-q4_K_M`

| | |
|---|---|
| Size | ~9 GB (Q4_K_M) |
| Placement | ~55% GPU / 45% system RAM |
| Speed | single-digit tok/s |
| Why | The 32 GB of system RAM makes a 14B *possible*, if not pleasant. |

Worth having installed for hard one-shot questions. Not worth using as a chat model. Run
`bench.py` before you decide whether the quality gain justifies the wait on your workload.

### Vision · `huihui_ai/qwen3-vl-abliterated:4b`

3.3 GB, fits comfortably. Published sizes in that family are 2B (1.9 GB), 4B (3.3 GB),
8B (6.1 GB), 30B (20 GB) — the 8B is already over budget, so 4B is the pick.

---

## Rejected, and why

| Candidate | Verdict |
|---|---|
| `huihui_ai/qwen3.5-abliterated:9B` | ~5.5–5.8 GB at Q4_K_M. Over budget; would spill. The newer generation is not worth losing full GPU residency. |
| Mistral-Nemo 12B abliterated / `dolphin-mistral-nemo:12b` | 7.48 GB at Q4_K_M. Spills, and Qwen3-14B is the better model at a similar penalty. Nemo's 128K context is unusable at this VRAM anyway. |
| Gemma-family abliterated 9B | ~5.8 GB. Same over-budget problem, and Gemma's larger vocabulary inflates the KV cache further. |
| `huihui_ai/qwen3-abliterated:30b-a3b` (MoE) | 3B active params sounds ideal, but the *full* ~18 GB of weights must be resident or streamed. 32 GB RAM makes it technically loadable and painfully slow. |
| Any `IQ2_*` / `IQ3_*` / `IQ4_*` quant | Smaller files, but i-quants are compute-heavy and run slower than Q4_K_M on Pascal. See `HARDWARE_NOTES.md`. |
| `Q8_0` of anything 4B+ | 4B at Q8_0 is ~4.3 GB and does fit. Worth trying if you want maximum quality at Tier 1 size and can live with a shorter context — but the Q4_K_M → Q8_0 quality gain is small compared to the context you give up. |
| 70B anything | Not on 6 GB + 32 GB. Not close. |

---

## Tags move — verify before you trust this file

Ollama registry tags get re-pointed and new generations land regularly. Before relying on
any size in this document:

```powershell
ollama show huihui_ai/qwen3.5-abliterated:4B
ollama list                       # actual on-disk sizes after pulling
ollama ps                         # GPU/CPU split while a model is loaded
python .\scripts\bench.py --all   # real throughput on this machine
```

The sizes here were compiled in September 2026 from the Ollama registry listings. Treat
`bench.py` output as the authority, not this table.
