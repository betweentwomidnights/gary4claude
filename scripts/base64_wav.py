#!/usr/bin/env python3
"""Encode or decode WAV bytes as base64 for API requests."""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode/decode WAV files to/from base64.")
    sub = parser.add_subparsers(dest="command", required=True)

    enc = sub.add_parser("encode", help="Encode a WAV file to base64 text")
    enc.add_argument("input", help="Input WAV")
    enc.add_argument("-o", "--output", help="Output text file; stdout if omitted")

    dec = sub.add_parser("decode", help="Decode base64 text to a WAV file")
    dec.add_argument("input", help="Input base64 text file, or '-' for stdin")
    dec.add_argument("output", help="Output WAV")

    args = parser.parse_args()

    if args.command == "encode":
        data = base64.b64encode(Path(args.input).read_bytes()).decode("ascii")
        if args.output:
            Path(args.output).write_text(data, encoding="ascii")
        else:
            print(data)
        return

    text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="ascii")
    Path(args.output).write_bytes(base64.b64decode("".join(text.split())))


if __name__ == "__main__":
    main()
