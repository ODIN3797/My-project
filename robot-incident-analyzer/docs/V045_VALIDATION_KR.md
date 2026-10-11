# v0.4.5 검증 결과 — 2026-10-11

## 변경 사항
- `sensor_msgs/msg/LaserScan` XCDR1 메시지 해석: frame, scan metadata, range/intensity 길이, finite 범위값 통계.
- `inf` 센서 거리값은 ROS2에서 일반적인 no-return 표현이므로 결함으로 추정하지 않음.
- 잘못된 range_min/max, zero angle_increment (여러 빔), 잘못된 intensities 길이는 데이터 품질 경고.
- 3개 연속 모든 range가 NaN일 때만 데이터 품질 경고, 최초 한 번 보고하고 정상 회복 후 재발 시 재발행.
- 새 합성 DB3/MCAP 테스트 8개 포함, 총 69개 테스트 통과.

## 성능 측정 (합성 데이터, 단일 Ubuntu/Linux 컨테이너, Python 3.13.5)

| 입력 | 파일 크기 | 분석 시간 | 프로세스 Peak RSS | 기본 메시지 상한 경고 |
|---|---:|---:|---:|---|
| DB3 150,000 msgs | 58.75 MiB | 2.072 s | 252.9 MiB | 없음 |
| MCAP 150,000 msgs | 59.94 MiB | 2.133 s | 250.3 MiB | 없음 |
| DB3 220,000 msgs | 86.16 MiB | 2.681 s | 305.2 MiB | 발생; 첫 200,000만 분석 |

이는 CPU/메모리 보증치, 1 GB 실측 성능, 서로 다른 로봇 타입에 대한 호환성 증거가 아니다. 별도 결과 JSON은 압축 내 `validation/results_v045/`에 포함된다.

## 외부 공개 데이터
기존 공개 BAGEL tour.mcap은 독립 작성된 샘플이며 실물 로봇에서 수집되었다는 근거가 없음. GitHub Actions에서 포맷 호환성 시험을 수행하고, 분석된 ROS 메시지 종류의 수를 확인하도록 구성. 이벤트에 독립적인 고장 정답 라벨이 없어 장애 검출률은 측정하지 않음.

## 여전히 미검증
- 실제 물리 로봇의 장애 로그 3건 및 현장 엔지니어 평가.
- ROS2 사용자 5인의 설치/정확도/실질적 시간 절감 측정.
- 수백 MB~수 GB의 압축 MCAP, 성능의 일관성, 일부 최신 ROSIDL 인코딩.
- 진단 precision/recall 및 safety-critical 판단.

## 해외 배포 게이트
실제 기록의 provenance 확인과 오탐/미탐 레이블 평가 이전에는 상용 정확도를 주장하지 않고, 알파 테스트용으로만 배포한다.
