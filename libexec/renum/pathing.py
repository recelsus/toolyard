from __future__ import annotations

import os
import glob
from pathlib import Path

from errors import CliError, InputError, OutputError
from model import InputTarget


GLOB_CHARS = "*?["


def resolve_input(raw: str, cwd: Path) -> InputTarget:
    requested_directory = raw.endswith(("/", os.sep))
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = cwd / path
    path = path.resolve(strict=False)

    if requested_directory:
        if not path.exists():
            raise InputError(f"input directory does not exist: {raw}")
        if not path.is_dir():
            raise InputError(f"path ends with '/' but is not a directory: {raw}")
        return InputTarget(raw=raw, path=path, kind="directory")

    if not path.exists():
        raise InputError(f"input does not exist: {raw}")
    if path.is_dir():
        return InputTarget(raw=raw, path=path, kind="directory")
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix == ".zip":
            return InputTarget(raw=raw, path=path, kind="zip")
        if suffix == ".rar":
            return InputTarget(raw=raw, path=path, kind="rar")
        detected = detect_archive_kind(path)
        if detected is not None:
            return InputTarget(raw=raw, path=path, kind=detected)
        raise InputError(f"unsupported input file type: {raw}")

    raise InputError(f"unsupported input path: {raw}")


def resolve_targets(raw_inputs: list[str], cwd: Path) -> tuple[list[InputTarget], bool]:
    targets: list[InputTarget] = []
    needs_confirmation = len(raw_inputs) != 1

    for raw in raw_inputs:
        if _has_glob(raw):
            matches = _expand_glob(raw, cwd)
            needs_confirmation = True
            for path in matches:
                targets.append(_target_from_existing_path(raw, path))
            continue

        target = resolve_input(raw, cwd)
        if target.kind == "directory":
            needs_confirmation = True
            targets.extend(_archives_in_directory(target.path))
        else:
            targets.append(target)

    unique: dict[Path, InputTarget] = {}
    for target in targets:
        unique.setdefault(target.path, target)
    return list(unique.values()), needs_confirmation


def _has_glob(raw: str) -> bool:
    return any(char in raw for char in GLOB_CHARS)


def _expand_glob(raw: str, cwd: Path) -> list[Path]:
    pattern = str(Path(raw).expanduser())
    if not Path(pattern).is_absolute():
        pattern = str(cwd / pattern)
    return sorted(Path(path).resolve(strict=False) for path in glob.glob(pattern, recursive=True))


def _archives_in_directory(directory: Path) -> list[InputTarget]:
    targets = []
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        if path.is_file():
            try:
                targets.append(_target_from_existing_path(str(path), path))
            except InputError:
                continue
    return targets


def _target_from_existing_path(raw: str, path: Path) -> InputTarget:
    path = path.resolve(strict=False)
    if not path.exists():
        raise InputError(f"input does not exist: {raw}")
    if path.is_dir():
        raise InputError(f"glob matched a directory, not an archive: {path}")
    if not path.is_file():
        raise InputError(f"unsupported input path: {path}")

    suffix = path.suffix.lower()
    if suffix == ".zip":
        return InputTarget(raw=raw, path=path, kind="zip")
    if suffix == ".rar":
        return InputTarget(raw=raw, path=path, kind="rar")
    detected = detect_archive_kind(path)
    if detected is not None:
        return InputTarget(raw=raw, path=path, kind=detected)
    raise InputError(f"unsupported input file type: {path}")


def detect_archive_kind(path: Path) -> str | None:
    try:
        with path.open("rb") as file:
            header = file.read(8)
    except OSError as exc:
        raise InputError(f"input file is not readable: {path}") from exc
    if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06") or header.startswith(b"PK\x07\x08"):
        return "zip"
    if header.startswith(b"Rar!\x1a\x07"):
        return "rar"
    return None


def default_output_for(target: InputTarget) -> Path:
    if target.kind == "directory":
        parent = target.path.parent
        stem = target.path.name or target.path.resolve().name
    else:
        parent = target.path.parent
        stem = target.path.stem
    return parent / f"{stem}.normalized.zip"


def resolve_output(output_arg: Path | None, target: InputTarget, cwd: Path) -> Path:
    output = output_arg if output_arg is not None else default_output_for(target)
    output = output.expanduser()
    if not output.is_absolute():
        output = cwd / output
    output = output.resolve(strict=False)
    if output.suffix.lower() != ".zip":
        raise CliError("output path must end with .zip")
    return output


def resolve_outputs(output_arg: Path | None, targets: list[InputTarget], cwd: Path) -> dict[Path, Path]:
    if output_arg is not None and len(targets) != 1:
        raise CliError("-o/--output can only be used with a single target archive")
    return {target.path: resolve_output(output_arg, target, cwd) for target in targets}


def ensure_preflight(target: InputTarget, output: Path, force: bool) -> None:
    if not os.access(target.path, os.R_OK):
        raise InputError(f"input is not readable: {target.path}")

    output_dir = output.parent
    if not output_dir.exists() or not output_dir.is_dir():
        raise OutputError(f"output directory does not exist: {output_dir}")
    if not os.access(output_dir, os.W_OK):
        raise OutputError(f"output directory is not writable: {output_dir}")
    if target.kind == "directory" and not os.access(target.path, os.R_OK):
        raise InputError(f"input directory is not readable: {target.path}")
    if output.exists() and not force:
        raise OutputError(f"output already exists: {output}")
