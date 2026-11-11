# DrugAge ITP rows vs primary sources — audit notes

**Date:** 2026-11-11
**DrugAge:** Build 5 (2024-11-29), archive SHA-256 `d12f5971…`
**Scope:** all 164 DrugAge rows flagged `ITP = Yes`, from 15 papers.
**Question:** does DrugAge's significance flag for each arm agree with the primary source?

## Method

For each ITP paper, the Europe PMC full text (open-access subset; stored in the raw
layer) was retrieved and the DrugAge rows for that PMID were compared, by hand, with the
paper's **pooled-across-sites** survival table: median change with log-rank p, and
90th-percentile change with Wang–Allison p. A DrugAge `S` was taken to mean p < 0.05 in
the corresponding test. Where full text was not retrievable, rows were checked only
against claims stated in the abstract.

Extraction was by one reviewer (Claude), not duplicated. Treat the results as a pilot.

## Coverage

| Paper (PMID) | Year | Rows | Checked against |
|---|---|---|---|
| 24245565 | 2014 | 6 | full-text Table 1 |
| 24341993 | 2014 | 6 | full-text Table 1 |
| 27312235 | 2016 | 18 | full-text Tables 1–2 |
| 30688027 | 2019 | 12 | full-text Table 1 |
| 30916479 | 2019 | 10 | full-text Table 1 (glycine, 2 rows); other 8 rows not in main tables |
| 33145977 | 2020 | 14 | full-text Tables 1–2 |
| 33788371 | 2021 | 10 | full-text Table 1 |
| 36179270 | 2022 | 12 | full-text Table 1 |
| 38041783 | 2024 | 20 | full-text Table 1 |
| 32990681 | 2020 | 2 | abstract (no survival table in text) |
| 18631321 | 2008 | 8 | abstract only (full text not retrievable) |
| 19587680 | 2009 | 8 | abstract only |
| 20974732 | 2011 | 10 | abstract only |
| 22451473 | 2013 | 10 | abstract only |
| 38753230 | 2024 | 18 | abstract only |

**98 rows** checked against a pooled table; the remainder against abstracts where the
abstract states a result for that arm.

## Findings

### Clear discrepancies (corrected in `data/reviews/direction_reviews.yaml`)

| Compound | Arm | DrugAge | Primary source | Consequence |
|---|---|---|---|---|
| Meclizine | F, 800 ppm from 12 mo (PMID 38041783) | +3% **S** | median +3%, log-rank **p = 0.40**; p90 +1%, W–A p = 1.00; abstract: female lifespan "not significantly affected" | female cohort 1/1 → 0/1; tier strong → mixed |
| Protandim | F, 600→1200 ppm from 10 mo (PMID 27312235) | +3% **S** | median +3%, log-rank **p = 0.291**; p90 +6%, W–A p = 0.163 | female cohort 1/1 → 0/1; tier strong → mixed |

### Flag disagreements without direction consequence

| Compound | Arm | DrugAge | Primary source | Note |
|---|---|---|---|---|
| Acarbose | F, 400 ppm from 8 mo (PMID 30688027) | 0% NS | median 0%, log-rank **p = 0.03** | significant log-rank on a 0% median change; direction is `null` either way |

### Borderline — flagged, not corrected

| Compound | Arm | DrugAge | Primary source | Note |
|---|---|---|---|---|
| Mycophenolic acid | F, 6.7 ppm from 9 mo (PMID 38041783) | −1% **S** | median −1%, log-rank **p = 0.05**; title: MPA does "not significantly affect lifespan in either sex" | p = 0.05 as printed is not < 0.05; this row is the compound's only harm-path evidence. Left to the mandatory harm review. |

### Source-internal inconsistency (DrugAge follows the table)

| Compound | Arm | Primary source | Note |
|---|---|---|---|
| 4-phenylbutyrate | F, 1000 ppm from 9 mo (PMID 38041783) | Table 1: median −2%, log-rank **p = 0.01**; title: no significant effect in either sex | DrugAge's `S` (shortening) matches the table. The paper's title and table disagree. |

## Reading

- **2 clear errors in 98 table-checked rows (~2%)**, both in the same direction: a small
  (+3%) female effect recorded as a significant extension, in papers whose headline result
  was male-only. Both inflate apparent sex-general replication, which is exactly the
  pattern the strong tier is meant to detect.
- One under-call (acarbose low dose, female) and one borderline call (MPA) suggest the
  flag is not mechanically "log-rank p < 0.05".
- n = 2 is not evidence of a systematic bias. It is enough to justify a proper study.

## If this becomes a methods paper

1. **Sampling frame:** all mammalian DrugAge rows (not only ITP), stratified by species,
   decade and significance flag; oversample `S` rows on small effects (|Δ| ≤ 5%).
2. **Double independent extraction** from the primary source, with adjudication; record
   the test used, the p-value and the effect as printed.
3. **Pre-specify** the decision rule (p < 0.05 on the paper's primary survival test;
   site-pooled where multi-site).
4. **Outcomes:** disagreement rate overall and by stratum; direction of errors (false
   significant vs false non-significant); consequence for derived conclusions (tier
   changes, harm-path entries, null-cell membership).
5. **Report back to HAGR** with row-level corrections; they maintain the resource.
