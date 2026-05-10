# Gary — MusicGen Continuation API

Audio continuation using AudioCraft MusicGen finetunes. Feed Gary audio and he extends it. Chain multiple continuations to build long tracks. Also handles retries (regenerate from last input) and transforms (via Terry/MelodyFlow).

Base: `https://g4l.thecollabagepatch.com`

All Gary endpoints are **async** — submit, then poll `/api/juce/poll_status/{session_id}` until done.

## Critical Concept: process_audio vs continue_music

These two endpoints do different things with `prompt_duration`:

- **`process_audio`**: Uses the **first** `prompt_duration` seconds of your audio as the conditioning input, then generates new audio extending from that point. Think of it as "listen to the beginning, then keep going."

- **`continue_music`**: Uses the **last** `prompt_duration` seconds of the provided audio as the conditioning input, then generates new audio extending from the end. Think of it as "listen to the ending, then keep going."

For building long tracks, `continue_music` is almost always what you want.

## Prompt Duration Preflight

Gary's practical default `prompt_duration` is **6 seconds**. Before calling either `process_audio` or `continue_music`, inspect the source WAV duration and make sure it is longer than the prompt window. A short Jerry loop can be around 5.5 seconds at fast tempos; sending it to Gary with `prompt_duration: 6`, `8`, or `12` can fail or produce ambiguous backend tensor errors.

Agent rule:

1. Decode/save the source audio as WAV.
2. Run `scripts/gary_preflight.py` with the intended `prompt_duration`.
3. If it says `tile_before_gary`, tile the WAV first with `scripts/tile_wav.py`, then encode the tiled WAV for Gary.

```bash
python scripts/gary_preflight.py seed.wav --prompt-duration 6
python scripts/tile_wav.py seed.wav seed_for_gary.wav --seconds 12
python scripts/base64_wav.py encode seed_for_gary.wav -o seed_for_gary.b64
```

Use `prompt_duration: 6` unless you have a reason to use more context. Only raise it to `8` or `12` after confirming the source audio is longer than that value. This applies to both endpoints:

- `process_audio` needs enough audio at the **start** for the first `prompt_duration` seconds.
- `continue_music` needs enough audio at the **end** for the last `prompt_duration` seconds.

## Stateless Workflow

Gary is largely **stateless**. You don't need to maintain a session across calls:

- `continue_music` creates a new session automatically when you pass `audio_data` — no need to track a session_id between continuations
- Each call: pass the full `audio_data` you want to continue from, get back new `audio_data` with the continuation appended
- **The only thing `session_id` is required for is `retry_music`** — because retry regenerates from the same starting audio, it needs to reference the session that holds that audio

In practice, a chaining workflow looks like:
1. Call `continue_music` with `audio_data` from Jerry/Foundation → poll → get back extended `audio_data`
2. Call `continue_music` again with that new `audio_data` → poll → get back further extended `audio_data`
3. If a continuation was bad, use `retry_music` with the `session_id` from that call
4. Repeat

## The Silence Problem and Retry Workflow

MusicGen has an **abrupt stop problem**. If you blindly chain 4 continuations in a row, you will very likely end up with stretches of silence. The model sometimes decides the music "ended" and generates nothing.

**How humans handle this:** In the JUCE plugin, users listen to / look at each continuation. If it went silent or sounds bad, they hit **retry** — which regenerates from the same starting point but produces a different result. They might also:
- **Change `prompt_duration`** on retry (shorter = less chance of silence)
- **Switch models** on retry (e.g., try `vanya_ai_dnb_0.1` instead of `keygen-gary-v2-small-8`)
- **Crop** the audio (trim off a bad ending) then continue from the clean cutoff point

**How an agent should handle this:** After each continuation, check the result. If the audio duration didn't grow meaningfully, or if you can detect silence, use `retry_music` with different parameters. You can also use `update_cropped_audio` to trim before continuing.

**Practical retry strategy:**
1. Continue with `prompt_duration: 6` after running the preflight check
2. Poll until complete, get `audio_data`
3. If the result seems short or you want a different take: `retry_music` with the same session
4. Optionally try a shorter `prompt_duration` (6-8) or different model on retry
5. Once you have a good continuation, continue again from there

