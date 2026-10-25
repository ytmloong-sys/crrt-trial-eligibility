import os, math, json
os.environ["HTTP_PROXY"]="http://127.0.0.1:7897"; os.environ["HTTPS_PROXY"]="http://127.0.0.1:7897"
import pandas as pd, numpy as np
from google.cloud import bigquery
from pathlib import Path

BASE=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")
client=bigquery.Client(project="deresuscitation-tte"); BT=chr(96); P="physionet-data.eicu_crd"
coh=pd.read_csv(BASE/"data"/"eicu_crrt_cohort.csv")
coh["any5"]=(coh[["starrt_eligible","akiki_eligible","akiki2_eligible","ideal_eligible","elain_eligible_partial"]].sum(axis=1)>0).astype(int)

# stratified sample: 10 eligible, 10 ineligible, 10 UO-missing
elig_ids=set(coh[coh.any5==1].sample(n=10, random_state=1).patientunitstayid)
inelig_pool=coh[(coh.any5==0)&(coh.uo_rows.fillna(0)>0)&(~coh.patientunitstayid.isin(elig_ids))]
inelig_ids=set(inelig_pool.sample(n=10, random_state=2).patientunitstayid)
uo_pool=coh[(coh.uo_rows.fillna(0)==0)&(~coh.patientunitstayid.isin(elig_ids|inelig_ids))]
uo_ids=set(uo_pool.sample(n=10, random_state=3).patientunitstayid)
sample=coh[coh.patientunitstayid.isin(elig_ids|inelig_ids|uo_ids)].copy()
sample["audit_group"]=np.where(sample.patientunitstayid.isin(elig_ids),"eligible_any",np.where(sample.patientunitstayid.isin(inelig_ids),"ineligible_all","uo_missing"))
print("sample",len(sample),sample.audit_group.value_counts().to_dict())
ids=sample.patientunitstayid.astype(int).tolist()
idlist=",".join(str(x) for x in ids)

def get(sql):
    return client.query(sql).to_dataframe()

pat=get(f"SELECT patientunitstayid, gender, age, admissionweight, unittype, hospitaldischargestatus, hospitaldischargeoffset FROM {BT}{P}.patient{BT} WHERE patientunitstayid IN ({idlist})")
tr=get(f"SELECT patientunitstayid, treatmentoffset, treatmentstring FROM {BT}{P}.treatment{BT} WHERE patientunitstayid IN ({idlist})")
lab=get(f"SELECT patientunitstayid, labresultoffset, labname, labresult FROM {BT}{P}.lab{BT} WHERE patientunitstayid IN ({idlist}) AND LOWER(labname) IN ('creatinine','potassium','ph','bicarbonate')")
uo=get(f"SELECT patientunitstayid, intakeoutputoffset, celllabel, cellvaluenumeric FROM {BT}{P}.intakeoutput{BT} WHERE patientunitstayid IN ({idlist}) AND (LOWER(celllabel) LIKE '%urine%' OR LOWER(celllabel) LIKE '%foley%' OR LOWER(celllabel) LIKE '%void%')")
inf=get(f"SELECT patientunitstayid, infusionoffset, drugname FROM {BT}{P}.infusiondrug{BT} WHERE patientunitstayid IN ({idlist})")
ap=get(f"SELECT patientunitstayid, ventday1 FROM {BT}{P}.apachepredvar{BT} WHERE patientunitstayid IN ({idlist})")
dx=get(f"SELECT patientunitstayid, diagnosisstring FROM {BT}{P}.diagnosis{BT} WHERE patientunitstayid IN ({idlist})")
hx=get(f"SELECT patientunitstayid, pasthistorypath FROM {BT}{P}.pasthistory{BT} WHERE patientunitstayid IN ({idlist})")

