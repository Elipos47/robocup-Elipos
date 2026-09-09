#!/usr/bin/env bash
# Setup ambiente dev su Windows (eseguire da Git Bash nella root del repo).
# Crea .venv e installa le dipendenze core Fase M0.
# YOLO (ultralytics/onnxruntime) si installa in Fase M2 vittime: vedi requirements.txt.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! python -m pip --version >/dev/null 2>&1; then
  echo "pip mancante, installo con ensurepip..."
  python -m ensurepip --upgrade
fi

if [ ! -d .venv ]; then
  python -m venv .venv
fi

. .venv/Scripts/activate
python -m pip install --upgrade pip
pip install "numpy>=1.26" "opencv-python>=4.9" "pyserial>=3.5" "pytest>=8.0"

echo "--- verifica ---"
python -c "import cv2, numpy, serial; print('cv2', cv2.__version__, '| numpy', numpy.__version__)"
python -m pytest src/tests -q
echo "OK: ambiente pronto. Webots 2026a va installato a parte (installer da cyberbotics.com)."
