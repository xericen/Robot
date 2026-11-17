# 충돌 회피 통제 실험 보강 결과

리뷰 ID: ssblbvzaiguanzwntrpqgkbxmiyweitr · 2026-11-17

## 구현한 보완 사항

| 항목 | 구현 |
|---|---|
| 만남 조건 | 정면 접근·횡단·Map1 2.8m 교행. 실제 장애물·내비게이션과 시각화 일치 |
| 인구 수 통제 | workers/mixed 분리, n=2/4/8/16, R0 제외 |
| 시드 | 위치·속도·출발 지연에 영향. 같은 집단에서 기존 에이전트의 초기 조건을 유지하며 n 증가 |
| 안전 지표 | 도달·무충돌 도달·안전 도달, 동적/정적 최소 이격과 위반을 분리 |
| ORCA 감사 | 위반 프레임의 위치·속도·반평면·목표/실제 잔차·추종 오차·폴백 저장 |
| 보존 | 실행 ID별 결과·초기 상태·설정·소스 해시·의존성, 이전 최신 사본 및 중단 재개 |
| 복잡도 | 프레임당 카운터와 Runtime 그래프, 경험적 증가 추세와 구현 이론의 구분 |
| 웹 | 환경 설정·실행 이력·새 안전 지표·완료 배치 요약표와 그래프 조회 |

기존 Pygame 예비 결과와 Newton 기준 실험은 유지했다. 좁은 교행 시험은 Map1 전용이며 나머지 만남 조건의 생성은6개 맵에서 검사했다. 다른 에이전트끼리의 회피나 온라인 재탐색을 새로 추가하지 않았으며, 동일 전역 탐색A*와 물리 제어기로 지역 회피 차이를 비교했다.

## 실제 수행 및 검증

- 본 실험 **240/240회**: Map1, A*, 동적 순찰, 2집단 × 4단계 × 3방식 × 시드42~51(10회), 한도5400프레임.
- 80개 논리적 조건에서 세 알고리즘의 scene_hash 일치, 조건당10회 및 중복 없는240개 실행 ID 확인.
- 예비 만남 실험 **18회**: 3시나리오 × 3방식 × 2시드, n=4 작업자, 한도2400프레임. 본 실험과 별도 배치다.
- 통제 재현성 **18회**: 9조합 × 2회, seed42·600프레임. 초기 상태·상태·물리시간·거리·충돌·안전 지표 완전 일치. 이 짧은 검증의 종료 상태를 장시간 목표 도달 검증으로 해석하지 않는다.
- 전체 pytest **142개 통과**, 후속 교통/보존 검사 **28개 통과**(기존 검사와 중복 포함). Viser/pytest 플러그인의 사용중단 경고는 있었으나 실패는 없다.
- WIZ 빌드 성공. 신규 이미지 경로 추가 시 클린 빌드로 등록한 후 실제PNG 응답을 확인했다.
- 실제 브라우저: 2회 실행의6개 ID 보존·동일 해시·재조회, baseline 복귀, 좁은 교행8장애물/4에이전트·라이브 조건 전환, 요약표24행·그래프18개·기존 비교 재조회·미도달N/A 검증.
- 기존 Pygame CSV의 작업 전후 SHA256 동일. 기존 figures도 수정하지 않았다.

## 본 실험 요약

전체 도달 **227/240**, 무충돌 도달 **152/240**, 안전 도달 **53/240**이다. 목표에 도달했다고 안전한 실행으로 처리하지 않는다.

아래는 n=16의 결과이며 각 행은10개 시드다. 안전 도달은 충돌0·동적/정적 안전거리 위반0과 최소 이격거리 조건을 모두 만족해야 한다.

| 집단 | 방식 | 도달률% | 무충돌 도달률% | 안전 도달률% | 평균 회피시간(ms) |
|---|---|---|---|---|---|
| 혼합 | Naive | 60.0 | 30.0 | 0.0 | 0.05724 |
| 혼합 | ORCA | 80.0 | 20.0 | 0.0 | 0.23444 |
| 혼합 | VO | 100.0 | 30.0 | 0.0 | 4.29905 |
| 작업자 전용 | Naive | 80.0 | 50.0 | 0.0 | 0.05665 |
| 작업자 전용 | ORCA | 100.0 | 50.0 | 0.0 | 0.22435 |
| 작업자 전용 | VO | 100.0 | 50.0 | 20.0 | 4.13322 |

모든 n에 대한 평균·표본 표준편차·성공한 도달시간 표본 수·95% Wilson 구간은 [본 실험 보고서](../results/newton/studies/20261117T094214513880Z_fc56a91c/report.md)와 [수치CSV](../results/newton/studies/20261117T094214513880Z_fc56a91c/safety_summary.csv)를 참조한다. n=2의 mixed는 다른 AMR이0대여서 workers와 같은 구성이다. 단일 맵·비협조적 순찰·10시드의 결과를 일반적인 알고리즘 우열로 확대하지 않는다.

## ORCA 분석

본 실험의 ORCA 위반/접촉 프레임 감사에서 physical_tracking_error 후보 **4182프레임**, infeasible_constraints **4531프레임**을 기록했다. 목표 속도가 제약을 만족하지만 실제 속도가 벗어나는 사례는 Newton 추종 오차의 근거다.

