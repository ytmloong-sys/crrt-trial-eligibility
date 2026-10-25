import pandas as pd, numpy as np, math, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
files={"MIMIC":"mimic_icu_landmark_flags.csv","eICU":"eicu_icu_landmark_flags.csv","SICdb":"sicdb_icu_landmark_flags.csv","Amsterdam":"amsterdam_icu_landmark_flags.csv"}
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
def wilson(k,n,z=1.96):
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return 100*(c-h),100*(c+h)
rows=[]
for co,f in files.items():
    d=pd.read_csv(BASE/"data"/f); s=d[cols].sum(axis=1)
    k=int((s==5).sum()); n=len(d); lo,hi=wilson(k,n)
    rows.append(dict(cohort=co,k=k,n=n,pct=100*k/n,lo=lo,hi=hi))
    print(co, k,n,round(100*k/n,1),round(lo,1),round(hi,1))
df=pd.DataFrame(rows); df.to_csv(BASE/"outputs"/"icu_landmark_all5.csv",index=False)
ps=df.pct.values/100; ns=df.n.values; ks=df.k.values
vs=ps*(1-ps)/ns; ws=1/vs; fe=(ws*ps).sum()/ws.sum(); Q=(ws*(ps-fe)**2).sum(); dfree=len(ps)-1
C=ws.sum()-(ws**2).sum()/ws.sum(); tau2=max(0,(Q-dfree)/C) if C>0 else 0
wr=1/(vs+tau2); re=(wr*ps).sum()/wr.sum(); se=math.sqrt(1/wr.sum()); I2=max(0,(Q-dfree)/Q)*100 if Q>0 else 0
print("pooled",round(100*re,2),round(100*(re-1.96*se),2),round(100*(re+1.96*se),2),"I2",round(I2,1))
