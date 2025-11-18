# URDF 차량 Collision 설정 문제 해결 과정

## 문제 상황
- 차체 collision을 mesh로 설정했을 때 앞바퀴가 제대로 굴러가지 않음
- 뒷바퀴는 정상 작동

## 원인 분석

### 1. Mesh Collision의 문제점
차체를 mesh collision으로 설정하면:
- **복잡한 형상**: Mesh는 수많은 삼각형 면으로 이루어진 복잡한 기하학적 구조
- **충돌 감지 부하**: 물리 엔진이 매 프레임마다 복잡한 mesh와 바퀴 간의 충돌을 계산
- **예상치 못한 충돌**: Mesh의 미세한 돌출부나 내부 구조가 바퀴와 간섭
- **성능 저하**: 연산량이 많아져 시뮬레이션이 불안정해짐

### 2. 앞바퀴가 특히 문제였던 이유
앞바퀴는 **조향(steering) 구조**를 가지고 있어:
- `front_left_steer_joint` (revolute) + `front_left_wheel_joint` (continuous)
- 2단계 조인트 구조로 더 복잡
- Mesh와의 충돌 계산 시 더 많은 자유도로 인해 간섭 가능성 증가

뒷바퀴는:
- `rear_left_wheel_joint` (continuous) 단일 조인트
- 단순 회전만 하므로 mesh와의 간섭이 상대적으로 적음

## 해결 방법

### 1차 시도: Visual과 Collision RPY 혼동
```xml
<!-- 잘못된 이해 -->
<visual>
  <origin xyz="0 0 0" rpy="0 1.5708 0"/>  <!-- Y축 90도 -->
</visual>
<collision>
  <origin xyz="0 0 0" rpy="0 1.5708 0"/>  <!-- Y축 90도 -->
</collision>
```

**문제점:**
- Visual mesh가 이미 올바른 방향(바퀴가 세워진 형태)으로 모델링되어 있었음
- `rpy="0 1.5708 0"`은 필요 없었음
- 바퀴는 원통형이라 Y축 90도 회전해도 시각적으로 차이 없어 보임

### 2차 시도: Collision RPY 수정
```xml
<!-- 올바른 설정 -->
<visual>
  <origin xyz="0 0 0" rpy="0 0 0"/>
</visual>
<collision>
  <origin xyz="0 0 0" rpy="1.5708 0 0"/>  <!-- X축 90도 -->
  <geometry><cylinder radius="0.358" length="0.279"/></geometry>
</collision>
```

**Cylinder의 기본 방향:**
- URDF에서 cylinder는 기본적으로 **Z축을 따라 세워진 상태**(눕혀져 있는 상태)
- 바퀴로 사용하려면 **X축으로 90도 회전**하여 Y축 방향으로 세워야 함

**앞바퀴 vs 뒷바퀴 RPY 불일치:**
- 앞바퀴: `rpy="0 1.5708 0"` (Y축 90도) - 잘못됨
- 뒷바퀴: `rpy="1.5708 0 0"` (X축 90도) - 올바름

→ 모든 바퀴를 `rpy="1.5708 0 0"`으로 통일

### 최종 해결: 차체 Collision을 Box로 변경

#### 바퀴 위치 및 크기 분석
```
바퀴 위치:
- 앞바퀴: x=1.1, y=±0.83, z=0.36
- 뒷바퀴: x=-1.0, y=±0.83, z=0.36

바퀴 크기:
- 반지름: 0.358m
- 폭: 0.279m

바퀴 범위:
- X축: -1.0 ~ 1.1 (휠베이스 2.1m)
- Y축: ±(0.83 + 0.14) = ±0.97m
- Z축: 하단 0.002m, 상단 0.718m
```

#### 차체 Box Collision 계산
```xml
<collision>
  <origin xyz="0.05 0 1.05" rpy="0 0 0"/>
  <geometry><box size="2.6 1.5 0.6"/></geometry>
</collision>
```

**설정 근거:**
- **origin x=0.05**: 앞뒤 바퀴 중심 (1.1 + (-1.0))/2
- **origin z=1.05**: 박스 하단 = 1.05 - 0.3 = 0.75m (바퀴 상단 0.718m보다 위)
- **size x=2.6**: 휠베이스 2.1m + 여유
- **size y=1.5**: 바퀴 간격 1.66m보다 작게 (바퀴와 겹치지 않도록)
- **size z=0.6**: 차체 높이

## 최종 URDF 설정

### 차체 (Base Link)
```xml
<link name="base_link">
  <visual>
    <origin xyz="0 0 0" rpy="0 0 0"/>
    <geometry><mesh filename="car_body.obj" scale="1 1 1"/></geometry>
  </visual>
  
  <collision>
    <origin xyz="0.05 0 1.05" rpy="0 0 0"/>
    <geometry><box size="2.6 1.5 0.6"/></geometry>
  </collision>
</link>
```

### 바퀴 (모든 바퀴 동일)
```xml
<link name="front_left_wheel">
  <visual>
    <origin xyz="0 0 0" rpy="0 0 0"/>
    <geometry><mesh filename="wheel_fl.obj" scale="1 1 1"/></geometry>
  </visual>
  
  <collision>
    <origin xyz="0 0 0" rpy="1.5708 0 0"/>
    <geometry><cylinder radius="0.358" length="0.279"/></geometry>
  </collision>
</link>
```

### Joint Axis
```xml
<joint name="front_left_wheel_joint" type="continuous">
  <axis xyz="0 1 0"/>  <!-- Y축 회전: 바퀴가 앞으로 굴러감 -->
</joint>
```

## 핵심 교훈

### 1. Visual RPY vs Collision RPY vs Joint Axis의 역할
- **Visual RPY**: 3D 모델 파일의 방향 조정 (모델링 좌표계 → URDF 좌표계)
- **Collision RPY**: 충돌 형상의 방향 조정 (기본 형상 → 원하는 방향)
- **Joint Axis**: 조인트의 회전축 정의 (물리적 운동 방향)

### 2. Mesh vs Primitive Collision
- **Mesh**: 시각적으로 정확하지만 연산 부하가 크고 예상치 못한 간섭 발생 가능
- **Primitive (Box, Cylinder, Sphere)**: 단순하지만 빠르고 안정적인 물리 시뮬레이션

### 3. Cylinder의 기본 방향
- URDF cylinder는 기본적으로 Z축 방향 (세워진 상태)
- 바퀴로 사용 시 반드시 `rpy="1.5708 0 0"` (X축 90도 회전) 필요

### 4. 대칭 형상의 함정
- 바퀴는 원통형이라 일부 회전은 시각적으로 차이가 없음
- `rpy="0 1.5708 0"` (Y축 90도)와 `rpy="0 0 0"`이 똑같아 보일 수 있음
- 하지만 물리 엔진은 정확한 방향을 요구함

## 결과
- 모든 바퀴가 정상적으로 굴러감
- 물리 시뮬레이션이 안정적으로 작동
- 차체와 바퀴 간 충돌 간섭 제거

## 데모 영상

https://github.com/user-attachments/assets/3c421729-767d-43b1-9095-4ddff0b613bb

*차체 collision을 mesh에서 box로 변경 후 정상 작동하는 모습*
g