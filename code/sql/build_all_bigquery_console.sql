-- build_all_bigquery_console.sql
-- Purpose: run the whole cohort build in the BigQuery web console, then export the final table to CSV.
-- Instructions:
--   1. Replace YOUR_PROJECT with your GCP project ID (e.g. my-project-123).
--   2. Create dataset mimic_work in the same location as the MIMIC datasets (usually US).
--   3. Paste this whole script into the BigQuery editor and Run.
--   4. Export the final SELECT result to local CSV (about 1,500 rows).

CREATE SCHEMA IF NOT EXISTS `YOUR_PROJECT.mimic_work`;

-- ===== 01_crrt_episodes.sql =====
-- 01_crrt_episodes.sql
-- Build CRRT episodes from ICU chartevents.
-- A CRRT episode is a run of CRRT settings with gaps <= max_gap_hours.
-- Only the first episode per ICU stay is retained.

CREATE OR REPLACE TABLE `YOUR_PROJECT.mimic_work.crrt_episodes` AS
WITH settings AS (
  SELECT
    ce.stay_id,
    ce.charttime,
    ce.itemid,
    ce.valuenum,
    ce.value
  FROM `physionet-data.mimiciv_3_1_icu.chartevents` ce
  WHERE ce.itemid IN (
    224144, -- Blood Flow (ml/min)
    224149, -- Access Pressure
    224150, -- Filter Pressure
    224151, -- Effluent Pressure
    224152, -- Return Pressure
    224153, -- Replacement Rate
    224154, -- Dialysate Rate
    224191, -- Hourly Patient Fluid Removal
    225183, -- Current Goal
    225956, -- Reason for CRRT Filter Change
    225976, -- Replacement Fluid
    225977, -- Dialysate Fluid
    228004, -- Citrate (ACD-A)
    228005, -- PBP (Prefilter) Replacement Rate
    228006, -- Post Filter Replacement Rate
    226457, -- Ultrafiltrate Output
    224146  -- System Integrity
  )
  AND ce.charttime IS NOT NULL
  AND (ce.valuenum IS NOT NULL OR ce.value IS NOT NULL)
),
active AS (
  SELECT DISTINCT stay_id, charttime
  FROM settings
),
gaps AS (
  SELECT
    stay_id,
    charttime,
    LAG(charttime) OVER (PARTITION BY stay_id ORDER BY charttime) AS prev_time
  FROM active
),
starts AS (
  SELECT
    stay_id,
    charttime,
    CASE
      WHEN prev_time IS NULL THEN 1
      WHEN DATETIME_DIFF(charttime, prev_time, HOUR) > 4 THEN 1
      ELSE 0
    END AS new_episode
  FROM gaps
),
episode_ids AS (
  SELECT
    stay_id,
    charttime,
    SUM(new_episode) OVER (PARTITION BY stay_id ORDER BY charttime) AS episode_id
  FROM starts
),
episodes AS (
  SELECT
    stay_id,
    episode_id,
    MIN(charttime) AS start_time,
    MAX(charttime) AS end_time,
    DATETIME_DIFF(MAX(charttime), MIN(charttime), MINUTE) / 60.0 AS duration_hours
  FROM episode_ids
  GROUP BY stay_id, episode_id
),
ranked AS (
  SELECT
    e.*,
    ROW_NUMBER() OVER (PARTITION BY e.stay_id ORDER BY e.start_time) AS episode_rank
  FROM episodes e
)
SELECT
  r.stay_id,
  ie.subject_id,
  ie.hadm_id,
  r.episode_id,
  r.episode_rank,
  r.start_time,
  r.end_time,
  r.duration_hours,
  ie.intime,
  ie.outtime,
  ie.first_careunit,
  ie.last_careunit,
  a.admittime,
  a.dischtime,
  a.deathtime,
  a.admission_type,
  a.race,
  p.gender,
  p.anchor_age,
  p.anchor_year,
  p.dod,
  LEAST(90, p.anchor_age + EXTRACT(YEAR FROM a.admittime) - p.anchor_year) AS age,
  COALESCE(a.deathtime, DATETIME(p.dod)) AS death_time
FROM ranked r
JOIN `physionet-data.mimiciv_3_1_icu.icustays` ie
  ON r.stay_id = ie.stay_id
JOIN `physionet-data.mimiciv_3_1_hosp.admissions` a
  ON ie.hadm_id = a.hadm_id
JOIN `physionet-data.mimiciv_3_1_hosp.patients` p
  ON ie.subject_id = p.subject_id
