# Foundation — Structured Synth/Sample Generation

RoyalCities Foundation-1 model. Generates synth patches, pads, bass, leads, and textured samples with fine-grained control over timbre, FX, and musical behavior. Has a powerful **randomize** endpoint that produces musically coherent presets.

Base: `https://g4l.thecollabagepatch.com/foundation`

Foundation is **async** — submit via `/generate`, poll via `/poll_status/{session_id}`.

## Endpoints

### POST /foundation/randomize

Generate a random but musically coherent preset. Returns decomposed parameter values you can inspect, tweak, and feed into `/generate`. This is the **recommended way** to start a Foundation generation.

**Parameters (JSON body, all optional):**
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `seed` | int | -1 | -1 for random, or fix for reproducibility |
| `mode` | string | `"standard"` | `"standard"` or `"mix"` (multi-timbre) |
| `variant` | string | `"auto"` | `"auto"`, `"M1"`, or `"T1"` |
| `family_hint` | string | — | Lock to a family: `"Synth"`, `"Bass"`, `"Pad"`, `"Keys"`, etc. |

**Response (key fields):**
```json
{
  "success": true,
  "seed": 1234567,
  "family": "Synth",
  "subfamily": "Lead",
  "descriptor_knob_a": "Bright",
  "descriptor_knob_b": "Pluck",
  "descriptor_knob_c": "Sharp",
  "descriptors_extra": [],
  "reverb_enabled": true,
  "reverb_amount": "Large Hall",
  "delay_enabled": false,
  "delay_type": "",
  "distortion_enabled": false,
  "distortion_amount": "",
  "phaser_enabled": false,
  "phaser_amount": "",
  "bitcrush_enabled": false,
  "bitcrush_amount": "",
  "behavior_tags": ["Moderate", "Arpeggio", "Rising"],
  "spatial_tags": ["Wide"],
  "band_tags": [],
  "wave_tech_tags": ["Saw"],
  "style_tags": [],
  "prompt": "Synth, Lead, Bright, Pluck, Sharp, Wide, Saw, Moderate, Arpeggio, Rising, Large Hall, 4 Bars, 120 BPM, C minor"
}
```

The `prompt` field is the fully assembled text prompt. You can pass the entire response body (or selected fields) directly to `/generate`.

### POST /foundation/generate

Submit a generation request. Returns immediately with a `session_id` for polling.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `host_bpm` | float | no | 120.0 | Your project BPM — output is time-stretched to match |
| `bars` | int | no | 4 | 4 or 8 bars |
| `key_root` | string | no | `"C"` | Note root: C, C#, Db, D, ... B |
| `key_mode` | string | no | `"minor"` | `"major"` or `"minor"` |
| `seed` | int | no | -1 | -1 for random |
| `steps` | int | no | 100 | Diffusion steps |
| `guidance_scale` | float | no | 7.0 | CFG scale |
| `custom_prompt_override` | string | no | — | Override the assembled prompt entirely |
| `family` | string | no | — | Instrument family (from randomize) |
| `subfamily` | string | no | — | Instrument subfamily (from randomize) |
| `descriptor_knob_a/b/c` | string | no | — | Timbre descriptors (from randomize) |
| `descriptors_extra` | list | no | — | Additional descriptors |
| `reverb_enabled` | bool | no | — | Enable reverb FX |
| `reverb_amount` | string | no | — | Reverb level/type |
| `delay_enabled` | bool | no | — | Enable delay FX |
| `delay_type` | string | no | — | Delay type |
| `distortion_enabled` | bool | no | — | |
| `distortion_amount` | string | no | — | |
| `phaser_enabled` | bool | no | — | |
| `phaser_amount` | string | no | — | |
| `bitcrush_enabled` | bool | no | — | |
| `bitcrush_amount` | string | no | — | |
| `behavior_tags` | list | no | — | Melody behavior |
| `spatial_tags` | list | no | — | Spatial characteristics |
| `band_tags` | list | no | — | Frequency band tags |
| `wave_tech_tags` | list | no | — | Waveform/technique tags |
| `style_tags` | list | no | — | Style tags |

**Response:**
```json
{
  "success": true,
  "session_id": "abc123def456",
  "seed": 1234567,
  "bars": 4,
  "host_bpm": 174.0,
  "foundation_bpm": 170,
  "gen_duration": 5.6471,
  "stretch_ratio": 1.0235,
  "prompt": "Synth, Lead, Bright, ..., 4 Bars, 170 BPM, C minor"
}
```

### GET /foundation/poll_status/{session_id}

Poll generation progress.

**Response:**
```json
{
  "success": true,
  "generation_in_progress": false,
  "transform_in_progress": false,
  "progress": 100,
  "status": "completed",
  "audio_data": "base64-encoded-wav...",
  "queue_status": {"status": "ready"}
}
```

### POST /foundation/audio2audio

Timbre transfer — restyle existing audio through Foundation's diffusion process.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes | — | Base64-encoded WAV input |
| `prompt` | string | yes | — | Target timbre description |
| `host_bpm` | float | yes | — | BPM of the input audio |
| `bars` | int | no | 8 | 4 or 8 |
| `init_noise_level` | float | no | 0.25 | 0.01-1.0: low = preserve input, high = more generation |
| `seed` | int | no | -1 | |
| `steps` | int | no | 75 | |
| `guidance_scale` | float | no | 7.0 | |
| `key_root` | string | no | `"C"` | |
| `key_mode` | string | no | `"minor"` | |

### GET /foundation/health

Health check. Returns `{"status": "ready"}` when model is loaded.

## Workflow: Randomize then Generate

The cleanest way to use Foundation:

```bash
# 1. Get a random preset (optionally hint at a family)
PRESET=$(curl -s https://g4l.thecollabagepatch.com/foundation/randomize \
  -H "Content-Type: application/json" \
  -d '{"family_hint": "Bass"}')

# 2. Feed the preset to generate, adding your BPM/key
GENERATE=$(echo "$PRESET" | jq '. + {"host_bpm": 174, "bars": 4, "key_root": "A", "key_mode": "minor"}' | \
  curl -s https://g4l.thecollabagepatch.com/foundation/generate \
    -H "Content-Type: application/json" -d @-)

SESSION_ID=$(echo "$GENERATE" | jq -r '.session_id')

# 3. Poll until done
# (see gary4claude.md for the generic poll loop)
```

## BPM Handling

Foundation generates at one of these internal BPMs: **100, 110, 120, 128, 130, 140, 150**. It picks the nearest to your `host_bpm` and time-stretches the output to match your actual tempo. This means:
- You can request any BPM and it will work
- The output is metrically locked to your tempo
- The `foundation_bpm` in the generate response tells you which internal BPM was used

## Matching Foundation Output to Jerry/Gary

To make a Foundation synth layer that matches a Jerry drum loop:
1. Use the same `host_bpm` you used for Jerry
2. Use the same `key_root` and `key_mode`
3. Match `bars` count
4. The outputs will be tempo-aligned and key-compatible
