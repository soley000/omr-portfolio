from types import SimpleNamespace

import pytest

import chargedesk.llm.client as client_mod
from chargedesk.llm.client import LLMClient, QuotaExhausted


class FakeTransport:
    """Imite le client OpenAI : renvoie des reponses ou leve des erreurs, dans l'ordre."""
    def __init__(self, script):
        self.script, self.calls = list(script), 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        msg = SimpleNamespace(content=step, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                               usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))


class ApiError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status_code = status


def make(tmp_path, script):
    return LLMClient(name="fake", model="fake-1", rpm=100, tpm=10**9, cache_dir=tmp_path,
                     transport=FakeTransport(script))


MSG = [{"role": "user", "content": "bonjour"}]


def test_identical_call_is_read_from_cache(tmp_path):
    llm = make(tmp_path, ["un"])
    first, second = llm.chat(MSG), llm.chat(MSG)
    assert first.content == second.content == "un"
    assert not first.cached and second.cached and llm.transport.calls == 1


def test_each_repetition_is_a_separate_call(tmp_path):
    llm = make(tmp_path, ["un", "deux"])
    assert llm.chat(MSG, rep=0).content == "un"
    assert llm.chat(MSG, rep=1).content == "deux"


def test_rate_limit_is_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)
    llm = make(tmp_path, [ApiError(429, "rate limit per minute"), "ok"])
    assert llm.chat(MSG).content == "ok" and llm.transport.calls == 2


def test_daily_quota_stops_the_run(tmp_path):
    llm = make(tmp_path, [ApiError(429, "Quota exceeded: requests per day")])
    with pytest.raises(QuotaExhausted):
        llm.chat(MSG)


class APITimeoutError(Exception):
    """Meme nom que l'erreur du client OpenAI quand le delai est depasse."""


def test_timeout_is_retried_then_reported_as_technical(tmp_path, monkeypatch):
    from chargedesk.llm.client import TransientError
    monkeypatch.setattr(client_mod.time, "sleep", lambda s: None)
    llm = make(tmp_path, [APITimeoutError("Request timed out."), "ok"])
    assert llm.chat(MSG).content == "ok"
    llm = make(tmp_path / "b", [APITimeoutError("Request timed out.")] * 5)
    with pytest.raises(TransientError):
        llm.chat(MSG)
    assert llm.transport.calls == 3          # 1 essai + 2 nouvelles tentatives, puis abandon


def test_provider_options_are_sent_and_change_the_cache_key(tmp_path):
    from chargedesk.llm.client import LLMClient
    seen = []

    class T:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen.append(kw)
                    from types import SimpleNamespace as N
                    return N(choices=[N(message=N(content="ok", tool_calls=None))],
                             usage=N(prompt_tokens=1, completion_tokens=1, completion_tokens_details=None))
    base = dict(name="x", model="m", rpm=100, tpm=10**6, cache_dir=tmp_path, transport=T)
    a, b = LLMClient(**base), LLMClient(**base, extra={"reasoning_effort": "low"})
    msgs = [{"role": "user", "content": "q"}]
    assert a._key(msgs, None, 0) != b._key(msgs, None, 0)
    b.chat(msgs)
    assert seen[-1]["reasoning_effort"] == "low"


def test_api_mode_does_not_wait_a_minute_for_the_rate_limit(tmp_path):
    import time
    import pytest
    from chargedesk.llm.client import LLMClient, TransientError
    c = LLMClient(name="x", model="m", rpm=1, tpm=10**6, cache_dir=None, transport=None, max_wait_s=2)
    c._calls.append((time.monotonic(), 10))           # une requete deja faite cette minute, rpm = 1
    t0 = time.monotonic()
    with pytest.raises(TransientError):
        c._wait_for_budget(10)
    assert time.monotonic() - t0 < 1


def _conn_error():
    class APIConnectionError(Exception):
        pass
    return APIConnectionError("Connection error.")


def test_connection_drops_are_retried_quickly_then_reported(tmp_path):
    import pytest
    from types import SimpleNamespace as N
    from chargedesk.llm.client import LLMClient, TransientError
    seen = {"n": 0}

    def make(fail_times):
        class T:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kw):
                        seen["n"] += 1
                        if seen["n"] <= fail_times:
                            raise _conn_error()
                        return N(choices=[N(message=N(content="ok", tool_calls=None))],
                                 usage=N(prompt_tokens=1, completion_tokens=1, completion_tokens_details=None))
        return T
    c = LLMClient(name="x", model="m", rpm=100, tpm=10**6, cache_dir=None, transport=make(2),
                  max_retries=2, max_timeouts=0, max_wait_s=6)
    assert c.chat([{"role": "user", "content": "q"}]).content == "ok"     # 2 coupures puis succes
    seen["n"] = 0
    c = LLMClient(name="x", model="m", rpm=100, tpm=10**6, cache_dir=None, transport=make(9),
                  max_retries=2, max_timeouts=0, max_wait_s=6)
    with pytest.raises(TransientError, match="connexion impossible"):
        c.chat([{"role": "user", "content": "q"}])


def test_per_call_timeout_is_passed_to_the_provider(tmp_path):
    from types import SimpleNamespace as N
    from chargedesk.llm.client import LLMClient
    seen = {}

    class T:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen.update(kw)
                    return N(choices=[N(message=N(content="ok", tool_calls=None))],
                             usage=N(prompt_tokens=1, completion_tokens=1, completion_tokens_details=None))
    LLMClient(name="x", model="m", rpm=100, tpm=10**6, cache_dir=None, transport=T).chat(
        [{"role": "user", "content": "q"}], timeout=7)
    assert seen["timeout"] == 7
