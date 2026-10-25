# SPDX Header Check

Check SPDX copyright and license headers in Python, shell, Rust, C/C++, CUDA, JavaScript, and TypeScript source files. The checker works with [prek/pre-commit](.pre-commit-hooks.yaml), [GitHub Actions](action.yml), and the command line.

It checks that headers appear at the start of each file, use the appropriate comment syntax, and follow the format written by [REUSE](https://reuse.software/). Checks do not modify files or change copyright years.

## Header format

```python
# SPDX-FileCopyrightText: 2026 Example Author
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
```

Use `#` comments for Python and shell, and `//` for Rust, C/C++, CUDA, JavaScript, and TypeScript. An interpreter shebang stays on the first line, before the header. Zero-byte files, including empty `__init__.py` and `py.typed` markers, are skipped, as permitted by the [REUSE specification](https://reuse.software/spec/).

The blank comment line between the SPDX fields matches `reuse annotate`. The blank line after the header separates it from the source code.

## Pre-commit / prek

Add to `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/mwyau/spdx-header-check
  rev: v0.1.0
  hooks:
    - id: spdx-header-check
```

## GitHub Actions

Run the checker after checking out the repository:

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: mwyau/spdx-header-check@v0.1.0
```

The Action checks all eligible tracked files. It requires Python on `PATH`.

## Command line

From a checkout of this repository:

```bash
python spdx_headers.py                                    # check tracked files
python spdx_headers.py src/module.py                      # check one file
python spdx_headers.py --fix                              # normalize existing headers
python spdx_headers.py --year 2027 --holder "Example Author"
```

The `--fix` option normalizes spacing in existing headers. It does not add missing copyright or license information. Use `reuse annotate` to annotate a new file.

The `--year` option extends a simple year or year range for the specified copyright holder. It fails when no matching notice is found or a matching notice has an unsupported year format; these notices are left unchanged. Other holders are preserved. Year updates are always explicit.

## Files checked

By default, the checker examines Git-tracked `.py`, `.pyi`, `.sh`, `.bash`, `.rs`, `.c`, `.cc`, `.cpp`, `.cxx`, `.h`, `.hpp`, `.hxx`, `.hh`, `.cu`, `.cuh`, `.js`, `.mjs`, `.cjs`, `.jsx`, `.ts`, `.mts`, `.cts`, `.tsx`, `pyproject.toml`, and `Cargo.toml` files. It skips files under vendor, third-party, and build directories. Explicit file arguments override the directory filter; missing requested files are errors.

Generated source files must have headers at the top. Add the header in the generation process so regeneration does not move or remove it. JSON and binary files require separate licensing metadata if full REUSE compliance is needed.

This tool checks header placement and formatting; it does not validate copyright ownership, license compatibility, or full REUSE compliance.

Licensed under [BSD-3-Clause](LICENSE).
