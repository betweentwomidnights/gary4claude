# Carey — ACE-Step Cover and Continuation

ACE-Step model wrapper. For autonomous agents, Carey's main tools are **cover mode** for restyling an existing track while preserving structure and **complete mode** for extending audio with full arrangement. Lego mode can generate stems over a beat, but it is best treated as a human/DAW-assisted workflow.

Base: `https://g4l.thecollabagepatch.com/carey`

All Carey endpoints are **async** — submit, then poll the status endpoint until done.

Carey generations can take a while. Submit one Carey job, poll its status every 3-5 seconds, and wait for `status: "completed"` plus `audio_data` before submitting the next Carey job. Queueing, loading, warming, and generating statuses are normal.

## Carey Queue Discipline

Carey runs GPU-heavy ACE-Step jobs. Agents should be patient and deliberate:

- Submit one Carey job at a time for a given song chain.
- Poll `/carey/{mode}/status/{task_id}` every 3-5 seconds.
- Do not resubmit because progress appears slow; model loading and queue waits are expected.
- Do not launch parallel cover/complete variations unless the user explicitly asks for multiple takes.
- If a job returns a retryable backend/queue error, wait 30-60 seconds before one retry.
- After completion, store the returned `audio_data`, `lyrics`, `caption`, `lora`, `bpm`, and `key_scale` before continuing.

## Agent-First Carey Workflow

Carey is most useful after the agent has already chosen a BPM/key and built enough musical context with Jerry, Foundation, and Gary.

1. Choose the global song BPM and key before calling Carey.
2. For LoRA-driven style, call `/carey/loras` and then `/carey/captions?lora=<adapter_id>`.
3. Use `/carey/cover` to apply the selected LoRA adapter to an existing track without changing its length.
4. Use `/carey/complete` to extend a track to a target duration, optionally with the same LoRA and caption.
5. Use `/carey/lego` only when the user specifically wants stem generation and expects human listening/arrangement judgment.

If the user asks for a named LoRA adapter such as `billie`, the practical path is usually:

```
song seed from Jerry/Foundation/Gary
  -> optionally tile the seed to a useful length with scripts/tile_wav.py
  -> write or retain lyrics if the source has lyrics
  -> GET /carey/captions?lora=billie
  -> POST /carey/cover with lora="billie"
  -> POST /carey/complete with lora="billie" if the covered section should continue
```

## Lyrics Across Carey Modes

Carey does not need written lyrics to produce useful vocal material. For many autonomous workflows, leave `lyrics` empty and let ACE-Step generate wordless, phonetic, or "sims-core" vocals. This often produces more surprising and musically useful results than generic agent-written lyrics.

Only write lyrics when the user asks for them, when the concept clearly depends on intelligible words, or when a previous Carey complete result with lyrics must be covered again.

Default autonomous choice:

```json
{
  "lyrics": ""
}
```

Lyrics should persist across Carey modes when they are used. If the agent writes lyrics for `/carey/complete`, store those lyrics in the session state and reuse the same text in any later `/carey/cover` request on that audio.

This is especially important for cover. ACE-Step cover works best when the `lyrics` field matches the lyrics already present in the source audio. If the source audio came from a Carey complete request with lyrics, pass those exact lyrics to cover. Do not rewrite, summarize, or omit them unless the user explicitly asks for different words.

Example pattern:

```json
{
  "lyrics": "[Verse 1]\n...\n[Chorus]\n...",
  "caption": "<caption from /carey/captions?lora=billie>",
  "lora": "billie"
}
```

Use the same `lyrics` string for complete and cover when they are part of the same song chain.

## LoRA and Caption Discovery

Carey exposes the available LoRA adapters and caption pools. The VST presents this as a dice button; an agent should call these endpoints directly.

LoRA names are backend adapter ids. Treat strings like `billie` as adapter keys discovered from `/carey/loras` or supplied by the user, not as freeform prompt instructions. The captions endpoint uses the same key: `/carey/captions?lora=<adapter_id>` returns a random caption from that adapter's caption pool.

### GET /carey/loras

Returns the currently available LoRA adapters.

**Response:**
```json
{
  "billie": {"scale": 1.0, "backends": ["base", "turbo"]},
  "koan": {"scale": 1.0, "backends": ["base", "turbo"]}
}
```

Names are dynamic. Do not hardcode them unless the task explicitly asks for one.

### GET /carey/captions/pools

Returns available caption pools and their sizes.

**Response:**
```json
{
  "default": 200,
  "billie": 42,
  "koan": 42
}
```

### GET /carey/captions

Returns a random default caption.

**Response:**
```json
{"caption": "dreamy alternative pop vocal, intimate, breathy, warm", "pool": "default", "pool_size": 200}
```

### GET /carey/captions?lora={name}

Returns a random caption from the selected LoRA adapter's caption pool.

```bash
curl -s "https://g4l.thecollabagepatch.com/carey/captions?lora=billie"
```

Use the returned `caption` in `/carey/cover` or `/carey/complete`, and pass the same adapter id in the `lora` field. This is the agent equivalent of pressing the LoRA-aware dice button in the plugin.

