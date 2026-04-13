# Drivetrain_Generalization Pipeline

## 0. 왜 Genesis인가

### 1. Solver와 MLP와의 결합

```
Genesis solver 단독
├── 속도: 빠름 (병렬, GPU)
└── 정확도: Bullet보다 낮음
        ↓ MLP 결합

Genesis solver + MLP 보정
├── 속도: 유지 (Genesis 기반)
└── 정확도: MLP가 solver의 체계적 오차를 학습해서 보정
```

### 2. 왜 이게 가능한가

Genesis가 **미분가능(differentiable)** 하게 설계되어 있기 때문에, solver가 만들어내는 오차에 대해 gradient 역전파 가능 

- **Bullet**: 미분 불가 → MLP가 오차를 학습할 gradient 경로 없음
- **Genesis**: 미분 가능 → solver 오차 → MLP → 보정값의 end-to-end 학습 가능

> **"왜 Genesis여야 하는가"의 핵심:**
> Bullet이 단독 물리 정확도는 높을 수 있지만,
> 미분가능성 덕분에 MLP와 결합하여 정확도를 보정할 수 있는 것은 Genesis만 가능.
> **속도(병렬 환경) + 정확도(MLP 보정)를 동시에 달성**하는 것이 목표.

### 3. 현재 상태 및 한계

Genesis 미분가능 시뮬레이션 코드는 존재하지만 (`diff.py`, `diff_gjk.py`, `backward.py`), 강체 접촉(contact) + 마찰(friction) 구간에서 gradient가 불안정하거나 미구현 상태. 차량은 바퀴-지면 접촉이 핵심인데 정확히 이 부분이 막힘

```
현재:  Genesis solver (fast, less accurate) + MPPI sampling으로 우회
목표:  Genesis solver + MLP 보정 (end-to-end differentiable)
```

MPPI는 미분가능성 없이도 작동하는 **샘플링 기반** 방법이라 현재 우회책으로 쓰이고 있다. 미분가능 차량 dynamics가 구현되면 MPPI 대신 gradient 기반 최적화로 대체할 수 있는 구조.

→ "MLP 결합 보정"은 현재 차량 접촉 dynamics에 대해서는 **미구현 상태이며 미래 방향**.

### 4. 그럼에도 지금 Genesis를 쓰는 이유

미분가능성이 막혀있어도, **병렬 환경** 측면에서 Genesis는 현재도 결정적인 메리트를 가짐.

**실제 수치 (RTX 5070 Ti, 차량 URDF 기준 직접 측정):**

| n_envs | steps/sec | 총 처리량 |
|---|---|---|
| 200 (현재 MPPI) | 502 | 0.10M env-steps/s |
| 2,000 | 451 | 0.90M env-steps/s |
| 10,000 | 226 | 2.26M env-steps/s |
| **20,000** | **142** | **2.83M env-steps/s ← 피크** |
| 50,000 | 53 | 2.64M env-steps/s |

- VRAM은 병목이 아님 (50,000 envs에서도 59MB만 사용)
- 처리량 기준 최대 약 **2만 개** 병렬 환경 (이 이상은 compute 포화로 감소)
- 현재 MPPI 200개 → 20,000개로 늘리면 샘플 품질 100배 향상 가능

**결정론적 재현성:**

Genesis는 동일한 초기 상태 + 동일한 제어 입력에 대해 완전히 동일한 결과를 보장 (diff=0.0 확인). MPPI golden truth 수집, BC 학습 데이터 재현, 민감도 실험 등 모든 단계에서 실험 재현성이 확보됨.


`` 현재 파이프라인은 미분가능성 없이도 동작하지만, 병렬 환경과 GPU 가속만으로도 압도적인 속도 우위를 가짐. 미분가능 dynamics가 완성되면 MLP 결합까지 확장 가능한 구조.``

---

## 1. 연구 배경 및 목적

**기존 파이프라인:**
- Blender에서 kinematic guide로 경로 주행 → golden truth 수집
- Genesis에서 MPPI로 optimal control 탐색 → BC MLP 학습
- BC MLP: path → (throttle, steer) 출력

**문제 인식:**
BC MLP는 특정 구동계 기준값(BC 학습 시 사용한 URDF의 기본 물리 파라미터 — mass, friction, torque가 변경 없는 상태)으로 수집한 데이터로 학습됨. 다른 구동계(질량 다른 차량 등)에 동일한 (throttle, steer)를 주면 차량 반응이 달라져 경로 이탈 발생.

