#!/bin/bash
# -----------------------------------------------------------------------------
# Aegis AI - Lightweight Multi-Agent Backend
# -----------------------------------------------------------------------------
# This script runs the Django backend WITHOUT loading the heavy PyTorch models.
# It enables STUB MODE for testing the LangGraph Orchestrator and Agent routing
# without burning through GPU/RAM limits.
# -----------------------------------------------------------------------------

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Force STUB_MODE to True to bypass PyTorch model loading
export AEGIS_STUB_MODE="True"

# Clear terminal for a clean start
clear

echo "╔════════════════════════════════════════════════════╗"
echo "║      AEGIS AI — MULTI-AGENT STATE (LIGHT MODE)     ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║ ✅ Orchestrator Agent     : Active                 ║"
echo "║ ⚠️ ML Agents (M1/M2)      : STUB MATCHING (Fast)   ║"
echo "║ 🤖 Auditor Agent (Groq)   : Active                 ║"
echo "║ 📊 Profiler Agent         : Active                 ║"
echo "║ ⚡ Enforcer Agent         : Active                 ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Run standard Django development server
python manage.py runserver 0.0.0.0:8000
