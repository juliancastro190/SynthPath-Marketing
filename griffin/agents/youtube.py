"""YouTube specialist — drives the existing faceless-Reddit-horror
production pipeline (griffin/youtube/pipeline.py) as delegated tasks
instead of a standalone CLI script. Same pipeline, same outputs under
data/youtube/<story-id>/ — this just gives Griffin (and the user, via
Griffin) a way to trigger it from a conversation.
"""

import os

from griffin.agents.base import SpecialistAgent
from griffin.brain.provider import ProviderError
from griffin.tools.registry import Tool, ToolError, ToolRegistry, apply_confirmation_flags
from griffin.youtube import pipeline
from griffin.youtube.assemble import AssembleError
from griffin.youtube.reddit import RedditError
from griffin.youtube.voice import VoiceError

SYSTEM_PROMPT = """You are the YouTube specialist on a small AI team, delegated a task by \
Griffin (the orchestrator) or its user. You drive the faceless-Reddit-\
horror production pipeline: source a story, adapt it into a narration \
script, build a thumbnail prompt, render narration audio, and assemble \
the finished video.

Two tools, same pipeline, different cost:
- youtube_draft — story, script, and thumbnail prompt only. Free, no \
  external spend. Use this by default.
- youtube_produce — the full pipeline, including narration audio rendered \
  via ElevenLabs. This spends real API credits, so it requires the user's \
  explicit yes before it runs — you'll get the outcome back as a tool \
  result either way, so just call it and react rather than asking the \
  user yourself first.

Each tool sources its story one of two ways: from Reddit (default), or, \
if `generate` is true, an original AI-written story instead — pass an \
optional `theme` to steer its premise. Use generate whenever the user asks \
for an original/made-up story, or whenever Reddit sourcing is failing \
(e.g. rate-limited or blocked) and the user is fine with a substitute \
rather than waiting. A generated story also has no rights/permission \
question, unlike retelling someone else's Reddit post.

Prefer youtube_draft unless the task explicitly asks for a finished, \
narrated (or fully assembled) video. Both tools return the actual story/
script/thumbnail-prompt text in the result, not just file paths — include \
that text directly in your reply (don't just point at the file), along \
with which story source was used (subreddit, or "AI-generated") and where \
the output landed on disk."""

_PIPELINE_ERRORS = (RedditError, ProviderError, VoiceError, AssembleError)

# These are the pipeline's small text outputs — worth reading back in full
# so the specialist (and Griffin, and the user) actually sees the story/
# script instead of just a file listing. Anything else (narration.mp3,
# video.mp4) is binary or large, so only its path is reported.
_TEXT_FILES = {"source.txt", "script.txt", "thumbnail_prompt.txt", "video.srt"}
_MAX_INLINE_CHARS = 8000


def _run(tool_input, dry_run):
    subreddits = tool_input.get("subreddits") or None
    background_asset = (tool_input.get("background_asset") or "").strip() or None
    generate = bool(tool_input.get("generate"))
    theme = (tool_input.get("theme") or "").strip() or None
    try:
        out_dir = pipeline.run(
            subreddits=subreddits,
            background_asset=background_asset,
            dry_run=dry_run,
            generate=generate,
            theme=theme,
        )
    except _PIPELINE_ERRORS as exc:
        raise ToolError(f"YouTube pipeline stopped: {exc}")

    if out_dir is None:
        return "No candidate stories found — try different subreddits."

    parts = [f"Produced under {out_dir}:"]
    for name in sorted(os.listdir(out_dir)):
        path = os.path.join(out_dir, name)
        if name not in _TEXT_FILES:
            parts.append(f"- {name} (binary/large — not shown here; open {path} directly)")
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if len(content) > _MAX_INLINE_CHARS:
            content = content[:_MAX_INLINE_CHARS] + "\n[...truncated...]"
        parts.append(f"\n--- {name} ---\n{content}")
    return "\n".join(parts)


def youtube_draft(tool_input):
    return _run(tool_input, dry_run=True)


def youtube_produce(tool_input):
    return _run(tool_input, dry_run=False)


def _describe_produce(tool_input):
    if tool_input.get("generate"):
        theme = (tool_input.get("theme") or "").strip()
        source = f"an AI-generated story ({theme})" if theme else "an AI-generated story"
    else:
        subs = tool_input.get("subreddits")
        source = ", ".join(subs) if subs else "the channel's default subreddits"
    return f"produce a full YouTube video (renders narration audio via ElevenLabs — spends API credits) from {source}"


_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "subreddits": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Subreddits to pull a candidate story from. Ignored if generate is true. Optional — defaults to the channel's standard list.",
        },
        "generate": {
            "type": "boolean",
            "description": "Write an original AI-generated story instead of sourcing one from Reddit.",
        },
        "theme": {
            "type": "string",
            "description": "Premise/theme to steer a generated story. Only used when generate is true.",
        },
        "background_asset": {
            "type": "string",
            "description": "Path to a background video/image loop for final assembly. Optional.",
        },
    },
    "required": [],
}

YOUTUBE_TOOLS = [
    Tool(
        name="youtube_draft",
        description="Source a story and write its narration script + thumbnail prompt. Free — no audio or video rendered.",
        input_schema=_INPUT_SCHEMA,
        handler=youtube_draft,
    ),
    Tool(
        name="youtube_produce",
        description=(
            "Run the full pipeline: story, script, thumbnail prompt, narration audio (ElevenLabs), "
            "and video assembly if a background asset is given. Spends API credits."
        ),
        input_schema=_INPUT_SCHEMA,
        handler=youtube_produce,
        describe=_describe_produce,
    ),
]


def build_youtube_registry(config=None):
    apply_confirmation_flags(YOUTUBE_TOOLS, config)
    registry = ToolRegistry()
    for tool in YOUTUBE_TOOLS:
        registry.register(tool)
    return registry


def build_youtube_agent(config=None):
    return SpecialistAgent(
        name="youtube",
        description=(
            "Sources Reddit stories and produces faceless-horror YouTube videos: script, "
            "thumbnail prompt, narration audio, and assembly."
        ),
        system_prompt=SYSTEM_PROMPT,
        build_registry=build_youtube_registry,
        config=config,
    )
