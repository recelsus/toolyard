from __future__ import annotations


EXIT_GENERAL = 1
EXIT_CLI = 2
EXIT_DEPENDENCY = 3
EXIT_INPUT = 4
EXIT_OUTPUT = 5


class RenumError(Exception):
    exit_code = EXIT_GENERAL


class CliError(RenumError):
    exit_code = EXIT_CLI


class DependencyError(RenumError):
    exit_code = EXIT_DEPENDENCY


class InputError(RenumError):
    exit_code = EXIT_INPUT


class OutputError(RenumError):
    exit_code = EXIT_OUTPUT
