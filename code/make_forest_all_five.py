import pandas as pd, numpy as np, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
df=pd.read_csv(BASE/"outputs"/"all_five_forest.csv")
def wilson(k,n,z=1.96):
    p=k/n; den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return 100*(c-h),100*(c+h)
cis=[wilson(k,n) for k,n in zip(df.k,df.n)]
df["lo"]=[x[0] for x in cis]; df["hi"]=[x[1] for x in cis]
# pooled from prior: 2.52 (1.41-3.62)
pooled=(2.52,1.41,3.62)
fig,ax=plt.subplots(figsize=(7.2,3.6))
y=np.arange(len(df))[::-1]
ax.errorbar(df.pct,y,xerr=[df.pct-df.lo,df.hi-df.pct],fmt="o",color="#2d3748",capsize=4)
for yi,(_,r) in zip(y,df.iterrows()):
    ax.text(5.2,yi,f"{r.pct:.1f}% ({r.lo:.1f}-{r.hi:.1f})",va="center",fontsize=8)
ax.axvline(pooled[0],color="#c53030",linestyle="--",lw=1)
ax.plot([pooled[1],pooled[0],pooled[2],pooled[0]],[ -1,-0.7,-1,-1.3],color="#c53030",lw=1)
ax.text(pooled[0],-1.55,f"Pooled {pooled[0]:.1f}% (95% CI {pooled[1]:.1f}-{pooled[2]:.1f}); I²=86.3%",ha="center",fontsize=8,color="#c53030")
ax.set_yticks(y); ax.set_yticklabels([f"{r.cohort} (n={int(r.n)})" for _,r in df.iterrows()])
ax.set_xlim(0,5.5); ax.set_xlabel("All-five timing-trial eligibility (%)")
ax.set_ylim(-2.0,len(df)-0.3)
ax.spines[["top","right"]].set_visible(False)
fig.tight_layout()
fig.savefig(BASE/"outputs"/"figureS4_all_five_forest.png",dpi=300)
fig.savefig(BASE/"outputs"/"figureS4_all_five_forest.pdf")
print("saved")
