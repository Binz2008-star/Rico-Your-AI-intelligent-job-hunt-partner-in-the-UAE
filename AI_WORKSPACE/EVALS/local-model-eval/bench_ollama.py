#!/usr/bin/env python3
"""
Rico local-model benchmark harness (CPU-first, Ollama API).

Purpose
-------
Reproducible, auditable measurement of open-weight models for Rico's real
workloads on the owner's development PC (i7-8700 / 32 GB / GTX 1060 6 GB).

This harness is an *evaluation* tool. It does not import, call, configure, or
modify any Rico production code, provider routing, or configuration.

Why this exists (fixes over the previous benchmark)
---------------------------------------------------
1. Reports PREFILL (prompt processing) and DECODE (generation) separately.
   Rico's dominant workload is "long job posting in, small JSON out", where
   prefill — not decode — dominates wall-clock latency. A single tok/s number
   that only covers decode cannot answer whether a model is usable.
2. Scores JSON as a PASS RATE over n varied prompts, not a single boolean.
   One passing sample is not evidence of the reliability Rico needs.
3. Records the exact quantization / model digest actually executed, so results
   are attributable to a specific artifact rather than a floating tag.
4. Distinguishes TIMEOUT and TRUNCATED from QUALITY FAILURE. A model that ran
   out of budget produced no quality evidence and must not be scored as bad.
5. Preserves every raw output next to the metrics.

Usage
-----
    python bench_ollama.py --models qwen2.5:7b qwen3:4b
    python bench_ollama.py --models qwen3:30b-a3b --timeout 900
    python bench_ollama.py --list-suite

Stdlib only — no pip install required.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# CPU-only by default. num_gpu=0 is deliberate: the GTX 1060 CUDA/PTX
# toolchain incompatibility is tracked separately and must not silently
# contaminate CPU measurements.
BASE_OPTIONS: dict[str, Any] = {
    "num_gpu": 0,
    "temperature": 0,
    "num_ctx": 8192,
}

# Outcome classification. Only QUALITY_* outcomes are admissible as
# model-quality evidence.
OUTCOME_OK = "OK"
OUTCOME_TIMEOUT = "TIMEOUT"
OUTCOME_TRUNCATED = "TRUNCATED"
OUTCOME_ERROR = "ERROR"


# --------------------------------------------------------------------------
# Workload definitions
# --------------------------------------------------------------------------

# A realistic UAE job posting, sized to match what Rico actually feeds the
# model. Synthetic — no real posting, no real user data.
JOB_POSTING = """\
Job Title: Senior Financial Analyst - FP&A
Company: Emaar Hospitality Group
Location: Dubai, United Arab Emirates
Employment Type: Full-time, On-site

About the role:
Reporting to the Head of Financial Planning, the Senior Financial Analyst will
own the monthly forecasting cycle across a portfolio of twelve hospitality
assets in the UAE and KSA. You will partner with asset general managers to
challenge assumptions, build driver-based models, and present variance
commentary to the executive committee.

Responsibilities:
- Own the monthly and quarterly forecast consolidation across the portfolio.
- Build and maintain driver-based revenue models (ADR, occupancy, RevPAR).
- Prepare board-level variance analysis with commercial narrative.
- Partner with Revenue Management on pricing scenario modelling.
- Support the annual budget cycle and 5-year strategic plan.
- Drive automation of recurring reporting in Power BI and Anaplan.

Requirements:
- Bachelor's degree in Finance, Accounting or Economics.
- Professional qualification (CFA, ACCA, CIMA or CPA) strongly preferred.
- 6-9 years of FP&A experience, with at least 3 in hospitality or real estate.
- Advanced financial modelling; Anaplan or similar EPM tool experience.
- GCC market experience required. Arabic is an advantage but not mandatory.
- Candidates must be currently resident in the UAE with a transferable visa.

