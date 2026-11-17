# Newton 3D 통합 시뮬레이터 검증 — 2026-11-09

리뷰: gufspsnglcysfivdpfogaxohxwithnxj · 작업 루트 /opt/app · WIZ main
실행 모델: gpt-6.1-sol · 추론 수준 medium (실행 프로세스 인자 확인, 요청 모델과 동일).

## 기존 구현 조사

- 프런트엔드는 React가 아닌 WIZ Angular 18/Pug이다. 기존 디자인과 메뉴를 유지했다.
- 기존 run_newton API는 Python 3.12의 독립 .venv에서 newton_warehouse.py를 subprocess.run으로 실행하고, 계산 종료 후 RESULT_JSON을 반환했다.
- 이전 Start는 배치 계산, Playback/Pause/Reset은 setInterval로 결과 프레임을 이동했다. 물리 프로세스를 제어하지 않았다.
- A*와 Naive/VO/ORCA는 algorithms/ 및 simulator/agents.py에 실제 구현되어 있다. 이를 그대로 재사용한다.
- 로봇/작업자는 ModelBuilder.add_body와 동적 충돌 형상을 사용한다. 공유 힘 제어기가 목표 속도를 Newton body_f에 적용하고 XPBD가 적분한다.
- body_q/body_qd는 Newton state에서, Contacts는 CollisionPipeline에서 읽는다. 기존 SVG는 XY 좌표를 25px/m로 투영했다.

## 구현 구조와 동작

대시보드 → live_newton API → 세션별 Python 3.12 newton_live 워커 → 기존 A*/회피 알고리즘 + Newton XPBD.

워커는 Newton 1.7.0 / Warp 1.19.0 / Viser 1.1.1을 재사용한다. 상태에는 Z·쿼터니언을 포함한 전체 body_q와 body_qd, 목표 속도, 현재 접촉 형상 ID, 안전 상태, 도달 여부, 계산 시간을 기록한다. 물리 계산 시간은 힘 적용·접촉 파이프라인·XPBD 구간을, 알고리즘 시간은 choose_velocity 호출을 측정한다.

ViewerViser.set_model/log_state가 같은 강체 자세를 3D로 렌더링한다. 바닥·벽·선반은 Newton 고정 충돌 형상, 로봇은 원통, 작업자는 캡슐이다. 격자·ID·출발/목표·A* 경로·실제 경로·현재 위험 고리를 추가했다. R0와 접촉하거나 안전거리를 위반한 현재 상태에서 빨간 고리를 표시한다. 누적 충돌 횟수만으로 위험 표시를 계속 켜지 않는다.

WIZ의 일반 커스텀 경로는 WebSocket 업그레이드를 HTTP 400으로 거부했다. 공통 서버 설정 변경·재시작 없이 원본 Viser 클라이언트의 WebSocket 인터페이스를 워커의 제한된 HTTP 중계에 연결했다. 메시지 포맷과 3D 렌더러는 설치된 Viser 그대로다. HTTPS 환경의 혼합 콘텐츠를 피하도록 브라우저에서 현재 origin 기준으로 중계 URL을 만든다.

- Start / 알고리즘 변경: 새 물리 세션. 선택한 실제 알고리즘을 공통 제어기에 연결.
- Pause / Resume: 실행 중 물리 적분 정지·재개. 정지 ACK 이후 시간/자세가 고정됨을 확인.
- Reset: 모델·강체를 다시 생성하고 t=0 정지 상태로 복원.
- 종료 후: 저장 기록 모드로 전환. 서버가 저장된 전체 강체 자세와 기록 시간 간격으로 재생·탐색하며 새 물리 계산은 하지 않음.
- 3D/2D는 워커의 같은 커서와 기록을 사용. 브라우저에 별도의 위치 적분기나 재생 타이머 없음.
- API 상태는 약 140ms 주기로 읽음. 네트워크 지연으로 UI 텔레메트리가 최신 물리 프레임보다 늦게 표시될 수 있음.
- 경로/위험 표시 설정은 새 알고리즘 및 기록 로드에서도 유지.
- 동시 워커 최대 4개, 15분 미사용 시 종료, 브라우저 중계 연결은 60초 미사용 시 정리. 프레임 30~900.
- 완성 기록: warehouse-collision-avoidance/results/live/{token}/record.json. 부분 프레임과 상태도 같은 세션 폴더에 저장.

