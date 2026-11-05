"""igtools is a thin front for the six tools, never a second copy of them.

The tools stay in skills/ (a lone skill folder must still run), and igtools
runs their own main(): `python3 -m igtools <tool> ...` must print what the
script prints, byte for byte, with the same exit code, and each library
function must return what the script prints with --json. The tools are read
from the source (every skills/*/*.py with a main), so a seventh tool that
igtools does not front breaks the net by name.
"""

import ast
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from _support import ROOT, SKILLS, fixture, read_fixture, run_tool

sys.path.insert(0, ROOT)
import igtools  # noqa: E402

PKG = os.path.join(ROOT, "igtools")

# (label, argv) per tool, run both as the script and through igtools.
# en and pt-BR, a verdict exit (1), and a refusal (2) for each.
RUNS = {
    "hookscore": [("strong", ["--hook", "You lose $400 a month on this", "--json"]),
                  ("pt-BR", ["--hook", "Você perde R$400 por mês nisso", "--lang", "pt-BR",
                             "--json"]),
                  ("a list", [fixture("hooks.txt"), "--json"]),
                  ("text", [fixture("hooks.txt")]),
                  ("weak", ["--hook", "some thoughts", "--json"]),
                  ("empty", ["-"]),
                  ("blank hook", ["--hook", "   ", "--json"]),
                  ("bad lang", ["--hook", "x", "--lang", "fr"])],
    "beats": [("json", [fixture("script.txt"), "--target", "30", "--json"]),
              ("pt-BR", [fixture("script.pt-BR.txt"), "--lang", "pt-BR", "--json"]),
              ("text", [fixture("script.txt")]),
              ("missing", ["/nope/missing.txt"])],
    "caption": [("json", [fixture("caption.txt"), "--keywords", "reels,hooks", "--json"]),
                ("pt-BR", [fixture("caption.pt-BR.txt"), "--lang", "pt-BR", "--json"]),
                ("text", [fixture("caption.txt")]),
                ("missing", ["/nope/missing.txt"])],
    "humanize": [("json", [fixture("bad_draft.txt"), "--json"]),
                 ("report", [fixture("bad_draft.txt"), "--report"]),
                 ("auto", [fixture("good_draft.pt-BR.txt"), "--lang", "auto", "--json"]),
                 ("bad lexicon", [fixture("bad_draft.txt"), "--lexicon", "/nope.json"])],
    "detect": [("json", [fixture("good_draft.txt"), "--json"]),
               ("pt-BR", [fixture("good_draft.pt-BR.txt"), "--lang", "pt-BR", "--json"]),
               ("before/after", [fixture("bad_draft.txt"), fixture("good_draft.txt")]),
               ("missing", ["/nope/missing.txt"])],
    "swipe": [("json", [fixture("captured.tsv"), "--json"]),
              ("pt-BR", [fixture("captured.pt-BR.tsv"), "--lang", "pt-BR", "--json"]),
              ("text", [fixture("captured.tsv")]),
              ("bad hooks", [fixture("captured.tsv"), "--hooks", "/nope.json"])],
}

# Each library function, called on a fixture, against the script's --json.
# (function, kwargs, tool, argv)
API = [
    ("score_hook", {"text": "You lose $400 a month on this"},
     "hookscore", ["--hook", "You lose $400 a month on this"]),
    ("score_hook", {"text": "Você perde R$400 por mês nisso", "lang": "pt-BR"},
     "hookscore", ["--hook", "Você perde R$400 por mês nisso", "--lang", "pt-BR"]),
    ("beat_sheet", {"script": read_fixture("script.txt"), "target": 30},
     "beats", [fixture("script.txt"), "--target", "30"]),
    ("beat_sheet", {"script": read_fixture("script.pt-BR.txt"), "wpm": 150, "lang": "pt-BR"},
     "beats", [fixture("script.pt-BR.txt"), "--wpm", "150", "--lang", "pt-BR"]),
    ("lint_caption", {"text": read_fixture("caption.txt"), "keywords": ["reels", "hooks"]},
     "caption", [fixture("caption.txt"), "--keywords", "reels,hooks"]),
    ("lint_caption", {"text": read_fixture("caption.pt-BR.txt"), "lang": "pt-BR",
                      "truncate": 90},
     "caption", [fixture("caption.pt-BR.txt"), "--lang", "pt-BR", "--truncate", "90"]),
    ("humanize", {"text": read_fixture("bad_draft.txt")},
     "humanize", [fixture("bad_draft.txt")]),
    ("humanize", {"text": read_fixture("good_draft.pt-BR.txt"), "lang": "pt-BR"},
     "humanize", [fixture("good_draft.pt-BR.txt"), "--lang", "pt-BR"]),
    ("detect", {"text": read_fixture("good_draft.txt")},
     "detect", [fixture("good_draft.txt")]),
    ("detect", {"text": read_fixture("good_draft.pt-BR.txt"), "lang": "pt-BR"},
     "detect", [fixture("good_draft.pt-BR.txt"), "--lang", "pt-BR"]),
    ("rank_swipe", {"tsv": read_fixture("captured.tsv")},
     "swipe", [fixture("captured.tsv")]),
    ("rank_swipe", {"tsv": read_fixture("captured.pt-BR.tsv"), "lang": "pt-BR"},
     "swipe", [fixture("captured.pt-BR.tsv"), "--lang", "pt-BR"]),
]


