# SPDX-FileCopyrightText: 2026 Albert M. W. Yau
#
# SPDX-License-Identifier: BSD-3-Clause

"""Regression tests for a standalone, dependency-free SPDX checker."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "spdx_headers.py"
COPYRIGHT = "# SPDX-FileCopyrightText: 2026 Albert M. W. Yau\n"
LICENSE = "# SPDX-License-Identifier: MIT\n"
PREFERRED = COPYRIGHT + "#\n" + LICENSE + "\n"
COMPACT = COPYRIGHT + LICENSE + "\n"


class HeaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "example.py"

    def run_check(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args, str(self.path)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_missing_explicit_path_fails(self):
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)

    def test_missing_explicit_path_with_fix_fails(self):
        result = self.run_check("--fix")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.path.exists())

    def test_year_requires_matching_holder(self):
        self.path.write_text(PREFERRED + "pass\n", encoding="utf-8")
        before = self.path.read_bytes()
        result = self.run_check("--year", "2027", "--holder", "Someone Else")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no supported copyright notice", result.stderr)
        self.assertEqual(self.path.read_bytes(), before)

    def test_year_already_covered_is_success(self):
        self.path.write_text(
            "# SPDX-FileCopyrightText: 2022-2027 Example Author\n"
            "#\n# SPDX-License-Identifier: MIT\n\npass\n",
            encoding="utf-8",
        )
        result = self.run_check("--year", "2027", "--holder", "Example Author")
        self.assertEqual(result.returncode, 0)
        self.assertIn("2022-2027", self.path.read_text())

    def test_multiple_year_formats_preserved(self):
        self.path.write_text(
            "# SPDX-FileCopyrightText: 2016, 2018-2019 Jane Doe\n"
            "# SPDX-FileCopyrightText: 2026 Example Author\n"
            "#\n# SPDX-License-Identifier: MIT\n\npass\n",
            encoding="utf-8",
        )
        result = self.run_check("--year", "2027", "--holder", "Example Author")
        self.assertEqual(result.returncode, 0)
        after = self.path.read_text()
        self.assertIn("2016, 2018-2019 Jane Doe", after)
        self.assertIn("2026-2027 Example Author", after)

    def test_unsupported_year_format_fails_without_changes(self):
        self.path.write_text(
            "# SPDX-FileCopyrightText: 2016, 2018-2019 Jane Doe\n"
            "#\n# SPDX-License-Identifier: MIT\n\npass\n",
            encoding="utf-8",
        )
        before = self.path.read_bytes()
        result = self.run_check("--year", "2027", "--holder", "Jane Doe")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unsupported year format", result.stderr)
        self.assertEqual(self.path.read_bytes(), before)

    def test_holder_requires_year(self):
        self.path.write_text(PREFERRED, encoding="utf-8")
        result = self.run_check("--holder", "Example Author")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--holder requires --year", result.stderr)

    def test_year_on_multiple_files_matches_any(self):
        other = Path(self.temp.name) / "other.py"
        self.path.write_text(PREFERRED, encoding="utf-8")
        other.write_text(
            "# SPDX-FileCopyrightText: 2019 Other Holder\n"
            "#\n# SPDX-License-Identifier: MIT\n\npass\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT), "--year", "2027",
                "--holder", "Albert M. W. Yau", str(self.path), str(other),
            ],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("2026-2027 Albert M. W. Yau", self.path.read_text())
        self.assertIn("2019 Other Holder", other.read_text())

    def test_canonical(self):
        self.path.write_text(PREFERRED + "print(1)\n", encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 0)

    def test_compact_needs_fix(self):
        self.path.write_text(COMPACT + "pass\n", encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 1)
        self.assertEqual(self.run_check("--fix").returncode, 0)
        self.assertEqual(self.path.read_text(), PREFERRED + "pass\n")

    def test_header_cannot_follow_imports(self):
        self.path.write_text("import sys\n\n" + PREFERRED, encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("misplaced", result.stderr)
        self.assertEqual(self.run_check("--fix").returncode, 1)

    def test_empty_is_exempt(self):
        self.path.write_bytes(b"")
        self.assertEqual(self.run_check().returncode, 0)

    def test_shebang_and_encoding(self):
        self.path.write_text(
            "#!/usr/bin/env python3\n# coding: utf-8\n"
            + PREFERRED + "print(1)\n", encoding="utf-8"
        )
        self.assertEqual(self.run_check().returncode, 0)

    def test_rust_inner_attribute_is_not_shebang(self):
        self.path = Path(self.temp.name) / "example.rs"
        self.path.write_text(
            "#![no_std]\n"
            "// SPDX-FileCopyrightText: 2026 Example\n"
            "//\n"
            "// SPDX-License-Identifier: MIT\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_check().returncode, 1)

    def test_rust_comment_style(self):
        self.path = Path(self.temp.name) / "example.rs"
        self.path.write_text(
            "// SPDX-FileCopyrightText: 2026 Example\n"
            "//\n"
            "// SPDX-License-Identifier: MIT\n\nfn main() {}\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_check().returncode, 0)

    def test_supported_slash_comment_extensions(self):
        extensions = (
            ".rs", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx",
            ".hh", ".cu", ".cuh", ".js", ".mjs", ".cjs", ".jsx",
            ".ts", ".mts", ".cts", ".tsx",
        )
        source = (
            "// SPDX-FileCopyrightText: 2026 Example Author\n"
            "//\n"
            "// SPDX-License-Identifier: MIT\n\n"
            "const value = 1;\n"
        )
        for ext in extensions:
            with self.subTest(ext=ext):
                self.path = Path(self.temp.name) / ("example" + ext)
                self.path.write_text(source, encoding="utf-8")
                self.assertEqual(self.run_check().returncode, 0)

    def test_supported_hash_comment_extensions(self):
        for ext in (".py", ".pyi", ".sh", ".bash"):
            with self.subTest(ext=ext):
                self.path = Path(self.temp.name) / ("example" + ext)
                self.path.write_text(PREFERRED + "pass\n", encoding="utf-8")
                self.assertEqual(self.run_check().returncode, 0)

    def test_wrong_comment_style_is_rejected_even_with_fix(self):
        for ext, valid_header in (
            (".py", "// SPDX-FileCopyrightText: 2026 Author\n"),
            (".rs", "# SPDX-FileCopyrightText: 2026 Author\n"),
            (".js", "# SPDX-FileCopyrightText: 2026 Author\n"),
            (".cu", "# SPDX-FileCopyrightText: 2026 Author\n"),
        ):
            with self.subTest(ext=ext):
                self.path = Path(self.temp.name) / ("example" + ext)
                prefix = "//" if valid_header.startswith("//") else "#"
                self.path.write_text(
                    valid_header
                    + prefix + "\n"
                    + prefix + " SPDX-License-Identifier: MIT\n\n"
                    + "code\n",
                    encoding="utf-8",
                )
                self.assertNotEqual(self.run_check().returncode, 0)
                self.assertNotEqual(self.run_check("--fix").returncode, 0)

    def test_js_shebang(self):
        self.path = Path(self.temp.name) / "example.js"
        self.path.write_text(
            "#!/usr/bin/env node\n"
            "// SPDX-FileCopyrightText: 2026 Example Author\n"
            "//\n"
            "// SPDX-License-Identifier: MIT\n\n"
            "console.log(1);\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_check().returncode, 0)

    def test_explicit_year_and_other_owners(self):
        self.path.write_text(
            "# SPDX-FileCopyrightText: 2015 Third Party\n"
            + COPYRIGHT + "#\n" + LICENSE + "\npass\n",
            encoding="utf-8",
        )
        self.assertEqual(
            self.run_check("--year", "2027", "--holder", "Albert M. W. Yau").returncode,
            0,
        )
        text = self.path.read_text()
        self.assertIn("2015 Third Party", text)
        self.assertIn("2026-2027 Albert M. W. Yau", text)
        self.assertEqual(self.run_check().returncode, 0)

    def test_missing_metadata_not_invented(self):
        self.path.write_text("pass\n", encoding="utf-8")
        self.assertEqual(self.run_check("--fix").returncode, 1)
        self.assertEqual(self.path.read_text(), "pass\n")

    def test_header_only(self):
        self.path.write_text(COPYRIGHT + "#\n" + LICENSE, encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 0)


if __name__ == "__main__":
    unittest.main()
