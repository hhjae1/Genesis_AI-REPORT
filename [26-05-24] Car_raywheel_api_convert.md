# Car_raywheel → genesis_vehicle SDK migration


## 0. API 정리

코드 convert 시 reference 용. 각 항목의 자세한 동작 / 적용 효과는 본문
migration 섹션에서 실제 사용될 때 설명.

### 핵심 클래스 / 함수

| 이름 | 역할 |
|------|------|
| `VehiclePhysics(scene, car, sensor, cfg, n_envs)` | 5-step pipeline 실행 driver  () |
| `VehicleInputs(throttle, brake, steer)` | typed 제어 입력 (자동차용) |
| `SkidSteerInputs`, `NoSteerInputs` | 차종별 입력 클래스 |
| `add_vehicle(scene, URDF, preset)` | URDF entity + raycaster + cfg 생성 helper |
| `parse_urdf(URDF)` | URDF 에서 wheel 정보 추출 |
| `WheelRayPattern(positions)` | -Z 방향 ray 패턴 정의 |
| `VehicleConfig`, `WheelConfig`, `ChassisConfig` | 설정 객체 |

- **`VehiclePhysics`**: 매 step 5단계 (raycast→suspension→slip→tire→omega) 를 batched 로 돌리는 메인 엔진. 옛 `CarRayWheelPhysics` 와 동일 위치.
- **`VehicleInputs`**: `physics.step()` 에 넣을 입력. positional args 대신 keyword 로 명확.
- **`SkidSteerInputs / NoSteerInputs`**: 탱크 (좌/우 throttle 따로) / 트레일러용. 자동차는 `VehicleInputs` 만 사용.
- **`add_vehicle`**: URDF 등록 + Raycaster 부착 + preset cfg 생성을 한 줄로. fine-grained 제어 필요하면 hand-wired (`parse_urdf` + `WheelRayPattern` 직접) 가능.
- **`parse_urdf`**: URDF 파싱해서 wheel position / radius / mass / joint name 추출.
- **`WheelRayPattern`**: 각 wheel 중심에서 -Z 방향 ray 1 개씩 정의하는 Genesis raycaster 패턴.
- **`VehicleConfig / WheelConfig / ChassisConfig`**: 차량 / wheel 별 / chassis 별 파라미터 보관 객체. user override 가 URDF default 보다 우선.

### Strategy 옵션 

| 축 | 옵션 |
|----|------|
| **Steering** | `Ackermann`, `PartialAckermann`, `SkidSteer`, `NoSteer` |
| **Drivetrain** | `FWD`, `RWD`, `AWD`, `PerSide` |
| **Coupling** | `Independent`, `SameSideBelt` |
| **Tire model** | `PacejkaAnisotropic`, `CoulombIsotropic` |

**Steering**
- **`Ackermann`**: 좌우 앞바퀴를 다른 각도로 (안쪽 더 sharp). 일반 승용차 표준. **우리 케이스.**
- **`PartialAckermann`**: 100% Ackermann ↔ parallel steering 사이. 고속 차량 (F1 등) 에서 캠버/타이어 효과 보정.
- **`SkidSteer`**: 앞바퀴 조향 없음. 좌/우 throttle 차이로 회전. 탱크, 굴삭기, 트랙터.
- **`NoSteer`**: 조향 자체 없음. 트레일러, 화물칸.

**Drivetrain**
- **`FWD`** (Front-Wheel Drive): 전륜구동. drive torque 가 앞바퀴에만.
- **`RWD`** (Rear-Wheel Drive): 후륜구동. 뒷바퀴에만. **우리 케이스 (Blender 차량).**
- **`AWD`** (All-Wheel Drive): 4륜구동. 모든 바퀴 분배.
- **`PerSide`**: 좌/우 따로 (탱크처럼 좌우 throttle 입력이 따로일 때).

**Coupling**
- **`Independent`**: 각 wheel 이 독립적으로 회전. 일반 자동차.
- **`SameSideBelt`**: 같은 쪽 wheel 들이 캐터필러 벨트로 묶임 (탱크 트랙처럼 한 쪽 wheel 들이 같이 도는 구조).

