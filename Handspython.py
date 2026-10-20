import sys
import subprocess
import os
import math
import struct
import urllib.request
import json
import time
import argparse

MODEL_FILENAME = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MIN_MODEL_SIZE_BYTES = 1000000
RECOMMENDED_PYTHON = "Python 3.10 - 3.12 (64-bit)"
CONFIG_FILENAME = "config.json"

DEFAULT_CONFIG = {
    "camera_index": 0,
    "tracked_hand": "both",
    "keybinds": {
        "thumb": "d",
        "index": "f",
        "middle": "g",
        "ring": "h",
        "pinky": "j",
    },
    "show_fps": True,
    "smoothing": True,
    "flip_camera": True,
    "detection_confidence": 0.7,
}

# MediaPipe Hand Connections (Pairs of landmark indices to render hand skeleton)
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index finger
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle finger
    (9, 10), (10, 11), (11, 12), (0, 9),
    # Ring finger
    (13, 14), (14, 15), (15, 16), (0, 13),
    # Pinky finger
    (17, 18), (18, 19), (19, 20), (0, 17),
    # Palm knuckles
    (5, 9), (9, 13), (13, 17),
]

TIP_IDS = [4, 8, 12, 16, 20]
JOINT_IDS = [2, 6, 10, 14, 18]
FINGER_NAMES = ["Thumb", "Index", "Middle", "Ring", "Pinky"]


class SetupError(RuntimeError):
    pass


def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_or_create_config():
    config_path = os.path.join(get_base_dir(), CONFIG_FILENAME)
    config = dict(DEFAULT_CONFIG)

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                if isinstance(user_cfg, dict):
                    if "keybinds" in user_cfg and isinstance(user_cfg["keybinds"], dict):
                        merged_keys = dict(DEFAULT_CONFIG["keybinds"])
                        merged_keys.update(user_cfg["keybinds"])
                        user_cfg["keybinds"] = merged_keys
                    config.update(user_cfg)
            return config
        except Exception as e:
            print(f"Notice: Could not parse {CONFIG_FILENAME} ({e}). Using default settings.")
            return config

    # Auto-generate default configuration file for ease of customization
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    except Exception:
        pass

    return config


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

    # Step 2: Check opencv (cv2)
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
        os.path.join(get_base_dir(), "release", "HandTracker.exe"),
        os.path.join(get_base_dir(), "dist", "HandTracker.exe"),
        os.path.join(get_base_dir(), "HandTracker.exe"),
    ]
    for exe in candidates:
        if os.path.isfile(exe):
            return exe
    return None


class KeyController:
    """Cross-platform keyboard input handler supporting pynput and keyboard."""

    def __init__(self):
        self._pynput_controller = None
        self._pynput_key_cls = None
        self._keyboard_module = None

        # Prioritize pynput on macOS and Linux (does not require root)
        if sys.platform != "win32":
            try:
                from pynput.keyboard import Controller, Key
                self._pynput_controller = Controller()
                self._pynput_key_cls = Key
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
                from pynput.keyboard import Controller, Key
                self._pynput_controller = Controller()
                self._pynput_key_cls = Key
            except Exception:
                pass

    def _resolve_pynput_key(self, key_str: str):
        if not self._pynput_key_cls:
            return key_str
        k = key_str.strip().lower()
        special_map = {
            "space": self._pynput_key_cls.space,
            "enter": self._pynput_key_cls.enter,
            "return": self._pynput_key_cls.enter,
            "shift": self._pynput_key_cls.shift,
            "ctrl": self._pynput_key_cls.ctrl,
            "control": self._pynput_key_cls.ctrl,
            "alt": self._pynput_key_cls.alt,
            "tab": self._pynput_key_cls.tab,
            "esc": self._pynput_key_cls.esc,
            "escape": self._pynput_key_cls.esc,
            "up": self._pynput_key_cls.up,
            "down": self._pynput_key_cls.down,
            "left": self._pynput_key_cls.left,
            "right": self._pynput_key_cls.right,
            "backspace": self._pynput_key_cls.backspace,
        }
        return special_map.get(k, key_str)

    def press(self, key_char: str):
        try:
            if self._pynput_controller is not None:
                self._pynput_controller.press(self._resolve_pynput_key(key_char))
            elif self._keyboard_module is not None:
                self._keyboard_module.press(key_char)
        except Exception:
            pass

    def release(self, key_char: str):
        try:
            if self._pynput_controller is not None:
                self._pynput_controller.release(self._resolve_pynput_key(key_char))
            elif self._keyboard_module is not None:
                self._keyboard_module.release(key_char)
        except Exception:
            pass

    def release_all(self, key_list):
        for k in key_list:
            self.release(k)

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


