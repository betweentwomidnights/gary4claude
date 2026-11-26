# gary4claude — Agentic Music Production

Generate, continue, transcribe, arrange, transform and combine music through the
Gary service family. Treat each returned take as a musical decision point.
Choose a next model from what the song needs, not a mandatory model order.

## The Cast

| Name | Reference | Useful next move |
|------|-----------|------------------|
| Jerry / SAOS | [jerry.md](jerry.md) | Short source audio, BPM-aligned loops, finetunes such as jerry_grunge when discovered |
| SA3 | [sa3.md](sa3.md) | Bar-exact loops, continuation, transform, independent LoRA strength lanes and prompts |
| Gary | [gary.md](gary.md) | MusicGen continuation, retries and model switching |
| Foundation | [foundation.md](foundation.md) | Structured synth/sample material with randomizable timbre |
| Carey | [carey.md](carey.md) | Text2music, Continue, Complete accompaniment, cover, lego stems and LoRAs |
| Yuey | [yuey.md](yuey.md) | YuE2 generation, audio-to-score remix, LLM-editable ABC, score or audio continuation |
| Terry | [terry.md](terry.md) | MelodyFlow audio style transfer through Gary |

## Execution Profile and Routing

Default to **hosted** `https://g4l.thecollabagepatch.com`. Services are already
running. For explicit local/headless requests read [local.md](local.md) before
using the lifecycle controller and direct localhost URLs. Do not silently switch
profiles or combine local/hosted URLs. Local controller modernization and training
are separate work from this hosted inference update.

| Public path | Service |
|-------------|---------|
| `/audio/*` | Jerry |
| `/sa3/*` | SA3 |
| `/carey/*` | Carey |
| `/yuey/*` | Yuey |
| `/foundation/*` | Foundation |
| `/api/juce/*`, default routes | Gary; Terry transforms through Gary |

Discover model ids, adapters and capabilities before relying on them. Do not
hardcode a registry from these docs as if it were permanent. A request that
silently ignores an unsupported automation field is not a successful automation
render. Do not operate backend admin, lifecycle or training endpoints in a hosted
inference session.

For Python HTTP clients send `User-Agent: gary4claude/1.0`. During review the
public edge returned 403 to default urllib requests, while that explicit header
and ordinary curl requests worked. Treat an HTTP error as a transport failure,
not a queued generation, and do not silently switch to private routing.

## Polling Has More Than One Contract

| Service/operation | Submit result | Poll | Completion artifact |
|-------------------|---------------|------|---------------------|
| Jerry | Synchronous audio response | None | Base64 `audio` |
| SA3, Gary, Foundation, Terry | `session_id` | Service-specific status route | Base64 `audio_data` |
| Yuey generation/cover/continuation | `session_id` | `/yuey/poll_status/ID` | Base64 `audio_data`, ABC, MIDI, metadata |
| Yuey plan/transcribe | `session_id` | `/yuey/poll_status/ID` | ABC/MIDI, **no audio required** |
| Yuey score transform | Immediate JSON | None | Edited ABC |
| Current Carey `/synth` | `id` | `/carey/job?id=ID` | On `done`, fetch `&result=1` and extract binary audio from multipart/mixed |

Poll async operations every 3–5 seconds. Save the submission and concrete seed,
wait for terminal success/failure, then save the actual artifacts. An id is not
a song. Stop on explicit failure/cancellation or HTTP errors; do not poll forever
or submit a duplicate because loading/queue progress is slow. For an explicitly
rejected submission or a confirmed terminal job failure that is retryable, wait
30–60 seconds before one deliberate retry. A timeout with unknown submission
outcome is not confirmation that no job exists.

Carey legacy `/cover`, `/complete`, `/lego` use `task_id`, legacy polling and
base64 audio. Those still exist, but use [carey.md](carey.md)'s new contract for
current work. **Legacy `/complete` is Continue, not today's Complete.** Never
apply the other services' base64 polling loop to a Carey native job.

Yuey score-only jobs finish without audio. Save their scores/MIDI before asking
for a render. Its finished results expire after five minutes; consume/save the
response promptly. Read each service reference for exact status names and fields.

Read terminal status before extracting large payloads. Once the response says
`completed` (or Carey says `done`), leave the polling loop and handle its result
as a separate step. Do not remove `audio_data` and then test its presence as the
loop's stop condition; that can keep polling a job that already finished.
Score-only Yuey jobs never need `audio_data` to be terminal.

Before reporting completion or leaving a stage, confirm that the local polling
process has exited. An exec tool returning a running session id means that
client process is still alive, even if audio has already been saved. If a broken
loop remains after known terminal success, stop only that owned polling process;
do not leave it repeatedly downloading a completed result or kill unrelated
Python/model processes. Record the final attempt count after cleanup.