If the selected pool does not exist, this endpoint returns 404. Fall back to `/carey/captions` or write a caption manually.

## LoRA Request Fields

`/carey/lego`, `/carey/complete`, and `/carey/cover` accept:

| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `lora` | string | no | `""` | Adapter name from `/carey/loras`; empty means no LoRA |
| `lora_scale` | float | no | `-1.0` | Strength override 0.0-1.0; -1 uses the server default |

Before sending a LoRA, check its `backends` list from `/carey/loras`. Current public LoRAs are generally for `"base"` and `"turbo"`. Lego requests route to Carey's regular backend for better vocal stems, so a LoRA can be rejected on lego unless its `backends` includes `"regular"`.

## Lego Mode — Optional Stem Workflow

Lego mode generates a single stem, such as vocals, drums, bass, guitar, piano, or strings, over existing audio. It is powerful, but it is not the preferred autonomous full-song path because judging stem quality usually requires human ears, timing decisions, and DAW-style arrangement.

For agentic full-song generation, prefer `/carey/cover` and `/carey/complete`. Use lego when the user explicitly asks for stem generation. The model can sing wordless/gibberish vocals by default, or you can provide lyrics with structure tags and it will vocalize those.

### POST /carey/lego

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes | — | Base64-encoded source audio (the beat to sing over) |
| `track_name` | string | yes | — | `"vocals"`, `"drums"`, `"bass"`, `"guitar"`, `"piano"`, `"strings"`, etc. |
| `bpm` | int | yes | — | BPM of the source audio |
| `caption` | string | no | `""` | Style caption — overrides default for track type |
| `lyrics` | string | no | `""` | Lyrics with structure tags like `[Verse 1]`, `[Chorus]` |
| `language` | string | no | `"en"` | Language code: `en`, `ja`, `zh`, etc. |
| `guidance_scale` | float | no | 7.0 | CFG scale. 7-9 recommended |
| `inference_steps` | int | no | 50 | Diffusion steps |
| `time_signature` | string | no | `"4"` | Time signature numerator |
| `batch_size` | int | no | 1 | Number of candidates |
| `audio_format` | string | no | `"wav"` | `"wav"`, `"mp3"`, `"flac"` |
| `lora` | string | no | `""` | Optional LoRA adapter; verify backend support first |
| `lora_scale` | float | no | `-1.0` | Optional LoRA strength override |

**Response:**
```json
{"task_id": "abc-123", "status": "queued"}
```

**Example — add sims-core vocals without lyrics:**
```bash
curl -s https://g4l.thecollabagepatch.com/carey/lego \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_data\": \"$TRACK_BASE64\",
    \"track_name\": \"vocals\",
    \"bpm\": 174,
    \"lyrics\": \"\",
    \"guidance_scale\": 8.0
  }"
```

**Example — add vocals with user-provided lyrics:**
```bash
curl -s https://g4l.thecollabagepatch.com/carey/lego \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_data\": \"$TRACK_BASE64\",
    \"track_name\": \"vocals\",
    \"bpm\": 174,
    \"lyrics\": \"$USER_LYRICS\",
    \"guidance_scale\": 8.0
  }"
```

### GET /carey/lego/status/{task_id}

Poll lego generation progress.

**Response (in progress):**
```json
{
  "success": true,
  "generation_in_progress": true,
  "progress": 45,
  "status": "generating",
  "progress_text": "generating stem..."
}
```

**Response (complete):**
```json
{
  "success": true,
  "generation_in_progress": false,
  "progress": 100,
  "status": "completed",
  "audio_data": "base64-wav..."
}
```

## Input Length for Lego Mode

Lego mode works best with **2 minutes or more** of input audio. The model was trained on longer sequences and produces much better vocal stems when it has sufficient musical context.

For shorter inputs, the wrapper automatically engages **loop assist** — it tiles (repeats) your audio to reach the minimum length before sending to the model. This works, but results are noticeably better with genuinely long input.

**Human-in-the-loop workflow for lego vocals:**
1. Generate a seed with Jerry or Foundation
2. Chain Gary continuations to build ~2 minutes of audio (with retries as needed)
3. Feed the full 2-minute track to Carey lego with `track_name: "vocals"`
4. Listen, align, retry, or arrange the generated stem in a DAW

## Complete Mode — ACE-Step Continuation

Extends audio with full arrangement. Unlike Gary's MusicGen continuation, Carey uses ACE-Step's diffusion approach which is more compositionally aware. Works well even with 30+ seconds of input — a successful Gary generation can lead straight into a Carey complete for interesting results.

