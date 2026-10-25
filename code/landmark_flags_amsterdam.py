import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation"); D=BASE/"data"
base=pd.read_csv(D/"amsterdam_crrt_base.csv")
base=base.drop(columns=["mv","vaso"],errors="ignore")
# ICU admission = 0; use existing demographics
num=pd.read_parquet(D/"amsterdam_numeric_filtered.parquet")
num=num[num.admissionid.isin(base.admissionid)].copy()
num["value"]=pd.to_numeric(num.value,errors="coerce")
def labs(items,a,b):
    x=num[num.item.isin(items)&(num.measuredat>=a)&(num.measuredat<=b)]
    return x
creat=labs(["Kreatinine (bloed)","Kreatinine","Kreatinine (overig)","A_Serum_Kreatinine"],-7*86400000,0)
creat["value"]=np.where(creat.unit.astype(str).str.contains("µmol|umol",case=False,na=False),creat.value/88.4,creat.value)
base=base.merge(creat.groupby("admissionid").value.min().rename("baseline_creat"),on="admissionid",how="left")
c24=labs(["Kreatinine (bloed)","Kreatinine","Kreatinine (overig)","A_Serum_Kreatinine"],0,86400000).copy()
c24["value"]=np.where(c24.unit.astype(str).str.contains("µmol|umol",case=False,na=False),c24.value/88.4,c24.value)
base=base.merge(c24.groupby("admissionid").value.max().rename("creat_max_24h"),on="admissionid",how="left")
base=base.merge(c24.groupby("admissionid").value.min().rename("creat_min_24h"),on="admissionid",how="left")
k=labs(["Kalium (bloed)","Kalium","Kalium Astrup"],0,86400000)
base=base.merge(k.groupby("admissionid").value.max().rename("k_max"),on="admissionid",how="left")
ph=labs(["pH (bloed)","PH"],0,86400000)
base=base.merge(ph.groupby("admissionid").value.min().rename("ph_min"),on="admissionid",how="left")
uo=num[(num.item=="UrineCAD")&(num.measuredat>=0)&(num.measuredat<=86400000)].copy()
for hrs,col in [(6,"uo_6h"),(12,"uo_12h"),(24,"uo_24h")]:
    x=uo[uo.measuredat<=hrs*3600000].groupby("admissionid").value.sum().rename(col)
    base=base.merge(x,on="admissionid",how="left")
base["uo_rows"]=base.admissionid.map(uo.groupby("admissionid").size()).fillna(0).astype(int)
# vaso any first 24h
vaso=pd.read_csv(D/"amsterdam_vaso_raw.csv")
vaso=vaso[vaso.admissionid.isin(base.admissionid)]
vaso=vaso[(vaso.start<=86400000)&(vaso.stop>=0)]
base=base.merge(vaso.groupby("admissionid").size().gt(0).astype(int).rename("vaso"),on="admissionid",how="left")
base["vaso"]=base.vaso.fillna(0).astype(int)
# MV any Beademen interval first 24h
proc=pd.read_csv(r"D:\ICU数据库\Amsterdam\processitems.csv",encoding="latin-1")
mv=proc[proc.item.str.lower().str.contains("beadem",na=False)].copy()
mv["start"]=mv.start/1000; mv["stop"]=mv.stop/1000  # ms -> seconds? process start ms; use ms
# use ms: start/stop already ms, first 24h = 86400000
mv2=proc[proc.item.str.lower().str.contains("beadem",na=False)]
mv2=mv2[(mv2.start<=86400000)&(mv2.stop>=0)]
base=base.merge(mv2.groupby("admissionid").size().gt(0).astype(int).rename("mv"),on="admissionid",how="left")
base["mv"]=base.mv.fillna(0).astype(int)
sep=pd.read_csv(D/"amsterdam_sepsis_raw.csv")
sep=sep[(sep.item=="Opname Sepsis")&(sep.value=="Ja")]
base["sepsis"]=base.admissionid.isin(set(sep.admissionid)).astype(int)
for c in ["esrd","prior_rrt","transplant","cirrhosis","cancer","obstruction","death_24h","chf"]:
    base[c]=0
base["gn_vasculitis"]=0
base["bicarb_min"]=np.nan
# generic flags
src=(BASE/"scripts"/"landmark_flags_mimic.py").read_text(encoding="utf-8")
exec(src.split("df=pd.read_csv")[0])
base=add_flags(base)
base.to_csv(D/"amsterdam_icu_landmark_flags.csv",index=False)
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
s=base[cols].sum(axis=1)
print("n",len(base))
for c in cols: print(c,int(base[c].sum()),round(100*base[c].mean(),1))
print("any5",int((s>0).sum()),round(100*(s>0).mean(),1),"all5",int((s==5).sum()),round(100*(s==5).mean(),1))