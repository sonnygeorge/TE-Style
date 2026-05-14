"""
Trim and speed-edit videos from the command line.

Examples:
  python scripts/edit_video.py \
      --input videos/in.mp4 \
      --output videos/out.mp4 \
      --trim-front 2.5 \
      --speed 1.5

  python scripts/edit_video.py \
      --input videos/in.mp4 \
      --output videos/out.mp4 \
      --trim-back 3 \
      --speed 2
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
from pathlib import Path


def check_dependencies() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe must be installed and available in PATH.")


def run_checked(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_duration_seconds(video_path: Path) -> float:
    output = run_checked(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
    )
    return float(output)


def build_atempo_chain(speed: float) -> str:
    # atempo supports factors between 0.5 and 2.0 per filter instance.
    factors: list[float] = []
    remaining = speed

    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5

    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim seconds from front/back and speed up/down a video."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input video path")
    parser.add_argument("--output", required=True, type=Path, help="Output video path")
    parser.add_argument(
        "--trim-front",
        type=float,
        default=0.0,
        help="Seconds to remove from the beginning (default: 0)",
    )
    parser.add_argument(
        "--trim-back",
        type=float,
        default=0.0,
        help="Seconds to remove from the end (default: 0)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier (e.g. 2.0 doubles speed, default: 1)",
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="Drop audio from output (optional)",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.input.exists():
        raise FileNotFoundError(f"Input video not found: {args.input}")
    if args.trim_front < 0 or args.trim_back < 0:
        raise ValueError("--trim-front and --trim-back must be >= 0.")
    if args.speed <= 0:
        raise ValueError("--speed must be > 0.")


def main() -> None:
    args = parse_args()
    validate_args(args)
    check_dependencies()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = get_duration_seconds(input_path)
    start = args.trim_front
    end = duration - args.trim_back

    if end <= start:
        raise ValueError(
            "Trim values remove entire video. "
            f"Duration={duration:.3f}s, start={start:.3f}s, end={end:.3f}s"
        )

    # -ss/-to before -i gives fast seek and bounded decode.
    command: list[str] = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.6f}",
        "-to",
        f"{end:.6f}",
        "-i",
        str(input_path),
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
        "-vf",
        f"setpts=PTS/{args.speed:.8f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
    ]

    if args.mute:
        command += ["-an"]
    else:
        atempo_chain = build_atempo_chain(args.speed)
        # Protect against floating-point artifacts like 1.0000000002.
        if math.isclose(args.speed, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            command += ["-c:a", "aac", "-b:a", "128k"]
        else:
            command += ["-af", atempo_chain, "-c:a", "aac", "-b:a", "128k"]

    command.append(str(output_path))
    subprocess.run(command, check=True)

    print(
        "Wrote edited video:",
        output_path,
        f"(trim_front={args.trim_front}s, trim_back={args.trim_back}s, speed={args.speed}x)",
    )


if __name__ == "__main__":
    main()
