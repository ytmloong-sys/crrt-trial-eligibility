import duckdb, sys, time
sys.stdout.reconfigure(encoding="utf-8")
root=r"D:\ICU数据库\Amsterdam"
base=r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation"
items=['Kreatinine (bloed)','Kreatinine','Kreatinine (overig)','A_Serum_Kreatinine','KREAT enzym. (bloed)','Kalium (bloed)','Kalium','Kalium Astrup','pH (bloed)','PH','UrineCAD','Lactaat (bloed)','Ureum (bloed)']
itemlist=",".join("'"+x.replace("'","''")+"'" for x in items)
con=duckdb.connect(); con.execute("SET threads=4")
out=base+r"\data\amsterdam_numeric_filtered.parquet"
q=f"""
COPY (
 SELECT admissionid,item,TRY_CAST(value AS DOUBLE) AS value,unit,measuredat,islabresult,fluidout
 FROM read_csv_auto('{root}\\numericitems.csv', header=true, sample_size=100000, encoding='latin-1')
 WHERE admissionid IN (SELECT admissionid FROM read_csv_auto('{base}\\data\\amsterdam_crrt_base.csv'))
   AND item IN ({itemlist})
) TO '{out}' (FORMAT PARQUET)
"""
t=time.time(); con.execute(q); print("done",round(time.time()-t,1),"s")
print(con.execute(f"SELECT COUNT(*) n, COUNT(DISTINCT admissionid) cases, COUNT(DISTINCT item) items FROM read_parquet('{out}')").fetchdf().to_string(index=False))
