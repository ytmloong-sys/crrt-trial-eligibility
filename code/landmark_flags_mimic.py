import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")

def add_flags(df):
    df=df.copy()
    for c in ["age","weight_kg","baseline_creat","creat_max_24h","creat_min_24h","uo_6h","uo_12h","uo_24h","k_max","bicarb_min","ph_min"]:
        if c in df.columns: df[c]=pd.to_numeric(df[c],errors="coerce")
    for c in ["mv","vaso","sepsis","ckd","esrd","transplant","cirrhosis","cancer","chf","copd","obstruction","gn_vasculitis","prior_rrt","death_24h"]:
        if c not in df.columns: df[c]=0
        df[c]=pd.to_numeric(df[c],errors="coerce").fillna(0).astype(int)
    df["female"]=(df["gender"].astype(str).str.upper().str[0]=="F").astype(int)
    df["creat_ratio"]=df["creat_max_24h"]/df["baseline_creat"]
    def egfr(scr,age,female):
        if pd.isna(scr) or pd.isna(age) or scr<=0: return np.nan
        k=0.7 if female else 0.9; a=-0.241 if female else -0.302
        return 142*min(scr/k,1)**a*max(scr/k,1)**-1.2*0.9938**age*(1.012 if female else 1)
    df["egfr"]=[egfr(s,a,f) for s,a,f in zip(df.baseline_creat,df.age,df.female)]
    df["severe_ckd_20"]=(df.egfr<20).fillna(False).astype(int)
    df["severe_ckd_30"]=(df.egfr<30).fillna(False).astype(int)
    df["uo_rate_24h"]=df.uo_24h/(df.weight_kg*24)
    df["uo_rate_12h"]=df.uo_12h/(df.weight_kg*12)
    df["aki3_creat"]=((df.creat_ratio>=3)|((df.creat_max_24h>=4)&((df.creat_max_24h-df.baseline_creat)>=0.3))).fillna(False).astype(int)
    df["aki3_uo"]=((df.uo_rate_24h<0.3)|(df.uo_12h<100)).fillna(False).astype(int)
    df["aki3"]=((df.aki3_creat==1)|(df.aki3_uo==1)).astype(int)
    df["aki2_creat"]=(df.creat_ratio>=2).fillna(False).astype(int)
    df["aki2_uo"]=(df.uo_rate_12h<0.5).fillna(False).astype(int)
    df["aki2"]=((df.aki2_creat==1)|(df.aki2_uo==1)).astype(int)
    df["rifle_f"]=((df.creat_ratio>=3)|(df.creat_max_24h>=4)|(df.uo_rate_24h<0.3)|(df.uo_12h<100)).fillna(False).astype(int)
    df["septic_shock"]=((df.sepsis==1)&(df.vaso==1)).astype(int)
    df["urgent_rrt"]=((df.k_max>6.5)|(df.ph_min<7.15)).fillna(False).astype(int)
    df["starrt_urgent"]=((df.k_max>5.5)|(df.bicarb_min<15)).fillna(False).astype(int)
    df["common_excl"]=((df.esrd==1)|(df.prior_rrt==1)|(df.transplant==1)|(df.death_24h==1)).astype(int)
    df["obstruction_excl"]=((df.obstruction==1)|(df.gn_vasculitis==1)).astype(int)
    df["starrt_eligible"]=((df.age>=18)&
        (((df.female==1)&(df.creat_max_24h>=100/88.4))|((df.female==0)&(df.creat_max_24h>=130/88.4)))&
        ((df.creat_ratio>=2)|((df.creat_max_24h>=354/88.4)&((df.creat_max_24h-df.baseline_creat)>=27/88.4))|(df.uo_12h<6*df.weight_kg))&
        ~((df.common_excl==1)|(df.obstruction_excl==1)|(df.severe_ckd_20==1)|(df.starrt_urgent==1)|(df.urgent_rrt==1))).astype(int)
    df["akiki_eligible"]=((df.age>=18)&(df.rifle_f==1)&((df.mv==1)|(df.vaso==1))&
        ~((df.common_excl==1)|(df.obstruction_excl==1)|(df.severe_ckd_30==1)|(df.cirrhosis==1)|(df.urgent_rrt==1))).astype(int)
    df["akiki2_eligible"]=((df.age>=18)&(df.aki3==1)&((df.mv==1)|(df.vaso==1))&
        ~((df.common_excl==1)|(df.obstruction_excl==1)|(df.severe_ckd_30==1)|(df.cirrhosis==1)|(df.urgent_rrt==1))).astype(int)
    df["ideal_eligible"]=((df.age>=18)&(df.septic_shock==1)&(df.rifle_f==1)&
        ~((df.esrd==1)|(df.prior_rrt==1)|(df.transplant==1)|(df.obstruction_excl==1)|(df.urgent_rrt==1)|(df.death_24h==1)|(df.cirrhosis==1)|(df.cancer==1))).astype(int)
    df["elain_eligible_partial"]=((df.age>=18)&(df.age<=90)&(df.aki2==1)&((df.sepsis==1)|(df.vaso==1)|(df.chf==1))&
        ~((df.common_excl==1)|(df.obstruction_excl==1)|(df.severe_ckd_30==1)|(df.cirrhosis==1)|(df.cancer==1))).astype(int)
    return df

df=pd.read_csv(BASE/"data"/"mimic_icu_landmark.csv")
df=add_flags(df)
df.to_csv(BASE/"data"/"mimic_icu_landmark_flags.csv",index=False)
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
s=df[cols].sum(axis=1)
print("n",len(df))
for c in cols: print(c,int(df[c].sum()),round(100*df[c].mean(),1))
print("any5",int((s>0).sum()),round(100*(s>0).mean(),1),"all5",int((s==5).sum()),round(100*(s==5).mean(),1))
