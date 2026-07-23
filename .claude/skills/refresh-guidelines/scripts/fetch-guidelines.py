#!/usr/bin/env python3
"""
fetch-guidelines.py — Fetch content from curated web sources for /refresh-guidelines.

Reads curated-sources.md to extract URLs and theme tags, fetches each URL,
extracts text content, and writes structured output to docs/guidelines-raw.json.

Python 3.10+, stdlib only.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


def _read_version() -> str:
    toml_path = pathlib.Path(__file__).resolve().parents[3] / "pyproject.toml"
    try:
        import tomllib  # Python 3.11+
        with open(toml_path, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except (ImportError, Exception):
        try:
            text = toml_path.read_text()
            m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            return m.group(1) if m else "unknown"
        except Exception:
            return "unknown"


_VERSION = _read_version()

# Script-relative paths (stable whether run from project or plugin cache)
SCRIPT_DIR = Path(__file__).resolve().parent
CURATED_SOURCES = SCRIPT_DIR.parent / "references" / "curated-sources.md"


def _resolve_docs_dir(docs_dir_arg: str | None) -> Path:
    """Return the docs output directory, defaulting to cwd/docs."""
    if docs_dir_arg:
        return Path(docs_dir_arg)
    return Path.cwd() / "docs"

# Freshness settings
STALE_THRESHOLD_DAYS = 30
FRESHNESS_TIMEOUT_SECONDS = 15

# Fetch settings
TIMEOUT_SECONDS = 30
MAX_CONTENT_LENGTH = 500_000  # 500KB per source
USER_AGENT = f"claude-md-best-practices/{_VERSION} (fetch-guidelines)"


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

class HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract readable text content."""

    SKIP_TAGS = frozenset([
        "script", "style", "nav", "footer", "header", "aside",
        "noscript", "svg", "iframe", "form",
    ])

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        # Collapse whitespace while preserving paragraph breaks
        lines = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
            elif lines and lines[-1] != "":
                lines.append("")
        return "\n".join(lines).strip()


def strip_html(html_content: str) -> str:
    """Convert HTML to plain text."""
    extractor = HTMLTextExtractor()
    try:
        extractor.feed(html_content)
    except Exception:
        # Fallback: crude tag stripping
        text = re.sub(r"<[^>]+>", " ", html_content)
        return re.sub(r"\s+", " ", text).strip()
    return extractor.get_text()


# ---------------------------------------------------------------------------
# Source parsing
# ---------------------------------------------------------------------------

def parse_curated_sources(path: Path) -> list[dict]:
    """Parse curated-sources.md and extract source entries."""
    content = path.read_text(encoding="utf-8")
    sources: list[dict] = []
    current_tier = 0

    # Match tier section headings
    tier_re = re.compile(r"^## Tier (\d+):", re.MULTILINE)
    # Match source entry headings: ### T1-001: Source Name
    entry_re = re.compile(r"^### (T\d+-\d+):\s*(.+)$", re.MULTILINE)
    # Match metadata fields
    url_re = re.compile(r"^\s*-\s*\*\*URL\*\*:\s*(.+)$", re.MULTILINE)
    themes_re = re.compile(r"^\s*-\s*\*\*Themes\*\*:\s*(.+)$", re.MULTILINE)
    verified_re = re.compile(
        r"^\s*-\s*\*\*Last verified\*\*:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE
    )

    # Split into sections by ### headings
    sections = re.split(r"(?=^### T\d+-\d+:)", content, flags=re.MULTILINE)

    for section in sections:
        # Check for tier heading above this section
        tier_match = tier_re.search(section)
        if tier_match:
            current_tier = int(tier_match.group(1))

        entry_match = entry_re.search(section)
        if not entry_match:
            continue

        source_id = entry_match.group(1)
        source_name = entry_match.group(2).strip()

        # Infer tier from source ID prefix
        tier_from_id = int(source_id[1])
        tier = tier_from_id if tier_from_id > 0 else current_tier

        url_match = url_re.search(section)
        themes_match = themes_re.search(section)
        verified_match = verified_re.search(section)

        if not url_match:
            print(f"  WARNING: No URL found for {source_id}, skipping", file=sys.stderr)
            continue

        url = url_match.group(1).strip()
        themes = []
        if themes_match:
            themes = [t.strip() for t in themes_match.group(1).split(",")]

        last_verified = verified_match.group(1) if verified_match else None

        sources.append({
            "id": source_id,
            "source_name": source_name,
            "url": url,
            "tier": tier,
            "themes": themes,
            "last_verified": last_verified,
        })

    return sources


