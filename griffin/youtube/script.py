"""Adapts a sourced Reddit story into a narration script, per the rules in
Marketing/faceless-youtube.md: hook first, short spoken sentences, Reddit
formatting rewritten into a spoken narrative, paragraph breaks as pause
points. Reuses the same provider seam Griffin's conversation loop calls.
"""

from griffin.brain import provider

SYSTEM_PROMPT = """You adapt Reddit horror stories into narration scripts for a
faceless YouTube channel. Rules:
- Open on the creepiest or most disorienting line in the story, not scene-setting.
- Write in short, readable-aloud sentences — this is narration, not prose meant to be read on a page.
- Restructure Reddit-isms (bullet points, "TL;DR", edits) into a spoken narrative.
- Keep a clear beginning, rising tension, and a clean ending line.
- Put a blank line between paragraphs — those breaks are breath/pause points for the narrator.
- Output ONLY the narration script text. No title, no preamble, no notes."""


def adapt_story(title, body):
    message = provider.run_turn(
        messages=[{"role": "user", "content": f"Title: {title}\n\nStory:\n{body}"}],
        system_prompt=SYSTEM_PROMPT,
    )
    return "\n".join(block.text for block in message.content if block.type == "text").strip()
