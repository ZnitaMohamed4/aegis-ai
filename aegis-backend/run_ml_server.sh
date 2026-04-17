#!/bin/bash
# -----------------------------------------------------------------------------
# Aegis AI - Heavy Multi-Agent Pipeline
# -----------------------------------------------------------------------------
# This script runs the FULL LangGraph architecture using Daphne (ASGI). 
# It loads the heavy PyTorch XLM-RoBERTa models into RAM for real-time inference.
# -----------------------------------------------------------------------------

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Ensure STUB_MODE is False to fully load PyTorch models
export AEGIS_STUB_MODE="False"

# Clear terminal for a clean start
clear

echo "╔════════════════════════════════════════════════════╗"
echo "║      AEGIS AI — MULTI-AGENT STATE (PROD MODE)      ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║ 🚀 Booting PyTorch Pipeline. Please wait...        ║"
echo "║ ✅ Orchestrator Agent     : Active                 ║"
echo "║ 🧠 ML Gatekeeper (M1)     : XLM-RoBERTa Binary     ║"
echo "║ 🔬 ML Classifier (M2)     : XLM-RoBERTa 4-Class    ║"
echo "║ 🤖 Auditor Agent (Groq)   : Llama 3 API            ║"
echo "║ 📊 Profiler Agent (Risk)  : Active                 ║"
echo "║ ⚡ Enforcer Agent (Action): Active                 ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Run ASGI server via Daphne
daphne -b 0.0.0.0 -p 8000 config.asgi:application
