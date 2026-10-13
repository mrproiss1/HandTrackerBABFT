# HandTracker

HandTracker is a webcam hand-tracking tool that turns finger curls into keyboard inputs.

It uses OpenCV and MediaPipe to detect one hand in real time. When you curl a finger, the app presses a matching keyboard key. When you open the finger again, the key is released.

The thumb detection also checks for a closed fist, so the thumb should count as pressed when it is tucked across the palm.

## Keybinds

| Finger | Key |
| --- | --- |
| Thumb | D |
| Index | F |
| Middle | G |
| Ring | H |
| Pinky | J |

## How to Use the EXE

1. Download `HandTracker.exe` from the release or `dist` folder.
2. Run `HandTracker.exe`.
3. Enter your camera index.
   - Most webcams use `0`.
   - If `0` does not work, try `1` or `2`.
4. Choose which hand should control the keys.
   - Type `left`, `right`, or `both`.
   - Press Enter to use the default: `both`.
5. Curl your fingers to press the matching keys.
6. Press `Q` in the camera window to quit.

The `.exe` version is standalone. You do not need to install Python or any Python libraries.

## How to Run From Source

This works on Windows, Linux, and macOS if Python is installed.

`Handspython.py` can install missing Python packages the first time it runs:

- If Python packages are missing, it tries to install them with `pip`.
- `hand_landmarker.task` will be automatically downloaded if missing, or you can place it in the same folder.
- Internet is needed only if Python packages or the AI model are missing.
- **Important for Windows 10/11**: You must use **64-bit Python** (Python 3.10, 3.11, or 3.12 64-bit). MediaPipe does not provide 32-bit Windows wheels.
- If you encounter a C++ DLL error, install the [Microsoft Visual C++ 2015-2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).
- If you do not want to install Python, just download and run `HandTracker.exe` from Releases.

### Easy Run

Windows:

```text
Double-click run_windows.bat
```

Linux/macOS:

```sh
sh run_linux_mac.sh
```

### Manual Run

Make sure this file is in the same folder:

```text
hand_landmarker.task
```

Then run the Python file:

```powershell
python Handspython.py
```

If you prefer to install the packages yourself first:

```powershell
pip install -r requirements.txt
```

The model file `hand_landmarker.task` is required for the Python version.

When the app starts, it asks which hand to track:

```text
Choose hand to track: left/right/both (Default both):
```

## Building the EXE

Install the runtime packages and PyInstaller:

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

Build the standalone Windows exe:

```powershell
pyinstaller --clean --onefile --noupx --name HandTracker --add-data "hand_landmarker.task;." --collect-data mediapipe Handspython.py
```

The finished app will be created at:

```text
dist/HandTracker.exe
```

Native apps for Linux and macOS can be built directly on those systems with PyInstaller or via GitHub Actions. The Python launcher (`run_linux_mac.sh`) provides automated virtual environment setup and dependency installation.

## Debug Window

The camera window shows finger status:

| Color | Meaning |
| --- | --- |
| Green | Finger is open |
| Red | Finger is curled and the key is pressed |

## Platform-Specific Notes

### Windows
- Windows SmartScreen or antivirus may show a warning because the `.exe` is unsigned.
- If using Python directly, ensure it is 64-bit Python (MediaPipe does not provide 32-bit Windows wheels).
- If you see a missing DLL error, install the [Microsoft Visual C++ 2015-2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### macOS
- Run `./run_linux_mac.sh` from Terminal.
- **Accessibility Permission**: Key simulation requires accessibility permission. Go to **System Settings -> Privacy & Security -> Accessibility**, and ensure Terminal (or your Python IDE) is checked.
- **Camera Permission**: When prompted, allow camera access, or go to **System Settings -> Privacy & Security -> Camera**.

### Linux (Ubuntu, Debian, Arch, Fedora)
- Run `bash run_linux_mac.sh`.
- The launcher automatically creates a local `.venv` environment to prevent `externally-managed-environment` (PEP 668) conflicts.
- **Keyboard Simulation**: Uses `pynput` natively under X11/XWayland without requiring root or `sudo`.
- **Camera Access**: Ensure your user is in the `video` group:
  ```bash
  sudo usermod -aG video $USER
  ```
  Then log out and log back in.

## License and Credit

This project uses the HandTracker Attribution License.

If you post a video, stream, tutorial, showcase, review, or other public media featuring this project, you must clearly credit:

```text
Created by mrproiss1
GitHub: https://github.com/mrproiss1
```
