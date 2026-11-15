"""Provider-free checks for the isolated report agent tool surface and final extraction."""

import asyncio

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from report_agent import (ReportOutputInvalid, ReportOutputNotJson, ReportOutputTruncated,
                          create_report_agent, extract_final_analysis)


class ReportFixtureModel(BaseChatModel):
    @property
    def model_provider(self):
        return "openai"

    @property
    def _llm_type(self):
        return "stellaris-report-fixture"

    def bind_tools(self, tools, **kwargs):
        names = {t.name for t in tools}
        assert {"read_report_evidence", "calculate_report"} <= names
        assert not ({"search_arxiv", "request_full_text", "read_paper", "search_paper",
                     "propose_experiment", "execute_analysis", "list_materials",
                     "organize_materials", "propose_claim", "task"} & names)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if not any(isinstance(m, ToolMessage) for m in messages):
            answer = AIMessage(content="", tool_calls=[{"name": "read_report_evidence",
                "args": {"run_id": "run_fixture", "section": "measurements", "offset": 0},
                "id": "report-read-1", "type": "tool_call"}])
        else:
            answer = AIMessage(content='<think>private reasoning</think>{"assessment":"inconclusive",'
                '"interpretation_markdown":"Assessment: inconclusive. Evidence is limited. Alternative explanations remain.",'
                '"limitations":["Unknown uncertainty"],"references":["run_fixture"]}')
        return ChatResult(generations=[ChatGeneration(message=answer)])


async def _check():
    calls = []

    def bridge(name, payload):
        calls.append((name, payload))
        return {"ok": True, "result": {"items": []}}

    request = {"run_id": "run_fixture", "project_id": "project_fixture",
               "report": {"title": "Test", "research_question": "Does evidence support the hypothesis?",
                          "evidence_run_ids": ["run_fixture"], "source_ids": []},
               "evidence_manifest": {"trusted": True}}
    agent, messages = create_report_agent(ReportFixtureModel(), request, bridge)
    result = await agent.ainvoke({"messages": [HumanMessage(content=messages[0]["content"])]})
    analysis = extract_final_analysis(result)
    assert calls == [("read_report_evidence", {"run_id": "run_fixture", "section": "measurements", "offset": 0})]
    assert analysis["assessment"] == "inconclusive"
    assert "private reasoning" not in analysis["interpretation_markdown"]
    assert analysis["references"] == ["run_fixture"]


def test_final_json_rejects_non_json_and_malformed_shape():
    class Message:
        type = "ai"
        tool_calls = []
        content = "not json"

    try:
        extract_final_analysis({"messages": [Message()]})
    except ValueError:
        pass
    else:
        raise AssertionError("invalid output must fail")


_VALID = ('{"assessment":"mixed","interpretation_markdown":"Assessment: mixed.",'
          '"limitations":["Small sample"],"references":["run_fixture"]}')


def _final(content, metadata=None):
    return {"messages": [AIMessage(content=content, response_metadata=metadata or {})]}


def test_final_json_tolerates_fences_and_surrounding_prose():
    for wrapped in (f"```json\n{_VALID}\n```", f"Here is the analysis:\n{_VALID}\nDone.",
                    [{"type": "text", "text": f"```\n{_VALID}\n```"}]):
        assert extract_final_analysis(_final(wrapped))["assessment"] == "mixed"


def test_final_json_failures_are_distinguishable():
    cases = [(_final(_VALID[:-40], {"stopReason": "max_tokens"}), ReportOutputTruncated),
             (_final(_VALID, {"finish_reason": "length"}), ReportOutputTruncated),
             (_final(_VALID[:-40]), ReportOutputNotJson),
             (_final('{"assessment":"proven","interpretation_markdown":"x","limitations":[],"references":[]}'),
              ReportOutputInvalid)]
    for result, expected in cases:
        try:
            extract_final_analysis(result)
        except expected:
            continue
        raise AssertionError(f"expected {expected.__name__}")


if __name__ == "__main__":
    asyncio.run(_check())
    test_final_json_rejects_non_json_and_malformed_shape()
    test_final_json_tolerates_fences_and_surrounding_prose()
    test_final_json_failures_are_distinguishable()
    print("PASS: real Deep Agent graph, bounded report tools, final JSON extraction without reasoning")
