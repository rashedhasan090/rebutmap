import contextlib
import io
import json
import os
import unittest

from rebutmap.cli import main

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


def run(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, buf.getvalue()


class CliTests(unittest.TestCase):
    def args(self, *extra):
        return (os.path.join(EX, "reviews.md"), os.path.join(EX, "response.md"),
                "--paper", os.path.join(EX, "paper_v2.tex"),
                "--before", os.path.join(EX, "paper_v1.tex")) + extra

    def test_demo_text(self):
        code, out = run(*self.args())
        self.assertEqual(code, 1)
        for c in ("unaddressed", "dangling-locator", "phantom-quote", "already-present",
                  "untouched-section", "mislabeled", "hollow", "deferred"):
            self.assertIn(c, out)

    def test_json(self):
        code, out = run(*self.args("--format", "json"))
        data = json.loads(out)
        self.assertEqual(data["summary"]["comments"], 7)
        self.assertEqual(data["summary"]["missing"], 1)
        self.assertEqual(data["summary"]["error"], 3)

    def test_markdown_and_fail_on_never(self):
        code, out = run(*self.args("--format", "markdown", "--fail-on", "never"))
        self.assertEqual(code, 0)
        self.assertIn("| [ ] | R2.W2 |", out)
        self.assertIn("| [x] | R1.1 |", out)

    def test_ignore_and_min_severity(self):
        code, out = run(*self.args("--ignore", "unaddressed", "--ignore", "dangling-locator",
                                   "--ignore", "phantom-quote", "--min-severity", "warning"))
        self.assertEqual(code, 0)
        self.assertNotIn("deferred ", out)
        code, _ = run(*self.args("--ignore", "nope"))
        self.assertEqual(code, 2)

    def test_missing_file(self):
        code, _ = run("nope.md", "nope2.md")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
