import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation"); D=BASE/"data"
cases=pd.read_csv(D/"sicdb_cases.csv")
cases=cases[cases.HoursOfCRRT.fillna(0)>0].copy()
cases=cases[pd.to_numeric(cases.AgeOnAdmission,errors="coerce")>=18].copy()
cases["weight_kg"]=pd.to_numeric(cases.WeightOnAdmission,errors="coerce")
cases.loc[cases.weight_kg>300,"weight_kg"]=cases.loc[cases.weight_kg>300,"weight_kg"]/1000
cases["age"]=pd.to_numeric(cases.AgeOnAdmission,errors="coerce")
cases["female"]=(cases.sex=="female").astype(int)
cases["gender"]=cases.sex
cases["death_24h"]=cases.death_24h.fillna(0).astype(int)
# labs at ICU admission: baseline -7d..0, max/min 0..24h
labs=pd.read_csv(D/"sicdb_labs.csv")
labs=labs[labs.CaseID.isin(cases.CaseID)].copy()
labs["value"]=pd.to_numeric(labs.value,errors="coerce")
def agg(name,fn,a,b,col):
    x=labs[(labs.lab==name)&(labs.Offset>=a)&(labs.Offset<=b)]
    return x.groupby("CaseID").value.agg(fn).rename(col)
for col,fn,a,b,name in [("baseline_creat","min",-604800,0,"creatinine"),("creat_max_24h","max",0,86400,"creatinine"),("creat_min_24h","min",0,86400,"creatinine"),("k_max","max",0,86400,"potassium"),("ph_min","min",0,86400,"ph"),("bicarb_min","min",0,86400,"bicarbonate")]:
    cases=cases.merge(agg(name,fn,a,b,col),on="CaseID",how="left")
# signals at ICU admission
sig=pd.read_parquet(D/"sicdb_float_sig.parquet")
sig=sig[sig.CaseID.isin(cases.CaseID)]
uo=sig[(sig.DataID.isin([725,2305]))&(sig.Offset>=0)&(sig.Offset<=86400)]
for hrs,col in [(6,"uo_6h"),(12,"uo_12h"),(24,"uo_24h")]:
    x=uo[uo.Offset<=hrs*3600].groupby("CaseID").Val.sum().rename(col)
    cases=cases.merge(x,on="CaseID",how="left")
mv=sig[(sig.DataID.isin([711,712,713,715,717,719,727,2019,2020,2021,3035]))&(sig.Val>0)&(sig.Offset>=0)&(sig.Offset<=86400)]
cases=cases.merge(mv.groupby("CaseID").size().gt(0).astype(int).rename("mv"),on="CaseID",how="left")
cases["mv"]=cases.mv.fillna(0).astype(int)
# vaso any first 24h
med=pd.read_csv(D/"sicdb_vaso.csv"); med=med[med.CaseID.isin(cases.CaseID)]
med=med[(med.Offset<=86400)&(med.OffsetDrugEnd>=0)]
cases=cases.merge(med.groupby("CaseID").size().gt(0).astype(int).rename("vaso"),on="CaseID",how="left")
cases["vaso"]=cases.vaso.fillna(0).astype(int)
# map disease flags
for src,dst in [("sepsis_adm","sepsis"),("esrd_icd","esrd"),("transplant_icd","transplant"),("cirrhosis_icd","cirrhosis"),("cancer_icd","cancer"),("obstruction_icd","obstruction")]:
    cases[dst]=cases[src].fillna(0).astype(int)
cases["prior_rrt"]=0
cases["gn_vasculitis"]=0
cases["chf"]=0
# reuse add_flags
src=(BASE/"scripts"/"landmark_flags_mimic.py").read_text(encoding="utf-8")
exec(src.split("df=pd.read_csv")[0])
cases=add_flags(cases)
cases.to_csv(D/"sicdb_icu_landmark_flags.csv",index=False)
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
s=cases[cols].sum(axis=1)
print("n",len(cases))
for c in cols: print(c,int(cases[c].sum()),round(100*cases[c].mean(),1))
print("any5",int((s>0).sum()),round(100*(s>0).mean(),1),"all5",int((s==5).sum()),round(100*(s==5).mean(),1))