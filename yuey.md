# Yuey — YuE2 Generation, Scores, Remix and Continuation

Hosted base: `https://g4l.thecollabagepatch.com/yuey`.

Yuey can compose a score, render an editable score, transcribe audio and remix
its musical content, or continue using either a symbolic score or encoded audio.
Save both the WAV and score: a score is a new kind of handoff between models.
An SA3/Jerry/Gary result has audio but no Yuey score until transcribed.

## Discovery and Polling

- `GET /yuey/health`: generation/transcription availability,
  `continuation.available`, audio formats, score transforms and length policy.
- `GET /yuey/props`: capabilities/defaults and installed runtime information.
- `GET /yuey/prompts`: `dice.instrumental` and `dice.vocal` style pools.

Every compute request returns `session_id`; poll
`GET /yuey/poll_status/ID` every 3–5 seconds until `completed` or `failed`.
Stages can include loading, transcription, ABC planning, semantic generation,
flow and decode. Progress is a work estimate, not an ETA. Do not resubmit when
planning/loading takes time.

**Completion depends on operation.** `/plan` and `/transcribe` finish with a
score and MIDI, without `audio_data`. `/generate`, `/cover` and `/continue`
finish with base64 `audio_data`, `abc`, `midi_data`, `midi_files` and `meta`.
Requiring audio for a transcription would poll forever. Save artifacts promptly:
finished jobs expire after five minutes. `?consume=1` returns and removes a
finished result; save that response before trying another GET.

Request `audio_format: "wav"` for direct use with the other Gary models and
stdlib WAV helpers. Yuey also advertises FLAC, float WAV and auto, but never
save FLAC bytes with a `.wav` extension or pass them blindly to a WAV-only
service. The completed `audio_format` names the actual container. Input audio
for transcription/cover/continuation can be base64 WAV or FLAC at any rate and
channel count.

## Choose the Next Branch

| Intent | Request | Source fidelity |
|--------|---------|-----------------|
| New piece | `/generate` with style and optional typed `planning` | New score and performance |
| Inspect/edit the plan first | `/plan`, then `/generate` with its `abc` | Same accepted score when rendered |
| Transcribe existing audio | `/transcribe` | Recovered melody/chords, not full source separation or lyric recognition |
| Remix directly | `/cover` with audio and style | Re-performed transcription, not waveform preservation |
| Edit a remix first | `/transcribe` → edit ABC → `/generate` with `abc` | Edited symbolic content |
| Continue from score | `/generate` with `abc_prefix` | Extends score, re-renders source and tail |
| Continue from audio | `/continue` with audio | Encodes source semantic tokens as well as transcribing; reconstructed source plus tail |

Do not claim either continuation preserves the original waveform bit for bit.
Score continuation can change the source's sound considerably. Audio continuation
anchors to more of the source performance/timbre, but is still reconstruction.

## Shared Song Controls

| Field | Meaning |
|-------|---------|
| `style` | Genre, mood, instruments, vocal character and development; aliases exist, prefer `style` |
| `lyrics` | Empty allows invented words/phonetics with vocals on; otherwise retain user/song lyrics |
| `instrumental` | Best-effort no vocals; requires empty lyrics and symbolic mode `melody` or `full` |
| `seed` | Negative/omitted chooses random; store returned concrete seed |
| `audio_format` | Prefer `"wav"` for cross-model chaining |
| `symbolic_mode` | `melody` gives arrangement freedom; `full` follows the full score including chords more closely; `off` ignores symbolic planning |
| `planning` | Typed tempo/key/meter interface for new `/plan` or `/generate` |
| `abc` | Complete score to render; no new planning |
| `abc_prefix` | Existing score/header for the planner to extend |
| `ending`, `target_bars`, `outro_bars` | Musical score-length controls; see below |
| `natural_max_seconds` | Can lower the server's natural score-length ceiling, never raise it |

`planning`, `abc` and `abc_prefix` are mutually exclusive. Explicit complete
`abc` already determines its bars; to change length edit the score. Do not send
all three hoping the backend will choose. `/cover` and audio `/continue` derive
their score from audio and cannot take a caller-supplied score/planning object.