WHERE r.duration_hours >= 24
  AND r.episode_rank = 1
  AND p.anchor_age + EXTRACT(YEAR FROM a.admittime) - p.anchor_year >= 18
;

-- ===== 02_eligibility.sql =====
-- 02_eligibility.sql
-- Stop-anchored eligibility: time zero is 6 h before the last charted CRRT setting.
-- This avoids selecting only patients with high urine output at a daily landmark,
-- which would make the gradual-taper group too small.
--
-- Eligibility at time zero:
--   * CRRT >= 24 h before time zero
--   * alive, still on CRRT, planned stop (not death/transfer within 24 h)
--   * norepinephrine <= threshold or none
--   * K+ <= threshold, pH >= threshold (if measured)
-- UO and creatinine are covariates, not eligibility criteria.

CREATE OR REPLACE TABLE `YOUR_PROJECT.mimic_work.crrt_eligibility` AS
WITH episodes AS (
  SELECT
    e.*,
    e.end_time AS stop_time,
    DATETIME_SUB(e.end_time, INTERVAL 6 HOUR) AS time_zero
  FROM `YOUR_PROJECT.mimic_work.crrt_episodes` e
  WHERE e.end_time >= DATETIME_ADD(e.start_time, INTERVAL 30 HOUR)
    AND (e.death_time IS NULL OR e.death_time > DATETIME_ADD(e.end_time, INTERVAL 24 HOUR))
    AND e.end_time < DATETIME_SUB(e.outtime, INTERVAL 1 HOUR)
),
weight AS (
  SELECT
    stay_id,
    AVG(valuenum) AS weight_kg
  FROM `physionet-data.mimiciv_3_1_icu.chartevents`
  WHERE itemid IN (226512, 224639)
    AND valuenum BETWEEN 20 AND 300
  GROUP BY stay_id
),
norepi AS (
  SELECT
    e.stay_id,
    e.time_zero,
    MAX(
      CASE
        WHEN ie.rateuom = 'mcg/kg/min' THEN ie.rate
        WHEN ie.rateuom = 'mcg/min' THEN ie.rate / NULLIF(w.weight_kg, 0)
        WHEN ie.rateuom = 'mcg/kg/hr' THEN ie.rate / 60.0
        WHEN ie.rateuom = 'mcg/hr' THEN ie.rate / 60.0 / NULLIF(w.weight_kg, 0)
        WHEN ie.rateuom = 'mg/hour' THEN ie.rate * 1000.0 / 60.0 / NULLIF(w.weight_kg, 0)
        ELSE NULL
      END
    ) AS norepi_rate
  FROM episodes e
  LEFT JOIN `physionet-data.mimiciv_3_1_icu.inputevents` ie
    ON ie.stay_id = e.stay_id
   AND ie.itemid = 221906
   AND ie.starttime <= e.time_zero
   AND ie.endtime > e.time_zero
  LEFT JOIN weight w
    ON e.stay_id = w.stay_id
  GROUP BY e.stay_id, e.time_zero
),
urine AS (
  SELECT
    e.stay_id,
    e.time_zero,
    SUM(CASE WHEN o.charttime >= DATETIME_SUB(e.time_zero, INTERVAL 6 HOUR) THEN o.value ELSE 0 END) AS uo_6h,
    SUM(o.value) AS uo_24h
  FROM episodes e
  LEFT JOIN `physionet-data.mimiciv_3_1_icu.outputevents` o
    ON o.stay_id = e.stay_id
   AND o.charttime BETWEEN DATETIME_SUB(e.time_zero, INTERVAL 24 HOUR) AND e.time_zero
   AND o.itemid IN (
     226559, -- Foley
     226560, -- Void
     226561, -- Condom Cath
     226584, -- Ileoconduit
     226563, -- Suprapubic
     226564, -- R Nephrostomy
     226565, -- L Nephrostomy
     226567, -- Straight Cath
     226557, -- R Ureteral Stent
     226558, -- L Ureteral Stent
     226566, -- Urine and GU Irrigant Out
     226627, -- OR Urine
     226631, -- PACU Urine
     226713, -- Incontinent/voids estimate
     227489  -- GU Irrigant/Urine Volume Out
   )
  GROUP BY e.stay_id, e.time_zero
),
labs AS (
  SELECT
    e.stay_id,
    e.time_zero,
    MAX(IF(le.itemid = 50971 AND le.charttime >= DATETIME_SUB(e.time_zero, INTERVAL 6 HOUR), le.valuenum, NULL)) AS k_max_6h,
    MIN(IF(le.itemid = 50820 AND le.charttime >= DATETIME_SUB(e.time_zero, INTERVAL 6 HOUR), le.valuenum, NULL)) AS ph_min_6h
  FROM episodes e
  LEFT JOIN `physionet-data.mimiciv_3_1_hosp.labevents` le
    ON le.subject_id = e.subject_id
   AND le.charttime BETWEEN DATETIME_SUB(e.time_zero, INTERVAL 6 HOUR) AND e.time_zero
  GROUP BY e.stay_id, e.time_zero
),
flags AS (
  SELECT
    e.*,
    w.weight_kg,
    n.norepi_rate,
    u.uo_6h,
    u.uo_24h,
    x.k_max_6h,
    x.ph_min_6h,
    (n.norepi_rate IS NULL OR n.norepi_rate <= 0.10) AS hemodynamic_ok,
    (x.k_max_6h IS NULL OR x.k_max_6h <= 5.5) AS k_ok,
    (x.ph_min_6h IS NULL OR x.ph_min_6h >= 7.25) AS ph_ok
  FROM episodes e
  LEFT JOIN weight w
    ON e.stay_id = w.stay_id
  LEFT JOIN norepi n
    ON e.stay_id = n.stay_id AND e.time_zero = n.time_zero
  LEFT JOIN urine u
    ON e.stay_id = u.stay_id AND e.time_zero = u.time_zero
  LEFT JOIN labs x
    ON e.stay_id = x.stay_id AND e.time_zero = x.time_zero
)
SELECT *
FROM flags
WHERE hemodynamic_ok
  AND k_ok
  AND ph_ok
