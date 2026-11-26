# Harm-signal checks against primary sources

These are checks of DrugAge rows that show a significant mammal **shortening**. Each one
compares DrugAge against the cited paper before the harm path relies on the row. The
meclizine correction (`data/reviews/direction_reviews.yaml`) is the precedent: DrugAge
marked a non-significant ITP arm as significant.

A row whose **direction** turns out wrong is recorded in `direction_reviews.yaml`. Rows
confirmed below need no record there. This file is the citation trail.

Checked 2026-11-18 by Claude, at Kevin Ferguson's request.

## Miller RA et al. 2024, GeroScience 46(5):4657–4670 (PMID 38753230, PMC11336000)

"Lifespan effects in male UM-HET3 mice treated with sodium thiosulfate, 16-hydroxyestriol,
and late-start canagliflozin."

- **The title is misleading:** the paper reports both sexes.
- **There are two corrections, and neither changes a number:**
  - PMC12397457 (DOI 10.1007/s11357-024-01283-0) adds two authors and restores the
    AKG_Late group in Figure 3.
  - PMC12634909 (DOI 10.1007/s11357-025-01752-0) replaces "16-hydroxyestriol" with
    "16-hydroxyestradiol" in the title, abstract, introduction, discussion and Table 1.

Figures below are from Table 2 (survival) and Table 1 (dose and start age), read on the
PMC article page.

| Group (Table 1) | Sex | Median % change, log-rank p | 90th percentile % change, Wang–Allison p | DrugAge | Verdict |
|---|---|---|---|---|---|
| Canagliflozin 180 ppm from 16 months, UM and UT sites only | F | **−6.1, p = 0.03** | −8.2, p = 0.23 | avg −6 S, max −8 NS | **Confirmed** |
| | M | +13.8, p = 0.004 | +4.2, p = 0.04 | +14 S, +4 S | Confirmed |
| Canagliflozin 180 ppm from 6 months, TJL site only | F | −1.3, p = 0.90 | +4.0, p = 0.79 | −1 NS, +4 NS | Confirmed |
| | M | +8.8, p = 0.02 | +4.5, p = 0.09 | +9 S, +5 NS | Confirmed |
| Nebivolol 60 ppm from 6 months | F | **−4.2, p = 0.03** | −4.7, p = 0.16 | avg **−5** S, max −5 NS | **Direction and significance confirmed.** DrugAge's median −5 is reported as −4.2 in the paper. The magnitude is slightly off; no direction review |
| | M | −3.4, p = 0.62 | −0.9, p = 0.50 | −3 NS, −1 NS | Confirmed |
| OH_Est 5 ppm from 12 months (= estriol, see below) | F | **−6.5, p = 0.002** | −4.5, p = 0.16 | −7 S, −5 NS | **Confirmed** |
| | M | +15.1, p = 0.0001 | +4.6, p = 0.03 | +15 S, +5 S | Confirmed |

### What weight the confirmed female shortenings bear

**Canagliflozin.**
- The shortening is a single experiment, and it is late-start only. Started at 6 months,
  females are unaffected, both here and in the earlier ITP study (PMID 32990681).
- The late-start group ran at two of three sites. A technical error at TJL started that
  site's mice at 6 months (Results).
- The authors' proposed mechanism (abstract): blood levels "approximately 20-fold higher in
  aged females than in young males", which points to accumulation in older females.
- Under the ITP tier rules (strong needs at least 2 independent experiments) it is not a
  strong signal. It is relevant all the same, because older women are prescribed SGLT2
  inhibitors.

**Nebivolol.** A single experiment, with a −4.2% median that is significant on median only.

**Estriol.** A single experiment with all three sites pooled. Its p = 0.002 is the
strongest female shortening in the paper, and it comes with the strongest male benefit.

### Identity: the ITP's "OH_Est" is estriol

The two names in the record each give half the answer:
- **The original paper** says "16α-hydroxyestriol". PubChem has no record of that name.
- **The 2025 correction** says "16-hydroxyestradiol". That name gives the parent but not
  the stereochemistry: 16β is 16-epiestriol, a different molecule.

Together they give **16α-hydroxyestradiol, which is estriol**. PubChem resolves that name
to CID 5756, InChIKey PROQIPRRNZUXQM-ZXXIGWHRSA-N. DrugAge already uses the corrected
name.

**Open:** the CAS number or supplier was not checked. The paper's Supplementary
Information was not read, and it should be checked before any published claim rests on
estriol.

