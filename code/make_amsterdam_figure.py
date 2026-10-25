import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
df=pd.read_csv(BASE/"outputs"/"amsterdam_trial_comparison.csv")
x=range(len(df)); w=.38
fig,ax=plt.subplots(figsize=(8,4.8))
ax.bar([i-w/2 for i in x],df.ams_pct,w,label="AmsterdamUMCdb",color="#6b46c1")
ax.bar([i+w/2 for i in x],df.mimic_pct,w,label="MIMIC-IV",color="#c53030")
ax.errorbar([i-w/2 for i in x],df.ams_pct,yerr=[df.ams_pct-df.ams_lo,df.ams_hi-df.ams_pct],fmt="none",ecolor="black",capsize=3,lw=.8)
ax.errorbar([i+w/2 for i in x],df.mimic_pct,yerr=[df.mimic_pct-df.mimic_lo,df.mimic_hi-df.mimic_pct],fmt="none",ecolor="black",capsize=3,lw=.8)
ax.set_xticks(list(x)); ax.set_xticklabels(df.trial,rotation=20,ha="right")
ax.set_ylabel("Eligible (%)"); ax.set_ylim(0,48); ax.legend(frameon=False)
ax.spines[["top","right"]].set_visible(False); fig.tight_layout()
fig.savefig(BASE/"outputs"/"figureS3_amsterdam_vs_mimic.png",dpi=300)
fig.savefig(BASE/"outputs"/"figureS3_amsterdam_vs_mimic.pdf")
print("saved")