## Model Switching Mid-Chain

You can absolutely switch models between continuations. This is how interesting outputs happen:

```
Jerry drum loop (174bpm)
  → continue with keygen-gary-v2-small-8 (adds electronic texture)
  → continue with vanya_ai_dnb_0.1 (adds DnB energy)
  → continue with bleeps-medium (adds glitchy elements)
```

Each model brings its own character but respects the audio context it's continuing from. Experiment freely.

## Endpoints

### POST /api/juce/process_audio

Start a new session. Uses the **first** `prompt_duration` seconds as input context.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes | — | Base64-encoded WAV |
| `model_name` | string | yes | — | MusicGen finetune (see models below) |
| `prompt_duration` | int | yes | — | Seconds from the **start** of audio to use as context (3-30) |
| `description` | string | no | — | Text prompt to guide generation |
| `top_k` | int | no | 250 | Top-k sampling (higher = more variety) |
| `temperature` | float | no | 1.0 | Sampling temperature |
| `cfg_coef` | float | no | 3.0 | Classifier-free guidance |

**Response:**
```json
{"success": true, "session_id": "abc123", "message": "Audio processing queued successfully"}
```

### POST /api/juce/continue_music

Continue from the **end** of the provided audio. Primary endpoint for building long tracks. Creates a new session automatically — just pass `audio_data` each time.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes* | — | Base64 WAV to continue from |
| `model_name` | string | yes | — | MusicGen finetune |
| `prompt_duration` | int | yes | — | Seconds from the **end** of audio to use as context |
| `description` | string | no | — | Text prompt |
| `top_k` | int | no | 250 | Sampling variety; lower is more constrained, higher is more exploratory |
| `temperature` | float | no | 1.0 | Sampling randomness |
| `cfg_coef` | float | no | 3.0 | Classifier-free guidance strength |
| `session_id` | string | no | — | Only needed if you want to reuse an existing session |

*Or `session_id` to continue from an existing session's audio.

**Example — continue from a Jerry drum loop:**
```bash
curl -s https://g4l.thecollabagepatch.com/api/juce/continue_music \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_data\": \"$JERRY_BASE64\",
    \"model_name\": \"thepatch/vanya_ai_dnb_0.1\",
    \"prompt_duration\": 6,
    \"description\": \"energetic drum and bass\"
  }"
# Response: {"success": true, "session_id": "xyz789"}
# Save session_id only if you might want to retry this specific generation
```

**Example — chain by passing the new audio_data back in:**
```bash
# Poll until complete, grab audio_data from response, then:
curl -s https://g4l.thecollabagepatch.com/api/juce/continue_music \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_data\": \"$EXTENDED_AUDIO_BASE64\",
    \"model_name\": \"thepatch/vanya_ai_dnb_0.1\",
    \"prompt_duration\": 6
  }"
```

### POST /api/juce/retry_music

Regenerate from the same starting point as the last generation. Different random seed = different result. Use this when a continuation produced silence or a bad output.

**This is why you save `session_id`** — retry needs to reference the session that holds the input audio from the last generation.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `session_id` | string | yes | — | Session to retry (from the continue_music response) |
| `model_name` | string | no | from session | Try a different model |
| `prompt_duration` | int | no | from session | Try shorter (6-8) if getting silence |
| `description` | string | no | — | |
| `top_k` | int | no | 250 | Sampling variety; lower is more constrained, higher is more exploratory |
| `temperature` | float | no | 1.0 | Sampling randomness |
| `cfg_coef` | float | no | 3.0 | Classifier-free guidance strength |

### POST /api/juce/transform_audio

