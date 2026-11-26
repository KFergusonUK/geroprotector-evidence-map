# Estriol — census of auto-accepts after adding it to the seed fixture: protocol

**Fixed before estriol's registry records are fetched.** It is committed ahead of the
fetch. Nothing below changes after this commit. Follows `docs/measurement_policy.md`.

## Why

Estriol was added as a seed compound on 2026-11-18 (fixture 0.9.0;
`docs/harm_signal_checks.md`). Adding a compound **adds auto-accepts**, so under the
policy (§3) it triggers measurement. The step-4b figure (99.5%) covered the earlier seed
compounds only. Estriol is also excluded from step 7, whose population is non-seed
compounds. Its rows are covered by neither measurement. This protocol covers them.

A census, not a sample. Estriol's trial volume is expected to be small, and a census
leaves no sampling error.

## Procedure

1. **Fetch.** Run the seed fetch, which now includes estriol's query strings (canonical
   name plus `must_match`), then `python -m agesdk resolve`.
2. **Check that the change is contained.** The resolve diff's new auto-accepts must **all
   be estriol rows**. Any new auto-accept for another compound means the fixture change
   leaked. In that case stop: it is a resolver defect, and it is fixed and diffed before
   anything else. The diff counts are recorded in the result.
3. **Freeze.** Write every estriol `auto_accept` row to
   `data/measurements/estriol_population.csv`, ordered by (`nct_id`, `idx`). Hash it and
   commit it before any row is viewed.
4. **Adjudicate.**
   - **If N ≤ 200,** every row is adjudicated: this is the census.
   - **If N > 200,** a simple random sample of 200 is adjudicated instead, drawn with
     `random.Random(20261124)`, and the step-4 bar applies.

   The identity rule is that of `docs/step4_precision_protocol.md`, with ambiguous counted
   as incorrect. Each verdict is recorded in `data/reviews/estriol_census.yaml` with the
   following, as in step 4:
   - systemic-exposure correctness;
   - role.

   The following count as **incorrect**:
   - a stereoisomer, including 16-epiestriol;
   - estradiol;
   - estrone;
   - an ester prodrug presented as estriol;
   - a combination product presented as estriol.
5. **Blind check.** Kevin Ferguson judges a packet without seeing Claude's verdicts.
   - If N ≤ 30: every row.
   - Otherwise: 30 rows drawn at random (`random.Random(20261125)`), plus every row Claude
     judged incorrect, up to 15.

   Rows are shuffled, and the packet does not say how many rows are of either kind. The
   outcome rules are those of step 7.

## Bar (decided now)

**Census (N ≤ 200).** The figure is exact for this population; it is reported as k / N
with a Wilson interval, for comparability.
- **0 errors:** estriol's auto-accepts are used.
- **Any error:** the error class is fixed (fixture case plus test). Every auto-accept
  affected by the fix is then re-checked, and the census is repeated on the changed rows.
  Estriol's rows are not used until a census shows 0 errors.

The bar is stricter than the step-4 bar on purpose. Estriol enters the outputs as a
**harm-path** candidate prescribed to women. One false join could mean claiming that
women are exposed to a drug they never took in that trial.

**Sample (N > 200).** The step-4 bar applies: 0–3 errors GO, 4–5 CONDITIONAL, 6 or more
NO-GO.

## Reported with the result

- **N** and the resolve diff counts.
- **Route:** how many auto-accepts are local (vaginal) and how many systemic. Expected:
  mostly local.
- **Role** suggestions. These are subject to the role-1 measurement, not this one.
- **The open identity point:** the ITP compound's CAS number has not been checked.
