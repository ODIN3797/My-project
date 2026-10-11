# Robot Incident Analyzer v0.4 시작 가이드

현재는 **현장용 검증이 끝나지 않은 실험용 도구**입니다. 가상 ROS2 로그로만 자동 검증했습니다.

## 1. 기본 데모

```bash
python3 -m robot_incident_analyzer demo --output demo_data
python3 -m robot_incident_analyzer analyze demo_data --output output
xdg-open output/report.html
```

## 2. 커스텀 ROS2 메시지 데모

```bash
python3 -m robot_incident_analyzer demo-custom --output demo_custom
python3 -m robot_incident_analyzer analyze demo_custom/fictional_custom_telemetry.mcap \
  --config examples/config_custom.json --output output_custom
xdg-open output_custom/report.html
```

- `.msg` 파일: `examples/schemas/<패키지명>/msg/<메시지명>.msg`
- 매핑 파일: `examples/config_custom.json`
- `schema_dirs`는 설정 파일이 있는 폴더를 기준으로 해석합니다.
- 커스텀 속도명령/피드백을 분석하려면 `custom_messages`에서 `role`과 `linear_x` 필드 경로를 지정합니다.
- 토픽 이름이 다르면 `topics`의 `command`와 `odometry` 경로를 실제 bag에 맞게 수정하거나, 두 경로를 제거해 자동 후보 탐색을 사용합니다.
- 의미가 불확실한 신호는 자동 추정하지 않습니다. `cmd_vel_raw`, `cmd_vel_safe`처럼 역할이 다른 경우 엔지니어 확인이 필요합니다.

## 3. 브라우저 GUI

```bash
python3 -m robot_incident_analyzer gui --config examples/config_custom.json
```

http://127.0.0.1:8765 접속 → 파일 업로드 → 분석 → 토픽 후보 확인 → HTML 보고서.

## 4. 앞으로의 과제

실제 로봇에서 기록한, 사용 허가를 받은 데이터로 진단 정확도와 성능을 별도 검증해야 합니다. 회사 기밀/고객 로그/사내 커스텀 메시지 정의를 무단 업로드하거나 공개하지 마세요. 이 로컬 GUI를 인터넷에 노출해서는 안 됩니다.
