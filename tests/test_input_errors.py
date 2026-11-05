"""A path the user gives that cannot be read or written is exit 2, never a verdict.

Exit 1 is a verdict (hookscore: best hook < 70; caption: not READY; detect: not
PASS), so a skill reads a traceback from a missing file as "your hook is weak".
The class is "every argument that names a file", which no grep can list: the
arguments are enumerated from each script's argparse (AST), every one of them is
declared here as a path (read or write) or not a path with its reason, and an
argument nobody declared breaks the net by name. Every path argument is then run
against hostile files: missing, a directory, bytes that are not UTF-8, and for
writes a folder that cannot be made. Each must be exit 2, name the path on
stderr, and print no traceback. stdin ("-") gets the non-UTF-8 case too.
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from _support import FIXTURES, TOOLS, fixture, run_tool

TSV = fixture("captured.tsv")
TEXT = fixture("bad_draft.txt")

# Every argparse dest of every tool. "read"/"write": a path; anything else is
# the reason the argument is not a path. Checked both ways against the source.
ARGS = {
    "hookscore": {"input": "read", "hook": "the hook text itself", "json": "flag",
                  "lang": "choices"},
    "beats": {"input": "read", "wpm": "number", "target": "number", "json": "flag",
              "lang": "choices"},
    "caption": {"input": "read", "truncate": "number", "keywords": "comma-separated terms",
                "json": "flag", "lang": "choices"},
    "humanize": {"input": "read", "out": "write", "report": "flag", "json": "flag",
                 "lexicon": "read", "lang": "choices"},
    "detect": {"input": "read", "compare": "read", "json": "flag", "lexicon": "read",
               "lang": "choices"},
    "swipe": {"input": "read", "hooks": "read", "out": "write", "json": "flag",
              "lang": "choices"},
}

# How to put a path in each argument: the argv around it ({p} = the path).
# Other arguments are a working input, so only the one under test can fail.
ARGV = {
    ("hookscore", "input"): ["{p}"],
    ("beats", "input"): ["{p}"],
    ("caption", "input"): ["{p}"],
    ("humanize", "input"): ["{p}"],
    ("humanize", "out"): [TEXT, "-o", "{p}"],
    ("humanize", "lexicon"): [TEXT, "--lexicon", "{p}"],
    ("detect", "input"): ["{p}"],
    ("detect", "compare"): [TEXT, "{p}"],
    ("detect", "lexicon"): [TEXT, "--lexicon", "{p}"],
    ("swipe", "input"): ["{p}"],
    ("swipe", "hooks"): [TSV, "--hooks", "{p}"],
    ("swipe", "out"): [TSV, "--out", "{p}"],
}


def argparse_dests(path):
    """dest of every ap.add_argument(...) in the script, as argparse derives it."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    dests = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            names = [a.value for a in node.args if isinstance(a, ast.Constant)]
            explicit = [k.value.value for k in node.keywords if k.arg == "dest"]
            long = [n for n in names if n.startswith("--")]
            name = explicit[0] if explicit else (long or names)[0].lstrip("-")
            dests.append(name.replace("-", "_"))
    return dests


def hostile_reads(d):
    """(label, path) for files that cannot be read as text."""
    bad = os.path.join(d, "latin1.txt")
    with open(bad, "wb") as fh:
        fh.write(b"caf\xe9 \xff\xfe hook\n")
    return [("missing", os.path.join(d, "nope", "missing.txt")),
            ("directory", d),
            ("not utf-8", bad)]


def hostile_writes(d):
    """(label, path) for places that cannot be written."""
    blocker = os.path.join(d, "a_file")
    with open(blocker, "w", encoding="utf-8") as fh:
        fh.write("x")
    return [("directory", d),
            ("parent is a file", os.path.join(blocker, "out.md"))]


class EveryPathArgumentIsDeclared(unittest.TestCase):
    def test_argparse_matches_the_declaration(self):
        self.assertEqual(set(ARGS), set(TOOLS), "a tool missing from ARGS")
        for tool, path in TOOLS.items():
            with self.subTest(tool=tool):
                found = argparse_dests(path)
                undeclared = [a for a in found if a not in ARGS[tool]]
                self.assertEqual(undeclared, [], f"{tool}: argument(s) not declared in ARGS")
                stale = [a for a in ARGS[tool] if a not in found]
                self.assertEqual(stale, [], f"{tool}: ARGS lists argument(s) the script lacks")

    def test_every_path_argument_has_a_case(self):
        for tool, args in ARGS.items():
            for arg, kind in args.items():
                if kind in ("read", "write"):
                    self.assertIn((tool, arg), ARGV, f"{tool} {arg}: path argument with no case")
        for key in ARGV:
            self.assertIn(ARGS[key[0]].get(key[1]), ("read", "write"), f"stale ARGV {key}")

    def test_the_dest_reader_sees_a_new_argument(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "t.py")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write('ap.add_argument("input")\nap.add_argument("-o", "--out-file")\n'
                         'ap.add_argument("--x", dest="why")\n')
            self.assertEqual(argparse_dests(src), ["input", "out_file", "why"])


