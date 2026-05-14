"""
Normalize repository videos for GitHub Pages hosting.

What this script does:
1) Recursively scans a video directory.
2) Re-encodes each video to H.264/AAC MP4.
3) Iteratively adjusts quality / scale until each output is <= threshold.
4) Replaces the original file when successful.
5) Updates `video` paths in the labels CSV when extensions change.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

FILE_SIZE_THRESHOLD_MB = 50
FILE_SIZE_THRESHOLD_BYTES = FILE_SIZE_THRESHOLD_MB * 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
DEFAULT_VIDEO_ROOT = Path("videos")
DEFAULT_LABELS_CSV = Path("te-style_labels.csv")


@dataclass(frozen=True)
class EncodeAttempt:
    crf: int
    max_width: int


ATTEMPTS = [
    EncodeAttempt(crf=23, max_width=1920),
    EncodeAttempt(crf=26, max_width=1920),
    EncodeAttempt(crf=28, max_width=1280),
    EncodeAttempt(crf=30, max_width=1280),
    EncodeAttempt(crf=32, max_width=960),
    EncodeAttempt(crf=34, max_width=854),
]


def run_checked(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def get_size_bytes(path: Path) -> int:
    return path.stat().st_size


def build_scale_filter(max_width: int) -> str:
    return f"scale='min({max_width},iw)':-2:flags=lanczos"


def encode_mp4(input_path: Path, output_path: Path, attempt: EncodeAttempt) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-map_metadata",
        "-1",
        "-movflags",
        "+faststart",
        "-vf",
        build_scale_filter(attempt.max_width),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(attempt.crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_path),
    ]
    run_checked(command)


def paths_equivalent(a: Path, b: Path) -> bool:
    if a == b:
        return True
    try:
        return a.exists() and b.exists() and a.samefile(b)
    except OSError:
        return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def standardize_extension_case(video_path: Path) -> Path:
    lower_suffix = video_path.suffix.lower()
    target_path = video_path.with_suffix(lower_suffix)
    if video_path == target_path:
        return video_path

    if target_path.exists() and not paths_equivalent(target_path, video_path):
        raise RuntimeError(
            f"Cannot standardize extension casing because destination exists: {target_path}"
        )

    # Case-only renames can be unreliable on case-insensitive filesystems,
    # so perform a two-step rename through a temporary path.
    temp_path = video_path.with_name(f"{video_path.name}.casefix_tmp")
    suffix_index = 1
    while temp_path.exists():
        temp_path = video_path.with_name(f"{video_path.name}.casefix_tmp{suffix_index}")
        suffix_index += 1

    video_path.replace(temp_path)
    temp_path.replace(target_path)
    return target_path


def normalize_video(video_path: Path) -> Path:
    target_path = video_path.with_suffix(".mp4")
    temp_path = video_path.with_name(f"{video_path.stem}.normalized.mp4")

    if temp_path.exists():
        temp_path.unlink()

    for attempt in ATTEMPTS:
        if temp_path.exists():
            temp_path.unlink()
        encode_mp4(video_path, temp_path, attempt)
        if get_size_bytes(temp_path) <= FILE_SIZE_THRESHOLD_BYTES:
            if target_path.exists() and not paths_equivalent(target_path, video_path):
                target_path.unlink()
            temp_path.replace(target_path)
            if not paths_equivalent(video_path, target_path) and video_path.exists():
                video_path.unlink()
            return target_path

    # Keep the best-effort final output even if it exceeds threshold,
    # but make that explicit to the caller.
    if target_path.exists() and not paths_equivalent(target_path, video_path):
        target_path.unlink()
    temp_path.replace(target_path)
    if not paths_equivalent(video_path, target_path) and video_path.exists():
        video_path.unlink()
    return target_path


def discover_videos(video_root: Path) -> list[Path]:
    videos = []
    for path in video_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(path)
    return sorted(videos)


def update_labels_csv(labels_csv: Path, path_mapping: dict[str, str]) -> int:
    with labels_csv.open("r", newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "video" not in fieldnames:
        return 0

    stem_mapping: dict[tuple[str, str], str] = {}
    for _, new_path in path_mapping.items():
        new_rel_path = Path(new_path)
        key = (new_rel_path.parent.as_posix().lower(), new_rel_path.stem.lower())
        stem_mapping[key] = new_path

    update_count = 0
    for row in rows:
        old_video_path = (row.get("video") or "").strip()
        if old_video_path in path_mapping:
            new_video_path = path_mapping[old_video_path]
            if new_video_path != old_video_path:
                row["video"] = new_video_path
                update_count += 1
            continue

        old_rel_path = Path(old_video_path)
        fallback_key = (old_rel_path.parent.as_posix().lower(), old_rel_path.stem.lower())
        if fallback_key in stem_mapping:
            new_video_path = stem_mapping[fallback_key]
            if new_video_path != old_video_path:
                row["video"] = new_video_path
                update_count += 1

    with labels_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return update_count


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    video_root = repo_root / DEFAULT_VIDEO_ROOT
    labels_csv = repo_root / DEFAULT_LABELS_CSV

    if not ffmpeg_available():
        raise RuntimeError("ffmpeg and ffprobe are required but not available in PATH.")

    if not video_root.exists():
        raise FileNotFoundError(f"Video root not found: {video_root}")

    path_mapping: dict[str, str] = {}
    videos = discover_videos(video_root)

    if not videos:
        print(f"No video files found under: {video_root}")
        return

    failures: list[tuple[Path, int]] = []
    for video in videos:
        original_rel = video.relative_to(repo_root).as_posix()
        video = standardize_extension_case(video)
        standardized_rel = video.relative_to(repo_root).as_posix()
        if standardized_rel != original_rel:
            path_mapping[original_rel] = standardized_rel
            print(f"Renamed extension casing: {original_rel} -> {standardized_rel}")

        original_size = get_size_bytes(video)
        if video.suffix == ".mp4" and original_size <= FILE_SIZE_THRESHOLD_BYTES:
            path_mapping[standardized_rel] = standardized_rel
            print(f"{standardized_rel} already normalized ({original_size / (1024 * 1024):.2f}MB)")
            continue

        normalized_path = normalize_video(video)
        normalized_rel = normalized_path.relative_to(repo_root).as_posix()
        normalized_size = get_size_bytes(normalized_path)
        path_mapping[standardized_rel] = normalized_rel

        size_mb = normalized_size / (1024 * 1024)
        original_mb = original_size / (1024 * 1024)
        print(f"{standardized_rel} -> {normalized_rel} ({original_mb:.2f}MB -> {size_mb:.2f}MB)")

        if normalized_size > FILE_SIZE_THRESHOLD_BYTES:
            failures.append((normalized_path, normalized_size))

    if labels_csv.exists():
        updated = update_labels_csv(labels_csv, path_mapping)
        print(f"Updated {updated} CSV row(s) in {labels_csv.relative_to(repo_root)}")
    else:
        print(f"Labels CSV not found; skipping path update: {labels_csv}")

    if failures:
        formatted = ", ".join(
            f"{path.relative_to(repo_root).as_posix()} ({size / (1024 * 1024):.2f}MB)"
            for path, size in failures
        )
        raise RuntimeError(
            f"Normalization completed but some files exceed {FILE_SIZE_THRESHOLD_MB}MB: {formatted}"
        )

    print("All videos normalized and within size threshold.")


if __name__ == "__main__":
    main()
