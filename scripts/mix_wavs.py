#!/usr/bin/env python3
"""Mix compatible PCM or IEEE-float WAV files into one WAV."""

from __future__ import annotations

import argparse
from pathlib import Path

from wav_utils import (
    mix_audio,
    read_wav,
    require_compatible,
    write_wav,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mix two or more compatible WAV files.")
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

    try:
        mixed = mix_audio(audios, args.gain, frame_count,
                          target_peak=0.95 if args.normalize else None)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    write_wav(args.output, mixed)
    print(f"wrote {Path(args.output)} ({frame_count / reference.sample_rate:.3f}s)")


if __name__ == "__main__":
    main()
