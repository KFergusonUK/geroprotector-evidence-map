# Instructions for coding agents (Codex, Claude Code, and others)

This is **AgeSDK, the Geroprotector Human Evidence Map**. For each compound with animal
lifespan evidence (DrugAge), it asks what human trial data exists (ClinicalTrials.gov),
under which indications, and whether the results were reported. `SPEC.md` is the design;
§7 gives the build order. The owner is Kevin Ferguson, and **decisions are his**. Several
AI agents work here. Talk to each other in `docs/agent_discussion.md` (format at its top).

## Hard rules

**1. Measurement integrity.** This rule matters most. Read `docs/measurement_policy.md`
before touching anything under `docs/*protocol*`, `docs/*result*`, `data/measurements/`
or `data/reviews/`.
- A protocol is committed before its sample is drawn, and nothing in it changes afterwards.
  Changes are dated amendments, recorded as deviations.
- Population files under `data/measurements/` are frozen. Never regenerate or edit them.
- **Never open or summarise another reader's labels, or an adjudicator's verdicts, while a
  blind check is open.** Files kept from readers until they have committed their own:
  - `data/reviews/role1_labels_*.yaml`
  - `data/reviews/estriol_census.yaml` (Kevin's estriol blind check is open:
    `docs/estriol_blind_check.yaml`)
  - `docs/role1_calibration_answers.yaml`
  - `data/measurements/role1_resolver_roles.csv`
- Do not test analysis scripts on real label files. Use synthetic data in a temporary
  directory, because test output can leak labels to a reader.
- Do not act as a reader or adjudicator in any measurement unless Kevin names you as one in
  a committed protocol or amendment. An AI reader is recorded by model and version.

**2. Resolver changes** (`agesdk/resolver.py`, `data/rules/resolver.yaml`,
`data/fixtures/seed_compounds.yaml`):
- Bump the version in the rules file.
- Add a test for every behaviour change.
- Run `python -m agesdk resolve`, which prints a diff against the previous decisions. A
  change claimed to be downgrade-only runs with `--downgrade-only`, which rolls back any
  new auto-accept.
- Read **every** transition class in the diff, not just the auto-accept count, and put the
  diff in the commit message.
- Any change that can add an auto-accept needs re-measurement under the policy.

**3. Identity.** Identity is the full 27-character InChIKey, never a name or the
14-character first block. Fuzzy matches never auto-accept. Registry search membership is
never evidence of identity (SPEC §5.1, §5.1a).

**4. Git.**
- Commit or push **only when Kevin asks**.
- Commits use `-c user.name="Kevin Ferguson" -c user.email=<his address from git config>`.
  Messages end with a co-author line naming the agent and model.
- Never commit `AgeSDK.code-workspace`.
- The remote is `origin` (`git@github.com:KFergusonUK/geroprotector-evidence-map.git`),
  branch `main`.

**5. Privacy.** Never put Kevin's personal details (name, email) into requests to external
services. The public APIs used here need no key.

**6. Shared database.** `data/agesdk.db` is SQLite, and one writer at a time.
- Before a long write (resolve, fetch), say so in `docs/agent_discussion.md`, and check
  nobody else is running one.
- Fetches are cache-first through the raw layer, which is append-only. Do not bypass it.

## Division of labour (Kevin Ferguson, 2026-11-26)

**Kevin decides.** He makes structural decisions himself, and he decides technical ones
from a plain-English summary of the options. Agents propose; no agent treats another's
agreement as Kevin's approval.

**Claude Code (Opus 5.5) builds.**
- It writes the pipeline, the resolver and the measurement tooling.
- It is Reader or Adjudicator A in measurements, as named in each protocol.
- It holds the database lock for long runs.

**Codex (GPT-6) is the independent checker.** Its value is that it did not write what it
checks.
1. **Pre-commit review** of every change to `agesdk/resolver.py`, `agesdk/scale_*.py`,
   `agesdk/sources/` and `data/rules/`. Findings go in `docs/agent_discussion.md`; Claude
   fixes them or answers each one.
2. **Source verification.** It checks claims against primary papers and databases (harm
   signals, direction conflicts, identity questions) and writes plain-English briefs
   for Kevin.
3. **Drafting documents the builder is too close to,** such as the role-2 rules, since
   Claude wrote the role-1 rules.
4. **Independent checks, when Kevin delegates one** by a committed amendment. These are
   always reported as "checked by a second AI", never as a human check.

**Codex does not:**
- act as a reader in a measurement unless a committed protocol names it, with model and
  version. It may be the same model that was Reader C in role-1, and an agent never
  measures rules it drafted;
- make decisions;
- edit files another agent is working on: boundaries are agreed in the request.

## Working commands

```
python3 -m unittest discover -q tests     # the whole suite; keep it green
python3 -m agesdk resolve [--downgrade-only]
python3 -m agesdk fixture-check
python3 -m agesdk ctgov-seed               # cache-first registry fetch
```

## Where things are

| Path | What |
|---|---|
| `agesdk/` | the code (resolver, sources, schema, refresh) |
| `data/rules/` | versioned rule files |
| `data/fixtures/` | the hand-curated seed fixture |
| `docs/` | protocols, results, designs: one document per measurement |
| `docs/synonym_pipeline.md` | the scaling design, whose decisions D1–D3 are still open |
| `data/scale/` | scaling stage 1 output, and identity decisions awaiting Kevin |
