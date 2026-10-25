import os, sys
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
from google.cloud import bigquery
client=bigquery.Client(project="deresuscitation-tte")
P="physionet-data.eicu_crd"; BT=chr(96); DEST="deresuscitation-tte.mimic_work.eicu_crrt_cohort"
sql=f"""
CREATE OR REPLACE TABLE {BT}{DEST}{BT} AS
WITH crrt AS (
  SELECT patientunitstayid,
         MIN(treatmentoffset) AS crrt_offset,
         MIN(treatmentoffset) - 360 AS time_zero
  FROM {BT}{P}.treatment{BT}
  WHERE LOWER(treatmentstring) LIKE '%c v v%' OR LOWER(treatmentstring) LIKE '%c a v h%'
  GROUP BY patientunitstayid
),
pat AS (
  SELECT patientunitstayid, uniquepid, hospitalid, unittype,
         gender, age,
         SAFE_CAST(REGEXP_EXTRACT(age, r'^[0-9]+') AS INT64) AS age_num,
         admissionweight AS weight_kg,
         hospitaldischargestatus, hospitaldischargeoffset,
         unitdischargestatus, unitdischargeoffset
  FROM {BT}{P}.patient{BT}
),
creat AS (
  SELECT c.patientunitstayid, c.time_zero,
    MIN(IF(l.labresultoffset BETWEEN c.time_zero-10080 AND c.time_zero, l.labresult, NULL)) AS baseline_creat,
    MAX(IF(l.labresultoffset BETWEEN c.time_zero-1440 AND c.time_zero, l.labresult, NULL)) AS creat_max_24h,
    MIN(IF(l.labresultoffset BETWEEN c.time_zero-1440 AND c.time_zero, l.labresult, NULL)) AS creat_min_24h,
    ARRAY_AGG(l.labresult ORDER BY ABS(l.labresultoffset-c.time_zero) LIMIT 1)[OFFSET(0)] AS creat_t0
  FROM crrt c JOIN {BT}{P}.lab{BT} l USING(patientunitstayid)
  WHERE LOWER(l.labname)='creatinine'
    AND l.labresultoffset BETWEEN c.time_zero-10080 AND c.time_zero+360
  GROUP BY 1,2
),
uo AS (
  SELECT c.patientunitstayid,
    SUM(IF(io.intakeoutputoffset BETWEEN c.time_zero-360 AND c.time_zero, io.cellvaluenumeric, NULL)) AS uo_6h,
    SUM(IF(io.intakeoutputoffset BETWEEN c.time_zero-720 AND c.time_zero, io.cellvaluenumeric, NULL)) AS uo_12h,
    SUM(IF(io.intakeoutputoffset BETWEEN c.time_zero-1440 AND c.time_zero, io.cellvaluenumeric, NULL)) AS uo_24h,
    COUNT(io.intakeoutputid) AS uo_rows
  FROM crrt c JOIN {BT}{P}.intakeoutput{BT} io USING(patientunitstayid)
  WHERE io.intakeoutputoffset BETWEEN c.time_zero-1440 AND c.time_zero
    AND (LOWER(io.celllabel) LIKE '%urine%' OR LOWER(io.celllabel) LIKE '%foley%' OR LOWER(io.celllabel) LIKE '%void%')
  GROUP BY 1
),
labs AS (
  SELECT c.patientunitstayid,
    MAX(IF(LOWER(l.labname)='potassium', l.labresult, NULL)) AS k_max,
    MIN(IF(LOWER(l.labname)='ph', l.labresult, NULL)) AS ph_min,
    MIN(IF(LOWER(l.labname)='bicarbonate', l.labresult, NULL)) AS bicarb_min
  FROM crrt c JOIN {BT}{P}.lab{BT} l USING(patientunitstayid)
  WHERE LOWER(l.labname) IN ('potassium','ph','bicarbonate')
    AND l.labresultoffset BETWEEN c.time_zero-1440 AND c.time_zero
  GROUP BY 1
),
vaso AS (
  SELECT c.patientunitstayid,
    MAX(IF(REGEXP_CONTAINS(LOWER(i.drugname), r'norepinephrine|epinephrine|dopamine|vasopressin|phenylephrine')
           AND i.infusionoffset BETWEEN c.time_zero-360 AND c.time_zero, 1, 0)) AS vaso
  FROM crrt c JOIN {BT}{P}.infusiondrug{BT} i USING(patientunitstayid)
  GROUP BY 1
),
mv AS (
  SELECT c.patientunitstayid,
    MAX(IF(a.ventday1=1,1,0)) AS mv
  FROM crrt c JOIN {BT}{P}.apachepredvar{BT} a USING(patientunitstayid)
  GROUP BY 1
),
sepsis AS (
  SELECT DISTINCT patientunitstayid, 1 AS sepsis
  FROM {BT}{P}.diagnosis{BT}
  WHERE LOWER(diagnosisstring) LIKE '%sepsis%'
),
hx AS (
  SELECT patientunitstayid,
    MAX(IF(LOWER(pasthistorypath) LIKE '%renal failure - hemodialysis%' OR LOWER(pasthistorypath) LIKE '%renal failure - peritoneal dialysis%',1,0)) AS esrd,
    MAX(IF(LOWER(pasthistorypath) LIKE '%transplant%',1,0)) AS transplant,
    MAX(IF(LOWER(pasthistorypath) LIKE '%cirrhosis%',1,0)) AS cirrhosis,
    MAX(IF(LOWER(pasthistorypath) LIKE '%cancer%' OR LOWER(pasthistorypath) LIKE '%malignancy%' OR LOWER(pasthistorypath) LIKE '%metastases%',1,0)) AS cancer,
    MAX(IF(LOWER(pasthistorypath) LIKE '%congestive heart failure%',1,0)) AS chf,
    MAX(IF(LOWER(pasthistorypath) LIKE '%copd%',1,0)) AS copd
  FROM {BT}{P}.pasthistory{BT}
  WHERE LOWER(pasthistorypath) LIKE '%renal failure%'
     OR LOWER(pasthistorypath) LIKE '%transplant%'
     OR LOWER(pasthistorypath) LIKE '%cirrhosis%'
     OR LOWER(pasthistorypath) LIKE '%cancer%'
     OR LOWER(pasthistorypath) LIKE '%malignancy%'
     OR LOWER(pasthistorypath) LIKE '%metastases%'
     OR LOWER(pasthistorypath) LIKE '%congestive heart failure%'
     OR LOWER(pasthistorypath) LIKE '%copd%'
  GROUP BY 1
),
obstruction AS (
  SELECT DISTINCT patientunitstayid, 1 AS obstruction
  FROM {BT}{P}.diagnosis{BT}
  WHERE (LOWER(diagnosisstring) LIKE '%renal%' OR LOWER(diagnosisstring) LIKE '%kidney%' OR LOWER(diagnosisstring) LIKE '%urinary%')
    AND (LOWER(diagnosisstring) LIKE '%obstruction%' OR LOWER(diagnosisstring) LIKE '%glomerulonephritis%' OR LOWER(diagnosisstring) LIKE '%vasculitis%')
),
prior_rrt AS (
  SELECT c.patientunitstayid,
    MAX(IF(LOWER(t.treatmentstring) LIKE 'renal|dialysis%'
           AND LOWER(t.treatmentstring) NOT LIKE '%catheter%'
           AND LOWER(t.treatmentstring) NOT LIKE '%insertion%'
           AND t.treatmentoffset < c.time_zero, 1, 0)) AS prior_rrt
  FROM crrt c JOIN {BT}{P}.treatment{BT} t USING(patientunitstayid)
  GROUP BY 1
)
SELECT
  c.patientunitstayid, p.uniquepid, p.hospitalid, p.unittype,
  p.gender, p.age, p.age_num, p.weight_kg,
  c.crrt_offset, c.time_zero,
  CASE WHEN c.crrt_offset <= 10080 THEN 1 ELSE 0 END AS crrt_within_7d,
  p.hospitaldischargestatus, p.hospitaldischargeoffset,
  CASE WHEN p.hospitaldischargestatus='Expired' THEN 1
       WHEN p.hospitaldischargestatus='Alive' THEN 0 ELSE NULL END AS death_hosp,
  CASE WHEN p.hospitaldischargestatus='Expired' AND p.hospitaldischargeoffset <= 1440 THEN 1 ELSE 0 END AS death_24h,
  cr.baseline_creat, cr.creat_max_24h, cr.creat_min_24h, cr.creat_t0,
  u.uo_6h, u.uo_12h, u.uo_24h, u.uo_rows,
  lb.k_max, lb.ph_min, lb.bicarb_min,
  COALESCE(v.vaso,0) AS vaso,
  COALESCE(m.mv,0) AS mv,
  COALESCE(s.sepsis,0) AS sepsis,
  COALESCE(h.esrd,0) AS esrd,
  COALESCE(h.transplant,0) AS transplant,
  COALESCE(h.cirrhosis,0) AS cirrhosis,
  COALESCE(h.cancer,0) AS cancer,
  COALESCE(h.chf,0) AS chf,
  COALESCE(h.copd,0) AS copd,
  COALESCE(o.obstruction,0) AS obstruction,
  COALESCE(pr.prior_rrt,0) AS prior_rrt,
  CASE WHEN LOWER(p.gender)='female' THEN 1 ELSE 0 END AS female,
  SAFE_DIVIDE(cr.creat_max_24h, cr.baseline_creat) AS creat_ratio,
  CASE WHEN LOWER(p.gender)='female' THEN
    142 * POWER(LEAST(SAFE_DIVIDE(cr.baseline_creat,0.7),1), -0.241)
        * POWER(GREATEST(SAFE_DIVIDE(cr.baseline_creat,0.7),1), -1.2)
        * POWER(0.9938, p.age_num) * 1.012
  ELSE
    142 * POWER(LEAST(SAFE_DIVIDE(cr.baseline_creat,0.9),1), -0.302)
        * POWER(GREATEST(SAFE_DIVIDE(cr.baseline_creat,0.9),1), -1.2)
        * POWER(0.9938, p.age_num)
  END AS egfr,
  CASE WHEN u.uo_24h IS NOT NULL AND p.weight_kg > 0 THEN u.uo_24h/(p.weight_kg*24) END AS uo_rate_24h,
  CASE WHEN u.uo_12h IS NOT NULL AND p.weight_kg > 0 THEN u.uo_12h/(p.weight_kg*12) END AS uo_rate_12h,
  CASE WHEN cr.creat_max_24h >= 3*cr.baseline_creat
        OR (cr.creat_max_24h >= 4.0 AND cr.creat_max_24h-cr.baseline_creat >= 0.3) THEN 1 ELSE 0 END AS aki3_creat,
  CASE WHEN (u.uo_24h IS NOT NULL AND p.weight_kg > 0 AND u.uo_24h/(p.weight_kg*24) < 0.3)
        OR (u.uo_12h IS NOT NULL AND u.uo_12h < 100) THEN 1 ELSE 0 END AS aki3_uo,
  CASE WHEN cr.creat_max_24h >= 2*cr.baseline_creat THEN 1 ELSE 0 END AS aki2_creat,
  CASE WHEN u.uo_12h IS NOT NULL AND p.weight_kg > 0 AND u.uo_12h/(p.weight_kg*12) < 0.5 THEN 1 ELSE 0 END AS aki2_uo,
  CASE WHEN cr.creat_max_24h >= 3*cr.baseline_creat
        OR cr.creat_max_24h >= 4.0
        OR (u.uo_24h IS NOT NULL AND p.weight_kg > 0 AND u.uo_24h/(p.weight_kg*24) < 0.3)
        OR (u.uo_12h IS NOT NULL AND u.uo_12h < 100) THEN 1 ELSE 0 END AS rifle_f,
  CASE WHEN COALESCE(lb.k_max,0) > 6.5 OR COALESCE(lb.ph_min,99) < 7.15 THEN 1 ELSE 0 END AS urgent_rrt,
  CASE WHEN COALESCE(lb.k_max,0) > 5.5 OR COALESCE(lb.bicarb_min,99) < 15 THEN 1 ELSE 0 END AS starrt_urgent,
  CASE WHEN COALESCE(h.esrd,0)=1 OR COALESCE(pr.prior_rrt,0)=1 OR COALESCE(h.transplant,0)=1 OR COALESCE(CASE WHEN p.hospitaldischargestatus='Expired' AND p.hospitaldischargeoffset <= 1440 THEN 1 ELSE 0 END,0)=1 THEN 1 ELSE 0 END AS common_excl,
  CASE WHEN COALESCE(o.obstruction,0)=1 THEN 1 ELSE 0 END AS obstruction_excl
FROM crrt c
JOIN pat p USING(patientunitstayid)
LEFT JOIN creat cr USING(patientunitstayid)
LEFT JOIN uo u USING(patientunitstayid)
LEFT JOIN labs lb USING(patientunitstayid)
LEFT JOIN vaso v USING(patientunitstayid)
LEFT JOIN mv m USING(patientunitstayid)
LEFT JOIN sepsis s USING(patientunitstayid)
LEFT JOIN hx h USING(patientunitstayid)
LEFT JOIN obstruction o USING(patientunitstayid)
LEFT JOIN prior_rrt pr USING(patientunitstayid)
"""
print("creating table...", flush=True)
job=client.query(sql)
job.result()
print("done", job.total_bytes_processed, flush=True)