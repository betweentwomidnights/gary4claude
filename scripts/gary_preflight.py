#!/usr/bin/env python3
"""Check whether a WAV is long enough for a Gary prompt_duration."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from wav_utils import read_wav


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a source WAV before calling Gary process_audio or "
            "continue_music. Reports whether prompt_duration fits and how "
            "many repeats would be needed to tile the source."
        ),
    )
    parser.add_argument("input", help="Input WAV")
    parser.add_argument(
        "--prompt-duration",
        type=float,
        default=6.0,
        help="Gary prompt_duration in seconds; default is 6",
    )
    parser.add_argument(
        "--min-margin",
        type=float,
        default=0.25,
        help="Extra seconds required beyond prompt_duration; default is 0.25",
    )
    parser.add_argument(
        "--target-duration",
        type=float,
        help="Optional desired tiled duration. Defaults to prompt_duration + min_margin.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print only JSON, without the human summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.prompt_duration <= 0:
        raise SystemExit("--prompt-duration must be greater than zero")
    if args.min_margin < 0:
        raise SystemExit("--min-margin must be zero or greater")

    audio = read_wav(args.input)
    minimum = args.prompt_duration + args.min_margin
    target = args.target_duration if args.target_duration is not None else minimum
    if target < minimum:
        raise SystemExit("--target-duration must be >= prompt_duration + min_margin")

    repeats = 1
    if audio.duration > 0:
        repeats = max(1, math.ceil(target / audio.duration))

    safe = audio.duration >= minimum
    result = {
        "path": str(Path(args.input)),
        "duration_seconds": round(audio.duration, 6),
        "prompt_duration": args.prompt_duration,
        "min_margin": args.min_margin,
        "minimum_source_duration_seconds": round(minimum, 6),
        "safe_for_gary": safe,
        "recommended_action": "use_as_is" if safe else "tile_before_gary",
        "tile_repeats_for_target": repeats,
        "tiled_duration_seconds": round(audio.duration * repeats, 6),
        "tile_command": (
            None
            if safe
            else f"python scripts/tile_wav.py {args.input} tiled_for_gary.wav --seconds {target:.3f}"
        ),
    }

    if not args.json:
        status = "OK" if safe else "TOO SHORT"
        print(f"{status}: {args.input} is {audio.duration:.3f}s; Gary context needs >= {minimum:.3f}s")
        if not safe:
            print(result["tile_command"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
