# Newton 실측 결과 — 2026-11-17

리뷰 ID: ssblbvzaiguanzwntrpqgkbxmiyweitr

Newton 1.7.0 / Warp 1.19.0 / CPU, Map 1 Standard, A*, 동적 순찰, 기본 5400프레임, 시드42~46. 스윕 60회, 6개 맵 비교18회, 재현성 검증30회를 실제 실행했다. 별도로 30프레임 웹 비교3회를 수행하여 timeout과 사용자 파라미터의 CSV 전달을 검증했다.

## 스윕 수치 요약

값은 시드 5개의 평균 ± 표본 표준편차다. n은 R0 제외. hard는 작업자7명+다른AMR2대로 n=9이다. 모든 조건에서 목표 도달률은 100%였으나 **success는 무충돌을 의미하지 않는다**. 충돌과 안전거리 위반을 별도 평가해야 한다.

| n | 방식 | 도달시간(s) | 거리(m) | 충돌+위반(회) | 성공률(%) | 평균 회피시간(ms) |
|---|---|---|---|---|---|---|
| 2 | Naive | 31.300 ± 0.000 | 33.739 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 0.01866 ± 0.00022 |
| 2 | VO | 30.600 ± 0.000 | 33.093 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 0.91713 ± 0.01721 |
| 2 | ORCA | 30.833 ± 0.000 | 33.080 ± 0.000 | 1.0 ± 0.0 | 100.0 ± 0.0 | 0.04933 ± 0.00081 |
| 4 | Naive | 31.300 ± 0.000 | 33.739 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 0.02542 ± 0.00048 |
| 4 | VO | 30.600 ± 0.000 | 33.093 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 1.50336 ± 0.06934 |
| 4 | ORCA | 30.833 ± 0.000 | 33.080 ± 0.000 | 1.0 ± 0.0 | 100.0 ± 0.0 | 0.07223 ± 0.00172 |
| 9 | Naive | 33.800 ± 0.000 | 35.190 ± 0.000 | 4.0 ± 0.0 | 100.0 ± 0.0 | 0.03989 ± 0.00484 |
| 9 | VO | 31.233 ± 0.000 | 33.656 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 2.74931 ± 0.04132 |
| 9 | ORCA | 31.900 ± 0.000 | 33.200 ± 0.000 | 2.0 ± 0.0 | 100.0 ± 0.0 | 0.12808 ± 0.00128 |
| 16 | Naive | 34.667 ± 0.000 | 33.988 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 0.05369 ± 0.00069 |
| 16 | VO | 33.033 ± 0.000 | 33.227 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 4.74756 ± 0.03795 |
| 16 | ORCA | 32.767 ± 0.000 | 33.221 ± 0.000 | 0.0 ± 0.0 | 100.0 ± 0.0 | 0.20766 ± 0.00402 |

Naive hard: 충돌1회+안전거리 위반3회, ORCA easy/medium: 안전거리 위반1회, ORCA hard: 안전거리 위반2회. VO는 이 스윕에서 충돌·안전거리 위반 모두0회다. 현재 시드 변화가 주 경로의 만남 조건을 크게 바꾸지 않아 일부 물리 지표 표준편차가0이다. 이 결과만으로 일반적인 안전성·우월성을 주장하지 않는다.

## 생성 그래프

- [01_arrival_time.png](../results/newton/figs/01_arrival_time.png)
- [02_path_length.png](../results/newton/figs/02_path_length.png)
- [03_collision_safety.png](../results/newton/figs/03_collision_safety.png)
- [04_success_rate.png](../results/newton/figs/04_success_rate.png)
- [05_algorithm_time.png](../results/newton/figs/05_algorithm_time.png)

각 파일은 1480×900, 200dpi PNG, Noto Sans KR Regular, 한국어 제목·축·범례, 회색 격자, 세 알고리즘별 색상 및 시드 간 표준편차를 사용한다. 계산시간은 로그 y축이다. 모든 그래프의 원자료는 [sweep_agent_count.csv](../results/newton/sweep_agent_count.csv), 수치 요약은 [summary.json](../results/newton/figs/summary.json)이다.

## 실제 개별 CSV 예시

Map1 / ORCA / medium / seed42 / 전체 맵 비교의 공통 작업자 배치 실행이다. 같은 파일명 재실행은 결과를 대체한다. 스윕은 별도 통합 CSV로 보존되어 있다.

```csv
map,algorithm,scenario,seed,agent_count,success,timeout,arrival_time_s,path_length_m,collision_count,safety_violation_count,replan_count,wall_time_s,algo_time_avg_ms,algo_time_max_ms,algo_steps,worker_count,other_robot_count,planner,traffic_mode,common_traffic,frame_limit,observed_time_s,safety_distance_m,max_speed_mps,orca_neighbor_dist_m,orca_max_neighbors,orca_horizon_s,time_step_s,vo_horizon_s,vo_candidates,naive_stop_margin_m,naive_influence_m,newton_version,warp_version
map1,ORCA,medium,42,4,1,0,30.1,32.96354675292969,0,0,0,7.739751060958952,0.06986702657807307,0.287995,903,4,0,astar,dynamic,1,5400,30.1,0.35,1.2,0.0,0,3.0,0.03333333333333333,3.0,74,0.0,1.2,1.7.0,1.19.0
```

## 18조건과 웹 검증

