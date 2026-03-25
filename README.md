# gary4claude

AI music production skill for Claude Code agents. Gives your agent access to a network of music generation APIs — text-to-audio, MusicGen continuation, structured synthesis, AI vocals, and audio transforms.

## The Cast

| Name | What it does |
|------|-------------|
| **Jerry** | Text-to-audio generation with BPM-aware looping (stable-audio + finetunes) |
| **Gary** | MusicGen continuation — chain generations to build long tracks |
| **Foundation** | Structured synth/sample generation with randomizable presets |
| **Carey** | AI vocals and stems over existing audio (ACE-Step) |
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
Use the jerry skill to generate a 174bpm drum loop, then use the gary skill
to continue it into a 2-minute track, then have carey sing over it.
```

## Skill Files

- `gary4claude.md` — Top-level overview, routing, workflows, audio flow between services
- `jerry.md` — stable-audio: text-to-audio, loops, finetune prompts
- `gary.md` — MusicGen: continuation, retry, transform, model switching
- `foundation.md` — Foundation-1: randomize + generate, BPM handling
- `carey.md` — ACE-Step: lego vocals, complete continuation
- `terry.md` — MelodyFlow: audio transforms via Gary

## API Base URL

All services are hosted at `https://g4l.thecollabagepatch.com`

## License

MIT
