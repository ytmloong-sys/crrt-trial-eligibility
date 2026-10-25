-- 10_landmark72_dataset.sql
-- One row per patient in the 72-h landmark cohort.

CREATE OR REPLACE TABLE `{{work}}.landmark72_analysis` AS
SELECT
  e.stay_id,
  e.subject_id,
  e.hadm_id,
  e.start_time,
  e.end_time,
  e.time_zero,
  e.age,
  e.gender,
  e.race,
  e.admission_type,
  e.first_careunit,
  e.duration_hours,
  e.hours_to_stop,
  e.early_stop,
  e.delayed_stop,
  e.rrt_restart_time,
  e.rrt_restart_28d,
  e.death_28d,
  e.death_90d,
  e.dialysis_free_28d,
  e.weight_kg,
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
FROM `{{work}}.crrt_landmark72` e
LEFT JOIN `{{work}}.crrt_landmark72_covariates` c
  ON e.stay_id = c.stay_id
 AND e.time_zero = c.time_zero
