#!/bin/zsh
set -e
cd "$(dirname "$0")"
python3 work/htri_export_gui.py
