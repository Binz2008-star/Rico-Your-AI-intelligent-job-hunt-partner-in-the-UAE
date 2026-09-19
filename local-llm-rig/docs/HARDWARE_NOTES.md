# Pascal-specific notes (GTX 1060 6GB, CC 6.1)

Generic local-LLM advice is written for Ampere and newer. Several pieces of it are wrong
for a 2016 Pascal card. These are the differences that actually change your results.

## 1. CUDA 13 dropped Pascal — this is a ticking upgrade hazard

CUDA 13.0 removed support for compute capability 5.0 through 7.2 (Maxwell, Pascal, Volta).
Supported architectures now start at Turing (sm_75). The GTX 1060 is CC 6.1, so it is
supported only by the **CUDA 12.x** line.

Ollama currently ships runtimes that still cover older architectures, but the failure mode
if that ever changes is nasty: **no error, no warning — the GPU is simply not used** and
generation falls back to the CPU at roughly a fifth of the speed.

Defend against it:

- Run `scripts/doctor.ps1` after every Ollama update. It exits non-zero if the GPU is gone.
- Note the Ollama version that works (`ollama --version`) before upgrading, so you can
  reinstall it.
- If a future release breaks Pascal, the fallback is llama.cpp built against CUDA 12.x.

## 2. Do not use i-quants (IQ2/IQ3/IQ4)

i-quants achieve smaller files by doing more arithmetic per weight. That trade assumes you
have compute to spare. Pascal does not: the GTX 1060 has 192 GB/s of bandwidth and modest
shader throughput, with no tensor cores at all.

The result is counter-intuitive and consistently reported on this generation: an `IQ4_XS`
file can be *smaller and slower* than the `Q4_K_M` of the same model.

**Use `Q4_K_M`.** Use `Q5_K_M` only when the model is small enough that it still fits with
room for the KV cache. Ignore the i-quant column in comparison tables.

## 3. FP16 is crippled on consumer Pascal

GP106 runs FP16 at 1/64 of its FP32 rate. Anything that leans on half-precision math is a
trap. In practice llama.cpp/Ollama handle this correctly by accumulating in FP32 for
K-quants, which is another reason K-quants are the right family here.

The practical consequence: **flash attention is not a guaranteed win on Pascal.** On modern
cards you enable it and move on; here it can be neutral or slower. Measure it:

```powershell
$env:OLLAMA_FLASH_ATTENTION="1"; # restart ollama, then bench
python .\scripts\bench.py --model hunter-open
```

Then set it to `"0"`, restart, and bench again. Keep whichever wins.

## 4. KV cache quantization is the lever that actually matters

On a 6 GB card, the KV cache is often the difference between 100% GPU and a CPU split.
Quantizing it to `q8_0` roughly halves its footprint against the default `f16`, with
quality loss that is hard to notice in practice.

```powershell
setx OLLAMA_KV_CACHE_TYPE "q8_0"
```

`setup.ps1` sets this for you. `q4_0` halves it again and is available if you are
desperate for context on Tier 2, but the quality cost there is real.

## 5. Bandwidth, not the CPU, sets your token rate

Once a model is fully resident on the GPU, generation speed is bounded by how fast the
card can stream the weights: **192 GB/s ÷ model size ≈ theoretical ceiling in tok/s**.
Real throughput lands well below that.

```
2.5 GB model  ->  theoretical ~77 tok/s   ->  expect meaningfully less in practice
5.0 GB model  ->  theoretical ~38 tok/s   ->  expect meaningfully less in practice
```

Two things follow:

- Overclocking the i7-8700 will not speed up a fully-GPU-resident model. It only helps
  once layers have spilled to CPU.
- **Halving the model size roughly doubles the speed.** This is why Tier 1 is the default.

## 6. When layers spill, the CPU side becomes the bottleneck

For `hunter-max`, the ~45% of layers living in system RAM are limited by DDR4 bandwidth
(roughly 40 GB/s dual-channel) and by the i7-8700's AVX2 throughput. Two things help:

- **Confirm your RAM is running in dual-channel.** Two sticks in the correct slots. A
  32 GB single-stick configuration halves memory bandwidth and roughly halves your
  CPU-side token rate. Check in Task Manager → Performance → Memory → "Slots used".
- Leave `num_thread` at Ollama's default. The i7-8700 has 6 physical cores; forcing 12
  threads onto 12 hyperthreads usually makes inference slower, not faster.

## 7. Windows-specific

- **Don't let the 1060 drive a 4K monitor while inferencing** if you can avoid it. Desktop
  composition at high resolution can cost several hundred MB of VRAM — which is exactly
  the margin Tier 2 is operating on.
- Close the browser before running Tier 2. Modern browsers with hardware acceleration
  routinely hold 500 MB+ of VRAM.
- Check the real free VRAM before loading:
  ```powershell
  nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv
  ```
- Keep models off a mechanical drive. First-load time is dominated by disk read; an SSD
  turns a 9 GB Tier 3 load from minutes into seconds.

## Quick reference

| Setting | Value on this machine | Reason |
|---|---|---|
| Quantization | `Q4_K_M` | i-quants are slower on Pascal |
| KV cache type | `q8_0` | Halves cache VRAM, negligible quality cost |
| Flash attention | **measure it** | Not a guaranteed win pre-Turing |
| Max fully-GPU model | ~5.0 GB weights | ~5.2 GB usable VRAM budget |
| CUDA line | 12.x only | CUDA 13 dropped CC 6.1 |
| Threads | Ollama default | 6 physical cores; oversubscription hurts |
