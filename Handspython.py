import sys
import subprocess
import os
import math
import struct
import urllib.request

MODEL_FILENAME = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MIN_MODEL_SIZE_BYTES = 1000000
RECOMMENDED_PYTHON = "Python 3.10 - 3.12 (64-bit)"


class SetupError(RuntimeError):
    pass


def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def check_python_architecture():
    """Verify that Python is 64-bit. MediaPipe does not support 32-bit Windows."""
    if struct.calcsize("P") * 8 == 32:
        if os.name == "nt":
            try:
                probe = subprocess.run(
                    ["py", "-3-64", "-c", "import struct, sys; sys.exit(0 if struct.calcsize('P')*8 == 64 else 1)"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if probe.returncode == 0:
                    print("Notice: Current interpreter is 32-bit. Relaunching with 64-bit Python...")
                    target_script = os.path.abspath(__file__)
                    sys.exit(subprocess.call(["py", "-3-64", target_script] + sys.argv[1:]))
            except Exception:
                pass

        raise SetupError(
            f"You are running 32-bit Python ({sys.version.split()[0]} 32-bit).\n"
            "MediaPipe does NOT support 32-bit Python on Windows.\n"
            "Fix:\n"
            "- Easiest: download and run HandTracker.exe from GitHub Releases (no Python required).\n"
            "- Or install 64-bit Python from https://www.python.org/downloads/ (select 'Windows installer (64-bit)')."
        )


def ensure_pip_available():
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("pip was not found. Trying to enable pip...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as error:
            raise SetupError(
                "Could not enable pip for this Python install. "
                f"Use HandTracker.exe, or install {RECOMMENDED_PYTHON} with pip enabled."
            ) from error

    # Upgrade pip and packaging tools quietly so modern wheel tags resolve cleanly
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


def run_pip_install(package_name):
    """Attempt pip install, falling back to --user and PEP 668 flags if needed."""
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--prefer-binary",
        "--disable-pip-version-check",
        package_name,
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        return True

    # Retry with --user (common permission failure on Windows Program Files without admin privileges)
    cmd_user = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--prefer-binary",
        "--disable-pip-version-check",
        "--user",
        package_name,
    ]
    res_user = subprocess.run(cmd_user)
    if res_user.returncode == 0:
        return True

    # Retry with --break-system-packages (for modern Linux / macOS Homebrew PEP 668 environments)
    if sys.platform != "win32":
        cmd_pep = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--prefer-binary",
            "--disable-pip-version-check",
            "--break-system-packages",
            package_name,
        ]
        res_pep = subprocess.run(cmd_pep)
        if res_pep.returncode == 0:
            return True

    return False


def install_missing_packages():
    check_python_architecture()

    # Step 1: Check and install mediapipe first (it brings opencv-contrib-python)
    need_mediapipe = False
    try:
        __import__("mediapipe")
    except ImportError:
        need_mediapipe = True

    if need_mediapipe:
        ensure_pip_available()
        print("Installing missing package: mediapipe")
        success = False
        for candidate in ["mediapipe", "mediapipe>=0.10.0", "mediapipe<=0.10.35"]:
            if run_pip_install(candidate):
                success = True
                break
        if not success:
            raise SetupError(
                "Could not install mediapipe.\n"
                "Possible reasons on Windows/macOS/Linux:\n"
                "- 32-bit Python is running instead of 64-bit Python.\n"
                "- Missing Microsoft Visual C++ 2015-2022 Redistributable (x64) on Windows.\n"
                "- Pip cannot reach PyPI or wheels are missing for your exact Python version.\n\n"
                "Fix:\n"
                "- Download and run HandTracker standalone from GitHub Releases.\n"
                "- Or install 64-bit Python (3.10, 3.11, or 3.12) with pip enabled."
            )

    # Step 2: Check opencv (cv2) - mediapipe usually supplies opencv-contrib-python
    need_cv2 = False
    try:
        __import__("cv2")
    except ImportError:
        need_cv2 = True

    if need_cv2:
        ensure_pip_available()
        print("Installing missing package: opencv-python")
        if not run_pip_install("opencv-python"):
            raise SetupError(
                "Could not install opencv-python. "
                f"Use HandTracker executable, or install {RECOMMENDED_PYTHON} with pip enabled."
            )

    # Step 3: Check keyboard input simulator (pynput on macOS/Linux, keyboard or pynput on Windows)
    need_input_lib = False
    if sys.platform == "win32":
        try:
            __import__("keyboard")
        except ImportError:
            try:
                __import__("pynput")
            except ImportError:
                need_input_lib = True
    else:
        try:
            __import__("pynput")
        except ImportError:
            need_input_lib = True

    if need_input_lib:
        ensure_pip_available()
        target_pkg = "pynput" if sys.platform != "win32" else "keyboard"
        print(f"Installing missing package: {target_pkg}")
        if not run_pip_install(target_pkg):
            alt_pkg = "pynput" if target_pkg == "keyboard" else "keyboard"
            if not run_pip_install(alt_pkg):
                raise SetupError(
                    f"Could not install keyboard simulation library ({target_pkg} or {alt_pkg}).\n"
                    f"Please install {RECOMMENDED_PYTHON} and run: pip install pynput"
                )


def ensure_hand_model():
    model_path = resource_path(MODEL_FILENAME)
    if os.path.exists(model_path) and os.path.getsize(model_path) > MIN_MODEL_SIZE_BYTES:
        return

    print("AI hand model not found or incomplete. Downloading hand_landmarker.task...")
    try:
        temp_path = model_path + ".download"
        urllib.request.urlretrieve(MODEL_URL, temp_path)
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > MIN_MODEL_SIZE_BYTES:
            os.replace(temp_path, model_path)
            print("AI hand model downloaded successfully.")
            return
    except Exception as e:
        print(f"Warning: Failed to auto-download model: {e}")

    if not (os.path.exists(model_path) and os.path.getsize(model_path) > MIN_MODEL_SIZE_BYTES):
        raise SetupError(
            f"{MODEL_FILENAME} is missing. Put {MODEL_FILENAME} in the same folder as Handspython.py, "
            "then run the script again."
        )


def launch_fallback_exe():
    """Look for existing HandTracker executable and return its path if available."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "release", "HandTracker.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "HandTracker.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "HandTracker.exe"),
    ]
    for exe in candidates:
        if os.path.isfile(exe):
            return exe
    return None


class KeyController:
    """Cross-platform keyboard input handler supporting pynput and keyboard."""

    def __init__(self):
        self._pynput_controller = None
        self._keyboard_module = None

        # Prioritize pynput on macOS and Linux (does not require root)
        if sys.platform != "win32":
            try:
                from pynput.keyboard import Controller
                self._pynput_controller = Controller()
            except Exception:
                pass

        if self._pynput_controller is None:
            try:
                import keyboard
                self._keyboard_module = keyboard
            except Exception:
                pass

        if self._keyboard_module is None and self._pynput_controller is None:
            try:
                from pynput.keyboard import Controller
                self._pynput_controller = Controller()
            except Exception:
                pass

    def press(self, key_char: str):
        if self._pynput_controller is not None:
            self._pynput_controller.press(key_char)
        elif self._keyboard_module is not None:
            self._keyboard_module.press(key_char)

    def release(self, key_char: str):
        if self._pynput_controller is not None:
            self._pynput_controller.release(key_char)
        elif self._keyboard_module is not None:
            self._keyboard_module.release(key_char)

    def is_available(self) -> bool:
        return self._pynput_controller is not None or self._keyboard_module is not None


# --- AUTO-INSTALLER & MODEL CHECKER ---
def setup_environment():
    if getattr(sys, "frozen", False):
        return

    install_missing_packages()
    ensure_hand_model()


try:
    setup_environment()
except Exception as error:
    print("\nAutomatic setup failed.")
    print(f"Error: {error}")
    print("\nFix:")
    print("- Easiest on Windows: download and run HandTracker.exe from Releases.")
    print(f"- Source users: install {RECOMMENDED_PYTHON} with pip enabled.")
    print(f"- Make sure {MODEL_FILENAME} is in the same folder as Handspython.py.")

    fallback_exe = launch_fallback_exe()
    if fallback_exe:
        print(f"\nFound standalone executable at: {fallback_exe}")
        choice = input("Would you like to start the standalone HandTracker.exe instead? (Y/n): ").strip().lower()
        if choice in ("", "y", "yes"):
            subprocess.Popen([fallback_exe])
            sys.exit(0)

    input("Press Enter to exit...")
    sys.exit(1)

try:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except ImportError as error:
    err_str = str(error)
    print("\nImport failed:", error)
    if "DLL load failed" in err_str:
        print("\nNote: Windows is missing the Microsoft Visual C++ Redistributable.")
        print("Please download and install it from:")
        print("https://aka.ms/vs/17/release/vc_redist.x64.exe")
    input("Press Enter to exit...")
    sys.exit(1)

key_controller = KeyController()

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

    # Open camera with cross-platform backend support
    if sys.platform == "darwin":
        cap = cv2.VideoCapture(cam_index, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap = cv2.VideoCapture(cam_index)
    else:
        cap = cv2.VideoCapture(cam_index)

    if not cap.isOpened():
        print(f"Error: Could not open camera (index {cam_index}).")
        if sys.platform == "darwin":
            print("\nmacOS Camera Permission Tip:")
            print("- Ensure your Terminal / Python has Camera permission.")
            print("- Open System Settings -> Privacy & Security -> Camera, and enable Terminal/Python.")
        elif sys.platform.startswith("linux"):
            print("\nLinux Camera Permission Tip:")
            print("- Ensure your user belongs to the 'video' group: sudo usermod -aG video $USER")
            print("- Verify camera device exists at /dev/video*.")
        else:
            print("- Check that the webcam is connected and not in use by another application.")
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
                    key_controller.press(FINGER_KEYS[i])
                    current_key_states[i] = True
                elif not fingers_active[i] and current_key_states[i]:
                    key_controller.release(FINGER_KEYS[i])
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
                    key_controller.release(FINGER_KEYS[i])
                    current_key_states[i] = False

        cv2.imshow('Hand Tracker Debug', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
