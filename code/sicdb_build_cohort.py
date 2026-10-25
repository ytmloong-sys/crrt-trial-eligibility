import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
D=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")/"data"
cases=pd.read_csv(D/"sicdb_cases.csv")
cases=cases[cases.HoursOfCRRT.fillna(0)>0].copy()
cases=cases[pd.to_numeric(cases.AgeOnAdmission,errors="coerce")>=18].copy()
cases["weight_kg"]=pd.to_numeric(cases.WeightOnAdmission,errors="coerce")
cases.loc[cases.weight_kg>300,"weight_kg"]=cases.loc[cases.weight_kg>300,"weight_kg"]/1000
cases["female"]=(cases.sex=="female").astype(int)
print("cases",len(cases))

sig=pd.read_parquet(D/"sicdb_float_sig.parquet")
crrt_ids=[723,730,731,732,2022,3071]
c=sig[sig.DataID.isin(crrt_ids) & (sig.Val>0)]
start=c.groupby("CaseID").Offset.min().rename("crrt_start")
stop=c.groupby("CaseID").Offset.max().rename("crrt_stop")
cases=cases.merge(start,on="CaseID",how="left").merge(stop,on="CaseID",how="left")
cases["crrt_start"]=cases.crrt_start.fillna(0)
cases["time_zero"]=(cases.crrt_start-21600).clip(lower=0)
print("crrt signal cases",cases.crrt_start.notna().sum(),"median start h",round(cases.crrt_start.median()/3600,2))
t0=cases.set_index("CaseID").time_zero

# signals relative to time zero
sig=sig[sig.CaseID.isin(cases.CaseID)].copy()
sig["rel"]=sig.Offset-sig.CaseID.map(t0)

uo=sig[sig.DataID.isin([725,2305]) & (sig.rel>=-86400) & (sig.rel<=0)]
uo_agg=uo.groupby("CaseID").agg(uo_24h=("Val","sum"),uo_rows=("Val","size"))
cases=cases.merge(uo_agg,on="CaseID",how="left")
# 12h/6h
for hrs in [6,12]:
    x=uo[uo.rel>=-hrs*3600].groupby("CaseID").Val.sum().rename(f"uo_{hrs}h")
    cases=cases.merge(x,on="CaseID",how="left")

mv_ids=[711,712,713,715,717,719,727,2019,2020,2021,3035]
mv=sig[sig.DataID.isin(mv_ids) & (sig.Val>0) & (sig.rel>=-21600) & (sig.rel<=0)]
mv_agg=mv.groupby("CaseID").size().gt(0).astype(int).rename("mv")
cases=cases.merge(mv_agg,on="CaseID",how="left")
cases["mv"]=cases.mv.fillna(0).astype(int)

# labs
labs=pd.read_csv(D/"sicdb_labs.csv")
labs=labs[labs.CaseID.isin(cases.CaseID)].copy()
labs["rel"]=labs.Offset-labs.CaseID.map(t0)
def lab_agg(name, fn, win, col):
    x=labs[(labs.lab==name)&(labs.rel>=win)&(labs.rel<=0)]
    return x.groupby("CaseID").value.agg(fn).rename(col)
cases=cases.merge(lab_agg("creatinine","min",-604800,"baseline_creat"),on="CaseID",how="left")
cases=cases.merge(lab_agg("creatinine","max",-86400,"creat_max_24h"),on="CaseID",how="left")
cases=cases.merge(lab_agg("creatinine","min",-86400,"creat_min_24h"),on="CaseID",how="left")
# closest creatinine to t0
x=labs[labs.lab=="creatinine"].copy(); x["absrel"]=x.rel.abs()
closest=x.sort_values("absrel").groupby("CaseID").first()["value"].rename("creat_t0")
cases=cases.merge(closest,on="CaseID",how="left")
cases=cases.merge(lab_agg("potassium","max",-86400,"k_max"),on="CaseID",how="left")
cases=cases.merge(lab_agg("ph","min",-86400,"ph_min"),on="CaseID",how="left")
cases=cases.merge(lab_agg("bicarbonate","min",-86400,"bicarb_min"),on="CaseID",how="left")
cases=cases.merge(lab_agg("urea","max",-86400,"urea_max"),on="CaseID",how="left")

# vaso active at t0
med=pd.read_csv(D/"sicdb_vaso.csv"); med=med[med.CaseID.isin(cases.CaseID)].copy()
med["t0"]=med.CaseID.map(t0)
med["active"]=((med.Offset<=med.t0)&(med.OffsetDrugEnd>=med.t0)).astype(int)
cases=cases.merge(med.groupby("CaseID").active.max().rename("vaso"),on="CaseID",how="left")
cases["vaso"]=cases.vaso.fillna(0).astype(int)

# derived
cases["creat_ratio"]=cases.creat_max_24h/cases.baseline_creat
cases["sepsis"]=cases.sepsis_adm.fillna(0).astype(int)
cases["ckd_history"]=cases.precondition_renal.fillna(0).astype(int)
cases["esrd"]=cases.esrd_icd.fillna(0).astype(int)
cases["transplant"]=cases.transplant_icd.fillna(0).astype(int)
cases["cirrhosis"]=cases.cirrhosis_icd.fillna(0).astype(int)
cases["cancer"]=cases.cancer_icd.fillna(0).astype(int)
cases["obstruction"]=cases.obstruction_icd.fillna(0).astype(int)

