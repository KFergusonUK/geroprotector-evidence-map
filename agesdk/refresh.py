"""Refresh and change detection (SPEC §11): a diff, not a monitor.

One run = refresh sources → re-process what changed → snapshot derived-view
membership → compare with the previous completed run → changelog. A changelog is
written only when v_cell_transitions has rows for this run. Reviewed decisions are
never touched: refresh writes only to the raw layer, the rebuildable normalised
layer, snapshots and the literature queue.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from agesdk import db, litscan, normalise
from agesdk.raw import utc_now
from agesdk.sources import ctgov, drugage

TRANSITION_TITLES = {
    "entered_gold_cell": "Entered the gold cell",
    "left_under_tested": "Left under-tested",
    "new_harm_candidate": "New harm candidate (needs human review)",
    "results_now_overdue": "Trial results now overdue",
    "itp_tier_changed": "ITP tier changed",
    "harm_review_needs_revisit": "Reviewed harm decision needs revisiting (evidence changed)",
    "review_orphaned": "Reviewed decision orphaned (its evidence no longer exists)",
}
TIER_LABEL = {"measured_lifespan": "measured lifespan", "inherited_class": "inherited via ATC class",
              "mechanistic_only": "MECHANISTIC ONLY — no lifespan evidence"}


def code_version() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=db.PROJECT_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def start_run(conn: sqlite3.Connection, note: str | None = None) -> int:
    cur = conn.execute("INSERT INTO snapshot_run (started_at, status, schema_version, code_version, "
                       "source_versions, note) VALUES (?, 'running', ?, ?, '{}', ?)",
                       (utc_now(), db.SCHEMA_VERSION, code_version(), note))
    conn.commit()
    return cur.lastrowid


def snapshot(conn: sqlite3.Connection, run_id: int, drugage_names: list[str] | None = None) -> int:
    """Store this run's membership: every derived cell, plus churn classes."""
    n = conn.execute("""INSERT INTO snapshot_membership
                        (run_id, cell, cell_class, subject, compound_id, canonical_name, entry_route,
                         evidence_tier, nct_id, state, evidence)
                        SELECT ?, cell, cell_class, subject, compound_id, canonical_name, entry_route,
                               evidence_tier, nct_id, state, evidence
                        FROM v_cell_membership_live""", (run_id,)).rowcount
    # Change class 1: compounds present in the current DrugAge build.
    n += conn.executemany("INSERT OR IGNORE INTO snapshot_membership (run_id, cell, cell_class, subject) "
                          "VALUES (?, 'drugage_compound', 'churn', ?)",
                          [(run_id, name) for name in sorted(set(drugage_names or []))]).rowcount
    conn.commit()
    return n


def finish_run(conn: sqlite3.Connection, run_id: int, source_versions: dict, status: str = "complete") -> None:
    conn.execute("UPDATE snapshot_run SET finished_at = ?, status = ?, source_versions = ? WHERE run_id = ?",
                 (utc_now(), status, json.dumps(source_versions, sort_keys=True), run_id))
    conn.commit()


def transitions(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM v_cell_transitions WHERE run_id = ? ORDER BY transition, canonical_name, subject",
        (run_id,))]


def churn_counts(conn: sqlite3.Connection, run_id: int) -> dict:
    return {f"{r['cell']}:{r['change']}": r["n"] for r in conn.execute(
        "SELECT cell, change, count(*) AS n FROM v_membership_changes WHERE run_id = ? AND cell_class = 'churn' "
        "GROUP BY cell, change", (run_id,))}


def render_changelog(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> str:
    run = dict(conn.execute("SELECT * FROM snapshot_run WHERE run_id = ?", (run_id,)).fetchone())
    sv = json.loads(run["source_versions"])
    lines = [f"# Evidence map changelog — {run['finished_at'][:10]}", "",
             f"Run {run_id} (previous run {rows[0]['prev_run_id'] if rows else '—'}), "
             f"code `{run['code_version'] or 'unknown'}`, schema v{run['schema_version']}.", "",
             "Sources: " + ", ".join(f"{k} `{v}`" for k, v in sorted(sv.items()) if v), "",
             "Only changes of derived-cell membership are listed here. Churn (new DrugAge "
             "compounds, new trials, trial state changes) is logged in the database, not surfaced. "
             "Nothing here changes a reviewed decision: harm-path and direction reviews remain "
             "as a human left them.", ""]
    for t, title in TRANSITION_TITLES.items():
        group = [r for r in rows if r["transition"] == t]
        if not group:
            continue
        lines += [f"## {title} ({len(group)})", ""]
        for r in group:
            name = r["canonical_name"] or r["subject"]
            tier = TIER_LABEL.get(r["evidence_tier"], r["evidence_tier"] or "—")
            state = (f": {r['old_state'] or '—'} → {r['new_state'] or '—'}"
                     if r["change"] == "state_changed" or t == "itp_tier_changed" else "")
            ev = r["new_evidence"] or r["old_evidence"]
            lines.append(f"- **{name}** [{tier}; entry: {r['entry_route'] or '—'}]{state}"
                         + (f" — evidence: `{ev}`" if ev else ""))
        lines.append("")
    return "\n".join(lines)


@dataclass
class RefreshResult:
    run_id: int
    transitions: list[dict]
    churn: dict
    sources: dict = field(default_factory=dict)
    changelog_path: Path | None = None


def run(conn: sqlite3.Connection, *, ctgov_terms: list[str] | None = None, do_ctgov: bool = True,
        do_litscan: bool = True, changelog_dir: Path | None = None, today: date | None = None,
        clients: dict | None = None) -> RefreshResult:
    clients = clients or {}
    run_id = start_run(conn)
    sources: dict = {}
    try:
        da = drugage.refresh(conn, run_id=run_id, client=clients.get("drugage"))
        sources["drugage"] = f"{da['api_version']} sha256:{da['archive_sha256'][:12]}"
        raw_id, rows = drugage.current_raw(conn)
        if da["changed"]:
            sources["drugage_reprocess"] = json.dumps(normalise.reprocess_drugage(conn, raw_id, rows))
        if do_ctgov:
            terms = ctgov_terms if ctgov_terms is not None else \
                [r[0] for r in conn.execute("SELECT canonical_name FROM compound ORDER BY canonical_name")]
            ct = ctgov.refresh(conn, terms, run_id=run_id, client=clients.get("ctgov"))
            sources["ctgov"] = f"{ct['api_version']} data {ct['data_timestamp']} ({ct['terms']} terms)"
        if do_litscan:
            ls = litscan.scan(conn, run_id=run_id, today=today, drugage_rows=rows, client=clients.get("litscan"))
            sources["litscan"] = f"{ls['query_version']} {ls['from']}..{ls['to']} queued {ls['queued']}"
        snapshot(conn, run_id, [r["compound_name"] for r in rows])
        finish_run(conn, run_id, sources)
    except Exception:
        finish_run(conn, run_id, sources, status="failed")
        raise
    rows_t = transitions(conn, run_id)
    result = RefreshResult(run_id, rows_t, churn_counts(conn, run_id), sources)
    if rows_t and changelog_dir is not None:
        changelog_dir.mkdir(parents=True, exist_ok=True)
        day = conn.execute("SELECT finished_at FROM snapshot_run WHERE run_id = ?", (run_id,)).fetchone()[0][:10]
        path = changelog_dir / f"{day}-run{run_id}.md"
        path.write_text(render_changelog(conn, run_id, rows_t), encoding="utf-8")
        result.changelog_path = path
    return result
