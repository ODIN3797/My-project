# Robot Incident Analyzer v0.4.3 — 외부 데이터 검증 현황

검증일: 2026-10-11

## 확인된 사항

- Python 자동 테스트 51개 성공 (기존 46개 + 독립 MCAP 포맷/압축/손상 테스트 5개).
- Ubuntu 호환 Linux / Python 3.13.5에서 Python wheel을 빌드하고 별도 가상환경에 설치해 실행 확인.
- 압축 MCAP에 대해 Python `zstandard`가 없는 환경에서 시스템 `libzstd`로 압축 해제 성공.
- MCAP 청크 CRC 오류와 파일 끝부분 손상 시 오류 발생하도록 수정.
- 합성 ROS2 MCAP 1개에서 4개 토픽, 35개 메시지, 이벤트 6개 읽음.

## 실패 또는 미완료

- 공개된 물리 로봇 MCAP/DB3 원본 파일을 실제로 내려받아 분석하지 못함. 외부 바이너리 다운로드가 환경에서 차단됨.
- 현업 로봇 데이터로 장애 탐지 정확도/정밀도/재현율 검증: **미완료**.
- 외국 현업 ROS2 엔지니어 실사용 인터뷰: **0명**.
- 업계 경쟁사 대비 처리시간/효율 비교: **미완료**.
- 상용 판매 가능 여부: **검증되지 않음**.

## 경쟁 구도 관련

- BAGEL (https://github.com/Hussain004/BAGEL): 무료 브라우저 기반 ROS bag 뷰어/편집기.
- bagx (https://github.com/rsasaki0109/bagx): ROS1/ROS2 파일 적합성 검사, 센서 간격 및 탐색/제어 파이프라인 분석.

단순 뷰어·통계 분석은 이미 경쟁이 강함. 제조사별 장애 이력의 증거 연결, 조치 우선순위, 장애 보고 자동화 등의 전문 분야를 검증해야 함.

## 실제 공개 데이터로 검증하는 다음 명령

JKK Research Center (https://jkk-research.github.io/dataset/jkk_dataset_02/) 페이지에서 직접 받은 `.mcap`을 기준으로:

```bash
cd robot-incident-analyzer-v0.4.3-beta
python3 -m unittest discover -s tests -q
bash scripts/validate_local_real_bag.sh /home/user/Downloads/sample.mcap physical output_real
```

파일 출처가 실제 주행 기록임이 확인된 경우에만 `physical`을 사용. 실제 파일을 확보하지 못했다면 이 명령을 실행했다고 주장하지 말 것. `REVIEW_REQUIRED`로 종료해도 보고서의 이유를 읽어야 하며, 이는 즉시 제품 결함을 의미하지 않음.

실행 결과: `output_real/FIELD_RESULTS.md`, `output_real/field_results.json`, `output_real/case_01/report.html`.

## 결론

**기술 사전 검증: 성공. 실측 로봇 정확도 및 해외 사용성: 아직 검증 필요.**
