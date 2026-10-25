import duckdb, sys, time
sys.stdout.reconfigure(encoding="utf-8")
root=r"D:\ICU数据库\SICdb\salzburg-intensive-care-database-sicdb-a-freely-accessible-intensive-care-database-1.0.8"
out=r"C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation\data\sicdb_float_sig.parquet"
con=duckdb.connect()
con.execute("SET threads=4")
ids=[723,730,731,732,2022,3071,725,2305,711,712,713,715,717,719,727,2019,2020,2021,3035]
idlist=",".join(map(str,ids))
print("extracting signals...", flush=True)
q=f"""
COPY (
 SELECT "CaseID","DataID","Offset","Val"
 FROM read_csv_auto('{root}\\data_float_h.csv.gz', header=true, sample_size=10000)
 WHERE "DataID" IN ({idlist}) AND "Val" IS NOT NULL
) TO '{out}' (FORMAT PARQUET)
"""
t=time.time(); con.execute(q); print("done", round(time.time()-t,1), "s", flush=True)
print(con.execute(f"SELECT COUNT(*) n, COUNT(DISTINCT CaseID) cases, COUNT(DISTINCT DataID) ids FROM read_parquet('{out}')").fetchdf().to_string(index=False))
