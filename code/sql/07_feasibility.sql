-- 07_feasibility.sql
-- Go/No-Go query. Run after 01-06.

WITH base AS (
  SELECT *
  FROM `{{work}}.analysis_dataset`
),
clean AS (
  SELECT *
  FROM base
  WHERE exposure IN ('gradual', 'abrupt')
)
SELECT
  (SELECT COUNT(*) FROM `{{work}}.crrt_episodes`) AS n_crrt_episodes,
  (SELECT COUNT(*) FROM `{{work}}.crrt_eligibility`) AS n_eligible,
  (SELECT COUNT(*) FROM clean) AS n_clean,
  (SELECT COUNTIF(exposure = 'gradual') FROM clean) AS n_gradual,
  (SELECT COUNTIF(exposure = 'abrupt') FROM clean) AS n_abrupt,
  (SELECT COUNTIF(exposure = 'ambiguous') FROM base) AS n_ambiguous,
  (SELECT COUNTIF(exposure = 'insufficient') FROM base) AS n_insufficient,
  ROUND(100 * SAFE_DIVIDE((SELECT COUNTIF(exposure = 'gradual') FROM clean), (SELECT COUNT(*) FROM clean)), 1) AS pct_gradual,
  ROUND(100 * AVG(dialysis_free_7d), 1) AS pct_dialysis_free_7d,
  ROUND(100 * AVG(CASE WHEN exposure = 'gradual' THEN dialysis_free_7d END), 1) AS pct_dialysis_free_7d_gradual,
  ROUND(100 * AVG(CASE WHEN exposure = 'abrupt' THEN dialysis_free_7d END), 1) AS pct_dialysis_free_7d_abrupt,
  ROUND(100 * AVG(death_90d), 1) AS pct_death_90d,
  ROUND(AVG(crrt_duration_hours), 1) AS mean_crrt_hours,
  ROUND(AVG(age), 1) AS mean_age,
  ROUND(100 * AVG(sepsis), 1) AS pct_sepsis
FROM clean
