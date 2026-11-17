# Warehouse Collision Avoidance Simulator

사람, 이동 로봇, 선반이 공존하는 Newton 3D 물류창고에서 A* 전역 경로와 Naive, Velocity Obstacles(VO), ORCA 지역 충돌 회피를 비교한다. 기존 Pygame 2D 실험 도구와 CSV·그래프는 사전 타당성 검증 데이터로 유지한다.

## 구현 상태

- 새 기본 창고 38m × 26m, 중앙 통로 6m, 세로 통로 5m, 선반 6개, START/GOAL 보호 반경 3m (기존 24m × 16m 실험은 유지)
- 작업자와 다른 이동 로봇, 협조/비협조 설정, 에이전트별 반지름·속도
- 세 알고리즘 공통 격자 A* 전역 경로
- 서로 다른 Naive·VO·ORCA 구현과 공통 인터페이스
- Pygame 실시간 UI와 마우스/키보드 제어
- 5개 시나리오, 5·10·20·40·80명, 반복 횟수와 시드 설정
- 10개 성능 지표, CSV 저장, 6개 Matplotlib 그래프
- 기하·A*·알고리즘·지표·재현성·교체 실행 pytest

## 설치와 실행

Python 3.11 이상을 권장한다. 이 작업에서는 Python 3.14.4와 pygame-ce 2.5.8로 검증했다.

```bash
cd warehouse-collision-avoidance
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --algorithm orca --agents 20 --scenario warehouse --seed 42
```

UI에서는 알고리즘, 시작/일시정지, 초기화, 에이전트 수, 속도, 시드를 버튼으로 바꿀 수 있다. `P`, `S`, `C`는 각각 경로, 안전거리, 충돌 위험 표시를 전환하며 `Esc`로 종료한다.

## Newton 3D 최소 프로토타입

기존 Naive·VO·ORCA 구현과 분리된 Newton 1.7.0 연동 스모크 테스트다. 바닥, 고정 선반 2개, 동적 구형 로봇을 Newton 강체로 생성하고, 평면 PD 힘으로 목표점까지 이동시킨다. 상태 배열과 접촉 버퍼를 읽어 최종 위치·속도·접촉 대상을 JSON으로 출력한다.

```bash
uv venv .venv --python python3.12
uv pip install --python .venv/bin/python -r requirements-newton.txt
.venv/bin/python newton_minimal.py --viewer null --frames 720
.venv/bin/python newton_minimal.py --viewer viser --frames 720 --port 8080
```

GUI가 없는 서버에서는 `ViewerNull`을 사용한다. `ViewerViser`는 실행 중 `http://localhost:8080`에서 볼 수 있으며, `ViewerGL`은 디스플레이/OpenGL 컨텍스트가 있는 환경에서만 사용한다. 이 프로토타입은 Newton 물리 연동 검증 범위이며 세 회피 알고리즘의 Newton 어댑터는 아직 연결하지 않았다.

## Newton 물류창고 통합 실행

`newton_warehouse.py`는 기존 A*와 Naive·VO·ORCA 구현을 Newton 1.7.0 강체 시뮬레이션에 연결한다. 알고리즘은 Newton에서 읽은 위치·속도를 입력받아 목표 속도를 반환하고, 공통 힘 제어기가 로봇 강체에 적용한다. 작업자와 추가 로봇도 Newton 동적 강체이며 바닥·벽·선반은 고정 충돌 형상이다.

```bash
.venv/bin/python newton_warehouse.py --algorithm orca --scenario crowded --agents 16 --frames 360 --viewer null
.venv/bin/python newton_warehouse.py --algorithm vo --scenario warehouse --agents 8 --frames 1800 --viewer viser --port 8080
```

프레임 한도 내 미도달은 `status: timeout`이며, 목표까지 0.25m 이내이고 실제 속도가 0.02m/s 이하인 경우에만 `success`로 기록한다. 웹 통합 화면은 Newton CPU를 실행 중 제어하고 ViewerViser 3D와 2D Top View를 제공한다. 정식 장시간 비교 실험은 CLI에서 수행한다.

## 반복 실험과 그래프

기본값은 물류창고 시나리오, 5·10·20·40·80명, 각 조건 10회다.

```bash
python -m experiments.runner --scenarios warehouse --counts 5 10 20 40 80 --repeats 10 --seed 42
python -m experiments.analysis
```

