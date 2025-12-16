# 드론 urdf 정리

### 🔹 base_link
```xml
<link name="base_link"> 
  <inertial> # 관성 모멘트(inertia tensor) = 물체가 회전하려고 할 때 저항하는 성질.
    
    <origin rpy="0 0 0" xyz="0 0 0"/> # 이 물체의 질량 중심(Center of Mass, CoM) 위치와 방향을 정의.  
    -> 드론 전체의 “몸통”으로 모든 좌표 계산의 기준

    <mass value="0.027"/>  * 해당 링크의 무게(kg 단위).

    <inertia ixx="1.4e-5" ixy="0.0" ixz="0.0"   
             iyy="1.4e-5" iyz="0.0" izz="2.17e-5"/> # ixx, iyy, izz → 각 축(X, Y, Z)에 대한 회전 관성 ,
                                              ixy, ixz, iyz → 축 사이의 관성 결합(드론 구조가 대칭이라 0) 
  
  </inertial>

  <visual>
    <origin rpy="0 0 0" xyz="0 0 0"/>
    <geometry>
      <mesh filename="./body.obj" scale="1 1 1"/> # mesh 는 링크(부품)의 3D 형상을 불러오는 곳
    </geometry> 
    <material name="grey">
      <color rgba=".5 .5 .5 1"/> # rgb + a(alpha) = 투명도, a가 0 이면 투명, 1이면 불투명
    </material> 
  </visual>

  <collision>
    <origin rpy="0 0 0" xyz="0 0 0"/>
    <geometry>
      <cylinder radius=".06" length=".025"/>
    </geometry>
  </collision>  
</link>
```

- 드론의 **본체(Body Frame)** 를 나타내는 기본 링크  

- 실제 **질량(0.027kg)**, **관성행렬(Ixx=Iyy=1.4e-5, Izz=2.17e-5)** 포함 → 시뮬레이션 시 물리적 계산 기준  
- **Visual**: `body.obj` mesh 사용 -> URDF의 기본 도형(box, cylinder, sphere)만으로는 복잡한 모양을 표현하기 힘듦

- **Collision**: 단순 원기둥 (반지름 0.06m, 길이 0.025m)인 기본 도형으로 충돌 모델 정의  
-> 실제 드론 본체는 복잡한 모양이지만, 충돌 계산에 그대로 쓰면 시뮬레이션이 무거워짐. 

- 본체의 질량/관성/시각화/충돌을 담당하는 **핵심 링크**  
- 좌표계 원점은 임의로 정해질 수 있으며, 꼭 질량 중심과 일치할 필요는 없음  

---

### 🔹 propeller links (prop0~3)
```xml
<link name="prop0_link">
  <inertial>
    <origin rpy="0 0 0" xyz="0.028 -0.028 0"/>
    <mass value="0"/>
    <inertia ixx="0" ixy="0" ixz="0" 
             iyy="0" iyz="0" izz="0"/>
  </inertial>
  <visual>
    <origin rpy="0 0 0" xyz="0.0323 -0.0323 0.0132"/>
    <geometry>
      <mesh filename="./propeller0.obj"/>
    </geometry> 
  </visual>
</link>
<joint name="prop0_joint" type="fixed">
  <parent link="base_link"/>
  <child link="prop0_link"/>
</joint>
```

- 모든 프로펠러 링크는 `prop0_link ~ prop3_link` 형태로 정의  

- `mass=0` → 실제 질량은 base_link에 포함됨

- `inertial=0` -> 프로펠러 자체의 회전 관성은 무시 (추력/토크로만 효과 반영)

- `fixed joint`로 base_link에 부착 → 본체와 함께 움직임

- 네 개 모두 **대각선 위치**에 배치되어 **X자 구조 쿼드콥터 레이아웃**을 형성  


---

### 🔹 center_of_mass_link
```xml
<link name="center_of_mass_link">
  <inertial>
    <origin rpy="0 0 0" xyz="0 0 0"/>
    <mass value="0"/>
    <inertia ixx="0" ixy="0" ixz="0" 
             iyy="0" iyz="0" izz="0"/>
  </inertial>
</link>
<joint name="center_of_mass_joint" type="fixed">
  <parent link="base_link"/>
  <child link="center_of_mass_link"/>
</joint>
```

- **질량 중심(CoM)** 을 나타내는 가상의 링크  
- `mass=0`, `inertia=0` → 물리적으로는 영향 없음  
- base_link와 `fixed joint`로 연결 → 항상 같은 위치  
- 오직 **질량 중심 좌표계 참조용**으로 사용  
- 제어/센서 계산에서 “무게 중심 기준 좌표계”가 필요할 때 활용  
- "이 좌표계는 CoM이다"라고 명시적으로 표현하기 위한 목적  