;

-- ===== 03_exposure.sql =====
-- 03_exposure.sql
-- Classify discontinuation strategy from dialysate flow in the 6 h before stop.
-- Gradual: last-2h median <= 75% of the 6-2h median.
-- Abrupt: last-2h median >= 90% of the 6-2h median.
-- Ambiguous: in between; excluded from primary analysis.

CREATE OR REPLACE TABLE `YOUR_PROJECT.mimic_work.crrt_exposure` AS
WITH e AS (
  SELECT *
  FROM `YOUR_PROJECT.mimic_work.crrt_eligibility`
),
rates AS (
  SELECT
    e.stay_id,
    e.time_zero,
    e.stop_time,
    ce.charttime,
    ce.valuenum AS rate
  FROM e
  JOIN `physionet-data.mimiciv_3_1_icu.chartevents` ce
    ON ce.stay_id = e.stay_id
   AND ce.itemid = 224154
   AND ce.charttime BETWEEN DATETIME_SUB(e.stop_time, INTERVAL 6 HOUR) AND e.stop_time
  WHERE ce.valuenum > 0
),
agg AS (
  SELECT
    stay_id,
    time_zero,
    stop_time,
    APPROX_QUANTILES(
      IF(charttime BETWEEN DATETIME_SUB(stop_time, INTERVAL 6 HOUR)
                     AND DATETIME_SUB(stop_time, INTERVAL 2 HOUR), rate, NULL),
      100 IGNORE NULLS
    )[SAFE_OFFSET(50)] AS baseline_rate,
    APPROX_QUANTILES(
      IF(charttime BETWEEN DATETIME_SUB(stop_time, INTERVAL 2 HOUR)
                     AND stop_time, rate, NULL),
      100 IGNORE NULLS
    )[SAFE_OFFSET(50)] AS last_rate,
    COUNT(*) AS n_rates
  FROM rates
  GROUP BY stay_id, time_zero, stop_time
),
taper AS (
  SELECT
    r.stay_id,
    MIN(r.charttime) AS taper_start
  FROM rates r
  JOIN agg a
    ON r.stay_id = a.stay_id
   AND r.time_zero = a.time_zero
   AND r.stop_time = a.stop_time
  WHERE a.baseline_rate IS NOT NULL
    AND a.baseline_rate > 0
    AND r.rate <= 0.75 * a.baseline_rate
  GROUP BY r.stay_id
)
SELECT
  e.*,
  a.baseline_rate,
  a.last_rate,
  a.n_rates,
  t.taper_start,
  CASE
    WHEN a.baseline_rate IS NULL OR a.baseline_rate = 0 OR a.n_rates < 3 THEN 'insufficient'
    WHEN a.last_rate <= 0.75 * a.baseline_rate THEN 'gradual'
    WHEN a.last_rate >= 0.90 * a.baseline_rate THEN 'abrupt'
    ELSE 'ambiguous'
  END AS exposure