모든 시나리오를 실행하려면 다음과 같이 지정한다.

```bash
python -m experiments.runner \
  --scenarios basic warehouse crossing multi_robot crowded \
  --counts 5 10 20 40 80 --repeats 10
```

CSV는 `results/csv/`, 그래프는 `results/figures/`에 저장된다. 실패한 실행의 도달 시간은 빈 값이며 임의의 제한 시간을 평균에 넣지 않는다.

## 알고리즘 실제 구현

### Naive

현재 거리만 검사한다. 안전거리 안에서는 목표 속도를 줄이고 가까운 에이전트 반대 방향의 반발 벡터를 더한다. 미래 충돌 예측은 없다. 스텝당 `O(n)`이다.

### Velocity Obstacles

상대 위치와 상대 속도의 이차방정식으로 3초 범위 충돌을 예측한다. 선호 속도·정지와 3개 속력 × 24개 방향을 평가해 안전하면서 선호 속도에 가장 가까운 후보를 선택한다. 후보 수 `K`에 대해 `O(Kn)`이며 현재 `K=74`다.

### ORCA

각 이웃으로 ORCA 속도 반평면을 생성하고 2차원 순차 선형계획으로 선호 속도에 가까운 허용 속도를 구한다. 협조 에이전트는 회피 책임을 절반씩 나누며 비협조 작업자는 제어 로봇이 전부 부담한다. 제약 생성은 `O(n)`, 현재 투영 구현의 최악 시간은 `O(n²)`이다. 외부 RVO2 라이브러리를 사용하거나 표준 구현이라고 가장하지 않으며, 구현 범위는 `docs/algorithm_analysis.md`에 명시했다.

## 지표

Goal Reaching Time, Path Length, Collision Count, Safety Distance Violations, Success Rate, 알고리즘 누적 시간, 스텝당 평균 시간, 95백분위 시간, Robot Stop Time, Minimum Separation을 실제 시뮬레이션 상태에서 계산한다. 충돌과 안전거리 위반은 상태에 새로 진입한 횟수로 각각 집계한다.

## 이번 검증 결과

```text
12 passed
```

Pygame은 SDL dummy 드라이버에서 5프레임 렌더링을 완료했다. 예비 실험은 물류창고 시나리오에서 5개 규모 × 3개 알고리즘 × 3회, 총 45회를 실제 실행했다. 20명까지 VO와 ORCA는 3/3 성공했고, 40명과 80명에서는 세 방식 모두 0/3 성공했다. 이 실패와 충돌 수는 CSV와 그래프에 그대로 포함했다. 예비 결과는 반복 3회뿐이므로 최종 발표 통계로 확정하지 않는다.

## 프로젝트 구조

```text
warehouse-collision-avoidance/
├── main.py
├── newton_minimal.py # Newton 3D 물리 연동 스모크 테스트
├── newton_warehouse.py # A*·회피 알고리즘·Newton 강체 통합
├── requirements-newton.txt
├── algorithms/       # 공통 인터페이스, Naive, VO, ORCA, A*
├── simulator/        # 에이전트, 물리, 환경, Pygame 렌더링
├── experiments/      # 시나리오, 지표, 반복 실행, 그래프
├── tests/
├── results/csv/
├── results/figures/
└── docs/
```

## 라이브러리와 라이선스

- pygame-ce 2.5.8: LGPL-2.1-or-later
- NumPy: BSD-3-Clause
- Pandas: BSD-3-Clause
- Matplotlib: PSF 기반 라이선스
- pytest: MIT

ORCA 계산은 프로젝트 내부 구현이며 RVO2 바이너리나 코드를 포함하지 않는다.

## 알려진 제한과 다음 개선

- 다른 작업자와 로봇은 지정 목적지를 왕복하지만 서로 간 회피는 하지 않는다.
- 동적 이웃 탐색은 전체 검사이며 k-d tree나 uniform grid가 없다.
- ORCA는 2D 반평면과 순차 LP 범위이며 장애물 ORCA 선분 제약은 A*와 물리 충돌 방지로 대체한다.
- 40명 이상 밀집 환경의 실패율이 높다. 공간 분할, 정체 해소 전략, 모든 로봇의 상호 ORCA 적용이 다음 개선 대상이다.
- 최종 보고에는 조건당 10회 이상을 실행하고 평균·표준편차 또는 신뢰구간을 다시 산출해야 한다.