**Tire model**
- **`PacejkaAnisotropic`**: Magic formula. 종/횡 방향 각각 비선형 곡선 + friction circle clamping. 자동차 sim 업계 표준.
- **`CoulombIsotropic`**: 단순 μN 마찰. 등방성 (방향 무관). 옛 mesh-contact engine 의 기본 마찰 모델. 빠르지만 부정확.

### Stability Hooks

| Hook | 트리거 |
|------|-------|
| `RollingResistance` | 항상 (tire force 후) |
| `LowSpeedRegularizer` | 저속 (pre-loop + post-tire) |
| `StaticFrictionLock` (v0.5.7) | brake 큼 + 저속 |

- **`RollingResistance`**: 굴림저항 추가. 차가 가속/감속 시 자연 감쇠 효과.   
-> 타이어가 굴러갈 때 변형/복원 과정에서 발생하는 작은 에너지 손실로 차가 자연 감속

- **`LowSpeedRegularizer`**: 저속 진동(Pacejka의 한계) 방지. `moving ∈ [0, 1]` factor 로 저속에서 tire force 끔 + omega 를 rolling-without-slip 쪽으로 끌어당김.   
-> 다시 말해, 저속에서 Pacejka 가 수학적으로 깨지는 걸 막아 차량의 진동을 방지

- **`StaticFrictionLock`  v0.5.7 NEW**: 진짜 정지 (stick-slip). brake 누른 채로 저속이면 wheel 의 contact 위치를 anchor 로 잡고, 그 anchor 에 spring-damper force 적용, friction ellipse 내에서 유지. 경사로에서도 흘러내림 없이 정지함.  
-> 즉, LowSpeedRegularizer에서 Pacejka 끄면 정지마찰 효과까지 같이 사라져 중력에 차가 미끄러지는데, 이것을 spring-damper force 를 추가로 인가 해서 사라진 정지마찰을 대체함.

### Preset (사전 정의 조합)

| Preset | 구성 |
|--------|------|
| `car_4w_fwd_ackermann` | 4 wheel + 전륜구동 + Ackermann |
| `car_4w_rwd_ackermann` | 4 wheel + **후륜구동** + Ackermann (우리 케이스) |
| `car_4w_awd_ackermann` | 4 wheel + 4륜구동 + Ackermann |
| `truck_6w_partial_ackermann` | 6 wheel + RWD + PartialAckermann |
| `tank_10w_skid_belt` | 10 wheel + PerSide + SkidSteer + SameSideBelt |

### Stability Profile (hook 묶음)

| Profile | 활성 hooks |
|---------|-----------|
| `"control"` | RollingResistance + LowSpeedRegularizer (MPPI / RL 친화) |
| `"raw"` | 없음 (순수 physics) |
| `"research"` | + 진단 hook |

### Sign convention (ISO 8855)

- `+X` 앞, `+Y` 왼쪽, `+Z` 위
- `+throttle` 전진가속, `brake [0,1]`, `+steer` 우회전
- Genesis RHS / URDF axis 의 flip 은 SDK 내부에서 자동 처리

---

## 1. MPPI 코드 convert 

### 1.1 옛 코드 구조 분석

전체 896 줄. 5 개의 주요 구성 요소로 나뉨:

```
┌─────────────────────────────────────────────────┐
│  step2_golden_mining_raywheel.py (896 줄)        │
│                                                   │
│  ① Imports + 상수 (54-65)                         │
│       └ car_raywheel 에서 6 개 심볼 import          │
│  ② MPPIParams dataclass (68-91)                   │
│       └ 8 개 hyperparameter (w_*, lambda 등)       │
│  ③ GenesisEnvSlidingMPPIRaywheel (97-406)          │
│       └ Env 셋업 + rollout + state sync/snapshot  │
│  ④ SlidingWindowMPPI (410-608)                    │
│       └ MPPI optimizer (sample → rollout → cost)  │
│  ⑤ run_golden_mining (713-851)                    │
│       └ main loop (frame 별 optimize + step)      │
└─────────────────────────────────────────────────┘
```
--- 

