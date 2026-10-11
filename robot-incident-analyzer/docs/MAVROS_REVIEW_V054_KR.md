# v0.5.4 신규 기능 · 로봇 상태 데이터와 2인 검증

## MAVROS/AMR 센서 데이터

- `mavros_msgs/msg/State`: connected/armed/guided/manual_input/mode/system_status 수집, 명시적 상태 변화만 이벤트로 남김
- `mavros_msgs/msg/ExtendedState`: landed_state / vtol_state 변경 기록
- `mavros_msgs/msg/StatusText`: MAVLink 심각도 0~4 메시지를 증거 이벤트로 기록(중복 연속 메시지는 억제)
- `sensor_msgs/msg/Range`: 초음파/IR 단일 거리값 파싱. REP-117에 따라 +∞/−∞는 정상 의미가 있으므로 자동 고장 판정 금지

현재는 표준 ROS2 메시지 타입에 한한 부분 지원이며, 모든 MAVROS 플러그인/커스텀 메시지를 자동 지원하지 않습니다. MAVROS FCU 상태 기록은 실제 하드웨어 오류 확인과 다릅니다.

## 서로 다른 엔지니어 2명의 라벨 비교

```bash
python3 -m robot_incident_analyzer compare-reviewers rate_timeline.json reviewer_A.json reviewer_B.json --output reviewers_out
xdg-open reviewers_out/reviewer_comparison.html
```

정확히 같은 SHA-256·토픽·메시지 타입·명시적 reviewed 상태, 다른 리뷰어 ID가 필요합니다. 두 사람이 검토한 시간에서만 일치율/코헨 카파를 계산하고, 한 명만 검토한 구간은 따로 계산합니다. 일치하더라도 정답으로 자동 확정하지 않고, 불일치 구간은 재검토 목록에 표시합니다.

`validation/v054_evidence`의 예시는 전부 **가상 리뷰어**로 생성한 기능 검증 자료입니다. 실물 장애 탐지율/오탐률을 의미하지 않습니다.

## 검증 단계

공개 Zenodo 주행 기록 2개에 포함된 sonar `Range` CDR 페이로드 호환성 검사를 GitHub Actions로 수행합니다. 성공 여부와 수집 메시지 수는 실행 결과를 통해 별도로 확인해야 합니다.

- ROS2 `sensor_msgs/Range` has a **schema-version difference**: Foxy/Humble terminate after `range`, while Jazzy/Rolling add `variance`. v0.5.4 accepts exactly these two recognized CDR layouts without inventing a variance value.
