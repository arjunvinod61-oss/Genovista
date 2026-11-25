# GENOVISTA 2.0

A smaller, evidence-first Streamlit application for exploring real human gene and variant records from Ensembl and NCBI.

## What is included

- **Overview** — saved-record counts and entry points.
- **Gene Explorer** — live human gene lookup through Ensembl REST, including Ensembl ID, chromosome, coordinates, strand, assembly, description, raw response and retrieval time.
- **Variant Search** — NCBI dbSNP RefSNP retrieval by rsID, ClinVar accession search through NCBI E-utilities, and gene lookup.
- **Variant Analysis** — dbSNP record, Ensembl VEP consequences, and ClinVar search by rsID.
- **Research Library** — SQLite cache with source provenance and JSON/CSV export.
- **About & Data Sources** — limitations and interpretation guidance.

## Deliberately deferred

The original gnomAD integration used a GraphQL query with questionable field names and attempted to look up an rsID without first resolving a normalized chromosome-position-reference-alternate allele. The original UI also formatted decimal allele frequency as a percentage incorrectly. Population-frequency analysis is therefore not exposed in this stable build. It should be reintroduced only after a current gnomAD dataset/schema query is verified end-to-end.

The original comparative-analysis, disease-association, standalone pathogenicity, and PDF-report pages were removed from the first stable build because their data contracts overlapped or depended on incomplete ClinVar handling. ClinVar evidence remains accessible from Variant Search and Variant Analysis. The saved research library exports JSON and CSV.

## Data integrity rules

- No random DNA sequences, synthetic variants, fake patients, or invented clinical classifications.
- API failure and no matching record are displayed separately.
- A missing ClinVar result is not interpreted as benign.
- Missing allele frequency is never interpreted as zero.
- Raw source responses, source names, and retrieval timestamps are retained in SQLite.
- Coordinates and assembly are displayed only when returned by the source.

## Local installation

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit (normally http://localhost:8501).

## Google Colab

Open `GENOVISTA_Colab.ipynb` in Google Colab, run its cells in order, upload this ZIP when prompted, and use the generated temporary Cloudflare URL. The public URL only works while the Colab runtime and tunnel are running.

## Optional NCBI API key

Set `NCBI_API_KEY` in the environment to use an NCBI API key. `NCBI_EMAIL` can also be set to a real contact email. No API key is required for the basic demonstration rate.

## Tests

```bash
pytest -q
```

## Disclaimer

For research and education only. ClinVar assertions are submitted interpretations, not personal medical diagnoses. Do not use this application for clinical decision-making.
