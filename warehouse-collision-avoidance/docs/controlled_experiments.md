# 충돌 회피 통제 실험 보강

기존 Pygame 예비 데이터와 Newton 기준 실험을 유지한다. 새 실험은 기존 A*/Dijkstra/RRT 및 Naive/VO/ORCA를 재사용하며, 전역 경로와 물리 제어기는 세 회피 방식에 동일하게 적용한다. 온라인 재탐색은 기본 비교에 섞지 않는다.

## 만남 조건

| 모드 | 동작 |
|---|---|
| baseline + legacy | 이전 프리셋 및 교통 그대로 유지 |
| head_on | 경로 상의 만남 위치를 선택해 첫 에이전트를 반대 방향으로 접근시킴 |
| crossing | 경로의 접선에 수직으로 횡단. 로봇의 명목 도착 예상 시각에 맞춰 에이전트 출발 지연 |
| narrow_passing | Map1 중앙 통로에 회색 적재물 두 개를 추가해 폭2.8m, 길이4m 시험 통로를 만듦. 선반6개는 유지 |

좁은 교행은 Map1 전용이다. 나머지 만남 조건은6개 맵에서 생성할 수 있다. 좁은 교행 장애물은 시각화뿐 아니라 Newton 충돌체와 전역 탐색 장애물에 같은 위치·크기로 반영된다. 단일 로봇의 안전 여유0.77m를 반영한 유효 경로를 계산한다. 두 에이전트의 안전한 교행 성공 자체는 보장하지 않고 실측 결과로 평가한다.

추가 에이전트도 경로 주변에서 횡단하도록 배치한다. 기존 순찰의 목적지 왕복 로직을 유지하며, 출발 전에는 목표 속도0으로 물리 정지 제어한다. 출발 시각은 물리시간과 비교하므로 렌더링 FPS나 벽시계에 의존하지 않는다. 다른 에이전트끼리의 상호 회피는 추가하지 않았다.

## 인구 통제 및 시드

- workers: n개 모두 작업자.
- mixed: 인덱스3,7,11,15…가 다른 AMR, 나머지는 작업자. 다른 AMR 수는 floor(n/4). n=2에는 다른 AMR이0대이므로 두 집단이 같은 구성이 된다.
- legacy: 기존 easy/medium/hard/crowded 프리셋 구성.
- 통제 실험은 기존 프리셋의 자동 인구 수를 사용하지 않고 입력 n을 정확히 적용한다. n은 R0을 제외한 총 에이전트 수다.
- 각 에이전트의 난수 스트림은 SeedSequence([seed, actor_index, 20261117]). 같은 집단·시드에서 n을 늘려도 기존 에이전트의 초기 조건은 유지되고 뒤에 추가된다.
- 시드로 만남 위치·초기 위치·최대 속도·출발 지연을 변화시킨다. 배치 후보는 선반·벽·초기 에이전트 겹침 및 순찰 선분의 여유를 검사한다.
- scene_hash는 정적 장애물·초기 위치/속도·목적지·반지름·속도·출발 시각·경로·물리 스텝의 해시다. 알고리즘 이름과 Runtime은 제외한다. 러너가 세 알고리즘의 해시 일치를 확인한다.

## 지표 정의

| 지표 | 정의 |
|---|---|
| success | 기존 그대로 목표0.25m 이내, 속도0.02m/s 이하 |
| collision_free_success | success이면서 R0의 바닥 제외 접촉 진입 횟수0 |
| safe_success | success이면서 충돌0·동적/정적 안전거리 위반0, 최소 이격거리도 안전거리 이상 |
| min_dynamic_clearance_m | R0과 다른 에이전트의 중심 거리에서 두 반지름을 뺀 값의 최솟값 |
| min_static_clearance_m | 벽·선반·시험 장애물까지 XY 평면에서 측정한 부호 있는 거리에서 R0 반지름을 뺀 최솟값 |
| min_separation_m | 동적/정적 최소 이격거리 중 작은 값. 음수는 평면 원형 외곽 기준 침투 |
| static_safety_violation_count | 정적 이격거리 < 안전거리인 상태로 진입한 횟수 |
| safety_violation_count | 동적 표면 이격거리 < 안전거리로 진입한 횟수 |
| neighbor_checks / candidate_checks / constraints | 실제 회피 함수의 진단 카운터 누적값. 그래프는 프레임 수로 나누어 비교 |

동적 이격거리는 프레임 전후 상대 이동의 선형 보간으로 최소 거리를 구해 끝점 사이의 근접 통과도 반영한다. 정적 거리는 프레임 끝점에서 측정한다. 이는 연속 시간의 정확한3D 형상 거리나 물리 접촉 버퍼와 동일한 지표가 아니다. 접촉은 Newton의 실제 물리 서브스텝 접촉 버퍼로 별도 집계한다. 작업자끼리의 충돌은 R0 평가 횟수에 포함하지 않는다.

목표 미도달은 timeout으로 남고 arrival_time_s는 빈 값이다. 실패 실행은 도달시간 평균에서 제외하지만 거리·충돌·안전 지표·Runtime 집계에는 포함한다.

## ORCA 위반 프레임 감사

위반 또는 접촉이 있는 프레임마다 다음을 orca_diagnostics.jsonl에 저장한다.

