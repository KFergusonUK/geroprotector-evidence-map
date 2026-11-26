# Direction conflicts: brief for Kevin

Prepared 2026-11-26 from the four conflicts listed in `docs/agent_discussion.md`.
These are animal lifespan studies. The path consequence below follows the current
`derive_direction()` rule: an assessed measure with an opposite point estimate to a
significant measure creates a conflict, which counts toward neither path until reviewed.
This is a data review, not a decision entered in `data/reviews/direction_reviews.yaml`.

## Beta-aminopropionitrile fumarate (BAPN), male mice — PMID 689120

DrugAge has two rows in this task: average lifespan +6% (significant) and +5%
(significant), with maximum lifespan −1% (not significant), both at 1,000 ppm in water
from 2 months. The two rows cite the same paper, so they are not independent replications.
The PubMed record identifies LaBella & Vivian's 1978 mouse paper but has no abstract or
results table; the publisher's full text was not available for this check. I cannot quote
or independently verify the paper's exact mean/maximum values, dose regimen, or statistical
tests. The paper title is “Beta-aminopropiontrile promotes longevity in mice.”

**Reading and path effect.** If the DrugAge values and significance flags are accepted,
the positive significant average and negative maximum point estimate meet the project's
conflict definition despite the maximum being NS: each row goes to neither extension nor
harm pending review. Treating the −1% NS maximum as ordinary sampling noise would place
the rows on the extension path, but that would waive the rule without primary-source
verification. The negative value does not support a harm path. Do not count the duplicated
rows as separate experiments.

**Recommendation:** Keep both rows in neither path pending the full paper; then ask whether
the two positive rows are separate dose groups and whether the maximum estimate is truly
opposite in the source.

## Levodopa, male mice, 1,000 ppm — PMID 850799

The conflict row says average +7% (NS), maximum −14% (significant), at 1,000 ppm in food
from 1 month. The [PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/850799/) says that
“high concentrations” of dietary levodopa prolonged mean lifespan by a maximum of 50%.
That supports the paper's general report of lifespan extension at high concentrations,
but the abstract does not give the 1,000-ppm result, maximum-lifespan estimate, or its
significance. The full Science article was not accessible for this check, so I cannot
verify those exact DrugAge entries or quote its dose table. The same-paper higher-dose
rows supplied in the task (+15% at 20,000 ppm and +28% at 40,000 ppm, both significant)
are consistent with a dose-specific effect and should not be used to overwrite the
1,000-ppm row.

**Reading and path effect.** Accepting the 1,000-ppm row as transcribed makes it a conflict:
neither extension nor harm pending review. If the significant −14% maximum is confirmed,
the project's rule keeps it out of both paths until a person decides how to weigh it. If
the maximum's direction or significance is wrong, the remaining +7% NS average is null,
also neither path. It is not an extension candidate at this dose on the current numbers.

**Recommendation:** Leave the 1,000-ppm row in neither path until the full source table is
checked; do not extrapolate the high-dose mean benefit down to this dose.

## Epitalon, female mice — PMID 14501183

The full [primary paper PDF](https://www.demogr.mpg.de/publications/files/1513_1189524145_1_BG-Anis-Epitalon-SHR.pdf)
is available. Table 6 gives mean lifespan as 456 days for saline and 455 days for
Epitalon, with no significance mark; the medians are 512 and 487 days (about −5%). The
paper says mean lifespan “did not change.” This explains DrugAge's −5% NS if its `avg`
field is actually the **median**; it would be a metric-label mismatch if `avg` means
arithmetic mean. For the long-lived end, Table 6 reports the mean lifespan of the last
10% as 709 versus 803 days (+13.3%), marked significant at *P* < 0.01. The maximum
lifespans are 739 versus 830 days (+12.3%), but **the maximum row has no significance
mark**. The paper's significant result is for the last 10% statistic, not for the maximum
statistic.

**Reading and path effect.** DrugAge's numeric +13% maximum direction is right, but its
`S` label is not supported by Table 6 as presented; it may have carried over the
significance of the distinct last-10%-of-survivors measure. The mean-lifespan comparison
is effectively null, and the median's −5% is not marked significant. If the maximum is
changed from significant to unassessed, the row becomes null (neither path); if someone
instead treats the significant last-10% result as an extension measure, that would add an
extension signal, but it would be a different endpoint from maximum lifespan. Neither
reading supports a harm path.

**Recommendation:** Propose reviewing the max `S` flag and the `avg`/median label. Keep
this row in neither path unless Kevin explicitly decides to count the significant
last-10% endpoint as extension evidence.
