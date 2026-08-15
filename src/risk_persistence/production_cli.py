from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from pathlib import Path
from typing import TextIO

from risk_persistence.production_config import RiskPersistenceConfigurationError
from risk_persistence.production_config import RiskPersistenceProductionConfig
from risk_persistence.production_config import RiskPersistenceProductionError
from risk_persistence.sqlite_production_health import RiskPersistenceHealthStatus
from risk_persistence.sqlite_production_health import SQLiteRiskPersistenceHealthChecker


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    parser = _build_parser()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    if args.command == "verify":
        return _verify(args.project_root, stdout=out, stderr=err)
    parser.print_help(out)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="risk-persistence",
        description="Read-only production RiskArtifact persistence operator commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify canonical production RiskArtifact persistence readiness without writing.",
    )
    verify_parser.add_argument("--project-root", required=True, help="Explicit AI-Investment-Research project root.")
    return parser


def _verify(project_root: str, *, stdout: TextIO, stderr: TextIO) -> int:
    try:
        config = RiskPersistenceProductionConfig.from_project_root(Path(project_root))
        result = SQLiteRiskPersistenceHealthChecker(config).check()
    except (RiskPersistenceConfigurationError, RiskPersistenceProductionError) as exc:
        print(f"CONFIG_ERROR {exc}", file=stderr)
        return 2
    print(_format_result(result), file=stdout)
    if result.status == RiskPersistenceHealthStatus.READY:
        return 0
    return 1


def _format_result(result) -> str:
    parts = [
        result.status.value,
        f"schema={_schema_label(result.schema_version)}",
        f"db={result.db_path_alias}",
    ]
    if result.quick_check_result is not None:
        parts.append(f"quick_check={result.quick_check_result}")
    if result.warnings:
        parts.append(f"warning={','.join(result.warnings)}")
    return " ".join(parts)


def _schema_label(schema_version: int | None) -> str:
    if schema_version is None:
        return "none"
    if schema_version == 0:
        return "empty"
    return f"v{schema_version}"


if __name__ == "__main__":
    raise SystemExit(main())
