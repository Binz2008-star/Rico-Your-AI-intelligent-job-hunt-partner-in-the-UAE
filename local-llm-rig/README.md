# Local Uncensored LLM Rig — GTX 1060 6GB / i7-8700 / 32 GB

A reproducible Ollama setup for running **uncensored (abliterated) local models** on a
Pascal-era 6 GB GPU. Nothing here calls a cloud API — every model runs on your own machine.

> **العربية:** [`README.ar.md`](README.ar.md)

> **This kit is staged inside another repository.** To split it out into its own
> standalone git repo in one step:
> `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-new-repo.ps1`

---

## Target machine

| Component | Spec | Why it matters |
|---|---|---|
| CPU | Intel Core i7-8700 (6C / 12T, 3.2–4.6 GHz, AVX2) | Handles CPU-offloaded layers. No AVX-512, so CPU-only speed is modest. |
| RAM | 32 GB DDR4 | Large enough to spill a 14B model to system memory. This is your headroom. |
| GPU | NVIDIA GTX 1060 6 GB (Pascal, CC 6.1, 192 GB/s) | **6 GB VRAM is the hard limit.** Bandwidth, not compute, sets tokens/sec. |
| OS | Windows 11 Pro | Ollama native Windows build. |

The single number that decides everything: **~5.0–5.3 GB of usable VRAM** after Windows
WDDM and the desktop compositor take their cut. A model file bigger than that gets split
across GPU and CPU, and throughput falls off a cliff.

---

## Quick start

```powershell
# 1. Install Ollama for Windows (once), then:
git clone https://github.com/<you>/ollama-uncensored-lab.git
cd ollama-uncensored-lab

# 2. Check the machine is actually using the GPU
powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1

# 3. Pull the recommended models and build the tuned variants
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1

# 4. Measure real tokens/sec, and real refusal rates, on YOUR box
python .\scripts\bench.py --all
python .\scripts\refusal-probe.py --all
```

Then just:

```powershell
ollama run hunter-open       # default -- most de-restricted that fits
ollama run hunter-open-fast  # same openness, faster, long context
ollama run hunter-dolphin    # different lineage, when hunter-open balks
ollama run hunter-max        # strongest reasoning, slow, refuses more
```

---

## The models, ranked by how de-restricted they are

Compliance is the ranking criterion here, not speed. Speed is the price.

### Why some "uncensored" models are more uncensored than others

Two different techniques, and the difference decides the ranking:

- **Abliteration** projects the refusal direction out of the weights. Surgery, not
  training. Works, but refusals survive in some phrasings and it nicks capability.
- **Uncensored finetuning** (Dolphin, Lexi) retrains on de-aligned data. Holds up better
  on capability and tends to comply more thoroughly.

**Models that do both are the most de-restricted available.** That is the JOSIEFIED
family, and it is why the default below is a JOSIEFIED build rather than a plain
abliterated one.

Also: **the system prompt is part of the model.** The JOSIEFIED builds ship one tuned as
part of the openness finetune, and replacing it with your own weakens compliance. Their
Modelfiles deliberately have no `SYSTEM` block so the tuned one is inherited. Do not
"improve" that.

### 1. `hunter-open` — the default

```
Base:  goekdenizguelmez/JOSIEFIED-Qwen3:8b-q4_k_m   (5.0 GB)
       abliterated AND finetuned for openness -- both treatments
Fits:  100% GPU, but only just: needs q8_0 KV cache and num_ctx 4096
Cost:  knife-edge VRAM, short context, ~half the speed of the 4B
```

Josiefied-Qwen3-8B-abliterated-v1. Listed on the UGI (Uncensored General Intelligence)
leaderboard, which scores willingness rather than capability alone.

**This is the honest trade:** prioritising compliance means running a 5.0 GB model on a
5.2 GB budget. 4096 tokens of context, and it spills to CPU if your desktop grabs more
VRAM. Watch `ollama ps` — anything other than `100% GPU` means you overshot.

### 2. `hunter-open-fast` — when the knife edge gets annoying

```
Base:  goekdenizguelmez/JOSIEFIED-Qwen3:4b-q4_k_m   (~2.5 GB)
Fits:  100% GPU with ~2.7 GB spare -- 16K context and up
```

Same openness treatment, weaker reasoning. Compliance comes from the treatment, not the
parameter count, so you give up intelligence here, not openness. Use it for long documents
and for speed.

