# Estriol census: result

**Protocol:** `docs/estriol_census_protocol.md` (`65a5449`), as amended by
`docs/estriol_census_amendment_1.md` (`d17079e`).
**Population:** `data/measurements/estriol_population.csv` (`8a3f776`), N = 18.
**Verdicts:** Claude, `data/reviews/estriol_census.yaml` (`46e4f39`).
**Blind check:** Codex (GPT-6), `docs/estriol_blind_check.yaml` (`ce495a9`).

## Result

**Identity: 18 of 18 auto-accepts are estriol itself.** Wilson 95% interval 82.4–100%.
There are 0 errors, so the census bar is **met**, and estriol's auto-accepts are used.

**Blind check: 18/18 agree, 0 disagree, so the number stands.** The checker was Codex
(GPT-6), an AI. Kevin Ferguson delegated the check to it (choice "1b"). This is weaker
than a human check. Two AIs can agree for the same wrong reason, although these two are
from different model families. Codex reports that it did not open Claude's verdicts before
committing its own. That rests on it following `AGENTS.md`.

**Route: 16 of 18 were correct under resolver-v5.**
- The two errors were an estriol nasal spray and an application in "the proximal third of
  the vagina". Both defaulted to systemic.
- Both are fixed in resolver-v6 (`a04b911`): "nostril" is unclear and "vagina" is local.

**Containment (protocol step 2):** all 18 new auto-accepts were estriol, all on newly
fetched studies. No row that already existed changed.

## What it means for the harm path

Only **2 of the 18 trials give estriol systemically**. Both are oral estriol 8 mg in
multiple sclerosis (NCT00451204, NCT01466114). Everything else is vaginal, which is local
under §5.6.

The ITP signal for estriol is a significant **female** shortening (−6.5%, p = 0.002;
`docs/harm_signal_checks.md`). So the systemic human evidence for women comes down to those
two MS trials.

**Still open:** the ITP compound's identity rests on the 2025 correction, not on a CAS
number. The paper's Supplementary Information has not been read.
