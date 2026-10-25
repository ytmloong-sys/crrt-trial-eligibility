import pandas as pd, numpy as np, math, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
rows=[]
for name,p in [("MIMIC","trial_variables_with_flags.csv"),("eICU","eicu_crrt_cohort.csv"),("SICdb","sicdb_crrt_cohort.csv"),("Amsterdam","amsterdam_crrt_cohort.csv")]:
    d=pd.read_csv(BASE/"data"/p)
    if name=="eICU": d=d[d.crrt_within_7d==1]
    s=d[cols].sum(axis=1); k=int((s==5).sum()); n=len(d)
    rows.append((name,k,n,100*k/n)); print(name,k,n,round(100*k/n,3))
ks=np.array([r[1] for r in rows],float); ns=np.array([r[2] for r in rows],float); ps=ks/ns
vs=ps*(1-ps)/ns; ws=1/vs; fe=(ws*ps).sum()/ws.sum(); Q=(ws*(ps-fe)**2).sum(); df=len(ps)-1
C=ws.sum()-(ws**2).sum()/ws.sum(); tau2=max(0,(Q-df)/C) if C>0 else 0
wr=1/(vs+tau2); re=(wr*ps).sum()/wr.sum(); se=math.sqrt(1/wr.sum()); I2=max(0,(Q-df)/Q)*100 if Q>0 else 0
print("pooled",round(100*re,2),"95CI",round(100*(re-1.96*se),2),round(100*(re+1.96*se),2),"I2",round(I2,1),"Q",round(Q,2))
pd.DataFrame(rows,columns=["cohort","k","n","pct"]).to_csv(BASE/"outputs"/"all_five_forest.csv",index=False)
