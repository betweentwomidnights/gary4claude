# Terry — MelodyFlow Audio Transform

Audio style transfer powered by MelodyFlow. Terry transforms existing audio using a text prompt — "8bit", "orchestral", "lo-fi", "underwater", etc. Terry is accessed through Gary's transform endpoint.

Base: `https://g4l.thecollabagepatch.com`

Terry is **async** — submit via Gary's transform endpoint, poll via Gary's poll_status.

## How to Use Terry

Terry doesn't have his own external endpoints. You call him through Gary:

Use Terry as a short-section color tool, not as the final step on a long completed song unless you intentionally want only an excerpt transformed. MelodyFlow returns about 30 seconds, so a common path is:

```
short seed or 30-second section -> Terry transform -> Gary/Carey continuation or completion
```

For a two-minute song, transform selected sections individually or use Carey cover for full-length restyling.

### POST /api/juce/transform_audio

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `session_id` | string | no | — | Existing Gary session (uses its audio) |
| `audio_data` | string | no | — | Or provide audio directly (base64 WAV) |
| `variation` | string | yes | — | Transform preset name. Use `"custom"` for free-text prompts |
| `custom_prompt` | string | no | — | Free-text style prompt (only used with `variation: "custom"`) |
| `flowstep` | float | no | — | Flow step magnitude. Higher values stay closer to source; lower values transform more radically |
| `solver` | string | no | — | ODE solver algorithm |

Either `session_id` or `audio_data` is required.

**Example — transform to 8bit:**
```bash
curl -s https://g4l.thecollabagepatch.com/api/juce/transform_audio \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_data\": \"$AUDIO_BASE64\",
    \"variation\": \"custom\",
    \"custom_prompt\": \"8bit chiptune\"
  }"
# Response: {"success": true, "session_id": "..."}
```

### GET /api/juce/poll_status/{session_id}

Same as Gary's poll endpoint. Check `transform_in_progress` (not `generation_in_progress`) for transform status.

When done, `audio_data` contains the transformed base64 WAV.

### POST /api/juce/undo_transform

Revert to pre-transform audio: `{"session_id": "..."}`

Returns `audio_data` with the original audio.

## Transform Prompt Ideas

The `custom_prompt` is a free-text description of the target style. Some ideas:

- `"8bit chiptune"` — retro game audio
- `"orchestral strings"` — classical reinterpretation
- `"lo-fi tape saturation"` — warm, degraded
- `"underwater reverb"` — submerged, filtered
- `"aggressive distortion"` — heavy, crunchy
- `"jazz piano"` — reharmonized, acoustic
- `"ambient drone"` — stretched, atmospheric
- `"acid 303"` — squelchy, resonant

## Important Notes

- Transforms work on audio up to ~30 seconds. For longer audio, transform sections individually.
- Only 1 transform can run at a time across the entire system (MelodyFlow is single-threaded with a dedicated queue).
- The `flowstep` parameter controls how far the transform deviates from the original, but it is reversed from what many agents expect: high values such as `0.13`-`0.15` stay closer to the source, while lower values produce more radical transformations.
- Use `undo_transform` if you don't like the result — it restores the previous audio.
