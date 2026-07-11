from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InputTarget:
    raw: str
    path: Path
    kind: str


@dataclass(frozen=True)
class Options:
    input_args: list[str]
    output: Path | None
    force: bool
    max_depth: int
    dry_run: bool
    verbose: bool
    yes: bool
    limit: int | None


@dataclass
class Stats:
    images: int = 0
    renamed: int = 0
    conflicts: int = 0
    internal_archives: int = 0
    written: bool = False
