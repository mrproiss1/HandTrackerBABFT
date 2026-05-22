import sys
import subprocess
import os
import urllib.request
import math

MODEL_FILENAME = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
REQUIRED_PACKAGES = [
    ('opencv-python', 'cv2'),
    ('mediapipe', 'mediapipe'),
    ('keyboard', 'keyboard'),
]


def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def ensure_pip_available():
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("pip was not found. Trying to enable pip...")
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])


def install_missing_packages():
    missing_packages = []
    for package, import_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package)

    if not missing_packages:
        return

    ensure_pip_available()
    for package in missing_packages:
        print(f"Installing missing package: {package}")
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            package,
        ])


def ensure_hand_model():
    model_path = resource_path(MODEL_FILENAME)
    model_folder = os.path.dirname(model_path)
    if model_folder:
        os.makedirs(model_folder, exist_ok=True)

    model_exists = os.path.exists(model_path) and os.path.getsize(model_path) > 1000000
    if model_exists:
        return

    print("Downloading AI hand model...")
    temp_path = model_path + ".download"
    urllib.request.urlretrieve(MODEL_URL, temp_path)
    os.replace(temp_path, model_path)


# --- AUTO-INSTALLER & MODEL DOWNLOADER ---
def setup_environment():
    if getattr(sys, "frozen", False):
        return

    install_missing_packages()
    ensure_hand_model()


try:
    setup_environment()
except Exception as error:
    print("\nAutomatic setup failed.")
    print("Make sure Python has internet access, then run this again.")
    print(f"Error: {error}")
    input("Press Enter to exit...")
    sys.exit(1)

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import keyboard

# --- CONFIGURATION ---
FINGER_KEYS = ['d', 'f', 'g', 'h', 'j']
finger_names = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
current_key_states = [False] * 5

# Landmarks for tips: Thumb(4), Index(8), Middle(12), Ring(16), Pinky(20)
TIP_IDS = [4, 8, 12, 16, 20]
# Landmarks for joints to compare against
JOINT_IDS = [2, 6, 10, 14, 18] 

# Initialize MediaPipe Tasks
base_options = python.BaseOptions(model_asset_path=resource_path('hand_landmarker.task'))
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=2,
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.7,
    min_tracking_confidence=0.7
)
detector = vision.HandLandmarker.create_from_options(options)


def ask_tracked_hand():
    choices = {
        "": "both",
        "b": "both",
        "both": "both",
        "l": "left",
        "left": "left",
        "r": "right",
        "right": "right",
    }

    while True:
        choice = input("Choose hand to track: left/right/both (Default both): ").strip().lower()
        if choice in choices:
            return choices[choice]
        print("Please enter left, right, or both.")


def get_handedness_name(detection_result, index):
    try:
        return detection_result.handedness[index][0].category_name.lower()
    except (AttributeError, IndexError):
        return ""


def get_selected_hand(detection_result, tracked_hand):
    if not detection_result.hand_landmarks:
        return None, ""

    if tracked_hand == "both":
        return detection_result.hand_landmarks[0], get_handedness_name(detection_result, 0)

    for index, landmarks in enumerate(detection_result.hand_landmarks):
        if get_handedness_name(detection_result, index) == tracked_hand:
            return landmarks, tracked_hand

    return None, ""


def get_distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)


def get_point_distance(point, x, y):
    return math.sqrt((point.x - x)**2 + (point.y - y)**2)


