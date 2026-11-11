# AgeSDK — Geroprotector Human Evidence Map

For compounds with animal lifespan evidence, what human trial data exists, under
what indications, and was it ever reported? See [SPEC.md](SPEC.md).

## Quick start

Python ≥ 3.10, one dependency (PyYAML). Standard library otherwise.

```sh
python -m agesdk init-db              # create schema, load reference data
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
| `agesdk/schema.sql` | Full SQLite schema; authoritative over SPEC §4 sketches |
| `agesdk/raw.py` | Append-only raw layer, rate-limited HTTP client, raw-layer cache |
| `agesdk/sources/` | One module per source (DrugAge, PubChem, ChEMBL so far) |
| `agesdk/fixture.py` | Seed fixture loading and checks |
| `data/fixtures/seed_compounds.yaml` | Hand-resolved seed compounds: resolver ground truth |
| `data/reference/species_taxon.csv` | Species → tier (mammal / invertebrate / …) |

## Data sources and attribution

- **DrugAge** (Human Ageing Genomic Resources), CC-BY 3.0. Barardo D. et al. (2017)
  The DrugAge database of ageing-related drugs. *Aging Cell* 16(3):594-597.
- **PubChem**, **ChEMBL**: public, see each source's terms.
