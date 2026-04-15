#!/bin/bash
# -----------------------------------------------------------------------------
# Aegis AI - Lightweight Backend Shortcut
# -----------------------------------------------------------------------------
# This script runs the Django backend WITHOUT loading the heavy PyTorch models.
# It enables STUB MODE, which uses quick heuristic keyword matching instead
# of XLM-RoBERTa, ensuring your computer stays fast while you work on the UI.
# -----------------------------------------------------------------------------

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Force STUB_MODE to True to bypass model loading in apps.py
export AEGIS_STUB_MODE="True"

echo "============================================="
echo "Starting AEGIS Backend in LIGHTWEIGHT mode"
echo "============================================="
echo "STUB MODE is ON. Heavy PyTorch models will NOT be loaded."
echo ""

# Run standard Django development server
python manage.py runserver 0.0.0.0:8000
