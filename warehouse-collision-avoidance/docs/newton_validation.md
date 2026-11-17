# Newton 3D 환경 검증 기록

검증일은 2026-11-09이며, 프로젝트의 독립 `.venv`에서 수행했다.

## 환경과 설치

- OS: Ubuntu 24.04.4 LTS, Linux x86_64
- CPU: Intel Xeon Gold 6138, 논리 CPU 80개
- Python: 3.12.3 (`uv venv`)
- GPU/드라이버: NVIDIA 장치, `nvidia-smi`, CUDA 드라이버 모두 없음
- 설치: Newton 1.7.0, Warp 1.19.0, MuJoCo/MuJoCo Warp 3.15.0, Viser 1.1.1
- Warp 장치: `cpu`만 인식, CUDA 실행 불가

Newton 공식 설치 문서는 Python 3.10 이상(3.11 이상 권장), Linux x86-64, CUDA 가속 시 지원 NVIDIA GPU와 드라이버를 요구하며 로컬 CUDA Toolkit은 필수가 아니라고 안내한다. 이 서버는 GPU 요구사항을 충족하지 않지만 Warp CPU 경로로 설치와 실행이 가능했다.

## 실제 실행 결과

```bash
uv venv .venv --python python3.12
uv pip install --python .venv/bin/python 'newton[examples]' 'viser>=1.1.1'
.venv/bin/python -m newton.examples basic_shapes --viewer null --device cpu --num-frames 20
.venv/bin/python newton_minimal.py --viewer null --frames 720
.venv/bin/python newton_minimal.py --viewer viser --frames 720 --port 8099
uv pip check --python .venv/bin/python
```

- 공식 `basic_shapes`: CPU에서 20프레임 정상 종료
- 최소 프로토타입: 434프레임, 물리 시간 7.2333초에 목표 반경 0.25m 진입
- 로봇: `(-3.0, 0.0)`에서 `(1.2559, 0.0)`까지 실제 Newton 강체로 이동
- 상태 읽기: 최종 위치와 선속도 `(0.9996, 0.0)` 확인
- 접촉 읽기: 최대 강체 접촉 1개, 로봇 접촉 대상 `ground` 확인
- `ViewerNull`: GUI 없이 정상 완료
- `ViewerViser`: `http://localhost:8099` 서버 기동, 상태/접촉 렌더 파이프라인 정상 완료
- `ViewerGL`: DISPLAY가 없어 `pyglet.display.xlib.NoSuchDisplayException` 발생; 이 서버에서는 사용 불가
- 의존성 검사: 105개 패키지 호환성 이상 없음

## 오류와 조치

1. 시스템 Python 3.12에 `ensurepip`가 없어 표준 `venv` 생성에 실패했다. 시스템 패키지는 변경하지 않고 기존 `uv`로 독립 환경을 만들었다.
2. 최초 360프레임 제한에서는 목표 도달 전 종료됐다. 제한을 720프레임으로 늘렸고 실제로는 434프레임에서 목표에 도달했다.
3. ViewerGL은 X11 DISPLAY 부재로 실패했다. 웹 기반 ViewerViser와 무창 ViewerNull로 각각 시각화 경로와 헤드리스 실행을 검증했다.

## 알고리즘 연동 판단

기존 Naive·VO·ORCA가 출력하는 X-Y 선호 속도를 Newton 제어기의 목표 속도 또는 평면 힘으로 변환하고, `state.body_q/body_qd`를 관측 상태로, `Contacts`를 실제 접촉 지표로 사용하는 어댑터를 만들 수 있다. 다만 현재 프로토타입은 단일 로봇 PD 제어만 검증했으며 세 알고리즘을 Newton에 연결하거나 동일 조건 성능을 측정하지 않았다. 다음 단계는 공통 어댑터, 사람/다중 로봇 강체, 정적 선반 충돌 제약, 결정적 시드와 지표 회귀 테스트 순서다.

## 공식 기준

- 설치: <https://newton-physics.github.io/newton/stable/guide/installation.html>
- 시각화: <https://newton-physics.github.io/newton/stable/guide/visualization.html>
- 소스/릴리스: <https://github.com/newton-physics/newton>
