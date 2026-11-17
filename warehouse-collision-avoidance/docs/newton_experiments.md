# Newton 재현 실험 설계

Newton 1.7.0 CPU 강체 시뮬레이션 + Viser 2D/3D 뷰어를 사용한다. 전역 탐색은 A*/Dijkstra/RRT이며 지역 회피만 Naive/VO/ORCA로 교체한다. 기존 Pygame 예비 실험은 사전 타당성 검증 데이터이며 `results/csv`, `results/figures`를 변경하지 않는다.

## 실행

프로젝트 `.venv/bin/python`을 사용한다. 실행 디렉터리는 warehouse-collision-avoidance다.

```bash
.venv/bin/python newton_warehouse.py --algorithm orca --scenario medium --agents 4 --map map1 --frames 5400
.venv/bin/python newton_experiments.py sweep
.venv/bin/python plot_newton_results.py
.venv/bin/python newton_experiments.py compare
.venv/bin/python newton_experiments.py reproducibility
.venv/bin/python -m pytest
```

- `sweep`: Map 1 Standard, A*, 동적 순찰, 4단계 × 3회피 × 시드 42~46 = 60회. 각 실행 직후 CSV를 저장하므로 중단 전 완료 데이터가 보존된다. 재실행은 60회 전체를 새로 실행하며 통합 CSV를 새 결과로 교체한다.
- `compare`: 6개 맵 × 3회피 = 18회, medium/seed42/공통 순찰 배치, 웹의 전체 비교와 같은 기본 조건.
- `reproducibility`: medium/Map1/A*에서 3회피 × 5시드 × 2회 = 30회. 성공 도달시간·반올림 전 경로길이·충돌수의 완전 일치를 비교한다. 원인 후보 및 결과를 reproducibility.json에 기록한다. 개별 CSV는 덮어쓰지 않는다.
- 기본 한도는 5400프레임, 기본 timeStep=1/30초로 최대 물리시간 180초다. 테스트용 `--frames`를 사용하면 CSV frame_limit에 다른 한도가 남는다.
- success는 목표까지 0.25m 이내이면서 속력 0.02m/s 이하인 실제 물리 상태다. 프레임 한도 내 조건을 만족하지 못하면 timeout이다.
- n은 제어 로봇 R0을 제외한 이동 에이전트 수다. easy=작업자2, medium=작업자4, hard=작업자7+다른AMR2=9, crowded=작업자12+다른AMR4=16. 작업자 수 7을 전체 에이전트 수로 잘못 표기하지 않는다.

## 결과 저장

`results/newton/<map>_<algorithm>_<scenario>_<seed>.csv`에 한 실행 한 행을 원자적으로 저장한다. 동일 파일명 재실행은 대체한다. 파일명에 포함되지 않는 설정(전역 탐색기, 속도, 안전거리, timeStep, 프레임 한도, 순찰 배치 방식 등)은 CSV 열로 보존한다. 다른 설정을 장기 보관하려면 별도 디렉터리에 결과를 복사한다. 스윕 전체는 `sweep_agent_count.csv`로 별도 보존한다.

웹 알고리즘 비교 탭의 '저장 CSV 불러오기'는 재시뮬레이션 없이 CSV를 읽는다. 현재 설정(시드·시나리오·전역 탐색·순찰·속도·안전거리·프레임 한도·회피 파라미터)과 일치하는 결과만 표시한다. 저장 CSV는 지표 요약이며 강체 프레임을 포함하지 않아 3D 재생 버튼을 비활성화한다. 현재 세션에서 비교한 기록의 재생은 유지한다.

## 지표

기존 계획서 6종을 유지한다: 도달 시간, 이동 거리, 충돌/안전거리 위반, 성공 여부/성공률, 실행시간, 입력 크기별 계산량/복잡도.

