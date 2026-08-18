"""Builds an AI-image-tool prompt for the video's thumbnail, per the style
guide in Marketing/faceless-youtube.md (desaturated, high-contrast, one
accent color, a single unsettling image, no in-image text). This does not
call an image API directly — no specific tool was wired in, so it hands
you a ready-to-paste prompt. Point it at whichever AI image tool you use,
or add a direct API call here once you settle on one.
"""

from griffin.brain import provider

SYSTEM_PROMPT = """You write prompts for an AI image generator, for horror
YouTube thumbnails. Style rules: desaturated, high-contrast, one accent
color, a single unsettling image (not a collage or multiple panels), no
text or lettering in the image (a title card is overlaid separately).
Output ONLY the image prompt, one paragraph, no preamble or quotation marks."""


def build_thumbnail_prompt(title, script_text):
    excerpt = script_text[:600]
    message = provider.run_turn(
        messages=[{"role": "user", "content": f"Video title: {title}\n\nNarration excerpt:\n{excerpt}"}],
        system_prompt=SYSTEM_PROMPT,
    )
    return "\n".join(block.text for block in message.content if block.type == "text").strip()
