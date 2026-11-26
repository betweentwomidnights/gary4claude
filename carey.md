# Carey — ACE-Step Inference

Hosted base: `https://g4l.thecollabagepatch.com/carey`.

Use the **ace-server job contract**, shared by acestep.cpp and current
gary4juce. The hosted wrapper implements it alongside legacy routes. Its public
contract is C++ compatible; on Spark it still translates requests to Python
ACE-Step backends internally.

## Choose the Musical Operation

| Intent | `task_type` | Result | Model variant |
|--------|-------------|--------|---------------|
| Generate from text | `text2music` | New music of `duration` seconds | turbo or base; sft only if discovered |
| Continue audio | `repaint` | Source context plus tail, up to the **total** `duration` | turbo or base; sft only if discovered |
| Add accompaniment | `complete` | Regenerated full arrangement at source duration | **base** |
| Add one instrument/vocal stem | `lego` | Generated track to audition and mix with backing | **base** |
| Cover/restyle | `cover-nofsq` | New performance at source duration | turbo or base |

**Naming trap:** legacy HTTP `/carey/complete` means continuation. Current
**Complete** means ACE-Step accompaniment: send `/carey/synth` with
`task_type: "complete"`. Current **Continue** sends `task_type: "repaint"`.

Complete works from a stem (for example, a cappella vocals), with `track` naming
what to add. It regenerates the mix conditioned on that stem; it does not return
only the additions or guarantee an untouched source. Lego generates one new
track in the context of backing audio. Audition for backing bleed before summing;
stem isolation is model dependent. An agent can render and mix lego locally;
a DAW is not required.

## Discover Models, Adapters, and Captions

First `GET /carey/props`. A shortened snapshot checked live on 2026-11-26:

```json
{
  "models": {"dit": ["acestep-v15-xl-base", "acestep-v15-xl-turbo"]},
  "adapters": ["koan", "john", "third_eye", "kev", "billie", "jacob", "crystal", "oliver"],
  "adapter_info": {
    "billie": {"model_family": "xl", "captions": ["<training caption>"]}
  }
}
```

Discover every session. Copy exact ids into `synth_model` and `adapter`.
Remote currently offers XL base and turbo, no SFT. A local GGUF filename is not
a remote model id. Match the adapter's `model_family` to the model. Presence in
`adapters` alone does not prove compatibility with every variant; honor errors
rather than silently dropping it. Lego and Complete require base.

Choose a suitable caption from `adapter_info[adapter].captions`, or write one
when no suitable pool exists. This replaces the legacy caption-dice round trip.

## Transport and Job Lifecycle

1. Save the AceRequest JSON. Choose and save a concrete unsigned 32-bit `seed`
   (0–4294967295) yourself; the service need not echo it.
2. `POST /carey/synth` as `multipart/form-data`: a `request` JSON part and an
   `audio` WAV part for every mode except text2music. Continue/Cover may also
   attach the same source as `ref_audio` for timbre anchoring.
3. Save the returned `{"id":"…"}`. Poll `GET /carey/job?id=ID` every 3–5 seconds.
4. `status: "running"` includes `progress: {stage, step, total}`. A waiting job
   is running with stage `queued`. Loading/encoding can take time; do not resubmit.
5. On `status: "done"`, fetch `GET /carey/job?id=ID&result=1`. This returns
   **multipart/mixed binary**, not JSON/base64. Extract the `audio/*` part;
   native ace-server can also include latent parts, which are not WAV files.
6. Stop on `failed` or `cancelled`; save `error`. A 404 is an unknown/expired
   job. Save each audio artifact before choosing the next model.

Spark accepts one request object, `output_format: "wav16"`, source/reference
files up to 240 seconds and a 256 MiB total upload. Results are 48 kHz stereo
PCM16 WAV, retained one hour after completion or latest fetch. Jobs do not
survive wrapper restart. Do not send batches unless an explicit task requires
and the backend supports them.

`POST /carey/job?id=ID&cancel=1` cancels the client job. Remotely, an already
submitted Python inference can continue while its result is discarded and its
queue lane drains. Cancellation does not necessarily free the GPU immediately.
Progress is not an ETA.

Submit using curl (`curl.exe` in Windows PowerShell):

```bash
curl -sS https://g4l.thecollabagepatch.com/carey/props
curl -sS https://g4l.thecollabagepatch.com/carey/synth \
  --form 'request=<request.json;type=application/json' \
  --form 'audio=@seed.wav;type=audio/wav'
# Omit the audio part for text2music.
curl -sS 'https://g4l.thecollabagepatch.com/carey/job?id=JOB_ID'
```

