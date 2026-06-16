# SA3 — Stable Audio 3 API

Stable Audio 3 medium model with async text-to-audio, BPM-aware loop generation,
promptable key/scale, audio continuation, audio transformation, and blendable LoRA adapters.

Base: `https://g4l.thecollabagepatch.com/sa3`

All SA3 generation endpoints are **async**. Submit one request, get a `session_id`,
then poll `/sa3/poll_status/{session_id}` until `status: "completed"` and
`audio_data` is present.

## What SA3 Is Good For

SA3 is another branch in the agentic music pipeline, not a replacement for Jerry,
Gary, Carey, Foundation, or Terry.

| Need | Consider SA3 when... |
|------|----------------------|
| BPM/key-locked source material | You want a 4/8/16/32-bar loop with a richer SA3/LoRA color that follows the song BPM and key/scale. |
| Style-forward generation | You want to use or blend SA3 LoRAs from `/sa3/loras`. |
| Continuation | You want the source audio kept and new audio generated after it. |
| Transformation | You want same-length audio-to-audio restyling with LoRA support. |
| Cross-model chaining | You want to move between SA3, Gary, Carey, Jerry, Terry, and Foundation based on the audio returned. |

Do not treat SA3 as a fixed recipe. It works best as one possible next move in a
branching workflow.

## Queue Discipline

SA3 has its own GPU queue lane with concurrency 1. Agents should:

- Submit one SA3 request at a time.
- Poll every 3-5 seconds.
- Wait for completion before feeding the result into another model.
- Store `audio_data`, `session_id`, `seed`, `prompt`, selected LoRAs, and any `meta` returned by polling.
- Avoid parallel alternate takes unless the user explicitly asks for them.

## Discovery Endpoints

### GET /sa3/health

Health, CUDA state, loaded model state, and current LoRA registry.

### GET /sa3/loras

Returns the live LoRA registry. Current remote backend LoRAs at the time this guide was
updated:

| LoRA | Character |
|------|-----------|
| `kev` | Heavy, grungy, hip-hop-influenced electronica with guitars and prog-rock influence. |
| `koan` | High-quality dubstep/neurofunk direction from the Koan-style training data. |
| `keygen` | 8-bit/chiptune, synthwave, game, and hip-hop-adjacent material. |
| `succession` | Orchestral/dramatic soundtrack color, useful especially in blends. |

Names are backend adapter ids. Discover them at runtime instead of assuming the list is
static.

### GET /sa3/prompts

LoRA-aware dice prompts. Use this like the human interface's smart prompt button.

```bash
curl -s https://g4l.thecollabagepatch.com/sa3/prompts
curl -s "https://g4l.thecollabagepatch.com/sa3/prompts?lora=kev"
curl -s "https://g4l.thecollabagepatch.com/sa3/prompts?lora=kev&lora=keygen"
```

No `lora` returns generic prompt pools. One or more `lora` query values returns a pool
that includes the selected LoRA distributions where available and generic defaults for
other buckets. Pick a prompt from the returned `prompts.dice` bucket that matches the
role you need, then append BPM/key yourself.

Do not hardcode prompt lists. The backend prompt pools are live-editable.

## LoRA Usage

Prefer the modern `loras` array instead of legacy single-LoRA fields:

```json
{
  "loras": [
    {"name": "kev", "strength": 0.8, "interval_min": 0.0, "interval_max": 1.0},
    {"name": "keygen", "strength": 0.35, "interval_min": 0.0, "interval_max": 1.0}
  ]
}
```

Rules of thumb:

- Omit `loras` or send an empty array when you want the base model.
- Use `GET /sa3/loras` before naming adapters.
- Blending several LoRAs at different strengths is often more interesting than maxing one adapter.
- Send every active LoRA to `/sa3/prompts` so the dice prompt can reflect the chosen blend.
- Treat LoRA strengths as creative controls, not correctness flags. Listen/inspect before deciding the next step.

## Prompt Responsibilities

SA3 is controllable by prompt for both BPM and key/scale, similar to ACE-Step. Treat
`bpm` and `key_scale` as part of the global song state and carry them through SA3,
Foundation, Carey, Jerry prompts, and Gary descriptions.

SA3 prompt pools are usually genre/vibe text. The agent should compose the final prompt
with the chosen session BPM and key/scale:

```text
<prompt from /sa3/prompts or user>, <BPM> bpm, <key> <scale>
```

Examples of key/scale text: `A minor`, `C major`, `F# minor`, `D dorian`. Keep the
same spelling across the song unless the user asks for modulation. For `/sa3/generate/loop`,
the BPM controls bar math; the key/scale steers the musical content.

