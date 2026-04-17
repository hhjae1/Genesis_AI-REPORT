# Genesis Path2Control 구동계/마찰 처리 정리 보고서

## 1. 현재 프로젝트의 위치

현재 구현한 모델은 Blender→Genesis 간의 직접적인 Sim2Sim 제어 번역기가 아니라,  
**목표 경로(path)가 주어졌을 때 Genesis 차량의 throttle/steer를 반환하는 Path2Control**임.

- teacher: **Genesis 내부 MPPI**
- student: **BC MLP**
- 현재 BC MLP의 성격: **특정 차량 / 특정 dynamics family에 맞춰진 single-vehicle Path2Control**임

즉 현재 정책은 특정 Genesis 차량과 특정 물리 가정 위에서 동작하는 경량 경로 추종 정책으로 이해할 수 있음.

---

## 2. 현재 단계의 핵심 질문

현재 연구 단계에서 확인하려는 핵심은 아래와 같음.

1. **Mass, torque, friction이 Genesis vehicle dynamics에서 어떻게 반영되는가**
2. **이들을 연구 관점에서 step-wise variable로 볼 것인지, rollout-static condition으로 둘 것인지 어떻게 정리할 것인가**
3. **특히 friction 계산 방식이 차량 거동에 얼마나 큰 영향을 주는가**
4. **friction semantics를 바꿀 경우, 기존 MPPI teacher와 BC MLP를 그대로 사용할 수 있는가**

현재 초점은 path OOD 일반화가 아니라,  
**같은 경로에서 차량/구동계 조건이 바뀔 때 Path2Control이 어떻게 달라지는가**를 정리하는 데 있음.

---

## 3. 구동계 파라미터 해석

### 3.1 Mass

#### physics level
- mass는 차량 dynamics에 지속적으로 반영되는 값임
- 공개 Genesis 코드상 runtime setter도 존재함
- 예를 들어 `set_mass_shift`, `set_links_inertial_mass`와 같은 API 및 solver accessor 경로가 확인되었음

#### 현재 연구 단계 해석
- mass는 본질적으로 dynamics에 계속 관여하므로, 넓게 보면 동적으로도 해석 가능한 파라미터임
- 그러나 **교수님 미팅 기준 현재 1차 단계에서는 mass를 step-wise changing variable로 직접 학습하지 않고, rollout-static condition으로 두고 진행**하는 것이 맞다고 정리되었음

#### 현재 정리
- **mass는 physics적으로는 step-wise dynamics에 반영되는 값임**
- **하지만 이번 1차 연구에서는 static conditioning으로 단순화함**

---

### 3.2 Torque / Actuation

#### physics level
- torque 및 actuation은 실제 physics step마다 force/control input 형태로 차량 거동에 반영됨
- 공개 Genesis에는 generic DOF control API와 force range clamp가 존재함
- `control_dofs_force`, `set_dofs_force_range` 등이 존재하며, 내부 control force는 force range에 의해 clamp됨

#### 현재 연구 단계 해석
- torque 역시 physics level에서는 분명히 step-wise하게 작동하는 요소임
- 그러나 **교수님 미팅 기준 현재 단계에서는 torque까지 time-varying drivetrain state로 직접 학습하는 것이 아니라, 우선 rollout-static condition으로 단순화**하는 방향이 맞다고 정리되었음

#### 현재 정리
- **torque는 physics적으로는 step-wise하게 반영됨**
- **하지만 이번 1차 연구에서는 static condition으로 처리함**  
`` -> static하게 둘 경우 torque가 극단적인 값으로 설정되지 않는 한 mlp가 close-loop으로 보정``
---

### 3.3 Friction

#### physics / semantics level
- friction coefficient 자체는 runtime에 갱신 가능함
- 공개 Genesis 문서 기준 rigid contact friction은 **두 geometry friction 중 큰 값(`MAX`)**으로 설명되어 있었음
- 공개 코드에서도 friction 관련 `max` 기반 처리 로직이 확인되었음

#### 문제의식
- `MAX` 방식이면 노면 friction이 매우 낮아도 타이어 friction이 높을 경우, 빙판과 같은 저마찰 surface effect가 비현실적으로 약해질 수 있음
- 교수님이 friction semantics를 문제 삼은 이유도 바로 이 지점이었음
  - 빙판인데도 타이어 friction이 노면 효과를 덮어써서 “안 미끄러지는” 상황이 나올 수 있음
  - 즉 저마찰 노면의 영향이 제대로 반영되지 않을 수 있음

