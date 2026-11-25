# GENOVISTA original-source audit

The supplied `genovista.zip` was inspected, including the application entry point, all original Streamlit page modules, SQLite layer, Ensembl/NCBI/dbSNP/gnomAD clients, validators, formatters, README and dependency list. The original archive also contained a bundled Windows-style Python environment and bytecode caches; these were excluded from the rebuilt deliverable.

## Confirmed defects in the original source

1. **Conditional session-state setup:** `app.py` initialized every service and state key only when `db_initialized` was absent. A partially populated Streamlit session could therefore miss `current_gene`, `current_variant`, `dbsnp_client` or `gnomad_client` and crash on a later page.
2. **Page dispatch mismatch:** the original dynamic function-name construction transformed labels containing `&` into names that did not match actual functions (`show_about_data_sources` vs `show_about`, and `show_pathogenicity_evidence` vs `show_pathogenicity`).
3. **dbSNP endpoint construction:** the original base URL already ended in `/variation/v0`, then appended another `/v0`; it also called `/variant/{rsID}` rather than NCBI's RefSNP route `/refsnp/{numeric_id}`.
4. **Variant search did not render results:** the original search function fetched and cached records, then reran without preserving a complete result object for the UI. Empty API responses were often silent.
5. **Database gene insert mismatch:** the original gene INSERT declared 11 columns but only 10 SQL placeholders while the save method supplied 11 values.
6. **Incorrect list-query execution:** `get_all_saved_variants` and `get_all_saved_genes` used `executescript()` for SELECT statements, rather than `execute()`, so fetched rows were not reliably populated.
7. **Fragile timestamp formatting:** stored ISO timestamp strings were passed to a formatter that expected a datetime object.
8. **Incomplete Ensembl gene mapping:** the original gene lookup discarded chromosome and coordinate fields even though the Gene Explorer expected them.
9. **VEP response-shape mismatch:** the original parser expected a dictionary containing a `variants` property, while Ensembl VEP's identifier endpoint returns a list of consequence records.
10. **ClinVar identifier misuse:** the original code passed VCV/RCV accession strings directly to ESummary, which expects Entrez UIDs. It also did not consistently search ClinVar by rsID.
11. **gnomAD query and identifier issues:** the original GraphQL selection contained questionable field syntax and assumed an rsID could be queried directly. Population frequencies need a normalized allele representation and a verified dataset/schema query. The old UI also displayed decimal frequency as a percent without consistently multiplying by 100.
12. **Unnecessary page coupling:** multiple modules assumed shared session keys existed and directly accessed them. Several features repeated API calls and had overlapping, inconsistent data contracts.
13. **Archive hygiene:** the original ZIP contained thousands of bundled environment/cache files that do not belong in a portable source archive.

## Scope decisions in GENOVISTA 2.0

Retained and rebuilt:
- Overview
- Gene Explorer (Ensembl REST)
- Variant Search (NCBI dbSNP, ClinVar accession search, Ensembl gene lookup)
- Variant Analysis (dbSNP identification, Ensembl VEP, ClinVar-by-rsID search)
- Research Library (SQLite cache with raw source JSON, provenance and JSON/CSV export)
- About & Data Sources

Deferred/removed from this stable release:
- gnomAD population-frequency analysis, until allele normalization and current GraphQL schema are verified end-to-end
- Separate comparative-analysis, disease-association and pathogenicity pages; their overlapping functions are consolidated into Variant Analysis and ClinVar search
- PDF report generation; the current library exports source records in JSON and a variant index in CSV

## Verification performed

- All Python files compile with `compileall`.
- Unit tests cover identifier validation, gene and variant SQLite round trips, deletion, Ensembl VEP list response handling, and GRCh38-preferred RefSNP placement parsing.
- Seven tests pass in the build environment.
- **Live API tests are not claimed by this audit.** The user already independently confirmed live Ensembl BRCA1 lookup and live NCBI RefSNP rs7412 retrieval in their earlier Colab runtime. The rebuilt app should still be tested live in the new Colab runtime for VEP and ClinVar responses.
