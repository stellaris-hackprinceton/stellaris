"""Deterministic, provider-free Deep Agents tool-flow check; invoked only by integration tests."""

import asyncio

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

import agent_runner


class DeterministicTestModel(BaseChatModel):
    """A test-only chat model. It cannot be selected through the public API or runtime config."""

    called_tool: bool = False
    target_tool: str
    tool_args: dict

    @property
    def _llm_type(self):
        return "stellaris-deterministic-integration-test"

    def bind_tools(self, tools, **kwargs):
        available = {getattr(tool, "name", None) for tool in tools}
        assert self.target_tool in available, f"missing test tool {self.target_tool}: {available}"
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not self.called_tool:
            self.called_tool = True
            answer = AIMessage(content="", tool_calls=[{"name": self.target_tool, "args": self.tool_args,
                                                        "id": "test-tool-call-1", "type": "tool_call"}])
        else:
            assert any(isinstance(message, ToolMessage) for message in messages)
            answer = AIMessage(content="Deterministic agent response completed.")
        return ChatResult(generations=[ChatGeneration(message=answer)])


async def _check():
    events = []
    agent_runner.emit = events.append
    claim_tool = next(tool for tool in agent_runner.make_tools() if tool.name == "propose_claim")
    malformed = claim_tool.invoke({
        "kind": "hypothesis", "text": "Malformed citation fixture.", "evidence_json": "[]",
        "citations_json": "{}", "assumptions_json": "[]", "limitations_json": "[]"})
    assert "citations_json must be a JSON array" in str(malformed), malformed
    assert events == [], events

    # A literature finding filed as an observation (the failure seen live) is returned to the model.
    citation = '[{"source_id": "arxiv:0000.00000", "locator": null, "excerpt": null}]'
    misfiled = claim_tool.invoke({
        "kind": "observation", "text": "Papers report global regularity is open.", "evidence_json": "[]",
        "citations_json": citation, "assumptions_json": "[]", "limitations_json": "[]"})
    assert "kind \"inference\"" in str(misfiled), misfiled
    no_assumption = claim_tool.invoke({
        "kind": "inference", "text": "Papers report global regularity is open.", "evidence_json": "[]",
        "citations_json": citation, "assumptions_json": "[]", "limitations_json": "[]"})
    assert "at least one assumption" in str(no_assumption), no_assumption
    assert events == [], events
    accepted = claim_tool.invoke({
        "kind": "inference", "text": "Papers report global regularity is open.", "evidence_json": "[]",
        "citations_json": citation, "assumptions_json": '["The abstracts reflect the papers."]',
        "limitations_json": "[]"})
    assert "sent to the backend" in str(accepted), accepted
    assert [e["payload"]["kind"] for e in events] == ["inference"], events
    events.clear()

    write_model = DeterministicTestModel(target_tool="write_file", tool_args={
        "file_path": "/scratch-persistence-probe.txt", "content": "persistent project scratch marker"})
    agent = agent_runner.create_agent(write_model)
    result = await agent.ainvoke({"messages": [HumanMessage(content="Write the scratch persistence probe.")]})
    assert result["messages"][-1].content == "Deterministic agent response completed."

    read_model = DeterministicTestModel(target_tool="read_file", tool_args={
        "file_path": "/scratch-persistence-probe.txt"})
    agent = agent_runner.create_agent(read_model)
    result = await agent.ainvoke({"messages": [HumanMessage(content="Read the existing scratch persistence probe.")]})
    read_result = next(message for message in result["messages"] if isinstance(message, ToolMessage))
    assert "persistent project scratch marker" in str(read_result.content), read_result.content

    claim_model = DeterministicTestModel(target_tool="propose_claim", tool_args={
        "kind": "hypothesis", "text": "A deterministic test hypothesis.", "evidence_json": "[]",
        "citations_json": "[]", "assumptions_json": "[]", "limitations_json": "[]"})
    agent = agent_runner.create_agent(claim_model)
    result = await agent.ainvoke({"messages": [HumanMessage(content="Propose a deterministic claim.")]})
    assert events == [{"type": "proposal", "kind": "claim", "payload": {
        "kind": "hypothesis", "text": "A deterministic test hypothesis.", "evidence": [], "citations": [],
        "assumptions": [], "limitations": []}}], events
    assert result["messages"][-1].content == "Deterministic agent response completed."


if __name__ == "__main__":
    asyncio.run(_check())
    print("Deep Agents deterministic tool flow passed.")
