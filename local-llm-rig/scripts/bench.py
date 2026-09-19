#!/usr/bin/env python3
"""Measure real Ollama throughput and GPU/CPU placement on this machine.

Blog benchmarks were run on someone else's hardware. This one runs on yours.

For each model it reports generation speed, prompt processing speed, cold load time,
and -- the number that matters most on a 6 GB card -- what percentage of the model
actually ended up in VRAM.

Standard library only. No pip install.

    python scripts/bench.py --all
    python scripts/bench.py --model hunter-fast --runs 5
    python scripts/bench.py --all --json results-before.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

DEFAULT_HOST = "http://127.0.0.1:11434"

# Built by setup.ps1. Anything not installed is skipped with a note.
DEFAULT_MODELS = [
    "hunter-fast",
    "hunter-smart",
    "hunter-dolphin",
    "hunter-max",
]

# Long enough to get past warmup noise, short enough that Tier 3 finishes this decade.
PROMPT = (
    "Explain how a CPU cache hierarchy works, and why cache misses dominate the cost "
    "of pointer-chasing data structures. Be specific and concrete."
)

NUM_PREDICT = 200

# Tier 3 runs at single-digit tokens/sec, so a short timeout would fail it spuriously.
TIMEOUT_S = 900


class OllamaError(RuntimeError):
    pass


def _request(host: str, path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = f"{host.rstrip('/')}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace").strip()
        raise OllamaError(f"HTTP {exc.code} from {path}: {body}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"Cannot reach Ollama at {host} ({exc.reason}).") from exc
    except TimeoutError as exc:
        raise OllamaError(f"Timed out after {timeout}s waiting on {path}.") from exc


def installed_models(host: str) -> set[str]:
    tags = _request(host, "/api/tags")
    names = set()
    for model in tags.get("models", []):
        name = model.get("name", "")
        names.add(name)
        # "hunter-fast:latest" should also match a request for "hunter-fast"
        if ":" in name:
            names.add(name.split(":", 1)[0])
    return names


def placement(host: str, model: str) -> dict:
    """Ask Ollama how much of the loaded model is actually in VRAM.

    On a 6 GB card this is the single most useful diagnostic: anything below 100%
    means layers spilled to the CPU and the throughput number needs that context.
    """
    try:
        running = _request(host, "/api/ps")
    except OllamaError:
        return {}

    for entry in running.get("models", []):
        name = entry.get("name", "")
        if name == model or name.split(":", 1)[0] == model:
            total = entry.get("size") or 0
            vram = entry.get("size_vram") or 0
            if not total:
                return {}
            return {
                "total_bytes": total,
                "vram_bytes": vram,
                "gpu_percent": round(100.0 * vram / total, 1),
            }
    return {}


def generate(host: str, model: str, num_predict: int) -> dict:
    payload = {
        "model": model,
        "prompt": PROMPT,
        "stream": False,
        "options": {"num_predict": num_predict},
    }
    return _request(host, "/api/generate", payload, timeout=TIMEOUT_S)


def _rate(count: int | None, duration_ns: int | None) -> float | None:
    """Tokens per second from Ollama's nanosecond timings."""
    if not count or not duration_ns:
        return None
    return count / (duration_ns / 1e9)


