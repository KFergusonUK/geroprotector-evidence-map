"""Raw layer: verbatim, append-only storage of every fetch, plus a polite HTTP client.

The raw layer *is* the cache (SPEC §8): ``CachedFetcher`` answers from
``raw_response`` before touching the network, and re-storing identical content
is a no-op, so fetchers are idempotent.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

USER_AGENT = "AgeSDK/0.1 (geroprotector human evidence map; open research)"

# Statuses worth caching: a successful answer, or a definitive "not found".
CACHEABLE_STATUSES = {200, 404}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json(obj) -> str:
    return json.dumps(obj or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StoredResponse:
    id: int
    inserted: bool          # False when identical content was already current
    body: str
    http_status: int | None
    fetched_at: str
    api_version: str | None


class RawStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def latest(self, source: str, endpoint: str, params: dict | None = None):
        return self.conn.execute(
            """SELECT * FROM raw_response
               WHERE source = ? AND endpoint = ? AND request_params = ?
               ORDER BY fetched_at DESC, id DESC LIMIT 1""",
            (source, endpoint, canonical_json(params)),
        ).fetchone()

    def store(self, source: str, endpoint: str, params: dict | None, body: str, *,
              http_status: int | None, api_version: str | None = None,
              meta: dict | None = None, fetched_at: str | None = None) -> StoredResponse:
        """Append a response unless the current row for this request has identical content."""
        digest = sha256_text(body)
        current = self.latest(source, endpoint, params)
        if current is not None and current["content_sha256"] == digest \
                and current["http_status"] == http_status:
            return StoredResponse(current["id"], False, current["response_body"],
                                  current["http_status"], current["fetched_at"],
                                  current["api_version"])
        fetched_at = fetched_at or utc_now()
        cur = self.conn.execute(
            """INSERT INTO raw_response
               (source, endpoint, request_params, response_body, http_status,
                fetched_at, api_version, content_sha256, response_meta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, endpoint, canonical_json(params), body, http_status, fetched_at,
             api_version, digest, canonical_json(meta) if meta else None),
        )
        self.conn.commit()
        return StoredResponse(cur.lastrowid, True, body, http_status, fetched_at, api_version)


class HttpError(RuntimeError):
    pass


class HttpClient:
    """Minimal GET client: per-host rate limiting, retries with backoff on 5xx/timeouts."""

    def __init__(self, min_interval_s: float = 0.5, timeout_s: float = 60.0,
                 retries: int = 3, backoff_s: float = 5.0):
        self.min_interval_s = min_interval_s
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _wait_turn(self, host: str) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last.get(host, 0.0)
            if elapsed < self.min_interval_s:
                time.sleep(self.min_interval_s - elapsed)
            self._last[host] = time.monotonic()

    def get(self, url: str, params: dict | None = None) -> tuple[int, bytes, dict]:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        host = urllib.parse.urlsplit(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait_turn(host)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.status, resp.read(), dict(resp.headers)
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    return e.code, e.read(), dict(e.headers or {})
                last_exc = e
            except (urllib.error.URLError, TimeoutError) as e:
                last_exc = e
            if attempt < self.retries:
                time.sleep(self.backoff_s * (2 ** attempt))
        raise HttpError(f"GET {url} failed after {self.retries + 1} attempts: {last_exc}")


KEPT_HEADERS = ("content-type", "last-modified", "etag", "date")


class CachedFetcher:
    """GET through the raw layer: answer from cache, else fetch, store, return."""

    def __init__(self, conn: sqlite3.Connection, source: str, base_url: str,
                 client: HttpClient, api_version: str | None = None):
        self.store = RawStore(conn)
        self.source = source
        self.base_url = base_url.rstrip("/")
        self.client = client
        self.api_version = api_version

    def get(self, endpoint: str, params: dict | None = None, *, refresh: bool = False) -> StoredResponse:
        endpoint = endpoint.lstrip("/")
        if not refresh:
            row = self.store.latest(self.source, endpoint, params)
            if row is not None:
                return StoredResponse(row["id"], False, row["response_body"], row["http_status"],
                                      row["fetched_at"], row["api_version"])
        status, body, headers = self.client.get(f"{self.base_url}/{endpoint}", params)
        if status not in CACHEABLE_STATUSES:
            raise HttpError(f"{self.source} {endpoint}: HTTP {status}")
        lower = {k.lower(): v for k, v in headers.items()}
        meta = {k: lower[k] for k in KEPT_HEADERS if k in lower}
        return self.store.store(self.source, endpoint, params, body.decode("utf-8"),
                                http_status=status, api_version=self.api_version, meta=meta)

    def get_json(self, endpoint: str, params: dict | None = None, **kw):
        resp = self.get(endpoint, params, **kw)
        return resp.http_status, json.loads(resp.body) if resp.http_status == 200 else None
