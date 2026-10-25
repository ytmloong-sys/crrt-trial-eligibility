-- 08_landmark72_cohort.sql
-- 72-hour landmark cohort:
--   time zero = 72 h after CRRT start
--   eligible if still on CRRT, alive, stable, no urgent RRT indication
--   exposure = discontinuation within 24 h after time zero (early) vs later (delayed)
--   primary outcome = 28-day dialysis-free survival

CREATE OR REPLACE TABLE `{{work}}.crrt_landmark72` AS
WITH episodes AS (
  SELECT
    e.*,
    DATETIME_ADD(e.start_time, INTERVAL 72 HOUR) AS time_zero,
    e.end_time AS stop_time
  FROM `{{work}}.crrt_episodes` e
  WHERE e.end_time > DATETIME_ADD(e.start_time, INTERVAL 72 HOUR)
    AND e.outtime > DATETIME_ADD(e.start_time, INTERVAL 72 HOUR)
    AND (e.death_time IS NULL OR e.death_time > DATETIME_ADD(e.start_time, INTERVAL 72 HOUR))
    AND e.end_time < DATETIME_SUB(e.outtime, INTERVAL 1 HOUR)
    AND (e.death_time IS NULL OR e.death_time > DATETIME_ADD(e.end_time, INTERVAL 24 HOUR))
),
weight AS (
  SELECT stay_id, AVG(valuenum) AS weight_kg
  FROM `{{icu}}.chartevents`
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
  LEFT JOIN `{{icu}}.inputevents` ie
    ON ie.stay_id = e.stay_id
   AND ie.itemid = 221906
   AND ie.starttime <= e.time_zero
   AND ie.endtime > e.time_zero
  LEFT JOIN weight w ON e.stay_id = w.stay_id
  GROUP BY e.stay_id, e.time_zero
),
urine AS (
  SELECT
    e.stay_id,
    e.time_zero,
    SUM(CASE WHEN o.charttime >= DATETIME_SUB(e.time_zero, INTERVAL 6 HOUR) THEN o.value ELSE 0 END) AS uo_6h,
    SUM(o.value) AS uo_24h
  FROM episodes e
  LEFT JOIN `{{icu}}.outputevents` o
    ON o.stay_id = e.stay_id
   AND o.charttime BETWEEN DATETIME_SUB(e.time_zero, INTERVAL 24 HOUR) AND e.time_zero
   AND o.itemid IN (
     226559,226560,226561,226584,226563,226564,226565,226567,
     226557,226558,226566,226627,226631,226713,227489
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
  LEFT JOIN `{{hosp}}.labevents` le
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
    (n.norepi_rate IS NULL OR n.norepi_rate <= {{norepi_max_ug_kg_min}}) AS hemodynamic_ok,
    (x.k_max_6h IS NULL OR x.k_max_6h <= {{potassium_max_mmol_l}}) AS k_ok,
    (x.ph_min_6h IS NULL OR x.ph_min_6h >= {{ph_min}}) AS ph_ok,
    DATETIME_DIFF(e.end_time, e.time_zero, HOUR) AS hours_to_stop
  FROM episodes e
  LEFT JOIN weight w ON e.stay_id = w.stay_id
  LEFT JOIN norepi n ON e.stay_id = n.stay_id AND e.time_zero = n.time_zero
  LEFT JOIN urine u ON e.stay_id = u.stay_id AND e.time_zero = u.time_zero
  LEFT JOIN labs x ON e.stay_id = x.stay_id AND e.time_zero = x.time_zero
),
eligible AS (
  SELECT *
  FROM flags
  WHERE hemodynamic_ok AND k_ok AND ph_ok
    AND hours_to_stop > 0
),
crrt_after AS (
  SELECT e.stay_id, MIN(ce.charttime) AS rrt_time
  FROM eligible e
  JOIN `{{icu}}.chartevents` ce
    ON ce.stay_id = e.stay_id
   AND ce.charttime > e.end_time
   AND ce.charttime <= DATETIME_ADD(e.time_zero, INTERVAL 28 DAY)
   AND ce.itemid IN (
     224144,224149,224150,224151,224152,224153,224154,
     224191,225183,225976,225977,228004,228005,228006,226457,224146
   )
  GROUP BY e.stay_id
),
proc_after AS (
  SELECT e.stay_id, MIN(pe.starttime) AS rrt_time
  FROM eligible e
  JOIN `{{icu}}.procedureevents` pe
    ON pe.stay_id = e.stay_id
   AND pe.starttime > e.end_time
   AND pe.starttime <= DATETIME_ADD(e.time_zero, INTERVAL 28 DAY)
  JOIN (
    SELECT itemid
    FROM `{{icu}}.d_items`
    WHERE REGEXP_CONTAINS(LOWER(label), r'hemodialysis|dialysis')
      AND linksto = 'procedureevents'
  ) di
    ON pe.itemid = di.itemid
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
  e.duration_hours,
  e.weight_kg,
  e.norepi_rate,
  e.uo_6h,
  e.uo_24h,
  e.k_max_6h,
  e.ph_min_6h,
  e.hours_to_stop,
  CASE WHEN e.hours_to_stop <= 24 THEN 1 ELSE 0 END AS early_stop,
  CASE WHEN e.hours_to_stop > 24 THEN 1 ELSE 0 END AS delayed_stop,
  r.rrt_restart_time,
  CASE
    WHEN r.rrt_restart_time IS NOT NULL
     AND r.rrt_restart_time <= DATETIME_ADD(e.time_zero, INTERVAL 28 DAY) THEN 1
    ELSE 0
  END AS rrt_restart_28d,
  CASE
    WHEN e.death_time IS NOT NULL
     AND e.death_time <= DATETIME_ADD(e.time_zero, INTERVAL 28 DAY) THEN 1
    ELSE 0
  END AS death_28d,
  CASE
    WHEN e.death_time IS NOT NULL
     AND e.death_time <= DATETIME_ADD(e.time_zero, INTERVAL 90 DAY) THEN 1
    ELSE 0
  END AS death_90d,
  CASE
    WHEN (e.death_time IS NULL OR e.death_time > DATETIME_ADD(e.time_zero, INTERVAL 28 DAY))
     AND (r.rrt_restart_time IS NULL OR r.rrt_restart_time > DATETIME_ADD(e.time_zero, INTERVAL 28 DAY))
     AND e.end_time <= DATETIME_ADD(e.time_zero, INTERVAL 28 DAY)
    THEN 1 ELSE 0
  END AS dialysis_free_28d
FROM eligible e
LEFT JOIN rrt r ON e.stay_id = r.stay_id
