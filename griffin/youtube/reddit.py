"""Story-sourcing seam: pulls candidate horror stories from Reddit.

Reddit tightened access to its public JSON endpoints in 2023 and now often
403s unauthenticated requests, even with a descriptive User-Agent — that's
the failure mode this was originally written against and outgrew live. If
REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set (a free "script" app, no
Reddit login used at runtime — see .env.example), this authenticates via
OAuth's client-credentials grant and reads through oauth.reddit.com, which
is what actually still works reliably. Without those set, it falls back to
the old unauthenticated www.reddit.com/*.json endpoint, which may or may
not be blocked depending on Reddit's mood that day.
"""

import time

import requests

from griffin.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET

USER_AGENT = "web:griffin-youtube-pipeline:v0.2 (by /u/griffin-agent)"

DEFAULT_SUBREDDITS = [
    "nosleep",
    "shortscarystories",
    "letsnotmeet",
    "creepyencounters",
    "thetruthishere",
]


class RedditError(Exception):
    """Raised when a story fetch fails. Safe to show the user."""


_token_cache = {"access_token": None, "expires_at": 0.0}


def _get_access_token():
    """Return a cached OAuth token, refreshing it if missing or close to
    expiry. Returns None (not an error) when no app credentials are
    configured, so callers fall back to the unauthenticated endpoint."""
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        return None

    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["access_token"]

    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RedditError(f"couldn't authenticate with Reddit (check REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET): {exc}")

    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def fetch_top_stories(subreddit, limit=10, timeframe="week"):
    """Return top self-text posts from `subreddit` as plain dicts, newest
    ranking algorithm aside — stickied posts and link-only posts (no story
    body) are dropped since neither is a usable candidate."""
    token = _get_access_token()
    base = "https://oauth.reddit.com" if token else "https://www.reddit.com"
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{base}/r/{subreddit}/top/.json"
    try:
        resp = requests.get(url, params={"limit": limit, "t": timeframe}, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        hint = "" if token else " — set REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET in .env, Reddit's unauthenticated endpoint is unreliable (see .env.example)"
        raise RedditError(f"couldn't reach r/{subreddit}: {exc}{hint}")

    stories = []
    for child in resp.json().get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied") or not post.get("selftext"):
            continue
        stories.append(
            {
                "id": post["id"],
                "subreddit": subreddit,
                "title": post["title"],
                "author": post.get("author", "[deleted]"),
                "body": post["selftext"],
                "permalink": f"https://reddit.com{post['permalink']}",
                "score": post.get("score", 0),
            }
        )
    return stories


def fetch_candidates(subreddits=None, limit_per_sub=5, timeframe="week"):
    """Pull candidates across the channel's whole subreddit list, ranked by
    score so the pipeline's default pick is the strongest one available."""
    subreddits = subreddits or DEFAULT_SUBREDDITS
    candidates = []
    for subreddit in subreddits:
        candidates.extend(fetch_top_stories(subreddit, limit=limit_per_sub, timeframe=timeframe))
    candidates.sort(key=lambda story: story["score"], reverse=True)
    return candidates