#### ① car_raywheel 에 대한 의존

```python
from car_raywheel import (
    CarRayWheelPhysics, WheelRayPattern,
    WHEEL_POSITIONS, DT, MAX_STEER_RAD,
    T_DRIVE_MAX, T_BRAKE_MAX,
)
```

| 심볼 | 역할 | SDK 대체 |
|------|------|---------|
| `CarRayWheelPhysics` | ray-wheel 물리 엔진 | `VehiclePhysics` |
| `WheelRayPattern` | sensor 패턴 | `WheelRayPattern` (SDK, 동일 이름) |
| `WHEEL_POSITIONS` | 4 wheel 좌표 (chassis local) | URDF 에서 자동 추출 → `parse_urdf` 또는 `add_vehicle` 안에서 처리 |
| `DT` | 시뮬 timestep (1/48 s) | scene 의 `SimOptions(dt=...)` 에서 직접 지정 |
| `MAX_STEER_RAD` | 조향각 한계 | `WheelConfig` 의 steer limit field |
| `T_DRIVE_MAX`, `T_BRAKE_MAX` | drive/brake 토크 한계 | `WheelConfig` 의 torque field |

→ **car_raywheel 의존을 모두 SDK 로 매핑 가능**.

---  

#### ② MPPIParams

순수 hyperparameter dataclass. SDK 와 무관 → **변경 불필요**.  

---

#### ③ GenesisEnvSlidingMPPIRaywheel

**역할**: `n_envs = 1 (real) + 200 (imagination) = 201` batched env 관리.

주요 메서드 (convert 가 의미 있는 것만):

| 메서드 | 역할 | SDK 영향 |
|--------|------|---------|
| `__init__` | scene/plane/car/sensor/physics 생성 | `CarRayWheelPhysics(...)` 호출 → `add_vehicle(...) + VehiclePhysics(...)` 로 교체 |
| `sync_imagination_to_real` | env 0 → env 1~200 state 복사 | Genesis state + ray-wheel internal state 둘 다 복사. SDK attribute 구조 매핑 필요 |
| `save_raywheel_snapshot` | rollout 전 ray-wheel state 저장 | SDK 의 internal state attribute 매핑 |
| `restore_raywheel_snapshot` | rollout 후 ray-wheel state 복원 | snapshot 과 한 쌍 |

---

#### ④ SlidingWindowMPPI (MPPI optimizer 본체)

순수 MPPI 알고리즘. **Genesis 나 SDK 와 무관** — env 객체만 받아서 동작.


→ **알고리즘 자체는 SDK 와 무관**. 단 env 객체의 인터페이스가 바뀌므로 env 호출 부분만 영향 받음.

---

#### ⑤ run_golden_mining (main loop)

```python
for frame_idx in range(num_frames):
    a_t, kappa_t, v_t, head_t, thr_b, steer_b, pos_t = (df 에서 target 추출)
    drive_opt, steer_opt = mppi.optimize(a_t, kappa_t, ...)
    state = env.step_real_only(drive_opt, steer_opt)
    # 결과 저장
```

→ **드라이버 layer**. env / mppi 객체 API 가 바뀌면 호출 부분만 수정.


```-> 아래에 1, 3, 5번에 대한 convert 과정을 명시```

---


### 1.2 SDK 로 convert
---
#### ① Imports

**Before**:
```python
from car_raywheel import (
    CarRayWheelPhysics, WheelRayPattern,
    WHEEL_POSITIONS, MAX_STEER_RAD,
    T_DRIVE_MAX, T_BRAKE_MAX,
)
```

**After**:
```python
# genesis_vehicle SDK
from genesis_vehicle import (
    VehiclePhysics, VehicleInputs,
    add_vehicle, car_4w_rwd_ackermann,
)
```