Transform/restyle audio using MelodyFlow (Terry). This route lives under `/api/juce`, but it is **not Gary/MusicGen continuation**. Gary continuation/retry uses `top_k`, `temperature`, and `cfg_coef`; Terry/MelodyFlow transform uses `flowstep`.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `session_id` | string | no | — | Existing session (uses its audio) |
| `audio_data` | string | no | — | Or provide audio directly |
| `variation` | string | yes | — | Transform preset name |
| `custom_prompt` | string | no | — | Free-text style prompt (e.g., "8bit", "orchestral") |
| `flowstep` | float | no | — | Flow step control; higher values stay closer to source, lower values transform more radically |
| `solver` | string | no | — | ODE solver |

**Example — 8bit transform:**
```bash
curl -s https://g4l.thecollabagepatch.com/api/juce/transform_audio \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"variation\": \"custom\",
    \"custom_prompt\": \"8bit chiptune\"
  }"
```

### POST /api/juce/undo_transform

Revert to the audio before the last transform.

**Parameters:** `{"session_id": "..."}` — returns the pre-transform `audio_data`.

### GET /api/juce/poll_status/{session_id}

Poll for generation/transform progress.

**Response:**
```json
{
  "success": true,
  "session_id": "abc123",
  "generation_in_progress": false,
  "transform_in_progress": false,
  "progress": 100,
  "status": "completed",
  "audio_data": "base64-encoded-wav...",
  "queue_status": {"status": "ready", "position": 0},
  "session_data": {
    "model_name": "thepatch/vanya_ai_dnb_0.1",
    "prompt_duration": 6,
    "parameters": {"top_k": 250, "temperature": 1.0, "cfg_coef": 3.0}
  }
}
```

Key fields:
- `generation_in_progress` / `transform_in_progress`: true while working
- `progress`: 0-100
- `audio_data`: base64 WAV when complete (null while in progress)
- `queue_status.status`: `"queued"`, `"ready"`, `"warming"`, or `"processing"`

### GET /api/models

Returns available MusicGen finetunes grouped by size.

## Available Models

| Size | Model | Character |
|------|-------|-----------|
| small | `thepatch/vanya_ai_dnb_0.1` | DnB specialist |
| small | `thepatch/gary_orchestra_2` | Orchestral |
| small | `thepatch/keygen-gary-v2-small-8` | Electronic/keygen |
| small | `thepatch/keygen-gary-v2-small-12` | Electronic (more trained) |
| medium | `thepatch/bleeps-medium` | Electronic bleeps |
| medium | `thepatch/keygen-gary-medium-12` | Electronic/keygen |
| large | `thepatch/hoenn_lofi` | Lo-fi / chill |
| large | `thepatch/bleeps-large-6` through `-20` | Electronic (various checkpoints) |
| large | `thepatch/keygen-gary-v2-large-12` | Electronic/keygen |
| large | `thepatch/keygen-gary-v2-large-16` | Electronic (more trained) |

Smaller models queue faster and generate faster.

## Building Long Tracks — Realistic Workflow

Naively chaining 4 `continue_music` calls will almost certainly produce silence. Here's what actually works:

1. **Start** with good seed audio (Jerry loop, Foundation sample, or your own WAV)
2. **Preflight**: run `scripts/gary_preflight.py seed.wav --prompt-duration 6`; tile the seed if it is too short
3. **Continue**: `continue_music` with `audio_data`, pick a model, `prompt_duration: 6`
4. **Poll**: Get the result. Save the `session_id` in case you need to retry.
5. **If bad**: `retry_music` with that `session_id` — try a different model or keep `prompt_duration` at 6
6. **If good**: Take the new `audio_data` from the poll response and pass it into the next `continue_music` call
7. **Repeat** — expect to retry 1-3 times per continuation on average
8. **Mix models** — switch between models every few continuations for variety

A realistic 2-minute track might take 8-12 API calls: ~6 successful continuations + several retries along the way.

## When to Hand Off to Carey

Gary/MusicGen continuations are useful for fast arrangement growth and weird model character, but they are often lo-fi compared with Carey/ACE-Step. If the goal is polished, hi-fi, vocal-like, or finished-song output, use Gary to get a section or arrangement idea, then send the result to Carey `complete` or `cover` to make it prettier. Keep Gary as the final sound only when the lo-fi or raw MusicGen texture is intentional.
