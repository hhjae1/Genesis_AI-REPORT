# Research History Index

> 모든 연구 문서의 중앙 인덱스

---

## 📁 Genesis AI Research

**Repository**: https://github.com/hhjae1/Genesis_AI-REPORT

### Drone System Analysis
- **[[25-09-20] drone_urdf.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-09-20]%20drone_urdf.md)** - Genesis 드론 URDF 파일 구조 및 설정 분석
- **[[25-09-22] drone_physics.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-09-22]%20drone_physics.md)** - Genesis 드론 물리 시뮬레이션 원리 및 구현 방법
- **[[25-09-25] drone_principle.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-09-25]%20drone_principle.md)** - Genesis 드론 기본 동작 원리 및 제어 메커니즘 분석
- **[[25-09-30] drone_mlp_reward.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-09-30]%20drone_mlp_reward.md)** - MLP 네트워크 구조 및 강화학습 보상 함수 설계

### Training & Memory Management
- **[[25-10-14] drone_time.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-10-14]%20drone_time.md)** - 드론 시뮬레이션 시간 체계와 병렬 학습 단위 (episode, rollout)
- **[[25-10-14] drone_training_gathering.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-10-14]%20drone_training_gathering.md)** - 병렬 환경의 GPU 기반 학습과 메모리 구조
- **[[25-10-18] drone_rollout_memory.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-10-18]%20drone_rollout_memory.md)** - PPO 학습 메모리 구조 및 관리

### URDF & Data Integration
- **[[25-11-17] urdf_collision_configuration_solution.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-11-17]%20urdf_collision_configuration_solution.md.md)** - URDF 차량 Collision 설정 문제 해결
- **[[25-11-25] blender_data_genesis_mlp.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-11-25]%20blender%20data_genesis_mlp.md)** - Blender 차량 직진 데이터 추출 및 Genesis MLP 적용
- **[[25-12-17] data_extraction_revision_and_issues.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-12-17]%20data_extraction_revision_and_issues.md)** - Blender 데이터 추출 재조정 및 S자 주행 데이터 문제점

---

## 📊 Timeline & Milestones

### 주요 마일스톤
- **9월**: 드론 예제 시뮬레이션 기초 분석 (URDF, 물리 엔진, 제어)
- **10월**: 강화학습 프레임워크 및 메모리 효율성에 대한 분석
- **11월**: 간단한 urdf를 만들고 직접 Genesis에 적용
- **12월**: 데이터 처리 최적화 및 이슈 해결(진행 중)

### 2025-09
- **Genesis Drone Analysis** - URDF, 물리 엔진, 제어 시스템 분석 완료

### 2025-10
- **Genesis Training Analysis** - PPO 메모리 구조 및 병렬 학습 분석

### 2025-11
- **Genesis URDF Vehicle Setup** - 차량 Collision 설정 완료
- **Blender-Genesis Integration** - 직진 주행 데이터 추출 및 MLP 적용

### 2025-12
- **Genesis Data Extraction Issues** - S자 주행 데이터 처리 문제점 파악

---

## 🔍 Quick Reference

### Genesis AI
- **Drone URDF**: [[25-09-20] drone_urdf.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-09-20]%20drone_urdf.md)
- **Reinforcement Learning**: [[25-09-30] drone_mlp_reward.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-09-30]%20drone_mlp_reward.md)
- **Training Memory**: [[25-10-18] drone_rollout_memory.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-10-18]%20drone_rollout_memory.md)
- **Data Integration**: [[25-11-25] blender_data_genesis_mlp.md](https://github.com/hhjae1/Genesis_AI-REPORT/blob/main/[25-11-25]%20blender%20data_genesis_mlp.md)

---

## 📝 Notes

- 모든 문서는 Markdown 형식으로 작성됨
- 주요 언어: Python/PyTorch
- 이미지 및 다이어그램 포함

---

**Last Updated**: 2025-12-17