Do not save the whole multipart body as `output.wav`. After status is done,
extract it with the stdlib MIME parser:

```python
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.request import Request, urlopen

url = "https://g4l.thecollabagepatch.com/carey/job?id=JOB_ID&result=1"
with urlopen(Request(url, headers={"User-Agent": "gary4claude/1.0"}), timeout=120) as response:
    content_type = response.headers["Content-Type"]
    body = response.read()
message = BytesParser(policy=policy.default).parsebytes(
    b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode("ascii")
    + b"\r\n\r\n" + body
)
parts = [p for p in message.walk() if p.get_content_type().startswith("audio/")]
if not parts:
    raise RuntimeError("Carey returned no audio part")
Path("output.wav").write_bytes(parts[0].get_payload(decode=True))
```

## AceRequest Fields

Fields belong inside the `request` part.

| Field | Usage |
|-------|-------|
| `task_type` | One of the tasks above |
| `caption` | Style direction; nonempty for text2music and cover |
| `lyrics` | `""` allows invented/phonetic vocals; `[Instrumental]` requests no vocals |
| `bpm` | Explicit session tempo |
| `keyscale` | e.g. `"A minor"`; not legacy `key_scale` |
| `timesignature` | Numerator string, e.g. `"4"`; not legacy `time_signature` |
| `vocal_language` | e.g. `"en"`; not legacy `language` |
| `duration` | Total output seconds; not legacy `audio_duration` |
| `inference_steps`, `guidance_scale` | Turbo: 8, 1.0. Base: start at 50, 7.0 |
| `seed` | Concrete unsigned 32-bit seed, saved before submission |
| `output_format` | `"wav16"` on current remote wrapper |
| `synth_model` | Exact id from `props.models.dit` |
| `adapter`, `adapter_scale` | Optional discovered LoRA and strength 0–1 |
| `track` | One name for lego; one or more joined with `" | "` for Complete |
| `repainting_start`, `repainting_end` | Continue: measured source seconds and final target seconds |
| `audio_cover_strength` | Complete client sends 1.0 by default; Cover controls source conditioning |
| `cover_noise_strength` | Cover starting-noise proximity; higher keeps closer to source |

Valid tracks: `vocals`, `backing_vocals`, `drums`, `bass`, `guitar`, `keyboard`,
`percussion`, `strings`, `synth`, `fx`, `brass`, `woodwinds`. Use `keyboard`, not
`piano`. The Complete strength slider exists in the client; native ACE-Step's
context-switch mechanism is inactive for this task, so do not promise it acts
like Cover strength.

## Request Examples

Each block is a separate `request.json`. Discover ids first; submit and save
one result before the next. Add the `audio` form part except for text2music.

### Text to Music

```json
{
  "task_type": "text2music",
  "caption": "warm downtempo electronica, deep bass, dusty drums, evolving synths",
  "lyrics": "[Instrumental]",
  "bpm": 120, "keyscale": "A minor", "timesignature": "4",
  "vocal_language": "en", "duration": 120,
  "synth_model": "acestep-v15-xl-turbo",
  "inference_steps": 8, "guidance_scale": 1.0,
  "seed": 831001, "output_format": "wav16"
}
```

No source upload. Client range is 30–240 seconds remotely; wrapper validation
is `0 < duration <= 240`. For a full song with no specified length, target 120.

### Continue a 32-Second Source to 120 Seconds

```json
{
  "task_type": "repaint",
  "caption": "develop the groove into an evolving electronic arrangement",
  "lyrics": "[Instrumental]",
  "bpm": 120, "keyscale": "A minor", "timesignature": "4",
  "vocal_language": "en", "duration": 120,
  "repainting_start": 32, "repainting_end": 120,
  "synth_model": "acestep-v15-xl-turbo",
  "inference_steps": 8, "guidance_scale": 1.0,
  "seed": 831001, "output_format": "wav16"
}
```

Measure the actual source. `duration` is absolute: 32 → 120 adds about 88
seconds. The remote target must exceed source duration by more than one second.
Optionally attach identical `ref_audio`. Inspect the preserved region and join;
do not promise a bit-identical splice.

### Complete: Add Drums and Bass Around a 32-Second Stem

