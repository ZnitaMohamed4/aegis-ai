#!/bin/bash
# -----------------------------------------------------------------------------
# Aegis AI - Heavy ML Pipeline Shortcut
# -----------------------------------------------------------------------------
# This script runs the FULL architecture using Daphne (ASGI). 
# It loads the heavy PyTorch XLM-RoBERTa models into RAM for real-time 
# inference and handles WebSockets for live Angular dashboard updates.
# -----------------------------------------------------------------------------

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Ensure STUB_MODE is False to definitely load models
export AEGIS_STUB_MODE="False"

echo "============================================="
echo "Starting AEGIS Backend + ML PIPELINE (Daphne)"
echo "============================================="
echo "Loading PyTorch models into RAM... This may take a moment."
echo ""

# Run ASGI server via Daphne
daphne -b 0.0.0.0 -p 8000 config.asgi:application
