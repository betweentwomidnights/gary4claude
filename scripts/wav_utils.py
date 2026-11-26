#!/usr/bin/env python3
"""Small stdlib-only PCM and IEEE-float WAV helpers for gary4claude."""

from __future__ import annotations

from dataclasses import dataclass
from array import array
import math
from pathlib import Path
import struct


PCM_FORMAT = 1
IEEE_FLOAT_FORMAT = 3
EXTENSIBLE_FORMAT = 0xFFFE
SUPPORTED_FORMATS = (PCM_FORMAT, IEEE_FLOAT_FORMAT)


@dataclass(frozen=True)
class WavData:
    channels: int
    sample_width: int
    sample_rate: int
    frames: bytes
    format_tag: int = PCM_FORMAT

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
    def format_name(self) -> str:
        return "ieee-float" if self.format_tag == IEEE_FLOAT_FORMAT else "pcm"

    @property
    def params_key(self) -> tuple[int, int, int, int]:
        return (self.format_tag, self.channels, self.sample_width, self.sample_rate)


def _riff_chunks(data: bytes):
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > len(data):
            raise ValueError(f"truncated WAV chunk {chunk_id!r}")
        yield chunk_id, data[payload_start:payload_end]
        offset = payload_end + (chunk_size & 1)


def read_wav(path: str | Path) -> WavData:
    data = Path(path).read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path} is not a RIFF/WAVE file")

    fmt = None
    frames = None
    for chunk_id, payload in _riff_chunks(data):
        if chunk_id == b"fmt " and fmt is None:
            fmt = payload
        elif chunk_id == b"data" and frames is None:
            frames = payload

    if fmt is None or len(fmt) < 16:
        raise ValueError(f"{path} has no valid fmt chunk")
    if frames is None:
        raise ValueError(f"{path} has no data chunk")

    format_tag, channels, sample_rate, _, block_align, bits = struct.unpack_from(
        "<HHIIHH", fmt, 0
    )
    if format_tag == EXTENSIBLE_FORMAT:
        if len(fmt) < 40:
            raise ValueError(f"{path} has a truncated WAVE_FORMAT_EXTENSIBLE fmt chunk")
        format_tag = struct.unpack_from("<I", fmt, 24)[0]

    if format_tag not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported WAV format tag: {format_tag}")
    if channels <= 0 or sample_rate <= 0 or bits <= 0 or bits % 8:
        raise ValueError(f"{path} has invalid WAV format fields")

    sample_width = bits // 8
    expected_align = channels * sample_width
    if block_align != expected_align:
        raise ValueError(
            f"unsupported WAV block alignment {block_align}; expected {expected_align}"
        )
    if format_tag == IEEE_FLOAT_FORMAT and sample_width != 4:
        raise ValueError("only 32-bit IEEE float WAV is supported")

    frames = frames[: len(frames) - (len(frames) % block_align)]
    return WavData(
        channels=channels,
        sample_width=sample_width,
        sample_rate=sample_rate,
        frames=frames,
        format_tag=format_tag,
    )


def _chunk(chunk_id: bytes, payload: bytes) -> bytes:
    padding = b"\x00" if len(payload) & 1 else b""
    return chunk_id + struct.pack("<I", len(payload)) + payload + padding


