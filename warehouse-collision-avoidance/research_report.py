"""Generate the research report, presentation summary and dashboard strictly from derived measured tables."""
from __future__ import annotations
from datetime import datetime,timezone
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research_data import ROOT,inputs,read_json,assert_originals

TITLE="창고 환경의 동적 장애물 밀집도에 따른 자율주행 로봇 충돌 회피 알고리즘 비교 분석"
ENGLISH="Comparative Analysis of Collision Avoidance Algorithms for Autonomous Mobile Robots under Dynamic Obstacle Density in Warehouse Environments"
def records(df):return json.loads(df.to_json(orient="records",double_precision=12))
def num(v,d=3):return "N/A" if v is None or pd.isna(v) else f"{v:.{d}f}"

def build(out):
    out=Path(out);audit=read_json(out/"audit.json")
    assert_originals(audit)
    main,pilot=inputs()
    alg=pd.read_csv(out/"algorithm_comparison.csv");scenarios=pd.read_csv(out/"scenario_comparison.csv")
    scale=pd.read_csv(out/"scalability_analysis.csv");layouts=pd.read_csv(out/"warehouse_layout_analysis.csv")
    paired=pd.read_csv(out/"paired_comparisons.csv");orca=read_json(out/"orca_summary.json")
    supplement=pd.read_csv(out/"supplemental_analysis.csv") if (out/"supplemental_analysis.csv").exists() else pd.DataFrame()
    # Link measured single-seed percentiles/counters without representing them as 10-seed historical estimates.
    if len(supplement):
        scale=scale.loc[:,~scale.columns.str.startswith("supplemental_seed42_")].copy()
        crossing=supplement[supplement.encounter_mode=="crossing"]
        keys=["run_id","algo_time_median_ms","algo_time_p95_ms","algo_time_max_ms","constraint_evaluations",
              "lp_pair_evaluations","lp_iterations","constraint_violation_count","robot_stop_time_s"]
        extra=crossing[["population_mode","agent_count","algorithm",*keys]].rename(
            columns={"population_mode":"population",**{k:"supplemental_seed42_"+k for k in keys}})
        scale=scale.merge(extra,on=["population","agent_count","algorithm"],how="left",validate="one_to_one")
        scale.to_csv(out/"scalability_analysis.csv",index=False,na_rep="N/A")
    unique=main.drop_duplicates(["algorithm","scene_hash"])
    sensitivity=unique.groupby("algorithm").agg(runs=("run_id","size"),goals=("success","sum"),
                   collision_free=("collision_free_success","sum"),safe=("safe_success","sum")).reset_index()
    sensitivity.to_csv(out/"physical_scene_sensitivity.csv",index=False)
    lines=["# "+TITLE,"\n"+ENGLISH,"\n생성 시각: "+datetime.now(timezone.utc).isoformat(),
      "\n## 1. Introduction",
      "\n작업자와 AMR이 혼재하는 창고에서 지역 충돌 회피의 안전성·이동 효율·계산 비용을 비교한다. "
      "목표 도달과 안전 도달을 구분하고 입력 크기에 따른 성능 변화를 검증한다. "
      "기존 완료 실험240회를 주 분석으로 재사용하며 추가 계측은 별도 실행으로 관리했다.",
      "\n## 2. Related Work",
      "\nNaive는 본 프로젝트의 현재 거리 기반 감속·반발 기준선이다. 미래 위치를 예측하지 않는다. "
      "[Fiorini와 Shiller(1998)](https://www.ariel.ac.il/sites/shiller/papers/fiorini98motion.pdf)의 VO는 "
      "상대 운동에서 충돌을 유발하는 속도 집합을 다룬다. 본 구현은 예측 시간3초와74개 후보를 검사하는 표본 기반 방식이다.",
      "\n[van den Berg 등(2011)의 ORCA](https://gamma-web.iacs.umd.edu/ORCA/)는 상호 책임 분담과 속도 반평면을 사용한다. "
      "현재 작업자·추가 AMR은 비협조적 순찰이어서 R0이 책임100%를 부담한다. 해당 구현을 표준 협조형 ORCA 전체의 성능으로 해석하지 않는다.",
      "\n창고의 전역 경로는 [Hart·Nilsson·Raphael(1968)](https://ai.stanford.edu/~nilsson/OnlinePubs-Nils/PublishedPapers/astar.pdf)의 "
      "A* 개념을 이용한 기존0.5m 격자 탐색을 공통 사용한다. Dijkstra는 같은 격자 최단 길이 검증, RRT는 별도 경로 탐색 계측에 활용했다.",
      "\n## 3. Methodology",
      "\nNewton1.7.0/Warp1.19.0 CPU 강체,30Hz 회피 업데이트·프레임당2물리 서브스텝, XPBD8반복이다. "
      "R0 반경0.42m, 최대속도1.2m/s, 안전 여유0.35m이며 힘 제어가 목표 속도를 추종한다. "
      "실험은 Map1/A*/동적 순찰, workers/mixed, n=2/4/8/16, 시드42~51,5400프레임 한도다. n은 R0을 제외한다. "
      "n=12는 기존 데이터 재사용을 위해 추가하지 않았다. mixed는4번째마다 AMR로 n=2에서 workers와 같은 물리 구성이 된다.",
      "\n회피 Runtime은 choose_velocity 본문 주변 perf_counter_ns 구간이다. 전역 탐색·물리·렌더링·감사/통계 비용은 제외한다. "
      "기존240회에는 평균/최악만 있어 프레임 중앙값·P95·정지 시간·LP 내부 검사·선호 속도는 N/A다. "
      "30회 단일 시드 보완 계측을 따로 저장했다. 추가 카운터 비용이 포함되므로 새 Runtime을 기존240회와 합치지 않는다.",
      "\n도달은 목표0.25m 이내 및 실제속력0.02m/s 이하, 무충돌 도달은 도달+바닥 제외 접촉0회, "
      "안전 도달은 무충돌+동적/정적 안전거리 위반0 및 최소 이격 기준이다. "
      "동적 최소 거리는 프레임 상대 이동의 선형 보간, 정적 거리는 끝점XY 거리다. 실제3D 접촉은 Newton 버퍼로 별도 집계한다. "
      "미도달 도착시간은 N/A, 경로 길이와 비용은 실패 실행도 포함한다. 재탐색은 구현상0회다.",
      "\n통계는 시드 전체를 묶어3000회 군집 부트스트랩한다. 같은 시드의 n·집단·알고리즘 관측을 함께 재표집하여 의존성을 보존한다. "
      "짝지은 차이는 동일 맵/만남/인구/n/시드/scene_hash끼리 A-B로 계산한다. "
      "도착시간 차이는 양쪽 도달 실행만 사용하므로 선택 편향 가능성이 남는다. 효과 크기dz는 시드별 차이 평균/표준편차이며 분산0이면 N/A다. "
      "80개 실행/알고리즘은80개 독립 시드가 아니며 독립 시드 묶음은10개다. 표본2개인 예비 시나리오의 구간은 불확실성이 크다.",
      "\n## 4. Experiments",
      "\n주 분석240회와 예비18회를 원본·설정·완료 마커·마지막 실제 물리 상태와 대조했다. "
      "세 알고리즘의80개 논리 조건은 모두 동일 초기 상태 해시이며 누락·중복·설정 불일치가 없다. "
      "과거142개 테스트 기록은 /tmp/newton-enhanced-final-tests.log 및 프로젝트 개발로그에 남아 있으며 이번 테스트는 별도 검증 기록에 보존한다.",
      "\nHead-On/Crossing/Narrow Passage 비교는 n=4 workers,2시드,2400프레임 예비18회를 쓴다. "
      "Dense Traffic은 기존Crossing의 n=8/16·두 집단120행 부분집합이며 새로운 독립120회가 아니다. "
      "서로 다른 시나리오의 인구·예산 차이를 무시한 난이도 순위나 검정은 하지 않는다. "
      "밀집은 본 프로젝트의 경로 주변 충돌 기회 증가를 뜻하며 실제 창고 전역의 보편적 군중 밀도 등급은 아니다.",
      "\n6개 맵은 동일 시작·목표·반경/여유로 실제 장애물과 기존 탐색기를 사용했다. "
      "장애물 점유는 회전 직사각형 면적의 합, 통행 영역은0.25m 격자의 보호 원형 중심 허용 비율이다. "
      "최소 통로 폭은 START와 연결된 영역에서 보호 반경을 수용하는 선반/벽 경계쌍 간격을0.25m로 샘플링한 운영적 지표다. "
      "연속 기하의 전역 최소 폭이라고 주장하지 않는다. 별도 열의 선택 경로 clearance 직경과도 구분한다. "
      "최단 길이는0.5m의 보수적인8이웃 격자 기준이며 연속 공간 최단 길이가 아니다. RRT는 최단성을 보장하지 않는다.",
      "\n## 5. Results",
      f'\n재집계: 도달{audit["totals"]["success"]}/240, 무충돌{audit["totals"]["collision_free_success"]}/240, 안전{audit["totals"]["safe_success"]}/240. 보고된227/152/53과 일치한다.',
      "\n|Algorithm|Goal Success|Collision-Free|Safe Success|Collision(평균/실행)|Path Length(m, 전체)|Runtime(ms/프레임)|",
      "|---|---|---|---|---|---|---|"]
    for _,r in alg.iterrows():
        lines.append(f'|{r.algorithm}|{int(r.success_count)}/{r.total_runs} ({r.success_rate_pct:.2f}%)|'
            f'{int(r.collision_free_success_count)}/{r.total_runs} ({r.collision_free_success_rate_pct:.2f}%)|'
            f'{int(r.safe_success_count)}/{r.total_runs} ({r.safe_success_rate_pct:.2f}%)|'
            f'{num(r.collision_count_mean)}|{num(r.path_length_m_mean)}|{num(r.algo_time_avg_ms_mean,5)}|')
    lines+=["\n세부 지표의 평균·중앙값·표준편차·최소/최대·95% 구간은 algorithm_comparison.csv에 있다. "
            "모든 도달률 분모는80이다. 최종 물리 상태 재검증에서도 같은 성공 건수를 얻었다.",
            "\n### 짝지은 차이와 효과 크기",
            "\n|차이 A-B|지표|평균 차이|95% 군집 구간|유효 짝|시드 묶음|시드 수준 dz|",
            "|---|---|---|---|---|---|---|"]
    for _,r in paired[paired.metric.isin(["success","safe_success","arrival_time_s","algo_time_avg_ms"])].iterrows():
        lines.append(f'|{r.algorithm_a}-{r.algorithm_b}|{r.metric}|{num(r.mean_difference,5)}|'
                     f'[{num(r.ci95_low,5)}, {num(r.ci95_high,5)}]|{r.paired_observations}|{r.seed_clusters}|{num(r.paired_cohen_dz_seed_level)}|')
    lines+=["\n성공 플래그 차이는0~1 비율 단위(×100하면%p)다. 동일 물리 장면을 중복한 n=2 집단을 제거한 민감도 집계는 physical_scene_sensitivity.csv에 따로 기록했다."]
    lines+=["\n### 시나리오별 실제 관측",
            "\n|시나리오|알고리즘|도달|무충돌 도달|안전 도달|충돌 평균|최소 이격 평균(m)|",
            "|---|---|---|---|---|---|---|"]
    for _,r in scenarios.iterrows():
        lines.append(f'|{r.scenario_label}|{r.algorithm}|{r.success_count}/{r.total_runs}|'
                     f'{r.collision_free_success_count}/{r.total_runs}|{r.safe_success_count}/{r.total_runs}|'
                     f'{num(r.collision_count_mean)}|{num(r.min_separation_m_mean)}|')
    if len(supplement):
        lines+=["\n별도 시드42 계측(주 분석과 합산하지 않음): 반응은 선호 속도와 출력의 차이>0.05m/s·이웃4m 이내, "
                "감속은 실제속력>0.2m/s 이후 가속도<-0.1m/s²·이웃4m 이내의 첫 관측이다. "
                "이 정의는 인과적 회피 반응을 보장하지 않으며 절대 시뮬레이션 시각이다.",
                "\n|시나리오|알고리즘|도달|접촉|actor0 정면 접촉|반응(s)|감속(s)|정지(s)|",
                "|---|---|---|---|---|---|---|"]
        for _,r in supplement[supplement.encounter_mode!="crossing"].iterrows():
            lines.append(f'|{r.scenario_label}|{r.algorithm}|{r.success}|{r.collision_count}|'
                         f'{num(r.head_on_actor0_contact_count,0)}|{num(r.avoidance_response_s)}|'
                         f'{num(r.deceleration_onset_s)}|{num(r.robot_stop_time_s)}|')
        lines.append("\nHead-On의 전체 접촉과 actor0 접촉을 구분한다. "
                     "Narrow Passage의 교행 성공은 무충돌 도달로 정의하며 목적지에 도달해도 접촉이 있으면 실패다. "
                     "작업자의 실제 경로 보호대 진입 시각, 출발 명령 시각, 중앙 횡단 시각은 supplemental_analysis.csv의 "
                     "actor_path_band_entry_s/actor_release_command_s/actor_first_crossing_s에 기록했다. "
                     "좁은 통로 폭은 각 신규 실행 configuration.json의 encounter.passage_width_m과 로봇 지름0.84m를 함께 확인한다.")
    lines+=["\n### 알고리즘별 장단점과 비용",
            "\n|알고리즘|이 데이터에서 관측된 특성|해석 한계|",
            "|---|---|---|",
            "|Naive|평균 회피 계산 비용이 가장 작지만 도달·무충돌·안전 도달이 모두 부족했다.|현재 위치 반응으로 선반 근처 정지·접촉이 가능하다.|",
            "|VO|주 분석 도달80/80·안전38/80이며 평균 회피 비용이 가장 컸다.|후보74개 검사 비용, 표본 밖 속도·비협조적 밀집·물리 제어 한계가 있다.|",
            "|ORCA|주 분석 충돌 평균은 가장 작았지만 안전 도달3/80으로 가장 낮았다.|접촉 최소화와 안전거리 준수는 다른 지표다. 순차 제약의 불가능·추종 오차가 남는다.|",
            "\n표의 순위는 이 맵·시드·설정에 관한 관측이며 전체 알고리즘 계열의 보편적 우월성을 뜻하지 않는다."]
    lines+=["\n### ORCA 위반 근거",
            f'\n감사{orca["frames"]}프레임: A={orca["categories"].get("A",0)}, B={orca["categories"].get("B",0)}, '
            f'D={orca["categories"].get("D",0)}, E={orca["categories"].get("E",0)}. '
            "C는 비협조적 움직임이라는 조건만으로 인과 원인을 확정하지 않았으며 E에 가능한 후보를 별도 표시했다.",
            "\n독립적2D 원판/반평면 교차 검사는 꼭짓점·경계/원 교점과 내부 후보를 검사했다. "
            "주어진 제약에 허용 속도가 없는D와, 해가 있는데 출력이 어긋난A를 구분한다. 실제 기록에서A 오류는 확인되지 않아 회피 알고리즘을 교체하지 않았다. "
            "B는 출력은 제약을 만족하지만 후속 실제 속도가 벗어나는 근거로, 물리 추종·프레임 중 조건 변화가 함께 작용할 수 있다. "
            "기존 preferred velocity와 정확한 제약 생성 시점의 작업자 상태는 N/A로 남기고 상대 위치/속도는 관측 후시점임을 명시했다.",
            "\n### 6개 맵",
            "\n|맵|점유율%|보호 중심 통행율 추정%|격자 최단(m)|우회율|통행 가능 최소 간격(m)|회전 수|확장 노드|",
            "|---|---|---|---|---|---|---|---|"]
    for _,r in layouts.iterrows():
        lines.append(f'|{r["map"]}|{100*r.obstacle_occupancy_ratio:.3f}|{100*r.protected_traversable_ratio_estimate:.3f}|'
                     f'{num(r.shortest_grid_path_length_m)}|{num(r.detour_ratio)}|{num(r.minimum_passable_gap_m)}|{r.turning_count}|{r.expanded_nodes}|')
    lines+=["\n모든 맵의 점유율은같다. Map4는 측정 격자 경로가 가장 길고 Map6은 해당 A* 경로의 방향 전환 수가 가장 많았다. "
            "Map1과Map5의 기준 최단 경로는같아 해당 지표만으로 두 맵의 난이도 차이를 입증하지 못했다.",
            "\n## 6. Discussion",
            "\n알고리즘별 도달·안전성과 계산 비용의 실제 비교는 위 분자/분모 및 짝지은 차이에 근거한다. "
            "안전 결과는 계산 비용이나 이론적 이름만으로 결정되지 않는다. "
            "가속도/속도 추종 지연·비협조적 순찰·정적 장애물의 지역 속도 제약 부재·교착성 정지와 표본화가 영향을 줄 수 있다. "
            "혼합16개 조건에서는 세 방식 모두 안전 도달0/10이었다. 따라서VO를 모든 조건에서 안전한 방식이라고 결론 내리지 않는다.",
            "\n현재 구현 기준: Naive O(n), VO O(Kn), K=74; ORCA 제약생성O(n)·순차 투영 최악O(n²). "
            "모든 ORCA 구현의 일반적인 평균/최악 복잡도를 의미하지 않는다. 공간 인덱스는 없고 이웃 제한을 켜면 필터/정렬 비용이 추가된다. "
            "실제 조기 종료·LP 투영 빈도·Python/NumPy 비용·CPU 부하·캐시와 입력 분포 때문에 Runtime 곡선은 Big-O와 다르다. "
            "기존카운터는 LP 내부 쌍 검사를 포함하지 않으므로 새로운 단일 시드 계측을 별도 제시했다.",
            "\n개발 서버 실측이며 전용CPU 고정 환경은 아니다. 단일 맵의주 분석, 비협조적 인구,10시드, 예비 시나리오2시드, "
            "강체의 평면 원형 거리 근사, 정적 간격 샘플링, 도착시간의 성공 조건부 선택이 한계다. "
            "프레임 관측을 독립 반복으로 세지 않았으며 특수상황의 무충돌 보장을 증명하지 않는다.",
            "\n## 7. Conclusion",
            "\n목표 도달과 안전 도달은 크게 달랐고, 알고리즘의 비용·도달률·안전성 사이에 실측 상충 관계가 나타났다. "
            "단일 최고 알고리즘이라는 결론 대신 조건별 표와 불확실성을 제시했다. 후속 연구는 정적 속도 제약, 가속도/추종 동역학을 반영한 회피, "
            "협조/비협조 대조, 독립 시드 확대와 추가 맵 주행이다. 온라인 재탐색은 현재 비교와 분리해 평가해야 한다.",
            "\n## 부록: 데이터·코드·재현성",
            f'\n작업 공간 브랜치={audit["git"]["branch"]}, HEAD={audit["git"]["head"]}. '
            "원격은 WIZ 샘플 프로젝트이며 Robot 저장소와 구분한다. 미커밋 변경은 audit.json에 기록했다.",
            "\n공개 Robot 스냅샷: "+str(audit["github"])+". 해당240회 배치 경로는 공개 트리에 없었다. "
            "로컬 원본을 삭제/대체하거나 공개 저장소에 자동 푸시하지 않았다.",
            "\n실험별 메타데이터는 dirty 작업 공간 HEAD 및 소스 해시를 기록한다. 기존 실행에서 알고리즘·엔진의 핵심 해시는 단일 버전이었고, "
            "실행기/저장/분석 파일 일부 해시는여러 버전이었다. 깨끗한 단일 Robot 커밋으로 전체 결과가 생성되었다고 주장하지 않는다.",
            "\n재현: .venv/bin/python research_pipeline.py --supplement . 기존240회가 없으면 --primary/--pilot로 실제 원본을 지정하거나 controlled_study.py를 새 배치로 실행한다. "
            "원본이 없으면 연구 수치를 생성하지 않고 missing 상태로 종료한다.",
            "\n파일: algorithm_comparison.csv, scenario_comparison.csv, scalability_analysis.csv, warehouse_layout_analysis.csv, orca_failure_analysis.csv, paired_comparisons.csv, supplemental_analysis.csv, audit.json. "
            "원본SHA256은 완료 전에 재검증한다. 신규 계측 소스 스냅샷·30개 새ID는이 연구 폴더 안에만 보존된다."]
    report="\n".join(lines)
    (out/"research_report.md").write_text(report)
    presentation=["# 발표용 핵심 결과",
        "- 연구 질문: 안전성·이동 효율·계산 비용은 알고리즘과 장애물 수에 따라 어떻게 바뀌는가?",
        f'- 원본 재검증: 목표{audit["totals"]["success"]}/{len(main)}, 무충돌{audit["totals"]["collision_free_success"]}/{len(main)}, 안전{audit["totals"]["safe_success"]}/{len(main)}.']
    for _,r in alg.iterrows():
        presentation.append(f'- {r.algorithm}: 목표{r.success_count}/{r.total_runs}, 안전{r.safe_success_count}/{r.total_runs}, 평균 회피{num(r.algo_time_avg_ms_mean,5)}ms.')
    presentation += [
        "- 단일 최고 알고리즘으로 일반화하지 않고 조건별 결과를 제시한다.",
        "- 같은 시드의 구성/프레임을 독립 표본으로 부풀리지 않고 시드 단위로 짝지어 비교한다.",
        f'- ORCA 분류: {orca["categories"]}. C는 원인 확정이 아닌 후보로 남긴다.',
        "- 맵 점유율·경로 우회·회전 수의 실제 지표로 설명한다.",
        "- 기존 P95/정지 시간은 미측정으로 표시하고 별도 계측은 주 분석과 혼합하지 않는다.",
        "- 공개 GitHub 상태와 로컬 작업 공간·소스 해시를 구분한다."]
    presentation="\n".join(presentation)+"\n"
    (out/"presentation_summary.md").write_text(presentation)
    figures=[p.name for p in sorted((out/"figs").glob("*.png"))]
    bundle={"schema":1,"id":out.name,"status":"complete","title":TITLE,"english_title":ENGLISH,
            "audit":{k:v for k,v in audit.items() if k not in ("original_sha256","source_versions","git")},
            "algorithms":records(alg),"scenarios":records(scenarios),"scalability":records(scale),"layouts":records(layouts),
            "paired":records(paired),"orca_summary":orca,"orca_cases":read_json(out/"orca_cases.json"),
            "supplement":records(supplement) if len(supplement) else [],"figures":figures,
            "statistical_method":read_json(out/"statistical_method.json"),
            "supplement_runs":len(supplement),"report":"research_report.md"}
    (out/"dashboard.json").write_text(json.dumps(bundle,ensure_ascii=False,allow_nan=False))
    return bundle
