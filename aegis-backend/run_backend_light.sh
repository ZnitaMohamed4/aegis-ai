#!/bin/bash
# -----------------------------------------------------------------------------
# Aegis AI - Lightweight Multi-Agent Backend
# -----------------------------------------------------------------------------
# This script runs the Django backend WITHOUT loading the heavy PyTorch models.
# It enables STUB MODE for testing the LangGraph Orchestrator and Agent routing
# without burning through GPU/RAM limits.
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

log_info "Initializing AEGIS AI Multi-Agent Backend (Light Mode)"

if [ -d "venv" ]; then
    log_info "Activating virtual environment..."
    source venv/bin/activate
fi

log_warn "Configuring environment variables: AEGIS_STUB_MODE=True"
export AEGIS_STUB_MODE="True"

log_info "Component Status:"
log_info "  - Orchestrator Agent     : Active"
log_warn "  - ML Agents (M1/M2)      : STUB MATCHING (Fast Mode)"
log_info "  - Auditor Agent (Groq)   : Active"
log_info "  - Profiler Agent (Risk)  : Active"
log_info "  - Enforcer Agent (Action): Active"

log_success "Lightweight initialization complete."
log_info "Starting standard Django development server on 0.0.0.0:8000"

python manage.py runserver 0.0.0.0:8000