Benefits: Competitive tax-free salary, annual air ticket, medical insurance
for self and dependants, 30 days annual leave, discretionary bonus.
"""

CANDIDATE_PROFILE = """\
Candidate: 7 years experience. Currently Financial Analyst at a logistics
company in Dubai. ACCA part-qualified (3 papers remaining). Strong Excel and
Power BI. No Anaplan. No hospitality sector experience. UAE resident on
employment visa, transferable with NOC. Arabic: native. English: fluent.
Target roles saved in profile: "Finance Manager", "FP&A Manager".
"""

# Strict schema Rico-style extraction must conform to.
JOB_ANALYSIS_SCHEMA = """\
{
  "role_title": string,
  "seniority": one of ["junior","mid","senior","lead","director"],
  "location_city": string,
  "is_uae_nationals_only": boolean,
  "required_years_experience": integer,
  "must_have_skills": array of string (max 6),
  "fit_score": integer 0-100,
  "fit_rationale": string (max 200 chars),
  "gaps": array of string (max 4)
}"""


@dataclass
class Task:
    """One benchmark task."""

    task_id: str
    category: str
    prompt: str
    system: Optional[str] = None
    # Returns (passed, note). None means "not automatically gradable" —
    # the task is recorded for human/judge review rather than auto-scored.
    grader: Optional[Callable[[str], tuple[bool, str]]] = None
    # Number of independent samples. >1 for reliability measurement.
    samples: int = 1
    # Whether this task's failure is admissible as model-quality evidence.
    admissible_as_quality: bool = True


def _grade_strict_json(raw: str) -> tuple[bool, str]:
    """Strict: the entire response must parse as JSON with the right keys.

    Markdown fences are a FORMAT failure, recorded distinctly from a parse
    failure, because a fenced-but-valid payload is trivially fixable in a
    production adapter while malformed JSON is not.
    """
    text = raw.strip()
    fenced = text.startswith("```")
    if fenced:
        body = text.split("```", 2)
        text = body[1] if len(body) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"parse_error:{exc.msg}"

    if not isinstance(parsed, dict):
        return False, "not_an_object"

    required = {
        "role_title",
        "seniority",
        "location_city",
        "is_uae_nationals_only",
        "required_years_experience",
        "must_have_skills",
        "fit_score",
        "fit_rationale",
        "gaps",
    }
    missing = required - set(parsed)
    if missing:
        return False, f"missing_keys:{sorted(missing)}"

    if not isinstance(parsed["is_uae_nationals_only"], bool):
        return False, "is_uae_nationals_only_not_bool"
    if not isinstance(parsed["fit_score"], int) or not 0 <= parsed["fit_score"] <= 100:
        return False, "fit_score_out_of_contract"
    if not isinstance(parsed["must_have_skills"], list):
        return False, "must_have_skills_not_array"

    return True, "fenced_but_valid" if fenced else "clean"


def _grade_arabic_script(raw: str) -> tuple[bool, str]:
    """Mechanical check only: did the model answer in Arabic script at all?

    This is a floor check, NOT a quality score. Arabic quality must be graded
    by a human Arabic reader or a stronger judge model. Do not report this as
    "Arabic quality".
    """
    arabic = sum(1 for ch in raw if "؀" <= ch <= "ۿ")
    total = sum(1 for ch in raw if ch.isalpha())
    if total == 0:
        return False, "no_text"
    ratio = arabic / total
    return ratio > 0.5, f"arabic_char_ratio={ratio:.2f}"


def build_suite() -> list[Task]:
    """The benchmark suite, weighted toward what Rico actually does."""
    json_prompt_variants = [
        "Extract the structured record. Respond with JSON only.",
        "Return only a JSON object matching the schema. No prose, no markdown.",
        "Parse this posting into the schema below. Output raw JSON.",
        "Give me the JSON record for this job. Nothing else.",
        "Convert the posting to the JSON contract. JSON only in your reply.",
    ]

    tasks: list[Task] = []

    # --- Rico primary workload: long input, small strict-JSON output --------
    # This is the single most decision-relevant task. High sample count
    # because Rico needs schema reliability, not a one-off success.
    for idx, instruction in enumerate(json_prompt_variants):
        tasks.append(
            Task(
                task_id=f"rico_job_extract_json_v{idx + 1}",
                category="rico_structured_extraction",
                system=(
                    "You are a job-posting parser. You output only valid JSON "
                    "conforming exactly to the provided schema."
                ),
                prompt=(
                    f"{instruction}\n\nSchema:\n{JOB_ANALYSIS_SCHEMA}\n\n"
                    f"Candidate profile:\n{CANDIDATE_PROFILE}\n\n"
                    f"Job posting:\n{JOB_POSTING}"
                ),
                grader=_grade_strict_json,
                samples=4,
            )
        )

    # --- Honest fit assessment (Rico must not flatter the user) -------------
    tasks.append(
        Task(
            task_id="rico_fit_honesty",
            category="rico_advice_quality",
            system=(
                "You are Rico, a direct UAE career advisor. You state fit and "
                "risk honestly. You never flatter and never pad with "
                "motivational filler."
            ),
            prompt=(
                f"{CANDIDATE_PROFILE}\n\n{JOB_POSTING}\n\n"
                "Should this candidate apply? Give a direct verdict, the two "
                "strongest gaps, and one better-fitting target role."
            ),
            grader=None,  # judge/human review
            samples=1,
        )
    )

    # --- Arabic: same career task, Arabic in / Arabic out -------------------
    tasks.append(
        Task(
            task_id="rico_arabic_advice",
            category="rico_arabic",
            system="أنت ريكو، مستشار مهني في الإمارات. كن مباشراً وصادقاً.",
            prompt=(
                "أنا محلل مالي لدي سبع سنوات خبرة في دبي، وأحمل شهادة ACCA "
                "جزئية. أريد الانتقال إلى وظيفة مدير تخطيط مالي. ما هي "
                "الفجوات الأساسية في ملفي، وما الخطوات العملية خلال الأشهر "
                "الستة القادمة؟"
            ),
            grader=_grade_arabic_script,  # floor check only
            samples=2,
        )
    )

    # --- Arabic structured output (hardest realistic combination) ----------
    tasks.append(
        Task(
            task_id="rico_arabic_json",
            category="rico_arabic_structured",
            system=(
                "You output only valid JSON. String values must be in Arabic."
            ),
            prompt=(
                "أعد وصفاً منظماً لهذه الوظيفة بصيغة JSON فقط.\n\n"
                f"Schema:\n{JOB_ANALYSIS_SCHEMA}\n\n"
                f"Job posting:\n{JOB_POSTING}"
            ),
            grader=_grade_strict_json,
            samples=2,
        )
    )

    # --- Nationality-restriction detection (a real Rico correctness bug) ---
    tasks.append(
        Task(
            task_id="rico_nationals_only_detection",
            category="rico_eligibility",
            system="You output only valid JSON.",
            prompt=(
                'Does this posting restrict applicants to UAE Nationals only? '
                'Answer with JSON: {"is_uae_nationals_only": boolean, '
                '"evidence": string}\n\n'
                "Posting: Emiratisation priority role. This vacancy is open to "
                "UAE Nationals holding a valid Family Book only.\n"
            ),
            grader=_grade_json_boolean_true,
            samples=3,
        )
    )

    # --- Coding (Rico tooling work, not user-facing) ------------------------
    tasks.append(
        Task(
            task_id="coding_python_function",
            category="coding",
            prompt=(
                "Write a Python function `normalize_target_roles(raw)` that "
                "takes a list of possibly messy role strings and returns a "
                "deduplicated, title-cased list with surrounding whitespace "
                "and trailing punctuation stripped, preserving first-seen "
                "order. Handle None and non-string entries safely. Return only "
                "the function, no explanation."
            ),
            grader=None,
            samples=1,
        )
    )

    return tasks


def _grade_json_boolean_true(raw: str) -> tuple[bool, str]:
    """The nationals-only posting is unambiguous; the answer must be true."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"parse_error:{exc.msg}"
    value = parsed.get("is_uae_nationals_only")
    if value is not True:
        return False, f"wrong_answer:{value!r}"
    return True, "correct"


