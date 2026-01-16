import bpy
import csv
import math
from mathutils import Vector, Quaternion, Matrix

# =====================
# CONFIG
# =====================

CAR_OBJECT_NAME   = "Corvette.Vehicle Body.RB"
FRONT_LEFT_WHEEL  = "Corvette.Vehicle Body.0.FL1_Wheel.RB"
FRONT_RIGHT_WHEEL = "Corvette.Vehicle Body.0.FR0_Wheel.RB"
REAR_LEFT_WHEEL   = "Corvette.Vehicle Body.1.BL1_Wheel.RB"
REAR_RIGHT_WHEEL  = "Corvette.Vehicle Body.1.BR0_Wheel.RB"

BLENDER_FORWARD_LOCAL = Vector((0.0, -1.0, 0.0))
WHEEL_SPIN_AXIS_LOCAL = Vector((1.0, 0.0, 0.0))

OUTPUT_CSV_PATH = r"\\wsl.localhost\Ubuntu-22.04\home\jaewon\projects\genesis\sensor_log.csv"

# Throttle 계산 설정
ALPHA = 0.7  # 가속도 가중치
BETA = 0.3   # spin 가중치
PERCENTILE = 95  # Local Max 계산용

ROT_B2G = Matrix.Rotation(math.radians(90.0), 3, 'Z')


def vec_B_to_G(v: Vector) -> Vector:
    return ROT_B2G @ v


def mat3_B_to_G(R: Matrix) -> Matrix:
    return ROT_B2G @ R


def quat_B_to_G(q: Quaternion) -> Quaternion:
    R_b = q.to_matrix()
    R_g = mat3_B_to_G(R_b)
    return R_g.to_quaternion().normalized()


def get_obj(name):
    return bpy.data.objects.get(name, None)


# ============================================
# CORRECT: Wheel Spin Tracker with vehicle direction
# ============================================

class WheelSpinTracker:
    def __init__(self):
        self.prev_rot = {}

    def get_spin_rate(self, wheel_obj, car_obj, vehicle_velocity, dt: float) -> float:
        """
        바퀴 회전 속도 계산 (부호 포함)
        
        Args:
            wheel_obj: 바퀴 오브젝트
            car_obj: 차량 오브젝트
            vehicle_velocity: 차량 속도 벡터
            dt: 시간 간격
            
        Returns:
            양수: 전진 방향 회전
            음수: 후진 방향 회전 (브레이크 포함)
        """
        if wheel_obj is None or dt <= 0.0:
            return 0.0

        name = wheel_obj.name
        curr_rot = wheel_obj.matrix_world.to_quaternion().normalized()

        R_w = wheel_obj.matrix_world.to_3x3()
        spin_axis_world = (R_w @ WHEEL_SPIN_AXIS_LOCAL).normalized()

        if name not in self.prev_rot:
            self.prev_rot[name] = curr_rot
            return 0.0

        prev_rot = self.prev_rot[name]

        # Quaternion 부호 일관성 보장
        if prev_rot.dot(curr_rot) < 0:
            curr_rot = Quaternion((-curr_rot.w, -curr_rot.x, -curr_rot.y, -curr_rot.z))

        delta = prev_rot.conjugated() @ curr_rot
        angle = delta.angle

        if angle < 1e-6:
            spin_rate = 0.0
        else:
            axis = delta.axis
            
            # 기본 회전 속도 (부호 있음)
            raw_spin = axis.dot(spin_axis_world) * angle / dt
            
            # 차량 전진 방향 계산
            R_car = car_obj.matrix_world.to_3x3()
            car_forward = R_car @ BLENDER_FORWARD_LOCAL
            
            # 차량 속도가 충분히 크면 속도 방향으로 판단
            speed = vehicle_velocity.length
            if speed > 0.01:  # 0.01 m/s 이상이면
                # 속도 벡터와 차량 전진 방향의 내적
                # 양수 = 전진, 음수 = 후진
                velocity_dir = vehicle_velocity.normalized()
                is_forward = car_forward.dot(velocity_dir) > 0
                
                # 전진이면 회전 방향 유지, 후진이면 반대
                spin_rate = abs(raw_spin) if is_forward else -abs(raw_spin)
            else:
                # 정지 상태면 절댓값만 사용 (방향 판단 어려움)
                spin_rate = abs(raw_spin)

        self.prev_rot[name] = curr_rot
        return spin_rate

    def reset(self):
        self.prev_rot.clear()


# ============================================
# Steering
# ============================================

def signed_yaw(a: Vector, b: Vector) -> float:
    a = Vector((a.x, a.y, 0))
    b = Vector((b.x, b.y, 0))
    if a.length < 1e-6 or b.length < 1e-6:
        return 0.0
    a.normalize()
    b.normalize()
    angle = math.acos(max(-1.0, min(1.0, a.dot(b))))
    return angle if a.cross(b).z >= 0 else -angle


