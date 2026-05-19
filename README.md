# HandTrackerBABFT
An Hand tracker built with python and uses ai to track the hand.

# HandTracker

HandTracker is a Python/OpenCV + MediaPipe hand-tracking tool that turns finger curls into keyboard inputs.

It uses your webcam to detect one hand in real time. When you curl a finger, the app presses a matching keyboard key. When you open the finger again, the key is released.

## Keybinds

| Finger | Key |
|---|---|
| Thumb | D |
| Index | F |
| Middle | G |
| Ring | H |
| Pinky | J |

## How It Works

- Opens your webcam.
- Tracks one hand using MediaPipe.
- Detects whether each finger is curled or open.
- Presses the assigned key while a finger is curled.
- Releases the key when the finger opens.
- Shows a debug window:
  - Green dot = finger open
  - Red dot = key pressed

## Controls

- Enter your camera index when the app starts.
- Press `Q` in the camera window to quit.

## Windows EXE

The Windows build is packaged as a standalone `.exe`, so Python does not need to be installed.

Just run:

HandTracker.exe
