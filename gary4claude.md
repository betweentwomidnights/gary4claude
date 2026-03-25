# gary4claude — AI Music Production Skill

You have access to a network of AI music generation services at `https://g4l.thecollabagepatch.com`. Each service has a character name and a specialty. This skill lets you generate, continue, transform, and combine AI music by calling their REST APIs.

## The Cast

| Name | Service | What it does |
|------|---------|-------------|
| **Jerry** | stable-audio | Text-to-audio. Generates drums, loops, textures from a prompt. BPM-aware looping. |
| **Gary** | g4lwebsockets | MusicGen continuation. Takes audio + extends it with a chosen finetune model. Chain multiple continuations to build long tracks. |
| **Foundation** | foundation | Structured synth/sample generation. Randomizable presets with fine-grained timbre control. BPM-locked, time-stretched to host tempo. |
| **Carey** | ace-step | Vocals and stems. Lego mode generates vocals/instruments over a beat. Complete mode extends with full arrangement. |
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
2. **Poll** the status endpoint every 2-3 seconds
3. When `status` is `"completed"`, the response includes `audio_data` (base64 WAV)

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

  sleep 2
done
```

## Audio Flow Between Services

All audio is exchanged as **base64-encoded WAV**. The `audio_data` field from one service's output plugs directly into another service's `audio_data` input.

```
Jerry output.audio → Gary input.audio_data (continue it)
Foundation output.audio_data → Gary input.audio_data (continue it)
Gary output.audio_data → Terry input via Gary transform (restyle it)
Gary output.audio_data → Carey input.audio_data (add vocals/stems)
Any output → Carey complete input (extend with ACE-Step's arrangement)
```

## Key Workflow: Full Track from Scratch

1. **Jerry**: Generate a drum loop — `POST /audio/generate/loop` with prompt + BPM
2. **Foundation**: Generate a matching synth layer — call `/foundation/randomize` then `/foundation/generate` with the same BPM and key
3. **Gary**: Continue each layer to build length — `POST /api/juce/continue_music` (chain 4-6 times for ~2 minutes)
4. **Carey (lego)**: Sing vocals over the combined track — `POST /carey/lego` with `track_name: "vocals"` and lyrics
5. **Terry**: Transform/restyle any section — `POST /api/juce/transform_audio` with a style prompt

## BPM/Key Matching Tips

- When combining outputs from different services, keep BPM consistent across all calls
- Foundation snaps to nearest supported BPM (100, 110, 120, 128, 130, 140, 150) but time-stretches output to your requested `host_bpm`
- Jerry requires BPM in the prompt text (e.g., "120bpm drum loop")
- Carey needs explicit `bpm` parameter
- Gary inherits BPM from the audio you feed it — no explicit BPM param needed

## Carey Lego Mode: Input Length Matters

Lego mode works best with **2+ minutes** of input audio. For shorter inputs, the wrapper automatically engages **loop assist** which tiles the audio to reach the minimum length. You'll get better results by chaining Gary continuations first to build up length before sending to Carey.

## Service-Specific Skills

For detailed endpoint documentation, parameter references, and examples, load the individual service skill:
- `jerry.md` — stable-audio endpoints and prompt craft
- `gary.md` — MusicGen continuation, retry, transform
- `foundation.md` — structured synthesis with randomize + generate
- `carey.md` — ACE-Step lego vocals + complete continuation
- `terry.md` — MelodyFlow transform (via Gary)

## Queue Behavior

All services are protected by a GPU queue. If the system is busy, your request will be queued and you'll see `queue_status` in poll responses with your position and estimated wait time. Just keep polling — the system is FIFO and will get to your request.