### POST /carey/complete

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes | — | Base64-encoded source audio |
| `bpm` | int | yes | — | BPM of the source |
| `audio_duration` | float | yes | — | Target total output duration in seconds |
| `caption` | string | no | `""` | Style caption — longer = stronger steer |
| `lyrics` | string | no | `""` | Lyrics with structure tags |
| `language` | string | no | `"en"` | Language code |
| `key_scale` | string | no | `""` | Key/scale e.g. `"F minor"`, `"C major"` |
| `guidance_scale` | float | no | 7.0 | |
| `inference_steps` | int | no | 50 | |
| `use_src_as_ref` | bool | no | false | Pass source as ref_audio for timbre anchoring |
| `time_signature` | string | no | `"4"` | |
| `batch_size` | int | no | 1 | |
| `audio_format` | string | no | `"wav"` | |
| `model` | string | no | `"xl-turbo"` | `"xl-turbo"` for fast/clean, `"xl-base"` for richer generation |
| `lora` | string | no | `""` | Optional LoRA adapter |
| `lora_scale` | float | no | `-1.0` | Optional LoRA strength override |

**Example — continue with a LoRA-specific caption:**
```bash
CAPTION=$(curl -s "https://g4l.thecollabagepatch.com/carey/captions?lora=billie" | jq -r '.caption')

jq -n \
  --arg audio_data "$TRACK_BASE64" \
  --arg caption "$CAPTION" \
  '{
    audio_data: $audio_data,
    bpm: 120,
    audio_duration: 90,
    key_scale: "A minor",
    caption: $caption,
    lyrics: "",
    model: "xl-base",
    lora: "billie",
    guidance_scale: 7.0,
    inference_steps: 50
  }' | curl -s https://g4l.thecollabagepatch.com/carey/complete \
  -H "Content-Type: application/json" \
  -d @-
```

### GET /carey/complete/status/{task_id}

Poll completion progress. Same response shape as lego status.

## Cover Mode — Restyle While Preserving Structure

Cover mode transforms an existing audio file into a new style while keeping the source structure and duration. This is the best Carey endpoint for applying a named LoRA adapter after the agent has already built a song seed.

Gary/MusicGen outputs often have a raw or lo-fi quality. That can be desirable, but if the user wants a more finished or hi-fi result, a good autonomous path is Gary for arrangement growth followed by Carey `complete` or `cover` for polish.

For a simple autonomous workflow, tile a good 4- or 8-bar seed to a longer duration first, then run cover gently. This gives ACE-Step more musical context while preserving the arrangement grid:

```bash
python scripts/tile_wav.py seed_8bar.wav seed_2min.wav --seconds 120
python scripts/base64_wav.py encode seed_2min.wav -o seed_2min.b64
```

### POST /carey/cover

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes | — | Base64-encoded source audio |
| `bpm` | int | yes | — | BPM of the source |
| `caption` | string | yes | — | Style caption driving the cover/remix |
| `lyrics` | string | no | `""` | Lyrics with structure tags |
| `language` | string | no | `"en"` | Language code |
| `key_scale` | string | no | `""` | Key/scale e.g. `"A minor"` |
| `cover_noise_strength` | float | no | 0.2 | 0=pure noise, 1=closest to source; 0.2 is a good default |
| `audio_cover_strength` | float | no | 0.3 | Semantic-code strength; try 0.5-0.7 for vocal-heavy material |
| `guidance_scale` | float | no | 1.0 | Turbo default; use higher values with `xl-base` |
| `inference_steps` | int | no | 8 | Turbo default; use ~50 with `xl-base` |
| `use_src_as_ref` | bool | no | false | Pass source as reference audio for subtler transformation |
| `time_signature` | string | no | `"4"` | Time signature numerator |
| `batch_size` | int | no | 1 | Number of candidates |
| `audio_format` | string | no | `"wav"` | `"wav"`, `"mp3"`, `"flac"` |
| `model` | string | no | `"xl-turbo"` | `"xl-turbo"` or `"xl-base"` |
| `lora` | string | no | `""` | Optional LoRA adapter |
| `lora_scale` | float | no | `-1.0` | Optional LoRA strength override |
| `no_fsq` | bool | no | false | Advanced: bypass FSQ roundtrip for fuller source-latent detail |

Strength guidance:

- Start with `cover_noise_strength: 0.2` and `audio_cover_strength: 0.3` when you want to keep the output fairly close to the source while adding polish.
- Try `cover_noise_strength: 0.1-0.15` and `audio_cover_strength: 0.12` for a sweeter or more surprising transformation.
- Raise `audio_cover_strength` toward `0.5` only when the source has vocals, when the source structure must remain very legible, or when you want a stronger adapter imprint.

**Example — cover a generated song seed with the `billie` LoRA adapter:**
```bash
CAPTION=$(curl -s "https://g4l.thecollabagepatch.com/carey/captions?lora=billie" | jq -r '.caption')

jq -n \
  --arg audio_data "$TRACK_BASE64" \
  --arg caption "$CAPTION" \
  '{
    audio_data: $audio_data,
    bpm: 120,
    key_scale: "A minor",
    caption: $caption,
    lyrics: "",
    model: "xl-base",
    lora: "billie",
    cover_noise_strength: 0.2,
    audio_cover_strength: 0.3,
    guidance_scale: 7.0,
    inference_steps: 50
  }' | curl -s https://g4l.thecollabagepatch.com/carey/cover \
  -H "Content-Type: application/json" \
  -d @-
```

### GET /carey/cover/status/{task_id}

Poll cover/remix progress. Same response shape as lego status.

### GET /carey/health

Health check for wrapper + backend.
