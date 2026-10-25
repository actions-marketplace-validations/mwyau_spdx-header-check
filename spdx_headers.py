#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Albert M. W. Yau
#
# SPDX-License-Identifier: BSD-3-Clause

"""Check REUSE-style SPDX source headers; edit only on explicit request."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HASH_SUFFIXES = frozenset({".py", ".pyi", ".sh", ".bash"})
SLASH_SUFFIXES = frozenset(
    {
        ".rs", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx", ".hh",
        ".cu", ".cuh", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts",
        ".cts", ".tsx",
    }
)
SUFFIXES = HASH_SUFFIXES | SLASH_SUFFIXES
MANIFESTS = frozenset({"pyproject.toml", "Cargo.toml"})
EXCLUDED_DIRS = frozenset(
    {"third_party", "vendor", "vendored", "node_modules", "build", "dist", ".venv"}
)

# Metadata must be at the beginning; a shebang and Python encoding are legal first.
HEADER = re.compile(
    r"\A(?P<preamble>(?:\#![ \t]*/[^\n]*\n)?"
    r"(?:\#[^\n]*coding[:=][ \t]*[-\w.]+[^\n]*\n)?)"
    r"(?P<copyrights>(?:(?:#|//) SPDX-FileCopyrightText: [^\n]+\n)+)"
    r"(?P<separator>(?:(?:#|//)?[ \t]*\n)*)"
    r"(?P<license>(?:#|//) SPDX-License-Identifier: [^\n]+\n)"
    r"(?P<after>(?:(?:#|//)?[ \t]*\n)*)"
)
NOTICE = re.compile(
    r"^(?P<prefix>(?:#|//) SPDX-FileCopyrightText: )"
    r"(?P<first>\d{4})(?:-(?P<last>\d{4}))? (?P<holder>[^\n]+)\n$"
)


def candidates() -> list[Path]:
    """Find only eligible first-party files tracked by Git."""
    result = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, check=True
    )
    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return [
        Path(name)
        for name in names
        if name
        and not (set(Path(name).parts[:-1]) & EXCLUDED_DIRS)
        and (Path(name).suffix in SUFFIXES or Path(name).name in MANIFESTS)
    ]


def check_file(
    path: Path, *, fix: bool, year: int | None, holder: str | None
) -> tuple[bool, bool]:
    """Return (valid, holder_matched); never invent copyright metadata."""
    if not path.is_file():
        print(f"{path}: file does not exist or is not regular", file=sys.stderr)
        return False, False
    original_bytes = path.read_bytes()
    if not original_bytes:
        return True, False  # Zero-byte files are exempt by REUSE Specification 3.3.
    try:
        original = original_bytes.decode("utf-8")
    except UnicodeDecodeError:
        print(f"{path}: not UTF-8", file=sys.stderr)
        return False, False
    newline = "\r\n" if b"\r\n" in original_bytes else "\n"
    content = original.replace("\r\n", "\n")
    match = HEADER.match(content)
    if not match:
        lines = content.splitlines()[:20]
        found = next(
            (n for n, line in enumerate(lines, 1) if "SPDX-FileCopyrightText:" in line),
            None,
        )
        detail = f"misplaced header at line {found}" if found else "missing SPDX header"
        print(f"{path}: {detail}", file=sys.stderr)
        return False, False

    copyrights = match.group("copyrights")
    license_line = match.group("license")
    prefix = "//" if copyrights.startswith("// ") else "#"
    if path.suffix in HASH_SUFFIXES or path.name in MANIFESTS:
        expected_prefix = "#"
    elif path.suffix in SLASH_SUFFIXES:
        expected_prefix = "//"
    else:
        expected_prefix = prefix  # Explicitly supplied files may be other types.
    if prefix != expected_prefix:
        print(f"{path}: expected {expected_prefix} comments", file=sys.stderr)
        return False, False
    if any(not line.startswith(prefix + " ") for line in copyrights.splitlines()):
        print(f"{path}: inconsistent copyright comment prefixes", file=sys.stderr)
        return False, False
    if not license_line.startswith(prefix + " "):
        print(f"{path}: license comment prefix differs from copyright", file=sys.stderr)
        return False, False
    holder_matched = False
    if year is not None:
        updated = []
        for line in copyrights.splitlines(keepends=True):
            notice = NOTICE.fullmatch(line)
            if notice and notice.group("holder") == holder:
                holder_matched = True
                first = int(notice.group("first"))
                last = max(year, int(notice.group("last") or first))
                years = f"{first}-{last}" if last > first else str(first)
                line = f"{notice.group('prefix')}{years} {holder}\n"
            elif line.rstrip("\n").endswith(" " + holder):
                # Do not rewrite non-contiguous years or other valid notices.
                print(
                    f"{path}: unsupported year format for {holder!r}; unchanged",
                    file=sys.stderr,
                )
                return False, False
            updated.append(line)
        copyrights = "".join(updated)

    body = content[match.end() :]
    expected = (
        match.group("preamble") + copyrights + prefix + "\n" + license_line
        + ("\n" + body if body else "")
    )
    if expected == content:
        return True, holder_matched
    if fix or year is not None:
        path.write_bytes(expected.replace("\n", newline).encode("utf-8"))
        print(f"updated {path}")
        return True, holder_matched
    print(f"{path}: header differs from REUSE-style spacing", file=sys.stderr)
    return False, holder_matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="normalize existing headers")
    parser.add_argument("--year", type=int, help="manually extend a named holder's year")
    parser.add_argument("--holder", help="holder whose year may be extended")
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    if args.year is not None:
        if not (1000 <= args.year <= 9999):
            parser.error("--year must be a four-digit year")
        if not args.holder:
            parser.error("--year requires --holder")
    if args.holder and args.year is None:
        parser.error("--holder requires --year")
    try:
        paths = args.files or candidates()
    except (subprocess.CalledProcessError, OSError) as exc:
        parser.error(f"could not list tracked files: {exc}")
    failed = False
    matched = False
    for path in paths:
        if not path.exists() and not args.files:
            # An unstaged deletion may still be listed by git ls-files.
            continue
        valid, found = check_file(
            path, fix=args.fix, year=args.year, holder=args.holder
        )
        failed |= not valid
        matched |= found
    if args.year is not None and not matched:
        print(f"no supported copyright notice found for {args.holder!r}", file=sys.stderr)
        failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