class BadPathIsExitTwo(unittest.TestCase):
    def assert_clean_failure(self, proc, path, what):
        self.assertEqual(proc.returncode, 2, f"{what}: exit {proc.returncode}\n{proc.stderr}")
        self.assertNotIn("Traceback", proc.stderr, what)
        self.assertIn(path, proc.stderr, f"{what}: the path is not named")

    def test_every_path_argument(self):
        for (tool, arg), around in ARGV.items():
            kind = ARGS[tool][arg]
            with tempfile.TemporaryDirectory() as d:
                cases = hostile_reads(d) if kind == "read" else hostile_writes(d)
                for label, path in cases:
                    with self.subTest(tool=tool, arg=arg, case=label):
                        argv = [path if a == "{p}" else a for a in around]
                        proc = run_tool(tool, *argv)
                        self.assert_clean_failure(proc, path, f"{tool} {arg} {label}")

    def test_stdin_that_is_not_utf8(self):
        for tool in TOOLS:
            with self.subTest(tool=tool):
                proc = subprocess.run([sys.executable, TOOLS[tool], "-"],
                                      input=b"caf\xe9 \xff hook\n", capture_output=True,
                                      timeout=60)
                err = proc.stderr.decode("utf-8", "replace")
                self.assertEqual(proc.returncode, 2, f"{tool}: exit {proc.returncode}\n{err}")
                self.assertNotIn("Traceback", err, tool)
                self.assertIn("stdin", err, tool)


class WriteIsHonouredInEveryMode(unittest.TestCase):
    """An output path is written whatever else is asked for. `humanize --json -o x`
    used to print the JSON and never write x, exit 0 even when x could not be
    written: a guard that failed open. The modes are each tool's "flag" arguments
    from ARGS (itself checked against argparse), so a new flag joins the net."""

    def modes(self, tool):
        return [[]] + [["--" + a.replace("_", "-")] for a, k in ARGS[tool].items()
                       if k == "flag"]

    def test_the_file_is_written(self):
        for (tool, arg), around in ARGV.items():
            if ARGS[tool][arg] != "write":
                continue
            for mode in self.modes(tool):
                with self.subTest(tool=tool, arg=arg, mode=mode), \
                        tempfile.TemporaryDirectory() as d:
                    path = os.path.join(d, "out.txt")
                    argv = [path if a == "{p}" else a for a in around] + mode
                    proc = run_tool(tool, *argv)
                    self.assertIn(proc.returncode, (0, 1), proc.stderr)
                    self.assertTrue(os.path.isfile(path), f"{tool} {mode}: {path} not written")
                    with open(path, encoding="utf-8") as fh:
                        self.assertTrue(fh.read().strip(), f"{tool} {mode}: empty file")

    def test_a_bad_path_is_exit_two(self):
        for (tool, arg), around in ARGV.items():
            if ARGS[tool][arg] != "write":
                continue
            for mode in self.modes(tool):
                with tempfile.TemporaryDirectory() as d:
                    for label, path in hostile_writes(d):
                        with self.subTest(tool=tool, arg=arg, mode=mode, case=label):
                            argv = [path if a == "{p}" else a for a in around] + mode
                            proc = run_tool(tool, *argv)
                            self.assertEqual(proc.returncode, 2,
                                             f"{tool} {mode} {label}: exit {proc.returncode}")
                            self.assertIn(path, proc.stderr)
                            self.assertNotIn("Traceback", proc.stderr)


class DefaultHooksStillDegrades(unittest.TestCase):
    """A missing ig-reel next to ig-viral is a lone copy, not a user error: the
    default hooks.json path keeps degrading. Only an explicit --hooks fails."""

    def test_broken_default_hooks_degrades(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(os.path.join(os.path.dirname(TOOLS["swipe"])),
                            os.path.join(d, "ig-viral"))
            os.makedirs(os.path.join(d, "ig-reel"))
            with open(os.path.join(d, "ig-reel", "hooks.json"), "w", encoding="utf-8") as fh:
                fh.write('{"hooks": [{"name": "no id"}]}')
            proc = run_tool(os.path.join(d, "ig-viral", "swipe.py"), TSV, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