def wheel_steer_angle(body_fwd, wheel_obj):
    if wheel_obj is None:
        return 0.0
    R = wheel_obj.matrix_world.to_3x3()
    wheel_fwd = R @ BLENDER_FORWARD_LOCAL
    ang = signed_yaw(body_fwd, wheel_fwd)
    if ang > math.pi / 2:
        ang -= math.pi
    elif ang < -math.pi / 2:
        ang += math.pi
    return ang


# ============================================
# Throttle 계산용 유틸리티
# ============================================

def percentile(data, p):
    """Percentile 계산 (numpy 없이)"""
    if len(data) == 0:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


def compute_throttle_from_data(collected_data):
    """
    수집된 데이터로부터 throttle 계산
    
    Returns:
        list of throttle values
    """
    if len(collected_data) < 2:
        return [0.0] * len(collected_data)
    
    # 속도 및 가속도 계산
    speeds = []
    accelerations = [0.0]  # 첫 프레임은 가속도 0
    
    for i, data in enumerate(collected_data):
        v = data['velocity']
        speed = math.sqrt(v.x**2 + v.y**2 + v.z**2)
        speeds.append(speed)
        
        if i > 0:
            dt = data['time'] - collected_data[i-1]['time']
            if dt > 0:
                accel = (speeds[i] - speeds[i-1]) / dt
                accelerations.append(accel)
            else:
                accelerations.append(0.0)
    
    # Local Max 계산 (95 percentile)
    accel_abs = [abs(a) for a in accelerations[1:]]  # 첫 프레임 제외
    spin_abs = [abs(d['spin_rear']) for d in collected_data]
    
    accel_max = percentile(accel_abs, PERCENTILE) if accel_abs else 1.0
    spin_max = percentile(spin_abs, PERCENTILE) if spin_abs else 1.0
    
    # 0으로 나누기 방지
    if accel_max < 1e-6:
        accel_max = 1.0
    if spin_max < 1e-6:
        spin_max = 1.0
    
    print(f"  Local Max - accel: {accel_max:.2f} m/s², spin: {spin_max:.2f} rad/s")
    
    # Throttle 계산
    throttles = []
    for i, data in enumerate(collected_data):
        accel_norm = accelerations[i] / accel_max
        spin_norm = data['spin_rear'] / spin_max
        
        throttle = ALPHA * accel_norm + BETA * spin_norm
        throttle = max(-1.0, min(1.0, throttle))  # clip to [-1, 1]
        throttles.append(throttle)
    
    return throttles


# ============================================
# CSV
# ============================================

def init_csv(path):
    with open(bpy.path.abspath(path), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "frame", "time",
            "g_pos_x", "g_pos_y", "g_pos_z",
            "g_qw", "g_qx", "g_qy", "g_qz",
            "g_lin_vx", "g_lin_vy", "g_lin_vz",
            "g_ang_vx", "g_ang_vy", "g_ang_vz",
            "steer",
            "spin_rear",
            "throttle"  # 추가!
        ])


def append_row(path, row):
    with open(bpy.path.abspath(path), "a", newline="") as f:
        csv.writer(f).writerow(row)


# ============================================
# Data collection (2-pass: collect then calculate throttle)
# ============================================

_collected_data = []  # 수집된 데이터 저장
_collected_frames = set()
_prev_frame_data = None
_wheel_tracker = WheelSpinTracker()