6개 맵 × Naive/VO/ORCA, medium 작업자4명, seed42, 공통 작업자 배치, A*, 동적 순찰, 기본5400프레임으로18개 CSV가 저장되었다. 세 방식 모두 도달했고 이 공통 배치에서는 실제 주행지표가 같았다. 경로 간섭이 적은 공통 작업자 배치여서 회피 알고리즘을 구분하기에 충분히 강한 조건은 아니다. 교차 통행 시점을 통제하는 실험이 다음 개선 대상이다.

브라우저에서 저장 CSV18행, 맵별 그래프6개, 새로고침 후 유지, 파라미터 입력8개를 검증했다. 실제30프레임 비교(seed9001, VO K=11)에서3개 알고리즘의 timeout·도달시간N/A·CSV설정값을 확인했다. 페이지 오류는0개였다.

- [표 화면](../results/newton/validation/persisted-table.png)
- [맵별 그래프](../results/newton/validation/persisted-comparison.png)
- [환경 설정](../results/newton/validation/parameters.png)
- [실제 timeout 화면](../results/newton/validation/real-timeout-table.png)
- [브라우저 검사 결과](../results/newton/validation/browser.json)

## 재현성

Map1/medium/A*에서 세 방식 각각 시드42~46을2회씩 총30회 실행했다. 15/15 조합의 도달시간·반올림 전 경로길이·충돌수가 완전히 같았다. 실행시간은 실측 벽시계이므로 동일 비교에서 제외했다. 5개 시드의 성공률은 각 방식100%, 성공여부 분산0, 충돌수 분산0이었다. [검증 JSON](../results/newton/reproducibility.json)에 물리 스텝·스폰 RNG·연산 순서 관련 코드 근거를 기록했다. 다른 CPU나 라이브러리 버전에 대한 동일성 보장은 아니다.

## 계측 위치와 구현 범위

계측은 `newton_warehouse.py:run`에서 `algorithm.choose_velocity` 직전·직후(341행 부근)이며 `perf_counter_ns` 차이를ms로 환산한다. 아래 세 함수의 계산·진단 카운터·이웃 처리만 포함한다.

- `algorithms/naive.py:NaiveAvoidance.choose_velocity`
- `algorithms/velocity_obstacle.py:VelocityObstacleAvoidance.choose_velocity`
- `algorithms/orca.py:ORCAAvoidance.choose_velocity`

전역 경로 계산은 앞선 `plan`, 물리 계산은 뒤의 두XPBD서브스텝, 렌더링은 `viewer.begin_frame/end_frame`으로 분리되어 있다. 평균·최악·실제호출수가CSV에남는다. 온라인 재탐색이 없어서 replan_count는0이다. ORCA는 비협조적 순찰 대상에 대해 R0이 회피책임100%를 부담하며 표준 상호협조형과 조건이 다르다.

기본 공간 인덱스 없음: Naive O(n), VO O(Kn) (K=74), ORCA 제약생성O(n)·순차LP최악O(n²). 이웃 제한을 켜면 거리필터O(n), 정렬O(n log n), m개이웃의LP O(m²)이다. 실측에는 Python과 CPU 스케줄링의 변동도 반영된다. 자세한 [방법론·파라미터](newton_experiments.md)를 참조한다.

## 검증 결과

- 최종 pytest: **117 passed**, 105.74초. Viser/pytest 플러그인의 기존 사용중단 경고70건, 실패0건.
- WIZ 정상 빌드 성공.
- 실제 스윕60/60, 비교18/18, 재현성15/15 조합(30회) 완료.
- 브라우저 저장결과18행·6그래프·새로고침·8개파라미터·실제3회timeout 비교 모두 통과, 페이지 오류0건.
- Pygame CSV 두 파일의 SHA256이 작업 전후 동일하다. Pygame 결과/그래프 쓰기 경로는 수정하지 않았다.

## 수정 및 추가 파일

- `newton_warehouse.py`: 순수회피 평균/최악/스텝, 실제 인구 수, 파라미터 적용, CSV저장
- `newton_results.py`: 결과스키마·파라미터 검증·원자적 CSV저장/읽기
- `newton_experiments.py`: 60회스윕·18조건비교·30회재현성CLI
- `plot_newton_results.py`: 한국어5종그래프·수치요약
- `algorithms/naive.py`, `algorithms/velocity_obstacle.py`, `algorithms/orca.py`: 기존기본값을유지하는 파라미터노출
- `requirements-newton.txt`, `README.md`, `docs/newton_experiments.md`, `fonts/*`: 실행문서·의존성·OFL폰트
- `src/app/page.algorithm.run/{api.py,view.ts,view.pug}`: 저장CSV조회·비교표/그래프·설정/현재파라미터
- `src/app/page.algorithm/{view.ts,view.pug}`: 현재기술스택·실험설계·지표의계획서반영
- `tests/conftest.py`, `tests/test_newton_results.py`, `tests/test_newton_csv_api.py`, `tests/browser_newton_results.py`: 테스트결과경로격리·회귀/브라우저검증
- `results/newton/*`: 실제CSV·그래프·재현성·스크린샷
- 프로젝트`devlog.md`와`devlog/2026-11-17/003-newton-results-pipeline.md`: 작업기록

기존 Pygame `results/csv`와`results/figures`는 수정하지 않았다. 테스트는 결과를 임시경로에격리한다. 커밋·배포는수행하지않았으며 사용자가변경을검토할수있는작업상태로남겼다.