감사 대상 프레임에서 평균 추종 오차는 **0.5017m/s**, 최대는 **1.4271m/s**다. 동적 위반/접촉 없이 정적 안전거리만 위반한 프레임도 **1318개** 있다. 정적 장애물은 현재 ORCA 반평면에 포함되지 않으므로 모든 위반을 비협조적 작업자 탓으로 돌리지 않는다. 분류는 원인 후보이며 단일 원인을 증명한 것이 아니다.

[감사 집계JSON](../results/newton/studies/20261117T094214513880Z_fc56a91c/orca_audit_summary.json), 실행별 runs/<run_id>/orca_diagnostics.jsonl에 근거를 보존했다. 충돌·위반은 여전히 발생한다. 가속도 제한과 추종 동역학, 정적 장애물 제약은 이후 알고리즘 개선의 대상이며 이번 비교 결과를 안전 보장으로 해석하지 않는다.

## 그래프와 웹 화면

본 실험은 집단별9종, 총18개200dpi PNG다. 예비 실험은 만남 조건별9종, 총27개다.

- [본 실험 그래프·원자료 폴더](../results/newton/studies/20261117T094214513880Z_fc56a91c/figs/)
- [원자료240행](../results/newton/studies/20261117T094214513880Z_fc56a91c/measurements.csv)
- [작업자 전용 계산량/Runtime](../results/newton/studies/20261117T094214513880Z_fc56a91c/figs/map1_crossing_workers/09_complexity.png)
- [혼합 계산량/Runtime](../results/newton/studies/20261117T094214513880Z_fc56a91c/figs/map1_crossing_mixed/09_complexity.png)
- [예비 만남 실험 보고서](../results/newton/studies/20261117T093838421883Z_01843a5b/report.md)
- [웹 본 실험 표](../results/newton/validation/controlled/full-study-results.png)
- [좁은 교행3D](../results/newton/validation/controlled/narrow-3d.png)
- [좁은 교행2D](../results/newton/validation/controlled/narrow-2d.png)
- [이력 조회](../results/newton/validation/controlled/history.png)
- [통제 재현성](../results/newton/validation/controlled/reproducibility.json)

웹 환경 설정에서 만남 조건과 인구 구성을 고른다. 알고리즘 비교의 '실행 이력 포함'으로 이전 실행을 조회한다. 실험 결과 탭의 '통제 실험 배치'에서는 재실행 없이 완료된 수치·그래프를 읽는다. 진행·중단 배치는 완료 결과로 표시하지 않는다. 물리 장면이 열려 있을 때 만남 조건을 바꾸면 새 조건의 정지 상태로 다시 초기화한다.

## 실행 및 보존

```bash
cd warehouse-collision-avoidance
.venv/bin/python controlled_study.py
.venv/bin/python plot_controlled_study.py results/newton/studies/<batch_id>
.venv/bin/python analyze_controlled_study.py results/newton/studies/<batch_id>
.venv/bin/python controlled_study.py --resume results/newton/studies/<batch_id>
.venv/bin/python verify_controlled_reproducibility.py
```

[방법론과 지표 정의](controlled_experiments.md)를 참조한다. 실험 Runtime은 개발 서버에서 측정한 값이며 시스템 부하·캐시·Python 비용의 영향을 받는다. 프레임당 카운터와 실행시간의 증가 추세는 이론적 최악 복잡도의 증명이 아니다.

## 변경 파일

- warehouse-collision-avoidance/newton_warehouse.py
- warehouse-collision-avoidance/algorithms/orca.py
- warehouse-collision-avoidance/newton_results.py
- warehouse-collision-avoidance/encounter_scenarios.py
- warehouse-collision-avoidance/newton_safety.py
- warehouse-collision-avoidance/experiment_archive.py
- warehouse-collision-avoidance/controlled_study.py
- warehouse-collision-avoidance/plot_newton_results.py
- warehouse-collision-avoidance/plot_controlled_study.py
- warehouse-collision-avoidance/analyze_controlled_study.py
- warehouse-collision-avoidance/verify_controlled_reproducibility.py
- warehouse-collision-avoidance/README.md
- warehouse-collision-avoidance/docs/controlled_experiments.md
- warehouse-collision-avoidance/docs/controlled_results.md
- warehouse-collision-avoidance/tests/test_controlled_encounters.py
- warehouse-collision-avoidance/tests/test_orca_audits.py
- warehouse-collision-avoidance/tests/test_controlled_analysis.py
- warehouse-collision-avoidance/tests/test_study_resume.py
- warehouse-collision-avoidance/tests/browser_newton_results.py
- warehouse-collision-avoidance/tests/browser_controlled_encounters.py
- warehouse-collision-avoidance/tests/browser_controlled_results.py
- warehouse-collision-avoidance/tests/browser_narrow_encounter.py
- src/app/page.algorithm.run/api.py
- src/app/page.algorithm.run/view.ts
- src/app/page.algorithm.run/view.pug
- src/app/page.algorithm/view.ts
- src/app/page.algorithm/view.pug
- src/route/warehouse.experiments/app.json
- src/route/warehouse.experiments/controller.py

위 파일과 프로젝트devlog, 실제results/newton 데이터·그래프·검증 자료를 추가/수정했다. 코드 커밋과 배포는 수행하지 않았다.
