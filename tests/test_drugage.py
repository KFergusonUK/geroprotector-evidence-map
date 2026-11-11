import io
import json
import unittest
import zipfile

from agesdk import db
from agesdk.sources import drugage

RELEASE = """<html><body><h1>DrugAge Build 5: Release Notes</h1>
<p><strong>Release date:</strong> November 29, 2024<br>
<strong>Number of entries:</strong> 3,406<br>
<strong>Number of drugs:</strong> 1045<br></p></body></html>"""

HEADER = ",".join(drugage.EXPECTED_COLUMNS)
ROW = "Rapamycin,Mus musculus,UM-HET3,14 ppm,,,13,S,,NA,Female,,NA,Yes,19587680"


def make_zip(csv_text, release=RELEASE):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("drugage.csv", csv_text)
        zf.writestr("release.html", release)
    return buf.getvalue()


def fresh():
    conn = db.connect(":memory:")
    db.init_db(conn)
    return conn


class DrugAgeIngest(unittest.TestCase):
    def count(self, conn):
        return conn.execute("SELECT count(*) FROM raw_response WHERE source = 'drugage'").fetchone()[0]

    def test_parse_release(self):
        self.assertEqual(drugage.parse_release(RELEASE),
                         {"build": 5, "release_date": "2024-11-29",
                          "entries_stated": 3406, "drugs_stated": 1045})
        self.assertEqual(drugage.api_version_from(drugage.parse_release(RELEASE)), "Build 5 (2024-11-29)")

    def test_ingest_stores_both_members_with_metadata(self):
        conn = fresh()
        out = drugage.ingest_archive(conn, make_zip(f"{HEADER}\n{ROW}\n"))
        self.assertEqual(out["_summary"]["csv_rows"], 1)
        row = conn.execute("SELECT * FROM raw_response WHERE endpoint = 'dataset.zip!drugage.csv'").fetchone()
        self.assertEqual(row["api_version"], "Build 5 (2024-11-29)")
        self.assertEqual(json.loads(row["request_params"]), {"url": drugage.URL})
        meta = json.loads(row["response_meta"])
        self.assertEqual(meta["licence"], "CC-BY-3.0")
        self.assertEqual(len(meta["archive_sha256"]), 64)
        self.assertEqual(drugage.current_rows(conn)[0]["compound_name"], "Rapamycin")

    def test_reingest_is_idempotent(self):
        conn = fresh()
        z = make_zip(f"{HEADER}\n{ROW}\n")
        drugage.ingest_archive(conn, z)
        out = drugage.ingest_archive(conn, z)
        self.assertFalse(out["drugage.csv"].inserted)
        self.assertEqual(self.count(conn), 2)

    def test_changed_data_appends(self):
        conn = fresh()
        drugage.ingest_archive(conn, make_zip(f"{HEADER}\n{ROW}\n"), fetched_at="2026-01-01T00:00:00+00:00")
        drugage.ingest_archive(conn, make_zip(f"{HEADER}\n{ROW}\n{ROW}\n"), fetched_at="2026-02-01T00:00:00+00:00")
        self.assertEqual(self.count(conn), 3)   # release unchanged, CSV appended
        self.assertEqual(len(drugage.current_rows(conn)), 2)

    def test_header_change_is_stored_then_rejected(self):
        conn = fresh()
        with self.assertRaises(drugage.DrugAgeFormatError):
            drugage.ingest_archive(conn, make_zip("compound,species\nX,Y\n"))
        self.assertEqual(self.count(conn), 2)   # raw layer keeps what arrived

    def test_fetch_skips_when_present(self):
        conn = fresh()
        drugage.ingest_archive(conn, make_zip(f"{HEADER}\n{ROW}\n"))

        class Boom:
            def get(self, *a, **k):
                raise AssertionError("network should not be touched")
        self.assertIn("skipped", drugage.fetch(conn, client=Boom()))


if __name__ == "__main__":
    unittest.main()