### 3. `hunter-dolphin` — the second lineage

```
Base:  huihui_ai/dolphin3-abliterated:8b   (~4.9 GB)
       Dolphin 3.0 uncensored finetune on Llama 3.1, then abliterated
```

Not redundant with `hunter-open`. Refusal behaviour that survives abliteration is specific
to the base model, so when the Qwen lineage balks at a phrasing, the Llama lineage usually
does not. Keeping one of each is the cheapest way to raise your effective ceiling.
**When `hunter-open` refuses, try this before rewriting your prompt.**

### 4. `hunter-max` — reasoning, not compliance

```
Base:  huihui_ai/qwen3-abliterated:14b-v2-q4_K_M   (~9 GB)
Fits:  NO -- ~55% GPU, the rest in your 32 GB of RAM
Speed: single-digit tok/s
```

Abliteration only, no openness finetune, so **it refuses more than the three above**. The
one place here where capability outranks de-restriction — opt in with
`setup.ps1 -IncludeMax`. If it balks, take the question to `hunter-open`.

Full reasoning, the rejected alternatives, and the technique comparison:
[`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md).

---

## Measure the censorship instead of trusting a ranking

The ordering above is a prior built from leaderboard positions and model-card claims. Your
prompts are not their prompts.

```powershell
python .\scripts\refusal-probe.py --all          # refusal + hedge rate per model
python .\scripts\refusal-probe.py --all --show   # and read the actual responses
```

`probes/false-refusal.json` holds lawful requests across the categories where aligned
models most often refuse by mistake — security research, pharmacology, chemistry, physical
security, dark fiction, blunt tone, contested politics, law — plus two in Arabic, because
models routinely refuse in Arabic what they answer in English.

You get two numbers per model:

- **refusal rate** — declined outright
- **hedge rate** — answered, but buried it in disclaimers and moralizing

Both matter. A model at 0% refusal that lectures you every time is still not what you
want. The probe set is a JSON file so you can extend it with your own prompts.

---

## Two things that will bite you on a GTX 1060

These are Pascal-specific and most "best local LLM" guides get them wrong.

**1. CUDA 13 dropped Pascal.** CUDA 13.0 removed support for compute capability 5.0–7.2,
which includes your CC 6.1 card. Support for the GTX 1060 lives on the CUDA 12.x line. If
an Ollama upgrade ever ships a CUDA-13-only build, your GPU silently stops being used and
everything falls back to CPU. **Run `doctor.ps1` after every Ollama update** — it fails
loudly if the GPU has dropped out. Pin your working Ollama version before upgrading.

**2. Do not use IQ-quants.** `IQ2_*`, `IQ3_*`, `IQ4_*` trade compute for size. Pascal does
not have the throughput to absorb that trade, and they routinely run *slower* than the
larger `Q4_K_M` file on this generation of card. Pascal's FP16 rate is also crippled
(1/64 of FP32), so K-quants with FP32 accumulation are the right choice. **Q4_K_M is the
sweet spot; Q5_K_M only if the model is small enough to still fit.**

More: [`docs/HARDWARE_NOTES.md`](docs/HARDWARE_NOTES.md) ·
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)

---

## Verifying, not trusting

Registry tags move and blog benchmarks are run on other people's hardware. Two commands
settle any disagreement on your own machine:

```powershell
ollama ps                            # is it 100% GPU, or did it spill to CPU?
python .\scripts\bench.py --all      # real tok/s and GPU/CPU split per model
python .\scripts\refusal-probe.py --all  # real refusal and hedge rates per model
```

`bench.py` writes `bench-results.json` so you can compare before and after a settings
change instead of guessing.

---

## Responsible use

Abliterated models have had their refusal behaviour removed. That makes them useful for
research, red-teaming, security work, fiction, and for avoiding the false refusals that
make general-purpose models annoying — and it also means **nothing stops them from
producing harmful output**. There is no safety layer between you and the weights. Keep
these models local, do not put an unfiltered one behind a public endpoint, and stay inside
the law that applies to you.

## License

MIT — see [`LICENSE`](LICENSE). Individual model weights carry their own upstream licenses
(Qwen: Apache-2.0; Llama-derived Dolphin: Llama 3.1 Community License). Check them before
any commercial use.