#### 현재 연구 단계 해석
- friction은 단순한 static vehicle parameter라기보다, **환경(surface condition)과 결합된 핵심 변수**로 보는 것이 맞음
- 다만 **현재 1차 단계에서 바로 local trigger 기반의 세밀한 step-wise friction teacher를 만드는 것이 목표는 아님**
- 현재 단계에서 중요한 것은 아래와 같음
  1. friction combine semantics를 더 타당하게 정리할 것
  2. 그 semantics 아래에서 nominal teacher를 다시 세울 것
  3. 이후 필요하면 다양한 노면 조건으로 확장할 것

#### 현재 friction 처리 원칙
- **combine rule은 `MULTIPLY`를 기준으로 채택함**
- **1차 teacher 재생성은 uniform asphalt 같은 균일 노면에서 먼저 수행함**
- 이후 확장 단계에서 아래와 같은 **global surface condition variation**으로 확장함
  - wet road
  - low-friction road
  - nearly icy road

#### 현재 정리
- **friction은 semantics 자체가 중요한 physics assumption임**
- **현재는 local step-wise friction보다, 전역적인 노면 상태 차이를 처리 가능한 구조로 먼저 정리하는 단계임**
- **기준 combine rule은 `MULTIPLY`로 둠**

---

## 4. Friction 계산 방식 비교 실험

### 4.1 실험 목적

본 실험의 목적은 다음과 같았음.

- Genesis에서 friction 계산 방식을 바꾸었을 때 실제 차량 거동이 달라지는지 확인하는 것
- `MAX`가 저마찰 노면을 비현실적으로 처리하는지 검증하는 것
- `MIN`, `MULTIPLY`가 더 타당한 대안이 될 수 있는지 비교하는 것

### 4.2 실험 방식

Genesis 문서에는 friction 처리 방식이 `MAX`로 설명되어 있었지만,  
**공개 문서 수준에서 `MAX / MIN / MULTIPLY`를 공식적으로 바꿔 쓸 수 있다는 설정은 명시적으로 확인되지 않았음.**

따라서 이번 비교는  
**“공식 메뉴 옵션 비교”를 수행한 것이 아니라, friction 계산식을 코드 수준에서 분기하여 실제 차량 거동 차이를 실험적으로 확인한 것**이었음.

즉 핵심은 다음과 같았음.

- 원래 코드에서 friction은 `MAX` 식으로 처리되고 있었음
- 해당 계산 자리를 `MIN`, `MULTIPLY`로 바꿔가며 비교했음
- 각 계산 방식이 실제 yaw, slip, lateral velocity, forward distance를 어떻게 바꾸는지 관찰했음

이 실험의 목적은  
**“공식 built-in 설정이 있는지”를 확인하는 것이 아니라, friction 계산 semantics가 실제 차량 거동을 바꾸는지 확인하는 것**이었음.

### 4.3 1차 실험 결과와 한계

초기 실험에서는 세 모드 간 lateral displacement 차이가 크게 나타나지 않았음.

이에 대한 해석은 다음과 같았음.

- 속도가 충분히 높지 않았음
- 조향 시점에서 차량이 이미 느려져 있었음
- 따라서 저마찰 surface effect가 lateral drift로 충분히 드러나지 못했음

다만 longitudinal distance 차이는 나타났기 때문에,  
**friction 계산 방식 변경이 실제 dynamics에 반영되었다는 점 자체는 확인되었음.**

### 4.4 2차 실험 결과

고속(8 m/s), 저마찰 노면, open-loop 급조향 조건에서 다시 실험한 결과는 다음과 같이 정리되었음.

#### MAX
- 타이어 friction이 노면 friction을 덮어썼음
- 빙판처럼 낮은 노면에서도 비교적 잘 굽어들었음
- 감속도 빠르게 나타났음
- 저마찰 surface effect를 과소표현하는 경향이 있었음

#### MIN
- 노면이 지배적으로 작용했음
- slip angle, yaw rate, lateral velocity가 크게 감소했음
- 직진성이 강하게 유지되었음
- 빙판 물리에 가장 직관적으로 가까운 거동을 보였음

#### MULTIPLY
- MAX와 MIN의 중간 거동을 보였음
- 어느 정도 미끄러지면서도 조향 반응은 유지되었음
- 현실적인 타협안으로 사용 가능하다고 판단되었음

### 4.5 실험 결론

이번 실험으로 확인된 핵심은 다음과 같았음.

