# 알고리즘 구현: Newton 물류창고 충돌 회피

Newton CPU 강체 시뮬레이션에서 A*·Dijkstra·RRT 전역 경로와 Naive·VO·ORCA 지역 회피를 비교하는 구현이다. 현재 알고리즘 과목의 설명·구현 페이지와 연결 코드를 포함한다.

## 최신 구현

- Standard, Horizontal, Zigzag, Maze, Dense, Fishbone 6종 창고 맵.
- 6개 맵 × Naive·VO·ORCA 총 18조건 비교, 동일한 초기 작업자 배치와 고정 파라미터.
- Viser 3D·2D 화면, 실행·일시정지·초기화, 기록 재생.
- 실제 CSV 결과·성능 그래프·전역 경로 실험과 브라우저 검증 자료.
- 시뮬레이션 시간 내 목표 미도달은 timeout으로 기록한다.

## 저장소 구조

| 경로 | 내용 |
|---|---|
| `warehouse-collision-avoidance/` | 독립 Python 시뮬레이터, 실험, 테스트, 측정 자료 |
| `src/app/page.algorithm/` | WIZ 알고리즘 설명·구현 탭 |
| `src/app/page.algorithm.run/` | WIZ 구현 페이지 및 Newton API |
| `src/model/newton.py` | 기존 2D 실험 모델 |
| `src/route/warehouse.viewer/` | 동일 출처 Viser 전송 라우트 |
| `src/assets/warehouse-simulator/` | 2D 비교 CSV와 그래프 |

## 독립 실행

```bash
cd warehouse-collision-avoidance
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-newton.txt
.venv/bin/python newton_warehouse.py --algorithm orca --scenario medium --agents 4 --frames 360 --viewer null
.venv/bin/python -m pytest
```

WIZ API 연동 테스트는 상위 `src/`가 있는 이 저장소 구조에서 실행한다. GUI 실행과 반복 실험은 [시뮬레이터 설명서](warehouse-collision-avoidance/README.md)를 참고한다.

## WIZ 구현 페이지 연결

기존 WIZ 프로젝트 루트에 이 저장소의 `warehouse-collision-avoidance/`와 `src/`를 같은 상대 경로로 병합한다. 기존 프로젝트의 `base` 컨트롤러, `layout.sidebar`, `portal/season` 서비스·세션 및 페이지 공유 컴포넌트가 필요하다. 이 저장소는 기존 서비스의 알고리즘 부분을 추출한 것으로 전체 WIZ 서비스의 독립 실행 번들은 아니다.

Newton 가상환경은 해당 프로젝트의 `warehouse-collision-avoidance/.venv`에 설치한다. WIZ 일반 빌드 후 `/algorithm` 또는 `/algorithm/run`에서 접근한다. 데이터베이스 설정과 기존 프로젝트의 계정·공유 설정은 이 저장소에 포함하지 않는다.

## 측정 자료와 제한

[6개 맵 비교 기록](warehouse-collision-avoidance/docs/all-map-comparison/README.md)에 실제 18조건 결과와 화면 검증 자료를 보관한다. 기본 medium/seed42 조건에서의 성공 결과를 다른 인원·시드·속도의 무충돌 보장으로 해석하지 않는다. 이전 실험과 제한은 각 문서에 기재하였다.

## 민감정보 처리

SSH 비밀키·공개키, 환경설정 비밀값, 데이터베이스 설정, 가상환경, 실행 세션 디렉터리는 업로드하지 않는다. 검증 자료에 남은 세션 식별값은 `REDACTED_SESSION`으로 치환하였다. `.gitignore`에서 키 파일·환경 파일·실행 세션을 제외한다.
