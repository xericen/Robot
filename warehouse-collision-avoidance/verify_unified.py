"""Independent selected-batch CSV/dashboard/source integrity verification."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from unified_batch import STORE,atomic
from unified_analysis import validate
def verify(identity):
    folder,config,df,inputs=validate(identity);out=STORE/"research"/identity
    bundle=json.loads((out/"dashboard.json").read_text());manifest=json.loads((out/"manifest.json").read_text())
    assert bundle["id"]==bundle["source_batch_id"]==manifest["batch_id"]==identity
    assert set(bundle["run_ids"])==set(df.run_id) and len(bundle["run_ids"])==90
    for file,key in [("algorithm_comparison.csv","algorithms"),("scenario_comparison.csv","scenarios"),
                     ("scalability_analysis.csv","scalability"),("warehouse_layout_analysis.csv","layouts"),
                     ("paired_comparisons.csv","paired"),("map_comparison.csv","map_comparisons")]:
        csv=pd.read_csv(out/file);rows=bundle[key];assert len(csv)==len(rows)
        for i,row in enumerate(rows):
            for col in csv.select_dtypes(include="number").columns:
                value=csv.iloc[i][col]
                if pd.isna(value):assert row[col] is None
                else:assert np.isclose(value,row[col],rtol=1e-8,atol=1e-10),(file,i,col)
    assert bundle["audit"]["totals"]["total"]==90
    assert all(r["total_runs"]==30 for r in bundle["algorithms"])
    assert all(r["total_runs"]==5 for r in bundle["map_comparisons"])
    assert bundle["scope"]["seed_count"]==5 and bundle["scenario_options"]==["Crossing"]
    assert len(bundle["layouts"])==6
    for f in bundle["figures"]:assert (out/"figs"/f).is_file()
    archived=json.loads((out/"audit.json").read_text())["input_sha256"]
    for rel,digest in archived.items():
        from unified_batch import ROOT
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest
    result={"passed":True,"batch_id":identity,"measured_runs":90,"scene_matched_triplets":30,
            "dashboard_numeric_csv_match":True,"input_files_verified":len(inputs),
            "independent_seed_clusters":5,"layout_count":6,"figures":len(bundle["figures"])}
    (out/"verification.json").write_text(json.dumps(result,indent=2))
    atomic(STORE/"active_batch.json",{"batch_id":identity,"research_id":identity,"validated":True})
    print(json.dumps(result),flush=True);return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("batch_id");verify(p.parse_args().batch_id)
