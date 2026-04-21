"""
AEGIS LangGraph Orchestrator — Graph Wiring Only.

This file defines the multi-agent pipeline topology using LangGraph.
All agent logic lives in ml_pipeline/agents/*.py.

Graph topology:
  pipeline (Agent 1+2) ──→ [needs_audit?] ──→ auditor (Agent 3)
                                │                     │
                                └──→ profiler (Agent 4) ←──┘
                                          │
                                     enforcer (Agent 5) → END

Refactored from 828-line monolith during Phase 2 audit (2026-04-21).
"""
from langgraph.graph import StateGraph, END

from .agents.state import ModerationState
from .agents.gatekeeper import ml_pipeline_node
from .agents.auditor import auditor_node
from .agents.profiler import profiler_node
from .agents.enforcer import enforcer_node


# 1. Initialize the graph with our State definition
workflow = StateGraph(ModerationState)

# 2. Add our Agent nodes
workflow.add_node("pipeline", ml_pipeline_node)
workflow.add_node("auditor", auditor_node)
workflow.add_node("profiler", profiler_node)
workflow.add_node("enforcer", enforcer_node)


# 3. Define the routing logic (Conditional Edges)
def route_after_pipeline(state: ModerationState):
    if state.get("needs_audit", False):
        return "auditor"   # Send to Agent 3
    return "profiler"      # Skip straight to Agent 4


# 4. Wire everything together!
workflow.set_entry_point("pipeline")
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