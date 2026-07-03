"""The triage agent: a hand-built LangGraph StateGraph.

        agent ── tool_calls ──▶ tools ──▶ agent ... (loop)
          │
          └─ no tool calls / escalated / iteration cap ──▶ END

The iteration cap (8 agent turns) triggers a forced escalation rather than a silent stop —
the same "never silently drop" rule the KB imposes on human triage.
"""

import time
from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from .llm import make_chat_model
from .registry import VersionConfig
from .tools import RunContext, build_tools, force_escalation
from .tracing import RunRecorder

MAX_AGENT_TURNS = 8

FORCED_ESCALATION_TEXT = (
    "I wasn't able to reach a grounded resolution within my investigation limit, so I've "
    "escalated this to a human support engineer ({esc_id}). They will review everything "
    "gathered so far and follow up with you directly."
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


@dataclass
class GraphEvent:
    """Streamed to the chat UI while the run progresses."""

    type: str                      # tool_call | tool_result | final
    data: dict = field(default_factory=dict)


def _usage(message: AIMessage) -> tuple[int, int]:
    meta = getattr(message, "usage_metadata", None) or {}
    return int(meta.get("input_tokens") or 0), int(meta.get("output_tokens") or 0)


def build_graph(
    config: VersionConfig,
    ctx: RunContext,
    recorder: RunRecorder,
    model: BaseChatModel | None = None,
):
    tools = build_tools(ctx, config.tools_enabled)
    tools_by_name = {t.name: t for t in tools}
    llm = (model or make_chat_model(config.model)).bind_tools(tools)
    system = SystemMessage(content=config.system_prompt)
    counters = {"agent_turns": 0, "input_tokens": 0, "output_tokens": 0}

    def agent_node(state: AgentState) -> dict[str, Any]:
        counters["agent_turns"] += 1
        t0 = time.monotonic()
        reply: AIMessage = llm.invoke([system, *state["messages"]])
        latency = int((time.monotonic() - t0) * 1000)
        tin, tout = _usage(reply)
        counters["input_tokens"] += tin
        counters["output_tokens"] += tout
        recorder.step(
            "llm",
            "agent",
            {"last_message": str(state["messages"][-1].content)[:2000]},
            {
                "content": str(reply.content)[:4000],
                "tool_calls": [
                    {"name": c["name"], "args": c["args"]} for c in (reply.tool_calls or [])
                ],
            },
            latency,
        )
        return {"messages": [reply]}

    def tools_node(state: AgentState) -> dict[str, Any]:
        last = state["messages"][-1]
        results: list[ToolMessage] = []
        for call in last.tool_calls or []:
            t0 = time.monotonic()
            tool = tools_by_name.get(call["name"])
            if tool is None:
                output = f"Unknown tool {call['name']!r}."
            else:
                try:
                    output = tool.invoke(call["args"])
                except Exception as exc:  # tool failure is data, not a crash
                    output = f"Tool error: {exc}"
            latency = int((time.monotonic() - t0) * 1000)
            recorder.step("tool", call["name"], call["args"], {"output": str(output)[:4000]},
                          latency)
            results.append(ToolMessage(content=str(output), tool_call_id=call["id"]))
        return {"messages": results}

    def route(state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            if counters["agent_turns"] >= MAX_AGENT_TURNS:
                return "cap"
            return "tools"
        return "end"

    def cap_node(state: AgentState) -> dict[str, Any]:
        esc_id = force_escalation(ctx, "iteration cap reached during triage")
        recorder.step("tool", "forced_escalation", {"reason": "iteration cap"}, {"id": esc_id})
        return {"messages": [AIMessage(content=FORCED_ESCALATION_TEXT.format(esc_id=esc_id))]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("cap", cap_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", "cap": "cap", "end": END})
    graph.add_edge("tools", "agent")
    graph.add_edge("cap", END)
    compiled = graph.compile()

    def run(history: list[BaseMessage]):
        """Execute the graph, yielding GraphEvents; finishes the recorder."""
        final_text = ""
        status = "final"
        try:
            for update in compiled.stream({"messages": history}, stream_mode="updates"):
                for node, payload in update.items():
                    for msg in payload.get("messages", []):
                        if isinstance(msg, AIMessage) and msg.tool_calls:
                            yield GraphEvent(
                                "tool_call",
                                {"tools": [c["name"] for c in msg.tool_calls]},
                            )
                        elif isinstance(msg, ToolMessage):
                            yield GraphEvent(
                                "tool_result", {"preview": str(msg.content)[:300]}
                            )
                        elif isinstance(msg, AIMessage):
                            final_text = str(msg.content)
                    if node == "cap":
                        status = "max_iterations"
            if ctx.escalated and status != "max_iterations":
                status = "escalated"
        except Exception as exc:
            status = "error"
            final_text = final_text or f"Run failed: {exc}"
            recorder.step("llm", "error", {}, {"error": str(exc)})
        recorder.finish(status, final_text, counters["input_tokens"], counters["output_tokens"])
        yield GraphEvent(
            "final",
            {
                "text": final_text,
                "run_id": recorder.run_id,
                "status": status,
                "escalated": ctx.escalated,
            },
        )

    return run
