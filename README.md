# gary4claude

AI music production skill for Claude Code agents. Chain hosted music models through generation, continuation, editable scores, accompaniment, LoRA automation and local audio assembly. Existing gary4local guidance is also included; this update focuses on remote inference.

## The Cast

| Name | What it does |
|------|-------------|
| **Jerry** | Text-to-audio generation with BPM-aware looping (stable-audio + finetunes) |
| **SA3** | Stable Audio 3 generation, loops, continuation, transform, and independently prompted LoRA automation lanes |
| **Gary** | MusicGen continuation — chain generations to build long tracks |
| **Foundation** | Structured synth/sample generation with randomizable presets |
| **Carey** | ACE-Step text2music, Continue, Complete accompaniment, cover and lego stems with LoRAs |
| **Yuey** | YuE2 generation, audio transcription/remix, editable ABC scores, score or encoded-audio continuation |
| **Terry** | Audio style transfer — transform audio with a text prompt (MelodyFlow) |

## Install

Copy the skill files into your project's `.claude/skills/` directory:

```bash
# From your project root
mkdir -p .claude/skills/gary4claude
curl -sL https://github.com/betweentwomidnights/gary4claude/archive/main.tar.gz | tar xz --strip-components=1 -C .claude/skills/gary4claude
```

Or clone directly:

```bash
git clone https://github.com/betweentwomidnights/gary4claude .claude/skills/gary4claude
```

## Usage

In a Claude Code session:

```
Use the gary4claude skill to make me a 2-minute DnB track with AI vocals.
```

Or get specific:

```
Use the gary4claude skill to make a 2-minute 174bpm DnB track in A minor,
then add a vocal stem with Carey's billie LoRA and mix it over the backing.
```

Agents should build songs sequentially: make one request, wait for the returned audio, save it, then decide the next step. Do not launch parallel generations unless the user explicitly asks for alternate takes.

For example: SA3 eight-bar loop → Yuey transcribe and extend the score → SA3
transform with independent LoRA prompts/curves → Carey lego vocals → local mix.
Yuey also supports encoded-audio continuation when source timbre matters more
than score editing. These are branches to choose, not required stages.

Carey's current API uses `/carey/synth` and `/carey/job` with multipart WAV
uploads/results. **Continue** is `repaint`; **Complete** adds accompaniment at
the source duration. The older `/carey/complete` route still means continuation.
Read `carey.md` before calling either contract.

### Headless gary4local

Install gary4local, build the desired service environments once in its desktop UI,
then close the app. Verify the headless runtime from the skill folder:

```powershell
python scripts/gary4local.py doctor --json
python scripts/gary4local.py ensure jerry --json
python scripts/gary4local.py stop jerry --json
```

See `local.md` for direct localhost routing, process ownership rules, and the
sequential service workflow.

## Skill Files

- `SKILL.md` — Claude Code entrypoint, profile selection, and core workflow
- `gary4claude.md` — Top-level overview, routing, workflows, audio flow between services
- `local.md` — Headless gary4local discovery, start/stop, and localhost routing
- `jerry.md` — stable-audio: text-to-audio, loops, finetune prompts
- `sa3.md` — Stable Audio 3: loops, continuation, transform, per-LoRA prompts and strength automation
- `gary.md` — MusicGen: continuation, retry, transform, model switching
- `foundation.md` — Foundation-1: randomize + generate, BPM handling
- `carey.md` — ACE-Step job API: text2music, Continue, Complete accompaniment, cover, lego and stem assembly
- `yuey.md` — YuE2: transcription/remix, ABC editing, score and encoded-audio continuation
- `terry.md` — MelodyFlow: audio transforms via Gary
- `inference-validation.md` — reference captures and fresh-session chain checks still to audition

## Utility Scripts

The `scripts/` directory contains stdlib-only WAV helpers for agents that should not need to write their own audio glue code:

- `scripts/mix_wavs.py` — mix compatible WAV loops/stems with floating-point headroom and optional final peak normalization
- `scripts/tile_wav.py` — repeat a loop to a target bar count, duration, or reference WAV length
- `scripts/trim_wav.py` — crop by seconds or bars
- `scripts/wav_info.py` — inspect duration, sample rate, channels, and peak
- `scripts/gary_preflight.py` — verify a WAV is long enough for Gary `prompt_duration` and get a tiling recommendation
- `scripts/base64_wav.py` — encode/decode WAV files for API payloads
- `scripts/gary4local.py` — discover and safely start/stop installed localhost services

Example:

```bash
python scripts/gary_preflight.py seed_4bar.wav --prompt-duration 6
python scripts/tile_wav.py drums_4bar.wav drums_8bar.wav --bars 8 --bpm 174
python scripts/mix_wavs.py drums_8bar.wav synth_8bar.wav -o seed.wav --gain 0.8 --gain 0.7 --normalize
python scripts/tile_wav.py seed.wav seed_2min.wav --seconds 120
```

## Hosted API Base URL

All services are hosted at `https://g4l.thecollabagepatch.com`

## License

MIT
