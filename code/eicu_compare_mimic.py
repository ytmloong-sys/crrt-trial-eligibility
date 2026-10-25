import os, math
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
from google.cloud import bigquery
import pandas as pd
from pathlib import Path

BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
client=bigquery.Client(project="deresuscitation-tte"); BT=chr(96); T="deresuscitation-tte.mimic_work.eicu_crrt_cohort"

def wilson(k,n,z=1.96):
    if n==0: return (None,None)
    p=k/n
    den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return (100*(center-half),100*(center+half))

# Export cohort
cohort=client.query(f"SELECT * FROM {BT}{T}{BT}").to_dataframe()
cohort.to_csv(BASE/"data"/"eicu_crrt_cohort.csv", index=False)
print("cohort", cohort.shape)

trials=["STARRT-AKI","AKIKI","AKIKI-2","IDEAL-ICU","ELAIN (partial)"]
cols={"STARRT-AKI":"starrt_eligible","AKIKI":"akiki_eligible","AKIKI-2":"akiki2_eligible","IDEAL-ICU":"ideal_eligible","ELAIN (partial)":"elain_eligible_partial"}

# eICU summaries
def eicu_summary(where):
    d=client.query(f"SELECT * FROM {BT}{T}{BT} WHERE {where}").to_dataframe()
    rows=[]
    for tr in trials:
        c=cols[tr]; k=int(d[c].sum()); n=len(d)
        lo,hi=wilson(k,n)
        rows.append(dict(trial=tr,n=n,eligible=k,pct=round(100*k/n,1),ci_low=round(lo,1),ci_high=round(hi,1)))
    return pd.DataFrame(rows), d

e_all,_=eicu_summary("crrt_within_7d=1")
e_uo,_=eicu_summary("crrt_within_7d=1 AND uo_rows>0")

# MIMIC flags
m=pd.read_csv(BASE/"data"/"trial_variables_with_flags.csv")
def mimic_summary(d):
    rows=[]
    for tr in trials:
        c=cols[tr]; k=int(d[c].sum()); n=len(d); lo,hi=wilson(k,n)
        rows.append(dict(trial=tr,n=n,eligible=k,pct=round(100*k/n,1),ci_low=round(lo,1),ci_high=round(hi,1)))
    return pd.DataFrame(rows)
m_all=mimic_summary(m)
m_uo=mimic_summary(m[m.uo_24h.notna()])

# Merge comparison
out=e_all.rename(columns={"n":"n_eicu_all","eligible":"eicu_all_n","pct":"eicu_all_pct","ci_low":"eicu_all_lo","ci_high":"eicu_all_hi"})
out=out.merge(e_uo.rename(columns={"n":"n_eicu_uo","eligible":"eicu_uo_n","pct":"eicu_uo_pct","ci_low":"eicu_uo_lo","ci_high":"eicu_uo_hi"}),on="trial")
out=out.merge(m_all.rename(columns={"n":"n_mimic_all","eligible":"mimic_all_n","pct":"mimic_all_pct","ci_low":"mimic_all_lo","ci_high":"mimic_all_hi"}),on="trial")
out=out.merge(m_uo.rename(columns={"n":"n_mimic_uo","eligible":"mimic_uo_n","pct":"mimic_uo_pct","ci_low":"mimic_uo_lo","ci_high":"mimic_uo_hi"}),on="trial")
out["diff_eicu_all_minus_mimic_all"]=(out["eicu_all_pct"]-out["mimic_all_pct"]).round(1)
out["diff_eicu_uo_minus_mimic_uo"]=(out["eicu_uo_pct"]-out["mimic_uo_pct"]).round(1)
out.to_csv(BASE/"outputs"/"eicu_trial_comparison.csv", index=False)
print(out.to_string(index=False))

# Any/all
def any_all(d, prefix):
    s=d[list(cols.values())].sum(axis=1)
    s4=d[list(cols.values())[:4]].sum(axis=1)
    return {
        f"{prefix}_n":len(d),
        f"{prefix}_any5":int((s>0).sum()), f"{prefix}_any5_pct":round(100*(s>0).mean(),1),
        f"{prefix}_all5":int((s==5).sum()), f"{prefix}_all5_pct":round(100*(s==5).mean(),1),
        f"{prefix}_any4":int((s4>0).sum()), f"{prefix}_any4_pct":round(100*(s4>0).mean(),1),
        f"{prefix}_all4":int((s4==4).sum()), f"{prefix}_all4_pct":round(100*(s4==4).mean(),1),
    }
summary={}
e_all_raw=cohort[cohort["crrt_within_7d"]==1].copy()
e_uo_raw=cohort[(cohort["crrt_within_7d"]==1)&(cohort["uo_rows"]>0)].copy()
summary.update(any_all(e_all_raw,"eicu_all"))
summary.update(any_all(e_uo_raw,"eicu_uo"))
summary.update(any_all(m,"mimic_all"))
summary.update(any_all(m[m.uo_24h.notna()],"mimic_uo"))
pd.Series(summary).to_csv(BASE/"outputs"/"eicu_vs_mimic_any_all.csv")
print("\n", pd.Series(summary).to_string())