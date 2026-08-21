"""Publisher specialist — takes a video the youtube specialist already
produced and actually posts it: uploads it to YouTube via the YouTube
Data API v3 (griffin/youtube/upload.py). Deliberately a separate
specialist from youtube itself: producing content and putting it live in
public are different levels of consequence, and keeping them apart means
a task that only asks for a script or a draft video never touches the
publish path by accident — the publisher only ever acts on a story_id
that already exists on disk, it never produces one itself.

publish_youtube_video is confirmation-gated (config.yaml's
requires_confirmation) — publishing to a real channel, visible to
whoever's watching it, is exactly the "never without asking" case
send_email and youtube_produce already established. On top of that gate,
it also defaults to privacyStatus "private" unless told otherwise, as a
second layer of safety: even an approved publish lands somewhere you can
review before making it public yourself.
"""

import os

from griffin.agents.base import SpecialistAgent
from griffin.storage import DATA_DIR
from griffin.tools.registry import Tool, ToolError, ToolRegistry, apply_confirmation_flags
from griffin.youtube.upload import UploadError, upload_video

YOUTUBE_OUTPUT_ROOT = os.path.join(DATA_DIR, "youtube")

SYSTEM_PROMPT = """You are the publisher specialist on a small AI team, delegated a task by \
Griffin (the orchestrator) or its user. Your one tool, publish_youtube_video, \
uploads an already-produced video to YouTube — you don't produce content \
yourself, that's the youtube specialist's job (youtube_produce). You need a \
story_id: the data/youtube/<id> folder youtube_produce reported when it ran. \
If you weren't given one, ask for it rather than guessing.

Every upload defaults to privacyStatus "private" unless the task explicitly \
asks for "unlisted" or "public" — leave it private unless told otherwise, so \
whoever's asking can review it on YouTube before it's visible to anyone else. \
Report back the video's URL, the title used, and the privacy status."""

_PRIVACY_STATUSES = ("private", "unlisted", "public")


def _story_dir(story_id):
    story_id = (story_id or "").strip()
    if not story_id:
        raise ToolError("Needs a story_id — the data/youtube/<id> folder youtube_produce reported.")
    story_dir = os.path.join(YOUTUBE_OUTPUT_ROOT, story_id)
    if not os.path.isdir(story_dir):
        raise ToolError(f"No such story: '{story_id}'. Check data/youtube/ or the id youtube_produce reported.")
    return story_dir


def _read_text(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def publish_youtube_video(tool_input):
    story_dir = _story_dir(tool_input.get("story_id"))
    video_path = os.path.join(story_dir, "video.mp4")
    if not os.path.exists(video_path):
        raise ToolError(
            f"No video.mp4 under {story_dir} — youtube_produce needs a background_asset to assemble "
            "a finished video before there's anything here to publish."
        )

    source_text = _read_text(os.path.join(story_dir, "source.txt"))
    default_title = source_text.splitlines()[0].strip() if source_text else "Untitled"
    title = (tool_input.get("title") or "").strip() or default_title

    script_text = _read_text(os.path.join(story_dir, "script.txt"))
    excerpt = script_text[:1500] + ("..." if len(script_text) > 1500 else "") if script_text else ""
    default_description = (excerpt + "\n\n" if excerpt else "") + "Narrated with AI voice synthesis."
    description = (tool_input.get("description") or "").strip() or default_description

    privacy_status = (tool_input.get("privacy_status") or "private").strip().lower()
    if privacy_status not in _PRIVACY_STATUSES:
        raise ToolError(f"privacy_status must be one of {', '.join(_PRIVACY_STATUSES)}.")

    tags = tool_input.get("tags") or None

    try:
        url = upload_video(video_path, title, description, privacy_status=privacy_status, tags=tags)
    except UploadError as exc:
        raise ToolError(str(exc))

    return f"Published to YouTube ({privacy_status}): {url}\nTitle: {title}"


def _describe_publish(tool_input):
    story_id = (tool_input.get("story_id") or "").strip()
    privacy_status = (tool_input.get("privacy_status") or "private").strip().lower()
    title = (tool_input.get("title") or "").strip()
    title_note = f' (title: "{title}")' if title else ""
    return f"upload the video from story '{story_id}' to YouTube as {privacy_status}{title_note}"


PUBLISHER_TOOLS = [
    Tool(
        name="publish_youtube_video",
        description=(
            "Upload an already-produced video (see the youtube specialist's youtube_produce) to "
            "YouTube. Needs a story_id (the data/youtube/<id> folder). Defaults to a private "
            "upload unless told otherwise."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "story_id": {"type": "string", "description": "The data/youtube/<id> folder from youtube_produce."},
                "title": {"type": "string", "description": "Optional title override. Defaults to the story's title."},
                "description": {
                    "type": "string",
                    "description": "Optional description override. Defaults to an excerpt of the script.",
                },
                "privacy_status": {
                    "type": "string",
                    "enum": list(_PRIVACY_STATUSES),
                    "description": "Defaults to 'private' if not given.",
                },
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional video tags."},
            },
            "required": ["story_id"],
        },
        handler=publish_youtube_video,
        describe=_describe_publish,
    ),
]


def build_publisher_registry(config=None):
    apply_confirmation_flags(PUBLISHER_TOOLS, config)
    registry = ToolRegistry()
    for tool in PUBLISHER_TOOLS:
        registry.register(tool)
    return registry


def build_publisher_agent(config=None):
    return SpecialistAgent(
        name="publisher",
        description=(
            "Uploads an already-produced YouTube video (from the youtube specialist) to YouTube, "
            "defaulting to a private upload you can review before making it public."
        ),
        system_prompt=SYSTEM_PROMPT,
        build_registry=build_publisher_registry,
        config=config,
    )
