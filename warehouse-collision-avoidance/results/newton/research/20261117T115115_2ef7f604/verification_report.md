# 최종 검증 보고

자동 테스트: 163개 통과, 0개 실패, 70개 의존성 경고, 132.11초.

초기 신규 테스트의 NumPy 2차원 cross 호출 오류를 명시적 행렬식으로 수정한 뒤 전체를 재실행했다.

WIZ 정상 빌드 성공. 실제 브라우저 5개 분석 메뉴·4개 시나리오·2개 인구 구성·6개 맵 전환과 잘못된 파일 접근 차단 통과.

원본 파일 2423개의 SHA256 보존 확인. 240회 원본과 예비18회를 분석했고 Dense120행은 중복 부분집합이다.

새 통제 시뮬레이션30회(시드42), 별도 전역 탐색54회. 검증용5프레임 테스트는 연구 표본으로 합산하지 않았다.

과거142개 테스트 기록을 별도 복사했다. 이번 추가 테스트20개를 포함한 총163개가 현재 기준이다.

원본의 목표227/240·무충돌152/240·안전53/240 재계산 일치, 중복·누락·설정/물리 상태 불일치 없음.

계측 전후 동일 조건24쌍의 물리 지표 일치. 보완 재개 시 기존30개 ID/CSV 변경 및 새 실행 없음.

원본 누락 시 가상 수치 생성 없이 종료하고 기존 출력 폴더 재사용은 명시적 재개 외 거부함을 검증했다.

원본 CSV와 dashboard.json의 모든 수치 열을 대조했다. 기존 원본 CSV의 P95·정지 시간·LP 내부 횟수는 N/A이며 단일 시드 보완 자료와 혼합하지 않았다.

검증 중 호환 별칭 CSV가 기존 실행에 의해 갱신되는 경로를 발견해 내용 해시가 일치하는 legacy_snapshots에서 원본을 복원했다. 중간 출력도 별도 보존했다. save_result는 이후 기존 별칭을 변경하지 않으며 실행별 metrics.csv를 반환한다.

## 미완료·해석 한계

- 과거 미측정 프레임별 항목과 선호 속도는 복구할 수 없어 N/A다. 별도30회는 단일 시드여서 전체240회의 P95로 대체할 수 없다.
- 주 분석은Map1/10시드, 예비 시나리오는2시드다. 추가 맵 주행·모든 시나리오의10시드 확장은 후속 연구다.
- ORCA의 C 인과 원인과 E 프레임의 단일 원인은 미확정이다. 독립 허용해 검사에서 확정된 A 오류는 없어 솔버를 교체하지 않았다.
- 통행 간격은0.25m 샘플 기반 운영 지표다. 연속 기하의 전역 최소 폭으로 단정하지 않는다.
- 공개 Robot 커밋과 로컬 WIZ HEAD/dirty 상태는 다르다. 공개 트리에 로컬240회 배치가 없으며 게시/푸시하지 않았다.

## 수정·추가 소스 파일

- warehouse-collision-avoidance/newton_warehouse.py

- warehouse-collision-avoidance/newton_results.py

- warehouse-collision-avoidance/experiment_archive.py

- warehouse-collision-avoidance/algorithms/base.py

- warehouse-collision-avoidance/algorithms/orca.py

- warehouse-collision-avoidance/algorithms/velocity_obstacle.py

- warehouse-collision-avoidance/requirements-newton.txt

- warehouse-collision-avoidance/README.md

- warehouse-collision-avoidance/research_data.py

- warehouse-collision-avoidance/research_statistics.py

- warehouse-collision-avoidance/research_orca.py

- warehouse-collision-avoidance/research_layouts.py

- warehouse-collision-avoidance/research_figures.py

- warehouse-collision-avoidance/research_supplement.py

- warehouse-collision-avoidance/research_telemetry.py

- warehouse-collision-avoidance/research_report.py

- warehouse-collision-avoidance/research_pipeline.py

- warehouse-collision-avoidance/verify_research.py

- warehouse-collision-avoidance/finalize_research.py

- warehouse-collision-avoidance/docs/research_reproduction.md

- warehouse-collision-avoidance/tests/test_research_analysis.py

- warehouse-collision-avoidance/tests/test_controlled_encounters.py

- warehouse-collision-avoidance/tests/browser_research_results.py

- src/app/page.algorithm.run/api.py

- src/app/page.algorithm.run/view.ts

- src/app/page.algorithm.run/view.pug

- src/app/page.algorithm.run/view.scss

- src/route/warehouse.experiments/controller.py

개발로그: devlog.md 및 devlog/2026-11-17/011-robot-research-analysis.md.

## 생성 자료

필수5개 분석CSV, 짝지은 통계/민감도/보완CSV, 원본감사·메타데이터·실행별로그,7절 연구 보고서, 발표 요약을 생성했다.

24개 PNG(200dpi, Noto Sans KR):
- figs/01_safe_success.png
- figs/02_collisions.png
- figs/03_crossing.png
- figs/03_dense_traffic.png
- figs/03_head_on.png
- figs/03_narrow_passing.png
- figs/04_runtime_mixed.png
- figs/04_runtime_workers.png
- figs/05_operations_mixed.png
- figs/05_operations_workers.png
- figs/06_distance_safety.png
- figs/07_clearance_distribution.png
- figs/08_orca_case1.png
- figs/08_orca_case2.png
- figs/08_orca_case3.png
- figs/09_layout_planning.png
- figs/10_layout_map1.png
- figs/10_layout_map2.png
- figs/10_layout_map3.png
- figs/10_layout_map4.png
- figs/10_layout_map5.png
- figs/10_layout_map6.png
- figs/11_supplement_mixed.png
- figs/11_supplement_workers.png

전체 파일 목록은 manifest.json, 원본 해시는 audit.json, 최종 분석 소스 해시는 analysis_provenance.json에 있다.
