import os
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
from google.cloud import bigquery
c=bigquery.Client(project="deresuscitation-tte"); bt=chr(96)
q=f"""
CREATE OR REPLACE TABLE {bt}deresuscitation-tte.mimic_work.eicu_icu_landmark_v2{bt} AS
WITH base AS (SELECT * FROM {bt}deresuscitation-tte.mimic_work.eicu_icu_landmark{bt}),
prior AS (
 SELECT patientunitstayid, MAX(IF(LOWER(treatmentstring) LIKE 'renal|dialysis%' AND LOWER(treatmentstring) NOT LIKE '%catheter%' AND LOWER(treatmentstring) NOT LIKE '%insertion%' AND treatmentoffset < 0,1,0)) new_prior
 FROM {bt}physionet-data.eicu_crd.treatment{bt} GROUP BY 1),
mv AS (
 SELECT patientunitstayid, MAX(IF((LOWER(airwaytype) LIKE '%ett%' OR LOWER(airwaytype) LIKE '%trach%' OR LOWER(airwaytype) LIKE '%endotracheal%') AND ventstartoffset <= 1440 AND (ventendoffset >= 0 OR ventendoffset IS NULL),1,0)) new_mv
 FROM {bt}physionet-data.eicu_crd.respiratorycare{bt} GROUP BY 1)
SELECT b.* EXCEPT(prior_rrt,mv),
 COALESCE(p.new_prior,0) AS prior_rrt,
 GREATEST(COALESCE(b.mv,0),COALESCE(m.new_mv,0)) AS mv
FROM base b LEFT JOIN prior p USING(patientunitstayid) LEFT JOIN mv m USING(patientunitstayid)
"""
c.query(q).result(); print("table built")
