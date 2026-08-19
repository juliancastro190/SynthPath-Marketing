"""The provider seam: the only place that talks to the model SDK directly.

Everything else in the harness calls `run_turn` and never touches the
Anthropic client. This is what lets the model/provider change, retries get
added, or costs get logged in one place later.
"""

import anthropic

from griffin.config import ANTHROPIC_API_KEY, HELICONE_API_KEY, HELICONE_BASE_URL, MODEL_NAME

MAX_TOKENS = 1024

_client = None


class ProviderError(Exception):
    """Raised when the model can't be reached or refuses the request.

    Carries a plain-language message safe to show directly to the user.
    """


def _get_client():
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise ProviderError(
                "No ANTHROPIC_API_KEY is set. Copy .env.example to .env and add your key."
            )
        kwargs = {"api_key": ANTHROPIC_API_KEY}
        if HELICONE_API_KEY:
            # Proxy through Helicone instead of hitting Anthropic directly —
            # every request/response (including tool calls) then shows up
            # as a live trace in Helicone's dashboard. Anthropic still gets
            # the request either way; Helicone just sits in front of it.
            kwargs["base_url"] = HELICONE_BASE_URL
            kwargs["default_headers"] = {"Helicone-Auth": f"Bearer {HELICONE_API_KEY}"}
        _client = anthropic.Anthropic(**kwargs)
    return _client


def run_turn(messages, system_prompt, tools=None, on_text=None):
    """Run one model turn to completion and return the final Message.

    `messages` is a list of {"role": "user"|"assistant", "content": ...}.
    Text is streamed as it arrives via `on_text(chunk)` if given, so a caller
    can print or speak it live — this is what Tier 3's voice output will
    hook into as well. Tool-use input isn't streamed; it only matters once
    it's complete, which is on the returned Message's content blocks.

    Raises ProviderError on any failure — callers don't need to know about
    the underlying SDK's exception types.
    """
    client = _get_client()
    kwargs = dict(model=MODEL_NAME, max_tokens=MAX_TOKENS, system=system_prompt, messages=messages)
    if tools:
        kwargs["tools"] = tools
    try:
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                if on_text:
                    on_text(text)
            return stream.get_final_message()
    except anthropic.AuthenticationError:
        raise ProviderError("Authentication failed — check your ANTHROPIC_API_KEY.")
    except anthropic.APIConnectionError:
        raise ProviderError("Couldn't reach the model — check your connection and try again.")
    except anthropic.RateLimitError:
        raise ProviderError("The model is rate-limiting us — wait a moment and try again.")
    except anthropic.APIStatusError as exc:
        raise ProviderError(f"The model provider returned an error ({exc.status_code}).")
    except anthropic.APIError as exc:
        raise ProviderError(f"Something went wrong talking to the model: {exc}")


def serialize_content_blocks(blocks):
    """Convert SDK response content blocks into plain dicts so they can be
    fed back into the next call's `messages` list."""
    serialized = []
    for block in blocks:
        if block.type == "text":
            serialized.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            serialized.append(
                {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
            )
        else:
            serialized.append(block.model_dump())
    return serialized