def egfr(scr,age,female):
    if pd.isna(scr) or pd.isna(age) or scr<=0: return np.nan
    k=0.7 if female else 0.9; a=-0.241 if female else -0.302
    return 142*min(scr/k,1)**a*max(scr/k,1)**-1.2*0.9938**age*(1.012 if female else 1)
cases["egfr"]=[egfr(s,a,f) for s,a,f in zip(cases.baseline_creat,cases.AgeOnAdmission,cases.female)]
cases["severe_ckd_20"]=(cases.egfr<20).fillna(False).astype(int)
cases["severe_ckd_30"]=(cases.egfr<30).fillna(False).astype(int)

cases["uo_rate_24h"]=cases.uo_24h/(cases.weight_kg*24)
cases["uo_rate_12h"]=cases.uo_12h/(cases.weight_kg*12)
cases["aki3_creat"]=((cases.creat_ratio>=3)|((cases.creat_max_24h>=4)&((cases.creat_max_24h-cases.baseline_creat)>=0.3))).fillna(False).astype(int)
cases["aki3_uo"]=((cases.uo_rate_24h<0.3)|(cases.uo_12h<100)).fillna(False).astype(int)
cases["aki3"]=((cases.aki3_creat==1)|(cases.aki3_uo==1)|(cases.kdigo_aki_168==3)).astype(int)
cases["aki2_creat"]=(cases.creat_ratio>=2).fillna(False).astype(int)
cases["aki2_uo"]=(cases.uo_rate_12h<0.5).fillna(False).astype(int)
cases["aki2"]=((cases.aki2_creat==1)|(cases.aki2_uo==1)).astype(int)
cases["rifle_f"]=((cases.creat_ratio>=3)|(cases.creat_max_24h>=4)|(cases.uo_rate_24h<0.3)|(cases.uo_12h<100)).fillna(False).astype(int)
cases["septic_shock"]=((cases.sepsis==1)&(cases.vaso==1)).astype(int)
cases["urgent_rrt"]=((cases.k_max>6.5)|(cases.ph_min<7.15)).fillna(False).astype(int)
cases["starrt_urgent"]=((cases.k_max>5.5)|(cases.bicarb_min<15)).fillna(False).astype(int)
cases["common_excl"]=((cases.esrd==1)|(cases.prior_rrt==1)|(cases.transplant==1)|(cases.death_24h==1)).astype(int)
cases["obstruction_excl"]=cases.obstruction.fillna(0).astype(int)

# flags
cases["starrt_eligible"]=((cases.AgeOnAdmission>=18)&
    (((cases.female==1)&(cases.creat_max_24h>=100/88.4))|((cases.female==0)&(cases.creat_max_24h>=130/88.4)))&
    ((cases.creat_ratio>=2)|((cases.creat_max_24h>=354/88.4)&((cases.creat_max_24h-cases.baseline_creat)>=27/88.4))|((cases.uo_12h<cases.weight_kg*6)))&
    ~((cases.common_excl==1)|(cases.obstruction_excl==1)|(cases.severe_ckd_20==1)|(cases.starrt_urgent==1)|(cases.urgent_rrt==1))).astype(int)
cases["akiki_eligible"]=((cases.AgeOnAdmission>=18)&(cases.rifle_f==1)&((cases.mv==1)|(cases.vaso==1))&
    ~((cases.common_excl==1)|(cases.obstruction_excl==1)|(cases.severe_ckd_30==1)|(cases.cirrhosis==1)|(cases.urgent_rrt==1))).astype(int)
cases["akiki2_eligible"]=((cases.AgeOnAdmission>=18)&(cases.aki3==1)&((cases.mv==1)|(cases.vaso==1))&
    ~((cases.common_excl==1)|(cases.obstruction_excl==1)|(cases.severe_ckd_30==1)|(cases.cirrhosis==1)|(cases.urgent_rrt==1))).astype(int)
cases["ideal_eligible"]=((cases.AgeOnAdmission>=18)&(cases.septic_shock==1)&(cases.rifle_f==1)&
    ~((cases.esrd==1)|(cases.prior_rrt==1)|(cases.transplant==1)|(cases.obstruction_excl==1)|(cases.urgent_rrt==1)|(cases.death_24h==1)|(cases.cirrhosis==1)|(cases.cancer==1))).astype(int)
cases["elain_eligible_partial"]=((cases.AgeOnAdmission>=18)&(cases.AgeOnAdmission<=90)&(cases.aki2==1)&((cases.sepsis==1)|(cases.vaso==1))&
    ~((cases.common_excl==1)|(cases.obstruction_excl==1)|(cases.severe_ckd_30==1)|(cases.cirrhosis==1)|(cases.cancer==1))).astype(int)
cases.to_csv(D/"sicdb_crrt_cohort.csv",index=False)
print("cohort",cases.shape)
for c in ["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]:
    print(c,int(cases[c].sum()),round(100*cases[c].mean(),1))
s=cases[["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]].sum(axis=1)
print("any5",int((s>0).sum()),round(100*(s>0).mean(),1),"all5",int((s==5).sum()),round(100*(s==5).mean(),1))
