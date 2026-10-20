# HandTracker BABFT

HandTracker BABFT is a real-time computer vision tool that turns human hand gestures and finger curls into keyboard inputs, designed specifically for controlling builds, mechanics, servos, thrusters, and contraptions in **Roblox: Build a Boat for Treasure (BABFT)** and other games.

It uses OpenCV and Google MediaPipe to track hand landmarks in real time. When you curl a finger, the assigned key is pressed down; when you open your finger back up, the key is immediately released.

---

# 📜 LICENSE & ATTRIBUTION REQUIREMENTS

> [!IMPORTANT]
> ### **mrproiss1 Attribution License**
> This project is licensed under the custom **mrproiss1 Attribution License**. You are free to use, modify, and share this tool for both personal and public use under the mandatory attribution terms below.

```text
==================================================================================
                          mrproiss1 Attribution License
                           Copyright (c) 2026 mrproiss1
==================================================================================

Permission is granted to use, copy, modify, and share this project for
personal or public use, subject to the conditions below.

If you post a video, stream, tutorial, showcase, review, or other public
media featuring this project, you must clearly credit:

    Created by mrproiss1
    GitHub: https://github.com/mrproiss1

1. The credit must be VISIBLE in the video itself (on screen).
2. Clearly place the credit and GitHub link in the video description.
3. You may NOT claim this project as your own original work.

This project is provided "as is", without warranty of any kind, express or
implied. The author is not liable for any damages or issues caused by use of
this project.
==================================================================================
```

### 🎬 Mandatory Content Creator Checklist (YouTube, TikTok, Twitch, Kick)
If you feature this software in any video, stream, tutorial, or showcase:
- [x] **On-Screen Display**: Display **"Created by mrproiss1"** visibly in your video.
- [x] **Video Description**: Include **`Created by mrproiss1 | GitHub: https://github.com/mrproiss1`** in the top section of your video description.
- [x] **Originality**: Do not claim ownership, originality, or creation of this tracking tool.

---

## Features

- **Real-Time Hand Landmark Tracking**: Tracks thumb, index, middle, ring, and pinky finger positions at high frame rates.
- **Visual Hand Skeleton HUD**: Renders real-time bone connections, joint indicators, and status badges.
- **Customizable Keybinds (`config.json`)**: Easily change the assigned key for each finger without modifying Python code.
- **Special Key Support**: Supports single characters (`d`, `f`, `g`, `h`, `j`) as well as special keys like `space`, `enter`, `shift`, `ctrl`, `alt`, `tab`, and arrow keys (`up`, `down`, `left`, `right`).
- **Fist & Thumb Intelligence**: Sophisticated thumb curl detection that recognizes closed fists, thumb tucks, and deliberate thumbs-up gestures.
- **Anti-Jitter Smoothing**: Debouncing filter to prevent keystroke fluttering when hovering near boundary angles.
- **Safe Key Release Guarantee**: Clean `try...finally` teardown ensures all pressed keys are instantly released when the app exits, preventing stuck keys.
- **Command Line Flags**: Supports `--camera`, `--hand`, `--keys`, `--headless`, and `--no-flip` for quick automation and streaming setups.
- **Cross-Platform**: Works natively on Windows, macOS, and Linux.

---

## Default Keybinds

| Finger | Default Key | Suggested BABFT Control |
|---|---|---|
| **Thumb** | `D` | Steer Right / Mechanism 1 |
| **Index** | `F` | Activate Tool / Thruster |
| **Middle** | `G` | Harpoon / Launch / Magnet |
| **Ring** | `H` | Custom Mechanism 2 |
| **Pinky** | `J` | Steer Left / Reset |

> [!TIP]
> You can customize any key in `config.json` or pass custom keys via command line (`--keys space,f,g,h,j`).

---

## Configuration (`config.json`)

On first launch, `config.json` is automatically loaded or created next to the application:

```json
{
    "camera_index": 0,
    "tracked_hand": "both",
    "keybinds": {
        "thumb": "d",
        "index": "f",
        "middle": "g",
        "ring": "h",
        "pinky": "j"
    },
    "show_fps": true,
    "smoothing": true,
    "flip_camera": true,
    "detection_confidence": 0.7
}
```

---

## How to Run

### Option 1: Standalone Executable (Windows)
1. Download `HandTracker.exe` from the latest **Releases**.
2. Run `HandTracker.exe` (no Python or libraries required).
3. Select your camera index and hand tracking preference (or press Enter for defaults).
4. Curl your fingers to trigger the keys in-game. Press **Q** in the camera window to quit.

### Option 2: Running from Source (Windows / macOS / Linux)

#### Windows
Double-click `run_windows.bat` or run in terminal:
```powershell
python Handspython.py
```

#### Linux & macOS
Run the automated launcher:
```bash
bash run_linux_mac.sh
```

#### Command Line Arguments
```bash
# Launch camera 1 tracking right hand with custom keys:
python Handspython.py --camera 1 --hand right --keys space,f,g,h,j

# Run in headless mode (no video window, minimal CPU/GPU usage):
python Handspython.py --camera 0 --headless
```

---

## Requirements & Setup

```bash
pip install -r requirements.txt
```

### Dependencies:
- `opencv-python`
- `mediapipe`
- `pynput`
- `keyboard` (Windows fallback)

---

## Building the Executable

```powershell
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --clean HandTracker.spec
```

The compiled binary will be placed in `dist/HandTracker.exe`.
