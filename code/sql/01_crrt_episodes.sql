-- 01_crrt_episodes.sql
-- Build CRRT episodes from ICU chartevents.
-- A CRRT episode is a run of CRRT settings with gaps <= max_gap_hours.
-- Only the first episode per ICU stay is retained.

CREATE OR REPLACE TABLE `{{work}}.crrt_episodes` AS
WITH settings AS (
  SELECT
    ce.stay_id,
    ce.charttime,
    ce.itemid,
    ce.valuenum,
    ce.value
  FROM `{{icu}}.chartevents` ce
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
      WHEN DATETIME_DIFF(charttime, prev_time, HOUR) > {{max_gap_hours}} THEN 1
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
JOIN `{{icu}}.icustays` ie
  ON r.stay_id = ie.stay_id
JOIN `{{hosp}}.admissions` a
  ON ie.hadm_id = a.hadm_id
JOIN `{{hosp}}.patients` p
  ON ie.subject_id = p.subject_id
WHERE r.duration_hours >= {{min_crrt_hours}}
  AND r.episode_rank = 1
  AND p.anchor_age + EXTRACT(YEAR FROM a.admittime) - p.anchor_year >= {{age_min}}
