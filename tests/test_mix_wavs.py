"""Regression checks for summing stems without clipping before normalization."""

from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from wav_utils import (  # noqa: E402
    IEEE_FLOAT_FORMAT, PCM_FORMAT, WavData, mix_audio, read_wav, write_wav,
)


def audio(values, width=2, format_tag=PCM_FORMAT, channels=1):
    if format_tag == IEEE_FLOAT_FORMAT:
        frames = struct.pack(f"<{len(values)}f", *values)
    elif width == 1:
        frames = bytes(value + 128 for value in values)
    else:
        frames = b"".join(int(value).to_bytes(width, "little", signed=True)
                          for value in values)
    return WavData(channels, width, 48000, frames, format_tag)


def values(wav):
    if wav.format_tag == IEEE_FLOAT_FORMAT:
        return list(struct.unpack(f"<{len(wav.frames) // 4}f", wav.frames))
    if wav.sample_width == 1:
        return [value - 128 for value in wav.frames]
    return [int.from_bytes(wav.frames[i:i + wav.sample_width], "little", signed=True)
            for i in range(0, len(wav.frames), wav.sample_width)]


class MixTests(unittest.TestCase):
    def test_normalization_preserves_unclipped_peak_ratios(self):
        for width in (1, 2, 3, 4):
            high = (1 << (width * 8 - 1)) - 1
            stem = audio([int(high * 0.8), int(high * 0.4), -int(high * 0.8)], width)
            mixed = values(mix_audio([stem, stem], [], 3, target_peak=0.95))
            with self.subTest(width=width):
                self.assertAlmostEqual(mixed[0], high * 0.95, delta=1)
                self.assertAlmostEqual(mixed[1] / mixed[0],
                                       values(stem)[1] / values(stem)[0], delta=0.01)
                self.assertEqual(mixed[2], -mixed[0])

    def test_intermediate_overload_can_cancel(self):
        positive, negative = audio([26000]), audio([-26000])
        result = mix_audio([positive, positive, negative], [], 1)
        reordered = mix_audio([positive, negative, positive], [], 1)
        self.assertEqual(values(result), [26000])
        self.assertEqual(result.frames, reordered.frames)

    def test_float_gain_is_not_clipped_before_summing(self):
        positive = audio([0.8, 0.4], 4, IEEE_FLOAT_FORMAT)
        negative = audio([-0.8, -0.4], 4, IEEE_FLOAT_FORMAT)
        result = values(mix_audio([positive, negative], [2, 1], 2, 0.95))
        self.assertAlmostEqual(result[0], 0.95, places=6)
        self.assertAlmostEqual(result[1], 0.475, places=6)

    def test_padding_stereo_and_unsigned_silence(self):
        first = audio([20, -20, 10, -10], 1, channels=2)
        second = audio([30, -30], 1, channels=2)
        self.assertEqual(values(mix_audio([first, second], [], 3)),
                         [50, -50, 10, -10, 0, 0])
        self.assertEqual(values(mix_audio([first, second], [], 1)), [50, -50])

    def test_invalid_gains_and_nonfinite_audio(self):
        stem = audio([1])
        for gains in ([float("nan")], [float("inf")], [1, 2]):
            with self.subTest(gains=gains), self.assertRaises(ValueError):
                mix_audio([stem], gains, 1)
        with self.assertRaises(ValueError):
            mix_audio([audio([float("nan")], 4, IEEE_FLOAT_FORMAT)], [], 1)
        with self.assertRaises(ValueError):
            mix_audio([stem], [], 1, target_peak=float("nan"))

    def test_cli_wav_roundtrip_and_length_policies(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("a.wav", "b.wav", "out.wav")]
            write_wav(paths[0], audio([26000, 13000, 0]))
            write_wav(paths[1], audio([26000, 13000]))
            for length, expected_frames in (("longest", 3), ("shortest", 2)):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "mix_wavs.py"),
                     str(paths[0]), str(paths[1]), "-o", str(paths[2]),
                     "--length", length, "--normalize"],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                mixed = read_wav(paths[2])
                self.assertEqual(mixed.frame_count, expected_frames)
                self.assertAlmostEqual(values(mixed)[0], 32767 * 0.95, delta=1)
                self.assertAlmostEqual(values(mixed)[1] / values(mixed)[0], 0.5, places=4)


if __name__ == "__main__":
    unittest.main()
