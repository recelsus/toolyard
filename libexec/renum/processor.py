from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from archives import extract_archive, require_rar_extractor, write_zip
from errors import InputError
from model import InputTarget, Stats
from normalizer import normalize_tree


def process_target(target: InputTarget, output: Path, force: bool, max_depth: int, dry_run: bool) -> tuple[Stats, str]:
    if max_depth < 0:
        raise InputError("max depth must be zero or greater")

    extractor = require_rar_extractor() if target.kind == "rar" else None
    with tempfile.TemporaryDirectory(prefix="renum-") as tmp:
        tmpdir = Path(tmp)
        work = tmpdir / "work"
        work.mkdir()

        used_extractor = "none"
        if target.kind == "directory":
            content = work / target.path.name
            shutil.copytree(target.path, content, symlinks=True)
            root = content
            used_extractor = "directory"
        else:
            root = work
            used_extractor = extract_archive(target.path, root, extractor, kind=target.kind)

        stats = _expand_internal_archives(root, max_depth=max_depth, extractor=extractor)
        normalized = normalize_tree(root, dry_run=dry_run)
        stats.images += normalized.images
        stats.renamed += normalized.renamed
        stats.conflicts += normalized.conflicts

        if stats.renamed > 0 and not dry_run:
            if output.exists() and force:
                output.unlink()
            write_zip(root, output)
            stats.written = True
        return stats, used_extractor


def _expand_internal_archives(root: Path, max_depth: int, extractor: str | None) -> Stats:
    stats = Stats()
    for depth in range(max_depth + 1):
        archives = [
            path
            for path in sorted(root.rglob("*"), key=lambda p: p.as_posix())
            if path.is_file() and path.suffix.lower() in {".zip", ".rar"}
        ]
        if not archives:
            return stats
        if depth >= max_depth:
            raise InputError(f"maximum internal archive depth exceeded: {max_depth}")
        for archive in archives:
            destination = archive.with_suffix("")
            if destination.exists():
                destination = archive.parent / f"{archive.stem}.extracted"
            destination.mkdir()
            extract_archive(archive, destination, extractor)
            archive.unlink()
            stats.internal_archives += 1
    return stats
