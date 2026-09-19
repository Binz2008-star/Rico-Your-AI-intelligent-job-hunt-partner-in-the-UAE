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

# 4. Measure real tokens/sec on YOUR box (not someone's blog)
python .\scripts\bench.py --all
```

Then just:

```powershell
ollama run hunter-fast      # daily driver
ollama run hunter-smart     # when you need more reasoning
ollama run hunter-max       # slow, strongest, partially on CPU
```

---

## The three tiers

Pick by what you are doing, not by parameter count.

### Tier 1 — `hunter-fast` (default, use this 90% of the time)

```
Base:  huihui_ai/qwen3.5-abliterated:4B        (~2.5 GB, Q4_K_M)
Fits:  fully on GPU, with room for a large context window
Speed: fast — highest tokens/sec of the three
```

Newest-generation base, fully GPU-resident, and the ~2.7 GB of leftover VRAM buys you a
genuinely long context instead of a 2K window. On a 6 GB card, a small modern model with
room to breathe beats a big model that thrashes.

### Tier 2 — `hunter-smart` (harder reasoning, still all-GPU)

```
Base:  huihui_ai/qwen3-abliterated:8b-v2-q4_K_M   (5.0 GB, 8.19B params)
Alt:   huihui_ai/dolphin3-abliterated:8b          (~4.9 GB, Llama 3.1 base, 128K ctx)
Fits:  only just — requires q8_0 KV cache and a capped context
Speed: roughly half of Tier 1
```

5.0 GB against ~5.2 GB usable is a **knife edge**. `hunter-smart` therefore pins
`num_ctx` low and the setup script sets `OLLAMA_KV_CACHE_TYPE=q8_0`. If you raise the
context, Ollama silently pushes layers to CPU and you lose most of the speed. Watch for it
with `ollama ps` — anything other than `100% GPU` means you overshot.

Dolphin 3.0 is the more thoroughly de-restricted of the two and has a much larger native
context; Qwen3-8B is the stronger reasoner. Both are built and installed — try both.

### Tier 3 — `hunter-max` (strongest, deliberately slow)

```
Base:  huihui_ai/qwen3-abliterated:14b-v2-q4_K_M  (~9 GB)
Fits:  NO — ~55% on GPU, the rest in your 32 GB of RAM
Speed: single-digit tokens/sec. Fine for one-shot hard questions, not for chat.
```

This is where the 32 GB of RAM earns its place. It will not be interactive. Use it when
quality matters more than latency, and expect to wait.

### Bonus — vision

```
huihui_ai/qwen3-vl-abliterated:4b    (3.3 GB) — uncensored image understanding, fits fine
```

Full reasoning behind these picks, with the alternatives that were rejected and why:
[`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md).

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
ollama ps                       # is it 100% GPU, or did it spill to CPU?
python .\scripts\bench.py --all # real tok/s, prompt speed, and GPU/CPU split per model
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
