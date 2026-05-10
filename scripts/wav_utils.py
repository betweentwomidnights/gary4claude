#!/usr/bin/env python3
"""Small stdlib-only WAV helpers for gary4claude utility scripts."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WavData:
    channels: int
    sample_width: int
    sample_rate: int
    frames: bytes

    @property
    def frame_count(self) -> int:
        frame_size = self.channels * self.sample_width
        return len(self.frames) // frame_size

    @property
    def duration(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return self.frame_count / self.sample_rate

    @property
    def params_key(self) -> tuple[int, int, int]:
        return (self.channels, self.sample_width, self.sample_rate)


def read_wav(path: str | Path) -> WavData:
    with wave.open(str(path), "rb") as wav:
        return WavData(
            channels=wav.getnchannels(),
            sample_width=wav.getsampwidth(),
            sample_rate=wav.getframerate(),
            frames=wav.readframes(wav.getnframes()),
        )


def write_wav(path: str | Path, audio: WavData) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(audio.channels)
        wav.setsampwidth(audio.sample_width)
        wav.setframerate(audio.sample_rate)
        wav.writeframes(audio.frames)


def require_compatible(reference: WavData, other: WavData, label: str) -> None:
    if reference.params_key != other.params_key:
        raise SystemExit(
            f"{label} has incompatible WAV format: "
            f"{other.channels}ch/{other.sample_width * 8}bit/{other.sample_rate}Hz; "
            f"expected {reference.channels}ch/"
            f"{reference.sample_width * 8}bit/{reference.sample_rate}Hz"
        )


def silence_like(audio: WavData, frame_count: int) -> bytes:
    frame_size = audio.channels * audio.sample_width
    return b"\x00" * max(0, frame_count) * frame_size


def frames_for_seconds(audio: WavData, seconds: float) -> int:
    return max(0, int(round(seconds * audio.sample_rate)))


def frame_byte_count(audio: WavData, frame_count: int) -> int:
    return max(0, frame_count) * audio.channels * audio.sample_width


def slice_frames(audio: WavData, start_frame: int, end_frame: int) -> bytes:
    start = frame_byte_count(audio, start_frame)
    end = frame_byte_count(audio, end_frame)
    return audio.frames[start:end]


def sample_bounds(sample_width: int) -> tuple[int, int]:
    if sample_width == 1:
        return -128, 127
    bits = sample_width * 8
    return -(1 << (bits - 1)), (1 << (bits - 1)) - 1


def _read_sample(data: bytes, offset: int, sample_width: int) -> int:
    raw = data[offset:offset + sample_width]
    if sample_width == 1:
        return raw[0] - 128
    return int.from_bytes(raw, "little", signed=True)


def _write_sample(value: int, sample_width: int) -> bytes:
    low, high = sample_bounds(sample_width)
    value = max(low, min(high, int(round(value))))
    if sample_width == 1:
        return bytes([value + 128])
    return value.to_bytes(sample_width, "little", signed=True)


def _map_samples(frames: bytes, sample_width: int, fn) -> bytes:
    out = bytearray(len(frames))
    for offset in range(0, len(frames), sample_width):
        out[offset:offset + sample_width] = _write_sample(
            fn(_read_sample(frames, offset, sample_width)),
            sample_width,
        )
    return bytes(out)


def gain(frames: bytes, sample_width: int, multiplier: float) -> bytes:
    if multiplier == 1.0:
        return frames
    return _map_samples(frames, sample_width, lambda sample: sample * multiplier)


def peak_fraction(frames: bytes, sample_width: int) -> float:
    _, high = sample_bounds(sample_width)
    if high <= 0:
        return 0.0
    peak = 0
    for offset in range(0, len(frames), sample_width):
        peak = max(peak, abs(_read_sample(frames, offset, sample_width)))
    return peak / high


def normalize(frames: bytes, sample_width: int, target_peak: float = 0.95) -> bytes:
    peak = peak_fraction(frames, sample_width)
    if peak <= 0:
        return frames
    return gain(frames, sample_width, target_peak / peak)


def add_frames(left: bytes, right: bytes, sample_width: int) -> bytes:
    if len(left) != len(right):
        raise ValueError("add_frames requires equal-length buffers")
    out = bytearray(len(left))
    for offset in range(0, len(left), sample_width):
        mixed = (
            _read_sample(left, offset, sample_width)
            + _read_sample(right, offset, sample_width)
        )
        out[offset:offset + sample_width] = _write_sample(mixed, sample_width)
    return bytes(out)
