import pandas as pd, numpy as np, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
root=Path(r"D:\ICU数据库\SICdb\salzburg-intensive-care-database-sicdb-a-freely-accessible-intensive-care-database-1.0.8"); out=Path(r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation")/"data"; out.mkdir(exist_ok=True)
refs=pd.read_csv(root/"d_references.csv.gz")
cases=pd.read_csv(root/"cases.csv.gz", low_memory=False)
# map codes
sex_map=refs[refs.ReferenceName=="Sex"].set_index("ReferenceGlobalID")["ReferenceValue"].to_dict()
sep_map=refs[refs.ReferenceName=="YesNoUnknown"].set_index("ReferenceGlobalID")["ReferenceValue"].to_dict()
dis_map=refs[refs.ReferenceName=="DischargeState"].set_index("ReferenceGlobalID")["ReferenceValue"].to_dict()
cases["sex"]=cases["Sex"].map(sex_map)
cases["sepsis_adm"]=cases["AdmissionFormHasSepsis"].map(sep_map).eq("Yes").astype(int)
cases["death_hosp"]=((cases["DischargeState"].map(dis_map).eq("verstorben")) | (cases["HospitalDischargeType"]==3130)).astype(int)
cases["death_24h"]=((cases["death_hosp"]==1) & (pd.to_numeric(cases["OffsetOfDeath"],errors="coerce")<=86400)).astype(int)
# data_ref fields
dr=pd.read_csv(root/"data_ref.csv.gz")
refval=refs.set_index("ReferenceGlobalID")["ReferenceValue"].to_dict()
def field(fid):
    x=dr[dr.FieldID==fid][["CaseID","RefID"]].copy()
    x["val"]=x["RefID"].map(refval)
    return x[["CaseID","val"]].rename(columns={"val":f"f{fid}"})
for fid in [3104,3113,3114]:
    f=field(fid)
    if len(f): cases=cases.merge(f,on="CaseID",how="left")
cases["precondition_renal"]=cases.get("f3104",pd.Series(index=cases.index)).eq("Yes").astype(int)
cases["kdigo_aki_168"]=pd.to_numeric(cases.get("f3113",pd.Series(index=cases.index)),errors="coerce")
# crude ICD10 text flags
txt=(cases["ICD10Main"].fillna("").astype(str)+" "+cases.get("DiagnosisT2",pd.Series("",index=cases.index)).fillna("").astype(str)).str.lower()
cases["esrd_icd"]=txt.str.contains(r"n18\.5|n18\.6|z99\.2|dialyse|dialysis",regex=True).astype(int)
cases["cirrhosis_icd"]=txt.str.contains("cirrhos|leberzirrhose",regex=True).astype(int)
cases["cancer_icd"]=txt.str.contains("cancer|karzinom|malign|neoplas",regex=True).astype(int)
cases["transplant_icd"]=txt.str.contains("transplant",regex=True).astype(int)
cases["obstruction_icd"]=txt.str.contains("obstruktion|obstruction|harnstau",regex=True).astype(int)
cases["prior_rrt"]=0  # not directly available; documented limitation
cases.to_csv(out/"sicdb_cases.csv",index=False)
print("cases",cases.shape)
# labs
labs=pd.read_csv(root/"laboratory.csv.gz", low_memory=False)
lab_ids=[367,368,369,453,463,685,688,697,698,700,663,538,451,456,666,667,355]
labs=labs[labs.LaboratoryID.isin(lab_ids)].copy()
lab_names={367:"creatinine",368:"creatinine",369:"creatinine",453:"potassium",463:"potassium",685:"potassium",688:"ph",697:"ph",698:"ph",700:"ph",663:"ph",538:"ph",451:"bicarbonate",456:"bicarbonate",666:"bicarbonate",667:"bicarbonate",355:"urea"}
labs["lab"]=labs.LaboratoryID.map(lab_names)
labs=labs[["CaseID","Offset","LaboratoryValue","lab"]].rename(columns={"LaboratoryValue":"value"})
labs.to_csv(out/"sicdb_labs.csv",index=False)
print("labs",labs.shape, labs.lab.value_counts().to_dict())
# vaso meds
med=pd.read_csv(root/"medication.csv.gz", low_memory=False)
vaso_ids=[1562,1502,1618,1550,1593]
med=med[med.DrugID.isin(vaso_ids)].copy()
med.to_csv(out/"sicdb_vaso.csv",index=False)
print("vaso",med.shape)
