# Jerry — stable-audio API

Text-to-audio generation with BPM-aware looping. Supports the base stable-audio-open model and community finetunes from HuggingFace. Jerry is **synchronous** — audio is returned directly in the response (no polling needed).

Base: `https://g4l.thecollabagepatch.com/audio`

## Agent Defaults

For autonomous song-building, Jerry is usually best used to make short, clean, BPM-locked source loops that can be tiled, mixed, or continued by Gary/Carey.

Choose the model path first:

| Need | Use | Prompt source | Suggested settings |
|------|-----|---------------|--------------------|
| Clean drums from standard SAOS | `/audio/generate/loop` with `loop_type: "drums"` | Short freeform prompt with BPM | `steps: 8`, `cfg_scale: 1.0` |
| Clean instrument/bass/synth loop from standard SAOS | `/audio/generate/loop` with `loop_type: "instruments"` | Short freeform prompt with BPM | `steps: 8`, `cfg_scale: 1.0` |
| A finetune's learned style | Switch/load finetune, then `/audio/models/prompts` | Pick from `prompts.dice` | `steps: 50`, `cfg_scale: 6.0` is reasonable |

Always include the BPM in the prompt, but do not prompt for loop mechanics such as "seamless", "perfect loop", "4-bar loop", or "8-bar groove". The loop endpoint handles bar sizing, looping, and crossfading. Use the `bars` field when you need a specific length.

For drums, set `loop_type: "drums"` instead of relying only on words like "drums" in the prompt. The endpoint appends drum-loop intent if needed and automatically uses negative conditioning against melody, harmony, pitched instruments, vocals, and singing. For non-drum material, set `loop_type: "instruments"` so the endpoint uses negative conditioning against drums and percussion.

## Using Finetunes and Smart Prompts

Jerry supports finetune models from HuggingFace. Each finetune has a `prompts.json` in its repo that contains curated prompts designed to trigger the finetune's trained distribution — these produce **much better results** than freeform prompts.

**Recommended workflow with a finetune:**

1. **Switch to the finetune:**
```bash
curl -s https://g4l.thecollabagepatch.com/audio/models/switch \
  -H "Content-Type: application/json" \
  -d '{"model_type": "finetune", "finetune_repo": "thepatch/jerry_grunge", "finetune_checkpoint": "jerry_grunge_e32_s2000.ckpt"}'
```

2. **Get the finetune's curated prompts:**
```bash
curl -s https://g4l.thecollabagepatch.com/audio/models/prompts
# Response includes prompts.dice with categories like "generic", "drums", "instrumental"
# Pick a prompt from the appropriate category — these are tuned for this finetune
```

Treat `prompts.dice` like Carey's caption dice button: inspect the categories, choose the category matching the role you need, and use one returned prompt as the core prompt. Common categories are `generic`, `drums`, and `instrumental`, but the exact prompt text comes from the active finetune.

3. **Generate using a curated prompt** (add BPM for loops):
```bash
curl -s https://g4l.thecollabagepatch.com/audio/generate/loop \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "<prompt from prompts.json>, 174bpm",
    "loop_type": "drums",
    "bars": 4,
    "steps": 50,
    "cfg_scale": 6.0,
    "return_format": "base64"
  }'
```

Use `loop_type: "drums"` when you picked a drum prompt, and `loop_type: "instruments"` when you picked an instrumental, bass, synth, guitar, or texture prompt.

You can also pass `finetune_repo` and `finetune_checkpoint` directly in the generate request without switching first.

## Endpoints

### POST /audio/generate

Generate audio from a text prompt.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `prompt` | string | yes | — | Text description of the audio |
| `seconds_total` | int | no | model max (~12s) | Duration in seconds, clamped to model capability |
| `steps` | int | no | 8 | Diffusion steps (1-250). 8 for fast, 50-100 for quality |
| `cfg_scale` | float | no | 1.0 | Classifier-free guidance (0-20) |
| `negative_prompt` | string | no | — | What to avoid |
| `return_format` | string | no | `"file"` | `"file"` (WAV download) or `"base64"` (inline) |
| `model_type` | string | no | `"standard"` | `"standard"` or `"finetune"` |
| `finetune_repo` | string | no | — | HuggingFace repo (e.g., `"thepatch/jerry_grunge"`) |
| `finetune_checkpoint` | string | no | — | Checkpoint filename |

### POST /audio/generate/loop

Generate a BPM-locked seamless loop. This is the **primary endpoint for agents** — handles bar calculation and crossfading automatically.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `prompt` | string | yes | — | **Must include BPM** (e.g., "120bpm drum loop") |
| `loop_type` | string | no | `"auto"` | `"drums"`, `"instruments"`, or `"auto"`; prefer explicit values for source loops |
| `bars` | int | no | auto-calculated | Number of bars (1, 2, 4, 8) |
| `style_strength` | float | no | 0.8 | Style adherence |
| `steps` | int | no | 8 | Diffusion steps; use 8 for standard SAOS, often 50 for finetunes |
| `cfg_scale` | float | no | 6.0 | Guidance scale; explicitly use about 1.0 for standard SAOS loops unless you want stronger prompt pressure |
| `seed` | int | no | -1 | -1 for random |
| `return_format` | string | no | `"file"` | `"file"` or `"base64"` |
| `model_type` | string | no | `"standard"` | `"standard"` or `"finetune"` |
| `finetune_repo` | string | no | — | HuggingFace repo |
| `finetune_checkpoint` | string | no | — | Checkpoint filename |

