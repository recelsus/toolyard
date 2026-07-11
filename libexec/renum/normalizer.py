from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from errors import OutputError
from model import Stats


IMAGE_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
}

NUMBERED_NAME_RE = re.compile(r"^(?P<prefix>.*?)(?P<number>[0-9]+)$")


def normalize_tree(root: Path, dry_run: bool = False) -> Stats:
    stats = Stats()
    for directory in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: p.as_posix()):
        _normalize_directory(directory, stats, dry_run)
    _normalize_directory(root, stats, dry_run)
    return stats


def _normalize_directory(directory: Path, stats: Stats, dry_run: bool) -> None:
    groups: dict[tuple[str, str], list[tuple[Path, str, int]]] = defaultdict(list)
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        match = NUMBERED_NAME_RE.match(path.stem)
        if match is None:
            continue
        prefix = match.group("prefix")
        number_text = match.group("number")
        groups[(prefix, path.suffix.lower())].append((path, number_text, int(number_text)))

    for (prefix, suffix), candidates in groups.items():
        _normalize_group(directory, prefix, suffix, candidates, stats, dry_run)


def _normalize_group(
    directory: Path,
    prefix: str,
    suffix: str,
    candidates: list[tuple[Path, str, int]],
    stats: Stats,
    dry_run: bool,
) -> None:
    stats.images += len(candidates)
    digit_widths = {len(number_text) for _, number_text, _ in candidates}
    if len(digit_widths) == 1:
        return

    width = max(digit_widths)
    by_number: dict[int, list[Path]] = defaultdict(list)
    for path, _, number in candidates:
        by_number[number].append(path)

    final_names: dict[Path, str] = {}
    for number in sorted(by_number):
        paths = by_number[number]
        padded = f"{number:0{width}d}"
        if len(paths) == 1:
            final_names[paths[0]] = f"{prefix}{padded}{suffix}"
            continue
        stats.conflicts += len(paths)
        for index, path in enumerate(paths):
            final_names[path] = f"{prefix}{padded}-{_suffix_label(index)}{suffix}"

    if len(set(final_names.values())) != len(final_names):
        raise OutputError(f"could not resolve filename conflicts in: {directory}")

    renames = {src: directory / name for src, name in final_names.items() if src.name != name}
    stats.renamed += len(renames)
    if dry_run or not renames:
        return

    temp_paths: dict[Path, Path] = {}
    for index, src in enumerate(renames):
        tmp = directory / f".renum-tmp-{index}-{src.name}"
        while tmp.exists():
            tmp = directory / f".renum-tmp-{index}-{tmp.name}"
        temp_paths[src] = tmp

    try:
        for src, tmp in temp_paths.items():
            src.rename(tmp)
        for src, tmp in temp_paths.items():
            tmp.rename(renames[src])
    except Exception as exc:
        raise OutputError(f"failed to rename files in: {directory}") from exc


def _suffix_label(index: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    label = ""
    current = index
    while True:
        label = alphabet[current % 26] + label
        current = current // 26 - 1
        if current < 0:
            return label
