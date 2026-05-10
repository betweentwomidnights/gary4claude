#!/usr/bin/env python3
"""Tile a WAV loop to a target duration, bar count, or reference WAV length."""

from __future__ import annotations

import argparse
from pathlib import Path

from wav_utils import WavData, frame_byte_count, frames_for_seconds, read_wav, slice_frames, write_wav


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repeat a PCM WAV loop to a target duration, bar count, or reference WAV length.",
    )
    parser.add_argument("input", help="Input WAV loop")
    parser.add_argument("output", help="Output tiled WAV")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--seconds", type=float, help="Target duration in seconds")
    target.add_argument("--bars", type=float, help="Target bar count; requires --bpm")
    target.add_argument("--match", help="Tile to match another WAV file's duration")
    parser.add_argument("--bpm", type=float, help="Tempo used with --bars")
    parser.add_argument(
        "--pad",
        action="store_true",
        help="Pad with silence if input is empty or target is not reached exactly",
    )
    return parser.parse_args()


def target_frames(args: argparse.Namespace, audio: WavData) -> int:
    if args.seconds is not None:
        return frames_for_seconds(audio, args.seconds)
    if args.bars is not None:
        if not args.bpm or args.bpm <= 0:
            raise SystemExit("--bars requires --bpm > 0")
        seconds = args.bars * 4.0 * 60.0 / args.bpm
        return frames_for_seconds(audio, seconds)
    match = read_wav(args.match)
    return frames_for_seconds(audio, match.duration)


def main() -> None:
    args = parse_args()
    audio = read_wav(args.input)
    wanted_frames = target_frames(args, audio)
    frame_size = audio.channels * audio.sample_width
    if wanted_frames <= 0:
        raise SystemExit("target duration must be greater than zero")
    if audio.frame_count <= 0:
        raise SystemExit("input WAV has no audio frames")

    wanted_bytes = frame_byte_count(audio, wanted_frames)
    repeats = (wanted_bytes + len(audio.frames) - 1) // len(audio.frames)
    tiled = (audio.frames * repeats)[:wanted_bytes]

    if args.pad and len(tiled) < wanted_bytes:
        tiled += b"\x00" * (wanted_bytes - len(tiled))

    # Keep byte length frame-aligned after slicing.
    tiled = tiled[: len(tiled) - (len(tiled) % frame_size)]
    write_wav(args.output, WavData(audio.channels, audio.sample_width, audio.sample_rate, tiled))
    print(f"wrote {Path(args.output)} ({wanted_frames / audio.sample_rate:.3f}s)")


if __name__ == "__main__":
    main()
