#!/usr/bin/env python3
"""Trim a WAV file by seconds or bars."""

from __future__ import annotations

import argparse
from pathlib import Path

from wav_utils import WavData, frames_for_seconds, read_wav, slice_frames, write_wav


def parse_time(value: str, bpm: float | None) -> float:
    if value.endswith("s"):
        return float(value[:-1])
    if value.endswith("bars"):
        if not bpm or bpm <= 0:
            raise SystemExit("bar-based trim values require --bpm > 0")
        bars = float(value[:-4])
        return bars * 4.0 * 60.0 / bpm
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trim a PCM WAV by seconds or bars. Examples: --start 8s --end 16s, --end 32bars --bpm 174.",
    )
    parser.add_argument("input", help="Input WAV")
    parser.add_argument("output", help="Output WAV")
    parser.add_argument("--start", default="0", help="Start time in seconds, or e.g. 4bars")
    parser.add_argument("--end", help="End time in seconds, or e.g. 32bars; default is end of file")
    parser.add_argument("--duration", help="Duration in seconds or bars; alternative to --end")
    parser.add_argument("--bpm", type=float, help="Tempo for bar-based values")
    args = parser.parse_args()

    if args.end and args.duration:
        raise SystemExit("use either --end or --duration, not both")

    audio = read_wav(args.input)
    start_seconds = parse_time(args.start, args.bpm)
    if args.duration:
        end_seconds = start_seconds + parse_time(args.duration, args.bpm)
    elif args.end:
        end_seconds = parse_time(args.end, args.bpm)
    else:
        end_seconds = audio.duration

    start_frame = frames_for_seconds(audio, start_seconds)
    end_frame = frames_for_seconds(audio, end_seconds)
    if start_frame < 0 or end_frame <= start_frame:
        raise SystemExit("trim range must have positive duration")
    start_frame = min(start_frame, audio.frame_count)
    end_frame = min(end_frame, audio.frame_count)

    trimmed = slice_frames(audio, start_frame, end_frame)
    write_wav(args.output, WavData(audio.channels, audio.sample_width, audio.sample_rate, trimmed))
    print(f"wrote {Path(args.output)} ({(end_frame - start_frame) / audio.sample_rate:.3f}s)")


if __name__ == "__main__":
    main()
