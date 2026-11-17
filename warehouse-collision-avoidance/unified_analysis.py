"""Generate all current research views strictly from one completed unified batch."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from unified_batch import ROOT,STORE,CONTRACT,study_folder,read_rows,hashes,atomic
from research_statistics import comparison,paired_differences,cluster_ci

def validate(batch_id):
    folder=study_folder(batch_id);config=json.loads((folder/"configuration.json").read_text())
    progress=json.loads((folder/"progress.json").read_text())
    if progress["phase"]!="complete" or progress["completed"]!=90:raise ValueError("완료된90조건 배치가 필요합니다.")
    if config["engine_sha256"]!=hashes():raise ValueError("실험 소스가 현재 물리 소스와 다릅니다.")
    rows=read_rows(batch_id);df=pd.DataFrame(rows)
    expected={(m,s,a.title() if a!="orca" and a!="vo" else a.upper()) for m in CONTRACT["maps"] for s in CONTRACT["seeds"] for a in CONTRACT["algorithms"]}
    actual=set(zip(df["map"],df.seed.astype(int),df.algorithm))
    if len(df)!=90 or actual!=expected or df.run_id.nunique()!=90:raise ValueError("중복/누락 조건이 있습니다.")
    if not df.groupby(["map","seed"]).scene_hash.nunique().eq(1).all():raise ValueError("세 알고리즘의 초기 상태가 다릅니다.")
    if not ((df.encounter_mode=="crossing")&(df.population_mode=="workers")&(df.agent_count==4)&(df.frame_limit==5400)).all():raise ValueError("통일 조건이 아닙니다.")
    expected_settings={"scenario":CONTRACT["scenario"],"planner":CONTRACT["planner"],"traffic_mode":CONTRACT["traffic_mode"],
                       "max_speed_mps":CONTRACT["speed"],"safety_distance_m":CONTRACT["safety"],"common_traffic":0,**CONTRACT["parameters"]}
    for key,value in expected_settings.items():
        if key not in df:raise ValueError("필수 조건 열이 없습니다: "+key)
        good=np.isclose(df[key].astype(float),value,rtol=0,atol=1e-12).all() if isinstance(value,(float,int)) else (df[key]==value).all()
        if not good:raise ValueError("통일 조건이 아닙니다: "+key)
    inputs={}
    for row in rows:
        run=STORE/"runs"/row["run_id"]
        if not (run/"complete.json").exists():raise ValueError("미완료 실행입니다.")
        completion=json.loads((run/"complete.json").read_text())
        if completion.get("complete") is not True or completion.get("run_id")!=row["run_id"]:raise ValueError("미완료 실행입니다.")
        result=json.loads((run/"result.json").read_text())
        last=json.loads((run/"trajectory.json").read_text())[-1]
        success=int(np.linalg.norm(np.asarray(last["robot"])-result["goal"])<=.25 and np.linalg.norm(last["velocity"])<=.02)
        if success!=row["success"] or result["scene_hash"]!=row["scene_hash"]:raise ValueError("물리 결과가 CSV와 다릅니다.")
        for key,result_key in [("collision_count","collisions"),("safety_violation_count","safety_violations"),("path_length_m","path_length_m")]:
            if not np.isclose(row[key],result[result_key]):raise ValueError("집계 값이 원본과 다릅니다.")
        if any(row[k]!=result[k] for k in ("safe_success","collision_free_success")):raise ValueError("도달 정의가 원본과 다릅니다.")
        saved=json.loads((run/"provenance.json").read_text())["source_sha256"]
        if any(saved.get(k)!=v for k,v in config["engine_sha256"].items()):raise ValueError("실행 중 소스 버전이 다릅니다.")
        for name in ["configuration.json","result.json","metrics.csv","initial_state.json","provenance.json","complete.json"]:
            path=run/name;inputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return folder,config,df,inputs

def records(df):return json.loads(df.to_json(orient="records",double_precision=12))
def build(batch_id):
    folder,config,df,inputs=validate(batch_id)
    out=STORE/"research"/batch_id
    if out.exists():raise ValueError("기존 분석 폴더를 덮어쓰지 않습니다.")
    out.mkdir(parents=True,exist_ok=False)
    audit={"totals":{"total":len(df),"success":int(df.success.sum()),"collision_free_success":int(df.collision_free_success.sum()),"safe_success":int(df.safe_success.sum())},
           "issues":[],"mismatches":[],"source_batch_id":batch_id,"input_sha256":inputs}
    old=STORE/"research/20261117T115115_2ef7f604/audit.json"
    protected=json.loads(old.read_text())["original_sha256"] if old.exists() else {}
    changed=[p for p,h in protected.items() if not (ROOT/p).exists() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    if changed:raise ValueError("이전 원본이 변경되었습니다: "+str(changed[:3]))
    audit["historical_files_unchanged"]=len(protected);atomic(out/"audit.json",audit)
    df.to_csv(out/"measurements.csv",index=False,na_rep="N/A")
    algorithms=pd.DataFrame([comparison(g,{"algorithm":a,"source":batch_id}) for a,g in df.groupby("algorithm")])
    algorithms.to_csv(out/"algorithm_comparison.csv",index=False,na_rep="N/A")
    per_map=pd.DataFrame([comparison(g,{"map":m,"algorithm":a,"source":batch_id}) for (m,a),g in df.groupby(["map","algorithm"])])
    per_map.to_csv(out/"map_comparison.csv",index=False,na_rep="N/A")
    scenarios=pd.DataFrame([comparison(g,{"scenario_label":"Crossing","algorithm":a,"source":batch_id,
        "interpretation":"six maps, n=4 workers, five paired seeds; no other encounter modes"}) for a,g in df.groupby("algorithm")])
    scenarios.to_csv(out/"scenario_comparison.csv",index=False,na_rep="N/A")
    scale=[]
    for a,g in df.groupby("algorithm"):
        row=comparison(g,{"algorithm":a,"population":"workers","agent_count":4,"source":batch_id,
                          "scope":"single n=4; no scalability slope"})
        for key in ("neighbor_checks","candidate_checks","constraints"):
            value=g[key]/g.algo_steps
            lo,hi,_=cluster_ci(value,g.seed)
            row.update({key+"_per_step_mean":float(value.mean()),key+"_per_step_ci95_low":lo,key+"_per_step_ci95_high":hi})
        scale.append(row)
    scale=pd.DataFrame(scale);scale.to_csv(out/"scalability_analysis.csv",index=False,na_rep="N/A")
    paired=paired_differences(df);paired.to_csv(out/"paired_comparisons.csv",index=False,na_rep="N/A")
    from research_orca import analyze_failures
    if int(df[df.algorithm=="ORCA"].orca_audit_frames.sum())>0:
        failures=analyze_failures(df,out);failures["source"]=batch_id
        failures.to_csv(out/"orca_failure_analysis.csv",index=False,na_rep="N/A")
    else:
        pd.DataFrame(columns=["run_id","frame","category","minimum_clearance_m"]).to_csv(out/"orca_failure_analysis.csv",index=False)
        atomic(out/"orca_summary.json",{"frames":0,"categories":{},"note":"No observed diagnostic frames; no invented cases."})
        atomic(out/"orca_representatives.json",[])
    from research_layouts import analyze_layouts
    cached=folder/"layout_metrics"
    if (cached/"manifest.json").exists():
        import shutil
        note=json.loads((cached/"manifest.json").read_text())
        if note["engine_sha256"]!=config["engine_sha256"]:raise ValueError("맵 계측 소스가 다릅니다.")
        for name in ["warehouse_layout_analysis.csv","warehouse_planner_runs.csv","warehouse_layout_scenes.json"]:
            if hashlib.sha256((cached/name).read_bytes()).hexdigest()!=note["files"][name]:raise ValueError("맵 계측 파일이 변경되었습니다.")
            shutil.copyfile(cached/name,out/name)
        layouts=pd.read_csv(out/"warehouse_layout_analysis.csv")
    else:
        layouts=analyze_layouts(out)
    from unified_figures import generate
    generate(df,per_map,out)
    scope={"batch_id":batch_id,"runs":90,"maps":6,"seed_count":5,"seeds":CONTRACT["seeds"],
           "encounter":"Crossing","population":"workers","agent_count":4,
           "note":"同一 배치90조건 · 6맵×3알고리즘×5시드 · n=4 횡단 작업자 · 다른 밀집도/만남으로 일반화하지 않음"}
    scope["note"]=scope["note"].replace("同一","동일")
    method={"bootstrap":"3000 seed-cluster replicates; whole seeds resampled across six maps; paired scene hashes",
            "independent_seed_clusters":5,"runs_per_algorithm":30,"turning":"planned-path heading changes",
            "limitations":["single n=4: no density scaling conclusion","only Crossing: other scenarios N/A","five seeds: exploratory intervals"]}
    atomic(out/"statistical_method.json",method)
    bundle={"schema":2,"id":batch_id,"source_batch_id":batch_id,"status":"complete",
            "title":"동일 조건6개 창고 맵의 충돌 회피 비교","scope":scope,"audit":audit,
            "run_ids":df.run_id.tolist(),"algorithms":records(algorithms),"map_comparisons":records(per_map),
            "scenarios":records(scenarios),"scenario_options":["Crossing"],"population_options":["workers"],
            "scalability":records(scale),"layouts":records(layouts),"paired":records(paired),
            "orca_summary":json.loads((out/"orca_summary.json").read_text()),
            "orca_cases":json.loads((out/"orca_cases.json").read_text()),"supplement":[],"supplement_runs":0,
            "statistical_method":method,"report":"research_report.md",
            "figures":[p.name for p in sorted((out/"figs").glob("*.png"))]}
    report=["# 동일 조건6개 창고 맵의 충돌 회피 비교 분석","\nBatch ID: "+batch_id,
      "\n## 실험 조건","6맵×Naive/VO/ORCA×시드42~46=90회. medium/n=4 workers/Crossing/A*/동적/속도1.2m/s/안전0.35m/5400프레임. 실제 강체 상태와 완료 기록으로 검증했다.",
      "\n## 데이터 출처","비교·결과·연구분석은 같은 measurements.csv/run_id 목록을 사용한다. 기존240회와 과거18회는 보존하고 새 분모에 합산하지 않았다.",
      "\n## 알고리즘 결과","|알고리즘|도달|무충돌 도달|안전 도달|평균 거리m|도달시간s|회피ms/step|","|---|---:|---:|---:|---:|---:|---:|"]
    for row in algorithms.to_dict("records"):
        fmt=lambda k:"N/A" if pd.isna(row[k]) else f'{row[k]:.5f}'
        report.append(f'|{row["algorithm"]}|{row["success_count"]}/30|{row["collision_free_success_count"]}/30|{row["safe_success_count"]}/30|{fmt("path_length_m_mean")}|{fmt("arrival_time_s_mean")}|{fmt("algo_time_avg_ms_mean")}|')
    report+=["\n## 맵별·통계 분석","map_comparison.csv는 각맵/알고리즘5개 시드, algorithm_comparison.csv는 알고리즘당30행이다. 동일 시드의6맵을 독립 시드로 부풀리지 않고5개 시드 군집으로 부트스트랩한다. 도착시간은 성공한 경우만 포함하며 paired_comparisons.csv는 동일조건 양쪽성공 짝을 사용한다.",
       "\n## ORCA 위반","실제 위험 프레임에 독립 반평면/속도 원판 허용해 검사를 적용했다. A/B/D/E 분류는 관측 증거이며 비협조 작업자나 제어기의 단일 인과를 단정하지 않는다. 세부 CSV와 관측 사례만 제시한다.",
       "\n## 배치·코드 검증",f'90개 유일 run_id,30개 초기상태 일치 triplet. 이전 원본{len(protected)}개 SHA256 유지. engine_sha256/구성/초기상태/마지막 물리프레임과 CSV 일치. 입력90건의 해시는 audit.json에 저장했다.',
       "\n## 한계","n=4와Crossing만 측정했으므로 에이전트 증가 성능이나Head-On/Narrow/Dense 결과를 새 배치의 결과로 주장하지 않는다. 기존 해당 연구는 과거별도배치다. 성공·무충돌·안전 도달을 구분하며5시드 구간은 탐색적이다. 현재 구현의ORCA는 비협조 장애물에대한책임100%이며 보편적우월성을 주장하지 않는다.",
       "\n## 재현",f'.venv/bin/python unified_batch.py --resume {batch_id}\n.venv/bin/python unified_analysis.py {batch_id}',
       "\n## 연구 자료","기존 docs/research_layouts.md의IJCAI2023/MovingAI 참고 범위를 유지한다. 배치는 자체설계이며논문레이아웃재현이 아니다. 알고리즘정의는기존 docs/algorithm_analysis.md를따른다."]
    (out/"research_report.md").write_text("\n".join(report)+"\n")
    (out/"presentation_summary.md").write_text("\n".join(report[:12])+"\n전체결론/한계는동일배치연구보고서참조.\n")
    # Public dashboard excludes large input hash map; audit remains downloadable in project.
    bundle["audit"]={k:v for k,v in audit.items() if k!="input_sha256"}
    atomic(out/"dashboard.json",bundle)
    atomic(out/"manifest.json",{"status":"complete","batch_id":batch_id,"primary_runs":90,"new_runs":90,"planner_runs":54,
                                "originals_unchanged":True,"engine_sha256":config["engine_sha256"]})
    print("ANALYSIS_READY="+batch_id,flush=True)
    return bundle
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("batch_id");build(p.parse_args().batch_id)