- friction combine semantics는 **실제 차량 거동을 크게 바꿨음**
- `MAX`는 저마찰 노면 효과를 비현실적으로 약화시킬 수 있었음
- `MIN`은 극단적인 저마찰 노면을 가장 직관적으로 반영했음
- `MULTIPLY`는 현실적인 중간 해석으로 사용하기 적절했음

즉 friction 계산 방식은 단순 구현 세부사항이 아니라,  
**teacher generation과 Path2Control 학습 전체에 영향을 주는 핵심 physics assumption**이라고 정리되었음.

---

## 5. Multiply 기준으로 teacher를 다시 만들어야 하는 이유

기존 MPPI teacher와 BC MLP는 사실상 `MAX` friction semantics 위에서 만들어졌을 가능성이 큼.

그러나 이제 기준 physics를 `MULTIPLY`로 바꾸면 아래와 같은 변화가 생김.

- environment dynamics 자체가 달라짐
- 같은 path라도 optimal throttle/steer가 달라질 수 있음
- 따라서 기존 `MAX` world에서의 optimal control sequence는 더 이상 `MULTIPLY` world의 golden truth라고 보기 어려움

### 정리
- **path 자체는 재사용 가능함**
- **하지만 path에 붙어 있는 optimal control label은 재생성 필요함**
- 즉 아래 순서가 필요함
  - path는 그대로 사용함
  - MPPI/grid search는 `MULTIPLY` 기준으로 다시 수행함
  - teacher를 새로 생성함
  - BC MLP를 다시 학습함

---

## 6. 현재 결론

### 구동계 파라미터
- **mass, torque는 physics level에서는 step-wise dynamics와 연결되어 있음**
- **하지만 이번 1차 연구에서는 교수님 지시에 따라 rollout-static condition으로 단순화함**

### friction
- **friction은 단순 파라미터가 아니라 physics semantics 문제로 정리됨**
- **기준 combine rule은 `MULTIPLY`로 둠**
- **1차 teacher 재생성은 uniform asphalt에서 먼저 수행함**
- 이후 필요하면 **global friction variation**으로 확장함

### teacher / base policy
- 기존 `MAX` 기준 teacher는 baseline으로 남길 수는 있어도,  
  `MULTIPLY` 기준 메인 teacher로는 사용할 수 없음
- 따라서 **`MULTIPLY` 기준 nominal MPPI/grid search와 BC 재학습이 필요함**

---

## 7. 이후 추가 확장 방향

현재 단계 이후의 확장 방향은 아래와 같이 정리됨.

### 7.1 friction 확장
- uniform asphalt 이후
- 전역적으로 다른 노면 조건으로 확장함
  - wet road
  - low-friction road
  - nearly icy road

### 7.2 mass adaptation
- `MULTIPLY` 기준 nominal teacher와 BC를 다시 세운 뒤
- mass를 rollout-static condition으로 둔 상태에서 adaptation 진행함

### 7.3 그 이후 단계
- 필요 시 local trigger 기반 friction 변화
- 더 복잡한 surface transition
- friction-aware adaptation 또는 conditioned policy로 확장 가능함

---

## 8. 최종 한 줄 요약

현재 연구 단계에서는  
**mass와 torque는 physics적으로는 step-wise하게 작동하지만 연구 모델링에서는 static condition으로 단순화하고, friction은 `MULTIPLY` semantics를 기준 physics로 채택한 뒤 uniform asphalt에서 nominal teacher를 다시 생성하는 것이 핵심임.**


## 9. 미팅 후 최종 정리

- mass, torque, friction은 physics level에서는 모두 step-wise하게 반영될 수 있음
- 특히 friction은 특정 구간을 box/volume trigger로 지정해, 해당 영역에 들어간 바퀴의 friction coefficient를 step-wise하게 바꾸는 방식으로 처리 가능함
- 다만 현재 1차 연구 단계에서는 이러한 파라미터를 동적으로 학습하지 않고, **구동계·질량·마찰 조건을 static하게 고정한 상태**에서 teacher와 policy를 구성하는 방향으로 정리됨
- friction semantics는 기존 `MAX` 대신 `MULTIPLY` 기준으로 다시 최적화 및 teacher 재생성이 필요함
- 다만 기존처럼 경로 전체에 대한 ST를 미리 계산해 데이터로 수집하는 방식은, 동적 상황이나 외란이 발생했을 때 대응에 한계가 있음
- 따라서 현재 상태를 매 step 반영해 자세를 보정할 수 있는 **대응기(controller)** 는 강화학습 기반으로 준비하는 방향으로 정리됨
