"""Dated pipeline-state backups (SPEC §11.5).

Each weekly run saves the database as a new release tagged
``pipeline-state-YYYY-MM-DD-run<N>``; nothing is overwritten. Retention: keep the
newest KEEP_WEEKLY backups, and beyond those the newest backup of each calendar month,
indefinitely. The newest backup is never pruned.

Used by .github/workflows/weekly-refresh.yml through ``python -m agesdk state-backups``,
which reads ``gh release list --json tagName`` output on stdin.
"""
from __future__ import annotations

import re
from datetime import date

PREFIX = "pipeline-state-"
TAG_RE = re.compile(r"^pipeline-state-(\d{4}-\d{2}-\d{2})-run(\d+)$")
KEEP_WEEKLY = 12


def tag_for(day: date, run_id: int) -> str:
    return f"{PREFIX}{day.isoformat()}-run{run_id}"


def parse(tag: str) -> tuple[date, int] | None:
    m = TAG_RE.match(tag)
    return (date.fromisoformat(m.group(1)), int(m.group(2))) if m else None


def _ordered(tags: list[str]) -> list[str]:
    """State tags, newest first (by date, then run id). Other tags are ignored."""
    parsed = [(parse(t), t) for t in tags]
    return [t for p, t in sorted(((p, t) for p, t in parsed if p), reverse=True)]


def latest(tags: list[str]) -> str | None:
    ordered = _ordered(tags)
    return ordered[0] if ordered else None


def to_prune(tags: list[str], keep_weekly: int = KEEP_WEEKLY) -> list[str]:
    ordered = _ordered(tags)
    keep = set(ordered[:keep_weekly])
    seen_months = set()
    for t in ordered:                          # newest first: first seen per month is kept
        d, _ = parse(t)
        if (d.year, d.month) not in seen_months:
            seen_months.add((d.year, d.month))
            if t not in ordered[:keep_weekly]:
                keep.add(t)
    return [t for t in ordered if t not in keep]