**연구 목표:**
기존 BC 파이프라인을 건드리지 않고, 구동계가 달라져도 경로를 잘 추종할 수 있도록 보정하는 방법 설계.

    
현재 BC MLP:
  - 특정 구동계(nominal URDF)로 수집한 데이터로 학습
  - path → (s, t) 출력
  - 이 (s, t)는 nominal 구동계에 최적화된 값

  문제:
  - 다른 구동계(mass 2배, 타이어 마찰 다름 등)에 같은 (s, t)를 주면 차가 다르게 반응
  - path는 동일해도 구동계가 다르면 BC가 낸 (s, t)로는 그 경로를 못 따라감

  우리가 하려는 것:
  - path + 구동계 정보 → BC가 낸 (s, t)를 보정 → 다른 구동계에서도 같은 경로를 따라갈 수 있게

---

## 2. 1차 실험: 구동계 민감도 진단 (Sensitivity Analysis)

**실험 설계 — One-factor-at-a-time:**

| 파라미터 | 범위 | 의미 |
|---|---|---|
| mass | ×0.5 ~ ×2.0 | 차량 질량 변화 |
| friction | ×0.5 ~ ×1.5 | 타이어 마찰 변화 |
| torque | ×0.7 ~ ×1.5 | 최대 구동 토크 변화 |

**경로 선택 이유 — 학습된 4개 경로(right, s_curve, wide_left, straight_curve) 사용:**

학습되지 않은 경로(OOD)를 사용하면 성능 저하의 원인이 "구동계 파라미터 변화 때문인지" vs "BC가 처음 보는 경로라 추종 자체를 못 하는 것인지" 분리가 불가능함. 학습된 경로에서 구동계만 바꾸면 경로 추종 능력은 고정되므로 구동계 파라미터의 영향만 순수하게 측정 가능.

**실험 환경:**
- 지면 friction = 2.0
- 타이어 friction = 2.5 (`set_friction(2.5)`)
- contact friction = max(2.5, 2.0) = 2.5 (Genesis max 방식)

---

## 3. 실험 결과

### 1. MASS — HIGH SENSITIVITY

https://github.com/user-attachments/assets/c2bb92a4-9b07-4d48-96a8-8846176a31c1

![alt text](images/drivetrain_mass.png)


| 조건 | mean_drift | degrad× |
|---|---|---|
| ×0.5 | 10.3m | 8.7× |
| ×0.75 | 2.6m | 2.2× |
| ×1.0 (기준값) | 1.18m | — |
| ×1.5 | 1.88m | 1.6× |
| ×2.0 | 3.62m | 3.1× |

양방향 모두 민감. 특히 가벼운 쪽(×0.5)이 더 심각.

### 2. FRICTION — 영향 없음

`mean_drift 1.04~1.44m로 전 범위 flat.`

원인:  Genesis contact friction = max(타이어, 지면) 방식. 지면(2.0)이 고정된 상태에서 타이어 friction이 2.0 이하로 내려가면 지면이 지배하여 변화 없음.   
→ 시뮬레이터 구조적 한계로 friction 실험 의미 x

### 3. TORQUE — 영향 없음

`mean_drift 1.15~1.19m로 flat.`

원인: Genesis에서 실제 바퀴에 가해지는 힘은 `throttle × MAX_TORQUE`로 계산됨. 실험에서 torque 한계값을 낮췄을 때, BC가 매 프레임 v_error(목표속도와 현재속도의 차이)를 입력으로 받아 throttle을 실시간으로 높여서 보상함. 즉 torque 한계가 줄면 throttle이 올라가 실제 가해지는 힘이 유지되는 closed-loop 구조. 현재 경로들이 토크 한계에 걸리지 않는 주행 범위이므로 throttle 조정으로 완전히 흡수 가능.

---

## 4. 핵심 발견

mass만 유일한 민감 파라미터. 그 이유:

- mass 변화의 주 영향은 속도가 아닌 lateral 관성 (코너링)
- v_error는 기준값과 거의 동일한데 drift만 3배 이상 커짐
- 무거워지면 코너에서 lateral force 부족 → 경로 이탈
- 이는 v_error 피드백으로 보상 불가 → BC의 구조적 한계

