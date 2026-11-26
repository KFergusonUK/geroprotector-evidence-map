# Estriol census, amendment 1: the blind checker is Codex (GPT-6), not Kevin Ferguson

Amends `docs/estriol_census_protocol.md`, step 5. Decided by Kevin Ferguson on 2026-11-26,
before any blind verdict existed: `docs/estriol_blind_check.yaml` had no verdicts. Kevin
was offered two options: doing the check himself (recommended), or delegating it to Codex.
He chose to delegate ("1b"). This is a deviation from the protocol and is reported as one.
The amendment is committed before Codex is asked to do the check.

## Why

Kevin Ferguson delegated technical checks that need pharmacology or chemistry knowledge to
a second AI. In his words: "I don't have the required knowledge in this area to be of much
decision assistance, unless it's structural".

The blind check exists because the adjudicator, Claude, also wrote the resolver and the
estriol fixture entry. An independent checker that did not write them still serves that
purpose. Identity has a checkable ground truth (§4 of the measurement policy): does this
intervention administer estriol itself?

## The change

| | Before | After |
|---|---|---|
| Blind checker | Kevin Ferguson | **Codex (GPT-6)**, the coding agent in Kevin's VS Code |
| Packet | `docs/estriol_blind_check.yaml`, all 18 rows, shuffled, no verdicts | unchanged |
| Outcome rules | protocol step 5 | unchanged |

**Conditions:**
- **Codex does not open `data/reviews/estriol_census.yaml`,** which holds Claude's
  verdicts, before its own verdicts are committed (`AGENTS.md`, hard rule 1). This rests on
  Codex following the rule: it has repository access, so a technical barrier is not
  possible. The result says so.
- **Codex judges from the packet and the registry links in it.** It may open the
  ClinicalTrials.gov pages and PubChem. It does not use the resolver's output.
- **Verdicts are written into `docs/estriol_blind_check.yaml`,** in the `verdict` and
  `note` fields, and committed before `python3 docs/estriol_blind.py compare` is run.

## What this weakens, stated now

**Independence between two AI systems is weaker than independence between an AI and a
person.** Shared conventions from training can make them agree for the same wrong reason.
The result reports the checker as "Codex (GPT-6)", never as an independent human check.

Codex is a different model family from the adjudicator (Claude), which helps. If Codex is
the same assistant that acted as Reader C ("Echo") in role-1, that does not matter here.
The task here is different (identity, not role), and the rows are different.
