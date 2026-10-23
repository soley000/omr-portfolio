"""Boucle de l'agent, avec un faux LLM qui joue un scenario d'appels d'outils."""
import json
from datetime import date

from chargedesk.eval.grading import grade
from chargedesk.eval.schema import Answer, Expected
from chargedesk.llm.client import LLMResponse
from chargedesk.systems import agent

E = date(2021, 10, 5)


def call(name, args, i=0):
    return {"id": f"c{i}", "name": name, "arguments": json.dumps(args)}


class ScriptedAgentLLM:
    """Chaque reponse prevue est soit une liste d'appels d'outils, soit un texte final."""
    def __init__(self, script):
        self.script, self.seen, self.tools_seen = list(script), [], []

    def chat(self, messages, tools=None, rep=0):
        self.seen.append([dict(m) for m in messages])
        self.tools_seen.append(tools)
        step = self.script.pop(0)
        calls, content = (step, None) if isinstance(step, list) else ([], step)
        return LLMResponse(content=content, tool_calls=calls, prompt_tokens=100, completion_tokens=20,
                           latency_s=0.1, cached=False, model="fake")


def final(value):
    return json.dumps({"status": "answered", "text": f"{value} pannes", "sources": ["get_metric"],
                       "figures": [{"name": "pannes", "value": value, "unit": "count"}]})


def test_agent_answers_from_a_tool_result(fake_warehouse):
    # 1er tour : le faux LLM demande l'outil ; on lit la vraie valeur pour l'ecrire dans la reponse
    probe = ScriptedAgentLLM([[call("get_metric", {"metric": "hw_faults", "period": "month_to_date"})], final(0)])
    out = agent.run(probe, fake_warehouse, E, "Combien de pannes ce mois-ci ?")
    value = out["tool_results"][0]["value"]
    llm = ScriptedAgentLLM([[call("get_metric", {"metric": "hw_faults", "period": "month_to_date"})], final(value)])
    out = agent.run(llm, fake_warehouse, E, "Combien de pannes ce mois-ci ?")
    assert out["n_steps"] == 1 and out["answer"]["figures"][0]["value"] == value
    tool_msg = llm.seen[1][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c0"
    g = grade(Answer(**out["answer"]), Expected(status="answered", figures=[{"name": "p", "value": value, "unit": "count"}]),
              tool_results=out["tool_results"])
    assert g.correct and not g.unsupported


def test_tool_error_is_given_back_to_the_llm(fake_warehouse):
    llm = ScriptedAgentLLM([[call("get_metric", {"metric": "hw_faults", "period": "last_7_days", "site": "Lune"})],
                            json.dumps({"status": "clarify", "text": "Quel site ?"})])
    out = agent.run(llm, fake_warehouse, E, "Pannes sur Lune ?")
    assert out["tool_trace"][0]["ok"] is False
    assert "error" in json.loads(llm.seen[1][-1]["content"])
    assert out["answer"]["status"] == "clarify"


def test_agent_is_stopped_after_max_steps(fake_warehouse):
    loop = [[call("get_drift", {}, i)] for i in range(agent.MAX_STEPS)]
    llm = ScriptedAgentLLM(loop + [final(1)])
    out = agent.run(llm, fake_warehouse, E, "?")
    assert out["n_steps"] == agent.MAX_STEPS
    assert llm.tools_seen[-1] is None          # dernier tour : plus d'outils proposes
    assert out["answer"] is not None


def test_bad_format_gets_one_retry(fake_warehouse):
    llm = ScriptedAgentLLM(["voici la reponse", final(3)])
    out = agent.run(llm, fake_warehouse, E, "?")
    assert out["retried_format"] and out["answer"]["figures"][0]["value"] == 3


def test_refusal_without_tools(fake_warehouse):
    llm = ScriptedAgentLLM([json.dumps({"status": "refuse", "text": "Lecture seule.",
                                        "refusal_reason": "modification"})])
    out = agent.run(llm, fake_warehouse, E, "Supprime la borne 23.")
    assert out["n_steps"] == 0 and out["answer"]["status"] == "refuse"


def test_text_after_json_is_tolerated():
    from chargedesk.systems.common import extract_json
    assert extract_json('{"status": "refuse"} et voila') == {"status": "refuse"}
    assert extract_json('Bien sur : ```json\n{"a": 1}\n``` merci') == {"a": 1}


def test_provider_rejection_is_given_back_to_the_model(fake_warehouse):
    from chargedesk.llm.client import ToolCallRejected

    class GroqLike(ScriptedAgentLLM):
        def chat(self, messages, tools=None, rep=0):
            if not self.seen:
                self.seen.append(messages)
                raise ToolCallRejected("tool call validation failed: attempted to call tool 'json'", 0.3)
            return super().chat(messages, tools, rep)

    llm = GroqLike([json.dumps({"status": "refuse", "text": "Lecture seule.", "refusal_reason": "modification"})])
    out = agent.run(llm, fake_warehouse, E, "Supprime la borne 23.")
    assert out["answer"]["status"] == "refuse" and out["provider_rejections"] == 1
    assert "sans appeler d'outil" in llm.seen[-1][-1]["content"]


def test_unreadable_final_answer_becomes_an_honest_clarification(fake_warehouse):
    llm = ScriptedAgentLLM(["", ""])
    out = agent.run(llm, fake_warehouse, E, "?")
    assert out["answer"]["status"] == "clarify" and out["fallback_answer"]


def test_guide_asks_to_clarify_vague_words():
    assert "problematique" in agent.GUIDE and "clarify" in agent.GUIDE
