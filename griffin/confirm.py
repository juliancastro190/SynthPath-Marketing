"""Shared yes/no parsing for interfaces that confirm consequential actions
via a free-text reply instead of a dedicated widget (voice, Discord).

An unclear answer is always treated as "no" — the confirmation gate's
whole point is that a consequential action never runs on an assumption.
"""

_YES_WORDS = ("yes", "yeah", "yep", "yup", "sure", "confirm", "affirmative", "go ahead", "do it")
_NO_WORDS = ("no", "nope", "don't", "do not", "cancel", "negative", "stop")


def parse_yes_no(text):
    lowered = text.lower()
    if any(word in lowered for word in _NO_WORDS):
        return False
    if any(word in lowered for word in _YES_WORDS):
        return True
    return False  # unclear answer -> safe default: decline, don't guess yes