# --------------------------------------------------------------------------
# Ollama API
# --------------------------------------------------------------------------


@dataclass
class RunResult:
    model: str
    model_digest: str
    quantization: str
    task_id: str
    category: str
    sample_index: int
    outcome: str
    # Prefill (prompt processing)
    prompt_tokens: int = 0
    prefill_seconds: float = 0.0
    prefill_tok_s: float = 0.0
    # Decode (generation)
    output_tokens: int = 0
    decode_seconds: float = 0.0
    decode_tok_s: float = 0.0
    # End to end, what a user would actually wait
    total_seconds: float = 0.0
    load_seconds: float = 0.0
    done_reason: str = ""
    graded: Optional[bool] = None
    grade_note: str = ""
    error: str = ""
    raw_output: str = field(default="", repr=False)


def _post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def describe_model(host: str, model: str, timeout: float = 60.0) -> tuple[str, str]:
    """Return (digest, quantization) so results attribute to a real artifact."""
    try:
        info = _post(f"{host}/api/show", {"model": model}, timeout)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return "unknown", f"unknown ({exc})"
    details = info.get("details") or {}
    quant = details.get("quantization_level") or "unknown"
    digest = (info.get("digest") or "")[:12] or "unknown"
    return digest, quant


def run_once(
    host: str,
    model: str,
    digest: str,
    quant: str,
    task: Task,
    sample_index: int,
    timeout: float,
    num_predict: int,
) -> RunResult:
    result = RunResult(
        model=model,
        model_digest=digest,
        quantization=quant,
        task_id=task.task_id,
        category=task.category,
        sample_index=sample_index,
        outcome=OUTCOME_ERROR,
    )

    options = dict(BASE_OPTIONS)
    options["num_predict"] = num_predict

    payload: dict[str, Any] = {
        "model": model,
        "prompt": task.prompt,
        "stream": False,
        "options": options,
    }
    if task.system:
        payload["system"] = task.system

    started = time.monotonic()
    try:
        body = _post(f"{host}/api/generate", payload, timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed = time.monotonic() - started
        # A socket timeout is indistinguishable from a very slow model here;
        # classify by elapsed time against the budget.
        if elapsed >= timeout * 0.95:
            result.outcome = OUTCOME_TIMEOUT
            result.error = f"timeout after {elapsed:.0f}s"
        else:
            result.error = f"{type(exc).__name__}: {exc}"
        result.total_seconds = elapsed
        return result
    except json.JSONDecodeError as exc:
        result.error = f"bad_response: {exc}"
        result.total_seconds = time.monotonic() - started
        return result

    ns = 1_000_000_000.0
    result.raw_output = body.get("response", "")
    result.prompt_tokens = int(body.get("prompt_eval_count") or 0)
    result.output_tokens = int(body.get("eval_count") or 0)
    result.prefill_seconds = float(body.get("prompt_eval_duration") or 0) / ns
    result.decode_seconds = float(body.get("eval_duration") or 0) / ns
    result.total_seconds = float(body.get("total_duration") or 0) / ns
    result.load_seconds = float(body.get("load_duration") or 0) / ns
    result.done_reason = str(body.get("done_reason") or "")

    if result.prefill_seconds > 0:
        result.prefill_tok_s = result.prompt_tokens / result.prefill_seconds
    if result.decode_seconds > 0:
        result.decode_tok_s = result.output_tokens / result.decode_seconds

    # Hitting the token ceiling means the sample is truncated. A truncated
    # sample is NOT quality evidence — it is a budget artifact.
    if result.done_reason == "length" or result.output_tokens >= num_predict:
        result.outcome = OUTCOME_TRUNCATED
    else:
        result.outcome = OUTCOME_OK

    if task.grader is not None and result.outcome == OUTCOME_OK:
        passed, note = task.grader(result.raw_output)
        result.graded = passed
        result.grade_note = note

    return result


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", help="Ollama model tags to test")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Per-request wall-clock budget in seconds (default 600)",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=700,
        help="Output token ceiling per request (default 700)",
    )
    parser.add_argument(
        "--out",
        default="results",
        help="Output directory for results and raw outputs",
    )
    parser.add_argument(
        "--list-suite", action="store_true", help="Print the suite and exit"
    )
    args = parser.parse_args()

    suite = build_suite()

    if args.list_suite:
        total = sum(t.samples for t in suite)
        print(f"{len(suite)} tasks, {total} requests per model\n")
        for task in suite:
            graded = "auto-graded" if task.grader else "review-only"
            print(f"  {task.task_id:34s} {task.category:28s} n={task.samples}  {graded}")
        return 0

    if not args.models:
        parser.error("--models is required unless --list-suite is used")

    out_dir = Path(args.out)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results: list[RunResult] = []

    for model in args.models:
        digest, quant = describe_model(args.host, model)
        print(f"\n=== {model}  digest={digest}  quant={quant} ===", flush=True)

        for task in suite:
            for sample_index in range(task.samples):
                label = f"{task.task_id}#{sample_index + 1}"
                print(f"  {label:40s} ", end="", flush=True)
                res = run_once(
                    args.host,
                    model,
                    digest,
                    quant,
                    task,
                    sample_index + 1,
                    args.timeout,
                    args.num_predict,
                )
                results.append(res)

                grade = ""
                if res.graded is True:
                    grade = f" PASS ({res.grade_note})"
                elif res.graded is False:
                    grade = f" FAIL ({res.grade_note})"

                print(
                    f"{res.outcome:9s} "
                    f"prefill {res.prompt_tokens:5d}tok/{res.prefill_tok_s:6.1f}t/s  "
                    f"decode {res.output_tokens:4d}tok/{res.decode_tok_s:5.2f}t/s  "
                    f"wall {res.total_seconds:6.1f}s{grade}",
                    flush=True,
                )

                safe_model = model.replace("/", "_").replace(":", "-")
                raw_path = raw_dir / f"{safe_model}__{label.replace('#', '_')}.txt"
                raw_path.write_text(res.raw_output, encoding="utf-8")

    # ---- Persist ---------------------------------------------------------
    rows = [asdict(r) for r in results]
    json_path = out_dir / f"bench_{stamp}.json"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out_dir / f"bench_{stamp}.csv"
    columns = [c for c in rows[0] if c != "raw_output"] if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        import csv as _csv

        writer = _csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    _print_summary(results)
    print(f"\nRaw outputs : {raw_dir}")
    print(f"Results JSON: {json_path}")
    print(f"Results CSV : {csv_path}")
    return 0