def is_thumb_closed(landmarks, closed_finger_count):
    thumb_cmc = landmarks[1]
    thumb_mcp = landmarks[2]
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    index_base = landmarks[5]
    middle_base = landmarks[9]
    ring_base = landmarks[13]
    pinky_base = landmarks[17]
    wrist = landmarks[0]

    palm_size = max(get_distance(wrist, middle_base), get_distance(index_base, pinky_base), 0.001)
    palm_center_x = (index_base.x + middle_base.x + ring_base.x + pinky_base.x) / 4
    palm_center_y = (index_base.y + middle_base.y + ring_base.y + pinky_base.y) / 4

    tip_to_palm = get_point_distance(thumb_tip, palm_center_x, palm_center_y)
    ip_to_palm = get_point_distance(thumb_ip, palm_center_x, palm_center_y)
    thumb_length = (
        get_distance(thumb_cmc, thumb_mcp) +
        get_distance(thumb_mcp, thumb_ip) +
        get_distance(thumb_ip, thumb_tip)
    )
    thumb_reach = get_distance(thumb_cmc, thumb_tip) / max(thumb_length, 0.001)

    palm_x_values = [index_base.x, middle_base.x, ring_base.x, pinky_base.x]
    palm_y_values = [wrist.y, index_base.y, middle_base.y, ring_base.y, pinky_base.y]
    palm_width = max(palm_x_values) - min(palm_x_values)
    palm_height = max(palm_y_values) - min(palm_y_values)
    thumb_inside_palm_area = (
        min(palm_x_values) - palm_width * 0.2 <= thumb_tip.x <= max(palm_x_values) + palm_width * 0.2 and
        min(palm_y_values) - palm_height * 0.35 <= thumb_tip.y <= max(palm_y_values) + palm_height * 0.35
    )

    near_index_base = get_distance(thumb_tip, index_base) < palm_size * 0.62
    near_middle_base = get_distance(thumb_tip, middle_base) < palm_size * 0.70
    near_ring_base = get_distance(thumb_tip, ring_base) < palm_size * 0.78
    near_pinky_base = get_distance(thumb_tip, pinky_base) < palm_size * 0.70
    is_near_palm_bases = near_index_base or near_middle_base or near_ring_base or near_pinky_base

    open_score = 0
    if tip_to_palm > palm_size * 1.02:
        open_score += 1
    if tip_to_palm > ip_to_palm + palm_size * 0.12:
        open_score += 1
    if thumb_reach > 0.76:
        open_score += 1
    if (
        get_distance(thumb_tip, index_base) > palm_size * 0.86 and
        get_distance(thumb_tip, middle_base) > palm_size * 0.92
    ):
        open_score += 1
    if not thumb_inside_palm_area and not is_near_palm_bases:
        open_score += 1

    closed_score = 0
    if near_pinky_base:
        closed_score += 2
    if is_near_palm_bases:
        closed_score += 1
    if tip_to_palm < palm_size * 0.72:
        closed_score += 1
    if tip_to_palm <= ip_to_palm + palm_size * 0.04:
        closed_score += 1
    if thumb_inside_palm_area and closed_finger_count >= 2:
        closed_score += 1
    if abs(thumb_tip.x - middle_base.x) < palm_size * 0.18 and tip_to_palm < palm_size * 0.82:
        closed_score += 1
    if closed_finger_count >= 3 and (thumb_inside_palm_area or is_near_palm_bases):
        closed_score += 1

    if open_score >= 3 and closed_score < 4:
        return False

    return closed_score >= 3


def main():
    print("=== Virtual Hand Tracker (FULL VISUAL DEBUG) ===")
    cam_index = input("Enter camera index (Default 0): ")
    cam_index = int(cam_index) if cam_index.isdigit() else 0
    tracked_hand = ask_tracked_hand()

    if tracked_hand == "both":
        print("Tracking: any detected hand")
    else:
        print(f"Tracking: {tracked_hand.capitalize()} hand only")

    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    while cap.isOpened():
        success, frame = cap.read()
        if not success: break

        h, w, _ = frame.shape
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        
        detection_result = detector.detect(mp_image)
        fingers_active = [0] * 5
        landmarks, detected_hand = get_selected_hand(detection_result, tracked_hand)

        if landmarks:
            # --- OTHER FINGERS LOGIC ---
            for i in range(1, 5):
                tip = landmarks[TIP_IDS[i]]
                joint = landmarks[JOINT_IDS[i]]
                if tip.y > joint.y: # Finger is curled down
                    fingers_active[i] = 1

            # --- THUMB LOGIC ---
            if is_thumb_closed(landmarks, sum(fingers_active[1:])):
                fingers_active[0] = 1

            # --- KEYPRESS & VISUAL FEEDBACK ---
            for i in range(5):
                # Update Keys
                if fingers_active[i] and not current_key_states[i]:
                    keyboard.press(FINGER_KEYS[i])
                    current_key_states[i] = True
                elif not fingers_active[i] and current_key_states[i]:
                    keyboard.release(FINGER_KEYS[i])
                    current_key_states[i] = False

                # Draw Visual Dots on Tips
                tip_coords = (int(landmarks[TIP_IDS[i]].x * w), int(landmarks[TIP_IDS[i]].y * h))
                color = (0, 0, 255) if fingers_active[i] else (0, 255, 0) # Red if Pressed, Green if Up
                cv2.circle(frame, tip_coords, 10, color, -1)
                cv2.putText(frame, FINGER_KEYS[i].upper(), (tip_coords[0]-5, tip_coords[1]+5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            # Header Status
            cv2.putText(frame, "RED = PRESSED | GREEN = OPEN", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            if detected_hand:
                cv2.putText(frame, f"TRACKING: {detected_hand.upper()} HAND", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
        else:
            # Clear all if hand is gone
            for i in range(5):
                if current_key_states[i]:
                    keyboard.release(FINGER_KEYS[i])
                    current_key_states[i] = False

        cv2.imshow('Hand Tracker Debug', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