Keep prompts compact. SA3 is token-limited and LoRA-trained prompts tend to be concise.
Do not duplicate BPM/key if the prompt already contains them.

## Endpoints

### POST /sa3/generate

Text-to-audio. Use when you want an arbitrary duration rather than a bar-exact loop.

| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `prompt` | string | yes | - | Include global BPM and key/scale unless intentionally freeform. |
| `duration` | float | no | `30` | Seconds, max server-limited. |
| `negative_prompt` | string | no | `"low quality"` | Keep default unless avoiding something specific. |
| `seed` | int | no | `-1` | Store the concrete seed returned. |
| `loras` | array | no | none | Blendable LoRA controls. |
| `steps` | int | no | `8` | Advanced; leave default for most agent workflows. |
| `cfg_scale` | float | no | `1.0` | Advanced; leave default. |

### POST /sa3/generate/loop

Bar-aligned loop generation. This is the main SA3 source-material endpoint.

| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `prompt` | string | yes | - | Include global BPM and key/scale; BPM may also be passed in `bpm`. |
| `bars` | int | no | `8` | Accepts `4`, `8`, `16`, `32`. |
| `bpm` | float | no | parsed from prompt | Pass explicitly if the prompt is ambiguous. |
| `seed` | int | no | `-1` | Store returned seed. |
| `loras` | array | no | none | Optional LoRA blend. |

The output is sample-exact to the requested bar length at 44.1 kHz stereo.

### POST /sa3/transform

Same-length audio-to-audio style transfer. Use this when you have source audio and want
SA3 to restyle it without changing its duration.

| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes | - | Base64 WAV. |
| `prompt` | string | yes | - | Target style; include global BPM and key/scale to preserve song state. |
| `strength` | float | no | `0.9` | `0.6` retains more source; `0.9` transforms strongly. |
| `seed` | int | no | `-1` | Store returned seed. |
| `loras` | array | no | none | Optional LoRA blend. |

Practical guidance: `0.6-0.9` is the useful transformation zone. Lower/subtler
settings can retain more of the source but may leave artifacts. If a subtle transform
has the right idea but sounds rough, a later Carey cover can be a useful cleanup/polish
step.

### POST /sa3/continue

Continue existing audio. Output length is source duration plus `continuation_seconds`.

| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `audio_data` | string | yes | - | Base64 WAV source. |
| `prompt` | string | yes | - | Direction for the new section; include global BPM and key/scale. |
| `continuation_seconds` | float | no | `8.0` | New audio after the source. |
| `continuation_mode` | string | no | `"inpaint"` | `"latent_prefix"` is also available. |
| `continuation_tail_pad` | float | no | `6.0` | Higher can be better for seamless chaining. |
| `seed` | int | no | `-1` | Store returned seed. |
| `loras` | array | no | none | Optional LoRA blend. |

Use `latent_prefix` when you want the continuation to inherit the source tempo/timbre
more strongly. Use the same source and seed to compare modes.

## Polling

Poll the returned `session_id`:

```bash
curl -s https://g4l.thecollabagepatch.com/sa3/poll_status/$SESSION_ID
```

Completion response includes `audio_data` and `meta`. `meta` can include exact loop,
transform, or continue timing details. Save it with the take.

## Chaining Guidance

SA3 is useful at the beginning, middle, or end of a chain:

- Start with SA3 when LoRA color or bar-exact loops are central to the prompt.
- Use SA3 continuation when a loop or section should grow while retaining its source.
- Use SA3 transform when a section has good structure but needs a different style or LoRA blend.
- Use Carey cover after SA3 when the result needs cleaner full-track polish or ACE-Step LoRA character.
- Use Gary after SA3 when MusicGen continuation/model switching is the interesting next branch.

Cross-model LoRA relationships can be musically useful. If similarly themed LoRAs exist
across SA3, Gary, or Carey, an agent may choose to move between those models while
keeping the style family related. Do this as a creative option, not a required pattern.

## Common Caveats

- SA3 is async, unlike Jerry.
- LoRA names are dynamic; discover them.
- Always save returned `seed` and `meta`.
- Keep the global BPM and key/scale explicit in prompts. For loops, BPM must be in `prompt` or `bpm`; key/scale stays prompt text.
- For transforms, do not assume lower strength is always cleaner. Listen/inspect and consider a cleanup pass if needed.
- Avoid backend/admin endpoints such as `/reload`, `/load`, and `/unload` unless Kev explicitly asks.