def _print_summary(results: list[RunResult]) -> None:
    print("\n" + "=" * 78)
    print("SUMMARY — admissible evidence only (TIMEOUT/TRUNCATED/ERROR excluded")
    print("from quality rates and reported separately)")
    print("=" * 78)

    by_model: dict[str, list[RunResult]] = {}
    for res in results:
        by_model.setdefault(res.model, []).append(res)

    for model, runs in by_model.items():
        ok = [r for r in runs if r.outcome == OUTCOME_OK]
        timeouts = sum(1 for r in runs if r.outcome == OUTCOME_TIMEOUT)
        truncated = sum(1 for r in runs if r.outcome == OUTCOME_TRUNCATED)
        errors = sum(1 for r in runs if r.outcome == OUTCOME_ERROR)

        graded = [r for r in ok if r.graded is not None]
        passed = sum(1 for r in graded if r.graded)

        json_runs = [
            r
            for r in graded
            if r.category
            in {
                "rico_structured_extraction",
                "rico_arabic_structured",
                "rico_eligibility",
            }
        ]
        json_passed = sum(1 for r in json_runs if r.graded)

        def _mean(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        print(f"\n{model}")
        print(f"  quantization      : {runs[0].quantization} (digest {runs[0].model_digest})")
        print(f"  completed         : {len(ok)}/{len(runs)}")
        print(f"  timeout/trunc/err : {timeouts}/{truncated}/{errors}")
        if graded:
            print(f"  auto-graded pass  : {passed}/{len(graded)} ({passed / len(graded):.0%})")
        if json_runs:
            rate = json_passed / len(json_runs)
            print(f"  JSON contract rate: {json_passed}/{len(json_runs)} ({rate:.0%})")
        if ok:
            print(f"  prefill mean      : {_mean([r.prefill_tok_s for r in ok]):.1f} tok/s")
            print(f"  decode mean       : {_mean([r.decode_tok_s for r in ok]):.2f} tok/s")
            print(f"  wall-clock mean   : {_mean([r.total_seconds for r in ok]):.1f} s")
            print(f"  wall-clock max    : {max(r.total_seconds for r in ok):.1f} s")

    print(
        "\nNOTE: review-only tasks (fit honesty, coding, Arabic prose) are NOT "
        "scored here.\nGrade them from the raw outputs with a human reader or a "
        "stronger judge model."
    )


if __name__ == "__main__":
    sys.exit(main())
