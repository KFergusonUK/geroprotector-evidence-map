import json
import unittest

from agesdk import ctgov_report
from agesdk.raw import last_watermark
from agesdk.sources import ctgov
from tests.test_schema import fresh

FX = {"fixture_version": "test", "compounds": [
    {"key": "metformin", "role": "seed", "canonical_name": "metformin",
     "must_match": ["metformin", "Metformin", "Glucophage", "Metformin 500 mg", "metformin HCl"]},
    {"key": "17a", "role": "seed", "canonical_name": "17-alpha-estradiol",
     "must_match": ["17‐alpha‐estradiol", "alfatradiol"]},
    {"key": "maso", "role": "linked_compound", "canonical_name": "masoprocol", "must_match": ["Actinex"]},
]}


def study(nct, interventions, updated="2026-01-01", **extra):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": f"Trial {nct}"},
        "statusModule": {"overallStatus": "COMPLETED", "lastUpdatePostDateStruct": {"date": updated},
                         "primaryCompletionDateStruct": {"date": "2020-01"}},
        "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"], "enrollmentInfo": {"count": 100}},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Acme", "class": "INDUSTRY"}},
        "conditionsModule": {"conditions": ["Type 2 Diabetes"], "keywords": ["glucose"]},
        "armsInterventionsModule": {"interventions": interventions,
                                    "armGroups": [{"label": "A", "type": "EXPERIMENTAL"}]},
        "outcomesModule": {"primaryOutcomes": [{"measure": "All-cause mortality", "timeFrame": "5 years"}]}},
        "derivedSection": {"conditionBrowseModule": {"meshes": [{"id": "D003924", "term": "Diabetes Mellitus, Type 2"}]},
                           "interventionBrowseModule": {"meshes": [{"id": "D008687", "term": "Metformin"}]}},
        "hasResults": False, **extra}


class FakeRegistry:
    def __init__(self, studies, index, data_ts="2026-11-10T10:00:05"):
        self.studies, self.index, self.data_ts = studies, index, data_ts
        self.calls = []

    def get(self, url, params=None):
        params = params or {}
        self.calls.append((url, dict(params)))
        if url.endswith("/version"):
            return 200, json.dumps({"apiVersion": "2.0.5", "dataTimestamp": self.data_ts}).encode(), {}
        if "filter.ids" in params:
            ids = params["filter.ids"].split(",")
            return 200, json.dumps({"studies": [self.studies[i] for i in ids if i in self.studies]}).encode(), {}
        ids = list(self.index.get(params["query.intr"], []))
        since = params.get("filter.advanced", "")
        if since:
            lo = since.split("[")[2].split(",")[0]
            ids = [i for i in ids if self.updated(i) >= lo]
        size = int(params["pageSize"]); start = int(params.get("pageToken", 0))
        page = ids[start:start + size]
        body = {"totalCount": len(ids), "studies": [
            {"protocolSection": {"identificationModule": {"nctId": i},
                                 "statusModule": {"lastUpdatePostDateStruct": {"date": self.updated(i)}}}}
            for i in page]}
        if start + size < len(ids):
            body["nextPageToken"] = str(start + size)
        return 200, json.dumps(body).encode(), {}

    def updated(self, nct):
        return self.studies[nct]["protocolSection"]["statusModule"]["lastUpdatePostDateStruct"]["date"]


def registry():
    s = {
        "NCT1": study("NCT1", [{"type": "DRUG", "name": "Metformin", "otherNames": ["Glucophage"]}]),
        "NCT2": study("NCT2", [{"type": "DRUG", "name": "Study Drug", "otherNames": ["Glucophage XR"],
                                "armGroupLabels": ["A"], "description": "500 mg twice daily",
                                "someFutureField": {"kept": True}}]),
        "NCT3": study("NCT3", [{"type": "DRUG", "name": "Standard care",
                                "description": "includes metformin where indicated"}]),
        "NCT4": study("NCT4", [{"type": "DRUG", "name": "Alfatradiol 0.025% solution"},
                               {"type": "DRUG", "name": "[18F]FDG", "description": "[tracer] imaging"}]),
    }
    idx = {"metformin": ["NCT1", "NCT2", "NCT3"], "Glucophage": ["NCT1", "NCT2"],
           "metformin HCl": ["NCT1"], "17-alpha-estradiol": [], "alfatradiol": ["NCT4"]}
    return FakeRegistry(s, idx)


class QueryPlan(unittest.TestCase):
    def test_terms(self):
        plan = ctgov.seed_query_plan(FX)
        terms = [(p["query_term"], p["compound_key"], p["term_source"]) for p in plan]
        self.assertEqual(terms, [("metformin", "metformin", "canonical_name"),
                                 ("Glucophage", "metformin", "must_match"),
                                 ("metformin HCl", "metformin", "must_match"),
                                 ("17-alpha-estradiol", "17a", "canonical_name"),
                                 ("alfatradiol", "17a", "must_match")])   # dose dropped; dashes and case collapsed

    def test_linked_and_trap_entries_excluded_by_default(self):
        self.assertNotIn("masoprocol", {p["query_term"] for p in ctgov.seed_query_plan(FX)})

    def test_term_claimed_twice_is_an_error(self):
        fx = {"compounds": FX["compounds"] + [{"key": "x", "role": "seed", "canonical_name": "Glucophage",
                                               "must_match": []}]}
        with self.assertRaises(ValueError):
            ctgov.seed_query_plan(fx)