- 프레임·물리시간, 로봇의 이전/이후 위치
- 목표/실제 속도, 속도 추종 오차
- 주변 에이전트 위치·속도·반지름
- ORCA 반평면의 point/direction, 목표/실제 속도의 최대 제약 잔차
- 제약 불가능으로 인한0속도 폴백 여부, 접촉·안전거리 위반 대상

가설 분류는 infeasible_constraints, physical_tracking_error, target_constraint_violation, prediction_or_noncooperative_motion이다. '목표 속도는 제약을 만족하지만 실제 속도가 벗어남'은 추종 오차의 정량 근거다. 다만 프레임 중 제약 변화와 비협조적 타 에이전트의 움직임도 영향을 주므로 단일 원인을 증명한 것으로 해석하지 않는다. ORCA는 비협조적 순찰 대상에 대해 R0이 회피 책임100%를 부담한다. 이 가정을 실제 상호 협조 ORCA와 혼동하지 않는다.

## 결과 보존

results/newton/runs/<UTC시각_UUID>/ 아래에 새 폴더를 만들며 기존 실행을 덮어쓰지 않는다.

- metrics.csv: 확장 지표·입력·카운터
- configuration.json: 전역 탐색기, 시드, 인구·만남 구성, 전체 회피 파라미터, 프레임 한도, 물리 조건
- initial_state.json: 실제 생성된 에이전트 상태·장애물·계획 경로
- provenance.json: Git HEAD/dirty, Python/OS, 관련 소스·맵·요구사항 SHA256, 설치된 의존성 버전
- orca_diagnostics.jsonl: 위반 프레임 감사
- trajectory.json, result.json: 기록한 궤적 스냅샷과 결과
- complete.json: 저장 완료 표시

원래 이름의 CSV는 최신 결과 조회용 사본이며, 교체 전 사본은 legacy_snapshots/<내용해시>.csv로 보존한다. 통제 실험의 최신 사본은 만남 조건·집단·n을 파일명에 추가해 이전 기준 실험과 구분한다. 웹의 '실행 이력 포함'으로 이전 실행을 함께 조회할 수 있다. 예전 CSV의 미측정 안전 지표는0으로 간주하지 않고 N/A로 표시한다.

Git HEAD만으로 수정 중인 코드를 식별할 수 없으므로 dirty와 파일별 SHA256을 함께 확인해야 한다. 실제 소스의 장기 보관은 해당 변경을 검토해 버전 관리에 남기는 절차와 함께 사용한다. 자동 커밋·배포는 하지 않는다.

## 실행

```bash
cd warehouse-collision-avoidance
.venv/bin/python newton_warehouse.py --scenario crowded --agents 4 --algorithm orca --encounter crossing --population workers
# 2집단 × 4단계 × 3방식 × 10시드 = 240회, 기본5400프레임
.venv/bin/python controlled_study.py
# 3종 만남의 별도 비교 (좁은 교행을 포함하므로 Map1 고정)
.venv/bin/python controlled_study.py --counts 4 --populations workers --encounters head_on,crossing,narrow_passing
.venv/bin/python plot_controlled_study.py results/newton/studies/<batch_id>
.venv/bin/python analyze_controlled_study.py results/newton/studies/<batch_id>
```

통제 러너 기본 반복은10회이며2~100회로 설정 가능하다. 각 배치는 별도ID를 사용한다. measurements.csv는 각 실행 직후 저장하며 progress.json에 완료 수를 남긴다. 실패 원인을 숨기지 않고 예외 발생 시 배치 phase=error로 기록한다. 결과를 재실행 없이 읽어 집단·맵·만남 조건별로 분리한 뒤 원래5종 그래프와 안전 도달률·무충돌 도달률·최소 이격거리·계산량/Runtime 비교까지9종을 생성한다.

계산량은 Naive O(n), VO O(Kn), ORCA 제약O(n)·순차LP 최악O(n²)라는 구현 기준과 함께 해석한다. 현재 공간 인덱스는 없으며, ORCA 이웃 제한을 켜면 필터O(n)·정렬O(n log n)·선택 이웃 m의 LP O(m²)가 추가된다. seed 간 표본 표준편차(ddof=1)를 사용하고, 실패로 도달시간 표본 수가 줄어드는 점을 표시한다. 실제Runtime에는 CPU 부하·캐시·Python 비용이 영향을 주며 Big-O의 직접적인 증명으로 사용하지 않는다.

분석 스크립트는 각 도달률의 95% Wilson 구간, 도달시간의 실제 성공 표본 수, ORCA 감사 프레임 분류를 함께 저장합니다. 정적 안전거리만 위반한 프레임도 구분해, 비협조적 작업자에 모든 원인을 돌리지 않습니다.

## 중단 및 재개

`controlled_study.py --resume results/newton/studies/<batch_id>`는 해당 배치의 configuration.json을 사용하고 이미 저장된 조건·시드·알고리즘은 건너뜁니다. 완료된 실행 ID를 유지하며 새 실행만 추가합니다. 동일 배치를 동시에 재개하면 파일 잠금으로 거부합니다. 새 버전의 러너는 SIGTERM/키보드 중단을 progress.json의 interrupted 상태로 기록합니다. 재개 시 다른 인수보다 저장된 원래 설정이 우선합니다.
