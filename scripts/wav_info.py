#!/usr/bin/env python3
"""Print basic WAV metadata as JSON."""

from __future__ import annotations

import argparse
import json

from wav_utils import peak_fraction, read_wav


def main() -> None:
    parser = argparse.ArgumentParser(description="Print basic PCM WAV metadata.")
    parser.add_argument("input", help="Input WAV")
    args = parser.parse_args()

    audio = read_wav(args.input)
    print(json.dumps({
        "path": args.input,
        "channels": audio.channels,
        "sample_width_bytes": audio.sample_width,
        "bit_depth": audio.sample_width * 8,
        "sample_rate": audio.sample_rate,
        "frames": audio.frame_count,
        "duration_seconds": round(audio.duration, 6),
        "peak": round(peak_fraction(audio.frames, audio.sample_width), 6),
    }, indent=2))


if __name__ == "__main__":
    main()
