import os, pandas as pd, numpy as np, sys
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
from google.cloud import bigquery
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation"); c=bigquery.Client(project="deresuscitation-tte"); bt=chr(96)
df=c.query(f"SELECT * FROM {bt}deresuscitation-tte.mimic_work.eicu_crrt_cohort{bt}").result().to_dataframe()
q=f"""SELECT patientunitstayid, MAX(IF((LOWER(airwaytype) LIKE '%ett%' OR LOWER(airwaytype) LIKE '%trach%' OR LOWER(airwaytype) LIKE '%endotracheal%') AND ventstartoffset <= time_zero+1440 AND (ventendoffset >= time_zero-1440 OR ventendoffset IS NULL),1,0)) new_mv
FROM {bt}physionet-data.eicu_crd.respiratorycare{bt} r JOIN {bt}deresuscitation-tte.mimic_work.eicu_crrt_cohort{bt} c USING(patientunitstayid) GROUP BY 1"""
m=c.query(q).result().to_dataframe(); df=df.merge(m,on="patientunitstayid",how="left")
df["mv"]=np.maximum(df.mv.fillna(0),df.new_mv.fillna(0)).astype(int)
excl=(df.common_excl==1)|(df.obstruction_excl==1)|(df.severe_ckd_30==1)|(df.cirrhosis==1)|(df.urgent_rrt==1)
df["akiki_eligible"]=((df.age_num>=18)&(df.rifle_f==1)&((df.mv==1)|(df.vaso==1))&~excl).astype(int)
df["akiki2_eligible"]=((df.age_num>=18)&(df.aki3==1)&((df.mv==1)|(df.vaso==1))&~excl).astype(int)
df.to_csv(BASE/"data"/"eicu_crrt_cohort_v2.csv",index=False)
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]; s=df[cols].sum(axis=1)
print("n",len(df))
for c in cols: print(c,int(df[c].sum()),round(100*df[c].mean(),1))
print("any5",int((s>0).sum()),round(100*(s>0).mean(),1),"all5",int((s==5).sum()),round(100*(s==5).mean(),1))
