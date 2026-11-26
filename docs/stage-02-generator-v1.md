# Stage 2: Generator v1

**Date:** 2026-11-26 · **Status:** Done (waiting for review)

## What we did

We built a Python script that makes **fake** healthcare billing data: insurance companies (payers), clinics (providers), patients, and claims with their line items. Give it a seed number and it always makes exactly the same data. There are no insurance replies (remits) or denials yet. Those come in Step 3.

## What we built

All code lives in `src/rcm/generator/`.

| File | What it does |
|---|---|
| `config.py` | `GeneratorConfig`: seed, number of claims (default 100,000), months (default 18), start date, number of providers and patients. Rejects zero or negative sizes. |
| `reference.py` | Fixed lookup lists: 10 made-up payers, 6 specialties, 16 CPT codes with list prices, 18 ICD-10 codes, and 3 places of service. |
| `entities.py` | Makes payers, providers and patients. |
| `claims.py` | Makes claim headers and claim lines. |
| `schema.py` | The agreed columns and types for every table. The tests check against it. |
| `build.py` | `generate(config)`: one call returns all five tables. |

### The five tables

| Table | One row is | Key columns |
|---|---|---|
| `payers` | an insurance company | `payer_id`, `payer_type` (commercial, medicare, medicare_advantage, medicaid, self_pay), `timely_filing_days` |
| `providers` | a clinic | `provider_id`, `specialty`, `state` |
| `patients` | a fake patient | `patient_id`, `birth_year`, `sex`, `state`, `payer_id` |
| `claims` | a bill sent to a payer | dates, place of service, main diagnosis, prior-auth flags, `line_count`, `total_charge` |
| `claim_lines` | one service on a bill | `cpt_code`, `icd10_code`, `units`, `line_charge` |

### How it makes the data look realistic

- **Busy and quiet:** some patients and clinics have many more claims than others.
- **Specialty fits the codes:** an eye clinic bills cataract surgery, not knee MRIs.
- **Age fits the insurance:** most patients 65 and over have Medicare.
- **Prior authorization:** expensive services (MRI, stress test, colonoscopy, cataract surgery) need prior auth. About 12% of those claims are missing it. Step 3 will turn that into denials.
- **Late claims:** most claims are sent within a week of the visit, but about 5% are sent 30 to 120 days late. Step 3 will use that for timely-filing denials.
- **Place of service:** surgeries happen at a surgery center or hospital, and most visits happen in an office.

### How we keep it obviously fake

- Every ID has a `SYN-` prefix: `SYN-PAY-0001`, `SYN-PRV-00001`, `SYN-MRN-000001`, `SYN-CLM-0000001`, `SYN-CLM-0000001-L01`.
- Payer and clinic names start with "Synthetic".
- Patients have **no names, no full birth date, and no SSN**, only birth year, sex and state.
- CPT and ICD-10 codes are public billing codes, not patient data. Prices are made up.

## Tests (written first)

We wrote the tests first and ran them. They failed with `No module named 'rcm.generator'`. Then we wrote the code until they passed.

| Test file | What it checks |
|---|---|
| `tests/unit/test_generator_determinism.py` | Same seed gives identical tables. A different seed gives different claims. |
| `tests/unit/test_generator_schema.py` | Correct tables, columns in order, column types, no empty values, unique keys, allowed values only. |
| `tests/unit/test_generator_synthetic.py` | Every ID matches its `SYN-` pattern. No value anywhere looks like an SSN (9 digits, with or without dashes) or a bare MRN (6+ digits alone). Patients have no name or birth-date columns. |
| `tests/unit/test_generator_claims.py` | Claim total = sum of lines. Line numbers run 1, 2, 3 and so on. Dates stay inside the window. Submission is never before service. Prior-auth flags follow the CPT rules. A claim's payer is the patient's payer. CPT codes fit the clinic specialty. Bad config values are rejected. |
| `tests/integration/test_generator_end_to_end.py` | A 20,000-claim, 18-month run: every ID link (foreign key) works. Patients have repeat visits. Every month has claims. Charges have a realistic spread. |

## How to run it

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

To try it in Python:

```python
from rcm.generator import GeneratorConfig, generate

tables = generate(GeneratorConfig(seed=42))   # 100,000 claims, 18 months
tables["claims"].head()
```

There is no command-line tool and no Parquet output yet. Both arrive in Step 3.

## Results

- `ruff check .` and `ruff format --check .`: passed
- `pytest -q`: **56 passed** (51 unit, 5 integration)
- Coverage on `src/`: **99%**
- A full 100,000-claim run takes about **0.5 seconds** and makes about 188,000 claim lines and 25,000 patients. The median claim is about $222.

## New dependencies

`numpy` and `pandas` were added to `pyproject.toml`.

## What is next

**Step 3: Generator v2.** Add insurance replies (remits) with CARC/RARC denial codes. Plant denial patterns (missing prior auth, late filing, and others) plus random noise. Add a command-line tool that writes about 100,000 claims to `data/raw/*.parquet`.