| CSV 열 | 정의 / 단위 |
|---|---|
| arrival_time_s | 성공한 실행의 물리시간(초). 실패는 빈 값, 평균에서 제외 |
| path_length_m | 매 프레임 Newton R0 위치의 이동거리 누적(m), 반올림 전 값 |
| collision_count | 바닥을 제외한 R0 접촉 상대별 비접촉→접촉 진입 횟수. 지속 접촉은 매 프레임 중복하지 않음 |
| safety_violation_count | 동적 에이전트와 중심 거리 < 두 반지름 + 안전거리인 상태의 진입 횟수. 정적 선반의 안전거리 지표가 아님 |
| success / timeout | 0 또는 1. 종료된 정상 실행에서 서로 배타적 |
| replan_count | 초기 전역 계획 이후 재탐색 수. 현재 온라인 재탐색 없음으로 실제 0 |
| wall_time_s | 초기화·전역 탐색·물리·회피·렌더링을 포함한 실행 벽시계 시간. 라이브는 사용자 일시정지 시간 포함, CSV 쓰기 제외 |
| algo_time_avg_ms / algo_time_max_ms | choose_velocity 호출 전체만 perf_counter_ns로 측정한 평균/최악(ms). 물리·렌더링·전역 탐색 제외 |
| algo_steps | 실제 choose_velocity 호출 횟수. R0 1대, 프레임당 1회이며 물리 서브스텝은 2회 |
| worker_count / other_robot_count | n의 구성. R0 제외 |
| observed_time_s | 성공/실패 모두 관찰한 실제 물리시간(초), 도달시간 대체값으로 사용 금지 |

계측 지점은 `newton_warehouse.py:run`의 `algorithm.choose_velocity` 호출 직전/직후다. 실제 함수는 `algorithms/naive.py:NaiveAvoidance.choose_velocity`, `algorithms/velocity_obstacle.py:VelocityObstacleAvoidance.choose_velocity`, `algorithms/orca.py:ORCAAvoidance.choose_velocity`다. 세 함수의 이웃 처리 및 진단 카운터 비용은 계측에 포함하며 A* 및 Newton 배열 읽기는 제외한다.

## 명시적 파라미터

환경 설정에서 수정하며 CLI는 `--parameters '{"vo_candidates":74}'`처럼 JSON 부분 오버라이드를 받는다. 미지 키·비유한값·범위 위반은 거부한다.

| 알고리즘 | 설정 | 기존 기본값 |
|---|---|---|
| 공통 | time_step_s (ORCA timeStep과 물리 프레임 공통) | 1/30 s |
| 공통 | maxSpeed / 안전거리 | 1.2 m/s / 0.35 m, 기존 속도·안전거리 입력 |
| ORCA | orca_neighbor_dist_m / orca_max_neighbors | 0 / 0 = 제한 없음. 기존은 하드코딩 반경/개수 없이 전체 이웃 처리 |
| ORCA | orca_horizon_s | 3 s |
| VO | vo_horizon_s / vo_candidates K | 3 s / 74 (선호·정지 2개 + 3속도 × 24방향) |
| Naive | naive_stop_margin_m | 0 m. 긴급 반응 기준은 두 에이전트 반지름+안전거리+추가 여유 |
| Naive | naive_influence_m | 1.2 m |

Naive는 긴급 상태에서 선호속도 25%와 반발력을 합하며, 반발력이 상쇄되면 정지한다. 별도의 하드 정지 알고리즘으로 설명하지 않는다. ORCA는 반평면 생성과 순차 2D 선형계획이며 비협조적 순찰 에이전트에 대해 R0이 회피 책임 100%를 부담한다. 상호 협조형 RVO2와 조건이 다르며, 불가능한 제약은 0 속도로 폴백한다. RVO2 외부 라이브러리는 사용하지 않는다.

## 계산량과 해석

기본 n은 전체 이웃이다. 공간 인덱스 없음. Naive O(n), VO O(Kn) (일찍 충돌을 찾으면 후보 이웃 루프 종료), ORCA 제약 O(n), 순차 투영 최악 O(n²). ORCA 이웃 제한을 켜면 거리 필터 O(n), 최근접 정렬 O(n log n), 선택 이웃 m에 대한 LP O(m²)가 추가된다. 실측 Python 오버헤드, 충돌 분포, 조기 종료, 물리 접촉, CPU 스케줄링 때문에 Big-O와 실제 증가율은 같지 않다.

그래프 5종은 실제 CSV만 읽고 시드 간 표본 표준편차(ddof=1)를 오차막대로 사용한다. 도달시간은 성공 실행만, 거리·사건·성공률·회피 계산시간은 실패를 포함한 전체 실행을 사용한다. 성공률의 오차막대는 0/100 시드별 관측의 표준편차이며 신뢰구간이 아니다. 계산시간 그래프는 로그 y축이다. 병렬 실행은 CPU 시간 비교를 왜곡할 수 있으므로 러너는 순차 실행한다. 5회 반복으로 성능 우열이나 안전 보장을 일반화하지 않는다.

Noto Sans KR는 `fonts/NotoSansKR.ttf`를 명시 등록하며 SIL OFL 라이선스를 함께 보관한다. 폰트가 없으면 대체 폰트로 조용히 진행하지 않고 오류를 낸다. 글꼴 출처: https://github.com/google/fonts/tree/main/ofl/notosanskr
