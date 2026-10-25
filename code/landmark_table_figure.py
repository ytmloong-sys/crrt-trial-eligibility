import pandas as pd, numpy as np, math, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
cols=["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]
files={"MIMIC":"mimic_icu_landmark_flags.csv","eICU":"eicu_icu_landmark_flags.csv","SICdb":"sicdb_icu_landmark_flags.csv","Amsterdam":"amsterdam_icu_landmark_flags.csv"}
prim={"MIMIC":[23.9,15.7,15.7,11.7,26.3,42.2,3.9],"eICU":[15.5,10.8,10.8,5.6,13.3,24.8,2.0],"SICdb":[27.2,24.7,34.2,5.6,30.2,55.2,1.4],"Amsterdam":[38.8,29.3,27.9,4.5,39.2,58.6,2.9]}
labels=["STARRT-AKI","AKIKI","AKIKI-2","IDEAL-ICU","ELAIN","Any 5","All 5"]
rows=[]
for co,f in files.items():
    d=pd.read_csv(BASE/"data"/f); s=d[cols].sum(axis=1)
    vals=[100*d[c].mean() for c in cols]+[100*(s>0).mean(),100*(s==5).mean()]
    vals=[round(x,1) for x in vals]
    rows.append([co,"CRRT−6 h"]+prim[co])
    rows.append([co,"ICU admission"]+vals)
out=pd.DataFrame(rows,columns=["Cohort","Time zero"]+labels)
out.to_csv(BASE/"outputs"/"TableS5_landmark.csv",index=False)
print(out.to_string(index=False))
# forest-style comparison
fig,ax=plt.subplots(figsize=(7.2,3.6))
cohorts=list(files.keys()); y=np.arange(len(cohorts))[::-1]
for yi,co in zip(y,cohorts):
    p=prim[co][-1]; l=out[(out.Cohort==co)&(out["Time zero"]=="ICU admission")]["All 5"].astype(float).iloc[0]
    ax.plot([p,l],[yi,yi],color="#a0aec0",lw=1,zorder=1)
    ax.scatter(p,yi,color="#c53030",s=45,zorder=2,label="Primary (CRRT−6 h)" if co=="MIMIC" else "")
    ax.scatter(l,yi,color="#2b6cb0",s=45,zorder=2,label="ICU admission" if co=="MIMIC" else "")
    ax.text(max(p,l)+0.15,yi,f"{p:.1f} → {l:.1f}%",va="center",fontsize=8)
ax.axvline(2.5,color="#c53030",ls="--",lw=.8)
ax.axvline(2.2,color="#2b6cb0",ls="--",lw=.8)
ax.set_yticks(y); ax.set_yticklabels(cohorts); ax.set_xlim(0,5.5)
ax.set_xlabel("All-five timing-trial eligibility (%)")
ax.legend(frameon=False,loc="lower right",fontsize=8)
ax.spines[["top","right"]].set_visible(False); fig.tight_layout()
fig.savefig(BASE/"outputs"/"figureS5_landmark_vs_primary.png",dpi=300)
fig.savefig(BASE/"outputs"/"figureS5_landmark_vs_primary.pdf")
print("saved")