세부 지표 정의는 `docs/experiment_methodology.md`, 복잡도 분석은 `docs/algorithm_analysis.md`를 참고한다.

## 웹 3D 통합 뷰어 (2026-11-09)

`/algorithm?section=implementation`에서 기본 3D View와 분석용 2D Top View를 전환한다. 두 뷰는 동일한 Newton `body_q`·`body_qd` 기록과 서버 시간 상태를 사용한다.

- Start: 새 Newton CPU/ViewerViser 세션 실행. 경로 길이·속도에 비해 짧은 실행 한도는 자동 보정하며 알고리즘 변경도 새 실행을 시작한다.
- Pause / Resume: 실행 중에는 실제 물리 계산 정지·재개.
- Reset: Newton 모델·강체를 출발 상태로 재생성하고 정지 상태로 유지.
- 프레임 한도 또는 목표 도달 후: 저장 기록 모드. Resume과 슬라이더는 기록을 재생·탐색한다.
- 물리 계산 시간과 회피 알고리즘 계산 시간을 각각 표시한다. 접촉·안전거리 지표는 R0 기준이다.
- 최대 4개 세션, UI 최대 프레임 30~10800 (기본 5400 = 물리 시간 180초), 15분 미사용 시 워커 종료. 완성 기록은 `results/live/{token}/record.json`에 남긴다.
- 서버는 CPU, 브라우저는 Viser WebGL 렌더러를 사용한다. WIZ의 커스텀 WebSocket 업그레이드 제약은 프로젝트 내부 HTTP 중계로 처리한다.
- 이전 2D/Pygame 실험과 최소 Newton 프로토타입은 유지한다. 이전 XY 전용 기록에는 3D 자세가 없으므로 새 실행이 필요하다.

검증: `.venv/bin/python -m pytest tests` (Newton·레이아웃·모델 정렬 회귀 포함 45개 통과).
브라우저 회귀 스크립트: `tests/browser_warehouse.py` (Playwright, Chromium, localhost WIZ 필요; CPU 접촉 테스트를 먼저 실행).
상세 구성·변경 파일·실측 결과·한계는 [3D 검증 기록](docs/newton_3d_validation.md)을 참고한다.

### 목표 도달 및 종료 조건 수정

형상 기본 밀도로 합산되던 로봇 질량(약 359kg)을 제어기 기준인 14kg으로 맞췄다. 작업자는 70kg, 추가 로봇은 12kg이며 형상 밀도로 실제 질량·관성을 계산한다. 바닥/이동 강체 마찰계수 0.05는 구동 바퀴의 낮은 주행 저항을 근사한다. 목표 근처에서는 선호 속도를 줄여 Newton 힘 제어로 감속한다.

기본 실행 한도는 이전 180프레임(6초)에서 5400프레임(180초)으로 늘렸다. 목표 도달 후 정지 조건을 충족하면 즉시 완료하며, 한도를 모두 사용해도 미도달이면 시간 초과로 표시한다. 성공한 마지막 프레임은 경로 기록 간격과 관계없이 반드시 저장한다. 기존 세션/저장 기록에는 이전 물리 설정이 남으므로 화면을 새로고침하고 Start로 새 실행을 시작한다.

### 짧은 실행 한도가 남은 경우의 실시간 주행

실시간 Start는 이전 탭이나 설정에 180프레임(6초)이 남아 있어도 경로 길이와 최대 속도로 필요한 시간을 계산한다. 주행 여유를 포함한 최소 한도는 `(2 × A* 경로 길이 / 최대 속도 + 10초) × 30fps`이며, 실시간 안전 한도 10800프레임 안에서 요청 한도를 확장한다. 기본 창고·속도 1.2m/s의 180프레임 요청은 1381프레임으로 보정된다. 화면에 보정된 시간을 안내하고 목표 도달·정지 시 즉시 완료한다.

비교 실험/CLI는 지정한 프레임 구간을 그대로 사용하며, 기록 로드는 원본 기록을 재생한다. 결과 메타데이터의 `requested_frame_limit`, `frame_limit`, `frame_budget_extended`로 요청 한도와 실제 한도를 구분한다.

실제 서비스 주소에서도 검증하도록 브라우저 목표 회귀에 `WAREHOUSE_BASE_URL`, `WAREHOUSE_LEGACY_FRAMES` 옵션을 추가했다. Reset 검사는 동시 polling 응답 대신 해당 Reset ACK를 직접 확인한다.

