"""End-to-end faceless-YouTube production pipeline: source a story, adapt
it into a narration script, render narration audio, build a thumbnail
prompt, and — given a background visual — assemble the finished video.
Run it with `python3 youtube_main.py`, not this module directly.

Outputs land under data/youtube/<story-id>/ (git-ignored, same convention
as everything else in data/): source.txt, script.txt,
thumbnail_prompt.txt, narration.mp3, and video.mp4 + video.srt if a
background asset was given.
"""

import argparse
import os
import uuid

from griffin.brain.provider import ProviderError
from griffin.storage import DATA_DIR
from griffin.youtube import reddit, script as script_mod, story as story_mod, thumbnail, voice
from griffin.youtube.assemble import AssembleError, assemble_video
from griffin.youtube.reddit import RedditError
from griffin.youtube.voice import VoiceError

OUTPUT_ROOT = os.path.join(DATA_DIR, "youtube")


def run(subreddits=None, background_asset=None, dry_run=False, generate=False, theme=None):
    """`generate=True` writes an original story (story.py) instead of
    sourcing one from Reddit — same downstream script/thumbnail/voice/
    assembly pipeline either way, just a different story source."""
    if generate:
        print("Generating an original story...")
        generated = story_mod.generate_story(theme=theme)
        story = {
            "id": uuid.uuid4().hex[:8],
            "subreddit": None,
            "title": generated["title"],
            "author": None,
            "permalink": None,
            "body": generated["body"],
            "score": None,
        }
        print(f"Generated: {story['title']!r}")
    else:
        print("Fetching candidate stories...")
        candidates = reddit.fetch_candidates(subreddits=subreddits)
        if not candidates:
            print("No candidates found — try different subreddits or a longer timeframe.")
            return None

        story = candidates[0]
        print(f"Picked: r/{story['subreddit']} — {story['title']!r} (score {story['score']})")

    out_dir = os.path.join(OUTPUT_ROOT, story["id"])
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "source.txt"), "w", encoding="utf-8") as f:
        if story["subreddit"]:
            f.write(f"{story['title']}\n{story['permalink']}\nby u/{story['author']}\n\n{story['body']}")
        else:
            f.write(f"{story['title']}\n(AI-generated original story — not sourced from Reddit)\n\n{story['body']}")

    print("Adapting into a narration script...")
    narration_script = script_mod.adapt_story(story["title"], story["body"])
    script_path = os.path.join(out_dir, "script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(narration_script)
    print(f"Script written to {script_path}")

    print("Building thumbnail prompt...")
    prompt = thumbnail.build_thumbnail_prompt(story["title"], narration_script)
    with open(os.path.join(out_dir, "thumbnail_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(prompt)
    print("Thumbnail prompt saved — paste it into your AI image tool.")

    if dry_run:
        print("Dry run: skipping narration audio and video assembly.")
        return out_dir

    print("Rendering narration audio (ElevenLabs)...")
    audio_path = os.path.join(out_dir, "narration.mp3")
    voice.render_narration(narration_script, audio_path)
    print(f"Narration audio written to {audio_path}")

    if background_asset:
        print("Assembling video (ffmpeg)...")
        video_path = os.path.join(out_dir, "video.mp4")
        try:
            assemble_video(audio_path, background_asset, narration_script, video_path)
            print(f"Video written to {video_path}")
        except AssembleError as exc:
            print(f"[video assembly skipped: {exc}]")
    else:
        print("No --background given — skipping video assembly.")
        print("Run again with --background <path to your visual loop/still> to finish the video.")

    return out_dir


def main():
    parser = argparse.ArgumentParser(description="Faceless-YouTube production pipeline")
    parser.add_argument(
        "--subreddit", action="append", dest="subreddits",
        help="Subreddit to pull from (repeatable). Defaults to the channel's standard list.",
    )
    parser.add_argument("--background", help="Path to a background video/image loop for assembly.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only fetch + script + thumbnail prompt — skip narration audio and video (no ElevenLabs/ffmpeg needed).",
    )
    parser.add_argument(
        "--generate", action="store_true",
        help="Write an original story instead of sourcing one from Reddit.",
    )
    parser.add_argument("--theme", help="Premise/theme to steer a --generate story. Ignored without --generate.")
    args = parser.parse_args()
    try:
        run(
            subreddits=args.subreddits,
            background_asset=args.background,
            dry_run=args.dry_run,
            generate=args.generate,
            theme=args.theme,
        )
    except (RedditError, ProviderError, VoiceError, AssembleError) as exc:
        print(f"\n[pipeline stopped: {exc}]")


if __name__ == "__main__":
    main()
