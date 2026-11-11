# AgeSDK — Geroprotector Human Evidence Map

For compounds with measured effects on animal lifespan, what human trial data
exists, under what indications, and was it ever reported? See [SPEC.md](SPEC.md).

## Two co-equal deliverables

Lifespan effects run both ways. The map has two entry paths with separate outputs
of equal standing, and **their counts are never merged** in any view or figure.
A compound on both paths appears in both, counted separately.

### Extension path — what extends animal lifespan, and what human data exists?

- **Enters on:** ≥1 animal result with significant lifespan extension.
- **Threshold:** conservative; replication matters (≥2 independent lab groups, or the
  ITP threshold). ITP evidence is shown as a ratio by sex, e.g. aspirin 1/6
  (male 1/3, female 0/3), rapamycin 14/16.
- **Outputs:** the **gold cell** (replicated extension + human trials), the **null cell**
  (well-powered ITP null + human trials), and **untested candidates**.
- **Class entry:** compounds sharing a specific ATC level-4 class with a direct
  compound enter too, always labelled `entry_route = 'class'` and reported separately.

### Harm path — what shortens mammalian lifespan while in wide human use?

- **Enters on:** ≥1 mammalian result with significant lifespan shortening.
- **Threshold:** sensitive; a single credible mammalian signal surfaces a candidate.
- **Review:** mandatory and human. Nothing reaches `v_harm_signal` without a named
  reviewer, a rationale and a stated human-exposure basis; the schema enforces it.
- **Output:** the **harm signal**: a pointer to evidence that deserves attention,
  not a verdict that a drug is unsafe in humans.

## Quick start

Python ≥ 3.10, one dependency (PyYAML). Standard library otherwise.

```sh
python -m agesdk init-db              # create/upgrade schema, load reference data
python -m agesdk fetch-drugage        # DrugAge → raw layer (no-op if already present)
python -m agesdk fixture-check --pubchem   # validate the seed fixture
python -m agesdk fixture-chembl       # ChEMBL IDs + ATC codes for the fixture, for hand entry
python -m unittest discover -s tests -t .
```

The database lives at `data/agesdk.sqlite` (override with `AGESDK_DB`). It is not
committed; everything in it is rebuilt from the sources and the reviewed data in `data/`.

## Layout

| Path | What |
| ---- | ---- |
| `agesdk/schema.sql` | Full SQLite schema and derived views; authoritative over SPEC §4 sketches |
| `agesdk/evidence.py` | Direction of effect (extension / shortening / null / unassessed) |
| `agesdk/raw.py` | Append-only raw layer, rate-limited HTTP client, raw-layer cache |
| `agesdk/sources/` | One module per source (DrugAge, PubChem, ChEMBL so far) |
| `agesdk/fixture.py` | Seed fixture loading and checks |
| `data/fixtures/seed_compounds.yaml` | Hand-resolved seed compounds: resolver ground truth |
| `data/reference/species_taxon.csv` | Species → tier (mammal / invertebrate / …) |

## Data sources and attribution

- **DrugAge** (Human Ageing Genomic Resources), CC-BY 3.0. Barardo D. et al. (2017)
  The DrugAge database of ageing-related drugs. *Aging Cell* 16(3):594-597.
- **PubChem**, **ChEMBL**: public, see each source's terms.