def ask_tracked_hand(default_hand="both"):
    choices = {
        "": default_hand,
        "b": "both",
        "both": "both",
        "l": "left",
        "left": "left",
        "r": "right",
        "right": "right",
    }

    while True:
        prompt = f"Choose hand to track: left/right/both (Default {default_hand}): "
        choice = input(prompt).strip().lower()
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
    wrist = landmarks[0]
    thumb_cmc = landmarks[1]
    thumb_mcp = landmarks[2]
    thumb_ip = landmarks[3]
    thumb_tip = landmarks[4]
    index_mcp = landmarks[5]
    index_pip = landmarks[6]
    middle_mcp = landmarks[9]
    ring_mcp = landmarks[13]
    pinky_mcp = landmarks[17]

    palm_size = max(get_distance(wrist, middle_mcp), get_distance(index_mcp, pinky_mcp), 0.001)

    # 1. Fist / Closed Hand check:
    # When 3 or 4 other fingers are curled down, the hand is closed.
    # The only exception is a deliberate 'thumbs up' where thumb points straight up and away.
    if closed_finger_count >= 3:
        is_thumbs_up = (
            thumb_tip.y < thumb_mcp.y - palm_size * 0.20 and
            get_distance(thumb_tip, index_mcp) > palm_size * 0.65 and
            get_distance(thumb_tip, index_pip) > palm_size * 0.55
        )
        if not is_thumbs_up:
            return True

    # 2. Distance to pinky base (shrinks significantly when thumb curls across the palm)
    dist_tip_pinky = get_distance(thumb_tip, pinky_mcp) / palm_size
    dist_ip_pinky = get_distance(thumb_ip, pinky_mcp) / palm_size
    if dist_tip_pinky < 0.85 or (dist_tip_pinky < dist_ip_pinky and dist_tip_pinky < 1.05):
        return True

    # 3. Proximity to index / middle finger knuckles (thumb resting against fingers or palm)
    dist_index_mcp = get_distance(thumb_tip, index_mcp) / palm_size
    dist_index_pip = get_distance(thumb_tip, index_pip) / palm_size
    dist_middle_mcp = get_distance(thumb_tip, middle_mcp) / palm_size
    if dist_index_mcp < 0.58 or dist_index_pip < 0.58 or dist_middle_mcp < 0.68:
        return True

    # 4. Proximity to palm center
    palm_center_x = (index_mcp.x + middle_mcp.x + ring_mcp.x + pinky_mcp.x) / 4
    palm_center_y = (index_mcp.y + middle_mcp.y + ring_mcp.y + pinky_mcp.y) / 4
    tip_to_palm = get_point_distance(thumb_tip, palm_center_x, palm_center_y) / palm_size
    if tip_to_palm < 0.72:
        return True

    # 5. Distance to wrist (curling thumb down toward palm base)
    if get_distance(thumb_tip, wrist) < get_distance(thumb_ip, wrist) * 0.95 and tip_to_palm < 0.90:
        return True

    # 6. Joint Angle at Thumb IP (sharp bend in thumb joint)
    v1 = (thumb_ip.x - thumb_mcp.x, thumb_ip.y - thumb_mcp.y)
    v2 = (thumb_tip.x - thumb_ip.x, thumb_tip.y - thumb_ip.y)
    len1 = math.hypot(v1[0], v1[1])
    len2 = math.hypot(v2[0], v2[1])
    if len1 > 0 and len2 > 0:
        cos_angle = (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)
        # Cosine < 0.60 indicates the thumb joint is bent (> 53 degrees)
        if cos_angle < 0.60 and dist_tip_pinky < 1.15:
            return True

    return False


def draw_hand_skeleton(frame, landmarks, w, h):
    """Render smooth bones and joints connecting hand landmarks."""
    # Convert landmarks to pixel coordinates
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    # Draw connection bones
    for p1, p2 in HAND_CONNECTIONS:
        if p1 < len(pts) and p2 < len(pts):
            cv2.line(frame, pts[p1], pts[p2], (210, 210, 210), 2, cv2.LINE_AA)

    # Draw subtle joint points
    for idx, (x, y) in enumerate(pts):
        if idx not in TIP_IDS:
            cv2.circle(frame, (x, y), 4, (180, 180, 180), -1, cv2.LINE_AA)


