"""The LLM gateway, tested with scripted fake providers: no network, no API key, no bill."""

import json

import httpx
import pytest

from rti_mate.llm.gateway import (
    CircuitBreaker,
    FakeLLM,
    LLMError,
    LLMGateway,
    LLMResult,
    LLMUnavailable,
    OpenAICompatProvider,
    Reply,
    cost_inr,
)

ASK = [{"role": "user", "content": "What is a path parameter?"}]


def busy(retry_after: float | None = None) -> LLMError:
    return LLMError("HTTP 429: slow down", retryable=True, retry_after=retry_after)


def bad_key() -> LLMError:
    return LLMError("HTTP 401: invalid API key", retryable=False)


class Harness:
    """A gateway with fake providers, a fake clock, and lists that remember what happened."""

    def __init__(self, *providers: FakeLLM, **options) -> None:
        self.now = 0.0
        self.slept: list[float] = []
        self.rows: list[dict] = []
        self.gateway = LLMGateway(
            list(providers),
            recorder=self.record,
            sleep=self.sleep,
            clock=lambda: self.now,
            **options,
        )

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)

    async def record(self, row: dict) -> None:
        self.rows.append(row)


async def collect(stream) -> tuple[str, LLMResult]:
    pieces = [item async for item in stream]
    return "".join(pieces[:-1]), pieces[-1]


async def test_generate_returns_the_answer_with_tokens_and_cost():
    h = Harness(FakeLLM("gemini", "gemini-3.8-flash", ["A path parameter is part of the URL."]))
    result = await h.gateway.generate(ASK)
    assert result.text == "A path parameter is part of the URL."
    assert (result.provider, result.attempts, result.fallback_used) == ("gemini", 1, False)
    assert result.tokens_in == 12 and result.tokens_out == 8
    assert result.cost_inr == cost_inr("gemini-3.8-flash", 12, 8, 95.0) > 0


async def test_a_429_is_retried_after_waiting_at_least_retry_after():
    primary = FakeLLM("gemini", script=[busy(retry_after=3), "Second try worked."])
    h = Harness(primary)
    result = await h.gateway.generate(ASK)
    assert result.text == "Second try worked." and result.attempts == 2
    assert primary.calls == 2 and h.slept[0] >= 3


async def test_falls_back_when_the_primary_keeps_failing():
    primary, backup = FakeLLM("gemini", script=[busy(), busy()]), FakeLLM("groq", script=["Hi."])
    h = Harness(primary, backup)
    result = await h.gateway.generate(ASK)
    assert (result.provider, result.fallback_used) == ("groq", True)
    assert primary.calls == 2 and backup.calls == 1
    assert [row["status"] for row in h.rows] == ["error", "ok"]  # both calls are on record


async def test_a_wrong_api_key_is_not_retried():
    primary, backup = FakeLLM("gemini", script=[bad_key()]), FakeLLM("groq", script=["Hi."])
    h = Harness(primary, backup)
    result = await h.gateway.generate(ASK)
    assert primary.calls == 1 and h.slept == [] and result.provider == "groq"


async def test_all_providers_down_raises_llm_unavailable():
    h = Harness(FakeLLM("gemini", script=[bad_key()]), FakeLLM("groq", script=[bad_key()]))
    with pytest.raises(LLMUnavailable, match="gemini.*groq"):
        await h.gateway.generate(ASK)


async def test_no_provider_configured_raises_llm_unavailable():
    with pytest.raises(LLMUnavailable, match="no LLM provider"):
        await Harness().gateway.generate(ASK)


async def test_the_circuit_opens_then_tests_the_provider_again_after_the_cooldown():
    primary = FakeLLM("gemini", script=[bad_key()] * 3 + ["Back again."])
    backup = FakeLLM("groq")
    h = Harness(primary, backup, breaker_threshold=3, breaker_cooldown=30)
    for _ in range(3):
        await h.gateway.generate(ASK)  # three failures in a row: the circuit opens
    assert h.gateway.breakers["gemini"].state == "open"
    await h.gateway.generate(ASK)
    assert primary.calls == 3  # the fourth question never touched the broken provider
    h.now += 31  # the cooldown passes: one test call is allowed
    result = await h.gateway.generate(ASK)
    assert result.provider == "gemini" and h.gateway.breakers["gemini"].state == "closed"


def test_circuit_breaker_states():
    now = [0.0]
    breaker = CircuitBreaker(threshold=2, cooldown=10, clock=lambda: now[0])
    breaker.failure()
    assert breaker.state == "closed" and breaker.allow()
    breaker.failure()
    assert breaker.state == "open" and not breaker.allow()
    now[0] = 11
    assert breaker.state == "half-open" and breaker.allow()
    breaker.failure()  # the test call failed: open again, for a new cooldown
    assert breaker.state == "open"
    now[0] = 22
    breaker.success()
    assert breaker.state == "closed" and breaker.failures == 0


async def test_stream_yields_pieces_and_then_one_result():
    h = Harness(FakeLLM("gemini", script=["Declare it in the path string."]))
    text, result = await collect(h.gateway.stream(ASK, prompt_version="chat_system_v1"))
    assert text.strip() == "Declare it in the path string."
    assert isinstance(result, LLMResult) and result.tokens_out == 6
    assert h.rows[0]["prompt_version"] == "chat_system_v1" and h.rows[0]["status"] == "ok"