---

## 5. 설계된 파이프라인: Residual Adapter

```
[기존 BC MLP — Frozen]
    입력: path 정보 (kappa, v lookahead, position error 등)
    출력: u_base = (throttle_base, steer_base)
            ↓
[Residual Adapter MLP — 새로 학습]
    입력: u_base, z_drive, 현재 state, 과거 n프레임 history
    출력: Δu = (Δthrottle, Δsteer)
```

**Adapter 핵심 설계 원칙:**

- **BC frozen** → 기존 path2control 성능 보존. BC는 gradient 없이 u_base만 제공
- **Adapter는 보정값(Δu)만 출력** → 전체 제어값을 처음부터 계산하지 않고 BC가 낸 답에서 얼마나 더하거나 빼야 하는지만 출력. 기준값 조건에서는 Δu≈0, 구동계가 달라질수록 Δu가 커지는 구조
- **현재 state 입력** → z_drive(mass 값)만으로는 "이 차가 무겁다"는 것만 알 뿐, 지금 실제로 얼마나 밀리고 있는지 모름. 직선/코너 여부에 따라 같은 mass라도 필요한 보정량이 다름
- **과거 n프레임 history 입력** → 관성 효과는 한 프레임에 나타나지 않고 누적됨. 직전 프레임들의 밀림 추세를 봐야 현재 보정 강도를 결정 가능

**z_drive (구동계 conditioning 벡터):**

Adapter가 어떤 구동계 조건에서 보정해야 하는지 알기 위한 필수 입력. 학습 시 "mass=m일 때 이 보정이 맞다"를 학습하고, 테스트 시 새로운 mass 값을 입력하면 그에 맞는 Δu를 출력하는 구조. z_drive 없이는 Adapter가 구동계 조건을 알 수 없어 일반화 불가.


현재 실험 결과 mass만 유의미한 민감도를 보이므로 우선 mass만 사용:
```
z_drive = [mass_multiplier]
```
추후 friction/torque도 유의미한 영향이 확인되면 확장:
```
z_drive = [w_mass × mass_mult, w_friction × friction_ratio, w_torque × torque_ratio]
```

테스트 시 mass를 미리 알고 있다고 가정하고 z_drive에 직접 입력 (oracle 가정). 현실 적용 시에는 mass 추정 단계가 별도로 필요.

**Loss:**

```python
u_base    = BC_frozen(path)
            # 기존 BC MLP가 path 정보만 보고 낸 (throttle, steer)

Δu        = Adapter(u_base, z_drive, state, history)
            # Adapter가 출력하는 보정값 (Δthrottle, Δsteer)

u_optimal = MPPI_golden_truth(mass=m)
            # mass=m 조건에서 MPPI가 찾아낸 최적 (throttle, steer)

# [학습 시]
loss = MSE(u_base + Δu, u_optimal)
     + λ × mean(|Δu_t - Δu_{t-1}|)
     # clip 없음 — gradient가 끊기지 않도록

# [실행(배포) 시]
u_final = clip(u_base + Δu, -1, 1)
          # 실제 차량에 입력할 때만 적용
```

BC는 frozen이라 gradient가 흐르지 않고, Adapter의 가중치만 이 loss로 업데이트됨.

---

## 6. 진행 중: Adapter 학습 데이터 수집

**방법 (MPPI golden truth 재수집):**
- mass ×0.5, ×0.75, ×1.0, ×1.25, ×1.5, ×2.0 조건별로
- 4개 경로에 대해 MPPI 재실행 → 각 mass 조건에서의 u_optimal 확보

**MPPI cost 함수:**
```
cost = W_VEL     × (v - v_ref)²
     + W_HEADING × heading_error²
     + W_KAPPA   × lateral_error²
     + W_RATE    × |Δsteer|
     + W_ACCEL   × |Δthrottle|
```

**파라미터 탐색:**
- 각 mass 조건 × 4개 경로 조합별로 MPPI 파라미터(W_VEL, W_HEADING, W_KAPPA, LAMBDA 등) grid search 수행
- mass가 달라지면 동역학이 바뀌어 동일한 가중치로는 MPPI가 최적 해를 제대로 탐색하지 못할 수 있음
- 각 조건에서 진짜 최적 u_optimal을 확보하는 것이 목표