- `CarRayWheelPhysics` → `VehiclePhysics` 로 교체. 이름만 다를 뿐 같은 역할 (5-step pipeline 실행).
- `WheelRayPattern`, `WHEEL_POSITIONS`, `MAX_STEER_RAD`, `T_DRIVE_MAX`, `T_BRAKE_MAX` → `add_vehicle` + preset (`car_4w_rwd_ackermann`) 조합으로 대체.
- `add_vehicle` 은 URDF entity + raycaster + cfg 생성을 한 줄로 해주는 helper 함수.
- `car_4w_rwd_ackermann` 은 5 가지 preset 중 하나로 `4 wheel + 후륜구동 + Ackermann` — 현재 우리가 실험하는 차량의 구동계 방식.
- `VehicleInputs` 는 새로 추가된 import — `physics.step()` 호출 시 `(throttle, brake, steer)` 를 묶어 전달하는 typed dataclass.
---
#### ③.1 Env class `__init__`

**Before**:
```python
# Car (URDF entity)
self.car = self.scene.add_entity(
    gs.morphs.URDF(file=urdf_path, pos=(0, 0, 1.0)),
    material=gs.materials.Rigid(friction=1.0),
)

# Sensor (raycaster)
self.sensor = self.scene.add_sensor(
    gs.sensors.Raycaster(
        pattern=WheelRayPattern(WHEEL_POSITIONS),
        entity_idx=self.car.idx,
        min_range=0.0, max_range=20.0,
        return_world_frame=True,
    )
)

self.scene.build(n_envs=self.n_envs)
self.solver = self.scene.rigid_solver

# Ray-wheel physics
self.physics = CarRayWheelPhysics(
    self.scene, self.car, self.sensor,
    n_envs=self.n_envs,
    tire_model="pacejka",
    enable_visual_rotation=False,
)
```

**After**:
```python
# SDK helper: URDF + raycaster + cfg 한 번에
self.car, self.sensor, self.cfg = add_vehicle(
    self.scene, urdf_path, car_4w_rwd_ackermann,
    pos=(0, 0, 1.0),
    material=gs.materials.Rigid(friction=1.0),
    raycaster_max_range=20.0,
    stability="control",
)

self.scene.build(n_envs=self.n_envs)
self.solver = self.scene.rigid_solver

# SDK physics
self.physics = VehiclePhysics(
    self.scene, self.car, self.sensor, self.cfg,
    n_envs=self.n_envs,
)
```
- **add_vehicle**은 기존에 따로 호출했던 URDF와 Sensor를 같이 호출하고 해당 차량의 특성(drive, brake 토크, 후륜, Pacejka 방식 물리 계산, hooks 등)들을 cfg로 묶어 관리하여 셋을 같이 쉽게 관리할 수 있게 해줌. 
- **preset(여기서는 car_4w_rwd_ackermann)** 은 원하는 차량의 cfg의 기본값을 제공하여 더욱 더 쉽게 접근 가능.
- **VehiclePhysics**는 앞에서 만든 scene / car / sensor / cfg 를 받아 매 step 마다 5-step pipeline (raycast → suspension → slip → tire → omega) 을 실행하는 driver. 근데 이것을 loop가 아닌 하나의 tensor로 처리하여 속도 측면에서 이점을 가져감.(자세한 정리는 아래)

**1. VehiclePhysics 효과**

옛 `CarRayWheelPhysics.step()` 은 wheel 별로 Python `for i in range(4)` loop를 돌면서 raycast / suspension / tire force 를 따로 계산했음. n_envs=200 인 MPPI imagination rollout 에서는 매 step 마다 wheel 별 kernel launch 가 4 배로 누적되어 GPU launch overhead 가 큼.

SDK는 **per-wheel pipeline 이 vectorize 됨** — Python loop 제거, `(n_envs, n_wheels)` shape ```tensor``` 로 한 번에 처리. Kernel launch 수가 ~250 → ~25 로 1/10 수준. 우리는 단순히 `CarRayWheelPhysics(...)` → `VehiclePhysics(...)` 로 교체했을 뿐인데 학습 속도가 휠씬 빨라질 것으로 예상