Keep BPM/key in typed `planning` or the score's `Q:` / `K:` fields. Style prompts
normally omit tempo/length to avoid contradicting the score. Key values in
`planning` use major/minor spellings such as `A minor` or `Bb major`. Omit key
or send an empty string to let the model choose while keeping tempo/meter.
Omit `planning` entirely to let it choose tempo too. Do not assume all Gary
prompt scales are accepted by this typed interface.

## New Generation or Plan First

`POST /yuey/generate`:

```json
{
  "style": "instrumental downtempo electronica, warm bass, dusty drums, evolving synth leads",
  "lyrics": "", "instrumental": true,
  "planning": {"bpm": 120, "key": "A minor", "meter_numerator": 4, "meter_denominator": 4},
  "symbolic_mode": "full",
  "target_bars": 16, "ending": "outro", "outro_bars": 4,
  "seed": 831001, "audio_format": "wav", "keep_models": false
}
```

For a reviewable score before audio work, send the same song controls to
`POST /yuey/plan`. Poll until completed, save `abc`, then send it to `/generate`
as `abc` with style, lyrics, instrumental flag, symbolic mode and seed. Omit
`planning` for this render. Preserve separate original and edited `.abc` files.

With `ending: "outro"`, `target_bars` selects the final **total score bars**,
retaining an ending of `outro_bars`. With `ending: "natural"` and
`target_bars: 0`, the planner chooses a length within server policy. Bars set
nominal musical length; rendered audio can include an extra tail. Inspect
`meta.score_duration`, `meta.duration` and truncation flags before exact cropping.

The hosted health checked on 2026-11-26 sets `natural_max_seconds: 96`.
A request can lower, not override, that natural-length ceiling; fixed-bar
fitting is a separate path. Do not silently assume an unbounded song, or try to
force a longer natural plan by increasing a token budget. `duration`,
`max_seconds` and `semantic_max_tokens` are advanced hard cutoffs, not ordinary
musical length controls; they can truncate an active phrase. Prefer bars.

## Audio → Transcription → Editable Remix

`POST /yuey/transcribe`:

```json
{
  "audio_data": "<base64 WAV>",
  "transcription_mode": "full",
  "pickup": "drop"
}
```

`transcription_mode` accepts `melody` or `full` (`mode` is also accepted).
Full recovers the melodic lanes plus chords. It does not extract separate
bass/drum/synth audio stems or recognize lyric text. `pickup: "drop"` (default
for transcription/cover) starts on the detected downbeat; `keep` retains the
lead-in. Save the actual inferred BPM, meter, bars and key; do not assume
transcription recovered exactly the intended eight bars.

To remix immediately, `POST /yuey/cover` with the same `audio_data`, chosen
`transcription_mode`, `style`, `instrumental`, `lyrics`, `seed` and
`audio_format: "wav"`. The endpoint transcribes and renders without a pause.

To edit first, transcribe once and send the accepted/edited score as `abc` to
`/generate` with the new `style`. Use `symbolic_mode: "full"` when chord edits
should guide the render; `melody` leaves more freedom. For an explicit tempo
change edit `Q:` and record that old MIDI/audio no longer share timing. The
JUCE remix workflow does this as two requests to control tempo before rendering.

For vocal remix, provide existing lyrics when known; transcription supplies
notes, not words. For instrumental remix, set `instrumental: true` and empty
lyrics. Default `instrumental_method: "transfer"` moves the Vocal lane melody
into Ins; `rest` silences those notes. No-vocal conditioning is best-effort;
retain warnings and audition.

## Two Continuation Methods

### Continue the Score

Use an existing Yuey `abc`, or transcribe another model's WAV first. Send
`POST /yuey/generate` with:

```json
{
  "style": "develop the groove with warm synths and a stronger rhythmic section",
  "lyrics": "", "instrumental": true,
  "abc_prefix": "<saved complete source ABC, ending in a newline>",
  "symbolic_mode": "full",
  "ending": "outro", "target_bars": 16, "outro_bars": 4,
  "seed": 831001, "audio_format": "wav", "keep_models": false
}
```

