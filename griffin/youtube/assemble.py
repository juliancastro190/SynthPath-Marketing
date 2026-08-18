"""Assembles narration audio plus a looping background visual into the
finished video via ffmpeg, with rough auto-timed captions burned in.

Requires ffmpeg (and ffprobe, which ships with it) on PATH. Also requires
a background visual — a looping video clip or a still image matching the
"slow-moving or static dark/ambient" visual style from
Marketing/faceless-youtube.md. This module doesn't source that asset for
you; point `background_asset_path` at whatever loop/still you're using.

Caption timing is estimated by distributing the audio's total duration
across caption chunks proportional to character count — not a real
word-level forced alignment. Good enough for burned-in captions on a
narration-driven video; swap in a proper aligner later if drift bothers you.
"""

import shutil
import subprocess
import textwrap


class AssembleError(Exception):
    """Raised when video assembly can't proceed. Safe to show the user."""


def _require_ffmpeg():
    if shutil.which("ffmpeg") is None:
        raise AssembleError(
            "ffmpeg is not installed — it's required to assemble video "
            "(e.g. `brew install ffmpeg` or `apt install ffmpeg`)."
        )
    if shutil.which("ffprobe") is None:
        raise AssembleError("ffprobe is not installed (it ships with ffmpeg).")


def _audio_duration_seconds(audio_path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _format_srt_timestamp(seconds):
    total_ms = int(round(seconds * 1000))
    hours, total_ms = divmod(total_ms, 3600000)
    minutes, total_ms = divmod(total_ms, 60000)
    secs, ms = divmod(total_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_captions_srt(script_text, total_duration, out_path, max_chars=70):
    """Split the script into caption-sized chunks and distribute
    `total_duration` across them by character count, then write an SRT."""
    sentences = [s.strip() for s in script_text.replace("\n", " ").split(". ") if s.strip()]
    chunks = []
    for sentence in sentences:
        chunks.extend(textwrap.wrap(sentence, max_chars) or [sentence])
    if not chunks:
        raise AssembleError("script has no text to caption")

    total_chars = sum(len(chunk) for chunk in chunks)
    cursor = 0.0
    with open(out_path, "w") as f:
        for index, chunk in enumerate(chunks, start=1):
            duration = total_duration * (len(chunk) / total_chars)
            start, end = cursor, cursor + duration
            f.write(
                f"{index}\n"
                f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n"
                f"{chunk}\n\n"
            )
            cursor = end
    return out_path


def assemble_video(narration_audio_path, background_asset_path, script_text, out_path, loop_background=True):
    _require_ffmpeg()
    duration = _audio_duration_seconds(narration_audio_path)

    srt_path = out_path.rsplit(".", 1)[0] + ".srt"
    build_captions_srt(script_text, duration, srt_path)

    cmd = ["ffmpeg", "-y"]
    if loop_background:
        cmd += ["-stream_loop", "-1"]
    cmd += [
        "-i", background_asset_path,
        "-i", narration_audio_path,
        "-filter_complex", f"[0:v]subtitles={srt_path}[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise AssembleError(f"ffmpeg failed: {exc.stderr[-2000:]}")
    return out_path