def bench_model(host: str, model: str, runs: int) -> dict:
    print(f"\n=== {model} ===")

    print("  warmup (cold load, not timed) ...", end="", flush=True)
    warm_start = time.time()
    try:
        warm = generate(host, model, num_predict=16)
    except OllamaError as exc:
        print(" FAILED")
        return {"model": model, "error": str(exc)}
    print(f" {time.time() - warm_start:.1f}s")

    load_ns = warm.get("load_duration")
    place = placement(host, model)
    if place:
        pct = place["gpu_percent"]
        flag = "" if pct >= 99.5 else "   <-- spilled to CPU"
        print(
            f"  placement: {pct}% GPU "
            f"({place['vram_bytes'] / 1e9:.2f} of {place['total_bytes'] / 1e9:.2f} GB in VRAM)"
            f"{flag}"
        )
    else:
        print("  placement: unavailable (/api/ps reported nothing for this model)")

    gen_rates: list[float] = []
    prompt_rates: list[float] = []

    for i in range(1, runs + 1):
        print(f"  run {i}/{runs} ...", end="", flush=True)
        try:
            result = generate(host, model, NUM_PREDICT)
        except OllamaError as exc:
            print(f" FAILED ({exc})")
            continue

        gen = _rate(result.get("eval_count"), result.get("eval_duration"))
        prm = _rate(result.get("prompt_eval_count"), result.get("prompt_eval_duration"))
        if gen is not None:
            gen_rates.append(gen)
        if prm is not None:
            prompt_rates.append(prm)
        print(f" {gen:.1f} tok/s" if gen is not None else " no timing data")

    if not gen_rates:
        return {"model": model, "error": "every timed run failed"}

    record = {
        "model": model,
        "runs": len(gen_rates),
        "generation_tok_s": {
            "median": round(statistics.median(gen_rates), 2),
            "min": round(min(gen_rates), 2),
            "max": round(max(gen_rates), 2),
        },
        "prompt_tok_s": (
            round(statistics.median(prompt_rates), 2) if prompt_rates else None
        ),
        "cold_load_s": round(load_ns / 1e9, 2) if load_ns else None,
        "placement": place or None,
    }
    print(f"  median: {record['generation_tok_s']['median']} tok/s generation")
    return record


def print_table(records: list[dict]) -> None:
    print("\n" + "=" * 72)
    print(f"{'model':<18}{'gen tok/s':>12}{'prompt tok/s':>14}{'GPU':>8}{'load s':>10}")
    print("-" * 72)
    for rec in records:
        if "error" in rec:
            print(f"{rec['model']:<18}{'-- ' + rec['error'][:48]:>52}")
            continue
        gen = rec["generation_tok_s"]["median"]
        prm = rec["prompt_tok_s"]
        place = rec.get("placement") or {}
        gpu = f"{place['gpu_percent']}%" if place else "?"
        load = rec["cold_load_s"]
        print(
            f"{rec['model']:<18}{gen:>12.1f}"
            f"{(f'{prm:.1f}' if prm else '?'):>14}"
            f"{gpu:>8}"
            f"{(f'{load:.1f}' if load else '?'):>10}"
        )
    print("=" * 72)
    print("Anything below 100% GPU means layers spilled to system RAM.")
    print("Fix that before drawing conclusions from the speed column.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"default {DEFAULT_HOST}")
    parser.add_argument("--model", action="append", dest="models",
                        help="model to benchmark (repeatable)")
    parser.add_argument("--all", action="store_true",
                        help="benchmark every hunter-* model that is installed")
    parser.add_argument("--runs", type=int, default=3, help="timed runs per model")
    parser.add_argument("--json", default="bench-results.json",
                        help="where to write results (default bench-results.json)")
    args = parser.parse_args()

    if not args.models and not args.all:
        parser.error("pass --all, or --model NAME at least once")

    try:
        version = _request(args.host, "/api/version").get("version", "unknown")
    except OllamaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("Is Ollama running? Try: ollama list", file=sys.stderr)
        return 1
    print(f"Ollama {version} at {args.host}")

    try:
        available = installed_models(args.host)
    except OllamaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    wanted = args.models if args.models else DEFAULT_MODELS
    targets = [m for m in wanted if m in available]
    missing = [m for m in wanted if m not in available]

    if missing:
        print(f"skipping (not installed): {', '.join(missing)}")
        if args.models:
            print("Run scripts/setup.ps1 first, or check `ollama list`.")
    if not targets:
        print("error: none of the requested models are installed.", file=sys.stderr)
        return 1

    records = [bench_model(args.host, model, args.runs) for model in targets]
    print_table(records)

    payload = {
        "ollama_version": version,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prompt_tokens_requested": NUM_PREDICT,
        "results": records,
    }
    with open(args.json, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"Wrote {args.json}")

    return 0 if any("error" not in r for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
