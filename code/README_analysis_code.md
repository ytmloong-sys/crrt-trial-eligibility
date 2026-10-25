# Analysis code for the CRRT trial-eligibility study

This package contains the SQL and Python code used to derive the MIMIC-IV cohort,
build the external cohorts, apply trial eligibility criteria, and generate the
criterion-attribution and pooled estimates.

## Data sources

- MIMIC-IV v3.1 (PhysioNet; credentialed access)
- eICU-CRD v2.0 (PhysioNet; credentialed access)
- SICdb v1.0.8 (PhysioNet; credentialed access)
- AmsterdamUMCdb v1.0.2 (PhysioNet; credentialed access)

Archived release concept DOI: 10.5281/zenodo.23634332 (v1.0.0 version DOI: 10.5281/zenodo.23634333).

No patient-level data are included. All databases remain under their respective
data use agreements.

## Order of analysis

1. MIMIC-IV: run SQL files 00-11 in a BigQuery project, then `02_build_dataset.py`
   and `03_primary_analysis.py`.
2. eICU: `eicu_build_cohort.py`, `eicu_add_flags.py`, `eicu_compare_mimic.py`,
   `eicu_audit_30.py`.
3. SICdb: `sicdb_build_cases_labs.py`, `sicdb_extract_signals.py`,
   `sicdb_build_cohort.py`.
4. AmsterdamUMCdb: `amsterdam_build_base.py`, `amsterdam_extract_numeric.py`,
   `amsterdam_build_cohort.py`.
5. ICU-admission landmark: run `sql/12_trial_variables_icu.sql` and `sql/13_eicu_icu_landmark.sql`, then the `landmark_flags_*` scripts and `landmark_table_figure.py`.
6. Synthesis: `criterion_attribution.py`, `all_five_meta.py`,
   `make_forest_all_five.py`, `make_amsterdam_figure.py`.

## Software

Python 3.12; pandas, NumPy, DuckDB, PyArrow, matplotlib, python-docx,
google-cloud-bigquery.

## Notes

File paths in the scripts reflect the original analysis environment and must be
adapted to the local data locations. The scripts are provided for transparency and
reproducibility, not as a turnkey pipeline.
