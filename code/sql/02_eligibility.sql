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

CREATE OR REPLACE TABLE `{{work}}.crrt_eligibility` AS
WITH episodes AS (
  SELECT
    e.*,
    e.end_time AS stop_time,
    DATETIME_SUB(e.end_time, INTERVAL 6 HOUR) AS time_zero
  FROM `{{work}}.crrt_episodes` e
  WHERE e.end_time >= DATETIME_ADD(e.start_time, INTERVAL 30 HOUR)
    AND (e.death_time IS NULL OR e.death_time > DATETIME_ADD(e.end_time, INTERVAL 24 HOUR))
    AND e.end_time < DATETIME_SUB(e.outtime, INTERVAL 1 HOUR)
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
  LEFT JOIN `{{icu}}.outputevents` o
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
    (x.ph_min_6h IS NULL OR x.ph_min_6h >= {{ph_min}}) AS ph_ok
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
