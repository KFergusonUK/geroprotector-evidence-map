"""DrugAge (HAGR) bulk download → raw layer.

The zip is binary, so each member is stored as its own raw_response row
(endpoint ``dataset.zip!<member>``) with the archive's hash in response_meta.
Licence: HAGR content is CC-BY 3.0; cite Barardo et al. 2017, Aging Cell 16(3):594-597.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import sqlite3
import zipfile
from datetime import datetime

from agesdk.raw import HttpClient, HttpError, RawStore, StoredResponse, utc_now

SOURCE = "drugage"
URL = "https://genomics.senescence.info/drugs/dataset.zip"
ARCHIVE = "dataset.zip"
CSV_MEMBER = "drugage.csv"
RELEASE_MEMBER = "release.html"
MAX_MEMBER_BYTES = 50 * 1024 * 1024

EXPECTED_COLUMNS = [
    "compound_name", "species", "strain", "dosage", "age_at_initiation",
    "treatment_duration", "avg_lifespan_change_percent", "avg_lifespan_significance",
    "max_lifespan_change_percent", "max_lifespan_significance", "gender",
    "weight_change_percent", "weight_change_significance", "ITP", "pubmed_id",
]

LICENCE = {
    "licence": "CC-BY-3.0",
    "licence_url": "https://genomics.senescence.info/legal.html",
    "citation": "Barardo D. et al. (2017) The DrugAge database of ageing-related drugs. "
                "Aging Cell 16(3):594-597.",
}


class DrugAgeFormatError(ValueError):
    pass


def parse_release(html: str) -> dict:
    """Pull build number and release date out of release.html."""
    text = re.sub(r"<[^>]+>", " ", html)
    out = {}
    if m := re.search(r"DrugAge\s+Build\s+(\d+)", text):
        out["build"] = int(m.group(1))
    if m := re.search(r"Release date:\s*([A-Z][a-z]+ \d{1,2}, \d{4})", text):
        out["release_date"] = datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
    if m := re.search(r"Number of entries:\s*([\d,]+)", text):
        out["entries_stated"] = int(m.group(1).replace(",", ""))
    if m := re.search(r"Number of drugs:\s*([\d,]+)", text):
        out["drugs_stated"] = int(m.group(1).replace(",", ""))
    return out


def api_version_from(release: dict) -> str | None:
    if "build" not in release:
        return None
    date = f" ({release['release_date']})" if "release_date" in release else ""
    return f"Build {release['build']}{date}"


def _read_member(zf: zipfile.ZipFile, name: str) -> bytes:
    info = zf.getinfo(name)  # KeyError if missing: fail loudly
    if info.file_size > MAX_MEMBER_BYTES:
        raise DrugAgeFormatError(f"{name} is {info.file_size} bytes; refusing")
    return zf.read(info)


def validate_csv(text: str) -> int:
    """Check the header is what the loaders expect; return data row count."""
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if header != EXPECTED_COLUMNS:
        raise DrugAgeFormatError(f"DrugAge CSV header changed: {header!r}")
    return sum(1 for _ in reader)


def ingest_archive(conn: sqlite3.Connection, zip_bytes: bytes, *,
                   http_meta: dict | None = None, fetched_at: str | None = None
                   ) -> dict[str, StoredResponse]:
    """Store both members of a DrugAge archive in the raw layer. Idempotent.

    The CSV is stored before validation, so the raw layer keeps exactly what
    arrived even if the format changed; validation then raises.
    """
    fetched_at = fetched_at or utc_now()
    zip_sha = hashlib.sha256(zip_bytes).hexdigest()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        release_html = _read_member(zf, RELEASE_MEMBER).decode("utf-8")
        csv_text = _read_member(zf, CSV_MEMBER).decode("utf-8")
        members = sorted(zf.namelist())

    release = parse_release(release_html)
    version = api_version_from(release)
    store = RawStore(conn)
    params = {"url": URL}
    common = {"archive_sha256": zip_sha, "archive_bytes": len(zip_bytes),
              "archive_members": members, **LICENCE, **(http_meta or {})}

    out = {}
    for member, body in ((RELEASE_MEMBER, release_html), (CSV_MEMBER, csv_text)):
        meta = {**common, "member": member,
                **({"release": release} if member == RELEASE_MEMBER else {})}
        out[member] = store.store(SOURCE, f"{ARCHIVE}!{member}", params, body,
                                  http_status=200, api_version=version, meta=meta,
                                  fetched_at=fetched_at)

    n_rows = validate_csv(csv_text)
    stated = release.get("entries_stated")
    out["_summary"] = {"api_version": version, "csv_rows": n_rows,
                       "entries_stated": stated, "archive_sha256": zip_sha}
    return out


def fetch(conn: sqlite3.Connection, *, refresh: bool = False,
          client: HttpClient | None = None) -> dict:
    """Download DrugAge unless already in the raw layer (or ``refresh``)."""
    store = RawStore(conn)
    if not refresh and store.latest(SOURCE, f"{ARCHIVE}!{CSV_MEMBER}", {"url": URL}):
        return {"skipped": "already in raw layer; use refresh=True to re-download"}
    client = client or HttpClient(min_interval_s=1.0)
    status, body, headers = client.get(URL)
    if status != 200:
        raise HttpError(f"DrugAge download: HTTP {status}")
    lower = {k.lower(): v for k, v in headers.items()}
    http_meta = {k: lower[k] for k in ("last-modified", "etag", "content-type") if k in lower}
    return ingest_archive(conn, body, http_meta=http_meta)


def current_rows(conn: sqlite3.Connection) -> list[dict]:
    """Parsed rows of the current DrugAge CSV in the raw layer."""
    row = RawStore(conn).latest(SOURCE, f"{ARCHIVE}!{CSV_MEMBER}", {"url": URL})
    if row is None:
        raise LookupError("DrugAge not loaded; run `python -m agesdk fetch-drugage`")
    return list(csv.DictReader(io.StringIO(row["response_body"])))
