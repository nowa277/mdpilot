"""Integration tests for LLM provider with real API calls.

These tests require valid API keys and are marked with @pytest.mark.integration.
Run with: pytest tests/test_llm_integration.py -v -m integration

Set environment variables:
- OPENAI_API_KEY for OpenAI models
- ANTHROPIC_API_KEY for Anthropic models
"""

from __future__ import annotations

import os

import pytest

from mdpilot.llm import LLMProvider


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_openai_call():
    """Test real OpenAI API call (requires OPENAI_API_KEY)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    provider = LLMProvider(
        model="gpt-4o-mini",
        api_key=api_key,
        temperature=0.0,
        max_tokens=100,
    )

    response = await provider.chat_once(
        messages=[{"role": "user", "content": "What is 2+2? Answer with just the number."}]
    )

    assert response.content is not None
    assert "4" in response.content.lower()
    assert response.finish_reason in ["stop", "length"]
    assert response.usage_prompt_tokens > 0
    assert response.usage_completion_tokens > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_anthropic_call():
    """Test real Anthropic API call (requires ANTHROPIC_API_KEY)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    provider = LLMProvider(
        model="claude-sonnet-4-20250514",
        api_key=api_key,
        temperature=0.0,
        max_tokens=100,
    )

    response = await provider.chat_once(
        messages=[{"role": "user", "content": "What is 2+2? Answer with just the number."}]
    )

    assert response.content is not None
    assert "4" in response.content.lower()
    assert response.finish_reason in ["stop", "end_turn", "length"]
    assert response.usage_prompt_tokens > 0
    assert response.usage_completion_tokens > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_streaming_call():
    """Test real streaming API call (requires OPENAI_API_KEY)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    provider = LLMProvider(
        model="gpt-4o-mini",
        api_key=api_key,
        temperature=0.0,
        max_tokens=50,
    )

    result_gen = await provider.chat(
        messages=[{"role": "user", "content": "Count from 1 to 3."}],
        stream=True,
    )

    chunks = []
    async for chunk in result_gen:
        chunks.append(chunk)

    assert len(chunks) > 0
    full_content = "".join(c.content for c in chunks)
    assert len(full_content) > 0
    # Should contain numbers 1, 2, 3
    assert any(str(i) in full_content for i in [1, 2, 3])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_tool_calling():
    """Test real tool calling with OpenAI (requires OPENAI_API_KEY)."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")

    provider = LLMProvider(
        model="gpt-4o-mini",
        api_key=api_key,
        temperature=0.0,
        max_tokens=200,
    )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name",
                        },
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    response = await provider.chat_once(
        messages=[{"role": "user", "content": "What's the weather in Boston?"}],
        tools=tools,
    )

    # Model should call the tool
    assert len(response.tool_calls) > 0
    tool_call = response.tool_calls[0]
    assert tool_call.name == "get_weather"
    assert "location" in tool_call.arguments
    assert "boston" in tool_call.arguments["location"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_error_handling():
    """Test error handling with invalid API key."""
    provider = LLMProvider(
        model="gpt-4o-mini",
        api_key="sk-invalid-key-12345",
        max_retries=0,  # Don't retry on auth errors
    )

    with pytest.raises(Exception) as exc_info:
        await provider.chat_once(
            messages=[{"role": "user", "content": "test"}]
        )

    # Should raise an authentication-related error
    # (litellm.AuthenticationError or similar)
    assert exc_info.value is not None
