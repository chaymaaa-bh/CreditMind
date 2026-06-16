from __future__ import annotations

from langgraph.graph import END, StateGraph

from m7_agents.agents import (
    anomalies,
    comportement,
    compliance,
    forecast,
    rapport,
    raisonnement,
    reseau,
    supervisor,
)
from m7_agents.state import CreditMindState

_PARALLEL_AGENTS = ["comportement", "reseau", "forecast", "anomalies", "compliance"]


def build_graph():
    builder = StateGraph(CreditMindState)

    builder.add_node("superviseur",  supervisor.run)
    builder.add_node("comportement", comportement.run)
    builder.add_node("reseau",       reseau.run)
    builder.add_node("forecast",     forecast.run)
    builder.add_node("anomalies",    anomalies.run)
    builder.add_node("compliance",   compliance.run)
    builder.add_node("raisonnement", raisonnement.run)
    builder.add_node("rapport",      rapport.run)

    builder.set_entry_point("superviseur")

    # Fan-out : superviseur → 5 agents en parallèle
    for agent in _PARALLEL_AGENTS:
        builder.add_edge("superviseur", agent)

    # Fan-in : 5 agents → raisonnement (attend tous les prédécesseurs)
    for agent in _PARALLEL_AGENTS:
        builder.add_edge(agent, "raisonnement")

    builder.add_edge("raisonnement", "rapport")
    builder.add_edge("rapport", END)

    return builder.compile()


graph = build_graph()