FROM e
LEFT JOIN agg a
  ON e.stay_id = a.stay_id
 AND e.time_zero = a.time_zero
 AND e.stop_time = a.stop_time
LEFT JOIN taper t
  ON e.stay_id = t.stay_id
;

-- ===== 04_outcomes.sql =====
-- 04_outcomes.sql
-- 7-day dialysis-free survival, RRT restart, and 90-day mortality.
-- RRT restart is defined as any CRRT charting or dialysis procedure after stop.

CREATE OR REPLACE TABLE `YOUR_PROJECT.mimic_work.crrt_outcomes` AS
WITH e AS (
  SELECT *
  FROM `YOUR_PROJECT.mimic_work.crrt_exposure`
),
crrt_after AS (
  SELECT
    e.stay_id,
    MIN(ce.charttime) AS rrt_time
  FROM e
  JOIN `physionet-data.mimiciv_3_1_icu.chartevents` ce
    ON ce.stay_id = e.stay_id
   AND ce.charttime > e.stop_time
   AND ce.charttime <= DATETIME_ADD(e.stop_time, INTERVAL 7 DAY)
   AND ce.itemid IN (
     224144,224149,224150,224151,224152,224153,224154,
     224191,225183,225976,225977,228004,228005,228006,226457,224146
   )
  GROUP BY e.stay_id
),
proc_after AS (
  SELECT
    e.stay_id,
    MIN(pe.starttime) AS rrt_time
  FROM e
  JOIN `physionet-data.mimiciv_3_1_icu.procedureevents` pe
    ON pe.stay_id = e.stay_id
   AND pe.starttime > e.stop_time
   AND pe.starttime <= DATETIME_ADD(e.stop_time, INTERVAL 7 DAY)
   AND pe.itemid IN (
     SELECT itemid
     FROM `physionet-data.mimiciv_3_1_icu.d_items`
     WHERE REGEXP_CONTAINS(LOWER(label), r'hemodialysis|dialysis')
       AND linksto = 'procedureevents'
   )
  GROUP BY e.stay_id
),
rrt AS (
  SELECT stay_id, MIN(rrt_time) AS rrt_restart_time
  FROM (
    SELECT * FROM crrt_after
    UNION ALL
    SELECT * FROM proc_after
  )
  GROUP BY stay_id
)
SELECT
  e.*,
  r.rrt_restart_time,
  DATETIME_DIFF(r.rrt_restart_time, e.stop_time, HOUR) / 24.0 AS days_to_rrt,
  CASE
    WHEN r.rrt_restart_time IS NOT NULL
     AND r.rrt_restart_time <= DATETIME_ADD(e.stop_time, INTERVAL 7 DAY) THEN 1
    ELSE 0
  END AS rrt_restart_7d,
  CASE
    WHEN e.death_time IS NOT NULL
     AND e.death_time <= DATETIME_ADD(e.stop_time, INTERVAL 7 DAY) THEN 1
    ELSE 0
  END AS death_7d,
  CASE
    WHEN (r.rrt_restart_time IS NOT NULL
          AND r.rrt_restart_time <= DATETIME_ADD(e.stop_time, INTERVAL 7 DAY))
      OR (e.death_time IS NOT NULL
          AND e.death_time <= DATETIME_ADD(e.stop_time, INTERVAL 7 DAY))
    THEN 1 ELSE 0
  END AS event_7d,
  LEAST(
    7.0,
    COALESCE(DATETIME_DIFF(r.rrt_restart_time, e.stop_time, HOUR) / 24.0, 7.0),
    COALESCE(DATETIME_DIFF(e.death_time, e.stop_time, HOUR) / 24.0, 7.0)
  ) AS time_7d,
  CASE
    WHEN e.death_time IS NOT NULL
     AND e.death_time <= DATETIME_ADD(e.stop_time, INTERVAL 90 DAY) THEN 1
    ELSE 0
  END AS death_90d
FROM e
LEFT JOIN rrt r
  ON e.stay_id = r.stay_id
;

-- ===== 05_covariates.sql =====
-- 05_covariates.sql
-- Baseline covariates measured at or before time zero.
-- Sepsis/comorbidity flags are ICD-based and intentionally simple for v0.1.

