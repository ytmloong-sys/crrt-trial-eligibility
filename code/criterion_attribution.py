import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
D=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")/"data"
cohorts={
"MIMIC":pd.read_csv(D/"trial_variables_with_flags.csv"),
"eICU":pd.read_csv(D/"eicu_crrt_cohort_v2.csv"),
"SICdb":pd.read_csv(D/"sicdb_crrt_cohort.csv"),
"Amsterdam":pd.read_csv(D/"amsterdam_crrt_cohort.csv"),
}
def get(d,c,default=0):
    if c in d.columns:
        return d[c].fillna(default).astype(int)
    return pd.Series(default,index=d.index,dtype=int)
def attribution(d,trial):
    n=len(d); elig=get(d,f"{trial}_eligible").eq(1)
    inelig=~elig
    reasons=pd.Series("Unavailable/other",index=d.index)
    assigned=pd.Series(False,index=d.index)
    def assign(mask,label):
        nonlocal assigned,reasons
        take=inelig & ~assigned & mask.fillna(False)
        reasons[take]=label; assigned |= take
    rrt=(get(d,"esrd")|get(d,"prior_rrt")|get(d,"transplant")|get(d,"death_24h")).astype(bool) if "esrd" in d.columns or "prior_rrt" in d.columns else pd.Series(False,index=d.index)
    # common order
    if trial=="starrt":
        assign(get(d,"severe_ckd_20").eq(1),"CKD/eGFR")
        assign(rrt,"Prior RRT/ESRD/transplant")
        assign((get(d,"urgent_rrt")|get(d,"starrt_urgent")).eq(1),"Urgent RRT indication")
        inc=((get(d,"creat_ratio")>=2)|((get(d,"creat_max_24h")>=4)&((get(d,"creat_max_24h")-get(d,"baseline_creat"))>=0.3))|((get(d,"uo_12h")<get(d,"weight_kg")*6)))
        assign(~inc,"No AKI inclusion")
    elif trial=="akiki":
        assign(get(d,"severe_ckd_30").eq(1),"CKD/eGFR")
        assign(rrt,"Prior RRT/ESRD/transplant")
        assign(get(d,"urgent_rrt").eq(1),"Urgent RRT indication")
        assign(get(d,"rifle_f").eq(0),"No RIFLE failure")
        assign((get(d,"mv")|get(d,"vaso")).eq(0),"No MV/vasopressor")
    elif trial=="akiki2":
        assign(get(d,"severe_ckd_30").eq(1),"CKD/eGFR")
        assign(rrt,"Prior RRT/ESRD/transplant")
        assign(get(d,"urgent_rrt").eq(1),"Urgent RRT indication")
        assign(get(d,"aki3").eq(0),"No AKI stage 3")
        assign((get(d,"mv")|get(d,"vaso")).eq(0),"No MV/vasopressor")
    elif trial=="ideal":
        assign(get(d,"sepsis").eq(0),"No septic shock/sepsis")
        assign(get(d,"rifle_f").eq(0),"No RIFLE failure")
        assign(rrt,"Prior RRT/ESRD/transplant")
        assign(get(d,"urgent_rrt").eq(1),"Urgent RRT indication")
    elif trial=="elain":
        assign(get(d,"severe_ckd_30").eq(1),"CKD/eGFR")
        assign(rrt,"Prior RRT/ESRD/transplant")
        assign(get(d,"aki2").eq(0),"No AKI stage 2")
        assign((get(d,"sepsis")|get(d,"vaso")).eq(0),"No sepsis/vasopressor")
    # other
    assign((get(d,"cirrhosis")|get(d,"cancer")|get(d,"obstruction")).astype(bool),"Other exclusion")
    return reasons[inelig].value_counts()
rows=[]
for co,d in cohorts.items():
    for tr in ["starrt","akiki","akiki2","ideal","elain"]:
        vc=attribution(d,tr); n=int((~get(d,f"{tr}_eligible").eq(1)).sum())
        for reason,count in vc.items():
            rows.append(dict(cohort=co,trial=tr,reason=reason,n_ineligible=n,count=int(count),pct=round(100*count/n,1) if n else 0))
out=pd.DataFrame(rows); out.to_csv(Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")/"outputs"/"criterion_attribution.csv",index=False)
print(out.groupby(["cohort","trial"]).pct.sum().to_string())
print("\nMIMIC/eICU details")
print(out[out.cohort.isin(["MIMIC","eICU"])].to_string(index=False))