rows=[]
for _,r in sample.iterrows():
    sid=int(r.patientunitstayid); t0=float(r.time_zero); coff=float(r.crrt_offset)
    fails=[]
    # 1 time zero
    if abs((coff-360)-t0)>0.01: fails.append("time_zero")
    # 2 crrt offset
    tt=tr[tr.patientunitstayid==sid]
    c=tt[tt.treatmentstring.str.lower().str.contains(r"c v v|c a v h",regex=True)]
    if len(c) and abs(c.treatmentoffset.min()-coff)>0.01: fails.append("crrt_offset")
    # 3 creatinine
    l=lab[(lab.patientunitstayid==sid)&(lab.labname=="creatinine")]
    win=l[(l.labresultoffset>=t0-10080)&(l.labresultoffset<=t0)]
    if len(win):
        base=win.labresult.min()
        if pd.notna(r.baseline_creat) and abs(base-r.baseline_creat)>0.01: fails.append("baseline_creat")
    w24=l[(l.labresultoffset>=t0-1440)&(l.labresultoffset<=t0)]
    if len(w24):
        if pd.notna(r.creat_max_24h) and abs(w24.labresult.max()-r.creat_max_24h)>0.01: fails.append("creat_max")
        if pd.notna(r.creat_min_24h) and abs(w24.labresult.min()-r.creat_min_24h)>0.01: fails.append("creat_min")
    # 4 UO
    u=uo[(uo.patientunitstayid==sid)&(uo.intakeoutputoffset>=t0-1440)&(uo.intakeoutputoffset<=t0)]
    if len(u):
        if pd.notna(r.uo_24h) and abs(u.cellvaluenumeric.sum()-r.uo_24h)>0.1: fails.append("uo_24h")
    # 5 vaso
    v=inf[(inf.patientunitstayid==sid)&(inf.infusionoffset>=t0-360)&(inf.infusionoffset<=t0)]
    vflag=int(v.drugname.str.lower().str.contains("norepinephrine|epinephrine|dopamine|vasopressin|phenylephrine",regex=True).any()) if len(v) else 0
    if vflag!=int(r.vaso): fails.append(f"vaso({vflag} vs {int(r.vaso)})")
    # 6 MV
    a=ap[ap.patientunitstayid==sid]
    mflag=int(a.ventday1.max()) if len(a) and pd.notna(a.ventday1.max()) else 0
    if mflag!=int(r.mv): fails.append(f"mv({mflag} vs {int(r.mv)})")
    # 7 sepsis
    d=dx[dx.patientunitstayid==sid]
    sflag=int(d.diagnosisstring.str.lower().str.contains("sepsis").any()) if len(d) else 0
    if sflag!=int(r.sepsis): fails.append(f"sepsis({sflag} vs {int(r.sepsis)})")
    # 8 prior RRT (before t0, exclude catheter/insertion)
    p=tt[(tt.treatmentoffset<t0)&(tt.treatmentstring.str.lower().str.contains(r"renal\|dialysis",regex=True))&(~tt.treatmentstring.str.lower().str.contains(r"catheter|insertion",regex=True))]
    pflag=int(len(p)>0)
    if pflag!=int(r.prior_rrt): fails.append(f"prior_rrt({pflag} vs {int(r.prior_rrt)})")
    # 9 history flags
    h=hx[hx.patientunitstayid==sid]
    hpath=h.pasthistorypath.str.lower() if len(h) else pd.Series(dtype=str)
    def hf(pattern): return int(hpath.str.contains(pattern,regex=True).any()) if len(hpath) else 0
    checks={"esrd":hf(r"renal failure - hemodialysis|renal failure - peritoneal dialysis"),"transplant":hf(r"transplant"),"cirrhosis":hf(r"cirrhosis"),"cancer":hf(r"cancer|malignancy|metastases"),"chf":hf(r"congestive heart failure"),"copd":hf(r"copd")}
    for k,vv in checks.items():
        if vv!=int(r[k]): fails.append(f"{k}({vv} vs {int(r[k])})")
    rows.append({"patientunitstayid":sid,"group":r.audit_group,"n_fails":len(fails),"fails":"; ".join(fails),
                 "crrt_offset":coff,"time_zero":t0,"baseline":r.baseline_creat,"creat_max":r.creat_max_24h,
                 "uo_24h":r.uo_24h,"vaso":r.vaso,"mv":r.mv,"sepsis":r.sepsis,"prior_rrt":r.prior_rrt,
                 "starrt":r.starrt_eligible,"akiki":r.akiki_eligible,"akiki2":r.akiki2_eligible,"ideal":r.ideal_eligible,"elain":r.elain_eligible_partial})
audit=pd.DataFrame(rows)
audit.to_csv(BASE/"outputs"/"eicu_audit_30.csv",index=False)
print(audit[["patientunitstayid","group","n_fails","fails"]].to_string(index=False))
print("\nsummary",audit.n_fails.value_counts().to_dict())