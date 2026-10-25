CREATE OR REPLACE TABLE `deresuscitation-tte.mimic_work.eicu_icu_landmark` AS
WITH c AS (
  SELECT * FROM `deresuscitation-tte.mimic_work.eicu_crrt_cohort`
  WHERE crrt_within_7d = 1
),
creat AS (
  SELECT c.patientunitstayid,
    MIN(IF(l.labresultoffset BETWEEN -10080 AND 0, l.labresult, NULL)) AS baseline_creat,
    MAX(IF(l.labresultoffset BETWEEN 0 AND 1440, l.labresult, NULL)) AS creat_max_24h,
    MIN(IF(l.labresultoffset BETWEEN 0 AND 1440, l.labresult, NULL)) AS creat_min_24h
  FROM c JOIN `physionet-data.eicu_crd.lab` l USING(patientunitstayid)
  WHERE LOWER(l.labname)='creatinine'
    AND l.labresultoffset BETWEEN -10080 AND 1440
  GROUP BY 1
),
uo AS (
  SELECT c.patientunitstayid,
    SUM(IF(io.intakeoutputoffset BETWEEN 0 AND 360, io.cellvaluenumeric, NULL)) AS uo_6h,
    SUM(IF(io.intakeoutputoffset BETWEEN 0 AND 720, io.cellvaluenumeric, NULL)) AS uo_12h,
    SUM(IF(io.intakeoutputoffset BETWEEN 0 AND 1440, io.cellvaluenumeric, NULL)) AS uo_24h,
    COUNT(io.intakeoutputid) AS uo_rows
  FROM c JOIN `physionet-data.eicu_crd.intakeoutput` io USING(patientunitstayid)
  WHERE io.intakeoutputoffset BETWEEN 0 AND 1440
    AND (LOWER(io.celllabel) LIKE '%urine%' OR LOWER(io.celllabel) LIKE '%foley%' OR LOWER(io.celllabel) LIKE '%void%')
  GROUP BY 1
),
labs AS (
  SELECT c.patientunitstayid,
    MAX(IF(LOWER(l.labname)='potassium', l.labresult, NULL)) AS k_max,
    MIN(IF(LOWER(l.labname)='ph', l.labresult, NULL)) AS ph_min,
    MIN(IF(LOWER(l.labname)='bicarbonate', l.labresult, NULL)) AS bicarb_min
  FROM c JOIN `physionet-data.eicu_crd.lab` l USING(patientunitstayid)
  WHERE LOWER(l.labname) IN ('potassium','ph','bicarbonate')
    AND l.labresultoffset BETWEEN 0 AND 1440
  GROUP BY 1
),
vaso AS (
  SELECT c.patientunitstayid,
    MAX(IF(REGEXP_CONTAINS(LOWER(i.drugname), r'norepinephrine|epinephrine|dopamine|vasopressin|phenylephrine')
           AND i.infusionoffset BETWEEN 0 AND 1440, 1, 0)) AS vaso
  FROM c JOIN `physionet-data.eicu_crd.infusiondrug` i USING(patientunitstayid)
  GROUP BY 1
)
SELECT c.* EXCEPT (baseline_creat, creat_max_24h, creat_min_24h, uo_6h, uo_12h, uo_24h, uo_rows, k_max, ph_min, bicarb_min, vaso),
  cr.baseline_creat, cr.creat_max_24h, cr.creat_min_24h,
  u.uo_6h, u.uo_12h, u.uo_24h, u.uo_rows,
  l.k_max, l.ph_min, l.bicarb_min,
  COALESCE(v.vaso, c.vaso, 0) AS vaso_icu
FROM c
LEFT JOIN creat cr USING(patientunitstayid)
LEFT JOIN uo u USING(patientunitstayid)
LEFT JOIN labs l USING(patientunitstayid)
LEFT JOIN vaso v USING(patientunitstayid);