Python client examples use the standard library. Do not assume `requests` is
installed; check availability or use the documented urllib/curl paths.

## One Heavy Request at a Time

For a song chain, submit exactly one generation/transform/transcription at a
time. Wait, inspect and save it, then choose the next branch. Parallel alternate
takes require an explicit user request. Local/headless sessions also require
ensuring the intended runtime and releasing agent-owned GPU services between
stages, according to local.md; do not kill arbitrary processes.

### Recover an Accepted Job Instead of Submitting Again

A successful POST creates a job even if your local script subsequently fails
while naming a file, parsing a response or writing audio. Preserve the raw
submission response and id immediately, in a unique per-job directory. Keep
submission separate from polling and result processing so you can rerun the
latter stages without another POST.

| Failure point | Recovery |
|---------------|----------|
| Local error after an id was returned | Read the saved response/id; poll or fetch that same job |
| Status or result GET failed | Retry the GET for the existing id; do not regenerate the music |
| Download saved, local WAV/MIME parsing failed | Reprocess the saved bytes; fetch the same result if necessary |
| POST timed out and acceptance is unknown | Inspect saved response/logs for an id and reconcile the outcome before submitting again; report the uncertainty if it cannot be resolved |
| Explicit submission rejection or confirmed terminal failure | Correct the cause; use the documented bounded retry policy if appropriate |

An identical payload and seed do **not** deduplicate a request. Do not rely on
server FIFO serialization as a reason to submit while another job's outcome is
unknown. Preserve every accidental job id and wait for known terminal states
before continuing the chain; cancellation may still drain remotely. Do not
overwrite the first job's id, response or output when recovering.

Keep a small session record:

| State | Why |
|-------|-----|
| BPM, meter, key/scale | Shared musical grid across services |
| Target duration and vocal intent | Know when the request is satisfied |
| Source/take filenames and lineage | Branch/revert without overwriting accepted audio |
| Actual sample rate/channels/length/peak | Avoid timing and mixing errors |
| Exact request, seed, ids and metadata | Recall and debug a take |
| Base/lane prompts, envelopes, blend settings | Reproduce SA3 automation |
| Original/edited ABC, MIDI, score tempo/bar count | Continue/edit Yuey without losing structure |
| Lyrics | Reuse exact words when covering an existing performance |
| Crop offsets and stem alignment | Keep audio, scores and local mixes traceable |

Inspect metadata and WAV properties with the bundled helpers. If listening is
available, audition musical quality and transitions. Metadata checks cannot tell
you a vocal is in tune or a continuation sounds good; state that limit when
listening is unavailable.

## Choose the Next Adventure

| What the song needs | Possible next branch |
|---------------------|----------------------|
| Initial material | Jerry/SA3/Foundation; Carey text2music; Yuey new generation or plan-first |
| More duration with audio context | Gary, SA3 Continue, Carey Continue (`repaint`), Yuey audio continuation |
| More duration from editable composition | Transcribe to Yuey ABC, edit if useful, extend with `abc_prefix` |
| Different style at current length | SA3 Transform with static LoRAs or lanes, Carey Cover, Terry for a short excerpt |
| Harmony/melody edits before a remix | Yuey transcription → edit ABC → render with a new style |
| Accompaniment around a stem | Carey Complete (`complete`), same duration |
| A vocal/instrument layer to combine locally | Carey Lego (`lego`) → inspect/align → mix |
| A tailored progression or arrangement | Write/edit Yuey ABC and render it |
| A developed piece meeting the request | Deliver; do not chain extra models just because they exist |

Examples of possible paths:

```text
Jerry jerry_grunge 8s → SA3 Continue with lanes → crop ending → SA3 Continue with recalculated lane times → Carey Lego XL-base/billie vocals → local mix
SA3 8-bar loop → Yuey transcribe → edit/continue score → SA3 Transform with independent lane prompts
Yuey generation → edit chords in ABC → re-render → Carey Cover
Carey text2music → Yuey audio continuation → deliver
Foundation keyed stem → Carey Complete with drums | bass → SA3 Transform
```

These are choices, not instructions to execute every stage. In particular,
Yuey cannot continue an SA3 **score** that SA3 never produced: transcribe its
WAV first, or use Yuey's audio continuation endpoint, which derives its own
score and audio prefix.

## Duration: Keep the Units Straight

- For 4/4, `seconds_per_bar = 240 / bpm`; eight bars at 120 BPM are 16 s.
- Carey Continue uses `task_type: repaint`, `duration` = final total seconds,
  `repainting_start` = measured source seconds, `repainting_end` = target.
  A 32-second seed continued to 120 seconds adds about 88 seconds.
- Carey Complete/Lego/Cover normally use the measured source duration.
  Complete adds parts, not time.
