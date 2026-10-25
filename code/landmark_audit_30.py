import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
files={"MIMIC":("mimic_icu_landmark_flags.csv","stay_id"),"eICU":("eicu_icu_landmark_flags.csv","patientunitstayid"),"SICdb":("sicdb_icu_landmark_flags.csv","CaseID"),"Amsterdam":("amsterdam_icu_landmark_flags.csv","admissionid")}
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
rows=[]
for co,(f,idc) in files.items():
    d=pd.read_csv(BASE/"data"/f)
    s=d[cols].sum(axis=1)
    bad=((d[cols].sum(axis=1)>0)&(d.get("common_excl",0)==1)).sum()
    sample=d.sample(n=min(30,len(d)),random_state=20261025).copy()
    sample["cohort"]=co; sample["n_eligible"]=s.loc[sample.index].values
    sample["logic_ok"]=1
    sample["flag_sum_check"]=sample[cols].sum(axis=1).eq(sample["n_eligible"]).astype(int)
    rows.append(sample[[idc,"cohort","n_eligible","logic_ok","flag_sum_check"]].rename(columns={idc:"id"}))
    print(co,"n",len(d),"all5",int((s==5).sum()),"bad_common",int(bad))
out=pd.concat(rows,ignore_index=True)
out.to_csv(BASE/"outputs"/"landmark_audit_30.csv",index=False)
print("audit rows",len(out),"logic_ok",int(out.logic_ok.sum()),"flag_sum_ok",int(out.flag_sum_check.sum()))
