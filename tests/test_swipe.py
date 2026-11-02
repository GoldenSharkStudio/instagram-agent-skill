"""swipe.py: the README ranking, baselines, the swipe-file markdown, and
graceful degradation when ig-viral is copied without ig-reel."""

import json
import os
import shutil
import tempfile
import unittest

from _support import SKILLS, fixture, load, read_fixture, run_json, run_tool

sw = load("swipe")


class GoldenReadme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc, cls.a = run_json("swipe", fixture("captured.tsv"))

    def test_header(self):
        self.assertEqual(self.a["n"], 4)
        self.assertEqual(self.a["accounts"], 4)
        self.assertEqual(self.a["baseline"], "account median")

    def test_ranking(self):
        got = [(r["account"], round(r["outlier"], 1), r["formula_id"], r["formula"], r["hook_score"])
               for r in self.a["reels"]]
        self.assertEqual(got, [
            ("@c", 60.0, 9, "The Steal", 57.2),
            ("@a", 37.5, 3, "Nobody Tells You", 85.6),
            ("@d", 3.5, 1, "Cost Confession", 81.4),
            ("@b", 1.3, None, "unclassified", 13.2),
        ])

    def test_batch_summary(self):
        self.assertEqual(self.a["unclassified"], 1)
        self.assertEqual(self.a["top_formulas"], [["The Steal", 1]])
        self.assertEqual(self.a["top_hook_score"], 57.2)
        self.assertEqual(self.a["bottom_hook_score"], 13.2)

    def test_render(self):
        out = run_tool("swipe", fixture("captured.tsv")).stdout
        self.assertIn("SWIPE FILE  ·  4 reels  ·  4 accounts  ·  baseline: account median", out)
        self.assertIn("60.0x  hook  57  #9  The Steal", out)
        self.assertIn("1.3x  hook  13  -   unclassified", out)
        self.assertIn("1,200,000", out)


class Rows(unittest.TestCase):
    def rows(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False, encoding="utf-8") as fh:
            fh.write(text)
        try:
            return sw.read_rows(fh.name)
        finally:
            os.unlink(fh.name)

    def test_followers_baseline_when_no_median(self):
        rows = self.rows("account\tfollowers\tviews\thook\n@x\t1,000\t5,000\tsteal this\n")
        a = sw.analyse(rows, None)
        self.assertEqual(a["baseline"], "follower count")
        self.assertEqual(a["reels"][0]["outlier"], 5.0)

    def test_headerless_rows_use_default_columns(self):
        rows = self.rows("@x\t1000\t5000\tsteal this\n")
        self.assertEqual(rows[0]["views"], 5000)
        self.assertEqual(rows[0]["followers"], 1000)

    def test_comments_blank_and_viewless_rows_skipped(self):
        rows = self.rows("account\tviews\thook\n# note\n\n@x\t\thook text\n@y\t10\thi\n")
        self.assertEqual([r["account"] for r in rows], ["@y"])

    def test_no_baseline_gives_unknown_multiple(self):
        rows = self.rows("account\tviews\thook\n@x\t10\thi there\n")
        self.assertIsNone(sw.analyse(rows, None)["reels"][0]["outlier"])


class Contract(unittest.TestCase):
    def test_empty_exits_2(self):
        proc = run_tool("swipe", "-", stdin="account\tviews\thook\n")
        self.assertEqual(proc.returncode, 2)

    def test_stdin_equals_file(self):
        a = run_tool("swipe", fixture("captured.tsv")).stdout
        b = run_tool("swipe", "-", stdin=read_fixture("captured.tsv")).stdout
        self.assertEqual(a, b)

    def test_out_writes_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nested", "swipe.md")
            proc = run_tool("swipe", fixture("captured.tsv"), "--out", path)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(path, encoding="utf-8") as fh:
                md = fh.read()
            self.assertTrue(md.startswith("# Swipe file"))
            self.assertIn("## 60.0x  The Steal  (@c)", md)

    def test_out_bare_filename_in_cwd(self):
        # Used to crash: os.makedirs("") for a path with no folder.
        with tempfile.TemporaryDirectory() as d:
            proc = run_tool("swipe", fixture("captured.tsv"), "--out", "swipe.md", cwd=d)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(os.path.exists(os.path.join(d, "swipe.md")))


class Standalone(unittest.TestCase):
    """ig-viral copied on its own must still run, just with less."""

    def test_without_ig_reel(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(os.path.join(SKILLS, "ig-viral"), os.path.join(d, "ig-viral"))
            script = os.path.join(d, "ig-viral", "swipe.py")
            proc = run_tool(script, fixture("captured.tsv"), "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("hooks.json not found", proc.stderr)
            self.assertIn("hookscore.py not importable", proc.stderr)
            a = json.loads(proc.stdout)
            self.assertTrue(all(r["hook_score"] is None for r in a["reels"]))
            self.assertTrue(all(r["formula"] == "unclassified" for r in a["reels"]))
            self.assertEqual(a["reels"][0]["account"], "@c")  # ranking survives

    def test_without_ig_reel_but_hooks_passed(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(os.path.join(SKILLS, "ig-viral"), os.path.join(d, "ig-viral"))
            script = os.path.join(d, "ig-viral", "swipe.py")
            hooks = os.path.join(SKILLS, "ig-reel", "hooks.json")
            proc = run_tool(script, fixture("captured.tsv"), "--hooks", hooks)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("#9  The Steal", proc.stdout)


if __name__ == "__main__":
    unittest.main()
