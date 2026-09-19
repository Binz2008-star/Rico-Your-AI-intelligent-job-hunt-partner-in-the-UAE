# Benchmark evidence — drop zone

This directory is where the local-model benchmark evidence belongs. It is
currently **empty**, which is finding F-0 in `../REVIEW.md`: the only copy of
the evidence lives on one Windows PC.

## What to copy here

From `C:\Users\loyal\Projects\...` on the development PC:

- `quality_results_MASTER.csv`
- the **21 valid API outputs** (`quality_*.txt`)
- `FINAL_BENCHMARK_SUMMARY.md` / `.csv` once finished
- any `bench_*.json` / `bench_*.csv` produced by `../bench_ollama.py`

## What must NOT be copied here

- The **14 CLI/CUDA-contaminated outputs**. They are not model-quality
  evidence. If they are kept at all, keep them on the PC under a clearly
  named `contaminated/` folder so they can never be mistaken for valid runs.
- Anything containing real user data, real CVs, API keys, or tokens. The
  benchmark suite uses synthetic profiles and a synthetic job posting
  specifically so that nothing sensitive ends up in version control.

## Why this matters

These are small text files with no secrets. Committing them makes the
benchmark auditable by a second reviewer and removes the single-disk failure
risk on P0 evidence.
