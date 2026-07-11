#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from errors import EXIT_CLI, CliError, InputError, RenumError
from model import InputTarget, Stats
from pathing import ensure_preflight, resolve_outputs, resolve_targets
from processor import process_target


HELP_TEXT = """\
renum - normalize numeric image filenames and write a ZIP archive

Usage:
  renum INPUT... [options]
  renum -h

Inputs:
  ZIP/RAR archive files, directories, or glob patterns.
  A path ending with '/' is treated as a directory path and scans archive files directly inside it.
  Glob patterns such as './*-type.zip' are supported.
  Target image extensions are .jpg, .jpeg, and .png.

Output:
  By default, writes INPUT.normalized.zip next to the input.
  RAR inputs are extracted and saved back as ZIP; renum never creates RAR archives.
  Existing output files are not overwritten unless --force is used.

Options:
  -o, --output PATH     Write ZIP to PATH
  -f, --force           Overwrite an existing output ZIP
  -y, --yes             Skip confirmation for batch targets
  -l, -limit, --limit N Process at most N target archives
  --max-depth N         Maximum depth for internal archives (default: 3)
  --dry-run             Scan and report without writing output
  -v, --verbose         Print extra details
  -h, --help, -help     Show this help

Dependencies:
  ZIP input/output uses Python standard library only.
  RAR input requires 7z or unrar in PATH for extraction only.

Examples:
  renum ./
  renum dir/
  renum './*-type.zip'
  renum ./archive.zip
  renum archive.rar
"""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        raise SystemExit(EXIT_CLI)


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(add_help=False, prog="renum", description="Normalize numeric image filenames.")
    parser.add_argument("input", nargs="*")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true")
    parser.add_argument("-l", "-limit", "--limit", type=int)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-h", "--help", "-help", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    ns = parser.parse_args(argv)

    if ns.help or not ns.input:
        print(HELP_TEXT, end="")
        return 0

    try:
        cwd = Path.cwd()
        targets, needs_confirmation = resolve_targets(ns.input, cwd)
        if not targets:
            raise InputError("no target ZIP/RAR files found")
        if ns.limit is not None and ns.limit < 1:
            raise CliError("-l/-limit must be 1 or greater")

        found_count = len(targets)
        selected_targets = targets[: ns.limit] if ns.limit is not None else targets
        outputs = resolve_outputs(ns.output, selected_targets, cwd)

        if needs_confirmation and not ns.yes and not ns.dry_run:
            if not confirm_batch(found_count, len(selected_targets)):
                print("renum: aborted")
                return 0

        for target in selected_targets:
            ensure_preflight(target, outputs[target.path], ns.force or ns.dry_run)

        results = []
        for target in selected_targets:
            output = outputs[target.path]
            stats, extractor = process_target(
                target=target,
                output=output,
                force=ns.force,
                max_depth=ns.max_depth,
                dry_run=ns.dry_run,
            )
            results.append((target, output, stats, extractor))
    except RenumError as exc:
        print(f"renum: error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("renum: interrupted", file=sys.stderr)
        return 1

    print(f"Targets:    {len(results)}")
    for index, (target, output, stats, extractor) in enumerate(results, start=1):
        if len(results) > 1:
            print()
            print(f"[{index}/{len(results)}]")
        print_result(target, output, stats, extractor, dry_run=ns.dry_run)
    return 0


def confirm_batch(found_count: int, selected_count: int) -> bool:
    if selected_count == found_count:
        prompt = f"Found {found_count} target ZIP/RAR file(s). Start processing? [y/N] "
    else:
        prompt = f"Found {found_count} target ZIP/RAR file(s). Process first {selected_count}? [y/N] "
    print(prompt, end="", flush=True)
    answer = sys.stdin.readline().strip().lower()
    return answer in {"y", "yes"}


def print_result(target: InputTarget, output: Path, stats: Stats, extractor: str, dry_run: bool) -> None:
    print(f"Input:      {target.path}")
    print(f"Kind:       {target.kind}")
    print(f"Extractor:  {extractor}")
    print(f"Images:     {stats.images}")
    print(f"Renamed:    {stats.renamed}")
    print(f"Conflicts:  {stats.conflicts}")
    print(f"Internal:   {stats.internal_archives}")
    if dry_run:
        print("Output:     (dry-run)")
    elif stats.written:
        print(f"Output:     {output}")
    else:
        print("Output:     (not written; already normalized or no target files)")


if __name__ == "__main__":
    raise SystemExit(main())
