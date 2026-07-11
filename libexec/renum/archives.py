from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

from errors import DependencyError, InputError


def find_rar_extractor() -> str | None:
    for command in ("7z", "unrar"):
        found = shutil.which(command)
        if found:
            return command
    return None


def require_rar_extractor() -> str:
    extractor = find_rar_extractor()
    if extractor is None:
        raise DependencyError(
            "RAR extraction requires one of these commands in PATH: 7z, unrar. No processing was performed."
        )
    return extractor


def extract_archive(archive: Path, destination: Path, extractor: str | None = None, kind: str | None = None) -> str:
    archive_kind = kind
    if archive_kind is None:
        suffix = archive.suffix.lower()
        if suffix == ".zip":
            archive_kind = "zip"
        elif suffix == ".rar":
            archive_kind = "rar"

    if archive_kind == "zip":
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(destination)
        except zipfile.BadZipFile as exc:
            raise InputError(f"broken ZIP archive: {archive}") from exc
        return "zipfile"

    if archive_kind == "rar":
        command = extractor or require_rar_extractor()
        if command == "7z":
            proc = subprocess.run(
                ["7z", "x", "-y", f"-o{destination}", str(archive)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        else:
            proc = subprocess.run(
                ["unrar", "x", "-o+", str(archive), str(destination)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise InputError(f"failed to extract RAR archive: {archive}\n{detail}")
        return command

    raise InputError(f"unsupported archive type: {archive}")


def write_zip(source_dir: Path, output: Path) -> None:
    tmp_output = output.with_name(f".{output.name}.tmp")
    if tmp_output.exists():
        tmp_output.unlink()
    try:
        with zipfile.ZipFile(tmp_output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(source_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(source_dir).as_posix())
        tmp_output.replace(output)
    except Exception:
        if tmp_output.exists():
            tmp_output.unlink()
        raise
