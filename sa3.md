# SA3 — Stable Audio 3 API

Stable Audio 3 medium model with async text-to-audio, BPM-aware loop generation,
promptable key/scale, audio continuation, audio transformation, and blendable LoRA adapters.

Hosted base: `https://g4l.thecollabagepatch.com/sa3`

Local base: `http://127.0.0.1:8006`. Ensure it with `python "<skill-dir>/scripts/gary4local.py" ensure sa3 --json`. Remove the hosted `/sa3` prefix from local paths. Resolve `<skill-dir>` from `SKILL.md`; see `local.md`.

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

- Send `loras: []` when you want the unadapted base model; omission can select a backend default adapter.
- Use `GET /sa3/loras` before naming adapters.
- Blending several LoRAs at different strengths is often more interesting than maxing one adapter.
- Send every active LoRA to `/sa3/prompts` so the dice prompt can reflect the chosen blend.
- Treat LoRA strengths as creative controls, not correctness flags. Listen/inspect before deciding the next step.

## LoRA Automation Lanes: Arrange Changes Over Time

`lora_lanes` gives each LoRA its own strength curve and optional prompt. The
top-level `prompt` describes the shared musical scene; a lane prompt describes
the character that lane contributes. An omitted/empty lane prompt inherits the
base prompt. A lane prompt is not a separate song or an isolated audio stem.
The model renders one jointly generated result.

Before using lanes, require `GET /sa3/health` → `capabilities.lora_lanes: true`.
An older server can ignore unknown fields and produce audio with no automation;
do not silently accept that as a successful lane render. The hosted health
checked on 2026-11-26 advertises 8 lanes, 256 points per lane, and only the
`velocity` envelope mode. Discover current limits and adapter names at runtime.

| Control | Meaning |
|---------|---------|
| `lora_lanes[].loras` | Adapters local to that lane; normally one discovered name with `strength: 1.0` |
| `lora_lanes[].envelope` | Ordered `[seconds, amount]` pairs; linear between points, held constant outside endpoints |
| `lora_lanes[].prompt` | Optional lane-specific conditioning; append the same session BPM and key as the base prompt |
| Top-level `loras` | Static adapters shared by the base and all lane passes |
| `lane_isolation` | Separates sections with different lane amounts during denoising; 0 disables it |
| `lane_isolation_until` | Sigma threshold; **0 runs isolation through the last step** |
| `lane_average_until` | Above this sigma threshold, use each lane's average strength to establish a shared arrangement; 0 disables averaging |

The curve multiplies the lane adapter's `strength`. With `strength: 1.0`, curve
amounts directly specify the intended strength (the UI uses 0–2). Do not also
put an automated adapter in top-level `loras`: that applies a shared adapter
even where its lane is zero. Use `loras: []` for a base model plus automated
adapters. Send an explicit empty list for an intentional unadapted request;
older service defaults can choose a default adapter when fields are omitted.

There are two different axes: envelope times are seconds in the audio, whereas
`interval_min/max`, isolation thresholds and averaging thresholds control
denoising noise levels. `interval_min/max` do not place a LoRA in a song section.
Curve transitions guide timbre/arrangement; self-attention can blend neighboring
sections, so they do not promise a hard audio edit at a sample boundary.

### Example: Eight Bars With Two Independently Prompted Lanes

At 120 BPM in 4/4, one bar is 2 seconds and eight bars last 16 seconds.
After discovery confirms `kev` and `keygen`, send this body to
`POST /sa3/generate/loop`:

```json
{
  "prompt": "instrumental electronic groove, steady drums and deep bass, 120 bpm, A minor",
  "bars": 8, "bpm": 120,
  "seed": 831001, "steps": 8, "cfg_scale": 1.0, "shift": "none",
  "loras": [],
  "lora_lanes": [
    {
      "loras": [{"name": "kev", "strength": 1.0}],
      "prompt": "gritty guitars and heavy syncopated drums, 120 bpm, A minor",
      "envelope": [[0, 0.9], [6, 0.9], [10, 0.15], [16, 0.15]]
    },
    {
      "loras": [{"name": "keygen", "strength": 1.0}],
      "prompt": "chiptune arpeggios and playful digital leads, 120 bpm, A minor",
      "envelope": [[0, 0.1], [6, 0.1], [10, 0.85], [16, 0.85]]
    }
  ],
  "lane_isolation": 1.0,
  "lane_isolation_until": 0.0,
  "lane_average_until": 0.5625
}
```

The opening emphasizes Kev; bars 4–5 crossfade toward Keygen. Choose each lane's
prompt independently, optionally using `/sa3/prompts?lora=<that_lane_name>`.
Use a shared base prompt for tempo, harmony and continuity. Keep every prompt
compact and include the common BPM/key once in each.

### Translate a Musical Plan Into API Time

For 4/4, `seconds_per_bar = 240 / bpm`. Bar 1 starts at 0; bar N starts at
`(N - 1) * seconds_per_bar`. For other meters use
`60 / bpm * numerator * 4 / denominator` when BPM counts quarter notes.