```→ 즉, 우리 기존 코드는 wheel 별 계산을 loop 로 돌면서 GPU 작업 요청을 여러 번 했지만, SDK 는 이 계산을 tensor 하나로 묶어 한 번에 처리해서 학습 속도에서 큰 이점을 얻는 것.``` 

---

#### ③.2 State 관리 (sync + save_snapshot + restore_snapshot)

MPPI 의 imagination rollout 을 위해 env 0 (real) 의 state 를 env 1~200 (imagination) 에 복사하고, rollout 후 real env state 를 **snapshot** (저장된 상태 dictionary) 으로 복원해야 함.   
```-> 게임에 비유하면 save / load — "여기서 분기 가능성 시뮬해보고 원위치 복귀" 패턴.```

→ **attribute 이름의 90% 가 그대로 호환** — 옛 코드 거의 그대로 사용되었고, 추가된 SDK attribute 들을 snapshot 에 포함시킴.

| 옛 우리 attribute | SDK 위치 | 변경 |
|-------------------|---------|------|
| `physics.omega`, `prev_compression`, `_prev_init` | 동일 | 그대로 |
| `physics.last_distances/compression/N/F_long/F_lat` | 동일 | 그대로 |
| (없음) | `last_T_drive`, `last_T_brake`, `last_kappa`, `last_alpha` |  SDK 가 추가로 가짐 → snapshot 에 포함 |

- `last_T_drive`, `last_T_brake`: 직전 step 에서 각 wheel 에 적용된 drive / brake 토크
- `last_kappa`, `last_alpha`: 직전 step 의 slip ratio (κ) / slip angle (α).


**1. SDK 가 추가한 attribute 4 개 — 왜 필요?**

기존 옛 코드는 모든 로직 Monolithic step() 안에 다 구현되어 있었음. But,

```-> SDK 는 hook system 도입으로 hook이 이런 중간값을 외부에서 읽기 때문에 instance attribute 로 노출시켰고, 그래서 결정적 rollout 위해 snapshot 에도 포함해야 함.(hook 추가로 인해 고려해야 할 attribute가 늚.)```
 

**2. 효과** — 결정론적 rollout 보장 + Hook 친화적:

- 시뮬 자체 결정성은 `omega` 와 `prev_compression` 만 복원해도 보장됨. 하지만 stability hook (RollingResistance / LowSpeedRegularizer / **StaticFrictionLock**) 이나 cost 함수가 `last_*` 를 참조할 수 있음   
—> 예를 들어 friction ellipse 안 / 밖 판단에 `last_kappa`, `last_alpha` 사용.

- SDK 는 보수적으로 **모든 `last_*` 를 snapshot 에 포함** → 어떤 hook 조합에서도 결정성 유지.  

---

#### ⑤ run_golden_mining (main loop)

옛 코드의 main loop 핵심:

```python
def run_golden_mining(blender_csv, urdf_path, ...):
    df = pd.read_csv(blender_csv)
    df = precompute_targets(df, ...)
    
    env = GenesisEnvSlidingMPPIRaywheel(urdf_path=urdf_path)
    mppi = SlidingWindowMPPI(env, params=MPPIParams(...))
    
    env.reset_to_state(...)
    env.stabilize(50)
    
    for frame_idx in tqdm(range(num_frames)):
        a_t = df['a_req'].iloc[...].values
        kappa_t = df['kappa_req'].iloc[...].values
        ...
        drive_opt, steer_opt, info = mppi.optimize(a_t, kappa_t, ...)
        state = env.step_real_only(drive_opt, steer_opt)
        results.append(...)
```

→ **이 함수 body 는 한 줄도 안 바뀜**. env class 의 `__init__` 내부만 SDK 로 바뀌었을 뿐, 외부에서 호출하는 메서드 시그니처 (`reset_to_state`, `stabilize`, `step_real_only`) 가 모두 동일하기 때문에 수정이 불필요했음.