**Example — drum loop with standard model:**
```bash
curl -s https://g4l.thecollabagepatch.com/audio/generate/loop \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "hard hitting dnb break, 174bpm, punchy kicks, tight snares",
    "loop_type": "drums",
    "bars": 4,
    "steps": 8,
    "cfg_scale": 1.0,
    "return_format": "base64"
  }'
```

**Example — instrument loop with standard model:**
```bash
curl -s https://g4l.thecollabagepatch.com/audio/generate/loop \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "deep techno bass, 140bpm, dark, rubbery, syncopated",
    "loop_type": "instruments",
    "bars": 4,
    "steps": 8,
    "cfg_scale": 1.0,
    "return_format": "base64"
  }'
```

### POST /audio/models/switch

Load a model (standard or finetune). The model stays cached for subsequent generate calls.

**Parameters (JSON body):**
| Param | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `model_type` | string | yes | — | `"standard"` or `"finetune"` |
| `finetune_repo` | string | if finetune | — | HuggingFace repo |
| `finetune_checkpoint` | string | if finetune | — | Checkpoint filename |

### POST /audio/models/checkpoints

List available checkpoints in a HuggingFace repo.

**Parameters:** `{"finetune_repo": "thepatch/jerry_grunge"}`

**Response:**
```json
{"success": true, "repo": "thepatch/jerry_grunge", "checkpoints": ["jerry_grunge_e32_s2000.ckpt", "..."], "count": 3}
```

### GET /audio/models/prompts

Get curated prompts for the active (or specified) model. These come from the finetune's `prompts.json` on HuggingFace. **Using these prompts produces much better results than freeform text** because they match the finetune's training distribution.

**Query params (all optional):**
| Param | Notes |
|-------|-------|
| `key` | Specific model cache key |
| `repo` | Filter by repo name |
| `checkpoint` | Filter by checkpoint |
| `prefer` | `"active"` (default), `"finetune"`, or `"recent"` |

**Response:**
```json
{
  "success": true,
  "model_key": "finetune:thepatch/jerry_grunge:jerry_grunge_e32_s2000.ckpt",
  "type": "finetune",
  "prompts": {
    "version": 1,
    "dice": {
      "generic": ["grunge guitar riff, distorted, raw", "..."],
      "drums": ["heavy grunge drums, loose hi-hats, 130bpm", "..."],
      "instrumental": ["grunge bass and guitar, sludgy, 120bpm", "..."]
    }
  }
}
```

Pick a prompt from `prompts.dice` in the appropriate category, then append your BPM for loop generation.

### GET /audio/models/status

Returns current model state, loaded checkpoints, and available models.

### GET /audio/health

Health check.

## Prompt Tips

- **Always include BPM** in loop prompts: `"140bpm"`, `"at 120 bpm"`, etc.
- Use `loop_type: "drums"` for drum loops; it automatically applies negative prompting to keep melody, harmony, pitched instruments, vocals, and singing out.
- Use `loop_type: "instruments"` for bass, synth, guitar, keys, pads, and textures; it automatically applies negative prompting to keep drums and percussion out.
- **Use curated prompts from `/models/prompts`** when using finetunes — freeform prompts may miss the trained distribution entirely
- For finetunes, choose a prompt from the relevant `prompts.dice` category before generating. Do not invent a prompt until you have checked the dice prompts.
- Be specific about instruments: `"acoustic drum kit"` vs `"808 drum machine"`
- Genre terms work well: `"dnb"`, `"lo-fi hip hop"`, `"ambient techno"`
- Describe texture: `"warm"`, `"gritty"`, `"ethereal"`, `"distorted"`
- Do not spend prompt tokens asking for a seamless/perfect loop or restating the bar count. The API handles loop construction from `bars` and BPM.
- Jerry's model max duration is ~12 seconds — for longer audio, generate a loop then feed it to Gary for continuation

## Important Caveats

- Response format matters: use `"return_format": "base64"` when you need to pass audio to another service
- `/generate/loop` requires BPM in the prompt — it will 400 if missing
- `/generate/loop` only accepts `bars` values of 1, 2, 4, or 8; if omitted, the API chooses the longest bar count that fits the active model at the detected BPM
- The endpoint's `loop_type` negative prompting is more reliable than trying to steer purity only through prompt wording
- Jerry is synchronous — no polling. The request blocks until audio is ready (typically 5-15 seconds)
- First generation with a finetune may be slow (model download from HuggingFace). Subsequent calls use the cache.