## 확장 창고와 렌더 모델 (2026-11-09)

웹 기본 시나리오는 medium이다. 로봇 수는 제어 로봇 R0를 포함한다.

| 프리셋 | 로봇 | 작업자 | 비고 |
|---|---:|---:|---|
| easy | 1 | 2 | 횡단 작업자 1명 |
| medium | 1 | 4 | 동일 조건 비교 기본값 |
| hard | 3 | 7 | 요청 범위 로봇 2~4대·작업자 6~8명 내의 기본 구성 |
| crowded 기본값 | 5 | 12 | 추가 에이전트 수로 밀도 조절 |
| 이전 실험 | 기존 구성 | 기존 구성 | basic / warehouse / crossing / multi_robot 유지 |

새 창고는 38×26m이며 START=(2.5,13), GOAL=(35.5,13)이다. 3×7m 선반 6개를 x=8/16/24, y=3/16에 배치한다. 중앙 가로 통로는 6m, 선반 열 사이 세로 통로는 5m다. 각 출발/목표 주변 3m에 에이전트 반경을 더한 구역을 초기 배치에서 제외하고, 초기 에이전트끼리 반경 합에 0.35m 이상의 간격을 둔다. 일부 작업자만 중앙 경로를 횡단하고 나머지는 양쪽 세로 통로에서 순찰한다.

`warehouse_visuals.py`는 코드로 만든 저폴리 GLB 렌더 자산이다. AMR은 차체·범퍼·바퀴·라이다, 작업자는 안전모·작업복·사지, 선반은 기둥·보·적재 상자로 구성한다. 별도 렌더 메시이며 Newton collider로 사용하지 않는다. 자산 빌더를 교체하면 물리 코드를 바꾸지 않고 외형을 교체할 수 있다.

새 환경의 단순 충돌체는 AMR cylinder(반경 0.42m, 반높이 0.26m, 14kg/추가 AMR 12kg), 작업자 capsule(반경 0.30m, 반높이 0.55m, 총 높이 1.70m, 70kg), 선반 box(높이 3.2m)다. 안전 여유는 기본 0.35m다. 메시의 body-local 원점을 collider의 강체 중심과 일치시키며 `body_q`의 위치·전체 회전을 렌더 루트에 적용한다. 토크 제어로 직립과 진행 방향을 유지하며 자세를 직접 덮어쓰지 않는다. 별도의 장식용 보행/바퀴 애니메이션은 없다.

Naive·VO·ORCA는 같은 A* 경로·초기 배치·시드·실제 Newton 상태로 R0를 제어한다. 추가 AMR/작업자는 같은 순찰 제어를 사용한다. ORCA는 이 순찰 강체가 상호 회피에 참여한다고 가정하지 않는다. 기존 기록을 로드하면 저장된 크기·선반·강체 종류·자세를 복원한다.

검증: 4개 프리셋×4개 시드의 배치/경로, crowded 0~120명 범위의 인원 보존, 메시/충돌 반경과 전체 자세 정렬, 실제 서비스의 4개 선택/렌더링, medium의 세 알고리즘 비교를 확인했다. 시드 42 medium 단일 실행에서 Naive/VO/ORCA 모두 목표에 도달했고 충돌은 0회였다. 안전거리 위반은 각각 0/0/1회로 그대로 기록한다. hard/crowded의 장시간 도달률과 반복 통계는 아직 검증하지 않았다.

브라우저 회귀:
```bash
PYTHONPATH=/tmp/bike-playwright WAREHOUSE_BASE_URL=https://project.wizide.com WAREHOUSE_CHROMIUM=/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome /opt/conda/envs/app/bin/python tests/browser_layout.py
```

## Newton 선반 배치 맵 6종

시뮬레이션 상단의 **Map 1~6 버튼**으로 Default / Horizontal / Zigzag / Maze / Dense / Asymmetric를 전환한다. 기존 주행을 멈추고 충돌체·작업자·A* 경로를 재생성한 뒤 시간 0에서 정지한다. **Start 또는 Resume**으로 출발한다. 기존 38×26m 바닥·외벽과 선반/박스 모델은 유지한다.

맵 설정은 `warehouse_maps.json` 한 곳에서 관리하며 렌더링·Newton 충돌체·A*가 같은 설정을 사용한다. CLI 예: `.venv/bin/python newton_warehouse.py --scenario medium --map map3 --algorithm orca --frames 3600 --viewer null`.

