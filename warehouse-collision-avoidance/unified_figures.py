"""Graphs from the selected ninety-run table; unavailable conditions are never fabricated."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Polygon
from research_figures import setup,save,C,NAMES
from research_statistics import describe

def generate(df,per_map,out):
    setup();out=Path(out);figs=out/"figs";figs.mkdir(exist_ok=True)
    for metric,name,title,label in [
        ("safe_success","01_safe_success.png","동일 배치의 안전 도달률","안전 도달률(%)"),
        ("collision_count","02_collisions.png","동일 배치의 충돌 횟수","평균 충돌/실행"),
        ("collision_free_success","03_crossing.png","6맵 횡단 · 무충돌 도달률","무충돌 도달률(%)")]:
        fig,ax=plt.subplots(figsize=(8,4.6));factor=100 if metric!="collision_count" else 1
        for i,a in enumerate(C):
            s=describe(df[df.algorithm==a],metric);m=s["mean"]*factor
            err=[[m-s["ci95_low"]*factor],[s["ci95_high"]*factor-m]]
            ax.bar(i,m,color=C[a],yerr=err,capsize=4)
        ax.set_xticks(range(3),[NAMES[a] for a in C]);ax.set(title=title,ylabel=label)
        save(fig,figs/name,"각 알고리즘30조건·시드5묶음 / 95% 시드 군집 부트스트랩")
    for metric,name,title,label in [
        ("safe_success","12_map_safe_success.png","맵별 안전 도달률","안전 도달률(%)"),
        ("algo_time_avg_ms","13_map_runtime.png","맵별 실제 회피 계산시간","회피 평균(ms/step)"),
        ("algo_time_avg_ms","04_runtime_workers.png","고정 n=4 · 맵별 계산 비용","회피 평균(ms/step)"),
        ("algo_time_p95_ms","11_supplement_workers.png","주 실험의 프레임 P95","프레임 P95(ms)")]:
        fig,ax=plt.subplots(figsize=(10,4.7))
        for j,a in enumerate(C):
            subset=per_map[per_map.algorithm==a].sort_values("map")
            y=subset[metric+"_mean"].to_numpy(dtype=float)
            lo=subset[metric+"_ci95_low"].to_numpy(dtype=float);hi=subset[metric+"_ci95_high"].to_numpy(dtype=float)
            if metric=="safe_success":y,lo,hi=y*100,lo*100,hi*100
            ax.bar(np.arange(6)+(j-1)*.24,y,width=.24,color=C[a],label=NAMES[a],
                   yerr=np.maximum(0,np.stack([y-lo,hi-y])),capsize=3)
        ax.set_xticks(range(6),[f"Map {i}" for i in range(1,7)]);ax.set(title=title,ylabel=label);ax.legend()
        save(fig,figs/name,"각 맵/알고리즘5시드 · n=4 고정: 밀집도 확장성 결론 아님")
    fig,axes=plt.subplots(1,3,figsize=(13,4.5))
    for ax,key,label in zip(axes,["neighbor_checks","candidate_checks","constraints"],["이웃 검사","후보 검사","ORCA 반평면"]):
        for a in C:
            g=df[df.algorithm==a].copy();g["per_step"]=g[key]/g.algo_steps
            v=g.groupby("map").per_step.mean();ax.plot(v.index,v.values,marker="o",label=NAMES[a],color=C[a])
        ax.set(title=label,xlabel="창고 맵",ylabel="회/step")
    axes[0].legend(fontsize=8);save(fig,figs/"05_operations_workers.png","실제 연산 카운터 · 작업자4명 고정")
    fig,ax=plt.subplots(figsize=(8,4.6))
    for a in C:
        g=df[df.algorithm==a];ax.scatter(g.path_length_m,g.min_separation_m,color=C[a],label=NAMES[a],alpha=.7)
    ax.axhline(.35,color="gray",linestyle="--");ax.set(xlabel="실제 이동 거리(m)",ylabel="최소 이격(m)",title="이동 효율과 안전성");ax.legend()
    save(fig,figs/"06_distance_safety.png","성공·미도달 실행 모두 포함")
    fig,ax=plt.subplots(figsize=(8,4.6))
    ax.boxplot([df[df.algorithm==a].min_separation_m for a in C],tick_labels=list(C),showmeans=True)
    ax.set(title="최소 이격거리 분포",ylabel="XY 이격(m)");ax.axhline(.35,color="gray",linestyle="--")
    save(fig,figs/"07_clearance_distribution.png")
    selected=json.loads((out/"orca_representatives.json").read_text());cases=[]
    if selected:
        failures=pd.read_csv(out/"orca_failure_analysis.csv")
        for i,rid in enumerate(selected,1):
            g=failures[failures.run_id==rid].sort_values("frame");fig,axes=plt.subplots(3,1,figsize=(9,7),sharex=True)
            for _,part in g.groupby((g.frame.diff().fillna(1)>1).cumsum()):
                axes[0].plot(part.simulation_time_s,part.minimum_clearance_m,marker=".",markersize=2)
                axes[1].plot(part.simulation_time_s,[np.linalg.norm(json.loads(x)) for x in part.orca_output_velocity],color="#2563eb")
                axes[1].plot(part.simulation_time_s,[np.linalg.norm(json.loads(x)) for x in part.actual_newton_velocity],color="#d97706")
                axes[2].plot(part.simulation_time_s,part.constraint_violation_amount,color="#2563eb")
                axes[2].plot(part.simulation_time_s,part.actual_constraint_violation_amount,color="#d97706")
            axes[0].axhline(.35,color="gray",linestyle="--")
            axes[0].set_ylabel("최소 이격(m)");axes[1].set_ylabel("출력/실제 속력");axes[2].set(xlabel="물리시간(s)",ylabel="출력/실제 잔차")
            fig.suptitle("동일 배치 ORCA 관측 사례 "+str(i));filename=f"08_orca_case{i}.png"
            save(fig,figs/filename,"로그 공백은 연결하지 않음 · 분류는 관측 증거이며 단일 인과 확정 아님")
            columns=["run_id","frame","simulation_time_s","category","minimum_clearance_m","orca_output_velocity",
                     "actual_newton_velocity","constraint_violation_amount","actual_constraint_violation_amount",
                     "velocity_tracking_error","preferred_velocity","seed","scenario","population","agent_count"]
            g=g.iloc[np.unique(np.linspace(0,len(g)-1,min(300,len(g))).astype(int))][columns].copy()
            for k in ["orca_output_velocity","actual_newton_velocity"]:g[k]=g[k].map(json.loads)
            cases.append({"run_id":rid,"figure":filename,"samples":json.loads(g.to_json(orient="records"))})
    (out/"orca_cases.json").write_text(json.dumps(cases,ensure_ascii=False))
    layouts=pd.read_csv(out/"warehouse_layout_analysis.csv");planner=pd.read_csv(out/"warehouse_planner_runs.csv")
    fig,axes=plt.subplots(1,2,figsize=(11,4.5));axes[0].bar(layouts["map"],layouts.shortest_grid_path_length_m,color="#0f766e")
    axes[0].set(title="동일6맵의 최단 격자 경로",ylabel="거리(m)")
    for name,g in planner.groupby("planner"):
        v=g.groupby("map").planning_time_ms.agg(["mean","std"]);axes[1].errorbar(v.index,v["mean"],yerr=v["std"],label=name,marker="o")
    axes[1].set(title="별도 전역 탐색54회",ylabel="계획시간(ms)",yscale="log");axes[1].legend()
    save(fig,figs/"09_layout_planning.png","주행90조건의 분모에는 포함하지 않음")
    for scene in json.loads((out/"warehouse_layout_scenes.json").read_text()):
        fig,ax=plt.subplots(figsize=(8,5.5))
        for polygon in scene["polygons"]:ax.add_patch(Polygon(polygon,color="#647b78"))
        for name,path in scene["paths"].items():
            path=np.asarray(path);ax.plot(path[:,0],path[:,1],label=name)
        c=scene["config"];ax.scatter(*c["startPosition"],c="#14b8a6");ax.scatter(*c["goalPosition"],c="red")
        ax.set(xlim=(0,38),ylim=(0,26),aspect="equal",title=c["mapName"]);ax.legend()
        save(fig,figs/f'10_layout_{scene["map"]}.png')
