import json
import unittest

from agesdk import ctgov_report, recall
from agesdk.sources import ctgov, openalex, pubmed
from tests.test_ctgov import FX, registry, study
from tests.test_schema import fresh

PUBMED_XML = """<?xml version="1.0"?><PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID>111</PMID><Article><ArticleTitle>Metformin trial A</ArticleTitle>
<DataBankList><DataBank><DataBankName>ClinicalTrials.gov</DataBankName>
<AccessionNumberList><AccessionNumber>NCT00000001</AccessionNumber></AccessionNumberList></DataBank></DataBankList>
</Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>222</PMID><Article><ArticleTitle>Metformin trial B</ArticleTitle>
<DataBankList><DataBank><DataBankName>ClinicalTrials.gov</DataBankName>
<AccessionNumberList><AccessionNumber>NCT00000099</AccessionNumber></AccessionNumberList></DataBank></DataBankList>
</Article></MedlineCitation></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>333</PMID><Article><ArticleTitle>No registration</ArticleTitle>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""


class Fake:
    def __init__(self, reg):
        self.reg = reg

    def get(self, url, params=None):
        params = params or {}
        if "esearch" in url:
            return 200, json.dumps({"esearchresult": {"idlist": ["333", "111", "222"]}}).encode(), {}
        if "efetch" in url:
            return 200, PUBMED_XML.encode(), {}
        if url.startswith(openalex.BASE):
            cites = {"111": 50, "222": 900, "333": 5000}
            return 200, json.dumps({"results": [{"ids": {"pmid": f"https://pubmed.ncbi.nlm.nih.gov/{p}"},
                                                 "cited_by_count": c} for p, c in cites.items()]}).encode(), {}
        if "/studies/NCT" in url:
            nct = url.rsplit("/", 1)[-1]
            if nct == "NCT00000099":   # a metformin trial our fetch never saw
                rec = {"protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": "x"},
                       "armsInterventionsModule": {"interventions": [{"name": "Metformin XR"}]}}}
                return 200, json.dumps(rec).encode(), {}
            return 200, json.dumps({"protocolSection": self.reg.studies[nct]["protocolSection"]}).encode(), {}
        return self.reg.get(url, params)


class RecallCheck(unittest.TestCase):
    def setUp(self):
        self.conn = fresh()
        self.reg = registry()
        self.reg.studies["NCT00000001"] = study("NCT00000001", [{"type": "DRUG", "name": "Metformin"}])
        self.reg.index["metformin"].append("NCT00000001")
        ctgov.fetch_seed(self.conn, FX, client=self.reg)

    def test_ranked_by_citations_and_registered_only(self):
        f = Fake(self.reg)
        cands = recall.candidates(pubmed.fetcher(self.conn, f), openalex.fetcher(self.conn, f), "metformin", "metformin")
        self.assertEqual([c["pmid"] for c in cands], ["222", "111"])      # 333 has no registration
        self.assertEqual([c["nct_id"] for c in cands], ["NCT00000099", "NCT00000001"])

    def test_classify(self):
        pat = ctgov_report._pattern(["metformin", "Glucophage"])
        rec = lambda ivs, **ps: {"protocolSection": {"armsInterventionsModule": {"interventions": ivs}, **ps}}
        self.assertEqual(recall.classify(rec([{"name": "Metformin"}]), pat), "intervention_name")
        self.assertEqual(recall.classify(rec([{"name": "Study drug", "otherNames": ["Glucophage"]}]), pat),
                         "intervention_other")
        self.assertEqual(recall.classify(rec([{"name": "Placebo"}],
                                             identificationModule={"briefTitle": "Add-on to metformin"}), pat),
                         "arms_or_title")
        self.assertEqual(recall.classify(rec([{"name": "Placebo"}]), pat), "absent")

    def test_miss_is_reported(self):
        fx = {"compounds": [{"key": "metformin", "role": "seed", "canonical_name": "metformin", "must_match": []}]}
        res = recall.run(self.conn, fx, client=Fake(self.reg))
        by = {s["nct_id"]: s for s in res["sample"]}
        self.assertTrue(by["NCT00000001"]["caught"])
        self.assertFalse(by["NCT00000099"]["caught"])
        self.assertEqual(res["summary"]["missed"], ["NCT00000099"])
        self.assertEqual(res["summary"]["eligible"], 2)


if __name__ == "__main__":
    unittest.main()
