"""Summarize actual controlled-study measurements and archived ORCA evidence."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import pandas as pd
from newton_results import ROOT


def wilson(k,n):
    z=1.959963984540054
    p=k/n;denominator=1+z*z/n
    centre=(p+z*z/(2*n))/denominator
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return (0. if k==0 else max(0.,100*(centre-radius))), (100. if k==n else min(100.,100*(centre+radius)))


def analyze(folder):
    folder=Path(folder)
    df=pd.read_csv(folder/"measurements.csv")
    paired=df.groupby(["map","encounter_mode","population_mode","agent_count","seed"])
    for _,g in paired:
        if g.algorithm.nunique()==3 and g.scene_hash.nunique()!=1:
            raise ValueError("짝지은 실험의 초기 상태가 다릅니다.")
    rows=[]
    for keys,g in df.groupby(["map","encounter_mode","population_mode","agent_count","algorithm"]):
        row=dict(zip(["map","encounter","population","n","algorithm"],keys))
        row["runs"]=len(g)
        for key in ("success","collision_free_success","safe_success"):
            row[key+"_pct"]=100*g[key].mean()
            lo,hi=wilson(int(g[key].sum()),len(g))
            row[key+"_ci95_low"],row[key+"_ci95_high"]=lo,hi
        for key in ("arrival_time_s","path_length_m","collision_count","safety_violation_count",
                    "static_safety_violation_count","min_separation_m","algo_time_avg_ms","algo_time_max_ms"):
            row[key+"_mean"]=g[key].mean()
            row[key+"_std"]=g[key].std()
            row[key+"_samples"]=int(g[key].notna().sum())
        for key in ("neighbor_checks","candidate_checks","constraints"):
            values=g[key]/g.algo_steps
            row[key+"_per_step_mean"]=values.mean()
            row[key+"_per_step_std"]=values.std()
        rows.append(row)
    summary=pd.DataFrame(rows)
    summary.to_csv(folder/"safety_summary.csv",index=False)
    tags=Counter(); tracking_errors=[]; target_violations=0; static_only=0
    for run_id in df[df.algorithm=="ORCA"].run_id:
        path=ROOT/"runs"/run_id/"orca_diagnostics.jsonl"
        for line in path.read_text().splitlines():
            event=json.loads(line)
            tags[event["hypothesis"]]+=1
            tracking_errors.append(event["tracking_error_mps"])
            target_violations+=int(event["max_target_constraint_residual"]>event["tolerance"])
            static_only+=int(not event["safety_neighbors"] and not event["collisions"])
    audit={"hypothesis_frame_counts":dict(tags),"target_constraint_violation_frames":target_violations,
           "static_risk_only_frames":static_only,
           "tracking_error_mean_mps":sum(tracking_errors)/len(tracking_errors) if tracking_errors else None,
           "tracking_error_max_mps":max(tracking_errors,default=None),
           "interpretation":"가설 분류이며 원인 증명이 아님. static_risk_only는 동적 위반/접촉 없이 정적 안전거리만 위반한 프레임."}
    (folder/"orca_audit_summary.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    text=["# 통제 실험 실측 요약",f"\n실행 {len(df)}회. 도달시간은 성공 실행만, 다른 지표는 실패를 포함해 집계한다.",
          "\n|맵/만남/집단|n|방식|실행 수|도달률%|무충돌 도달률%|안전 도달률%|도달시간 평균±표준편차(s)|회피시간 평균±표준편차(ms)|",
          "|---|---|---|---|---|---|---|---|---|"]
    def value(x):return "N/A" if pd.isna(x) else f"{x:.4f}"
    for _,r in summary.iterrows():
        text.append(f'|{r["map"]}/{r.encounter}/{r.population}|{r.n}|{r.algorithm}|{r.runs}|'
                    f'{r.success_pct:.1f}|{r.collision_free_success_pct:.1f}|{r.safe_success_pct:.1f}|'
                    f'{value(r.arrival_time_s_mean)} ± {value(r.arrival_time_s_std)}|'
                    f'{value(r.algo_time_avg_ms_mean)} ± {value(r.algo_time_avg_ms_std)}|')
    text+=["\n각 도달률의95% Wilson 구간, 실패 제외 도달시간 표본 수, 개별 안전 지표와 카운터는 safety_summary.csv에 보존한다.",
           "\n## 입력 크기와 계산량"]
    for (m,e,p,a),g in summary.groupby(["map","encounter","population","algorithm"]):
        g=g.sort_values("n");first,last=g.iloc[0],g.iloc[-1]
        ratio=last.algo_time_avg_ms_mean/first.algo_time_avg_ms_mean
        exponent=(math.log(ratio)/math.log(last.n/first.n)) if last.n>first.n and ratio>0 else None
        text.append(f'- {m}/{e}/{p}/{a}: n={first.n}→{last.n}, 평균 회피시간 {ratio:.2f}배, '
                    f'끝점 기준 경험적 지수 {value(exponent)}. 이 값은 Big-O의 증명이 아니다.')
    text+=["\n## ORCA 감사","\n```json",json.dumps(audit,ensure_ascii=False,indent=2),"```",
           "\n목표는 제약을 만족하지만 실제 속도가 벗어난 프레임은 추종 오차의 근거다. "
           "정적 장애물은 ORCA 반평면에 포함되지 않으므로 정적 접근을 비협조적 작업자의 영향으로 단정하지 않는다. "
           "비협조적 순찰과 제약 불가능, 물리 제어 지연을 함께 해석해야 한다.",
           "\n실행별 결과/설정/초기 상태/코드 해시·의존성은 results/newton/runs/<run_id>/에 있다. "
           "현 비교의 전역 탐색은A*이고 온라인 재탐색은 사용하지 않는다."]
    (folder/"report.md").write_text("\n".join(text))
    print(summary.to_string(index=False))
    print(json.dumps(audit,ensure_ascii=False,indent=2))
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("folder",type=Path);args=p.parse_args();analyze(args.folder)