def draw_hud(frame, w, h, fps, tracked_hand, detected_hand, finger_keys, current_key_states, show_fps):
    """Render professional semi-transparent HUD overlay."""
    # Top status bar background
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 42), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    # Top status text
    status_text = "RED = PRESSED | GREEN = OPEN"
    cv2.putText(frame, status_text, (15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)

    hand_label = f"HAND: {detected_hand.upper() if detected_hand else 'NONE'}"
    cv2.putText(frame, hand_label, (w // 2 - 60, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 215, 0), 1, cv2.LINE_AA)

    if show_fps:
        fps_text = f"FPS: {int(fps)}"
        cv2.putText(frame, fps_text, (w - 110, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 200), 1, cv2.LINE_AA)

    # Bottom Keybinds HUD
    card_width = 86
    spacing = 10
    total_w = 5 * card_width + 4 * spacing
    start_x = max(10, (w - total_w) // 2)
    card_y1 = h - 50
    card_y2 = h - 12

    for i in range(5):
        cx1 = start_x + i * (card_width + spacing)
        cx2 = cx1 + card_width
        is_active = current_key_states[i]

        # Active = Red highlight, Inactive = Dark slate with subtle green outline
        bg_col = (40, 40, 180) if is_active else (35, 35, 35)
        border_col = (0, 0, 255) if is_active else (0, 200, 0)

        cv2.rectangle(frame, (cx1, card_y1), (cx2, card_y2), bg_col, -1)
        cv2.rectangle(frame, (cx1, card_y1), (cx2, card_y2), border_col, 2)

        key_label = f"{FINGER_NAMES[i][:3]}:{finger_keys[i].upper()}"
        cv2.putText(frame, key_label, (cx1 + 8, card_y1 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)


def parse_arguments(config):
    parser = argparse.ArgumentParser(
        description="HandTracker - Real-time webcam hand tracking keyboard input simulator."
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        help="Webcam camera index (default from config or prompt).",
    )
    parser.add_argument(
        "--hand",
        choices=["both", "left", "right"],
        default=None,
        help="Which hand to track (both, left, or right).",
    )
    parser.add_argument(
        "--keys",
        type=str,
        default=None,
        help="Comma-separated keys for [thumb,index,middle,ring,pinky], e.g. 'd,f,g,h,j'.",
    )
    parser.add_argument(
        "--no-flip",
        action="store_true",
        help="Disable camera horizontal mirror flipping.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without displaying the OpenCV debug window for maximum efficiency.",
    )
    parser.add_argument(
        "--no-fps",
        action="store_true",
        help="Hide FPS counter in the overlay.",
    )
    return parser.parse_args()


def main():
    print("=== HandTracker BABFT (Virtual Hand Gesture Controller) ===")
    config = load_or_create_config()
    args = parse_arguments(config)

    # Camera index determination
    if args.camera is not None:
        cam_index = args.camera
    else:
        cam_input = input(f"Enter camera index (Default {config.get('camera_index', 0)}): ").strip()
        cam_index = int(cam_input) if cam_input.isdigit() else config.get("camera_index", 0)

    # Tracked hand determination
    if args.hand is not None:
        tracked_hand = args.hand
    else:
        tracked_hand = ask_tracked_hand(default_hand=config.get("tracked_hand", "both"))

    # Keybinds determination
    key_dict = config.get("keybinds", DEFAULT_CONFIG["keybinds"])
    finger_keys = [
        str(key_dict.get("thumb", "d")),
        str(key_dict.get("index", "f")),
        str(key_dict.get("middle", "g")),
        str(key_dict.get("ring", "h")),
        str(key_dict.get("pinky", "j")),
    ]

    if args.keys:
        custom_keys = [k.strip() for k in args.keys.split(",") if k.strip()]
        if len(custom_keys) == 5:
            finger_keys = custom_keys
        else:
            print(f"Warning: --keys requires exactly 5 comma-separated keys. Using: {finger_keys}")

    flip_camera = not args.no_flip and config.get("flip_camera", True)
    show_fps = not args.no_fps and config.get("show_fps", True)
    smoothing = config.get("smoothing", True)
    detection_conf = float(config.get("detection_confidence", 0.7))

    print(f"\nConfiguration loaded:")
    print(f"- Camera Index: {cam_index}")
    print(f"- Tracking Hand: {tracked_hand.capitalize()}")
    print(f"- Keybinds: Thumb={finger_keys[0].upper()}, Index={finger_keys[1].upper()}, "
          f"Middle={finger_keys[2].upper()}, Ring={finger_keys[3].upper()}, Pinky={finger_keys[4].upper()}")
    print(f"- Display Mirror: {'Enabled' if flip_camera else 'Disabled'}")
    print(f"- Headless Mode: {'Enabled' if args.headless else 'Disabled'}")
    print("Starting hand detector...\n")

    key_controller = KeyController()
    current_key_states = [False] * 5
    consecutive_active = [0] * 5

    # Initialize MediaPipe Tasks HandLandmarker
    base_options = python.BaseOptions(model_asset_path=resource_path(MODEL_FILENAME))
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=2,
        min_hand_detection_confidence=detection_conf,
        min_hand_presence_confidence=detection_conf,
        min_tracking_confidence=detection_conf,
    )
    detector = vision.HandLandmarker.create_from_options(options)

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

    fps = 0.0
    prev_time = time.time()

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            h, w, _ = frame.shape
            if flip_camera:
                frame = cv2.flip(frame, 1)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            detection_result = detector.detect(mp_image)
            raw_active = [0] * 5
            landmarks, detected_hand = get_selected_hand(detection_result, tracked_hand)

            if landmarks:
                # --- OTHER FINGERS LOGIC (Index, Middle, Ring, Pinky) ---
                for i in range(1, 5):
                    tip = landmarks[TIP_IDS[i]]
                    joint = landmarks[JOINT_IDS[i]]
                    if tip.y > joint.y:  # Finger is curled down
                        raw_active[i] = 1

                # --- THUMB LOGIC ---
                if is_thumb_closed(landmarks, sum(raw_active[1:])):
                    raw_active[0] = 1

                # Smooth / Debounce states to prevent jitter near threshold
                for i in range(5):
                    if raw_active[i]:
                        consecutive_active[i] = min(consecutive_active[i] + 1, 5)
                    else:
                        consecutive_active[i] = max(consecutive_active[i] - 1, 0)

                    target_state = (consecutive_active[i] >= 2) if smoothing else bool(raw_active[i])

                    # Update key states
                    if target_state and not current_key_states[i]:
                        key_controller.press(finger_keys[i])
                        current_key_states[i] = True
                    elif not target_state and current_key_states[i]:
                        key_controller.release(finger_keys[i])
                        current_key_states[i] = False

                # Visual Rendering (if not headless)
                if not args.headless:
                    draw_hand_skeleton(frame, landmarks, w, h)

                    for i in range(5):
                        tip_coords = (int(landmarks[TIP_IDS[i]].x * w), int(landmarks[TIP_IDS[i]].y * h))
                        color = (0, 0, 255) if current_key_states[i] else (0, 255, 0)
                        cv2.circle(frame, tip_coords, 10, color, -1, cv2.LINE_AA)
                        cv2.circle(frame, tip_coords, 12, (255, 255, 255), 1, cv2.LINE_AA)
                        cv2.putText(
                            frame,
                            finger_keys[i].upper(),
                            (tip_coords[0] - 5, tip_coords[1] + 5),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,
                            (255, 255, 255),
                            1,
                            cv2.LINE_AA,
                        )
            else:
                # Clear all active keys if no hand detected
                for i in range(5):
                    if current_key_states[i]:
                        key_controller.release(finger_keys[i])
                        current_key_states[i] = False
                    consecutive_active[i] = 0

            # FPS computation
            curr_time = time.time()
            time_diff = curr_time - prev_time
            if time_diff > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / time_diff)
            prev_time = curr_time

            # Show window if GUI active
            if not args.headless:
                draw_hud(frame, w, h, fps, tracked_hand, detected_hand, finger_keys, current_key_states, show_fps)
                cv2.imshow("HandTracker BABFT Debug", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        print("\nStopping HandTracker...")
    finally:
        # Guarantee all pressed keys are released on exit
        key_controller.release_all(finger_keys)
        cap.release()
        cv2.destroyAllWindows()
        print("HandTracker stopped cleanly. All keys released.")


if __name__ == "__main__":
    main()
