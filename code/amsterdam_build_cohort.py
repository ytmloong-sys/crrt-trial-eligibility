import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
D=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")/"data"
base=pd.read_csv(D/"amsterdam_crrt_base.csv")
base["t0_ms"]=base.time_zero_h*3_600_000
print("base",base.shape)

num=pd.read_parquet(D/"amsterdam_numeric_filtered.parquet")
num["value"]=pd.to_numeric(num["value"],errors="coerce")
num=num[num.admissionid.isin(base.admissionid)].copy()
num["rel_h"]=(num.measuredat-num.admissionid.map(base.set_index("admissionid").t0_ms))/3_600_000
print("num",num.shape)

def lab_items(names):
    return num[num.item.isin(names)].copy()
creat=lab_items(["Kreatinine (bloed)","Kreatinine","Kreatinine (overig)","A_Serum_Kreatinine"])
creat["value"]=np.where(creat.unit.astype(str).str.contains("µmol|umol",case=False,na=False),creat.value/88.4,creat.value)
creat=creat[(creat.rel_h>=-168)&(creat.rel_h<=0)]
base=base.merge(creat.groupby("admissionid").value.min().rename("baseline_creat"),on="admissionid",how="left")
c24=creat[(creat.rel_h>=-24)]
base=base.merge(c24.groupby("admissionid").value.max().rename("creat_max_24h"),on="admissionid",how="left")
base=base.merge(c24.groupby("admissionid").value.min().rename("creat_min_24h"),on="admissionid",how="left")
c24["absrel"]=c24.rel_h.abs()
base=base.merge(c24.sort_values("absrel").groupby("admissionid").first().value.rename("creat_t0"),on="admissionid",how="left")

k=lab_items(["Kalium (bloed)","Kalium","Kalium Astrup"])
k=k[(k.rel_h>=-24)&(k.rel_h<=0)]
base=base.merge(k.groupby("admissionid").value.max().rename("k_max"),on="admissionid",how="left")
ph=lab_items(["pH (bloed)","PH"])
ph=ph[(ph.rel_h>=-24)&(ph.rel_h<=0)]
base=base.merge(ph.groupby("admissionid").value.min().rename("ph_min"),on="admissionid",how="left")

uo=num[(num.item=="UrineCAD")].copy()
for hrs in [6,12,24]:
    x=uo[uo.rel_h>=-hrs].groupby("admissionid").value.sum().rename(f"uo_{hrs}h")
    base=base.merge(x,on="admissionid",how="left")
base["uo_rows"]=base.admissionid.map(uo.groupby("admissionid").size()).fillna(0).astype(int)

vaso=pd.read_csv(D/"amsterdam_vaso_raw.csv",encoding="utf-8")
vaso=vaso[vaso.admissionid.isin(base.admissionid)].copy()
vaso["t0"]=vaso.admissionid.map(base.set_index("admissionid").t0_ms)
vaso["active"]=((vaso.start<=vaso.t0)&(vaso.stop>=vaso.t0)).astype(int)
base=base.merge(vaso.groupby("admissionid").active.max().rename("vaso"),on="admissionid",how="left")
base["vaso"]=base.vaso.fillna(0).astype(int)

sep=pd.read_csv(D/"amsterdam_sepsis_raw.csv",encoding="utf-8")
sep=sep[(sep.item=="Opname Sepsis")&(sep.value=="Ja")]
base["sepsis"]=base.admissionid.isin(set(sep.admissionid)).astype(int)

base["creat_ratio"]=base.creat_max_24h/base.baseline_creat
base["uo_rate_24h"]=base.uo_24h/(base.weight_kg*24)
base["uo_rate_12h"]=base.uo_12h/(base.weight_kg*12)
base["aki3_creat"]=((base.creat_ratio>=3)|((base.creat_max_24h>=4)&((base.creat_max_24h-base.baseline_creat)>=0.3))).fillna(False).astype(int)
base["aki3_uo"]=((base.uo_rate_24h<0.3)|(base.uo_12h<100)).fillna(False).astype(int)
base["aki3"]=((base.aki3_creat==1)|(base.aki3_uo==1)).astype(int)
base["aki2_creat"]=(base.creat_ratio>=2).fillna(False).astype(int)
base["aki2_uo"]=(base.uo_rate_12h<0.5).fillna(False).astype(int)
base["aki2"]=((base.aki2_creat==1)|(base.aki2_uo==1)).astype(int)
base["rifle_f"]=((base.creat_ratio>=3)|(base.creat_max_24h>=4)|(base.uo_rate_24h<0.3)|(base.uo_12h<100)).fillna(False).astype(int)
base["septic_shock"]=((base.sepsis==1)&(base.vaso==1)).astype(int)
base["urgent_rrt"]=((base.k_max>6.5)|(base.ph_min<7.15)).fillna(False).astype(int)
base["starrt_urgent"]=(base.k_max>5.5).fillna(False).astype(int)
# unavailable exclusions
for c in ["esrd","prior_rrt","transplant","cirrhosis","cancer","obstruction","death_24h"]:
    base[c]=0
base["common_excl"]=0
base["obstruction_excl"]=0
base["severe_ckd_20"]=0
base["severe_ckd_30"]=0
base["starrt_eligible"]=((base.age>=18)&
    (((base.female==1)&(base.creat_max_24h>=100/88.4))|((base.female==0)&(base.creat_max_24h>=130/88.4)))&
    ((base.creat_ratio>=2)|((base.creat_max_24h>=354/88.4)&((base.creat_max_24h-base.baseline_creat)>=27/88.4))|((base.uo_12h<base.weight_kg*6)))&
    ~((base.starrt_urgent==1)|(base.urgent_rrt==1))).astype(int)
base["akiki_eligible"]=((base.age>=18)&(base.rifle_f==1)&((base.mv==1)|(base.vaso==1))&
    ~(base.urgent_rrt==1)).astype(int)
base["akiki2_eligible"]=((base.age>=18)&(base.aki3==1)&((base.mv==1)|(base.vaso==1))&
    ~(base.urgent_rrt==1)).astype(int)
base["ideal_eligible"]=((base.age>=18)&(base.septic_shock==1)&(base.rifle_f==1)&
    ~(base.urgent_rrt==1)).astype(int)
base["elain_eligible_partial"]=((base.age>=18)&(base.age<=90)&(base.aki2==1)&((base.sepsis==1)|(base.vaso==1))).astype(int)
base.to_csv(D/"amsterdam_crrt_cohort.csv",index=False)
print("cohort",base.shape)
for c in ["baseline_creat","creat_max_24h","uo_24h","k_max","ph_min"]:
    print(c,"available",int(base[c].notna().sum()))
for c in ["sepsis","mv","vaso","aki3","rifle_f","aki2","death_hosp"]:
    print(c,int(base[c].sum()),round(100*base[c].mean(),1))
for c in ["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]:
    print(c,int(base[c].sum()),round(100*base[c].mean(),1))
s=base[["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]].sum(axis=1)
print("any5",int((s>0).sum()),round(100*(s>0).mean(),1),"all5",int((s==5).sum()),round(100*(s==5).mean(),1))