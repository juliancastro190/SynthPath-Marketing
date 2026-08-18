"""Story-sourcing seam: pulls candidate horror stories from Reddit.

Reddit's public `.json` endpoints (no auth needed) increasingly return a
flat 403 for unauthenticated requests, regardless of User-Agent — a policy
tightening on Reddit's side, not something fixable by request-shaping. If
REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET are set, this fetches via OAuth
instead (a free "script" app at https://www.reddit.com/prefs/apps —
no approval process, just a Reddit account), which Reddit does not block.
Falls back to the public endpoint if no app credentials are configured.
"""

import requests

from griffin.config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET

USER_AGENT = "faceless-youtube-pipeline/0.1 (single-user script)"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
PUBLIC_BASE_URL = "https://www.reddit.com"
OAUTH_BASE_URL = "https://oauth.reddit.com"

DEFAULT_SUBREDDITS = [
    "nosleep",
    "shortscarystories",
    "letsnotmeet",
    "creepyencounters",
    "thetruthishere",
]

_token = None


class RedditError(Exception):
    """Raised when a story fetch fails. Safe to show the user."""


def _get_oauth_token():
    global _token
    if _token is None:
        try:
            resp = requests.post(
                TOKEN_URL,
                auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            resp.raise_for_status()
            _token = resp.json()["access_token"]
        except requests.RequestException as exc:
            raise RedditError(f"couldn't authenticate with Reddit: {exc}")
    return _token


def _request_listing(subreddit, limit, timeframe):
    use_oauth = bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)
    if use_oauth:
        url = f"{OAUTH_BASE_URL}/r/{subreddit}/top"
        headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {_get_oauth_token()}"}
    else:
        url = f"{PUBLIC_BASE_URL}/r/{subreddit}/top/.json"
        headers = {"User-Agent": USER_AGENT}

    try:
        resp = requests.get(url, params={"limit": limit, "t": timeframe}, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        hint = (
            "" if use_oauth else
            " — reddit.com is blocking unauthenticated requests for many IPs now; "
            "set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env to fetch via OAuth instead "
            "(free 'script' app: https://www.reddit.com/prefs/apps)"
        )
        raise RedditError(f"couldn't reach r/{subreddit}: {exc}{hint}")


def fetch_top_stories(subreddit, limit=10, timeframe="week"):
    """Return top self-text posts from `subreddit` as plain dicts. Stickied
    posts and link-only posts (no story body) are dropped since neither is
    a usable candidate."""
    data = _request_listing(subreddit, limit, timeframe)

    stories = []
    for child in data.get("data", {}).get("children", []):
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