- Generation/loop: curves start at 0 and cover the requested output.
- Transform: curves start at 0 and cover the measured source duration.
- Continue: **time 0 is the start of the retained source**, not the new tail.
  To automate 8 new seconds after an 8-second source, move a local
  `[[0, 0.2], [8, 1.0]]` curve to `[[8, 0.2], [16, 1.0]]`.
  The JUCE client makes this offset explicitly; it draws lanes over only the
  added region. Do not send normalized 0–1 UI positions as API seconds.
- After cropping/replacing a source, measure its new length and recalculate the
  next request's lane offsets. Save every source/take before trimming.

With `shift: "none"` and eight steps, JUCE's blend stops map to:

| Blend | Shared early steps | `lane_average_until` |
|-------|--------------------|----------------------|
| Smooth | 4 | 0.5625 |
| Next | 3 | 0.6875 |
| Next | 2 | 0.8125 |
| Responsive | 0 | 0 |

All four use `lane_isolation: 1`, `lane_isolation_until: 0`. These values follow
`SA3LaneModel.h`'s linear schedule at `steps: 8`, with generation or
continuation starting at sigma 1. **Do not reuse the table unchanged for a
transform, another shift or step count.** JUCE computes the thresholds from
the actual schedule and transform strength. For an initial transform use
`lane_average_until: 0` with the same gentle isolation, or derive thresholds
from that implementation. The current JUCE UI defaults to `logsnr`, so its
actual request thresholds differ from this deliberately linear example.
The raw API defaults leave averaging/isolation off;
send the chosen values explicitly.

Each velocity lane adds a diffusion pass per step; three lanes cost more than
one static blend. Begin with two intentional curves, avoid redundant points,
and add more lanes only for a musical reason. The hosted backend currently
does not advertise the native server's cheaper `layer` mode.

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

For a finished full song, SA3 transform can be the single final polish pass because
it preserves the input duration. Keep the established BPM and key/scale explicit in
the prompt. After a successful final transform, stop rather than automatically
sending the result through another model. If the transform has the right idea but
audible roughness, Carey cover may replace it as the chosen final pass; avoid treating
both as mandatory stages.

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

Use terminal status to exit polling before extracting the audio. For example,
with a previously saved session id, Python's standard library is sufficient:

```python
import base64
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

session_id = "<saved session_id>"
url = f"https://g4l.thecollabagepatch.com/sa3/poll_status/{session_id}"
while True:
    with urlopen(Request(url, headers={"User-Agent": "gary4claude/1.0"}), timeout=120) as response:
        result = json.load(response)
    status = result.get("status")
    if status == "failed" or result.get("success") is False:
        raise RuntimeError(result.get("error", "SA3 job failed"))
    if status == "completed":
        break
    time.sleep(4)

audio = result.get("audio_data")
if not audio:
    raise RuntimeError("Completed SA3 job returned no audio_data")
Path("output.wav").write_bytes(base64.b64decode(audio, validate=True))
metadata = {key: value for key, value in result.items() if key != "audio_data"}
Path("result.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
```

If decoding/writing fails, recover the existing result; do not submit another
generation. Do not use a removed `audio_data` field to decide whether to poll
again. Save to a new take filename instead of overwriting an accepted result.

## Chaining Guidance

SA3 is useful at the beginning, middle, or end of a chain:

- Start with SA3 when LoRA color or bar-exact loops are central to the prompt.
- Use SA3 continuation when a loop or section should grow while retaining its source.
- Use SA3 transform when a section has good structure but needs a different style or LoRA blend, including as the one final same-length polish pass on a full song.
- Use Carey cover after SA3 when the result needs cleaner full-track polish or ACE-Step LoRA character.
- Use Gary after SA3 when MusicGen continuation/model switching is the interesting next branch.

Cross-model LoRA relationships can be musically useful. If similarly themed LoRAs exist
across SA3, Gary, or Carey, an agent may choose to move between those models while
keeping the style family related. Do this as a creative option, not a required pattern.

## Common Caveats

- SA3 is async, unlike Jerry.
- Lanes are capability-gated. Save the exact envelopes, lane prompts and blend settings with the take.
- LoRA names are dynamic; discover them.
- Always save returned `seed` and `meta`.
- Keep the global BPM and key/scale explicit in prompts. For loops, BPM must be in `prompt` or `bpm`; key/scale stays prompt text.
- For transforms, do not assume lower strength is always cleaner. Listen/inspect and consider a cleanup pass if needed.
- Avoid backend/admin endpoints such as `/reload`, `/load`, and `/unload` unless Kev explicitly asks.

## Contract Evidence

Reviewed 2026-11-26: gary4juce `Source/Components/Jerry/SA3Lanes.cpp`,
`SA3LaneModel.h`, and `Source/PluginEditor.Jerry.cpp`; sa3.cpp
`docs/SERVER.md` for lane semantics. Hosted `/sa3/health` was checked through
Spark's existing proxy over SSH and advertises lane support. Native sa3.cpp's
unified `/generate` + `init_path` API differs from the hosted wrapper's
`/transform` and `/continue`; use the hosted endpoints above for this profile.
The musical examples have not yet been auditioned as part of this doc review.
