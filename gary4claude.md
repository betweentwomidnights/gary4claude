# gary4claude — AI Music Production Skill

You have access to a network of AI music generation services at `https://g4l.thecollabagepatch.com`. Each service has a character name and a specialty. This skill lets you generate, continue, transform, and combine AI music by calling their REST APIs.

## The Cast

| Name | Service | What it does |
|------|---------|-------------|
| **Jerry** | stable-audio | Text-to-audio. Generates drums, loops, textures from a prompt. BPM-aware looping. |
| **Gary** | g4lwebsockets | MusicGen continuation. Takes audio + extends it with a chosen finetune model. Chain multiple continuations to build long tracks. |
| **Foundation** | foundation | Structured synth/sample generation. Randomizable presets with fine-grained timbre control. BPM-locked, time-stretched to host tempo. |
| **Carey** | ace-step | Cover and complete modes for ACE-Step restyling, continuation, named LoRA adapter selection, and optional stem workflows. |
| **Terry** | melodyflow | Audio style transfer. Transforms existing audio with a text prompt (e.g., "8bit", "orchestral"). Accessed through Gary's transform endpoint. |

## Base URL

All requests go through: `https://g4l.thecollabagepatch.com`

| Path prefix | Routes to |
|------------|-----------|
| `/audio/*` | Jerry (stable-audio) |
| `/carey/*` | Carey (ace-step wrapper) |
| `/foundation/*` | Foundation |
| `/api/juce/*` | Gary (g4lwebsockets REST) |
| (no prefix) | Gary (default route) |

## Universal Polling Pattern

Jerry is synchronous (returns audio immediately). All other services are async:

1. **Submit** a generation request → get back `session_id` (or `task_id` for Carey)
2. **Poll** the status endpoint every 3-5 seconds
3. When `status` is `"completed"`, the response includes `audio_data` (base64 WAV)
4. Use that returned `audio_data` as the input to the next step

```bash
# Generic poll loop — works for Gary, Foundation, and Carey
while true; do
  RESP=$(curl -s "$POLL_URL")
  STATUS=$(echo "$RESP" | jq -r '.status // .generation_in_progress')

  # Check for completion
  if echo "$RESP" | jq -e '.audio_data // empty' > /dev/null 2>&1; then
    echo "$RESP" | jq -r '.audio_data' | base64 -d > output.wav
    break
  fi

  # Check for failure
  if echo "$RESP" | jq -e '.error // empty' > /dev/null 2>&1; then
    echo "FAILED: $(echo "$RESP" | jq -r '.error')"
    break
  fi

  sleep 4
done
```

Do not submit follow-up generation requests until the previous async job has completed or failed. A `task_id`/`session_id` means the job is queued or running; it is not the audio result. Agents should wait, poll, and reuse the returned `audio_data`.

## One Request at a Time

For autonomous song-building, make exactly one generation/transform request at a time. This is not a fixed recipe; it is a branching workflow. The next decision depends on the audio that comes back from the previous step.

At each step, inspect what you have and choose one next move:

| If you have... | Good next moves |
|----------------|-----------------|
| No audio yet | Make a Jerry loop, or make a Foundation preset/generation |
| A short drum/percussion loop | Continue with Gary, mix with Foundation, or tile it to match another loop |
| A short synth/bass/pad loop | Mix with Jerry drums, continue with Gary, or send to Carey complete |
| A mixed 4- or 8-bar seed | Tile it, continue with Gary, transform a short version with Terry, or send to Carey complete |
| A useful 30-second section | Continue with Gary, complete with Carey, or cover with Carey |
| A full song or long section | Cover with Carey, complete/extend with Carey, or stop |
| A Carey complete result with lyrics | Reuse the exact same lyrics if you later use Carey cover |

Example paths:

```
Foundation randomize -> Foundation generate -> Carey complete with lyrics -> stop
Jerry drum loop -> Foundation synth loop -> mix -> tile -> Carey cover with a named LoRA adapter
Jerry loop -> Gary continue -> Terry transform 30-second section -> Carey complete
Foundation bass loop -> Gary continue -> Carey cover -> Carey complete
```

Do not start Carey while Gary is still generating. Do not start Terry while Foundation is still generating. Do not submit three alternate covers while deciding what to do next. The agent should make a plan, execute one step, inspect/save the returned audio artifact, then choose the next branch.

Terry/MelodyFlow note: Terry transforms a short section, commonly around 30 seconds. It is usually best before final full-song completion, or when you intentionally want to transform only an excerpt. If you send Terry a completed two-minute Carey song, the result may only represent the first short section rather than the whole song.

## Audio Flow Between Services

All audio is exchanged as **base64-encoded WAV**. The `audio_data` field from one service's output plugs directly into another service's `audio_data` input.

```
Jerry output.audio → Gary input.audio_data (continue it)
Foundation output.audio_data → Gary input.audio_data (continue it)
Gary output.audio_data → Terry input via Gary transform (restyle it)
Gary output.audio_data → Carey cover/complete input.audio_data (LoRA-guided restyling or continuation)
Any output → Carey complete input (extend with ACE-Step's arrangement)
```