Estriol is an approved hormone drug used mainly by women, and largely by the vaginal route,
which §5.6 treats as local. It was added as a seed compound on 2026-11-18 (fixture 0.9.0;
see the fixture's `decisions`). Its auto-accepts are measured by census before use
(`docs/estriol_census_protocol.md`).

## Not yet checked (candidates from the same review)

- **Metformin −14%** (PMID 23900241). This was at 10,000 ppm, ten times the dose that gave
  +6% in the same study, so it is a toxicity-dose result. The harm review must see the
  dose.
- **Aspirin −10% and chloroquine −8%**, both from one 1973 study (PMID 4788962). Neither
  effect follows dose: aspirin is null at 113 ppm and at 495 ppm but −10% at 242 ppm.
- **Phenobarbital −17% and nicotine −11%**, both from one 1976 rat study (PMID 132031).
- **Quercetin −14%** (PMID 7140862, 1982), a single study.
- **Mycophenolic acid −1% "significant"** (PMID 38041783). This looks like the meclizine
  pattern. Kevin Ferguson decided to leave it unresolved.

**A structural point for the harm review:** one source paper can produce several harm
candidates. The review should see when candidates share a PMID.

## Additional DrugAge Build 5 candidates checked 2026-11-26

The verdict concerns whether the cited paper supports the row as transcribed. It does not
mean that a mouse or rat result establishes harm in people. For older papers whose full
tables were unavailable, I have not inferred the exact result from DrugAge.

### Metformin — Martin-Montalvo et al. 2013 (PMID 23900241)

The full paper is available in [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3736576/).
Its abstract says the 0.1% dietary dose extended lifespan in male mice, while the higher
1% dose was toxic. The Results report mean lifespan **+5.83%** at 0.1% in C57BL/6 mice
(*p* = 0.02), **+4.15%** in B6C3F1 mice (*p* = 0.064), and **−14.4%** at 1% in C57BL/6
mice (*p* < 0.001), likely due to renal failure. Thus the DrugAge row at 10,000 ppm
(1%) is **confirmed** in direction, magnitude and significance; 1,000 ppm is the same
paper's 0.1% dose. The authors explicitly call 1% toxic. This is a dose-specific toxic
harm signal, not evidence that ordinary human metformin exposure shortens life. The
opposite results at 0.1% and 1% also mean the shortening does not follow a simple
monotonic dose-response.

### Aspirin and chloroquine — Hochschild 1973 (PMID 4788962)

The publisher exposes the [abstract](https://karger.com/ggi/article-abstract/19/5-6/271/148550/Effects-of-Various-Drugs-on-Longevity-in-Female?redirectedFrom=PDF),
but the article's tables and full text are subscriber-only in the copy available for this
check. The abstract says that, aside from two cases of apparently toxic effects, lifespan
differences were not significant at *p* < 0.05; it does not identify the two cases or give
the dose-specific survival statistics. I therefore cannot verify DrugAge's aspirin
−10% (*S*) at 242 ppm, its 0% arms at 113 and 495 ppm, or chloroquine −8% (*S*) at
13.2 ppm and 0% at 39.5 ppm against the paper's table. **Verdict: not independently
verified (full table unavailable); no direction/significance correction proposed.** If
the supplied rows are accurate, their pattern is non-monotonic for both compounds, and
the reported shortenings could be the paper's two toxic cases; that remains a hypothesis,
not a verified reading. Aspirin and chloroquine are two rows from one study, not
independent replications.

### Phenobarbital and nicotine — Schmähl & Habs 1976 (PMID 132031)

The [publisher summary](https://link.springer.com/article/10.1007/BF00304936) and PubMed
abstract are accessible; the full article/table is not. The abstract reports 858
Sprague-Dawley rats across 12 substances and says nicotine and phenobarbital “diminish
the mean survival times.” This supports the **qualitative shortening direction** for
both, but does not expose the sex-specific means, dose, *p*-values, or control-group
construction. The DrugAge magnitudes (phenobarbital −9.6% female / −16.7% male;
nicotine −8.5% female / −11.5% male) and the stated 2 mg/kg/week dose therefore remain
**unverified against the paper's table**. The compounds are certainly from the same
paper; whether they shared a single concurrent control cannot be checked from the
accessible abstract. No numeric or significance correction is proposed without the
table.

### Quercetin — Jones & Hughes 1982 (PMID 7140862)

The [PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/7140862/) is accessible, but the
full table is not. It says a dietary supplement of 0.1% quercetin “significantly reduced
the life span of mice” and that the effect was predominantly in shorter-lived males.
This confirms the **qualitative direction and reported significance** of the male harm
signal, and supports a sex difference. It does not give the male −14% or female −6%
(*NS*) values; those magnitudes and female statistics remain unverified. **Verdict:
direction/significance confirmed from the abstract; magnitude not independently
verified.** This is one old mouse study, not evidence that normal quercetin-containing
foods shorten human lifespan.
