# 연구 자료와 구현 범위

검토일: 2026-11-16. 아래 자료의 실제 내용과 **이번 프로젝트에서 직접 설계한 배치**를 구분한다. 맵 1~6은 원 논문의 검증된 레이아웃 6종이 아니며, 논문 최적화 결과를 복제했다고 주장하지 않는다.

| 자료 | 확인한 실제 내용 | 이번 구현에 참고한 요소 | 재현하지 않은 부분 |
|---|---|---|---|
| A: Zhang et al., IJCAI 2023 | MAP-Elites/DSAGE로 창고 레이아웃을 최적화하고 MILP로 제약을 복구한다. 비교 배치의 선반 수를 같게 유지한다. | 선반 수/면적 통제, 연결성 검사, 레이아웃 다양화와 실험 조건 기록 | MAP-Elites·DSAGE·MILP·다중 로봇 throughput 실험 |
| B: Wu et al., 2020 | 피킹 스테이션의 내부/외부 위치와 구역화를 포함한 7개 장면을 semi-open queueing network로 평가한다. | 구조·배치 조건을 명시적으로 분리한 실험 설계 | 이 프로젝트의 Standard/Horizontal/Zigzag/Maze/Dense가 해당 논문의 장면이라는 주장, SOQN과 스테이션 최적화 |
| C: Zhao et al., DOI eswa.2024.125166 | 출판사 검색 색인의 초록·하이라이트에서 Fishbone RMFS와 대각선 cross-aisle의 비교 목적을 확인했다. 직접 본문 요청은 HTTP 403이었다. | Map6의 ±45도 선반, 대각선 분기와 V자 우회 통로라는 설계 아이디어 | 원문 상세 좌표·최적 각도·수식·성능 수치. **6개 선반의 Fishbone-inspired custom layout**이며 원 배치의 축척 재현이 아니다. |
| D: Moving AI Warehouse Benchmarks | 4개 warehouse 격자 맵과 even/random 시나리오, 고정 START/GOAL 목록을 제공한다. | 고정 장애물·공통 출발/목표·시드 기록을 통한 재현성 | 원본 161×63 이상 격자 맵의 직접 임포트·동일 점수·다중 로봇 MAPF 성능 |
| 추가: LaValle, 1998 RRT | 무작위 샘플·최근접 노드·트리 확장으로 유효 경로를 찾는다. | 단일 goal-biased RRT와 충돌 검사, 고정 시드·반복/시간 제한 | RRT*/최적성·점근 최적성 주장 |

## 원문·공개 코드

