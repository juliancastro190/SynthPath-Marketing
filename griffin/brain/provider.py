"""The provider seam: the only place that talks to the model SDK directly.

Everything else in the harness calls `stream_reply` and never touches the
Anthropic client. This is what lets the model/provider change, retries get
added, or costs get logged in one place later.
"""

import anthropic

from griffin.config import ANTHROPIC_API_KEY, MODEL_NAME

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
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def stream_reply(messages, system_prompt):
    """Send a conversation to the model and yield reply text as it streams in.

    `messages` is a list of {"role": "user"|"assistant", "content": str}.
    Raises ProviderError on any failure — callers don't need to know about
    the underlying SDK's exception types.
    """
    client = _get_client()
    try:
        with client.messages.stream(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
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
