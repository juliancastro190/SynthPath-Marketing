"""Story-sourcing seam: pulls candidate horror stories from Reddit's public
JSON endpoint. Read-only, no app registration or OAuth needed — just a
descriptive User-Agent, which Reddit requires for any non-browser client.
"""

import requests

USER_AGENT = "faceless-youtube-pipeline/0.1 (single-user script)"

DEFAULT_SUBREDDITS = [
    "nosleep",
    "shortscarystories",
    "letsnotmeet",
    "creepyencounters",
    "thetruthishere",
]


class RedditError(Exception):
    """Raised when a story fetch fails. Safe to show the user."""


def fetch_top_stories(subreddit, limit=10, timeframe="week"):
    """Return top self-text posts from `subreddit` as plain dicts, newest
    ranking algorithm aside — stickied posts and link-only posts (no story
    body) are dropped since neither is a usable candidate."""
    url = f"https://www.reddit.com/r/{subreddit}/top/.json"
    try:
        resp = requests.get(
            url,
            params={"limit": limit, "t": timeframe},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RedditError(f"couldn't reach r/{subreddit}: {exc}")

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