async def test_stream_falls_back_if_nothing_was_sent_yet():
    h = Harness(FakeLLM("gemini", script=[busy()]), FakeLLM("groq", script=["From the backup."]))
    text, result = await collect(h.gateway.stream(ASK))
    assert text.strip() == "From the backup." and result.fallback_used


async def test_stream_does_not_switch_models_in_the_middle_of_an_answer():
    primary = FakeLLM("gemini", script=[("partial", busy())])
    backup = FakeLLM("groq")
    h = Harness(primary, backup)
    seen = []
    with pytest.raises(LLMUnavailable, match="mid-answer"):
        async for item in h.gateway.stream(ASK):
            seen.append(item)
    assert "".join(seen).strip() == "Half an answer" and backup.calls == 0


async def test_a_broken_recorder_never_breaks_an_answer():
    async def broken(row: dict) -> None:
        raise RuntimeError("database is down")

    gateway = LLMGateway([FakeLLM(script=["Still answered."])], recorder=broken)
    assert (await gateway.generate(ASK)).text == "Still answered."


def test_cost_uses_the_price_table_and_is_zero_for_unknown_models():
    # 1M tokens in at $0.75 + 1M out at $3.75 = $4.50 = Rs 427.50 at Rs 95
    assert cost_inr("gemini-3.8-flash", 1_000_000, 1_000_000, 95.0) == 427.5
    assert cost_inr("some-new-model", 1000, 1000, 95.0) == 0.0


class NoUsage(FakeLLM):
    """A provider that sends an answer but no token counts."""

    async def generate(self, messages, *, temperature=0.2):
        return Reply("x" * 40)


async def test_missing_token_counts_are_estimated_from_the_text():
    h = Harness(NoUsage("gemini", "gemini-3.8-flash"))
    result = await h.gateway.generate([{"role": "user", "content": "y" * 400}])
    assert (result.tokens_in, result.tokens_out) == (100, 10)  # about 4 characters per token


# ---- the real HTTP provider, against a fake server (httpx.MockTransport) ----
def provider_with(handler) -> OpenAICompatProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAICompatProvider("gemini", "https://llm.test/v1/", "k-123", "m-1", client=client)


async def test_provider_sends_an_openai_style_request_and_reads_the_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"] = str(request.url), request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        reply = {
            "choices": [{"message": {"role": "assistant", "content": "Hello."}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 2},
        }
        return httpx.Response(200, json=reply)

    reply = await provider_with(handler).generate(ASK)
    assert reply == Reply("Hello.", 9, 2)
    assert seen["url"] == "https://llm.test/v1/chat/completions" and seen["auth"] == "Bearer k-123"
    assert seen["body"]["model"] == "m-1" and seen["body"]["messages"] == ASK
    assert "response_format" not in seen["body"]
    await provider_with(handler).generate(ASK, response_format={"type": "json_object"})
    assert seen["body"]["response_format"] == {"type": "json_object"}  # passed on untouched


async def test_provider_turns_http_errors_into_llm_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "7"}, json={"error": "rate limit"})

    with pytest.raises(LLMError) as error:
        await provider_with(handler).generate(ASK)
    assert error.value.retryable and error.value.retry_after == 7.0

    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(LLMError) as error:
        await provider_with(unauthorized).generate(ASK)
    assert not error.value.retryable


async def test_provider_reads_a_server_sent_event_stream():
    def chunk(text: str) -> str:
        return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"

    usage = {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 3}}
    body = chunk("Path ") + chunk("parameters ") + chunk("rock.")
    body += "data: " + json.dumps(usage) + "\n\ndata: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    counted = Reply()
    pieces = [piece async for piece in provider_with(handler).stream(ASK, counted)]
    assert "".join(pieces) == "Path parameters rock."
    assert (counted.tokens_in, counted.tokens_out) == (9, 3)


async def test_a_stream_that_stops_without_saying_done_is_an_error():
    cut_off = 'data: {"choices": [{"delta": {"content": "Half an "}}]}\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=cut_off, headers={"content-type": "text/event-stream"})

    pieces = []
    with pytest.raises(LLMError, match="ended early"):
        async for piece in provider_with(handler).stream(ASK, Reply()):
            pieces.append(piece)
    assert pieces == ["Half an "]  # what arrived was passed on; then the truth was told

    def finished(request: httpx.Request) -> httpx.Response:  # no [DONE], but a finish_reason
        last = '{"choices": [{"delta": {"content": "Done."}, "finish_reason": "stop"}]}'
        return httpx.Response(200, text=f"data: {last}\n\n")

    assert [p async for p in provider_with(finished).stream(ASK, Reply())] == ["Done."]


async def test_a_timeout_moves_on_but_a_dropped_connection_is_worth_one_retry():
    def hangs(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no answer in 30 s")

    def refuses(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMError) as slow:
        await provider_with(hangs).generate(ASK)
    with pytest.raises(LLMError) as dropped:
        await provider_with(refuses).generate(ASK)
    assert not slow.value.retryable and "ReadTimeout" in str(slow.value)
    assert dropped.value.retryable
