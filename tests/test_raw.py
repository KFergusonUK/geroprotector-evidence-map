import unittest

from agesdk import db
from agesdk.raw import CachedFetcher, HttpError, RawStore


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, params=None):
        self.calls += 1
        return self.responses.pop(0)


def fresh():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


class RawStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()
        self.store = RawStore(self.conn)

    def count(self):
        return self.conn.execute("SELECT count(*) FROM raw_response").fetchone()[0]

    def test_identical_content_is_not_duplicated(self):
        a = self.store.store("s", "e", {"q": 1}, "body", http_status=200)
        b = self.store.store("s", "e", {"q": 1}, "body", http_status=200)
        self.assertTrue(a.inserted)
        self.assertFalse(b.inserted)
        self.assertEqual(a.id, b.id)
        self.assertEqual(self.count(), 1)

    def test_param_order_does_not_matter(self):
        self.store.store("s", "e", {"a": 1, "b": 2}, "body", http_status=200)
        self.store.store("s", "e", {"b": 2, "a": 1}, "body", http_status=200)
        self.assertEqual(self.count(), 1)

    def test_changed_content_appends_and_supersedes(self):
        self.store.store("s", "e", None, "v1", http_status=200, fetched_at="2026-01-01T00:00:00+00:00")
        self.store.store("s", "e", None, "v2", http_status=200, fetched_at="2026-02-01T00:00:00+00:00")
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.store.latest("s", "e", None)["response_body"], "v2")
        current = self.conn.execute("SELECT response_body FROM v_raw_current").fetchall()
        self.assertEqual([r[0] for r in current], ["v2"])


class CachedFetcherTests(unittest.TestCase):
    def test_cache_hit_skips_network(self):
        conn = fresh()
        client = FakeClient([(200, b'{"x": 1}', {"Content-Type": "application/json"})])
        f = CachedFetcher(conn, "pubchem", "https://example.org", client)
        self.assertEqual(f.get_json("a/b"), (200, {"x": 1}))
        self.assertEqual(f.get_json("a/b"), (200, {"x": 1}))
        self.assertEqual(client.calls, 1)

    def test_404_is_cached_as_an_answer(self):
        conn = fresh()
        client = FakeClient([(404, b'{"Fault": {}}', {})])
        f = CachedFetcher(conn, "pubchem", "https://example.org", client)
        self.assertEqual(f.get_json("name/unknown"), (404, None))
        self.assertEqual(f.get_json("name/unknown"), (404, None))
        self.assertEqual(client.calls, 1)

    def test_server_errors_are_not_cached(self):
        conn = fresh()
        client = FakeClient([(500, b"oops", {}), (200, b"{}", {})])
        f = CachedFetcher(conn, "chembl", "https://example.org", client)
        with self.assertRaises(HttpError):
            f.get("x")
        self.assertEqual(conn.execute("SELECT count(*) FROM raw_response").fetchone()[0], 0)
        self.assertEqual(f.get_json("x"), (200, {}))


if __name__ == "__main__":
    unittest.main()