def tools_in_source():
    """{name: path} of every script under skills/ that defines main()."""
    out = {}
    for path in sorted(glob.glob(os.path.join(SKILLS, "*", "*.py"))):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        if any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body):
            out[os.path.splitext(os.path.basename(path))[0]] = path
    return out


def run_igtools(*args, cwd=ROOT, env=None, stdin=None):
    return subprocess.run([sys.executable, "-m", "igtools", *args], input=stdin,
                          capture_output=True, text=True, encoding="utf-8",
                          cwd=cwd, env=env, timeout=60)


class EveryToolIsFronted(unittest.TestCase):
    def test_igtools_fronts_every_tool_in_the_source(self):
        src = tools_in_source()
        self.assertEqual(set(igtools.TOOLS), set(src), "a tool igtools does not front")
        for name, path in src.items():
            with self.subTest(tool=name):
                self.assertEqual(os.path.realpath(igtools.path_of(name)), os.path.realpath(path))

    def test_every_tool_is_run_here(self):
        self.assertEqual(set(RUNS), set(tools_in_source()))
        self.assertEqual({tool for _, _, tool, _ in API}, set(tools_in_source()),
                         "a tool with no library function checked")

    def test_one_function_per_tool(self):
        self.assertEqual(sorted(igtools.API), sorted({f for f, _, _, _ in API}))
        self.assertEqual(set(igtools.API.values()), set(igtools.TOOLS))

    def test_schema_matches_the_tools(self):
        for name in igtools.TOOLS:
            with self.subTest(tool=name):
                self.assertEqual(igtools.load(name).SCHEMA, igtools.SCHEMA)