[맵별 배치·검증 결과·실제 Viewer 캡처 6장](docs/warehouse_maps.md). 2026-11-16 검증: pytest 93개 통과, medium/seed42에서 6맵×3알고리즘 18조건 모두 목표 도달 및 선반 접촉 없음. 모든 인원·시드 조건의 무충돌을 보장하는 결과는 아니다.

## 논문을 참고한 레이아웃·전역 경로 비교 (2026-11-16 확장)

현재 여섯 버튼은 **Standard / Horizontal / Zigzag / Maze / Dense / Fishbone**이다. 앞선 Asymmetric 배치와 과거 검증 문서는 이전 버전의 기록이다. 기존 38×26m 바닥·외벽, 선반6개·크기3×7×3.2m와 AMR/작업자 모델을 유지했다. Fishbone은 ±45도 선반을 포함한 **자체 Fishbone-inspired 배치**이며 원 논문의 검증된 배치를 재현한 것이 아니다.

전역 경로 탐색 선택에 기존 **A***와 **Dijkstra / RRT**를 제공한다. 지역 회피 **Naive / VO / ORCA** 선택은 별도로 유지한다. 맵 전환 때 주행을 정지하고 실제 Newton collider·작업자·내비게이션·경로를 재생성한다. 대각선 선반은 메시/box collider/원형 로봇 충돌 검사가 동일한 중심·회전을 사용한다. 2D도 실제 회전을 표시한다.

실험 결과 탭에는 실제 Newton CPU 실행으로 얻은 경로 길이·계획 시간·성공률 그래프, 확장 노드·주행 시간·충돌·재탐색·방향 전환 표와 계획/실제 경로 표시가 있다. **60조건 Newton CPU 실험 실행**으로 재측정할 수 있고 실행 중에는 부분 결과임을 표시한다.

실험 조건: Python3.12.3 / Newton1.7.0 / Warp1.19.0 / CPU, R0 radius0.42m, 안전거리0.35m, 속도1.2m/s, 공통 START(2.5,13)·GOAL(35.5,13), 작업자4명 공통 초기/순찰 조건. 지역 회피는 ORCA 고정. 정적·동적 모드 각각 A*/Dijkstra 각1회, RRT 시드42/43/44 각1회로 총60건을 실제 실행했다. 60건 모두 목표 도달·정지했으며 R0 선반/외벽 접촉은 없었다. 소규모 검증으로 일반적인 우월성·무충돌을 보장하지 않는다.

설정: A*/Dijkstra 0.5m 8연결 격자, RRT max3000회/3초·step1.5m·goal bias0.15·결정적 shortcut. RRT는 최적성을 가정하지 않는다. RRT 확장 노드는 N/A, 반복1회인 탐색기의 분산도 N/A다. 계획 시간(ms)과 실제 이동 시간(simulation seconds)을 분리한다. 재탐색은 초기 계산을 제외한0회이며 온라인 재탐색은 미구현이다.

```bash
cd warehouse-collision-avoidance
.venv/bin/python newton_warehouse.py --scenario medium --map map6 --planner rrt --planner-seed 42 --algorithm orca --frames 3600 --viewer null
.venv/bin/python planning_study.py --rrt-repeats 3
# numpy/matplotlib가 설치된 분석용 Python:
python export_planning_study.py
.venv/bin/python -m pytest tests
```