Here `target_bars: 16` assumes the saved score has eight bars and the intent
is eight more. It means total bars, not appended bars. Count the source first;
use `source_bars + added_bars`. Preserve the whole valid prefix, both voices
and barlines. For natural extension use `ending: "natural"`, `target_bars: 0`.
The natural ceiling applies to newly added material, not the retained prefix.
The result includes a re-rendered opening, not the original source WAV.

### Continue the Encoded Audio

Require `health.continuation.available: true`. Send `POST /yuey/continue`:

```json
{
  "audio_data": "<base64 source WAV>",
  "style": "continue the existing groove with a developing synth melody",
  "lyrics": "", "instrumental": true,
  "transcription_mode": "full", "pickup": "keep",
  "continuation_bars": 8, "use_continuation_adapter": true,
  "seed": 831001, "audio_format": "wav", "keep_models": false
}
```

`continuation_bars` is **new** bars (1–256); zero/omitted lets the planner choose.
Unlike score continuation it is not a total. Source audio supplies both the
score prefix and a 25 Hz semantic prefix. Do not also send `abc`, `abc_prefix`
or `planning`. Keep the matching continuation adapter enabled; the service
rejects decoding these tokens without it. Save `semantic_prefix_frames` and
`semantic_prefix_duration` when returned. Natural extension remains subject to
the hosted policy. Use the measured result metadata rather than assuming exact
wall-clock length from the requested bars.

## Editing ABC as an Agent

Use a returned score as the starting template. Preserve its header, named
voices (`V: Vocal`, `V: Ins`), section comments, key and meter unless changing
them intentionally. The native dialect commonly uses `L:1/16`: in 4/4 each
voice must sum to 16 units per bar. A whole-bar rest is `z16|`; a chord label
like `"Am"` changes harmony without consuming time. Keep voice bar counts and
section boundaries aligned. Do not replace the score with generic ABC from a
notation library without checking compatibility.

An LLM can edit pitches, rhythmic values, chord symbols, section order and
repetition directly, then render the resulting `abc`. Keep the style prompt:
the score carries notes/harmony, while style carries the intended sound.
Tempo/header-only changes do not time-stretch the original source audio.

For supported deterministic edits, discover `health.score_transforms` and use
synchronous `POST /yuey/score/transform`:

```json
{"abc": "<saved score>", "op": "transpose", "semitones": 5}
```

Other advertised ops are `half_time`, `double_time`, `melody_to_instrument`,
`swap_lanes`, `drop_chords`. The response includes validated `abc`, `changed`,
`bars`, `bpm` and possibly a rounding `note`. These edits have no job id and
require no polling. A 400 identifies an unsupported score/edit; correct the
score rather than repeatedly submitting it. Direct hand edits still need a
successful render and audition; syntactic validity is not musical quality.

Keep `midi_data` (combined file) and nonempty `midi_files` values. Files can
include `transcription.mid`, `melody.mid`, `melody_vocal.mid`,
`melody_instrumental.mid` and `chords.mid`. These are symbolic MIDI lanes, not
audio stems. Generation MIDI is derived from the final rendered score. Cropping
or changing the WAV invalidates its original MIDI/score alignment; retain the
original pair and record offsets instead of silently calling them synchronized.

## Chaining and Scope

Example: SA3 eight-bar loop → Yuey transcribe → inspect/edit score → Yuey score
continuation → SA3 transform with lane-specific prompts → Carey lego vocals →
local mix. Choose each branch from the preceding result; it is not a mandatory
recipe. For source timbre anchoring, choose Yuey audio continuation instead.

This guide targets hosted inference. Native local Yuey uses port 8007 without
`/yuey`, but the bundled lifecycle controller has not been updated for it in
this pass. Do not silently switch profiles or add training work. Newer native
checkouts contain extra adapter controls; only use features actually advertised
and supported by the hosted deployment.

## Contract Evidence

Reviewed 2026-11-26: yuey.cpp checkout at `C:/dev/yue2.cpp`, `docs/server.md`;
gary4juce `Source/PluginEditor.Yuey.cpp`; Spark live `/yuey/health` through its
existing Caddy listener over SSH. Hosted health reports v0.2.1, generation and
transcription available, encoded-audio continuation configured, WAV/FLAC formats,
and the six score transforms above. This review did not submit generation jobs
or audition these examples. Local source may be newer than hosted deployment;
capability discovery takes precedence over local-only features.
