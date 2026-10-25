import os, pandas as pd, numpy as np, sys
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
from google.cloud import bigquery
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
c=bigquery.Client(project="deresuscitation-tte"); bt=chr(96)
df=c.query(f"SELECT * FROM {bt}deresuscitation-tte.mimic_work.eicu_icu_landmark{bt}").result().to_dataframe()
df=df.rename(columns={"vaso_icu":"vaso"})
if "age_num" in df.columns and "age" not in df.columns: df["age"]=df["age_num"]
# reuse the add_flags function from the MIMIC script
src=(BASE/"scripts"/"landmark_flags_mimic.py").read_text(encoding="utf-8")
exec(src.split("df=pd.read_csv")[0])
df=add_flags(df)
df.to_csv(BASE/"data"/"eicu_icu_landmark_flags.csv",index=False)
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
s=df[cols].sum(axis=1)
print("n",len(df))
for col in cols: print(col,int(df[col].sum()),round(100*df[col].mean(),1))
print("any5",int((s>0).sum()),round(100*(s>0).mean(),1),"all5",int((s==5).sum()),round(100*(s==5).mean(),1))