class CliIsTheScript(unittest.TestCase):
    def test_same_stdout_stderr_and_exit(self):
        for tool, runs in RUNS.items():
            for label, argv in runs:
                with self.subTest(tool=tool, run=label):
                    want = run_tool(tool, *argv, stdin="")
                    got = run_igtools(tool, *argv, stdin="")
                    self.assertNotIn("Traceback", got.stderr)
                    self.assertEqual(got.returncode, want.returncode, got.stderr)
                    self.assertEqual(got.stdout, want.stdout)
                    # argparse names the program, and wraps its usage line by
                    # the name's length: the one difference allowed.
                    script = os.path.basename(igtools.path_of(tool))
                    got_err = got.stderr.replace(f"igtools {tool}", script)
                    if want.stderr.startswith("usage:"):
                        got_err, want_err = " ".join(got_err.split()), " ".join(want.stderr.split())
                    else:
                        want_err = want.stderr
                    self.assertEqual(got_err, want_err)

    def test_the_runs_hit_every_exit_code(self):
        codes = {}
        for tool, runs in RUNS.items():
            for _, argv in runs:
                codes.setdefault(tool, set()).add(run_tool(tool, *argv, stdin="").returncode)
        for tool, seen in codes.items():
            with self.subTest(tool=tool):
                self.assertIn(0, seen)
                self.assertIn(2, seen)

    def test_no_tool_or_unknown_tool_is_exit_2(self):
        for argv in ([], ["nope"], ["--json"]):
            with self.subTest(argv=argv):
                proc = run_igtools(*argv)
                self.assertEqual(proc.returncode, 2)
                self.assertNotIn("Traceback", proc.stderr)
                for name in igtools.TOOLS:
                    self.assertIn(name, proc.stderr)

    def test_help_is_exit_0(self):
        proc = run_igtools("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("hookscore", proc.stdout)

    def test_a_tool_help_names_igtools(self):
        proc = run_igtools("caption", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("igtools caption", proc.stdout)


class LibraryIsTheJson(unittest.TestCase):
    def test_each_function_returns_the_scripts_json(self):
        for fn, kwargs, tool, argv in API:
            with self.subTest(fn=fn, lang=kwargs.get("lang", "en")):
                want = json.loads(run_tool(tool, *argv, "--json").stdout)
                got = getattr(igtools, fn)(**kwargs)
                if tool == "detect":         # the text came on stdin: its source is "-"
                    self.assertEqual(got.pop("source"), "-")
                    want.pop("source")
                self.assertEqual(got, want)

    def test_the_process_is_left_as_it_was(self):
        before = (sys.argv[:], sys.stdin, sys.stdout, sys.stderr)
        igtools.score_hook("You lose $400 a month on this")
        with self.assertRaises(igtools.Error):
            igtools.score_hook("")
        self.assertEqual((sys.argv, sys.stdin, sys.stdout, sys.stderr), before)

    def test_a_refusal_is_an_error_with_the_message(self):
        cases = [("score_hook", {"text": "   "}, "nothing"),
                 ("score_hook", {"text": "x", "lang": "fr"}, "fr"),
                 ("beat_sheet", {"script": ""}, ""),
                 ("rank_swipe", {"tsv": ""}, ""),
                 ("humanize", {"text": "x", "lexicon": "/nope.json"}, "/nope.json"),
                 ("detect", {"text": "x", "lexicon": "/nope.json"}, "/nope.json")]
        for fn, kwargs, needle in cases:
            with self.subTest(fn=fn, kwargs=kwargs):
                with self.assertRaises(igtools.Error) as ctx:
                    getattr(igtools, fn)(**kwargs)
                self.assertEqual(ctx.exception.code, 2)
                self.assertTrue(str(ctx.exception).strip())
                self.assertIn(needle, str(ctx.exception))
                self.assertNotIn("Traceback", str(ctx.exception))

    def test_a_verdict_is_not_an_error(self):
        # Exit 1 is a verdict: the dict comes back and says so.
        self.assertEqual(igtools.score_hook("some thoughts")["verdict"], "WEAK")
        self.assertNotEqual(igtools.lint_caption(read_fixture("caption.txt"))["verdict"], "READY")

    def test_a_hook_that_looks_like_a_flag_is_text(self):
        self.assertEqual(igtools.score_hook("--json")["hook"], "--json")

    def test_a_keyword_with_a_comma_is_refused(self):
        with self.assertRaises(ValueError):
            igtools.lint_caption("x", keywords=["a,b"])

    def test_nfd_input_gives_the_nfc_result(self):
        import unicodedata
        text = "Você perde R$400 por mês nisso"
        self.assertEqual(igtools.score_hook(unicodedata.normalize("NFD", text), lang="pt-BR"),
                         igtools.score_hook(text, lang="pt-BR"))


class Vendored(unittest.TestCase):
    """The copy a program carries: igtools/ and skills/ under one folder."""

    def copy(self, d, with_skills=True):
        root = os.path.join(d, "vendor")
        shutil.copytree(PKG, os.path.join(root, "igtools"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        if with_skills:
            shutil.copytree(SKILLS, os.path.join(root, "skills"),
                            ignore=shutil.ignore_patterns("__pycache__"))
        return root

    def test_runs_from_another_cwd_with_pythonpath(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.copy(d)
            env = dict(os.environ, PYTHONPATH=root)
            proc = run_igtools("hookscore", "--hook", "Você perde R$400 por mês nisso",
                               "--lang", "pt-BR", "--json", cwd=d, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["schema"], igtools.SCHEMA)

    def test_without_skills_is_exit_2_naming_the_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = self.copy(d, with_skills=False)
            env = dict(os.environ, PYTHONPATH=root)
            proc = run_igtools("caption", fixture("caption.txt"), "--json", cwd=d, env=env)
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertIn(os.path.join("skills", "ig-caption", "caption.py"), proc.stderr)


if __name__ == "__main__":
    unittest.main()
