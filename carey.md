# Carey — ACE-Step Vocals and Continuation

ACE-Step model wrapper. Carey's killer feature is **lego mode** — generating AI vocals (or other stems) over a beat. Also supports **complete mode** for extending audio with full arrangement using ACE-Step's diffusion approach.

Base: `https://g4l.thecollabagepatch.com/carey`

All Carey endpoints are **async** — submit, then poll the status endpoint until done.

## Lego Mode — The Main Event

Lego mode generates a single stem (most importantly: **vocals**) over existing audio. This is how you get an AI singer performing over a beat you built with Jerry/Gary/Foundation.

The model will sing in a sims-like gibberish by default, which honestly sounds great. Or you can provide lyrics with structure tags and it'll vocalize those.

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

**Response:**
```json
{"task_id": "abc-123", "status": "queued"}
```

**Example — add vocals with lyrics:**
```bash
curl -s https://g4l.thecollabagepatch.com/carey/lego \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_data\": \"$TRACK_BASE64\",
    \"track_name\": \"vocals\",
    \"bpm\": 174,
    \"lyrics\": \"[Verse 1]\\nRunning through the neon lights\\nChasing shadows in the night\",
    \"guidance_scale\": 8.0
  }"
```

**Example — vocals without lyrics (sims gibberish):**
```bash
curl -s https://g4l.thecollabagepatch.com/carey/lego \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_data\": \"$TRACK_BASE64\",
    \"track_name\": \"vocals\",
    \"bpm\": 174
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

**Recommended workflow for lego vocals:**
1. Generate a seed with Jerry or Foundation
2. Chain Gary continuations to build ~2 minutes of audio (with retries as needed)
3. Feed the full 2-minute track to Carey lego with `track_name: "vocals"`

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

### GET /carey/complete/status/{task_id}

Poll completion progress. Same response shape as lego status.

### GET /carey/health

Health check for wrapper + backend.
