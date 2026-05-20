#!/usr/bin/env python3
"""Sync GitHub issue/PR activity to linked Asana tasks.

This script is intentionally conservative:
- It never changes Rico application code.
- It only posts comments to Asana tasks that are explicitly linked in a GitHub issue/PR body/comment.
- It skips safely when ASANA_ACCESS_TOKEN is not configured.
- It treats GitHub Issue #147 as the canonical guardrails issue.

Required GitHub Actions env:
    ASANA_ACCESS_TOKEN  optional secret; when absent, sync is skipped
    GITHUB_EVENT_PATH   provided by GitHub Actions
    GITHUB_REPOSITORY   provided by GitHub Actions
    GITHUB_SERVER_URL   provided by GitHub Actions
    GITHUB_RUN_ID       provided by GitHub Actions
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

ASANA_TASK_URL_RE = re.compile(r"https://app\.asana\.com/[^\s)]+/task/(\d+)")
ASANA_GID_RE = re.compile(r"(?:asana[_ -]?task|task[_ -]?gid)[:=]\s*(\d{10,})", re.I)
CANONICAL_GUARDRAILS_ISSUE = "#147"


@dataclass(frozen=True)
class GitHubContext:
    event_name: str
    repo: str
    html_url: str
    title: str
    body: str
    actor: str
    action: str
    state: str | None = None
    merged: bool | None = None


def _load_event() -> dict[str, Any]:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is not set")
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_context(event: dict[str, Any]) -> GitHubContext:
    event_name = os.getenv("GITHUB_EVENT_NAME", "unknown")
    repo = os.getenv("GITHUB_REPOSITORY", "unknown/repo")

    if "pull_request" in event:
        pr = event["pull_request"]
        return GitHubContext(
            event_name=event_name,
            repo=repo,
            html_url=pr.get("html_url", ""),
            title=pr.get("title", ""),
            body=pr.get("body") or "",
            actor=(event.get("sender") or {}).get("login", "unknown"),
            action=event.get("action", "unknown"),
            state=pr.get("state"),
            merged=bool(pr.get("merged")),
        )

    if "issue" in event:
        issue = event["issue"]
        return GitHubContext(
            event_name=event_name,
            repo=repo,
            html_url=issue.get("html_url", ""),
            title=issue.get("title", ""),
            body=issue.get("body") or "",
            actor=(event.get("sender") or {}).get("login", "unknown"),
            action=event.get("action", "unknown"),
            state=issue.get("state"),
        )

    return GitHubContext(
        event_name=event_name,
        repo=repo,
        html_url=os.getenv("GITHUB_SERVER_URL", "https://github.com") + "/" + repo,
        title="GitHub event",
        body=json.dumps(event)[:2000],
        actor="unknown",
        action=event.get("action", "unknown") if isinstance(event, dict) else "unknown",
    )


def _extract_task_gids(*texts: str) -> list[str]:
    gids: set[str] = set()
    for text in texts:
        if not text:
            continue
        gids.update(ASANA_TASK_URL_RE.findall(text))
        gids.update(ASANA_GID_RE.findall(text))
    return sorted(gids)


def _build_asana_comment(ctx: GitHubContext) -> str:
    status_parts = [f"GitHub {ctx.event_name} {ctx.action}".strip()]
    if ctx.state:
        status_parts.append(f"state={ctx.state}")
    if ctx.merged is not None:
        status_parts.append(f"merged={str(ctx.merged).lower()}")

    run_url = ""
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    run_id = os.getenv("GITHUB_RUN_ID")
    if run_id and ctx.repo != "unknown/repo":
        run_url = f"\nWorkflow run: {server}/{ctx.repo}/actions/runs/{run_id}"

    return (
        "Automated Rico sync update\n\n"
        f"Source: {ctx.html_url}\n"
        f"Repository: {ctx.repo}\n"
        f"Title: {ctx.title}\n"
        f"Actor: {ctx.actor}\n"
        f"Status: {'; '.join(status_parts)}"
        f"{run_url}\n\n"
        f"Guardrails reference: {CANONICAL_GUARDRAILS_ISSUE}\n"
    )


def _asana_request(method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = "https://app.asana.com/api/1.0" + path
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps({"data": payload}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Asana API error {exc.code}: {body}") from exc


def _post_task_comment(task_gid: str, comment: str, token: str) -> None:
    _asana_request("POST", f"/tasks/{task_gid}/stories", token, {"text": comment})


def main() -> int:
    token = os.getenv("ASANA_ACCESS_TOKEN", "").strip()
    event = _load_event()
    ctx = _extract_context(event)

    # Include comment body when the event is an issue/PR comment.
    comment_body = ""
    if isinstance(event.get("comment"), dict):
        comment_body = event["comment"].get("body") or ""

    gids = _extract_task_gids(ctx.title, ctx.body, comment_body)

    if not gids:
        print("No linked Asana task IDs found. Nothing to sync.")
        return 0

    if not token:
        print("ASANA_ACCESS_TOKEN is not configured. Found tasks but skipped sync:", ", ".join(gids))
        return 0

    comment = _build_asana_comment(ctx)
    failures: list[str] = []
    for gid in gids:
        try:
            _post_task_comment(gid, comment, token)
            print(f"Synced GitHub event to Asana task {gid}")
        except Exception as exc:  # noqa: BLE001 - keep workflow resilient across multiple tasks
            failures.append(f"{gid}: {exc}")
            print(f"Failed to sync Asana task {gid}: {exc}", file=sys.stderr)

    if failures:
        print("Some Asana sync attempts failed:", file=sys.stderr)
        for failure in failures:
            print("-", failure, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
