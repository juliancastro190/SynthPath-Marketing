# Faceless YouTube: Reddit Horror Stories

**What this is:** the operating runbook for running a faceless Reddit-horror YouTube channel end to end — no camera, no host, just narration over visuals. This is written TO the AI assistant running the channel: read it before every production cycle, and treat it as the loop you execute, not background reading. (For the underlying content principles this pipeline is built on, see [[marketing-content]]. For how to read the channel's numbers, see [[marketing-analytics]]. For the always-read-first principles, see [[jareds-takes]].)

## Run it

The pipeline below is implemented, not just described: `python3 -m griffin.main` (run from the repo root) runs source → script → thumbnail-prompt → narration → video assembly end to end. `--dry-run` stops after the script and thumbnail prompt (no ElevenLabs or ffmpeg needed). `--background <path>` points at the visual loop/still to assemble the video against; without it, the run stops after narration audio. Needs `ANTHROPIC_API_KEY` and `ELEVENLABS_API_KEY` in `.env`, and `ffmpeg` on PATH for assembly. If story fetching fails with a 403 from reddit.com (increasingly common for unauthenticated requests), set `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `.env` — a free "script" app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps), no approval needed — and the pipeline fetches via OAuth instead. If reddit.com is unreachable at all (a network-level block, not just Reddit's own 403), skip the fetch entirely with `--story-file <path>`: a `.txt` file with the title on the first line, a blank line, then the story body — copy-paste a story you read on your phone or another device. Outputs land in `data/youtube/<story-id>/`. Code lives in `griffin/youtube/` (`reddit.py`, `script.py`, `voice.py`, `thumbnail.py`, `assemble.py`, `pipeline.py`).

## The channel in one line

Narrated Reddit horror stories (r/nosleep, r/letsnotmeet, r/shortscarystories, r/creepyencounters, r/thetruthishere, and similar) over dark ambient visuals, built for people who fall asleep or work with horror narration playing in the background. Faceless means the production is entirely: source story → script → voice → visuals → edit → thumbnail → title → upload. No stage needs a human face or on-camera talent, which means every stage is a task an assistant can actually own.

## Stack

- **Voice:** ElevenLabs (already wired into this repo — see `voice_main.py`, `.env.example` for `ELEVENLABS_VOICE_ID`). Pick one consistent voice and stick with it; the voice IS the channel's face. A darker, calmer, slightly gravelly premade voice reads better for horror than a bright default.
- **Visuals/assembly:** script-based, via FFmpeg (or Remotion if the edit needs programmatic scenes/text overlays, not just a static/looping backdrop cut to audio). Because it's scripted, the whole visual+edit stage should be a repeatable pipeline, not manual per-video editing.
- **Thumbnails:** AI image tool, prompt-driven. One consistent visual style (same color grade, same title-card treatment) across every thumbnail so the channel is recognizable at a glance in a feed of other horror channels.

## The production loop

Run this per video, start to finish. Every stage has one job — don't let stages bleed into each other (e.g. don't pick a story because it has a good thumbnail-able image; pick it because the story is good, then make the thumbnail work for it).

### 1. Source and vet the story

- Pull candidates from the subreddits above (or other nosleep-style horror-fiction communities). Prioritize: strong hook in the first 2-3 sentences, a clear escalating structure, a real ending (not "and then it just stopped" with no payoff), and length that fits a single video (long enough to hold a listener, not so long it drags — a 10-20 minute narrated read is a solid default; longer "compilation" videos can bundle 3-5 shorter stories).
- **Never post a story verbatim without permission or clear reuse terms.** Most nosleep-style stories are original fiction owned by the author. Either: get explicit permission and credit the author and subreddit in the video description, or rewrite the story substantially (different wording, restructured scenes, same core premise) so it's a transformative retelling, not a copy. When in doubt, don't use it — there are always more stories.
- Keep a running log of story sources used (title, author/subreddit, permission status) so nothing gets reused or re-claimed by accident.

### 2. Adapt into a script

- Rewrite for the ear, not the eye. Reddit text leans on formatting (bullet points, edits, "TL;DR") that doesn't survive narration — convert it into a spoken narrative with a clear beginning, rising tension, and a clean ending line.
- Front-load the hook. The first 15 seconds decide whether someone stays; open on the creepiest or most disorienting line in the story, not scene-setting throat-clearing.
- Write in short, readable-aloud sentences. ElevenLabs (like any TTS) reads short declarative sentences with better pacing and natural pauses than long compound ones — this is a narration script, not a short story manuscript.
- Mark pacing cues in the script draft (paragraph breaks = breath/pause points) so the TTS output has room to breathe during tense moments instead of racing through them.

### 3. Generate voice (ElevenLabs)

- Same voice ID every video — consistency is the whole point of a faceless channel's identity.
- Generate in chunks that respect natural scene breaks, not one giant blob, so a bad line can be regenerated without re-rendering the whole narration.
- Listen back for mispronunciations or flat delivery on the story's key turns (the reveal, the climax) — those are worth a regenerate even if the rest is fine.

### 4. Build the visuals and assemble (FFmpeg/Remotion)

- Visual track: slow-moving or static dark/ambient backgrounds (fog, empty hallways, forests at night, analog-horror-style textures) that don't compete with the narration for attention. Avoid fast cuts or busy visuals — the audio is the content; the visual is a mood, not a second story.
- Sync: build the assembly pipeline so a finished voice track + a visual asset + optional caption track render into a finished video from a script, not by hand-editing in a GUI each time. That's what makes this a channel an assistant can run at volume instead of a one-off video.
- Captions: burn in captions (auto-generated from the ElevenLabs script/audio, cleaned up for accuracy). A meaningful share of horror-narration viewers watch muted or half-attention; captions keep them.
- Keep a simple template (intro card → story → outro card with a CTA) so every video has the same shape and the pipeline stays scriptable end to end.

### 5. Thumbnail (AI image tool)

- One consistent visual identity: same font/title-card treatment, same color grade (desaturated, high-contrast, a single accent color works well for horror), same rough composition (a single unsettling image, not a cluttered collage).
- The thumbnail's job is the same as any lead magnet's headline: promise the specific unsettling thing the story delivers, don't oversell past what's actually in the video. A thumbnail that overpromises tanks retention even if it wins the click.
- Generate a few variants per video and pick by "does this stop a thumb mid-scroll," not by which one you personally like best.

### 6. Title and description

- Title carries the hook: name the specific creepy premise ("The neighbor who mowed his lawn at 3am," not "A Scary Story About My Neighbor"). Specific beats vague every time, same rule as copy anywhere else (see [[marketing-copywriting]]).
- Description: 2-3 sentences restating the hook, then credit (original author/subreddit if applicable), then the channel's CTA (subscribe, or a link if the channel ever builds a funnel off of it — see [[the-fundamentals]] if that's ever a goal beyond ad revenue).
- Tags/keywords: story themes (e.g. "true horror story," "reddit horror," "scary story to fall asleep to") — write for what a real viewer would type into search, not for stuffing.

### 7. Upload and schedule

- Consistency beats volume. Pick a cadence the pipeline can actually sustain (e.g. 2-3x/week) and hold it — YouTube's own recommender rewards a channel it can predict.
- Upload at a time that matches when horror-narration viewers actually watch: evenings and late night in the channel's primary audience timezone tend to outperform mid-day.

## What to measure

Same philosophy as [[marketing-analytics]]: a few numbers, read in context, turned into a decision — not a dashboard you stare at.

- **Average view duration / retention curve** is the primary number for this format, more than views themselves. A steep early drop-off means the hook (or the first 15 seconds of the read) isn't working — fix the next script's opening, don't just make more videos and hope.
- **Click-through rate (impressions → views)** tells you if the thumbnail+title combo is doing its job. Low CTR with decent retention on the videos that DO get clicked means the packaging is the problem, not the content.
- **Watch time** (not just view count) is what YouTube's algorithm actually optimizes distribution around — a slightly shorter video that's watched to 80% beats a longer one watched to 20%.
- Set thresholds ahead of time (e.g. "below 40% average retention = rework the next 3 scripts' openings") so the numbers make the call instead of you re-litigating it every time.

## The one rule

Every video is: one good story, vetted for rights, adapted for the ear, one consistent voice, one consistent visual identity, a title and thumbnail that promise exactly what the video delivers. Do that on a repeatable pipeline and a faceless channel scales the same way content scales anywhere else — the front door just happens to be narrated horror instead of a lead magnet.