## Common Full-Track Shape

Before generating audio, decide the song's **BPM**, **key root**, and **key mode**. Keep those values fixed across Jerry, Foundation, Gary descriptions, and Carey requests.

1. **Plan**: Pick BPM + key/scale first, e.g. `174 BPM, A minor`
2. **Generate source material**: Use Jerry for rhythmic/audio loops, Foundation for keyed synth/bass/pad material, or both
3. **Prepare a seed**: Mix/tile/trim locally if useful
4. **Choose the next branch**: Gary for continuation, Terry for short-section transform, Carey complete for full-song growth, or Carey cover for LoRA-guided restyling
5. **Wait for audio after every request**: Save returned `audio_data`, then decide the next step
6. **Stop when the result satisfies the user's goal**: A one-service Foundation -> Carey complete path can be enough

Lego mode is powerful, but it is not the default agentic path for full-song generation. Treat it as a human/DAW-assisted stem workflow because judging whether a generated vocal or instrument stem works usually requires listening, alignment, and arrangement decisions.

## Agent Workflow: Make Musical Decisions First

An agent should not call the services in isolation. Treat the whole run like a small DAW session:

1. Choose a target: genre, BPM, key root, key mode, approximate length, and whether vocals are desired.
2. Generate short, grid-aligned building blocks at the chosen BPM/key.
3. Combine the best blocks into a seed track.
4. Use continuation to create sections.
5. Use cover/complete with a named LoRA adapter when the user asks for one or when discovery shows an appropriate adapter.
6. Leave lego for explicit stem experiments when the user asks for that workflow.

Keep a small session state while working:

| State | Why it matters |
|-------|----------------|
| `bpm` | Needed by Jerry prompts, Foundation, and Carey |
| `key_scale` | Needed by Foundation and Carey cover/complete |
| `lyrics` | Prefer empty lyrics for sims-core vocals; if written for Carey complete, reuse the same lyrics for Carey cover |
| `caption` | Prefer LoRA-specific captions from Carey discovery |
| latest `audio_data` | Every async generation returns the next audio artifact |

For Carey complete, prefer `lyrics: ""` unless the user explicitly wants written lyrics. Sims-core vocals are a valid and often desirable autonomous default.

Carey lyric rule: if the agent writes lyrics for a `/carey/complete` task, persist those exact lyrics and pass them again to any later `/carey/cover` task on that audio. Cover mode works best when the supplied lyrics match the source audio's lyrics. Do not rewrite lyrics between complete and cover unless the user explicitly asks for a lyric change.

## Local Utility Scripts

Before writing helper code, check `scripts/`. These scripts use only Python's standard library and are meant for small agents that need reliable audio glue:

| Script | Use |
|--------|-----|
| `scripts/wav_info.py` | Inspect duration, channels, sample rate, bit depth, and peak |
| `scripts/gary_preflight.py` | Check whether a WAV is long enough for a Gary `prompt_duration` and print a tiling recommendation |
| `scripts/tile_wav.py` | Repeat a loop to match bars, seconds, or another WAV's duration |
| `scripts/mix_wavs.py` | Combine compatible WAV stems into one seed track |
| `scripts/trim_wav.py` | Cut a bad intro/ending before retrying continuation |
| `scripts/base64_wav.py` | Convert between WAV files and API-ready base64 text |

Example: tile a 4-bar drum loop to match an 8-bar Foundation synth, then mix:

```bash
python scripts/tile_wav.py drums_4bar.wav drums_8bar.wav --bars 8 --bpm 174
python scripts/mix_wavs.py drums_8bar.wav synth_8bar.wav -o seed_8bar.wav --gain 0.8 --gain 0.7 --normalize
```

Example: check a short loop before sending it to Gary. Gary's default `prompt_duration` is 6 seconds, so the source WAV must be longer than that window. If the preflight says `tile_before_gary`, tile the source before encoding it for Gary.

```bash
python scripts/gary_preflight.py seed_4bar.wav --prompt-duration 6
python scripts/tile_wav.py seed_4bar.wav seed_for_gary.wav --seconds 12
python scripts/base64_wav.py encode seed_for_gary.wav -o seed_for_gary.b64
```

Example: tile a combined seed to 2 minutes, then use Carey cover with gentle settings:

```bash
python scripts/tile_wav.py seed_8bar.wav seed_2min.wav --seconds 120
python scripts/base64_wav.py encode seed_2min.wav -o seed_2min.b64
```

Then call `/carey/cover` with the encoded audio, a LoRA-specific caption, and conservative shine settings such as `cover_noise_strength: 0.2` and `audio_cover_strength: 0.3`. For a sweeter, more transformed cover, try lower values around `cover_noise_strength: 0.1-0.15` and `audio_cover_strength: 0.12`. Raise `audio_cover_strength` toward `0.5` only when the source has vocals or when you intentionally want a stronger adapter effect.

Useful defaults:

