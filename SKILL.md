---
name: gary4claude
description: Produce and manipulate music with the hosted Gary APIs or an installed gary4local runtime. Use when the user asks to generate songs, loops, samples, stems, or source material; continue, cover, remix, transcribe, arrange, or transform audio; edit YuE2 scores; use Gary, Jerry, Terry, Carey, SA3, Yuey, or Foundation; or operate gary4local music services headlessly.
---

# Gary4Claude

Create music by orchestrating the Gary service family. Treat each result as a
musical decision point, not as one step in a fixed pipeline.

## Resolve the Skill Directory

The absolute directory containing this skill is `${CLAUDE_SKILL_DIR}`. Use that
absolute path for every bundled script and reference regardless of the current
working directory. Never run `python scripts/...` relative to the user's project.
Whenever a reference uses `<skill-dir>`, replace it with this absolute directory.

## Select the Execution Profile

Choose exactly one profile for the entire run:

- For local, localhost, headless, or gary4local requests, read [local.md](local.md)
  before calling any API. Run
  `python "${CLAUDE_SKILL_DIR}/scripts/gary4local.py" doctor --json` and use only
  direct `127.0.0.1` URLs.
- Otherwise use the hosted profile documented in
  [gary4claude.md](gary4claude.md). Hosted services are already running.

Do not silently fall back from local to hosted. Report a local installation or
service error instead.

## Load the Relevant Guidance

Read [gary4claude.md](gary4claude.md) for shared routing, polling, audio flow, and
song-building guidance. Then read only the service references needed for the next
musical step:

| Service | Read | Primary use |
|---------|------|-------------|
| Jerry | [jerry.md](jerry.md) | Text-to-audio and BPM-aligned source loops |
| SA3 | [sa3.md](sa3.md) | Generation, loops, continuation, transform, LoRA automation lanes and prompts |
| Gary | [gary.md](gary.md) | MusicGen continuation and retry |
| Foundation | [foundation.md](foundation.md) | Structured synth and sample generation |
| Carey | [carey.md](carey.md) | Text2music, Continue, Complete accompaniment, cover, lego stems, LoRAs |
| Yuey | [yuey.md](yuey.md) | YuE2 generation, transcription/remix, editable ABC, score/audio continuation |
| Terry | [terry.md](terry.md) | MelodyFlow audio transformation |

## Run the Session

1. Establish genre, BPM, key/scale, approximate duration, and vocal intent. For a
   full-song request with no explicit duration, target 120 seconds. Ask only when
   the missing choice would materially alter the result; otherwise make a
   reasonable musical choice and state it.
2. Create a session output directory in the user's working project. Save every WAV
   and useful JSON response there with descriptive, ordered names.
3. Submit exactly one heavy generation or transform at a time.
4. Poll asynchronous jobs every 3-5 seconds until completion or failure. Carey
   `/synth` returns `id`; poll `/job`, then fetch and extract multipart audio on
   `done`. Other services generally return base64 audio on completion. Yuey
   `/plan` and `/transcribe` complete with a score, without audio. An id is not
   the finished artifact. Read the service's exact contract.
5. Save and inspect each returned artifact before selecting the next service or
   retry. Use the scripts in `scripts/` for WAV inspection, tiling, trimming,
   mixing, preflight, and base64 conversion.
6. For a finished full-song request, normally perform exactly one final polish
   pass: Carey cover to preserve the arrangement while refining it, or SA3
   transform for same-length restyling/LoRA color. Skip this when the user wants a
   raw/demo result, declines polish, or the latest result already came from a
   deliberate final cover/transform or the requested final lego-vocal mix.
7. Stop when the result satisfies the request. Do not keep chaining model stages
   after the finishing pass merely because they are available.

Carey **Continue** uses `task_type: "repaint"`: `duration` is final total seconds,
including the source. A 32-second seed with `duration: 120` adds about 88 seconds.
Carey **Complete** uses `task_type: "complete"` and adds accompaniment at source
duration. The legacy `/complete` route still means continuation; do not confuse
it with the new task. Discover current models/adapters through `/carey/props`.

Yuey score continuation uses `abc_prefix` and total `target_bars`; encoded-audio
continuation uses `/continue` and added `continuation_bars`. An SA3 result needs
transcription before it has a Yuey score. SA3 lane points use seconds from the
source start; offset continuation lanes by the measured source duration.

For local/headless sessions, ensure the next service immediately before use and
stop it after its response and artifacts have been saved. Run one GPU service at a
time. Never kill arbitrary port owners or all Python processes; use
`scripts/gary4local.py` so only agent-owned processes are stopped.

For an older Python Carey runtime, before starting it locally, run
`python "${CLAUDE_SKILL_DIR}/scripts/gary4local.py" gpu --json`. Use
`--carey-family auto` (the default) unless the user explicitly requests a family;
auto selects the standard family on lower-VRAM GPUs instead of blindly following
an XL desktop setting. Native ace-server instead discovers models through
`/props`. This update focuses on hosted inference; verify installed runtime and
controller support before applying the older local lifecycle recipe to it.

## Boundaries

- Do not mix local and hosted URLs in one run.
- Do not launch parallel alternatives unless the user explicitly requests them.
- Do not overwrite source audio or previously accepted takes.
- Do not attempt LoRA training from this version of the skill. Headless inference
  is supported; training guidance will be added separately after its workflow has
  explicit dataset and safety controls.
- When a requested workflow needs lego stems, preserve the backing and generated
  stem, check alignment/bleed, and mix with headroom. Do not require a manual DAW
  step solely because the agent can perform the audio assembly locally.
