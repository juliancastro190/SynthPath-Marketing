"""Generates an original nosleep-style horror story from scratch, as an
alternative story source to griffin/youtube/reddit.py's Reddit sourcing.
Reuses the same provider seam as script.py/thumbnail.py.

This also sidesteps a real constraint Marketing/faceless-youtube.md calls
out: most nosleep-style stories are another author's owned fiction, and
using one without permission or a substantial rewrite is a rights problem.
An original AI-generated story has no other author to credit or clear —
it's the channel's own fiction from the start.
"""

from griffin.brain import provider

SYSTEM_PROMPT = """You write original horror fiction in the style of r/nosleep and
similar creepypasta communities, for narration on a faceless YouTube channel.

Rules:
- First-person "this really happened to me" account, Reddit-post style, not
  third person.
- Strong hook in the first 2-3 sentences — open close to the unsettling part,
  not slow scene-setting.
- Clear escalating structure and a real ending with payoff. Never trail off
  or end on "and then it just stopped" with nothing resolved.
- Roughly 1500-2500 words — long enough for a 10-20 minute narrated read,
  not so long it drags.
- An original premise. Don't reuse a well-known existing creepypasta's
  premise (Slender Man, the Backrooms, Jeff the Killer, etc.) — write
  something new.

Output format: first line is the title, then a blank line, then the story
body. Nothing else — no "Title:" label, no preamble, no notes."""


def generate_story(theme=None):
    """Return {"title": ..., "body": ...} for a freshly written story. If
    `theme` is given, it steers the premise; otherwise the model picks."""
    user_text = (
        f"Write an original horror story. Theme/premise to build it around: {theme}"
        if theme
        else "Write an original horror story. Pick the premise yourself."
    )
    message = provider.run_turn(
        messages=[{"role": "user", "content": user_text}],
        system_prompt=SYSTEM_PROMPT,
    )
    text = "\n".join(block.text for block in message.content if block.type == "text").strip()
    title, _, body = text.partition("\n\n")
    return {"title": title.strip(), "body": (body or text).strip()}
