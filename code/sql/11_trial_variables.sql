-- 11_trial_variables.sql
-- One row per CRRT episode with variables needed to operationalize trial eligibility.
-- t0 = 6 h before CRRT start (pre-CRRT decision point).

CREATE OR REPLACE TABLE `{{work}}.trial_variables` AS
WITH e AS (
  SELECT
    e.*,
    DATETIME_SUB(e.start_time, INTERVAL 6 HOUR) AS t0
  FROM `{{work}}.crrt_episodes` e
),
weight AS (
  SELECT stay_id, AVG(valuenum) AS weight_kg
  FROM `{{icu}}.chartevents`
  WHERE itemid IN (226512, 224639)
    AND valuenum BETWEEN 20 AND 300
  GROUP BY stay_id
),
creat_base AS (
  SELECT e.stay_id, MIN(le.valuenum) AS baseline_creat
  FROM e
  JOIN `{{hosp}}.labevents` le
    ON le.subject_id = e.subject_id
   AND le.itemid = 50912
   AND le.charttime BETWEEN DATETIME_SUB(e.t0, INTERVAL 7 DAY) AND e.t0
  GROUP BY e.stay_id
),
creat24 AS (
  SELECT e.stay_id,
    MAX(le.valuenum) AS creat_max_24h,
    MIN(le.valuenum) AS creat_min_24h
  FROM e
  JOIN `{{hosp}}.labevents` le
    ON le.subject_id = e.subject_id
   AND le.itemid = 50912
   AND le.charttime BETWEEN DATETIME_SUB(e.t0, INTERVAL 24 HOUR) AND e.t0
  GROUP BY e.stay_id
),
uo AS (
  SELECT e.stay_id,
    CASE WHEN COUNT(o.charttime) = 0 THEN NULL
         ELSE SUM(CASE WHEN o.charttime >= DATETIME_SUB(e.t0, INTERVAL 6 HOUR) THEN o.value ELSE 0 END)
    END AS uo_6h,
    CASE WHEN COUNT(o.charttime) = 0 THEN NULL
         ELSE SUM(CASE WHEN o.charttime >= DATETIME_SUB(e.t0, INTERVAL 12 HOUR) THEN o.value ELSE 0 END)
    END AS uo_12h,
    CASE WHEN COUNT(o.charttime) = 0 THEN NULL ELSE SUM(o.value) END AS uo_24h
  FROM e
  LEFT JOIN `{{icu}}.outputevents` o
    ON o.stay_id = e.stay_id
   AND o.charttime BETWEEN DATETIME_SUB(e.t0, INTERVAL 24 HOUR) AND e.t0
   AND o.itemid IN (
     226559,226560,226561,226584,226563,226564,226565,226567,
     226557,226558,226566,226627,226631,226713,227489
   )
  GROUP BY e.stay_id
),
labs AS (
  SELECT e.stay_id,
    MAX(IF(le.itemid = 50971, le.valuenum, NULL)) AS k_max,
    MIN(IF(le.itemid = 50882, le.valuenum, NULL)) AS bicarb_min,
    MIN(IF(le.itemid = 50820, le.valuenum, NULL)) AS ph_min
  FROM e
  LEFT JOIN `{{hosp}}.labevents` le
    ON le.subject_id = e.subject_id
   AND le.charttime BETWEEN DATETIME_SUB(e.t0, INTERVAL 24 HOUR) AND e.t0
   AND le.itemid IN (50971, 50882, 50820)
  GROUP BY e.stay_id
),
mv AS (
  SELECT e.stay_id, MAX(1) AS mv
  FROM e
  JOIN `{{icu}}.procedureevents` pe
    ON pe.stay_id = e.stay_id
   AND pe.itemid = 225792
   AND pe.starttime <= e.t0
   AND pe.endtime >= e.t0
  GROUP BY e.stay_id
),
vaso AS (
  SELECT e.stay_id, MAX(1) AS vaso
  FROM e
  JOIN `{{icu}}.inputevents` ie
    ON ie.stay_id = e.stay_id
   AND ie.itemid IN (221906,221289,221662,222315,221749)
   AND ie.starttime <= e.t0
   AND ie.endtime > e.t0
  GROUP BY e.stay_id
),
dx AS (
  SELECT
    hadm_id,
    MAX(IF(icd_code LIKE 'A41%' OR icd_code LIKE '038%' OR icd_code LIKE '99591%' OR icd_code LIKE '99592%', 1, 0)) AS sepsis,
    MAX(IF(icd_code LIKE 'N18%' OR icd_code LIKE '585%', 1, 0)) AS ckd,
    MAX(IF(icd_code LIKE 'N186%' OR icd_code LIKE '5856%', 1, 0)) AS esrd,
    MAX(IF(icd_code LIKE 'Z940%' OR icd_code LIKE 'V420%', 1, 0)) AS transplant,
    MAX(IF(icd_code LIKE 'K74%' OR icd_code LIKE '5715%' OR icd_code LIKE '5712%' OR icd_code LIKE '5716%', 1, 0)) AS cirrhosis,
    MAX(IF(icd_code LIKE 'C%' OR icd_code BETWEEN '140' AND '208', 1, 0)) AS cancer,
    MAX(IF(icd_code LIKE 'I50%' OR icd_code LIKE '428%', 1, 0)) AS chf,
    MAX(IF(icd_code LIKE 'J44%' OR icd_code LIKE '496%', 1, 0)) AS copd,
    MAX(IF(icd_code LIKE 'N13%' OR icd_code LIKE '591%', 1, 0)) AS obstruction,
    MAX(IF(icd_code LIKE 'N00%' OR icd_code LIKE 'N01%' OR icd_code LIKE 'N02%' OR icd_code LIKE 'N03%' OR icd_code LIKE 'N04%' OR icd_code LIKE 'N05%' OR icd_code LIKE 'M31%', 1, 0)) AS gn_vasculitis
  FROM `{{hosp}}.diagnoses_icd`
  GROUP BY hadm_id
),
prior_rrt AS (
  SELECT DISTINCT e.stay_id
  FROM e
  JOIN `{{icu}}.procedureevents` pe
    ON pe.stay_id = e.stay_id
   AND pe.starttime < e.t0
  JOIN (
    SELECT itemid
    FROM `{{icu}}.d_items`
    WHERE (
        LOWER(label) LIKE '%hemodialysis%'
        OR LOWER(label) LIKE '%cvvh%'
        OR LOWER(label) LIKE '%crrt%'
        OR LOWER(label) LIKE '%renal replacement%'
      )
      AND LOWER(label) NOT LIKE '%catheter%'
      AND linksto = 'procedureevents'
  ) di
    ON pe.itemid = di.itemid
)
SELECT
  e.stay_id,
  e.subject_id,
  e.hadm_id,
  e.t0,
  e.start_time,
  e.end_time,
  e.age,
  e.gender,
  e.race,
  e.admission_type,
  e.first_careunit,
  e.duration_hours,
  w.weight_kg,
  cb.baseline_creat,
  c.creat_max_24h,
  c.creat_min_24h,
  u.uo_6h,
  u.uo_12h,
  u.uo_24h,
  l.k_max,
  l.bicarb_min,
  l.ph_min,
  COALESCE(m.mv, 0) AS mv,
  COALESCE(v.vaso, 0) AS vaso,
  COALESCE(dx.sepsis, 0) AS sepsis,
  COALESCE(dx.ckd, 0) AS ckd,
  COALESCE(dx.esrd, 0) AS esrd,
  COALESCE(dx.transplant, 0) AS transplant,
  COALESCE(dx.cirrhosis, 0) AS cirrhosis,
  COALESCE(dx.cancer, 0) AS cancer,
  COALESCE(dx.chf, 0) AS chf,
  COALESCE(dx.copd, 0) AS copd,
  COALESCE(dx.obstruction, 0) AS obstruction,
  COALESCE(dx.gn_vasculitis, 0) AS gn_vasculitis,
  CASE WHEN pr.stay_id IS NOT NULL THEN 1 ELSE 0 END AS prior_rrt,
  CASE WHEN e.death_time IS NOT NULL AND e.death_time <= DATETIME_ADD(e.t0, INTERVAL 24 HOUR) THEN 1 ELSE 0 END AS death_24h,
  CASE WHEN e.death_time IS NOT NULL AND e.death_time <= DATETIME_ADD(e.t0, INTERVAL 90 DAY) THEN 1 ELSE 0 END AS death_90d,
  CASE WHEN e.death_time IS NOT NULL AND e.death_time <= DATETIME_ADD(e.start_time, INTERVAL 90 DAY) THEN 1 ELSE 0 END AS death_90d_from_crrt
FROM e
LEFT JOIN weight w ON e.stay_id = w.stay_id
LEFT JOIN creat_base cb ON e.stay_id = cb.stay_id
LEFT JOIN creat24 c ON e.stay_id = c.stay_id
LEFT JOIN uo u ON e.stay_id = u.stay_id
LEFT JOIN labs l ON e.stay_id = l.stay_id
LEFT JOIN mv m ON e.stay_id = m.stay_id
LEFT JOIN vaso v ON e.stay_id = v.stay_id
LEFT JOIN dx ON e.hadm_id = dx.hadm_id
LEFT JOIN prior_rrt pr ON e.stay_id = pr.stay_id