## 변경 파일

| 경로 (WIZ main 기준) | 변경 |
|---|---|
| src/app/page.algorithm.run/view.ts | 실제 제어 API, 상태·기록 모드, 3D/2D 전환, 전체화면 |
| src/app/page.algorithm.run/view.pug | ViewerViser iframe, 2D 분석 뷰, 지표·강체 상태 표, 버튼 |
| src/app/page.algorithm.run/view.scss | 청록색 대형 뷰어와 반응형 배치 |
| src/app/page.algorithm.run/api.py | 기존 API 유지, 세션 생성·상태·제어·기록 API 추가 |
| src/route/warehouse.viewer/app.json | 같은 origin의 뷰어·중계 경로 |
| src/route/warehouse.viewer/controller.py | 설치된 Viser HTML 제공 및 제한된 HTTP 중계 |
| warehouse-collision-avoidance/newton_warehouse.py | 전체 자세·목표 속도·접촉·시간 계측, 라이브 브리지 훅, 단순 강체 |
| warehouse-collision-avoidance/newton_live.py | 물리 실행 게이트, 실제 Pause/Resume/Reset, 공통 기록 커서, Viser 오버레이 |
| warehouse-collision-avoidance/viewer_transport.py | 로컬 Viser 바이너리 연결의 제한된 큐·HTTP 서버 |
| warehouse-collision-avoidance/viewer_transport.js | Viser 워커의 HTTP 전송 어댑터 |
| warehouse-collision-avoidance/tests/test_newton_viewer.py | CPU 접촉, Newton/Viser 좌표 일치, 실제 알고리즘 회귀 |
| warehouse-collision-avoidance/tests/browser_warehouse.py | 실제 Chromium에서 UI·알고리즘·재생·충돌 회귀 |
| warehouse-collision-avoidance/README.md | 현재 3D 웹 실행 및 제어 설명 |
| warehouse-collision-avoidance/docs/newton_3d_validation.md | 이 검증 기록 |
| warehouse-collision-avoidance/docs/validation/ | 실제 브라우저 캡처와 검증 결과 JSON |
| devlog.md 및 devlog/2026-11-09/013-newton-3d-viewer.md | 프로젝트 개발로그 |
| /opt/app/devlog/20261109/014-newton-3d-viewer.md | ReviewOps 개발로그 |

기존 newton_minimal.py, requirements-newton.txt, algorithms/, 기존 CSV·그래프·Pygame 소스는 수정/삭제하지 않았다. 테스트용 pytest 9.2.0 및 보조 패키지 2개만 Newton 독립 .venv에 추가했다.

## 실제 검증