class SeedFetch(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()
        self.reg = registry()
        self.out = ctgov.fetch_seed(self.conn, FX, client=self.reg)

    def test_every_hit_records_its_query_string(self):
        hits = {(r[0], r[1]) for r in self.conn.execute("SELECT query_term, nct_id FROM ctgov_query_hit")}
        self.assertEqual(hits, {("metformin", "NCT1"), ("metformin", "NCT2"), ("metformin", "NCT3"),
                                ("Glucophage", "NCT1"), ("Glucophage", "NCT2"), ("metformin HCl", "NCT1"),
                                ("alfatradiol", "NCT4")})

    def test_each_study_fetched_once(self):
        id_calls = [p["filter.ids"] for u, p in self.reg.calls if "filter.ids" in p]
        fetched = [i for c in id_calls for i in c.split(",")]
        self.assertEqual(sorted(fetched), ["NCT1", "NCT2", "NCT3", "NCT4"])

    def test_intervention_objects_kept_verbatim(self):
        r = dict(self.conn.execute("SELECT * FROM ctgov_intervention WHERE nct_id = 'NCT2'").fetchone())
        self.assertEqual((r["name"], json.loads(r["other_names"]), json.loads(r["arm_group_labels"])),
                         ("Study Drug", ["Glucophage XR"], ["A"]))
        self.assertEqual(json.loads(r["object_json"])["someFutureField"], {"kept": True})

    def test_conditions_outcomes_and_mesh_kept(self):
        s = dict(self.conn.execute("SELECT * FROM ctgov_study WHERE nct_id = 'NCT1'").fetchone())
        self.assertEqual(json.loads(s["conditions_module"])["keywords"], ["glucose"])
        self.assertEqual(json.loads(s["outcomes_module"])["primaryOutcomes"][0]["measure"], "All-cause mortality")
        self.assertEqual(json.loads(s["condition_browse"])["meshes"][0]["id"], "D003924")
        self.assertEqual(json.loads(s["intervention_browse"])["meshes"][0]["term"], "Metformin")
        self.assertIn("protocolSection", json.loads(s["study_json"]))

    def test_api_version_and_params_on_every_response(self):
        rows = self.conn.execute("SELECT api_version, request_params FROM raw_response WHERE source = 'ctgov'").fetchall()
        self.assertTrue(rows)
        for v, p in rows:
            self.assertEqual(v, "2.0.5 data 2026-11-10T10:00:05")
            self.assertTrue({"query.intr", "filter.ids"} & set(json.loads(p)))

    def test_rerun_is_idempotent_and_offline(self):
        raw_before = self.conn.execute("SELECT count(*) FROM raw_response").fetchone()[0]
        calls_before = len(self.reg.calls)
        again = ctgov.fetch_seed(self.conn, FX, client=self.reg)
        self.assertEqual(again["network_calls"], 0)
        self.assertEqual(len(self.reg.calls), calls_before)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM raw_response").fetchone()[0], raw_before)
        self.assertEqual(again["studies"], 4)

    def test_watermarks_recorded_for_incremental_refresh(self):
        self.assertEqual(last_watermark(self.conn, "ctgov", "studies", {"query.intr": "metformin"}), "2026-11-10")

    def test_incremental_refresh_refetches_only_updated(self):
        self.reg.studies["NCT2"]["protocolSection"]["statusModule"]["lastUpdatePostDateStruct"]["date"] = "2026-11-12"
        self.reg.studies["NCT2"]["protocolSection"]["statusModule"]["overallStatus"] = "TERMINATED"
        self.reg.data_ts = "2026-11-17T10:00:00"
        n = len(self.reg.calls)
        out = ctgov.refresh(self.conn, client=self.reg)
        new_ids = [p["filter.ids"] for u, p in self.reg.calls[n:] if "filter.ids" in p]
        self.assertEqual(sorted(set(new_ids)), ["NCT2"])
        self.assertEqual(self.conn.execute("SELECT overall_status FROM ctgov_study WHERE nct_id = 'NCT2'").fetchone()[0],
                         "TERMINATED")
        self.assertEqual(out["studies"], 2)   # NCT2 via 'metformin' and 'Glucophage'

    def test_report_separates_name_from_other_fields(self):
        rep = ctgov_report.build(self.conn)["metformin"]
        self.assertEqual((rep["studies"], rep["name_visible"], rep["not_in_name"]), (3, 1, 2))
        self.assertEqual(rep["not_in_name_by_field"], {"other_names": 1, "description": 1})
        self.assertEqual(rep["per_term_hits"]["metformin"], 3)


if __name__ == "__main__":
    unittest.main()
