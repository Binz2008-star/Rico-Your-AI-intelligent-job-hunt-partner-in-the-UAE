# Troubleshooting

## `ollama ps` says something other than `100% GPU`

The model did not fit. In order of what to try:

1. Lower `num_ctx` in the Modelfile and rebuild (`ollama create hunter-smart -f ...`).
2. Confirm `OLLAMA_KV_CACHE_TYPE=q8_0` is actually set in the *service's* environment —
   `setx` only affects new processes, so you must restart Ollama (see below).
3. Close the browser and anything else using the GPU, then check real free VRAM:
   `nvidia-smi --query-gpu=memory.free --format=csv`
4. Drop to the next tier down. A Tier 1 model at full speed beats a Tier 2 model at 30%.

## Everything is suddenly ~5x slower after an Ollama update

Almost certainly the GPU stopped being used. Run `scripts/doctor.ps1`. If it reports the
GPU is missing, this is the CUDA 13 / Pascal hazard described in `HARDWARE_NOTES.md` —
reinstall the previous Ollama version.

Confirm directly while a model is loaded:

```powershell
nvidia-smi          # is there an ollama process holding VRAM?
ollama ps           # what split does Ollama report?
```

## Environment variables don't seem to take effect

Ollama on Windows runs as a background service started at login. It reads its environment
at start, so a variable set in your current shell is invisible to it.

```powershell
setx OLLAMA_KV_CACHE_TYPE "q8_0"     # persists for future processes
# then fully restart Ollama:
Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force
# relaunch Ollama from the Start menu (or log out and back in)
```

Verify it took:

```powershell
[Environment]::GetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "User")
```

## Out of memory / model fails to load

```
Error: model requires more system memory than is available
```

For Tier 3 this usually means something large is already resident. `ollama ps` shows
what is loaded; `ollama stop <model>` unloads it. Ollama keeps a model in memory for
5 minutes by default — set `OLLAMA_KEEP_ALIVE=30s` if you are switching between tiers a
lot and running into this.

## The model still refuses things

Abliteration is not perfect, and refusals can survive in some phrasings.

- Try `hunter-dolphin` instead — Dolphin 3.0 is an uncensored finetune rather than a
  weight projection, and is generally more compliant.
- A system prompt helps. The shipped Modelfiles already set a direct, non-moralizing one.
- Reformulating the request usually works better than arguing with the model about it.

## `bench.py` can't connect

```
Cannot reach Ollama at http://127.0.0.1:11434
```

Ollama isn't running, or it is bound elsewhere. Start it from the Start menu, then:

```powershell
curl http://127.0.0.1:11434/api/version
```

If you set `OLLAMA_HOST`, pass the same value: `python .\scripts\bench.py --all --host http://...`

## Downloads are slow or keep stalling

`ollama pull` resumes — just re-run the same command. Tier 3 is a ~9 GB download; expect
it to take a while.

## First response after loading is very slow, then it speeds up

Normal. That is the model being read from disk into VRAM plus prompt processing. It only
happens on a cold load. `bench.py` runs a warmup pass before timing for exactly this
reason.
