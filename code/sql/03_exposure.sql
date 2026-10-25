-- 03_exposure.sql
-- Classify discontinuation strategy from dialysate flow in the 6 h before stop.
-- Gradual: last-2h median <= 75% of the 6-2h median.
-- Abrupt: last-2h median >= 90% of the 6-2h median.
-- Ambiguous: in between; excluded from primary analysis.

CREATE OR REPLACE TABLE `{{work}}.crrt_exposure` AS
WITH e AS (
  SELECT *
  FROM `{{work}}.crrt_eligibility`
),
rates AS (
  SELECT
    e.stay_id,
    e.time_zero,
    e.stop_time,
    ce.charttime,
    ce.valuenum AS rate
  FROM e
  JOIN `{{icu}}.chartevents` ce
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
    AND r.rate <= {{gradual_ratio}} * a.baseline_rate
  GROUP BY r.stay_id
)
SELECT
  e.*,
  a.baseline_rate,
  a.last_rate,
  a.n_rates,
  t.taper_start,
  CASE
    WHEN a.baseline_rate IS NULL OR a.baseline_rate = 0 OR a.n_rates < {{min_rate_points}} THEN 'insufficient'
    WHEN a.last_rate <= {{gradual_ratio}} * a.baseline_rate THEN 'gradual'
    WHEN a.last_rate >= {{abrupt_ratio}} * a.baseline_rate THEN 'abrupt'
    ELSE 'ambiguous'
  END AS exposure
FROM e
LEFT JOIN agg a
  ON e.stay_id = a.stay_id
 AND e.time_zero = a.time_zero
 AND e.stop_time = a.stop_time
LEFT JOIN taper t
  ON e.stay_id = t.stay_id