- [실험 결과표·그래프·스크린샷·실행 로그](docs/planning-study/README.md)
- [전체 좌표·회전·참고 자료별 적용/미적용 범위](docs/research_layouts.md)
- [현재 맵 설정 JSON](warehouse_maps.json)
- 참고 A: [Zhang et al., IJCAI 2023](https://arxiv.org/html/2305.06436v3), [공식 코드](https://github.com/lunjohnzhang/warehouse_env_gen_public)
- 참고 B: [Wu et al., 2020 RMFS layout](https://doi.org/10.1177/1729881420978543)
- 참고 C: [Fishbone RMFS](https://doi.org/10.1016/j.eswa.2024.125166) — 출판사 초록·하이라이트 확인, 본문403 접근 제한.
- 참고 D: [Moving AI Warehouse](https://benchmarks.pathfinding.ai/mapf-benchmarks/warehouse-maps/) — 고정 시나리오/재현성 참고, 원본 대형 격자를 직접 임포트한 것은 아니다.
- RRT: [LaValle 저자 자료](https://lavalle.pl/rrtpubs.html)

## Naive·VO·ORCA의 6개 맵 비교 (2026-11-17)

**알고리즘 비교** 탭의 기본 범위는 이제 **6개 맵 전체**다. **6개 맵 · 18조건 비교 실행**을 누르면 Standard → Horizontal → Zigzag → Maze → Dense → Fishbone 순서로 각 맵에서 Naive/VO/ORCA를 실제 Newton CPU로 실행한다. 맵별로 요청을 나누어 진행 상태와 반환된 결과를 표시한다.

전역 탐색기·작업자 모드·인원/시나리오·시드·속도·안전거리·프레임 한도는 실행 시작 시 고정한다. 전체 비교에는 맵 설정의 공통 worker-0~3 초기 위치/왕복 목표를 적용한다. 추가 로봇은 작업자 재배치의 대상이 아니다. hard/crowded의 추가 인원은 해당 맵의 기존 유효 배치를 사용한다. 24×16m 레거시 시나리오에서 전체 비교를 시작하면 38×26m medium(작업자4명)으로 전환한다.

결과 표는 맵·지역 회피 알고리즘별로 구분하며, 각 알고리즘을 누르면 해당 맵의 Newton 3D/2D 기록을 연다. 기록을 Reset해도 공통 작업자 설정을 유지한다. 새 비교가 기존 실행 기록을 삭제하지 않으며, 중간 오류가 나면 반환된 결과를 유지하고 실패한 맵을 표시한다. 기존 **선택한 맵만** 비교도 선택할 수 있다.

기존 **실험 결과 → 60조건 Newton CPU 실험**은 A*/Dijkstra/RRT 전역 탐색 비교이며, 이번 Naive/VO/ORCA 18조건 비교와 별개다. 프레임 한도 내 목표 미도달은 timeout으로 기록한다.

재현 브라우저 검사:
```bash
WAREHOUSE_CHROMIUM=/path/to/chromium python tests/browser_all_map_comparison.py
.venv/bin/python -m pytest tests/test_common_comparison_traffic.py
```


## Newton 결과 저장·계측·반복 실험

Newton 1.7.0 CPU 강체 시뮬레이션 + Viser 2D/3D 뷰어, 전역 탐색 A*/Dijkstra/RRT를 사용한다. 기본 한도는 5400프레임이다. [실험 설계와 파라미터·지표 정의](docs/newton_experiments.md)에 실행법, 저장 스키마, 재현성 및 복잡도 분석을 정리했다.

```bash
.venv/bin/python newton_experiments.py sweep
.venv/bin/python plot_newton_results.py
.venv/bin/python newton_experiments.py compare
.venv/bin/python newton_experiments.py reproducibility
```

CSV·그래프·검증 결과는 `results/newton/`에만 저장한다. 스윕은 Map1/A*/동적 순찰, n=2/4/9/16, 시드42~46으로 60회다. hard는 작업자7명과 다른 AMR2대를 포함하므로 n=9이다. 웹 알고리즘 비교에서 저장 CSV를 불러오면 재실행 없이 표·맵별 도달시간 그래프를 볼 수 있다.

| 파라미터 | 기본값 |
|---|---|
| ORCA neighborDist / maxNeighbors | 0 / 0 (전체, 기존 제한 없음) |
| ORCA timeStep / maxSpeed / horizon | 1/30 s / 1.2 m/s / 3 s |
| VO horizon / K | 3 s / 74 |
| Naive 안전거리 / 긴급 반응 추가 여유 / 영향거리 | 0.35 m / 0 m / 1.2 m |

환경 설정에서 위 값을 수정한다. Naive 긴급 반경은 반지름 합+안전거리+추가 여유이며 감속/반발 방식이다. 회피 계산시간은 `newton_warehouse.run`의 `choose_velocity` 호출만 감싼 평균·최악·스텝 수로 기록한다. 물리·렌더링·전역 경로 계산은 포함하지 않는다. 실패 실행의 도달시간은 빈 값이다.

2026-11-17 실제 수행한 스윕 60회·18조건 비교·재현성 30회의 [수치 요약과 화면 캡처](docs/newton_result_summary.md)를 제공한다. 일반적인 성능 우열을 단정하지 않으며 충돌·안전거리 위반도 함께 보고한다.
