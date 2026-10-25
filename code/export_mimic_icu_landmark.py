import os, numpy as np, pandas as pd, sys
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
from google.cloud import bigquery
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
c=bigquery.Client(project="deresuscitation-tte")
bt=chr(96)
q=f"SELECT * FROM {bt}deresuscitation-tte.mimic_work.trial_variables_icu{bt}"
df=c.query(q).result().to_dataframe()
df.to_csv(BASE/"data"/"mimic_icu_landmark.csv",index=False)
print("exported",df.shape)
