-- 02_eligibility.sql
-- Daily landmark screening for the first time a patient meets liberation criteria.
-- Time zero = first eligible daily landmark.
-- This is deliberately conservative; sensitivity analyses can relax individual criteria.

WITH episodes AS (
  SELECT *
  FROM `deresuscitation-tte.mimic_work.crrt_episodes`
  WHERE end_time >= DATETIME_ADD(start_time, INTERVAL 26 HOUR)
),
landmarks AS (
  SELECT
    e.*,
    DATETIME_ADD(e.start_time, INTERVAL h HOUR) AS landmark
  FROM episodes e
  CROSS JOIN UNNEST(GENERATE_ARRAY(
    24,
    DATETIME_DIFF(e.end_time, e.start_time, HOUR) - 2,
    24
  )) AS h
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
    l.stay_id,
    l.landmark,
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
  FROM landmarks l
  LEFT JOIN `physionet-data.mimiciv_3_1_icu.inputevents` ie
    ON ie.stay_id = l.stay_id
   AND ie.itemid = 221906
   AND ie.starttime <= l.landmark
   AND ie.endtime > l.landmark
  LEFT JOIN weight w
    ON l.stay_id = w.stay_id
  GROUP BY l.stay_id, l.landmark
),
urine AS (
  SELECT
    l.stay_id,
    l.landmark,
    SUM(CASE WHEN o.charttime >= DATETIME_SUB(l.landmark, INTERVAL 6 HOUR) THEN o.value ELSE 0 END) AS uo_6h,
    SUM(o.value) AS uo_24h
  FROM landmarks l
  LEFT JOIN `physionet-data.mimiciv_3_1_icu.outputevents` o
    ON o.stay_id = l.stay_id
   AND o.charttime BETWEEN DATETIME_SUB(l.landmark, INTERVAL 24 HOUR) AND l.landmark
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
     227488, -- GU Irrigant Volume In
     227489  -- GU Irrigant/Urine Volume Out
   )
  GROUP BY l.stay_id, l.landmark
),
labs AS (
  SELECT
    l.stay_id,
    l.landmark,
    MAX(IF(le.itemid = 50912 AND le.charttime >= DATETIME_SUB(l.landmark, INTERVAL 24 HOUR), le.valuenum, NULL)) AS creat_max_24h,
    MIN(IF(le.itemid = 50912 AND le.charttime >= DATETIME_SUB(l.landmark, INTERVAL 24 HOUR), le.valuenum, NULL)) AS creat_min_24h,
    MAX(IF(le.itemid = 50971 AND le.charttime >= DATETIME_SUB(l.landmark, INTERVAL 6 HOUR), le.valuenum, NULL)) AS k_max_6h,
    MIN(IF(le.itemid = 50820 AND le.charttime >= DATETIME_SUB(l.landmark, INTERVAL 6 HOUR), le.valuenum, NULL)) AS ph_min_6h
  FROM landmarks l
  LEFT JOIN `physionet-data.mimiciv_3_1_hosp.labevents` le
    ON le.subject_id = l.subject_id
   AND le.charttime BETWEEN DATETIME_SUB(l.landmark, INTERVAL 24 HOUR) AND l.landmark
  GROUP BY l.stay_id, l.landmark
),
flags AS (
  SELECT
    l.*,
    w.weight_kg,
    n.norepi_rate,
    u.uo_6h,
    u.uo_24h,
    x.creat_max_24h,
    x.creat_min_24h,
    x.creat_max_24h - x.creat_min_24h AS creat_delta,
    x.k_max_6h,
    x.ph_min_6h,
    (n.norepi_rate IS NULL OR n.norepi_rate <= 0.10) AS hemodynamic_ok,
    (w.weight_kg IS NOT NULL
      AND (u.uo_6h >= 0.50 * w.weight_kg * 6.0 OR u.uo_24h >= 400)) AS urine_ok,
    (x.creat_max_24h IS NULL OR (x.creat_max_24h - x.creat_min_24h) < 0.30) AS creat_ok,
    (x.k_max_6h IS NULL OR x.k_max_6h <= 5.5) AS k_ok,
    (x.ph_min_6h IS NULL OR x.ph_min_6h >= 7.25) AS ph_ok
  FROM landmarks l
  LEFT JOIN weight w
    ON l.stay_id = w.stay_id
  LEFT JOIN norepi n
    ON l.stay_id = n.stay_id AND l.landmark = n.landmark
  LEFT JOIN urine u
    ON l.stay_id = u.stay_id AND l.landmark = u.landmark
  LEFT JOIN labs x
    ON l.stay_id = x.stay_id AND l.landmark = x.landmark
)
SELECT
  COUNT(*) AS n,
  APPROX_QUANTILES(uo_6h, 100)[OFFSET(10)] AS uo6_p10,
  APPROX_QUANTILES(uo_6h, 100)[OFFSET(50)] AS uo6_p50,
  APPROX_QUANTILES(uo_6h, 100)[OFFSET(90)] AS uo6_p90,
  APPROX_QUANTILES(uo_24h, 100)[OFFSET(50)] AS uo24_p50,
  APPROX_QUANTILES(weight_kg, 100)[OFFSET(50)] AS wt_p50,
  COUNTIF(uo_6h >= 0.5 * weight_kg * 6) AS n_uo6_ok,
  COUNTIF(uo_24h >= 400) AS n_uo24_ok,
  COUNTIF(uo_6h >= 0.5 * weight_kg * 6 OR uo_24h >= 400) AS n_either,
  COUNTIF(uo_6h = 0) AS n_uo6_zero
FROM flags;
