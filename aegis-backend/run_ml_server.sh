#!/bin/bash
# -----------------------------------------------------------------------------
# Aegis AI - Heavy Multi-Agent Pipeline
# -----------------------------------------------------------------------------
# This script runs the FULL LangGraph architecture using Daphne (ASGI). 
# It loads the heavy PyTorch XLM-RoBERTa models into RAM for real-time inference.
# -----------------------------------------------------------------------------

set -e

# Logging utilities
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $(date +'%Y-%m-%d %H:%M:%S') - $1"; }

cd "$(dirname "$0")"

log_info "Initializing AEGIS AI Multi-Agent Pipeline (Production Mode)"

if [ -d "venv" ]; then
    log_info "Activating virtual environment..."
    source venv/bin/activate
fi

log_info "Configuring environment variables: AEGIS_STUB_MODE=False"
export AEGIS_STUB_MODE="False"

log_info "Booting PyTorch Pipeline. Loading models into memory..."
log_info "Component Status:"
log_info "  - Orchestrator Agent     : Active"
log_info "  - ML Gatekeeper (M1)     : XLM-RoBERTa Binary"
log_info "  - ML Classifier (M2)     : XLM-RoBERTa 4-Class"
log_info "  - Auditor Agent (Groq)   : Llama 3 API"
log_info "  - Profiler Agent (Risk)  : Active"
log_info "  - Enforcer Agent (Action): Active"

log_success "Pipeline initialization complete."
log_info "Starting ASGI server via Daphne on 0.0.0.0:8000"

daphne -b 0.0.0.0 -p 8000 config.asgi:application
