# RL_drivetrain_process_pipeline

## 1. RL Pipeline 목적

본 파이프라인의 목적은 **새로운 경로에 대한 path OOD generalization**을 평가하는 것이 아니라,  
**같은 경로에서 drivetrain/surface condition이 바뀌었을 때 BC frozen nominal controller 위에 붙인 RL residual이 이를 보정할 수 있는지 확인하는 것**

즉, BC는 nominal path follower로 고정하고, RL residual은 차량/노면 dynamics 변화에 대한 보정기로 학습.



## 2. 전체 실험 순서 요약

```text
Step 1.
Rollout-static friction/torque variation
- episode마다 condition randomization
- episode 동안 condition 유지
- mass는 우선 비활성화 가능

Step 2.
Global friction condition variation
- asphalt / wet / low-friction / icy
- episode마다 전역 노면 condition 랜덤

Step 3.
Local friction trigger
- 특정 구간에서만 friction 변화
- 주행 중 surface transition 대응 확인

Step 4.
Mass / torque time-varying extension
- 필요 시 후순위로 추가
```

## 1단계: Rollout-static drivetrain/surface variation

### 목적

episode 시작 시 drivetrain/surface condition을 랜덤하게 샘플링하고, episode 동안 해당 조건을 고정  
이 상태에서 frozen BC가 nominal action을 출력하고, RL residual이 달라진 dynamics 조건에 맞춰 추가 보정을 학습하는지 확인  
mass, torque, friction은 physics level에서는 step-wise하게 반영될 수 있지만, 현재 1차 연구 단계에서는 바로 time-varying variable로 학습하기보다 **rollout-static condition**으로 단순화

### 설정

```text
episode 시작 시 랜덤 샘플링:
- torque condition
- friction condition
- mass condition

episode 동안:
- 샘플링된 조건 유지
```

예시 설정:

```text
torque_scale   ~ Uniform(0.7, 1.0)
friction_scale ~ Uniform(0.6, 1.0)
mass_scale     ~ Uniform(1.0, 1.3)
```

다만 초기 실험에서는 구현 안정성을 위해 다음처럼 시작하는 것이 적절하다.

```text
1차 권장:
- torque_scale randomization
- friction_scale randomization
- mass_scale은 옵션만 두고 비활성화
```

## 2단계: Global friction condition variation

### 목적

friction은 단순 차량 파라미터가 아니라 surface condition과 결합된 핵심 physics assumption 
따라서 1단계에서 단순 friction scale randomization이 동작하면, 다음 단계에서는 전역 노면 조건을 명시적으로 나누어 실험

### 설정

episode마다 전체 노면 조건을 하나 선택

```text
global surface condition:
- asphalt
- wet road
- low-friction road
- nearly icy road
```

예시:

```text
asphalt:
friction_scale ≈ 1.0

wet road:
friction_scale ≈ 0.7 ~ 0.8

low-friction road:
friction_scale ≈ 0.4 ~ 0.6

nearly icy road:
friction_scale ≈ 0.1 ~ 0.3
```


## 3단계: Local friction trigger 또는 step-wise transition

### 목적

2단계까지는 episode 전체에서 하나의 surface condition을 유지
하지만 실제 도로에서는 특정 구간에서만 노면 상태가 바뀔 수 있다. 따라서 이후에는 local friction trigger를 통해 구간별 friction 변화를 추가

### 설정

```text
특정 path 구간 또는 box/volume 영역 지정

차량이 해당 영역에 들어가면:
- wheel friction coefficient 변경
- 또는 surface friction condition 변경
```

### 예시:

```text
구간 A:
asphalt

구간 B:
low-friction patch

구간 C:
asphalt 복귀
```


## 4단계: 필요 시 mass/torque time-varying

### 목적

mass와 torque도 physics level에서는 step-wise dynamics에 반영될 수 있음.  
그러나 현재 1차 연구 범위에서는 mass/torque를 직접 time-varying state로 학습하는 것은 후순위

### 확장 조건

아래 조건이 만족된 뒤 진행

```text
1. rollout-static torque/friction variation에서 residual RL 효과 확인
2. global friction condition variation에서 효과 확인
3. local friction trigger에서 step-wise surface 변화 대응 확인
```

그 이후 필요하면 mass/torque도 time-varying하게 확장

### 예시

```text
주행 중 torque limit 감소:
max_torque(t) = nominal_torque * scale(t)

주행 중 mass 변화:
mass(t) = nominal_mass * scale(t)
```


## 3. 최종 정리

현재 목적은 **같은 경로에서 drivetrain/surface condition이 바뀌었을 때, 기존 BC nominal controller 위에 붙인 RL residual이 변화된 dynamics를 보정할 수 있는지 확인**

따라서 초기 위치/heading perturbation보다 우선해야 할 것은 다음

```text
1. rollout-static torque/friction variation
2. global friction condition variation
3. local friction trigger
4. 필요 시 mass/torque time-varying
```

즉, BC는 nominal path follower로 고정하고, RL residual은 차량/노면 dynamics 변화에 대한 보정기로 학습