```json
{
  "task_type": "complete", "track": "drums | bass",
  "caption": "intimate alternative pop, restrained drums, warm melodic bass",
  "lyrics": "", "bpm": 120, "keyscale": "A minor",
  "timesignature": "4", "vocal_language": "en", "duration": 32,
  "synth_model": "acestep-v15-xl-base",
  "inference_steps": 50, "guidance_scale": 7.0,
  "audio_cover_strength": 1.0,
  "seed": 831001, "output_format": "wav16"
}
```

Upload the source stem as `audio`. Caption the whole song; `track` names the
additions. Result is a completed arrangement. Do not automatically sum the
source back into it.

### Lego: Vocals Over a 120-Second Backing

```json
{
  "task_type": "lego", "track": "vocals",
  "caption": "intimate breathy alternative pop vocal",
  "lyrics": "", "bpm": 120, "keyscale": "A minor",
  "timesignature": "4", "vocal_language": "en", "duration": 120,
  "repainting_start": 0, "repainting_end": -1,
  "synth_model": "acestep-v15-xl-base",
  "adapter": "billie", "adapter_scale": 0.8,
  "inference_steps": 50, "guidance_scale": 7.0,
  "seed": 831001, "output_format": "wav16"
}
```

Upload backing as `audio`. Prefer a caption from the adapter pool. Keep backing
and returned stem separately; inspect bleed/alignment before combining.

### Cover / Same-Length Polish

Use `task_type: "cover-nofsq"`, a nonempty `caption`, measured source `duration`
and `audio` (optional identical `ref_audio`). Start with
`cover_noise_strength: 0.2`, `audio_cover_strength: 0.3`. A more transformed
branch can try 0.1–0.15 and 0.12 respectively. Base: 50 steps / CFG 7;
turbo: 8 / 1. Keep session BPM/key.

## Lyrics and Stem Assembly

Leave lyrics empty for invented/phonetic vocals unless intelligible words are
requested. Use `[Instrumental]` for no vocals. If lyrics were written for an
earlier stage, save and reuse their exact text when covering that performance.

New `/synth` does **not** loop short sources or trim results. The plugin does
that locally. For lego/Complete, context can help: optionally tile a bar-aligned
seed to at least 32 bars and 120 seconds (whichever is longer), within 240 seconds.
Save the original and trim the result back if intended. Repeated context is not
a developed arrangement.

Inspect WAVs using `wav_info.py`. Match sample rate, channels, sample width and
encoding before mixing; use an available converter such as ffmpeg when needed.
Do not change tempo to fix a sample-rate mismatch. Align to the same source
start; determine and correct any model latency before mixing. Trim/pad
intentionally rather than accepting an unexpected long vocal tail.

```bash
python "<skill-dir>/scripts/mix_wavs.py" backing.wav vocals.wav -o vocal_mix.wav --gain 0.8 --gain 0.7 --length shortest --normalize
python "<skill-dir>/scripts/wav_info.py" vocal_mix.wav
```

The mixer sums with floating-point headroom and normalizes once before encoding;
`--normalize` targets a 0.95 sample peak. This prevents mix-sum clipping; it
cannot repair distortion in a source or guarantee true-peak limiting.

## Legacy and Local Compatibility

Legacy `/carey/cover`, `/carey/complete`, `/carey/lego` and their status routes
still exist. They use `task_id`, base64 `audio_data`, and old fields (`model`,
`lora`, `lora_scale`, `key_scale`, `audio_duration`). Their `/complete` means
continuation; legacy lego vocals can route differently from new base-model lego.
Never mix request/poll contracts. Prefer `/synth` for current inference.

For explicitly local sessions, read [local.md](local.md) and discover the runtime.
Native Carey on port 8003 uses `/synth`, `/job`, `/props` without `/carey`.
Older Python installs can expose only legacy routes. Local lifecycle/controller
modernization is outside this hosted update; do not assume old Python GPU-family
selection applies to native ace-server.

## Contract Evidence

Reviewed 2026-11-26: acestep.cpp `docs/ARCHITECTURE.md`, `tools/ace-server.cpp`;
gary4juce `Source/PluginEditor.Carey.cpp`, `Source/PluginEditorCareyHelpers.h`,
`docs/CAREY_BACKEND_CONTRACT.md`; Spark
`~/gary-backend-spark/ace-step-wrapper/native_api.py`. The running wrapper file
matched the reviewed host file by SHA-256; live `/carey/props` matched discovery.
No generation was submitted for this review. Live metadata was checked through
Spark's existing Caddy listener over SSH and at the public URL. Default Python
urllib requests received 403; curl and urllib with an explicit
`User-Agent: gary4claude/1.0` returned 200. Use that header with Python clients.
