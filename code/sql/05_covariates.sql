-- 05_covariates.sql
-- Baseline covariates measured at or before time zero.
-- BigQuery does not support correlated subqueries that reference other tables,
-- so all covariates are built with joins/aggregations.

CREATE OR REPLACE TABLE `{{work}}.crrt_covariates` AS
WITH e AS (
  SELECT *
  FROM `{{work}}.crrt_outcomes`
),
weight AS (
  SELECT
    stay_id,
    AVG(valuenum) AS weight_kg
  FROM `{{icu}}.chartevents`
  WHERE itemid IN (226512, 224639)
    AND valuenum BETWEEN 20 AND 300
  GROUP BY stay_id
),
creat_ranked AS (
  SELECT
    e.stay_id,
    le.valuenum AS baseline_creat,
    ROW_NUMBER() OVER (PARTITION BY e.stay_id ORDER BY le.charttime DESC) AS rn
  FROM e
  JOIN `{{hosp}}.labevents` le
    ON le.subject_id = e.subject_id
   AND le.itemid = 50912
   AND le.charttime <= e.time_zero
),
creat AS (
  SELECT stay_id, baseline_creat FROM creat_ranked WHERE rn = 1
),
lactate_ranked AS (
  SELECT
    e.stay_id,
    le.valuenum AS lactate,
    ROW_NUMBER() OVER (PARTITION BY e.stay_id ORDER BY le.charttime DESC) AS rn
  FROM e
  JOIN `{{hosp}}.labevents` le
    ON le.subject_id = e.subject_id
   AND le.itemid = 50813
   AND le.charttime BETWEEN DATETIME_SUB(e.time_zero, INTERVAL 6 HOUR) AND e.time_zero
),
lactate AS (
  SELECT stay_id, lactate FROM lactate_ranked WHERE rn = 1
),
diuretic AS (
  SELECT e.stay_id, MAX(1) AS diuretic_24h
  FROM e
  JOIN `{{icu}}.inputevents` ie
    ON ie.stay_id = e.stay_id
   AND ie.itemid = 221794 -- Furosemide
   AND ie.starttime BETWEEN DATETIME_SUB(e.time_zero, INTERVAL 24 HOUR) AND e.time_zero
  GROUP BY e.stay_id
),
dx AS (
  SELECT
    hadm_id,
    MAX(IF(icd_code LIKE 'A41%' OR icd_code LIKE '038%' OR icd_code LIKE '99591%' OR icd_code LIKE '99592%', 1, 0)) AS sepsis,
    MAX(IF(icd_code LIKE 'I50%' OR icd_code LIKE '428%', 1, 0)) AS chf,
    MAX(IF(icd_code LIKE 'N18%' OR icd_code LIKE '585%', 1, 0)) AS ckd,
    MAX(IF(icd_code LIKE 'E11%' OR icd_code LIKE '250%', 1, 0)) AS diabetes,
    MAX(IF(icd_code LIKE 'J44%' OR icd_code LIKE '496%', 1, 0)) AS copd,
    MAX(IF(icd_code LIKE 'K70%' OR icd_code LIKE 'K74%' OR icd_code LIKE '571%', 1, 0)) AS liver,
    MAX(IF(icd_code LIKE 'C%' OR icd_code BETWEEN '140' AND '208', 1, 0)) AS cancer
  FROM `{{hosp}}.diagnoses_icd`
  GROUP BY hadm_id
),
mv AS (
  SELECT e.stay_id, MAX(1) AS mv
  FROM e
  JOIN `{{icu}}.procedureevents` pe
    ON pe.stay_id = e.stay_id
   AND pe.itemid = 225792 -- Invasive ventilation
   AND pe.starttime <= e.time_zero
   AND pe.endtime >= e.time_zero
  GROUP BY e.stay_id
)
SELECT
  e.stay_id,
  e.time_zero,
  e.stop_time,
  w.weight_kg,
  c.baseline_creat,
  l.lactate,
  e.norepi_rate,
  e.uo_6h,
  e.uo_24h,
  COALESCE(d.diuretic_24h, 0) AS diuretic_24h,
  COALESCE(dx.sepsis, 0) AS sepsis,
  COALESCE(dx.chf, 0) AS chf,
  COALESCE(dx.ckd, 0) AS ckd,
  COALESCE(dx.diabetes, 0) AS diabetes,
  COALESCE(dx.copd, 0) AS copd,
  COALESCE(dx.liver, 0) AS liver,
  COALESCE(dx.cancer, 0) AS cancer,
  COALESCE(m.mv, 0) AS mv
FROM e
LEFT JOIN weight w
  ON e.stay_id = w.stay_id
LEFT JOIN creat c
  ON e.stay_id = c.stay_id
LEFT JOIN lactate l
  ON e.stay_id = l.stay_id
LEFT JOIN diuretic d
  ON e.stay_id = d.stay_id
LEFT JOIN dx
  ON e.hadm_id = dx.hadm_id
LEFT JOIN mv m
  ON e.stay_id = m.stay_id
