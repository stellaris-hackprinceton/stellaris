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


def _experiment_args(calibration, input_ids="[]"):
    return {"title": "Dropped-ball work-energy check", "hypothesis": "Work by gravity equals the change in kinetic energy.",
            "method": "physical", "protocol_markdown": "Record a dropped ball beside a metre stick.",
            "variables_json": '[{"name": "drop height", "role": "independent", "description": "Release height", "unit": "m"}]',
            "success_criteria_json": '["Energy terms agree within uncertainty."]',
            "input_artifact_ids_json": input_ids, "calibration_json": calibration,
            "limitations_json": '["Air resistance is neglected."]'}


def _check_experiment_proposals(events):
    """Regression for INVALID_AGENT_OUTPUT '/calibration/mode' (work-energy test): an unsupported calibration
    is returned to the model as a correctable tool error and never reaches the backend or fails the run.
    The exact mode the live agent submitted was not captured; these modes are representative fixtures."""
    tool = next(t for t in agent_runner.make_tools({"art_known"}) if t.name == "propose_experiment")
    for calibration in ('{"mode": "photogate", "assumptions": []}',
                        '{"mode": "reference_length", "artifact_id": "art_known", "frame_index": 0, '
                        '"point_a_px": [0, 0], "point_b_px": [10, 0], "reference_length_m": 1, '
                        '"reference_uncertainty_m": null, "assumptions": []}',
                        '{"mode": "none"}'):
        reply = str(tool.invoke(_experiment_args(calibration)))
        assert "not sent; nothing was saved" in reply and "calibration" in reply, reply
    unknown_input = str(tool.invoke(_experiment_args('{"mode": "none", "assumptions": []}', '["art_invented"]')))
    assert "input_artifact_ids" in unknown_input, unknown_input
    assert events == [], events
    accepted = str(tool.invoke(_experiment_args(
        '{"mode": "none", "assumptions": ["Pixels until the user calibrates the metre stick."]}', '["art_known"]')))
    assert "sent to the backend" in accepted, accepted
    assert [e["kind"] for e in events] == ["experiment"], events
    assert events[0]["payload"]["calibration"]["mode"] == "none", events
    events.clear()


# Recorded-shape Atom fixture with placeholder IDs; titles/abstracts are test text, not real papers.
_ARXIV_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><id>http://arxiv.org/abs/0000.00001v1</id><published>2020-01-02T00:00:00Z</published>
    <title>Fixture: video analysis of the work-energy theorem for a falling ball</title>
    <summary>Fixture abstract. Kinetic energy gain matches work done by gravity.</summary>
    <author><name>Fixture Author</name></author></entry>
  <entry><id>http://arxiv.org/abs/0000.00002v1</id><published>2021-01-02T00:00:00Z</published>
    <title>Fixture: student satisfaction with coursework in higher education</title>
    <summary>Fixture abstract about surveys and the energy of teaching teams.</summary>
    <author><name>Fixture Author</name></author></entry>
</feed>"""


def _check_arxiv_fixture(events):
    terms = agent_runner.arxiv_terms("Let's prove the work-energy theorem; find relevant literature")
    assert terms == [("work", "energy"), ("theorem",)], terms
    terms = agent_runner.arxiv_terms('"work energy theorem" AND kinetic')
    assert terms == [("work", "energy", "theorem"), ("kinetic",)], terms
    terms_only_stop = agent_runner.arxiv_terms('"of the" and/or Schrödinger equation')
    assert terms_only_stop == [("schrödinger",), ("equation",)], terms_only_stop
    assert agent_runner._has_term(" two theorems hold ", "theorem")
    assert not agent_runner._has_term(" a workshop report ", "work"), "prefix must not match"
    query = agent_runner.build_arxiv_query(terms)
    assert query == 'all:"work energy theorem" AND all:kinetic', query
    selected, rejected = agent_runner.parse_arxiv_entries(_ARXIV_FIXTURE, agent_runner.arxiv_terms("work-energy theorem"))
    assert [r["external_id"] for r in selected] == ["0000.00001v1"], selected
    assert [(c["record"]["external_id"], c["missing_terms"]) for c in rejected] == [
        ("0000.00002v1", ["work energy", "theorem"])], rejected
    tool = next(t for t in agent_runner.make_tools() if t.name == "search_arxiv")
    assert "stopwords" in str(tool.invoke({"query": "the and of"}))
    save = next(t for t in agent_runner.make_tools() if t.name == "save_source")
    assert "Only candidates" in str(save.invoke({"arxiv_id": "arxiv:0000.00001v1"})), "unsearched records are not saved"
    assert events == [], events


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

    _check_experiment_proposals(events)
    _check_arxiv_fixture(events)

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
