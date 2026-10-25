import os
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
from google.cloud import bigquery
client=bigquery.Client(project="deresuscitation-tte"); BT=chr(96); T="deresuscitation-tte.mimic_work.eicu_crrt_cohort"
sql=f"""
CREATE OR REPLACE TABLE {BT}{T}{BT} AS
WITH base AS (
  SELECT *,
    CASE WHEN aki3_creat=1 OR aki3_uo=1 THEN 1 ELSE 0 END AS aki3,
    CASE WHEN aki2_creat=1 OR aki2_uo=1 THEN 1 ELSE 0 END AS aki2,
    CASE WHEN sepsis=1 AND vaso=1 THEN 1 ELSE 0 END AS septic_shock,
    CASE WHEN egfr < 20 THEN 1 ELSE 0 END AS severe_ckd_20,
    CASE WHEN egfr < 30 THEN 1 ELSE 0 END AS severe_ckd_30
  FROM {BT}{T}{BT}
)
SELECT *,
  CASE WHEN age_num >= 18
    AND ((female=1 AND creat_max_24h >= 100/88.4) OR (female=0 AND creat_max_24h >= 130/88.4))
    AND (creat_ratio >= 2 OR (creat_max_24h >= 354/88.4 AND creat_max_24h-baseline_creat >= 27/88.4)
         OR (uo_12h IS NOT NULL AND weight_kg > 0 AND uo_12h < 6.0*weight_kg))
    AND NOT (common_excl=1 OR obstruction_excl=1 OR severe_ckd_20=1 OR starrt_urgent=1 OR urgent_rrt=1)
    THEN 1 ELSE 0 END AS starrt_eligible,
  CASE WHEN age_num >= 18 AND rifle_f=1 AND (mv=1 OR vaso=1)
    AND NOT (common_excl=1 OR obstruction_excl=1 OR severe_ckd_30=1 OR cirrhosis=1 OR urgent_rrt=1)
    THEN 1 ELSE 0 END AS akiki_eligible,
  CASE WHEN age_num >= 18 AND aki3=1 AND (mv=1 OR vaso=1)
    AND NOT (common_excl=1 OR obstruction_excl=1 OR severe_ckd_30=1 OR cirrhosis=1 OR urgent_rrt=1)
    THEN 1 ELSE 0 END AS akiki2_eligible,
  CASE WHEN age_num >= 18 AND septic_shock=1 AND rifle_f=1
    AND NOT (esrd=1 OR prior_rrt=1 OR transplant=1 OR obstruction_excl=1 OR urgent_rrt=1 OR death_24h=1 OR cirrhosis=1 OR cancer=1)
    THEN 1 ELSE 0 END AS ideal_eligible,
  CASE WHEN age_num >= 18 AND age_num <= 90 AND aki2=1
    AND (sepsis=1 OR vaso=1 OR chf=1)
    AND NOT (common_excl=1 OR obstruction_excl=1 OR severe_ckd_30=1 OR cirrhosis=1 OR cancer=1)
    THEN 1 ELSE 0 END AS elain_eligible_partial
FROM base
"""
print("adding flags...", flush=True)
job=client.query(sql); job.result(); print("done", flush=True)
