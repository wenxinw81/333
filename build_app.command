#!/bin/zsh
set -e
cd "$(dirname "$0")"

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller is not installed."
  echo "Install it with: python3 -m pip install pyinstaller"
  exit 1
fi

python3 -m PyInstaller \
  --name "HTRI XML Exporter" \
  --windowed \
  --onedir \
  --add-data "work:work" \
  work/htri_export_gui.py

echo "Build finished: dist/HTRI XML Exporter"