CREATE OR REPLACE TABLE `YOUR_PROJECT.mimic_work.crrt_covariates` AS
WITH e AS (
  SELECT *
  FROM `YOUR_PROJECT.mimic_work.crrt_outcomes`
),
weight AS (
  SELECT
    stay_id,
    AVG(valuenum) AS weight_kg
  FROM `physionet-data.mimiciv_3_1_icu.chartevents`
  WHERE itemid IN (226512, 224639)
    AND valuenum BETWEEN 20 AND 300
  GROUP BY stay_id
)
SELECT
  e.stay_id,
  e.time_zero,
  e.stop_time,
  w.weight_kg,
  (SELECT le.valuenum
   FROM `physionet-data.mimiciv_3_1_hosp.labevents` le
   WHERE le.subject_id = e.subject_id
     AND le.itemid = 50912
     AND le.charttime <= e.time_zero
   ORDER BY le.charttime DESC
   LIMIT 1) AS baseline_creat,
  (SELECT le.valuenum
   FROM `physionet-data.mimiciv_3_1_hosp.labevents` le
   WHERE le.subject_id = e.subject_id
     AND le.itemid = 50813
     AND le.charttime BETWEEN DATETIME_SUB(e.time_zero, INTERVAL 6 HOUR) AND e.time_zero
   ORDER BY le.charttime DESC
   LIMIT 1) AS lactate,
  e.norepi_rate,
  e.uo_6h,
  e.uo_24h,
  EXISTS(
    SELECT 1
    FROM `physionet-data.mimiciv_3_1_icu.inputevents` ie
    WHERE ie.stay_id = e.stay_id
      AND ie.itemid = 221794 -- Furosemide
      AND ie.starttime BETWEEN DATETIME_SUB(e.time_zero, INTERVAL 24 HOUR) AND e.time_zero
  ) AS diuretic_24h,
  EXISTS(
    SELECT 1
    FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
    WHERE d.hadm_id = e.hadm_id
      AND (
        d.icd_code LIKE 'A41%' OR d.icd_code LIKE '038%'
        OR d.icd_code LIKE '99591%' OR d.icd_code LIKE '99592%'
      )
  ) AS sepsis,
  EXISTS(
    SELECT 1 FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
    WHERE d.hadm_id = e.hadm_id
      AND (d.icd_code LIKE 'I50%' OR d.icd_code LIKE '428%')
  ) AS chf,
  EXISTS(
    SELECT 1 FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
    WHERE d.hadm_id = e.hadm_id
      AND (d.icd_code LIKE 'N18%' OR d.icd_code LIKE '585%')
  ) AS ckd,
  EXISTS(
    SELECT 1 FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
    WHERE d.hadm_id = e.hadm_id
      AND (d.icd_code LIKE 'E11%' OR d.icd_code LIKE '250%')
  ) AS diabetes,
  EXISTS(
    SELECT 1 FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
    WHERE d.hadm_id = e.hadm_id
      AND (d.icd_code LIKE 'J44%' OR d.icd_code LIKE '496%')
  ) AS copd,
  EXISTS(
    SELECT 1 FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
    WHERE d.hadm_id = e.hadm_id
      AND (d.icd_code LIKE 'K70%' OR d.icd_code LIKE 'K74%' OR d.icd_code LIKE '571%')
  ) AS liver,
  EXISTS(
    SELECT 1 FROM `physionet-data.mimiciv_3_1_hosp.diagnoses_icd` d
    WHERE d.hadm_id = e.hadm_id
      AND (d.icd_code LIKE 'C%' OR d.icd_code BETWEEN '140' AND '208')
  ) AS cancer,
  EXISTS(
    SELECT 1
    FROM `physionet-data.mimiciv_3_1_icu.procedureevents` pe
    WHERE pe.stay_id = e.stay_id
      AND pe.itemid = 225792 -- Invasive ventilation
      AND pe.starttime <= e.time_zero
      AND pe.endtime >= e.time_zero
  ) AS mv
FROM e
LEFT JOIN weight w
  ON e.stay_id = w.stay_id
;

-- ===== 06_analysis_dataset.sql =====
-- 06_analysis_dataset.sql
-- One row per eligible patient. This is the table exported to Parquet for Python analysis.

CREATE OR REPLACE TABLE `YOUR_PROJECT.mimic_work.analysis_dataset` AS
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
FROM `YOUR_PROJECT.mimic_work.crrt_outcomes` e
LEFT JOIN `YOUR_PROJECT.mimic_work.crrt_covariates` c
  ON e.stay_id = c.stay_id
 AND e.time_zero = c.time_zero
 AND e.stop_time = c.stop_time
;

-- Final table: export this result to CSV.
SELECT * FROM `YOUR_PROJECT.mimic_work.analysis_dataset`;