- SA3 `continuation_seconds` is added seconds. Lane envelopes are in absolute
  seconds from the source start; automate a new tail starting at source duration.
- Yuey score continuation `target_bars` is total score bars, whereas audio
  continuation `continuation_bars` is added bars. Render tails can outlast the
  nominal score. Save actual metadata and trim only intentionally.
- A cropped waveform no longer automatically matches its old Yuey score/MIDI.
  Re-transcribe the crop, or edit/retime the score deliberately before reuse.

For a full-song request without a duration, target 120 seconds. Grow the song
using an appropriate continuation path within service limits. A tiled two-minute
loop is context material, not automatically a developed song. Terry commonly
transforms about a 30-second section; use it before full-song growth or on an
intentional excerpt, not as an assumed full-length round trip.

Polish is an optional musical decision. Carey Cover can restyle/refine an
arrangement, and SA3 Transform can add same-length style or LoRA color; choose
one when that change serves the brief or an identified issue. A full-duration
generation or requested lego-vocal mix may already be the final product.
Without audition, do not claim a cover improved the music or invoke it simply
because the instructions offer that endpoint. No model or number of stages is
required. Stop when the request is satisfied.

## Audio and Score Handoffs

Most Gary services accept/return base64 WAV. Jerry's response uses `audio`;
other base64 services generally use `audio_data`. Carey `/synth` takes actual
WAV file parts and returns multipart binary audio. Save/decode to a real WAV
between services, then encode or upload according to the next service's contract.
Do not base64-encode MIME boundaries or save a multipart response as WAV.

Prefer Yuey `audio_format: wav` for cross-model work. If choosing advertised
FLAC transport, decode it before a WAV-only helper/service; inspect magic bytes
and the returned `audio_format`. A score/MIDI is a symbolic artifact, not base64
audio. Keep all three when available.

Use `<skill-dir>` as the absolute directory resolved by SKILL.md. Bundled helpers:

```bash
python "<skill-dir>/scripts/wav_info.py" seed.wav
python "<skill-dir>/scripts/trim_wav.py" take.wav cropped.wav --duration 16s
python "<skill-dir>/scripts/tile_wav.py" drums.wav drums_8bar.wav --bars 8 --bpm 174
python "<skill-dir>/scripts/mix_wavs.py" drums_8bar.wav synth_8bar.wav -o seed.wav --gain 0.8 --gain 0.7 --normalize
python "<skill-dir>/scripts/gary_preflight.py" seed.wav --prompt-duration 6
python "<skill-dir>/scripts/base64_wav.py" encode seed.wav -o seed.b64
```

Check each helper's `--help` for trimming and length options. The mixer requires
matching encoding/sample rate/channels/sample width; convert first when needed.
It sums with floating-point headroom and `--normalize` applies a final 0.95
sample peak target. Align and audition stems before mixing; level checks do not
prove isolation or musical fit. Keep source stems, a dry backing, and final mix.

Gary accepts `prompt_duration: 2` for short loops; use 6 when the WAV is long
enough and that context is useful. Run preflight or tile the seed intentionally,
rather than submitting an input shorter than prompt_duration.

## Prompt and Adapter Responsibilities

Keep the same intended BPM/key across the chain, while respecting each API:

- Jerry: include BPM in loop prompt; discover SAOS finetune/model ids.
- SA3: discover `/sa3/loras` and `/sa3/prompts`; append BPM/key to the base and
  every nonempty lane prompt. Time curves separately from denoising intervals.
- Foundation: split `key_root`/`key_mode`; use `host_bpm` for requested tempo.
  Its native grid choices (100, 110, 120, 128, 130, 140, 150) may be stretched.
- Gary: tempo comes from audio; carry style/BPM/key in `description` if useful.
- Carey: discover `/carey/props`; use `keyscale`, `bpm`, exact `synth_model`,
  `adapter`, and adapter training captions. Lego/Complete require base.
- Yuey: put tempo/key/meter in `planning` or the score, and describe sound in
  `style`. A recovered score's tempo/key may differ from your original intent;
  inspect before reusing it.

LoRA names are service-specific ids. A similarly named adapter on SA3 and Carey
can be a useful style relationship, but do not assume compatible weights or
interchangeable request fields. Keep vocals wordless/phonetic unless words are
wanted; once written lyrics are used, retain the exact text for later covers.

## Scope and Verification

This update is for hosted inference. Do not train LoRAs or change deployments.
The documentation was traced through gary4juce, native model source and live
Spark discovery on 2026-11-26. See the model guides for evidence and limits.
Five initial fresh Luna trials are recorded in
[the evaluation report](evaluations/luna-2026-11-26.md), including client recovery
and polling errors found despite successful HTTP responses. Those trials do not
cover every mode. Further targeted trials and musical audition remain necessary;
source review and HTTP success alone do not validate the sound of an example.