| 확인 항목 | 결과/근거 |
|---|---|
| WIZ 빌드 | API 추가 시 clean build 및 최종 normal build 성공 |
| CPU 물리 | Newton 1.7.0, Warp 1.19.0, CPU에서 실제 강체 이동 |
| Python 회귀 | .venv/bin/python -m pytest tests → 16 passed |
| 환경 호환성 | uv pip check --python .venv/bin/python → 108 packages compatible |
| Viser 렌더 좌표 | 실제 ViewerViser packed shape transform과 해당 body_q 위치를 atol=1e-6로 대조 |
| 2D 좌표 | Chromium에서 SVG transform과 API body_q 투영 좌표를 1e-6 이내로 대조 |
| 접촉 | 테스트에서 실제 동적 강체를 접촉시키고 Contacts 형상 ID, 충돌 횟수, risk 검증 |
| 위험 시각화 | 해당 실제 접촉 기록을 Viser에서 렌더하고 빨간 고리 캡처 확인 |
| 실시간 제어 | API와 브라우저에서 Start/Pause/Resume/Reset, 정지 중 시간·상태 불변, t=0 복원 확인 |
| 기록 제어 | 프레임 탐색·재생·정지, 비교 결과 VO 기록 3D 연결 확인 |
| 알고리즘 | Naive/VO/ORCA 모두 실제 실행/목표 속도/표시 변경 확인 |
| 브라우저 | headless Chromium에서 실제 WebGL canvas, 2D/3D, 카메라 회전·확대, 전체화면, 경로 토글 확인 |
| 오류 | 검증 경로의 pageerror/console error 없음. 신규 워커 error.json 없음 |
| 기존 기능 | 기존 12개 테스트 포함 통과, 3알고리즘 비교 API/결과 재사용 확인 |

브라우저는 기존 설치된 Playwright와 Chromium을 사용했다. 실행 예:

```bash
cd /opt/app/project/main/warehouse-collision-avoidance
.venv/bin/python -m pytest tests
PYTHONPATH=/tmp/bike-playwright \
WAREHOUSE_CHROMIUM=/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome \
/opt/conda/envs/app/bin/python tests/browser_warehouse.py
```

브라우저 스크립트는 localhost:3000 WIZ가 실행 중인 개발 환경 전용이며, 먼저 CPU 접촉 테스트를 실행해 생성된 collision-record.json을 사용한다. 테스트 세션은 종료 시 close한다.

## 오류 및 해결

- WIZ 일반 경로 WebSocket 400 → Viser 바이너리 프로토콜을 유지한 HTTP 중계로 해결.
- 기존 Playback만으로 물리 정지 불가 → 워커 적분 루프의 명령 게이트 및 ACK 추가.
- 과거 누적 충돌만으로 계속 빨갛게 표시 → 표시 시점의 Contacts/안전 상태로 변경.
- 비교 실행 중 이전 결과를 선택해 반응 없는 동작 → 계산·제어 중 결과 버튼 비활성화.
- 새 세션에서 경로 토글이 기본값으로 복구됨 → 새 세션 초기화 시 표시 설정 동기화.
- pytest 부재 → 시스템 패키지 대신 독립 Newton .venv에 설치.
- 초기 브라우저 검사에서 중복 canvas/기존 설명 표를 함께 선택한 검사 스크립트 실패 → 실제 Three.js canvas와 통합 대시보드 내부로 선택자 한정 후 재검증.

## 미구현·미검증 및 남은 리스크

- GPU/CUDA, ViewerGL, GPU 성능 비교는 미검증. 서버 물리는 CPU, 테스트 브라우저는 software WebGL임.
- 실제 public HTTPS 도메인·여러 원격 동시 사용자 부하·지속 운영 성능은 미검증. localhost 브라우저와 같은 origin HTTP 중계는 검증.
- 30Hz는 요청한 물리 스텝/재생 간격이다. CPU·HTTP 중계 비용 때문에 실제 벽시계 30FPS를 보장하지 않음.
- 충돌·안전거리 통계와 위험 고리는 제어 로봇 R0 기준. 전체 강체 쌍의 전역 충돌 총계는 미구현.
- 고품질 로봇/작업자 모델은 미구현. 현재 원통·캡슐과 박스 선반을 사용.
- XY만 포함한 기존 기록을 3D 기록으로 변환하는 기능은 없음. 강체 자세가 없는 기록은 재실행 안내로 거부.
- dash pytest 플러그인과 Viser line_width의 deprecation 경고가 있으나 테스트 실패는 없음.
- 빌드에서 기존 npm 취약점 67건이 보고됨. 이번 범위에서는 프런트엔드 의존성을 변경하지 않음.
- 서버 재시작·원격 배포·Git push는 수행하지 않음.
