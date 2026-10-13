#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Virtual Hand Tracker (Linux / macOS Launcher) ==="

# 1. Detect Python 3
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Error: Python 3 is not installed."
    echo "Please install Python 3 (3.10 - 3.12 recommended):"
    echo "  - macOS: brew install python"
    echo "  - Ubuntu/Debian: sudo apt update && sudo apt install -y python3 python3-pip python3-venv"
    echo "  - Arch Linux: sudo pacman -S python python-pip"
    echo "  - Fedora: sudo dnf install -y python3 python3-pip"
    exit 1
fi

# 2. Check architecture
ARCH_BITS=$($PYTHON_BIN -c "import struct; print(struct.calcsize('P') * 8)" 2>/dev/null || echo "64")
if [ "$ARCH_BITS" != "64" ]; then
    echo "Warning: Running $ARCH_BITS-bit Python. MediaPipe requires 64-bit Python."
fi

# 3. Create virtual environment to prevent PEP 668 externally-managed-environment errors
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Setting up Python virtual environment in $VENV_DIR..."
    $PYTHON_BIN -m venv "$VENV_DIR" 2>/dev/null || $PYTHON_BIN -m venv --without-pip "$VENV_DIR" 2>/dev/null || true
fi

# Activate virtual environment if present
if [ -f "$VENV_DIR/bin/activate" ]; then
    . "$VENV_DIR/bin/activate"
    PYTHON_BIN="python3"
fi

# 4. Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Verifying Python dependencies..."
    $PYTHON_BIN -m pip install --upgrade pip --quiet 2>/dev/null || true
    $PYTHON_BIN -m pip install --prefer-binary -r requirements.txt --quiet 2>/dev/null || true
fi

# 5. Launch Handspython.py
echo "Starting HandTracker..."
exec $PYTHON_BIN Handspython.py "$@"
