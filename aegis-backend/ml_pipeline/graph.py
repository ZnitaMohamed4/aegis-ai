"""
AEGIS LangGraph Orchestrator — Graph Wiring Only.

This file defines the multi-agent pipeline topology using LangGraph.
All agent logic lives in ml_pipeline/agents/*.py.

Graph topology (6 agents):
  transcriber (Agent 0) ──→ pipeline (Agent 1+2) ──→ [needs_audit?] ──→ auditor (Agent 3)
                                    │                       │
                                    └──→ profiler (Agent 4) ←──┘
                                              │
                                         enforcer (Agent 5) → END

Refactored from 828-line monolith during Phase 2 audit (2026-04-21).
Agent 0 (Transcription) added during Phase 4 hardening (2026-06-10).
"""
from langgraph.graph import StateGraph, END

from .agents.state import ModerationState
from .agents.transcriber import transcriber_node
from .agents.gatekeeper import ml_pipeline_node
from .agents.auditor import auditor_node
from .agents.profiler import profiler_node
from .agents.enforcer import enforcer_node


# 1. Initialize the graph with our State definition
workflow = StateGraph(ModerationState)

# 2. Add our Agent nodes
workflow.add_node("transcriber", transcriber_node)   # Agent 0: Speech-to-Text
workflow.add_node("pipeline", ml_pipeline_node)      # Agent 1+2: ML Pipeline
workflow.add_node("auditor", auditor_node)           # Agent 3: LLM Auditor
workflow.add_node("profiler", profiler_node)         # Agent 4: Behavioral Profiler
workflow.add_node("enforcer", enforcer_node)         # Agent 5: Enforcer


# 3. Define the routing logic (Conditional Edges)
def route_after_pipeline(state: ModerationState):
    if state.get("needs_audit", False):
        return "auditor"   # Send to Agent 3
    return "profiler"      # Skip straight to Agent 4


# 4. Wire everything together!
workflow.set_entry_point("transcriber")               # Agent 0 is the entry point
workflow.add_edge("transcriber", "pipeline")          # Agent 0 → Agent 1+2
workflow.add_conditional_edges(
    "pipeline",
    route_after_pipeline,
    {
        "auditor": "auditor",
        "profiler": "profiler"
    }
)
workflow.add_edge("auditor", "profiler")
workflow.add_edge("profiler", "enforcer")    # Agent 4 → Agent 5
workflow.add_edge("enforcer", END)           # Agent 5 ends the graph

# 5. Compile it into an executable app
aegis_graph = workflow.compile()