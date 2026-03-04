# Sim-to-Sim Inverse Control Pipeline: 결과 정리

## 개요

Blender에서 생성한 경로를 Genesis 물리 시뮬레이터에서 재현하는 파이프라인.
MPPI로 최적 제어 입력을 탐색하고, BC(Behavioral Cloning)로 새로운 경로에 대한 일반화를 확인.

---

## Step 1. MPPI 경로 최적화 결과 (6개 경로)

> MPPI(Model Predictive Path Integral)로 각 경로의 최적 throttle/steer 제어 입력을 탐색.
> **파란색**: Blender 기준 경로 | **초록색**: MPPI 최적화 경로

### 1-1. Original

<!-- 영상: golden_inputs_optimized_v2.csv 기반 MPPI 주행 -->

https://github.com/user-attachments/assets/670176b7-ce4b-482e-b88d-2aebb3af6422

| 항목 | 값 |
|------|-----|
| 프레임 수 | 439 |
| Mean Drift | 0.64 m |
| Max Drift | 3.26 m |

---

### 1-2. Right

<!-- 영상: golden_right.csv 기반 MPPI 주행 -->

https://github.com/user-attachments/assets/8c307023-96b9-4ad0-b2f9-db269022ffbe

| 항목 | 값 |
|------|-----|
| 프레임 수 | 339 |
| Mean Drift | 0.93 m |
| Max Drift | 4.92 m |

---

### 1-3. Sharp Right

<!-- 영상: golden_sharp_right.csv 기반 MPPI 주행 -->

(https://github.com/user-attachments/assets/d59d8bdb-914e-43a8-a00c-f6f8fe83a3bc)

| 항목 | 값 |
|------|-----|
| 프레임 수 | 289 |
| Mean Drift | 0.92 m |
| Max Drift | 4.49 m |

---

### 1-4. S-Curve

<!-- 영상: golden_s_curve.csv 기반 MPPI 주행 -->

https://github.com/user-attachments/assets/ff151565-9660-4f5b-95ee-f5339056207c

| 항목 | 값 |
|------|-----|
| 프레임 수 | 269 |
| Mean Drift | 1.69 m |
| Max Drift | 10.18 m |

---

### 1-5. Wide Left

<!-- 영상: golden_wide_left.csv 기반 MPPI 주행 -->

https://github.com/user-attachments/assets/f35dddc2-704c-4305-bfb7-4fb868d8a285

| 항목 | 값 |
|------|-----|
| 프레임 수 | 213 |
| Mean Drift | 1.37 m |
| Max Drift | 10.01 m |

---

### 1-6. Straight Curve

<!-- 영상: golden_straight_curve.csv 기반 MPPI 주행 -->

https://github.com/user-attachments/assets/97c0d3b0-a7ca-4e89-917c-1b67026d4d4f

| 항목 | 값 |
|------|-----|
| 프레임 수 | 190 |
| Mean Drift | 1.31 m |
| Max Drift | 10.08 m |

---

## Step 2. BC 학습 및 새로운 경로 일반화

> 위 6개 경로의 MPPI golden data로 BC MLP를 학습.
> 학습에 사용하지 않은 새로운 경로 3개를 BC 정책으로 주행시켜 일반화 성능 확인.
> **파란색**: Blender 기준 경로 | **빨간색**: BC 추론 경로

### BC 모델 구성

| 항목 | 내용 |
|------|------|
| 입력 차원 | 27 (오차 3 + 현재 상태 4 + 미래 kappa×10 + 미래 v×10) |
| 구조 | 27 → 64(ReLU) → 64(ReLU) → 2(Tanh) |
| 출력 | throttle, steer (범위 [-1, 1]) |
| 손실 함수 | MSE |
| 옵티마이저 | Adam |
| 학습/검증 분할 | 80% / 20% |
| 학습 데이터 수 | 약 1,700 샘플 (6개 경로 합산) |

---

### 2-1. SS-Curve (미학습 경로)

<!-- 영상: BC 정책으로 ss_curve 주행 (blender_data_ss_curve_processed.csv) -->

https://github.com/user-attachments/assets/85db77a4-0532-4ad9-920c-54ed61f22b01

| 항목 | 값 |
|------|-----|
| 경로 길이 | 500 프레임 |
| X 범위 | -31 ~ 9 m |
| Y 범위 | -76 ~ -30 m |
| 특징 | 완만한 이중 S자 곡선 |

---

### 2-2. Hairpin (미학습 경로)

<!-- 영상: BC 정책으로 hairpin 주행 (blender_data_hairpin_processed.csv) -->

https://github.com/user-attachments/assets/4ef9447a-d25d-4051-8a94-22858842305e

| 항목 | 값 |
|------|-----|
| 경로 길이 | 450 프레임 |
| X 범위 | -37 ~ 38 m |
| Y 범위 | -37 ~ 0 m |
| 특징 | 180° U턴 포함 급커브 |

---

### 2-3. Slalom (미학습 경로)

<!-- 영상: BC 정책으로 slalom 주행 (blender_data_slalom_processed.csv) -->

https://github.com/user-attachments/assets/3522ca80-e934-45dc-aac2-69a50441ec11

| 항목 | 값 |
|------|-----|
| 경로 길이 | 270 프레임 |
| X 범위 | -40 ~ 39 m |
| Y 범위 | -3 ~ 3 m |
| 특징 | 좌우 방향 전환 6회 반복 |

---

## 결과 요약

| 경로 | 유형 | 결과 |
|------|------|------|
| original | 학습 경로 | MPPI mean drift 0.64m |
| right | 학습 경로 | MPPI mean drift 0.93m |
| sharp_right | 학습 경로 | MPPI mean drift 0.92m |
| s_curve | 학습 경로 | MPPI mean drift 1.69m |
| wide_left | 학습 경로 | MPPI mean drift 1.37m |
| straight_curve | 학습 경로 | MPPI mean drift 1.31m |
| ss_curve | **미학습** | BC 정책으로 주행 시도 |
| hairpin | **미학습** | BC 정책으로 주행 시도 |
| slalom | **미학습** | BC 정책으로 주행 시도 |

> 학습 데이터의 다양성이 BC 일반화 성능에 직접적인 영향을 미치며,
> 새로운 경로의 kappa/속도 분포가 학습 분포와 크게 벗어날수록 Covariate Shift로 인한 성능 저하가 발생.