# ---------------------------------------------------------------------------
# Content fetching
# ---------------------------------------------------------------------------

class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    """Handle HTTP 308 Permanent Redirect (not handled by default urllib)."""

    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)


_opener = urllib.request.build_opener(_RedirectHandler)


def fetch_url(url: str) -> str | None:
    """Fetch content from a URL. Returns text content or None on failure."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html, text/plain, text/markdown, */*",
        },
    )
    try:
        with _opener.open(req, timeout=TIMEOUT_SECONDS) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(MAX_CONTENT_LENGTH)

            # Detect encoding
            encoding = "utf-8"
            if "charset=" in content_type:
                charset_match = re.search(r"charset=([\w-]+)", content_type)
                if charset_match:
                    encoding = charset_match.group(1)

            text = raw.decode(encoding, errors="replace")

            # Strip HTML if content is HTML
            if (
                "html" in content_type.lower()
                or text.strip().startswith("<!")
                or text.strip().startswith("<html")
            ):
                text = strip_html(text)

            return text

    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {url}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"  URL error: {e.reason} — {url}", file=sys.stderr)
    except TimeoutError:
        print(f"  Timeout: {url}", file=sys.stderr)
    except Exception as e:
        print(f"  Error fetching {url}: {e}", file=sys.stderr)

    return None


# ---------------------------------------------------------------------------
# Content block extraction
# ---------------------------------------------------------------------------

def extract_content_blocks(text: str, themes: list[str]) -> list[dict]:
    """Split fetched text into themed content blocks based on headings."""
    blocks: list[dict] = []

    # Split by markdown-style headings (lines starting with # or lines followed by === or ---)
    heading_re = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

    sections: list[tuple[str, str]] = []
    matches = list(heading_re.finditer(text))

    if not matches:
        # No headings found — treat entire text as one block
        if text.strip():
            blocks.append({
                "theme": themes[0] if themes else "content",
                "heading": "(no heading)",
                "text": _truncate(text.strip(), 2000),
            })
        return blocks

    # Extract sections between headings
    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if body:
            sections.append((heading, body))

    # Assign themes to sections based on keyword matching
    theme_keywords = {
        "structural": ["structure", "size", "length", "lines", "format", "section", "organize",
                       "hierarchy", "layout", "template", "skeleton", "file"],
        "content": ["include", "content", "write", "describe", "document", "instruction",
                    "convention", "rule", "guideline", "practice"],
        "anti-patterns": ["avoid", "don't", "mistake", "anti-pattern", "wrong", "bad",
                         "never", "pitfall", "common error", "bloat"],
        "integration": ["hook", "skill", "agent", "setting", "plugin", "mcp", "tool",
                       "automat", "trigger", "event", "config"],
        "behavioral": ["workflow", "pattern", "behavior", "habit", "approach", "style",
                       "prefer", "always", "when", "how to", "process"],
        "maintenance": ["update", "maintain", "review", "refresh", "version", "evolve",
                       "improve", "cadence", "stale", "outdated"],
    }

    for heading, body in sections:
        combined = f"{heading} {body}".lower()

        # Score each theme
        best_theme = themes[0] if themes else "content"
        best_score = 0

        for theme, keywords in theme_keywords.items():
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_theme = theme

        # Only include if theme is in the source's declared themes (or if no filter)
        if not themes or best_theme in themes:
            blocks.append({
                "theme": best_theme,
                "heading": heading,
                "text": _truncate(body, 2000),
            })

    return blocks


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, adding ellipsis if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


# ---------------------------------------------------------------------------
# Source freshness checking
# ---------------------------------------------------------------------------

def check_url_status(
    url: str, timeout: int = FRESHNESS_TIMEOUT_SECONDS
) -> tuple[int | None, str | None]:
    """Check URL reachability via HEAD (fallback to GET on 405).

    Returns (http_status, final_url). On network error returns (None, None).
    """
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(
            url,
            method=method,
            headers={"User-Agent": USER_AGENT},
        )
        try:
            with _opener.open(req, timeout=timeout) as resp:
                return (resp.status, resp.url)
        except urllib.error.HTTPError as e:
            if e.code == 405 and method == "HEAD":
                continue  # retry with GET
            return (e.code, None)
        except (urllib.error.URLError, TimeoutError, OSError):
            return (None, None)

    return (None, None)


def check_source_freshness(
    sources: list[dict],
    stale_threshold_days: int = STALE_THRESHOLD_DAYS,
    today: datetime | None = None,
) -> list[dict]:
    """Check each source for staleness and URL reachability.

    Args:
        sources: Parsed source entries from parse_curated_sources().
        stale_threshold_days: Days after which a source is considered stale.
        today: Override for current date (for testing).

    Returns:
        List of dicts with freshness status per source.
    """
    if today is None:
        today = datetime.now(timezone.utc)

    results: list[dict] = []

    for source in sources:
        last_verified = source.get("last_verified")

        # Compute staleness
        if last_verified:
            verified_date = datetime.strptime(last_verified, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            days_since = (today - verified_date).days
            is_stale = days_since > stale_threshold_days
        else:
            days_since = -1
            is_stale = True  # Missing date = treat as stale

        # Check URL reachability
        http_status, final_url = check_url_status(source["url"])
        is_reachable = http_status is not None and 200 <= http_status < 400

        results.append({
            "id": source["id"],
            "source_name": source["source_name"],
            "url": source["url"],
            "tier": source["tier"],
            "last_verified": last_verified,
            "is_stale": is_stale,
            "days_since_verified": days_since,
            "http_status": http_status,
            "is_reachable": is_reachable,
            "final_url": final_url,
            "needs_attention": is_stale or not is_reachable,
        })

    return results


def check_freshness_main(docs_dir: Path) -> int:
    """Entry point for --check-freshness mode."""
    print(f"fetch-guidelines.py --check-freshness — {datetime.now(timezone.utc).isoformat()}",
          file=sys.stderr)

    if not CURATED_SOURCES.exists():
        print(f"ERROR: Curated sources not found: {CURATED_SOURCES}", file=sys.stderr)
        return 1

    sources = parse_curated_sources(CURATED_SOURCES)
    print(f"Found {len(sources)} sources in curated-sources.md", file=sys.stderr)

    if not sources:
        print("ERROR: No sources found", file=sys.stderr)
        return 1

    print(f"Checking freshness (threshold: {STALE_THRESHOLD_DAYS} days)...\n", file=sys.stderr)
    results = check_source_freshness(sources)

    stale_count = sum(1 for r in results if r["is_stale"])
    broken_count = sum(1 for r in results if not r["is_reachable"])
    attention_count = sum(1 for r in results if r["needs_attention"])

    # Print per-source status
    for r in results:
        status = "OK"
        issue = ""
        if not r["is_reachable"]:
            status = "BROKEN"
            issue = f"HTTP {r['http_status']}" if r["http_status"] else "unreachable"
        elif r["is_stale"]:
            status = "STALE"
            if r["days_since_verified"] == -1:
                issue = "no verified date"
            else:
                issue = f"{r['days_since_verified']} days since verification"
        print(f"  [{r['id']}] {r['source_name']}: {status}"
              + (f" ({issue})" if issue else ""), file=sys.stderr)

    # Write report
    freshness_report_file = docs_dir / "freshness-report.json"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stale_threshold_days": STALE_THRESHOLD_DAYS,
        "total_sources": len(results),
        "stale_count": stale_count,
        "broken_count": broken_count,
        "needs_attention_count": attention_count,
        "sources": results,
    }

    freshness_report_file.parent.mkdir(parents=True, exist_ok=True)
    freshness_report_file.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n--- Freshness Summary ---", file=sys.stderr)
    print(f"Stale: {stale_count}, Broken: {broken_count}, "
          f"Needs attention: {attention_count}, Total: {len(results)}", file=sys.stderr)
    print(f"Report: {freshness_report_file}", file=sys.stderr)

    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def dry_run_main(docs_dir: Path) -> int:
    """Entry point for --dry-run mode. Prints source list without fetching or writing."""
    print(f"fetch-guidelines.py --dry-run — {datetime.now(timezone.utc).isoformat()}",
          file=sys.stderr)

    if not CURATED_SOURCES.exists():
        print(f"ERROR: Curated sources not found: {CURATED_SOURCES}", file=sys.stderr)
        return 1

    sources = parse_curated_sources(CURATED_SOURCES)
    output_file = docs_dir / "guidelines-raw.json"

    print(f"\nDry-run preview — {len(sources)} sources would be fetched:\n", file=sys.stderr)
    for source in sources:
        themes_str = ", ".join(source["themes"]) if source["themes"] else "(no themes)"
        print(f"  [{source['id']}] {source['source_name']}", file=sys.stderr)
        print(f"    URL: {source['url']}", file=sys.stderr)
        print(f"    Themes: {themes_str}", file=sys.stderr)

    print(f"\nWould fetch {len(sources)} sources, would write to {output_file}.",
          file=sys.stderr)
    print("No files written (dry-run mode).", file=sys.stderr)
    return 0


def main(docs_dir: Path | None = None, check_freshness: bool = False,
         dry_run: bool = False) -> int:
    """Fetch content from curated web sources and write to docs_dir.

    Args:
        docs_dir: Output directory (default: cwd/docs).
        check_freshness: Run freshness check instead of fetching content.
        dry_run: Print source list without fetching or writing any files.

    Returns 0 on success, 1 on fatal error.
    """
    resolved_docs_dir = docs_dir if docs_dir is not None else Path.cwd() / "docs"

    if dry_run:
        return dry_run_main(resolved_docs_dir)

    if check_freshness:
        return check_freshness_main(resolved_docs_dir)

    print(f"fetch-guidelines.py — {datetime.now(timezone.utc).isoformat()}", file=sys.stderr)

    # Validate paths
    if not CURATED_SOURCES.exists():
        print(f"ERROR: Curated sources not found: {CURATED_SOURCES}", file=sys.stderr)
        return 1

    output_file = resolved_docs_dir / "guidelines-raw.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Parse sources
    sources = parse_curated_sources(CURATED_SOURCES)
    print(f"Found {len(sources)} sources in curated-sources.md", file=sys.stderr)

    if not sources:
        print("ERROR: No sources found", file=sys.stderr)
        return 1

    # Fetch and process each source
    results: list[dict] = []
    success_count = 0
    fail_count = 0

    for source in sources:
        print(f"\nFetching [{source['id']}] {source['source_name']}...", file=sys.stderr)
        print(f"  URL: {source['url']}", file=sys.stderr)

        text = fetch_url(source["url"])
        if text is None:
            fail_count += 1
            print("  FAILED — skipping", file=sys.stderr)
            continue

        # Extract content blocks
        blocks = extract_content_blocks(text, source["themes"])
        print(f"  OK — extracted {len(blocks)} content blocks", file=sys.stderr)

        results.append({
            "source_id": source["id"],
            "source_url": source["url"],
            "source_name": source["source_name"],
            "tier": source["tier"],
            "themes": source["themes"],
            "last_fetched": datetime.now(timezone.utc).isoformat(),
            "content_blocks": blocks,
        })
        success_count += 1

    # Write output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources_attempted": len(sources),
        "sources_fetched": success_count,
        "sources_failed": fail_count,
        "entries": results,
    }

    output_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n--- Summary ---", file=sys.stderr)
    print(
        f"Sources: {success_count} fetched, {fail_count} failed, {len(sources)} total",
        file=sys.stderr,
    )
    print(f"Output: {output_file}", file=sys.stderr)

    # Return 0 even with partial failures (fault-tolerant)
    if success_count == 0:
        print("ERROR: All sources failed", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    _parser = argparse.ArgumentParser(
        description="Fetch CLAUDE.md best practices from curated web sources."
    )
    _parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Check source URL reachability and staleness instead of fetching content.",
    )
    _parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print source list without fetching or writing any files.",
    )
    _parser.add_argument(
        "--docs-dir",
        metavar="PATH",
        help="Directory for output files (default: ./docs relative to cwd).",
    )
    _args = _parser.parse_args()
    sys.exit(main(
        docs_dir=_resolve_docs_dir(_args.docs_dir),
        check_freshness=_args.check_freshness,
        dry_run=_args.dry_run,
    ))