def write_wav(path: str | Path, audio: WavData) -> None:
    if audio.format_tag not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported WAV format tag: {audio.format_tag}")
    if audio.format_tag == IEEE_FLOAT_FORMAT and audio.sample_width != 4:
        raise ValueError("only 32-bit IEEE float WAV is supported")

    block_align = audio.channels * audio.sample_width
    bits = audio.sample_width * 8
    byte_rate = audio.sample_rate * block_align
    fmt = struct.pack(
        "<HHIIHH",
        audio.format_tag,
        audio.channels,
        audio.sample_rate,
        byte_rate,
        block_align,
        bits,
    )
    chunks = [_chunk(b"fmt ", fmt)]
    if audio.format_tag != PCM_FORMAT:
        chunks.append(_chunk(b"fact", struct.pack("<I", audio.frame_count)))
    chunks.append(_chunk(b"data", audio.frames))
    body = b"WAVE" + b"".join(chunks)
    Path(path).write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def require_compatible(reference: WavData, other: WavData, label: str) -> None:
    if reference.params_key != other.params_key:
        raise SystemExit(
            f"{label} has incompatible WAV format: "
            f"{other.format_name}/{other.channels}ch/"
            f"{other.sample_width * 8}bit/{other.sample_rate}Hz; expected "
            f"{reference.format_name}/{reference.channels}ch/"
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


def _read_sample(
    data: bytes,
    offset: int,
    sample_width: int,
    format_tag: int,
) -> float | int:
    if format_tag == IEEE_FLOAT_FORMAT:
        return struct.unpack_from("<f", data, offset)[0]
    raw = data[offset:offset + sample_width]
    if sample_width == 1:
        return raw[0] - 128
    return int.from_bytes(raw, "little", signed=True)


def _write_sample(value: float | int, sample_width: int, format_tag: int) -> bytes:
    if format_tag == IEEE_FLOAT_FORMAT:
        return struct.pack("<f", max(-1.0, min(1.0, float(value))))
    low, high = sample_bounds(sample_width)
    value = max(low, min(high, int(round(value))))
    if sample_width == 1:
        return bytes([value + 128])
    return value.to_bytes(sample_width, "little", signed=True)


def _map_samples(
    frames: bytes,
    sample_width: int,
    format_tag: int,
    fn,
) -> bytes:
    out = bytearray(len(frames))
    for offset in range(0, len(frames), sample_width):
        out[offset:offset + sample_width] = _write_sample(
            fn(_read_sample(frames, offset, sample_width, format_tag)),
            sample_width,
            format_tag,
        )
    return bytes(out)


def gain(
    frames: bytes,
    sample_width: int,
    multiplier: float,
    format_tag: int = PCM_FORMAT,
) -> bytes:
    if multiplier == 1.0:
        return frames
    return _map_samples(
        frames,
        sample_width,
        format_tag,
        lambda sample: sample * multiplier,
    )


def peak_fraction(
    frames: bytes,
    sample_width: int,
    format_tag: int = PCM_FORMAT,
) -> float:
    peak = 0.0
    for offset in range(0, len(frames), sample_width):
        peak = max(
            peak,
            abs(float(_read_sample(frames, offset, sample_width, format_tag))),
        )
    if format_tag == IEEE_FLOAT_FORMAT:
        return peak
    _, high = sample_bounds(sample_width)
    return peak / high if high > 0 else 0.0


def normalize(
    frames: bytes,
    sample_width: int,
    target_peak: float = 0.95,
    format_tag: int = PCM_FORMAT,
) -> bytes:
    peak = peak_fraction(frames, sample_width, format_tag)
    if peak <= 0:
        return frames
    return gain(frames, sample_width, target_peak / peak, format_tag)


def add_frames(
    left: bytes,
    right: bytes,
    sample_width: int,
    format_tag: int = PCM_FORMAT,
) -> bytes:
    if len(left) != len(right):
        raise ValueError("add_frames requires equal-length buffers")
    out = bytearray(len(left))
    for offset in range(0, len(left), sample_width):
        mixed = _read_sample(left, offset, sample_width, format_tag) + _read_sample(
            right,
            offset,
            sample_width,
            format_tag,
        )
        out[offset:offset + sample_width] = _write_sample(
            mixed,
            sample_width,
            format_tag,
        )
    return bytes(out)


def mix_audio(
    audios: list[WavData],
    gains: list[float],
    frame_count: int,
    target_peak: float | None = None,
) -> WavData:
    """Sum in double precision; normalize before the only output quantization.

    Applying gain/add_frames to encoded PCM clips each intermediate buffer.
    That destroys peaks (and cancellation) before a later normalize can help.
    """
    if not audios or frame_count < 0:
        raise ValueError("mix_audio needs input audio and a nonnegative frame count")
    if len(gains) > len(audios) or not all(math.isfinite(g) for g in gains):
        raise ValueError("provide at most one finite gain per input")
    if target_peak is not None and not 0 < target_peak <= 1:
        raise ValueError("target peak must be in (0, 1]")
    reference = audios[0]
    samples = array("d", [0.0]) * (frame_count * reference.channels)
    for index, audio in enumerate(audios):
        require_compatible(reference, audio, f"input {index + 1}")
        multiplier = gains[index] if index < len(gains) else 1.0
        count = min(frame_count, audio.frame_count) * audio.channels
        for sample_index in range(count):
            value = _read_sample(
                audio.frames, sample_index * audio.sample_width,
                audio.sample_width, audio.format_tag,
            )
            mixed = samples[sample_index] + value * multiplier
            if not math.isfinite(mixed):
                raise ValueError("mix contains non-finite samples")
            samples[sample_index] = mixed

    scale = 1.0
    if target_peak is not None:
        peak = max((abs(value) for value in samples), default=0.0)
        full_scale = (1.0 if reference.format_tag == IEEE_FLOAT_FORMAT
                      else sample_bounds(reference.sample_width)[1])
        if peak > 0:
            scale = target_peak * full_scale / peak
    out = bytearray(len(samples) * reference.sample_width)
    for index, value in enumerate(samples):
        offset = index * reference.sample_width
        out[offset:offset + reference.sample_width] = _write_sample(
            value * scale, reference.sample_width, reference.format_tag,
        )
    return WavData(reference.channels, reference.sample_width,
                   reference.sample_rate, bytes(out), reference.format_tag)