def car_logger_handler(scene):
    """핸들러: 각 프레임마다 데이터 수집"""
    global _collected_data, _collected_frames, _prev_frame_data, _wheel_tracker
    
    car = get_obj(CAR_OBJECT_NAME)
    if car is None:
        return
    
    frame = scene.frame_current
    
    # 이미 수집한 프레임이면 무시
    if frame in _collected_frames:
        return
    
    _collected_frames.add(frame)
    
    fps = scene.render.fps
    time_sec = frame / fps
    
    # dt 계산 및 속도 계산
    if _prev_frame_data is None:
        dt = 1.0 / fps
        prev_loc = car.matrix_world.translation.copy()
        prev_rot = car.matrix_world.to_quaternion().normalized()
        v_B = Vector((0, 0, 0))
        w_B = Vector((0, 0, 0))
    else:
        dt = (frame - _prev_frame_data['frame']) / fps
        prev_loc = _prev_frame_data['loc']
        prev_rot = _prev_frame_data['rot']
        
        curr_loc = car.matrix_world.translation
        curr_rot = car.matrix_world.to_quaternion().normalized()
        
        # 선속도
        v_B = (curr_loc - prev_loc) / dt
        
        # 각속도
        if prev_rot.dot(curr_rot) < 0:
            curr_rot = Quaternion((-curr_rot.w, -curr_rot.x, -curr_rot.y, -curr_rot.z))
        
        delta = prev_rot.conjugated() @ curr_rot
        angle = delta.angle
        
        if angle < 1e-6:
            w_B = Vector((0, 0, 0))
        else:
            w_B = Vector(delta.axis) * (angle / dt)
    
    # 현재 데이터 저장
    loc = car.matrix_world.translation.copy()
    rot = car.matrix_world.to_quaternion().normalized()
    
    _prev_frame_data = {
        'frame': frame,
        'loc': loc,
        'rot': rot
    }
    
    # 좌표계 변환
    pos_G = vec_B_to_G(loc)
    rot_G = quat_B_to_G(rot)
    lin_v_G = vec_B_to_G(v_B)
    ang_v_G = vec_B_to_G(w_B)
    
    # 조향각
    R_body = car.matrix_world.to_3x3()
    body_fwd = R_body @ BLENDER_FORWARD_LOCAL
    
    wheel_FL = get_obj(FRONT_LEFT_WHEEL)
    wheel_FR = get_obj(FRONT_RIGHT_WHEEL)
    
    steer_L = wheel_steer_angle(body_fwd, wheel_FL)
    steer_R = wheel_steer_angle(body_fwd, wheel_FR)
    steer = 0.5 * (steer_L + steer_R)
    
    # 휠 스핀 (차량 속도 방향 고려)
    wheel_RL = get_obj(REAR_LEFT_WHEEL)
    wheel_RR = get_obj(REAR_RIGHT_WHEEL)
    
    spin_RL = _wheel_tracker.get_spin_rate(wheel_RL, car, v_B, dt)
    spin_RR = _wheel_tracker.get_spin_rate(wheel_RR, car, v_B, dt)
    spin_rear = 0.5 * (spin_RL + spin_RR)
    
    # 데이터 저장 (throttle은 나중에 계산)
    data = {
        'frame': frame,
        'time': time_sec,
        'position': pos_G,
        'rotation': rot_G,
        'velocity': lin_v_G,
        'angular_velocity': ang_v_G,
        'steer': steer,
        'spin_rear': spin_rear
    }
    
    _collected_data.append(data)


def register_handler():
    """핸들러 등록"""
    global _collected_data, _collected_frames, _prev_frame_data, _wheel_tracker
    
    _collected_data = []
    _collected_frames = set()
    _prev_frame_data = None
    _wheel_tracker.reset()
    
    handlers = bpy.app.handlers.frame_change_post
    handlers[:] = [h for h in handlers if h.__name__ != "car_logger_handler"]
    handlers.append(car_logger_handler)


def unregister_handler():
    """핸들러 제거"""
    handlers = bpy.app.handlers.frame_change_post
    handlers[:] = [h for h in handlers if h.__name__ != "car_logger_handler"]


def export_all_frames(start=1, end=250):
    """프레임 범위를 순회하며 데이터 수집"""
    
    car = get_obj(CAR_OBJECT_NAME)
    if car is None:
        print(f"ERROR: Car object '{CAR_OBJECT_NAME}' not found!")
        return
    
    scene = bpy.context.scene
    
    register_handler()
    
    original_frame = scene.frame_current
    
    print(f"[Step 1/2] Collecting data from frames {start} to {end}...")
    
    try:
        # Pass 1: 데이터 수집
        for frame in range(start, end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            
            if frame % 50 == 0:
                print(f"  Frame {frame}/{end} collected")
        
        print(f"  Collected {len(_collected_data)} frames")
        
        # Pass 2: Throttle 계산
        print(f"\n[Step 2/2] Computing throttle values...")
        throttles = compute_throttle_from_data(_collected_data)
        
        # CSV 저장
        print(f"\n[Step 3/3] Writing to CSV...")
        init_csv(OUTPUT_CSV_PATH)
        
        for i, data in enumerate(_collected_data):
            row = [
                data['frame'], data['time'],
                data['position'].x, data['position'].y, data['position'].z,
                data['rotation'].w, data['rotation'].x, data['rotation'].y, data['rotation'].z,
                data['velocity'].x, data['velocity'].y, data['velocity'].z,
                data['angular_velocity'].x, data['angular_velocity'].y, data['angular_velocity'].z,
                data['steer'],
                data['spin_rear'],
                throttles[i]  # 계산된 throttle 추가
            ]
            append_row(OUTPUT_CSV_PATH, row)
        
        print(f"\n✅ Export complete!")
        print(f"   - Frames: {len(_collected_data)}")
        print(f"   - File: {OUTPUT_CSV_PATH}")
        print(f"   - Throttle range: {min(throttles):.3f} ~ {max(throttles):.3f}")
        print(f"   - Throttle mean: {sum(throttles)/len(throttles):.3f}")
        
    finally:
        unregister_handler()
        scene.frame_set(original_frame)


if __name__ == "__main__":
    export_all_frames(1, 250)