#!/usr/bin/env python3
"""Append audio duration to MP3 filenames.

Examples:
    python audio_files.py /path/to/music
    python audio_files.py /path/to/music --dry-run
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


DURATION_SUFFIX_RE = re.compile(r"__(?:\d+h\d{2}m\d{2}s(?:\.\d{3})?|\d+m\d{2}s(?:\.\d{3})?|\d+s(?:\.\d{3})?)$")


def format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    milliseconds = int(round((seconds - total_seconds) * 1000))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}.{milliseconds:03d}s"
    if minutes:
        return f"{minutes}m{secs:02d}.{milliseconds:03d}s"
    return f"{secs}.{milliseconds:03d}s"


def get_audio_duration(path: Path) -> float:
    try:
        from mutagen.mp3 import MP3
    except ImportError:
        pass
    else:
        try:
            return MP3(str(path)).info.length
        except Exception:
            pass

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"Could not determine duration for {path}. Install mutagen or ffprobe."
        ) from exc


def iter_mp3_files(folder: Path) -> Iterable[Path]:
    for path in sorted(folder.rglob("*.mp3")):
        if path.is_file():
            yield path


def build_new_name(path: Path, duration: float) -> Path:
    suffix = format_duration(duration)
    stem = path.stem
    parent = path.parent
    new_name = f"{stem}__{suffix}{path.suffix}"
    candidate = parent / new_name

    counter = 1
    while candidate.exists() and candidate != path:
        candidate = parent / f"{stem}__{suffix}({counter}){path.suffix}"
        counter += 1

    return candidate


def rename_mp3_files(folder: Path, dry_run: bool = False) -> int:
    renamed = 0
    for path in iter_mp3_files(folder):
        if not path.is_file():
            continue

        if DURATION_SUFFIX_RE.search(path.stem):
            print(f"Skipping already renamed file: {path.name}")
            continue

        try:
            duration = get_audio_duration(path)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            continue

        new_path = build_new_name(path, duration)
        if new_path == path:
            continue

        print(f"{'Would rename' if dry_run else 'Renaming'}: {path.name} -> {new_path.name}")
        if not dry_run:
            path.rename(new_path)
        renamed += 1

    return renamed


def main() -> int:
    parser = argparse.ArgumentParser(description="Append MP3 audio length to filenames")
    parser.add_argument("folder", nargs="?", default=".", help="Folder containing MP3 files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be renamed")
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 1

    renamed = rename_mp3_files(folder, dry_run=args.dry_run)
    print(f"Processed {renamed} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
