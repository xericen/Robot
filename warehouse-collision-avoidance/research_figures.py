"""Publication-style figures from measured CSVs; no interpolation of missing observations."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt,font_manager
from research_data import ROOT,inputs,read_json
from research_statistics import describe
C={"Naive":"#d97706","VO":"#2563eb","ORCA":"#0f766e"}
NAMES={"Naive":"단순 반응형(Naive)","VO":"속도 장애물(VO)","ORCA":"속도 제약(ORCA)"}

def setup():
    font=ROOT/"fonts/NotoSansKR.ttf";font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({"font.family":font_manager.FontProperties(fname=font).get_name(),"axes.unicode_minus":False,
                         "font.size":10,"axes.grid":True,"grid.color":"#d1d5db","grid.alpha":.65})

def save(fig,path,note=""):
    if note:fig.text(.02,.01,note,fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(path,dpi=200);plt.close(fig)

def bars(df,metric,path,title,ylabel,percent=False):
    fig,ax=plt.subplots(figsize=(7,4.4))
    labels=[];means=[];low=[];high=[]
    for a in C:
        g=df[df.algorithm==a];stats=describe(g,metric);factor=100 if percent else 1
        mean=stats["mean"]*factor;lo=stats["ci95_low"];hi=stats["ci95_high"]
        labels.append(NAMES[a]);means.append(mean)
        low.append(mean-lo*factor if lo is not None else 0);high.append(hi*factor-mean if hi is not None else 0)
    ax.bar(labels,means,color=list(C.values()),yerr=np.array([low,high]),capsize=5)
    ax.set(title=title,ylabel=ylabel)
    save(fig,path,"95% 구간: 시드 단위 군집 부트스트랩 · 표본 수/실험 범위는 보고서 참조")

def generate(out):
    setup();out=Path(out);figdir=out/"figs";figdir.mkdir(exist_ok=True)
    main,pilot=inputs()
    bars(main,"safe_success",figdir/"01_safe_success.png","알고리즘별 안전 도달률","안전 도달률(%)",True)
    bars(main,"collision_count",figdir/"02_collisions.png","알고리즘별 충돌 진입 횟수","평균 횟수/실행")
    for mode,label in (("head_on","정면 접근"),("crossing","통로 횡단"),("narrow_passing","좁은 통로 교행"),("dense_traffic","밀집 교통")):
        d=main[main.agent_count>=8] if mode=="dense_traffic" else pilot[pilot.encounter_mode==mode]
        bars(d,"collision_free_success",figdir/("03_"+mode+".png"),label+" · 무충돌 도달률","무충돌 도달률(%)",True)
    for population in ("workers","mixed"):
        d=main[main.population_mode==population]
        fig,ax=plt.subplots(figsize=(7,4.4))
        for a,color in C.items():
            xs=[];ys=[];lo=[];hi=[]
            for n,g in d[d.algorithm==a].groupby("agent_count"):
                s=describe(g,"algo_time_avg_ms");xs.append(n);ys.append(s["mean"])
                lo.append(s["mean"]-s["ci95_low"]);hi.append(s["ci95_high"]-s["mean"])
            ax.errorbar(xs,ys,yerr=np.array([lo,hi]),color=color,label=NAMES[a],marker="o",capsize=4)
        ax.set(title=("작업자 전용" if population=="workers" else "혼합")+" · 계산시간 확장성",
               xlabel="에이전트 수(R0 제외)",ylabel="평균 회피 계산시간(ms/프레임)",yscale="log")
        ax.set_xticks([2,4,8,16]);ax.legend()
        save(fig,figdir/("04_runtime_"+population+".png"),"기존 240회 · 각 점 10시드 · 오차막대 95% 시드 군집 구간")
        fig,axes=plt.subplots(1,3,figsize=(12,4))
        for ax,key,title in zip(axes,("neighbor_checks","candidate_checks","constraints"),("이웃 검사","후보·제약 검사","생성 반평면")):
            for a,color in C.items():
                g=d[d.algorithm==a].copy();g["count"]=g[key]/g.algo_steps
                s=g.groupby("agent_count")["count"].agg(["mean","std"])
                ax.errorbar(s.index,s["mean"],yerr=s["std"],color=color,label=NAMES[a],marker="o",capsize=3)
            ax.set(title=title,xlabel="에이전트 수",ylabel="회/프레임");ax.set_xticks([2,4,8,16])
        axes[0].legend(fontsize=8)
        save(fig,figdir/("05_operations_"+population+".png"),"실제 진단 카운터 · 표준편차 · LP 내부 쌍 검사는 별도 보완 계측")
    fig,ax=plt.subplots(figsize=(7,4.6))
    for a,color in C.items():
        d=main[main.algorithm==a]
        for success,marker in ((1,"o"),(0,"x")):
            g=d[d.success==success]
            ax.scatter(g.path_length_m,g.min_separation_m,color=color,marker=marker,alpha=.55,label=NAMES[a]+(" 도달" if success else " 미도달"))
    ax.axhline(.35,color="gray",linestyle="--");ax.set(title="이동 거리와 최소 이격거리",xlabel="실제 누적 이동 거리(m)",ylabel="최소 표면 이격거리(m)")
    ax.legend(fontsize=8);save(fig,figdir/"06_distance_safety.png","점은 실제 실행 · 목표 미도달 거리도 포함 · 지터/보간 없음")
    fig,ax=plt.subplots(figsize=(7,4.5))
    ax.boxplot([main[main.algorithm==a].min_separation_m for a in C],tick_labels=[NAMES[a] for a in C],showmeans=True)
    ax.axhline(.35,color="gray",linestyle="--");ax.set(title="최소 이격거리 분포",ylabel="XY 표면 이격거리(m)")
    save(fig,figdir/"07_clearance_distribution.png","동적 프레임 상대이동 보간/정적 끝점 · 음수는 원형 외곽 기준 침투")
    # Only actually logged risk frames. Split each gap rather than drawing an invented continuous trace.
    selected=read_json(out/"orca_representatives.json")
    cases=[]
    columns=["run_id","frame","simulation_time_s","category","minimum_clearance_m","orca_output_velocity","actual_newton_velocity",
             "constraint_violation_amount","actual_constraint_violation_amount","velocity_tracking_error","seed","scenario","population","agent_count","preferred_velocity"]
    failures=pd.read_csv(out/"orca_failure_analysis.csv",usecols=columns)
    for index,rid in enumerate(selected):
        g=failures[failures.run_id==rid].sort_values("frame")
        fig,axes=plt.subplots(3,1,figsize=(9,7),sharex=True)
        segments=(g.frame.diff().fillna(1)>1).cumsum()
        for _,part in g.groupby(segments):
            t=part.simulation_time_s
            axes[0].plot(t,part.minimum_clearance_m,marker=".",markersize=2)
            axes[1].plot(t,[np.linalg.norm(json.loads(x)) for x in part.orca_output_velocity],color="#2563eb",label="출력 속력")
            axes[1].plot(t,[np.linalg.norm(json.loads(x)) for x in part.actual_newton_velocity],color="#d97706",label="실제 속력")
            axes[2].plot(t,part.constraint_violation_amount,color="#2563eb",label="출력 잔차")
            axes[2].plot(t,part.actual_constraint_violation_amount,color="#d97706",label="실제 잔차")
        axes[0].axhline(.35,color="gray",linestyle="--");axes[0].set_ylabel("최소 이격(m)")
        axes[1].set_ylabel("속력(m/s)");axes[2].set_ylabel("반평면 잔차");axes[2].set_xlabel("물리시간(s)")
        for ax in axes[1:]:
            handles,labels=ax.get_legend_handles_labels();unique=dict(zip(labels,handles));ax.legend(unique.values(),unique.keys())
        fig.suptitle("ORCA 실제 위반 기록 · 사례 "+str(index+1))
        filename="08_orca_case"+str(index+1)+".png"
        save(fig,figdir/filename,"위반 프레임만 관측 · 기록 공백은 연결하지 않음 · 선호 속도는 기존 로그에서 N/A")
        sample=g.iloc[np.unique(np.linspace(0,len(g)-1,min(len(g),300)).astype(int))].copy()
        sample["orca_output_velocity"]=sample.orca_output_velocity.map(json.loads)
        sample["actual_newton_velocity"]=sample.actual_newton_velocity.map(json.loads)
        cases.append({"run_id":rid,"figure":filename,"frames":len(g),"samples":json.loads(sample.to_json(orient="records")),
                      "note":"표시용 최대300개 관측 프레임; 전체 기록은 CSV"})
    (out/"orca_cases.json").write_text(json.dumps(cases,ensure_ascii=False,indent=2))
    layouts=pd.read_csv(out/"warehouse_layout_analysis.csv");runs=pd.read_csv(out/"warehouse_planner_runs.csv")
    fig,axes=plt.subplots(1,2,figsize=(11,4.5))
    axes[0].bar(layouts["map"],layouts.shortest_grid_path_length_m,color="#0f766e")
    axes[0].set(title="맵별 최단 격자 경로",ylabel="길이(m)")
    for i,(p,label) in enumerate((("astar","A*"),("dijkstra","Dijkstra"),("rrt","RRT"))):
        s=runs[runs.planner==p].groupby("map").planning_time_ms.agg(["mean","std"])
        axes[1].errorbar(s.index,s["mean"],yerr=s["std"],marker="o",capsize=3,label=label)
    axes[1].set(title="기존 탐색기의 실제 계산시간",ylabel="시간(ms)",yscale="log");axes[1].legend()
    save(fig,figdir/"09_layout_planning.png","A*/Dijkstra 0.5m 격자 · RRT 최단성 보장 없음 · 시드42/43/44")
    scenes=read_json(out/"warehouse_layout_scenes.json")
    from matplotlib.patches import Polygon
    for scene in scenes:
        fig,ax=plt.subplots(figsize=(7,5))
        for poly in scene["polygons"]:ax.add_patch(Polygon(poly,facecolor="#64748b",edgecolor="#334155"))
        path=np.array(scene["paths"]["astar"]);ax.plot(path[:,0],path[:,1],color="#2563eb",label="A* 경로")
        config=scene["config"];ax.scatter(*config["robotSpawnPosition"],color="#0f766e",marker="s",label="출발");ax.scatter(*config["goalPosition"],color="#16a34a",marker="*",label="목표")
        ax.set(xlim=(0,38),ylim=(0,26),xlabel="X(m)",ylabel="Y(m)",title=config["mapName"]);ax.set_aspect("equal");ax.legend()
        save(fig,figdir/("10_layout_"+scene["map"]+".png"),"실제 선반 위치·회전과 기존 A* 결과 · 반경0.42m/안전 여유0.35m")
    return cases

def supplement_figures(out):
    setup();out=Path(out);d=pd.read_csv(out/"supplemental_analysis.csv");files=[]
    for p in ("workers","mixed"):
        g=d[(d.population_mode==p)&d.encounter_mode.eq("crossing")]
        fig,axes=plt.subplots(1,2,figsize=(10,4.5))
        for a,color in C.items():
            x=g[g.algorithm==a].sort_values("agent_count")
            axes[0].plot(x.agent_count,x.algo_time_median_ms,color=color,marker="o",label=NAMES[a]+" 중앙값")
            axes[0].plot(x.agent_count,x.algo_time_p95_ms,color=color,linestyle="--",marker="x",label=NAMES[a]+" P95")
            axes[1].plot(x.agent_count,(x.constraint_evaluations+x.lp_pair_evaluations)/x.algo_steps,color=color,marker="o",label=NAMES[a])
        axes[0].set(yscale="log",title="프레임 계산시간 중앙값/P95",ylabel="ms/프레임")
        axes[1].set(title="실제 반평면 검사(외부+LP 내부)",ylabel="회/프레임")
        for ax in axes:ax.set_xlabel("에이전트 수");ax.set_xticks([2,4,8,16]);ax.legend(fontsize=7)
        filename="11_supplement_"+p+".png"
        save(fig,out/"figs"/filename,"별도 보완 계측 · seed42 한 번 · 프레임들은 독립 반복 표본이 아니므로 CI 없음")
        files.append(filename)
    return files
