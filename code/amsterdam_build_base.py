import pandas as pd, numpy as np, sys
sys.stdout.reconfigure(encoding="utf-8")
p=r"D:\ICU数据库\Amsterdam"
adm=pd.read_csv(p+r"\admissions.csv",encoding="latin-1")
proc=pd.read_csv(p+r"\processitems.csv",encoding="latin-1")
cv=proc[proc.item.str.upper().eq("CVVH")].copy()
cv["start_h"]=cv.start/3_600_000
cv["stop_h"]=cv.stop/3_600_000
agg=cv.groupby("admissionid").agg(crrt_start_h=("start_h","min"),crrt_stop_h=("stop_h","max"),cvvh_intervals=("start_h","size")).reset_index()
base=adm.merge(agg,on="admissionid",how="inner")
# age/weight midpoints
def age_mid(x):
    if pd.isna(x): return np.nan
    if x=="80+": return 85
    if x=="18-39": return 28.5
    if "-" in x:
        a,b=x.split("-"); return (float(a)+float(b)+1)/2
    return np.nan
def wt_mid(x):
    if pd.isna(x): return np.nan
    if x=="59-": return 55
    if x=="110+": return 115
    if "-" in x:
        a,b=x.split("-"); return (float(a)+float(b)+1)/2
    return np.nan
base["age"]=base.agegroup.map(age_mid)
base["weight_kg"]=base.weightgroup.map(wt_mid)
base["female"]=(base.gender=="Vrouw").astype(int)
base["death_hosp"]=(base.destination=="Overleden").astype(int)
base["time_zero_h"]=(base.crrt_start_h-6).clip(lower=0)
# MV intervals active at time zero
mv=proc[proc.item.str.lower().str.contains("beadem",na=False)].copy()
mv["start_h"]=mv.start/3_600_000; mv["stop_h"]=mv.stop/3_600_000
rows=[]
for _,r in base.iterrows():
    x=mv[(mv.admissionid==r.admissionid)&(mv.start_h<=r.time_zero_h)&(mv.stop_h>=r.time_zero_h)]
    rows.append(1 if len(x) else 0)
base["mv"]=rows
base.to_csv(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation\data\amsterdam_crrt_base.csv",index=False)
print(base.shape)
print("CVVH admissions",base.admissionid.nunique(),"age missing",base.age.isna().sum(),"weight missing",base.weight_kg.isna().sum())
print("median age",base.age.median(),"female",base.female.mean(),"death",base.death_hosp.mean(),"MV",base.mv.mean())
print("crrt start h median",base.crrt_start_h.median(),"timezero",base.time_zero_h.median())
