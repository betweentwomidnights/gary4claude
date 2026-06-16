# gary4claude

AI music production skill for Claude Code agents. Gives your agent access to a network of music generation APIs — text-to-audio, MusicGen continuation, structured synthesis, ACE-Step cover/continuation, LoRA style injection, and audio transforms.

## The Cast

| Name | What it does |
|------|-------------|
| **Jerry** | Text-to-audio generation with BPM-aware looping (stable-audio + finetunes) |
| **SA3** | Stable Audio 3 generation, loops, continuation, transform, and blendable LoRAs |
| **Gary** | MusicGen continuation — chain generations to build long tracks |
| **Foundation** | Structured synth/sample generation with randomizable presets |
| **Carey** | ACE-Step cover/continuation with LoRA captions; optional stem generation |
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
then use Carey's billie LoRA adapter with cover/complete.
```

Agents should build songs sequentially: make one request, wait for the returned audio, save it, then decide the next step. Do not launch parallel generations unless the user explicitly asks for alternate takes.

## Skill Files

- `gary4claude.md` — Top-level overview, routing, workflows, audio flow between services
- `jerry.md` — stable-audio: text-to-audio, loops, finetune prompts
- `sa3.md` — Stable Audio 3: loops, continuation, transform, LoRA blending
- `gary.md` — MusicGen: continuation, retry, transform, model switching
- `foundation.md` — Foundation-1: randomize + generate, BPM handling
- `carey.md` — ACE-Step: cover, complete continuation, LoRAs, captions, optional lego stems
- `terry.md` — MelodyFlow: audio transforms via Gary

## Utility Scripts

The `scripts/` directory contains stdlib-only WAV helpers for agents that should not need to write their own audio glue code:

- `scripts/mix_wavs.py` — mix compatible WAV loops/stems
- `scripts/tile_wav.py` — repeat a loop to a target bar count, duration, or reference WAV length
- `scripts/trim_wav.py` — crop by seconds or bars
- `scripts/wav_info.py` — inspect duration, sample rate, channels, and peak
- `scripts/gary_preflight.py` — verify a WAV is long enough for Gary `prompt_duration` and get a tiling recommendation
- `scripts/base64_wav.py` — encode/decode WAV files for API payloads

Example:

```bash
python scripts/gary_preflight.py seed_4bar.wav --prompt-duration 6
python scripts/tile_wav.py drums_4bar.wav drums_8bar.wav --bars 8 --bpm 174
python scripts/mix_wavs.py drums_8bar.wav synth_8bar.wav -o seed.wav --gain 0.8 --gain 0.7 --normalize
python scripts/tile_wav.py seed.wav seed_2min.wav --seconds 120
```

## API Base URL

All services are hosted at `https://g4l.thecollabagepatch.com`

## License

MIT
