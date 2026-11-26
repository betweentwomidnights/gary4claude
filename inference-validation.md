# Hosted Inference: Next Fresh-Session Checks

The API guides were reviewed against source and live metadata on 2026-11-26.
No music generations or production changes were made during that review. These
are musical/agent trials to run with the user next, one heavy request at a time.
Use the hosted profile; do not turn these into a deployment or training task.

## Useful JUCE Reference Capture

A multi-lane SA3 Continue is the most useful next human reference: two or three
LoRAs, distinct lane prompts, overlapping rises/falls, a nonzero source duration,
and a chosen blend setting. Keep the source WAV and returned WAV so timing and
musical effect can both be checked. Record the lane UI range, crop decisions,
BPM/key, steps, shift and transform strength if applicable.

Current gary4juce can export this without copying a huge base64 request. In
Audio Storage choose **generation details → JSON**, then drag the generated
audio. A matching timestamped `.json` remains beside the WAV in `dragged_audio`.
The record includes the actual render's request settings and crop edits, and
identifies conditioning audio by hash. It excludes audio upload payloads and
credentials. Embedded metadata is another option. This is documented in
`C:/dev/gary4juce/docs/EXPORT_METADATA.md`.

Compare capture against sa3.md: adapter strength versus curve multiplier,
seconds versus normalized UI positions, source-duration offset, decorated lane
prompts and blend thresholds computed for the actual shift/step schedule.
The JSON alone verifies serialization; the WAV pair is needed to judge sound.

## Fresh-Session Trials

| Trial | What success should establish |
|-------|-------------------------------|
| SA3 eight-bar loop → Yuey transcribe → score continuation | Agent recognizes no SA3 score exists, waits for score-only completion, preserves valid ABC and uses total target bars |
| Yuey encoded-audio continuation of the same seed | Agent selects `/continue`, uses added bars, saves semantic-prefix metadata, and does not promise an untouched waveform |
| Yuey transcription → chord/melody edit → render | Agent keeps voice/bar durations aligned, chooses full versus melody deliberately, saves original/edited scores and new audio |
| SAOS jerry_grunge → SA3 lanes → crop → SA3 lanes | Agent discovers the finetune, recalculates lane absolute times after cropping, retains source lineage and inspects transitions |
| Carey text2music | Agent discovers `/props`, selects XL turbo/base as available, waits for `done` and extracts multipart audio |
| Carey Complete versus Lego | Agent uses base, recognizes accompaniment/full mix versus added track, and avoids summing a completed arrangement into its own source |
| Carey billie lego vocals → backing mix | Agent checks bleed, timing and WAV compatibility, mixes with normalization before output encoding, and saves stems plus final WAV |

For each trial retain the prompt, request JSON, submission/status metadata,
ordered artifacts, intended versus actual duration and a short listening note.
If no listening tool is available, mark musical quality unassessed. Do not count
successful HTTP transport as evidence that the continuation or vocal works.

## Known Remaining Limits

- Default Python urllib requests received HTTP 403, while curl and Python with
  `User-Agent: gary4claude/1.0` returned 200 at the public Carey props URL.
  Fresh sessions should send the explicit header and verify reachability;
  do not silently switch to a private host address.
- Current hosted Carey exposes the C++ job contract through a Python wrapper.
  Its cancelled submitted jobs can drain in the background. Local ace-server
  and remote internals are not identical.
- A local yuey.cpp checkout can contain adapter features newer than the hosted
  v0.2.1 deployment. Discover capabilities rather than copying local UI controls.
- The old Python-oriented local lifecycle helper has not been migrated for all
  native runtimes. Installer embedding, Linux headless workflows and LoRA
  training remain separate work.
- Sample-peak normalization prevents mix-sum clipping when enabled; it is not
  true-peak limiting, source-distortion repair, stem isolation or automatic
  latency detection.