| Goal | Suggested choice |
|------|------------------|
| DnB | 170-174 BPM, minor key |
| House/techno | 120-130 BPM, minor key |
| Ambient | 90-120 BPM, major or minor |
| Pop/indie | 90-125 BPM, major or minor |

For key choice, simple roots like `A minor`, `C minor`, `F minor`, `D minor`, `C major`, and `G major` are good defaults. Use the exact same key text when a Carey endpoint accepts `key_scale`, and split it into `key_root` + `key_mode` for Foundation.

## Agent "Dice Button": Captions and LoRAs

The VST uses a dice button for style captions. An agent should do the same thing programmatically through Carey:

```bash
# Discover available LoRA adapters
curl -s https://g4l.thecollabagepatch.com/carey/loras

# See caption pools
curl -s https://g4l.thecollabagepatch.com/carey/captions/pools

# Get a random default caption
curl -s https://g4l.thecollabagepatch.com/carey/captions

# Get a random caption tuned for a selected LoRA
curl -s "https://g4l.thecollabagepatch.com/carey/captions?lora=billie"
```

LoRA names such as `billie`, `koan`, or `kev` are backend adapter ids, not prompt text. When API calls are allowed, discover available adapters with `/carey/loras`; if the user names one of those adapters, use that exact key. Get the caption with `/carey/captions?lora=<adapter_id>`, then pass the returned `caption` directly in `/carey/cover` or `/carey/complete` and pass the same adapter id in the `lora` field. This matters: a LoRA-specific caption is usually a better control signal than a generic freeform style prompt.

Important routing caveat: check `/carey/loras` before choosing where to use a LoRA. Current public LoRAs are intended for the ACE `base` and `turbo` backends, which means they are a natural fit for `/carey/cover` and `/carey/complete`. Lego currently routes to the regular ACE backend, so a LoRA may be rejected there unless its `backends` list includes `"regular"`.

## Carey Cover as Style Injection

`/carey/cover` restyles an existing track while preserving structure and duration. This is now strong enough to be a creative step in the full-song workflow, especially with named LoRA adapters:

1. Build a song seed with Jerry/Foundation/Gary.
2. Discover LoRAs with `/carey/loras`.
3. Get a LoRA-specific caption with `/carey/captions?lora=<adapter_id>`.
4. Call `/carey/cover` with `lora: "<adapter_id>"` and the returned caption to apply that adapter to the track.
5. Optionally feed the covered result into `/carey/complete` to continue the new direction into a longer section.

## BPM/Key Matching Tips

- When combining outputs from different services, keep BPM consistent across all calls
- Foundation snaps to nearest supported BPM (100, 110, 120, 128, 130, 140, 150) but time-stretches output to your requested `host_bpm`
- Jerry requires BPM in the prompt text (e.g., "120bpm drum loop")
- Foundation needs `key_root` and `key_mode`; Carey cover/complete can take `key_scale` like `"A minor"`
- Carey needs an explicit `bpm` parameter
- Gary inherits BPM from the audio you feed it — no explicit BPM param needed
- Gary can still be guided with a text `description`; include the same BPM/key in that description when it helps the model stay coherent
- Gary's practical default `prompt_duration` is 6 seconds; inspect or preflight short loops before sending them to `process_audio` or `continue_music`
- Gary outputs often have a raw/lo-fi MusicGen character; unless that texture is the goal, consider Carey `complete` or `cover` as the polish step

## Carey Lego Mode: Human-in-the-Loop

Lego mode works best with **2+ minutes** of input audio. For shorter inputs, the wrapper automatically engages **loop assist** which tiles the audio to reach the minimum length.

For autonomous full-song generation, prefer Carey cover/complete. Use lego only when the user specifically wants stem generation and expects to judge the result by ear.

## Service-Specific Skills

For detailed endpoint documentation, parameter references, and examples, load the individual service skill:
- `jerry.md` — stable-audio endpoints and prompt craft
- `gary.md` — MusicGen continuation, retry, transform
- `foundation.md` — structured synthesis with randomize + generate
- `carey.md` — ACE-Step cover, complete continuation, LoRAs, captions, and optional lego stems
- `terry.md` — MelodyFlow transform (via Gary)

## Queue Behavior

All services are protected by a GPU queue. If the system is busy, your request will be queued and you'll see `queue_status` in poll responses with your position and estimated wait time. Just keep polling — the system is FIFO and will get to your request.

Agent rules:

- Use one generation/transform request at a time across the whole pipeline.
- Run heavy generations sequentially unless the user explicitly asks for alternate takes.
- Do not fire multiple Carey cover/complete jobs for the same source audio just to "see what happens"; choose one caption/LoRA/setting, submit it, and wait.
- Poll every 3-5 seconds; faster polling does not make the model finish sooner.
- Treat queue/warming/loading/generating statuses as normal. ACE-Step model loading alone can add 30-60 seconds before generation starts.
- When a job fails with a retryable queue/backend error, wait 30-60 seconds before retrying once.
- When a generation succeeds, save the returned audio before making the next request.
