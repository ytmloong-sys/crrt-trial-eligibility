-- 06_analysis_dataset.sql
-- One row per eligible patient. This is the table exported to Parquet for Python analysis.

CREATE OR REPLACE TABLE `{{work}}.analysis_dataset` AS
SELECT
  e.stay_id,
  e.subject_id,
  e.hadm_id,
  e.start_time,
  e.end_time,
  e.time_zero,
  e.stop_time,
  e.age,
  e.gender,
  e.race,
  e.admission_type,
  e.first_careunit,
  e.duration_hours AS crrt_duration_hours,
  e.weight_kg,
  e.baseline_rate,
  e.last_rate,
  e.taper_start,
  e.exposure,
  e.rrt_restart_time,
  e.rrt_restart_7d,
  e.death_7d,
  e.event_7d,
  e.time_7d,
  1 - e.event_7d AS dialysis_free_7d,
  e.death_90d,
  e.norepi_rate,
  e.uo_6h,
  e.uo_24h,
  c.baseline_creat,
  c.lactate,
  c.diuretic_24h,
  c.sepsis,
  c.chf,
  c.ckd,
  c.diabetes,
  c.copd,
  c.liver,
  c.cancer,
  c.mv
FROM `{{work}}.crrt_outcomes` e
LEFT JOIN `{{work}}.crrt_covariates` c
  ON e.stay_id = c.stay_id
 AND e.time_zero = c.time_zero
 AND e.stop_time = c.stop_time
