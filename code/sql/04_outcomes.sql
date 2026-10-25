-- 04_outcomes.sql
-- 7-day dialysis-free survival, RRT restart, and 90-day mortality.
-- RRT restart is defined as any CRRT charting or dialysis procedure after stop.

CREATE OR REPLACE TABLE `{{work}}.crrt_outcomes` AS
WITH e AS (
  SELECT *
  FROM `{{work}}.crrt_exposure`
),
crrt_after AS (
  SELECT
    e.stay_id,
    MIN(ce.charttime) AS rrt_time
  FROM e
  JOIN `{{icu}}.chartevents` ce
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
  JOIN `{{icu}}.procedureevents` pe
    ON pe.stay_id = e.stay_id
   AND pe.starttime > e.stop_time
   AND pe.starttime <= DATETIME_ADD(e.stop_time, INTERVAL 7 DAY)
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