- A 논문: [IJCAI](https://www.ijcai.org/proceedings/2023/0611.pdf), [저자 공개 HTML 전체 논문](https://arxiv.org/html/2305.06436v3).
- A 공식 코드: [warehouse_env_gen_public](https://github.com/lunjohnzhang/warehouse_env_gen_public), master README 확인. C++/Python, RHCR/DSAGE, Singularity/CPLEX 기반이다. 라이브러리를 설치하거나 코드를 복사하지 않았다.
- B: [Research of the layout optimization in robotic mobile fulfillment systems](https://journals.sagepub.com/doi/10.1177/1729881420978543). 출판사 전체 HTML의 초록·방법·배치 설명 확인.
- C: [Warehouse layout optimization for fishbone robotic mobile fulfillment systems](https://doi.org/10.1016/j.eswa.2024.125166), [출판사 초록 페이지](https://www.sciencedirect.com/science/article/pii/S0957417424020335). DOI 연도는 2024이며, 이를 최종 권·호 출판연도로 단정하지 않는다.
- D: [Warehouse Maps](https://benchmarks.pathfinding.ai/mapf-benchmarks/warehouse-maps/), [Moving AI 공식 설명](https://www.movingai.com/benchmarks/mapf.html).
- RRT: [LaValle 저자 설명](https://lavalle.pl/rrtpubs.html), [1998 기술보고서](https://msl.cs.illinois.edu/~lavalle/papers/Lav98c.pdf).

## 좌표와 회전

[warehouse_maps.json](../warehouse_maps.json)이 물리·렌더·경로 검사의 단일 설정이다. 단위 m, 선반 중심 XY, Z축 회전 degree. 38×26m 바닥·외벽, 선반 3×7×3.2m 6개, 로봇 radius0.42m·속도1.2m/s·안전거리0.35m를 통제한다.

| 맵 | 중심 XY (선반 0~5) | 회전 0~5 |
|---|---|---|
| Standard | (9.5,6.5), (9.5,19.5), (17.5,6.5), (17.5,19.5), (25.5,6.5), (25.5,19.5) | 0,0,0,0,0,0 |
| Horizontal | (9,8.5), (9,16.5), (19,12.5), (19,20), (29,8.5), (29,16.5) | 90,90,90,90,90,90 |
| Zigzag | (10,6.5), (10,16.5), (19,9.5), (19,19.5), (28,6.5), (28,16.5) | 0,0,0,0,0,0 |
| Maze | (11,20), (6,16.5), (11,12), (20,9), (29,15), (21,19.5) | 90,0,90,0,90,0 |
| Dense | (14,8.5), (14,18.5), (20,8.5), (20,18.5), (26,8.5), (26,18.5) | 0,0,0,0,0,0 |
| Fishbone-inspired | (9,7), (19,11), (29,7), (9,19), (19,22), (29,19) | -45,0,45,45,0,-45 |

모든 맵의 START=(2.5,13), GOAL=(35.5,13). 원래 Zigzag/Maze/Dense/Asymmetric의 서로 다른 출발/목표는 이번 비교 조건에서 통일했다. 이전 실험 JSON과 캡처는 이전 버전의 기록으로 유지한다. Standard의 기존 일반 실행 작업자 배치는 보존하되, **성능 비교에서는** 모든 맵의 작업자를 아래 공통 시나리오로 재배치한다.

| 작업자 | 초기 위치 | 왕복 목적지 |
|---|---|---|
| worker-0 | (35,3) | (35,23) |
| worker-1 | (3,23) | (7,23) |
| worker-2 | (35,23) | (31,23) |
| worker-3 | (3,3) | (7,3) |

정적 실험은 4명 강체를 삭제하지 않고 목표 속도를 0으로 유지한다. 동적 실험은 동일한 초기 위치·속도 상한·왕복 목표를 사용한다. 실제 강체 간 접촉 때문에 시간별 궤적이 달라질 수 있으므로 동일한 궤적 파일을 강제 재생하는 실험이라고 표현하지 않는다.

## 알고리즘·지표 정의

- 기존 A* 유지: 0.5m 8연결 격자, 대각선 모서리 통과 금지. Dijkstra는 동일한 격자/비용에서 휴리스틱을 0으로 설정한다.
- RRT: 3000회 제한, 3초 제한, step1.5m, goal bias0.15, 시드42/43/44. 반환 경로에 결정적 shortcut을 적용한다. 격자 최단 경로와 동일한 최적성을 보장하지 않는다.
- 모든 planner는 동일한 원형 로봇 반경+안전거리, 회전 선반과 연속 선분 0.08m 간격 검사를 사용한다. AABB를 대각선 선반의 실제 장애물로 대신 사용하지 않는다.
- 지역 회피 Naive/VO/ORCA는 그대로 유지하며, 전역 planner 비교는 ORCA만 사용한다.
- Path Length는 반환된 계획 경로 길이, Actual Distance는 Newton body_q 이동 거리다.
- Planning Time은 경로 계산·검사·RRT shortcut의 CPU wall time(ms). Newton physics/지역 회피 시간과 별도다.
- Expanded Nodes는 A*/Dijkstra에서 실제 확장한 고유 격자 노드 수. RRT는 N/A; iterations와 tree_nodes를 별도로 기록한다.
- Travel Time은 목표 거리≤0.25m 및 속도≤0.02m/s로 도달·정지한 시뮬레이션 시간. 미도달은 N/A와 관측 종료 시간을 함께 기록한다.
- Success Rate는 성공 건수/전체 실행 건수. planning failure도 분모에 포함한다.
- Replanning Count=0: 실행 중 재탐색은 구현하지 않았고 초기 계산은 재탐색으로 세지 않는다. 작업자 회피는 기존 ORCA가 담당한다.
- Turning Count는 계획 polyline의 15도 이상 방향 변화 수. 실제 강체의 헤딩 회전 횟수는 N/A다.
- 평균·모분산(ddof=0)을 기록한다. A*/Dijkstra는 각 1회이므로 분산 N/A; RRT는 각 조건 3회다. 이는 소규모 기능 검증이며 통계적 우월성 검정이 아니다.

원시 행의 `initial_workers`는 저장된 첫 Newton 프레임의 작업자 좌표다. 동적 모드에서는 이미 첫 물리 스텝이 진행되어 설정된 spawn과 최대 약0.00073m 차이가 있다. 정확한 설정 초기 위치는 `maps[].workerSpawnPositions`에 기록되어 있다.
