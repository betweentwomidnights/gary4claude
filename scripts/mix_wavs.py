#!/usr/bin/env python3
"""Mix compatible PCM WAV files into one WAV."""

from __future__ import annotations

import argparse
from pathlib import Path

from wav_utils import (
    WavData,
    add_frames,
    frame_byte_count,
    gain,
    normalize,
    read_wav,
    require_compatible,
    silence_like,
    write_wav,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mix two or more compatible PCM WAV files.")
    parser.add_argument("inputs", nargs="+", help="Input WAV files")
    parser.add_argument("-o", "--output", required=True, help="Output WAV")
    parser.add_argument(
        "--gain",
        type=float,
        action="append",
        default=[],
        help="Linear gain for each input, in order. Missing gains default to 1.0.",
    )
    parser.add_argument(
        "--length",
        choices=["longest", "shortest"],
        default="longest",
        help="Output length policy",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize output peak to 0.95 after mixing",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if len(args.inputs) < 2:
        raise SystemExit("mix_wavs.py needs at least two input WAV files")

    audios = [read_wav(path) for path in args.inputs]
    reference = audios[0]
    for path, audio in zip(args.inputs[1:], audios[1:]):
        require_compatible(reference, audio, path)

    if args.length == "shortest":
        frame_count = min(audio.frame_count for audio in audios)
    else:
        frame_count = max(audio.frame_count for audio in audios)

    out = silence_like(reference, frame_count)
    for index, audio in enumerate(audios):
        gain_value = args.gain[index] if index < len(args.gain) else 1.0
        chunk = audio.frames[: frame_byte_count(audio, frame_count)]
        if audio.frame_count < frame_count:
            chunk += silence_like(audio, frame_count - audio.frame_count)
        chunk = gain(chunk, audio.sample_width, gain_value)
        out = add_frames(out, chunk, reference.sample_width)

    if args.normalize:
        out = normalize(out, reference.sample_width)

    write_wav(args.output, WavData(reference.channels, reference.sample_width, reference.sample_rate, out))
    print(f"wrote {Path(args.output)} ({frame_count / reference.sample_rate:.3f}s)")


if __name__ == "__main__":
    main()
